"""
ETL validation routines.

These checks are intentionally lightweight but aligned with the
Phase 1 schema and ETL design. They are meant to be run after a
full load and will raise a RuntimeError on failure.

Checks:
- Foreign key integrity for key relationships (best-effort via queries).
- Player-season hub/satellite consistency.
- Team-season hub/satellite consistency.
- Games and boxscore_team integrity.
- PBP integrity (basic).
- Awards/draft referential sanity.
"""

from __future__ import annotations

from typing import Iterable

from psycopg import Connection

from .logging_utils import get_logger, log_structured

logger = get_logger(__name__)


def _run_count_query(conn: Connection, sql: str) -> int:
    with conn.cursor() as cur:
        cur.execute(sql)
        row = cur.fetchone()
        return int(row[0]) if row and row[0] is not None else 0


def _fail_if_any(conn: Connection, sql: str, message: str) -> None:
    cnt = _run_count_query(conn, sql)
    if cnt > 0:
        raise RuntimeError(f"Validation failed: {message} (count={cnt})")
    log_structured(logger, logger.level, "Validation passed", check=message, count=cnt)


def check_fk_integrity(conn: Connection) -> None:
    """
    Core FK-like validations using COUNT queries.
    These mirror declared FKs and key relationships.
    """
    # games.home_team_id / away_team_id -> teams
    _fail_if_any(
        conn,
        """
        SELECT COUNT(*)
        FROM games g
        LEFT JOIN teams th ON g.home_team_id = th.team_id
        WHERE g.home_team_id IS NOT NULL AND th.team_id IS NULL
        """,
        "games.home_team_id missing in teams",
    )
    _fail_if_any(
        conn,
        """
        SELECT COUNT(*)
        FROM games g
        LEFT JOIN teams ta ON g.away_team_id = ta.team_id
        WHERE g.away_team_id IS NOT NULL AND ta.team_id IS NULL
        """,
        "games.away_team_id missing in teams",
    )

    # boxscore_team.game_id -> games, team_id/opponent_team_id -> teams
    _fail_if_any(
        conn,
        """
        SELECT COUNT(*)
        FROM boxscore_team bt
        LEFT JOIN games g ON bt.game_id = g.game_id
        WHERE g.game_id IS NULL
        """,
        "boxscore_team.game_id missing in games",
    )
    _fail_if_any(
        conn,
        """
        SELECT COUNT(*)
        FROM boxscore_team bt
        LEFT JOIN teams t ON bt.team_id = t.team_id
        WHERE bt.team_id IS NOT NULL AND t.team_id IS NULL
        """,
        "boxscore_team.team_id missing in teams",
    )

    # pbp_events.game_id -> games
    _fail_if_any(
        conn,
        """
        SELECT COUNT(*)
        FROM pbp_events p
        LEFT JOIN games g ON p.game_id = g.game_id
        WHERE g.game_id IS NULL
        """,
        "pbp_events.game_id missing in games",
    )

    # inactive_players -> games, players
    _fail_if_any(
        conn,
        """
        SELECT COUNT(*)
        FROM inactive_players ip
        LEFT JOIN games g ON ip.game_id = g.game_id
        WHERE g.game_id IS NULL
        """,
        "inactive_players.game_id missing in games",
    )
    _fail_if_any(
        conn,
        """
        SELECT COUNT(*)
        FROM inactive_players ip
        LEFT JOIN players p ON ip.player_id = p.player_id
        WHERE p.player_id IS NULL
        """,
        "inactive_players.player_id missing in players",
    )


