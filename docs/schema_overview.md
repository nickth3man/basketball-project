# Schema Overview (Phase 1)

This schema models a Basketball-Reference/Stathead-style warehouse with clean, stable keys and season-level hubs suitable for box scores, advanced stats, and awards.

Core entities:
- `players`: Canonical player dimension keyed by `player_id` (numeric, NBA-style person_id). Text slugs and bio data are attributes; `player_aliases` stores alternate names/slugs keyed back to `players`.
- `teams`: Canonical team dimension keyed by `team_id` (including historical/defunct franchises). `team_history` tracks season-specific naming/locational changes; `team_abbrev_mappings` normalizes raw abbreviations to `team_id`.
- `seasons`: Canonical season dimension keyed by `season_id`, with `season_end_year` and league metadata.

Games and box scores:
- `games` uses `game_id` as the global key across all game-related data. It links to `seasons` and `teams` (home/away), with BRIN indexing on `game_date_est` for efficient chronological access.
- `boxscore_team` has one row per (`game_id`, `team_id`), combining team-level line score and efficiency stats, including `is_home` and `opponent_team_id`.
- `boxscore_player` has one row per (`game_id`, `player_id`, `team_id`), ready for granular player box scores.

Player-season modeling:
- `player_season` is the central hub keyed by `seas_id`, representing one player-season-team context with links to `players`, `teams`, and `seasons`.
- Special policies:
  - TOT rows: modeled as distinct `seas_id` with `is_total = true`, `team_id` NULL, and `team_abbrev = 'TOT'`.
  - League averages: modeled with `team_id` NULL and `is_league_average = true`.
- Satellite tables (`player_season_per_game`, `player_season_totals`, `player_season_per36`, `player_season_per100`, `player_season_advanced`) are 1:1 with `player_season` via `seas_id`, storing derived and advanced statistics.

Team-season modeling:
- `team_season` represents one team-season (and scope) keyed by `team_season_id`, linked to `teams` and `seasons`, with flags for playoffs and league-average rows.
- Satellites (`team_season_totals`, `team_season_per_game`, `team_season_per100`, `team_season_opponent_totals`, `team_season_opponent_per_game`, `team_season_opponent_per100`) attach aggregated, rate, and opponent metrics via `team_season_id`.

Play-by-play and availability:
- `pbp_events` is keyed by (`game_id`, `eventnum`) and references `players`/`teams` where available, BRIN-indexed on `game_id` for large-scale queries.
- `inactive_players` tracks one row per (`game_id`, `player_id`) for official inactives.

Awards and draft:
- `awards_all_star_selections`, `awards_player_shares`, `awards_end_of_season_teams`, and `awards_end_of_season_voting` primarily reference `player_id` (and `team_id` when applicable) plus season fields, aligning votes/teams with the core dimensions.
- `draft_picks` records draft selections keyed to `player_id` and `team_id` when resolvable.

Metadata:
- `data_versions` and `etl_runs` record source versions and pipeline executions to ensure data lineage and reproducibility across loads.