-- 002_team_dimension_scd.sql
-- Type 2 Slowly Changing Dimension for Team Information
-- 
-- Design Philosophy:
-- - NBA team_id is the natural key (persistent across relocations)
-- - team_surrogate_key is the surrogate key (sequential per version)
-- - effective_start_date/effective_end_date track temporal validity
-- - is_current flag for efficient current-state queries
-- - change_reason documents why new version was created
--
-- Convention Alignment:
-- - NBA API: team_id 1610612760 persists Seattle SuperSonics → OKC Thunder
-- - Basketball-Reference: current slug contains full franchise history
-- - Sports Analytics Standard: Type 2 SCD with surrogate keys (NFL/MLB pattern)
--
-- Example Scenario (Seattle → OKC):
-- team_surrogate_key | team_id    | season_year | team_city    | team_name   | effective_start_date | effective_end_date | is_current | change_reason
-- 1                  | 1610612760 | 1967-68     | Seattle      | SuperSonics | 1967-10-13          | 2008-06-30         | FALSE      | relocation
-- 2                  | 1610612760 | 2008-09     | Oklahoma City| Thunder     | 2008-07-01          | 9999-12-31         | TRUE       | NULL

-----------------------
-- DROP EXISTING (for idempotency)
-----------------------
DROP TABLE IF EXISTS team_info_common CASCADE;