def check_player_season_consistency(conn: Connection) -> None:
    """
    Validate player_season hub and satellites.
    """
    # Satellites must have matching hub row
    for table in [
        "player_season_per_game",
        "player_season_totals",
        "player_season_per36",
        "player_season_per100",
        "player_season_advanced",
    ]:
        _fail_if_any(
            conn,
            f"""
            SELECT COUNT(*)
            FROM {table} s
            LEFT JOIN player_season ps ON s.seas_id = ps.seas_id
            WHERE ps.seas_id IS NULL
            """,
            f"{table}.seas_id missing in player_season",
        )

    # TOT rows: is_total implies team_id IS NULL and team_abbrev = 'TOT'
    _fail_if_any(
        conn,
        """
        SELECT COUNT(*)
        FROM player_season
        WHERE is_total = TRUE
          AND (team_id IS NOT NULL OR team_abbrev <> 'TOT')
        """,
        "player_season TOT rows not normalized correctly",
    )

    # League-average rows: is_league_average implies team_id IS NULL
    _fail_if_any(
        conn,
        """
        SELECT COUNT(*)
        FROM player_season
        WHERE is_league_average = TRUE
          AND team_id IS NOT NULL
        """,
        "player_season league-average rows not normalized correctly",
    )


def check_team_season_consistency(conn: Connection) -> None:
    """
    Validate team_season hub and satellites.
    """
    # Satellites must have matching hub row
    for table in [
        "team_season_totals",
        "team_season_per_game",
        "team_season_per100",
        "team_season_opponent_totals",
        "team_season_opponent_per_game",
        "team_season_opponent_per100",
    ]:
        _fail_if_any(
            conn,
            f"""
            SELECT COUNT(*)
            FROM {table} s
            LEFT JOIN team_season ts ON s.team_season_id = ts.team_season_id
            WHERE ts.team_season_id IS NULL
            """,
            f"{table}.team_season_id missing in team_season",
        )

    # team_season uniqueness constraint semantics:
    # (team_id, season_end_year, is_playoffs=false) unique where team_id not null
    _fail_if_any(
        conn,
        """
        SELECT COUNT(*)
        FROM (
          SELECT team_id, season_end_year, is_playoffs, COUNT(*) c
          FROM team_season
          WHERE team_id IS NOT NULL
          GROUP BY team_id, season_end_year, is_playoffs
          HAVING COUNT(*) > 1
        ) d
        """,
        "Duplicate team_season rows for same team/season/scope",
    )


def check_games_integrity(conn: Connection) -> None:
    """
    Validate games and boxscore_team consistency.
    """
    # Each game should have at most 2 boxscore_team rows (home/away)
    _fail_if_any(
        conn,
        """
        SELECT COUNT(*)
        FROM (
          SELECT game_id, COUNT(*) c
          FROM boxscore_team
          GROUP BY game_id
          HAVING COUNT(*) > 2
        ) x
        """,
        "Games with more than 2 boxscore_team rows",
    )

    # boxscore_team PK uniqueness
    _fail_if_any(
        conn,
        """
        SELECT COUNT(*)
        FROM (
          SELECT game_id, team_id, COUNT(*) c
          FROM boxscore_team
          GROUP BY game_id, team_id
          HAVING COUNT(*) > 1
        ) x
        """,
        "Duplicate boxscore_team (game_id, team_id) rows",
    )


def check_awards_and_draft(conn: Connection) -> None:
    """
    Sanity checks for awards and draft tables.
    These are soft checks (no FK constraints enforced here).
    """
    # Ensure awards/draft do not reference obviously missing players when ids are present.
    _fail_if_any(
        conn,
        """
        SELECT COUNT(*)
        FROM awards_player_shares a
        LEFT JOIN players p ON a.player_id = p.player_id
        WHERE a.player_id IS NOT NULL AND p.player_id IS NULL
        """,
        "awards_player_shares.player_id missing in players",
    )
    _fail_if_any(
        conn,
        """
        SELECT COUNT(*)
        FROM draft_picks d
        LEFT JOIN players p ON d.player_id = p.player_id
        WHERE d.player_id IS NOT NULL AND p.player_id IS NULL
        """,
        "draft_picks.player_id missing in players",
    )


def run_all_validations(conn: Connection) -> None:
    """
    Run all validation checks; raise on first failure.
    """
    checks: Iterable = [
        check_fk_integrity,
        check_player_season_consistency,
        check_team_season_consistency,
        check_games_integrity,
        check_awards_and_draft,
    ]
    for fn in checks:
        log_structured(
            logger,
            logger.level,
            "Running validation",
            check=fn.__name__,
        )
        fn(conn)
    log_structured(logger, logger.level, "All validations passed")
