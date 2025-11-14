"""
load_team_dimension.py

Type 2 Slowly Changing Dimension ETL for team_info_common table.

This is a MINIMAL IMPLEMENTATION stub demonstrating the Type 2 SCD pattern.
For production use, this should be expanded with:
- nba_api integration for FranchiseHistory data
- Automated change detection logic
- Full validation suite

Current Focus: Bootstrap with known relocations/rebrandings

Convention Alignment:
- Seattle SuperSonics (1967-2008, team_id 1610612760) → OKC Thunder  
  (2008-present, same team_id)
- Charlotte: Original Hornets (1988-2002) + Bobcats→Hornets (2014-present)
  with history reclamation
"""

from __future__ import annotations

from psycopg import Connection

from .config import Config
from .db import get_connection
from .logging_utils import get_logger

logger = get_logger(__name__)


def load_team_dimension(config: Config, conn: Connection) -> None:
    """
    Load initial Type 2 SCD versions for known team transitions.
    
    This bootstrap version inserts foundational dimension records for:
    - Seattle SuperSonics → OKC Thunder (team_id 1610612760)
    - Charlotte Bobcats → Hornets (team_id 1610612751)
    
    Future iterations will:
    1. Pull from nba_api FranchiseHistory endpoint
    2. Detect changes dynamically
    3. Handle all 30 franchises
    
    Args:
        config: ETL configuration
        conn: PostgreSQL connection
    """
    logger.info("=" * 80)
    logger.info("Loading Team Dimension (Type 2 SCD)")
    logger.info("=" * 80)
    
    # Bootstrap: Insert known relocations/rebrandings
    known_versions = [
        # Seattle SuperSonics → OKC Thunder (same team_id across relocation)
        {
            "team_id": 1610612760,
            "season_year": "1967-68",
            "team_city": "Seattle",
            "team_name": "SuperSonics",
            "team_abbreviation": "SEA",
            "effective_start_date": "1967-10-13",
            "effective_end_date": "2008-06-30",
            "is_current": False,
            "change_reason": None,  # Initial version
        },
        {
            "team_id": 1610612760,
            "season_year": "2008-09",
            "team_city": "Oklahoma City",
            "team_name": "Thunder",
            "team_abbreviation": "OKC",
            "effective_start_date": "2008-07-01",
            "effective_end_date": "9999-12-31",
            "is_current": True,
            "change_reason": "relocation",
        },
        # Charlotte Bobcats → Hornets (rebranding)
        {
            "team_id": 1610612751,
            "season_year": "2004-05",
            "team_city": "Charlotte",
            "team_name": "Bobcats",
            "team_abbreviation": "CHA",
            "effective_start_date": "2004-11-04",
            "effective_end_date": "2014-05-20",
            "is_current": False,
            "change_reason": None,  # Expansion team
        },
        {
            "team_id": 1610612751,
            "season_year": "2014-15",
            "team_city": "Charlotte",
            "team_name": "Hornets",
            "team_abbreviation": "CHO",
            "effective_start_date": "2014-10-29",
            "effective_end_date": "9999-12-31",
            "is_current": True,
            "change_reason": "rebranding",
        },
    ]
    
    insert_query = """
        INSERT INTO team_info_common (
            team_id, season_year, team_city, team_name, team_abbreviation,
            effective_start_date, effective_end_date, is_current, change_reason
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (team_id, effective_start_date) DO NOTHING
        RETURNING team_surrogate_key
    """
    
    with conn.cursor() as cur:
        for version in known_versions:
            cur.execute(
                insert_query,
                (
                    version["team_id"],
                    version["season_year"],
                    version["team_city"],
                    version["team_name"],
                    version["team_abbreviation"],
                    version["effective_start_date"],
                    version["effective_end_date"],
                    version["is_current"],
                    version["change_reason"],
                ),
            )
            row = cur.fetchone()
            if row:
                surrogate_key = row[0]
                logger.info(
                    f"Inserted team dimension version: "
                    f"team_id={version['team_id']}, "
                    f"surrogate_key={surrogate_key}, "
                    f"season={version['season_year']}, "
                    f"city={version['team_city']}, "
                    f"name={version['team_name']}"
                )
    
    conn.commit()
    logger.info("Team dimension bootstrap complete")