-----------------------
-- CREATE TYPE 2 SCD DIMENSION
-----------------------
CREATE TABLE team_info_common (
    -- Surrogate Key (per Kimball methodology)
    team_surrogate_key      SERIAL PRIMARY KEY,
    
    -- Natural Key (NBA's persistent franchise identifier)
    team_id                 INTEGER NOT NULL REFERENCES teams(team_id),
    
    -- Season Context (format: "YYYY-YY" e.g., "2008-09")
    season_year             VARCHAR(7) NOT NULL,
    
    -- Team Identity Attributes (slowly changing)
    team_city               VARCHAR(50),
    team_name               VARCHAR(50),
    team_abbreviation       VARCHAR(3),
    team_conference         VARCHAR(10) CHECK (team_conference IN ('East', 'West', NULL)),
    team_division           VARCHAR(20),
    team_code               VARCHAR(50),
    team_slug               VARCHAR(50),
    
    -- Season Performance Metrics
    w                       INTEGER,
    l                       INTEGER,
    pct                     DECIMAL(5,3),
    conf_rank               INTEGER,
    div_rank                INTEGER,
    pts_rank                INTEGER,
    pts_pg                  DECIMAL(5,2),
    reb_rank                INTEGER,
    reb_pg                  DECIMAL(5,2),
    ast_rank                INTEGER,
    ast_pg                  DECIMAL(5,2),
    opp_pts_rank            INTEGER,
    opp_pts_pg              DECIMAL(5,2),
    
    -- Franchise Temporal Boundaries
    min_year                INTEGER,  -- First season of franchise existence
    max_year                INTEGER,  -- Last season (or NULL if active)
    
    -- Type 2 SCD Temporal Tracking
    effective_start_date    DATE NOT NULL,
    effective_end_date      DATE NOT NULL DEFAULT '9999-12-31',
    is_current              BOOLEAN NOT NULL DEFAULT TRUE,
    
    -- Change Management
    change_reason           VARCHAR(50) CHECK (change_reason IN (
        'relocation',                -- Physical move (Seattle → OKC)
        'rebranding',                -- Name change same city (Bobcats → Hornets)
        'conference_realignment',    -- Division/conference change
        'shared_history_transfer',   -- Charlotte reclaiming 1988-2002 history
        'expansion',                 -- New franchise creation
        'name_change',               -- Minor name updates
        NULL
    )),
    
    -- External IDs
    league_id               VARCHAR(10),
    season_id               VARCHAR(20),
    
    -- Metadata
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT unique_team_version UNIQUE(team_id, effective_start_date),
    CONSTRAINT valid_effective_dates CHECK (effective_start_date <= effective_end_date),
    CONSTRAINT valid_current_flag CHECK (
        (is_current = TRUE AND effective_end_date = '9999-12-31'::DATE) OR
        (is_current = FALSE AND effective_end_date < '9999-12-31'::DATE)
    )
);

-----------------------
-- INDEXES FOR QUERY PERFORMANCE
-----------------------

-- Temporal queries: "Get team info as of date"
CREATE INDEX team_info_common_temporal_idx 
    ON team_info_common (team_id, effective_start_date, effective_end_date);

-- Current state queries: "Get all current teams"
CREATE INDEX team_info_common_is_current_idx 
    ON team_info_common (is_current) 
    WHERE is_current = TRUE;

-- Fact table joins: "Lookup surrogate key for game on date"
CREATE INDEX team_info_common_lookup_idx 
    ON team_info_common (team_id, effective_start_date DESC);

-- Season-based queries: "Get team info for 2008-09 season"
CREATE INDEX team_info_common_season_idx 
    ON team_info_common (season_year);

-- Change tracking: "Find all relocations"
CREATE INDEX team_info_common_change_reason_idx 
    ON team_info_common (change_reason) 
    WHERE change_reason IS NOT NULL;

-- Abbreviation lookups (for compatibility with existing queries)
CREATE INDEX team_info_common_abbrev_idx 
    ON team_info_common (team_abbreviation);

-----------------------
-- VALIDATION FUNCTION
-----------------------

-- Ensure exactly one is_current=TRUE per team_id
CREATE OR REPLACE FUNCTION validate_team_current_flag()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.is_current = TRUE THEN
        -- Check if another current record exists for same team_id
        IF EXISTS (
            SELECT 1 
            FROM team_info_common 
            WHERE team_id = NEW.team_id 
              AND is_current = TRUE 
              AND team_surrogate_key != NEW.team_surrogate_key
        ) THEN
            RAISE EXCEPTION 'team_id % already has a current record', NEW.team_id;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER enforce_single_current_per_team
    BEFORE INSERT OR UPDATE ON team_info_common
    FOR EACH ROW
    EXECUTE FUNCTION validate_team_current_flag();

-----------------------
-- HELPER VIEWS
-----------------------

-- Current team snapshot (replacement for old teams table queries)
CREATE OR REPLACE VIEW v_teams_current AS
SELECT 
    team_surrogate_key,
    team_id,
    season_year,
    team_city,
    team_name,
    team_abbreviation,
    team_conference,
    team_division,
    w, l, pct,
    conf_rank,
    div_rank,
    effective_start_date,
    min_year,
    max_year
FROM team_info_common
WHERE is_current = TRUE;

-- Complete franchise history (for auditing/reporting)
CREATE OR REPLACE VIEW v_team_franchise_history AS
SELECT 
    team_id,
    team_surrogate_key,
    season_year,
    team_city,
    team_name,
    team_abbreviation,
    effective_start_date,
    effective_end_date,
    is_current,
    change_reason,
    LEAD(effective_start_date) OVER (PARTITION BY team_id ORDER BY effective_start_date) AS next_version_start
FROM team_info_common
ORDER BY team_id, effective_start_date;

-----------------------
-- COMMENTS
-----------------------

COMMENT ON TABLE team_info_common IS 'Type 2 Slowly Changing Dimension for NBA team attributes. Tracks team identity changes over time using surrogate keys and effective date ranges.';

COMMENT ON COLUMN team_info_common.team_surrogate_key IS 'Sequential integer surrogate key - one per dimension version. Use this for fact table foreign keys.';

COMMENT ON COLUMN team_info_common.team_id IS 'NBA natural key - persistent across relocations (e.g., 1610612760 for Seattle/OKC franchise)';

COMMENT ON COLUMN team_info_common.effective_start_date IS 'Date this dimension version became active (inclusive)';

COMMENT ON COLUMN team_info_common.effective_end_date IS 'Date this dimension version expired (exclusive). 9999-12-31 indicates current version.';

COMMENT ON COLUMN team_info_common.is_current IS 'TRUE for current version (optimization for WHERE is_current = TRUE queries)';

COMMENT ON COLUMN team_info_common.change_reason IS 'Why this new version was created. NULL for initial version.';

COMMENT ON VIEW v_teams_current IS 'Current snapshot of all active teams (is_current=TRUE). Simplified view for dashboard queries.';

COMMENT ON VIEW v_team_franchise_history IS 'Complete temporal history of all team changes. Shows progression of franchise identity over time.';
