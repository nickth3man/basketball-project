-- 003_games_table_surrogate_keys.sql
-- Update games and boxscore tables to use team_surrogate_key FK
--
-- Strategy:
-- - Add new columns for surrogate keys alongside existing natural keys
-- - Keep natural keys (home_team_id, away_team_id) for compatibility
-- - Migrate to surrogate keys gradually (Phase 1: add columns, Phase 2: populate, Phase 3: enforce)
-- 
-- This allows:
-- 1. Backward compatibility during transition
-- 2. Data validation before enforcing constraints
-- 3. Incremental migration

-----------------------
-- PHASE 1: ADD SURROGATE KEY COLUMNS
-----------------------

ALTER TABLE games 
    ADD COLUMN home_team_surrogate_key INTEGER REFERENCES team_info_common(team_surrogate_key),
    ADD COLUMN away_team_surrogate_key INTEGER REFERENCES team_info_common(team_surrogate_key);

ALTER TABLE boxscore_team
    ADD COLUMN team_surrogate_key INTEGER REFERENCES team_info_common(team_surrogate_key),
    ADD COLUMN opponent_team_surrogate_key INTEGER REFERENCES team_info_common(team_surrogate_key);

ALTER TABLE boxscore_player
    ADD COLUMN team_surrogate_key_fk INTEGER REFERENCES team_info_common(team_surrogate_key);

-----------------------
-- PHASE 2: POPULATE SURROGATE KEYS (from natural keys + game_date)
-----------------------

-- Games table: home team
UPDATE games SET home_team_surrogate_key = (
    SELECT team_surrogate_key
    FROM team_info_common
    WHERE team_id = games.home_team_id
      AND effective_start_date <= games.game_date_est
      AND effective_end_date >= games.game_date_est
    LIMIT 1
)
WHERE home_team_id IS NOT NULL;

-- Games table: away team
UPDATE games SET away_team_surrogate_key = (
    SELECT team_surrogate_key
    FROM team_info_common
    WHERE team_id = games.away_team_id
      AND effective_start_date <= games.game_date_est
      AND effective_end_date >= games.game_date_est
    LIMIT 1
)
WHERE away_team_id IS NOT NULL;

-- Boxscore_team: team
UPDATE boxscore_team SET team_surrogate_key = (
    SELECT tic.team_surrogate_key
    FROM team_info_common tic
    JOIN games g ON g.game_id = boxscore_team.game_id
    WHERE tic.team_id = boxscore_team.team_id
      AND tic.effective_start_date <= g.game_date_est
      AND tic.effective_end_date >= g.game_date_est
    LIMIT 1
)
WHERE team_id IS NOT NULL;

-- Boxscore_team: opponent
UPDATE boxscore_team SET opponent_team_surrogate_key = (
    SELECT tic.team_surrogate_key
    FROM team_info_common tic
    JOIN games g ON g.game_id = boxscore_team.game_id
    WHERE tic.team_id = boxscore_team.opponent_team_id
      AND tic.effective_start_date <= g.game_date_est
      AND tic.effective_end_date >= g.game_date_est
    LIMIT 1
)
WHERE opponent_team_id IS NOT NULL;

-- Boxscore_player: team
UPDATE boxscore_player SET team_surrogate_key_fk = (
    SELECT tic.team_surrogate_key
    FROM team_info_common tic
    JOIN games g ON g.game_id = boxscore_player.game_id
    WHERE tic.team_id = boxscore_player.team_id
      AND tic.effective_start_date <= g.game_date_est
      AND tic.effective_end_date >= g.game_date_est
    LIMIT 1
)
WHERE team_id IS NOT NULL;

-----------------------
-- INDEXES FOR PERFORMANCE
-----------------------

-- Games table surrogate key lookups
CREATE INDEX games_home_team_surrogate_idx ON games (home_team_surrogate_key);
CREATE INDEX games_away_team_surrogate_idx ON games (away_team_surrogate_key);

-- Boxscore surrogate key lookups
CREATE INDEX boxscore_team_surrogate_idx ON boxscore_team (team_surrogate_key);
CREATE INDEX boxscore_team_opponent_surrogate_idx 
    ON boxscore_team (opponent_team_surrogate_key);
CREATE INDEX boxscore_player_team_surrogate_idx 
    ON boxscore_player (team_surrogate_key_fk);

-----------------------
-- VALIDATION QUERIES
-----------------------

-- Check NULL surrogate keys (should be 0 after population)
-- Uncomment to run validation:
-- SELECT 'games.home_team_surrogate_key NULLs' AS check_type, 
--        COUNT(*) AS null_count
-- FROM games WHERE home_team_id IS NOT NULL AND home_team_surrogate_key IS NULL
-- UNION ALL
-- SELECT 'games.away_team_surrogate_key NULLs', COUNT(*)
-- FROM games WHERE away_team_id IS NOT NULL AND away_team_surrogate_key IS NULL
-- UNION ALL
-- SELECT 'boxscore_team.team_surrogate_key NULLs', COUNT(*)
-- FROM boxscore_team WHERE team_id IS NOT NULL AND team_surrogate_key IS NULL;

-----------------------
-- PHASE 3 (FUTURE): ENFORCE CONSTRAINTS
-----------------------

-- After validation passes, uncomment to enforce NOT NULL:
-- ALTER TABLE games 
--     ALTER COLUMN home_team_surrogate_key SET NOT NULL,
--     ALTER COLUMN away_team_surrogate_key SET NOT NULL;

-- ALTER TABLE boxscore_team
--     ALTER COLUMN team_surrogate_key SET NOT NULL;

-- ALTER TABLE boxscore_player
--     ALTER COLUMN team_surrogate_key_fk SET NOT NULL;

-----------------------
-- MIGRATION COMPLETE
-----------------------

COMMENT ON COLUMN games.home_team_surrogate_key IS 'FK to team_info_common surrogate key (Type 2 SCD). Resolved using home_team_id + game_date_est.';
COMMENT ON COLUMN games.away_team_surrogate_key IS 'FK to team_info_common surrogate key (Type 2 SCD). Resolved using away_team_id + game_date_est.';
COMMENT ON COLUMN boxscore_team.team_surrogate_key IS 'FK to team_info_common surrogate key (Type 2 SCD). Resolved using team_id + game_date.';
COMMENT ON COLUMN boxscore_player.team_surrogate_key_fk IS 'FK to team_info_common surrogate key (Type 2 SCD). Resolved using team_id + game_date.';