def lookup_team_surrogate_key(
    conn: Connection, team_id: int, as_of_date: str
) -> int | None:
    """
    Lookup team_surrogate_key for a given team_id and date.
    
    Used by fact table loaders (games, boxscores) to resolve FK references.
    
    Args:
        conn: PostgreSQL connection
        team_id: NBA natural key
        as_of_date: Date to lookup (game date, format: YYYY-MM-DD)
    
    Returns:
        team_surrogate_key if found, None otherwise
    
    Example:
        # Get surrogate key for OKC Thunder game on 2010-01-15
        surrogate_key = lookup_team_surrogate_key(conn, 1610612760, '2010-01-15')
        # Returns: team_surrogate_key for OKC Thunder version (effective 2008-07-01+)
        
        # Get surrogate key for Seattle SuperSonics game on 2005-03-20
        surrogate_key = lookup_team_surrogate_key(conn, 1610612760, '2005-03-20')
        # Returns: team_surrogate_key for Seattle SuperSonics version (1967-2008)
    """
    query = """
        SELECT team_surrogate_key
        FROM team_info_common
        WHERE team_id = %s
          AND effective_start_date <= %s
          AND effective_end_date >= %s
        LIMIT 1
    """
    
    with conn.cursor() as cur:
        cur.execute(query, (team_id, as_of_date, as_of_date))
        row = cur.fetchone()
        return row[0] if row else None


def validate_team_dimension(conn: Connection) -> int:
    """
    Validate Type 2 SCD temporal consistency.
    
    Checks:
    1. Each team_id has exactly one is_current=TRUE record
    2. No temporal gaps between dimension versions
    3. FK integrity to teams table
    
    Args:
        conn: PostgreSQL connection
    
    Returns:
        Number of validation errors found (0 = success)
    """
    errors = []
    
    # Rule 1: Exactly one is_current=TRUE per team_id
    query_current = """
        SELECT team_id, COUNT(*) as current_count
        FROM team_info_common
        WHERE is_current = TRUE
        GROUP BY team_id
        HAVING COUNT(*) != 1
    """
    
    with conn.cursor() as cur:
        cur.execute(query_current)
        for team_id, count in cur.fetchall():
            errors.append(
                f"team_id {team_id} has {count} current records (expected 1)"
            )
    
    # Rule 2: No temporal gaps
    query_gaps = """
        WITH versions AS (
            SELECT 
                team_id,
                effective_end_date,
                LEAD(effective_start_date) OVER (
                    PARTITION BY team_id ORDER BY effective_start_date
                ) AS next_start_date
            FROM team_info_common
            WHERE is_current = FALSE
        )
        SELECT team_id, effective_end_date, next_start_date
        FROM versions
        WHERE next_start_date IS NOT NULL
          AND effective_end_date + INTERVAL '1 day' != next_start_date
    """
    
    with conn.cursor() as cur:
        cur.execute(query_gaps)
        for team_id, end_date, next_start in cur.fetchall():
            errors.append(
                f"team_id {team_id} has temporal gap: "
                f"version ends {end_date}, next starts {next_start}"
            )
    
    # Rule 3: FK integrity
    query_fk = """
        SELECT DISTINCT team_id
        FROM team_info_common
        WHERE team_id NOT IN (SELECT team_id FROM teams)
    """
    
    with conn.cursor() as cur:
        cur.execute(query_fk)
        for (team_id,) in cur.fetchall():
            errors.append(
                f"team_id {team_id} in team_info_common but not in teams table"
            )
    
    if errors:
        logger.error(f"Validation failed with {len(errors)} errors:")
        for error in errors:
            logger.error(f"  - {error}")
    else:
        logger.info("Validation passed: temporal consistency OK")
    
    return len(errors)


if __name__ == "__main__":
    from .config import Config
    
    config = Config.from_env()
    conn = get_connection(config)
    
    try:
        load_team_dimension(config, conn)
        error_count = validate_team_dimension(conn)
        exit(error_count)
    finally:
        conn.close()
