-- 001_initial_schema.sql
-- Phase 1 Canonical Schema - Initial Migration
-- Assumptions:
-- - Run on an empty PostgreSQL database (no existing conflicting tables).
-- - Uses default "public" schema.
-- - Encoding: UTF8.
-- - No non-standard extensions required (only standard BTREE and BRIN indexes).

-----------------------
-- CORE DIMENSIONS
-----------------------

CREATE TABLE players (
    player_id          INTEGER PRIMARY KEY,
    slug               TEXT,
    full_name          TEXT,
    first_name         TEXT,
    last_name          TEXT,
    is_active          BOOLEAN,
    birth_date         DATE,
    birth_year         INTEGER,
    height_inches      INTEGER,
    weight_lbs         INTEGER,
    country            TEXT,
    position           TEXT,
    shoots             TEXT,
    hof_inducted       BOOLEAN,
    rookie_year        INTEGER,
    final_year         INTEGER,
    created_at         TIMESTAMPTZ DEFAULT NOW(),
    updated_at         TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX players_slug_unique_idx ON players (slug);

CREATE TABLE player_aliases (
    player_alias_id    BIGSERIAL PRIMARY KEY,
    player_id          INTEGER NOT NULL REFERENCES players(player_id),
    alias_type         TEXT NOT NULL,
    alias_value        TEXT NOT NULL
);

CREATE INDEX player_aliases_player_id_idx ON player_aliases (player_id);
CREATE INDEX player_aliases_alias_value_idx ON player_aliases (alias_value);

CREATE TABLE teams (
    team_id            INTEGER PRIMARY KEY,
    team_abbrev        TEXT,
    team_name          TEXT,
    team_city          TEXT,
    start_season       INTEGER,
    end_season         INTEGER,
    is_active          BOOLEAN,
    created_at         TIMESTAMPTZ DEFAULT NOW(),
    updated_at         TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX teams_team_abbrev_unique_idx ON teams (team_abbrev);

CREATE TABLE team_history (
    team_history_id    BIGSERIAL PRIMARY KEY,
    team_id            INTEGER NOT NULL REFERENCES teams(team_id),
    season_end_year    INTEGER NOT NULL,
    team_abbrev        TEXT,
    team_name          TEXT,
    team_city          TEXT,
    lg                 TEXT,
    from_year          INTEGER,
    to_year            INTEGER
);

CREATE INDEX team_history_team_id_season_idx ON team_history (team_id, season_end_year);

CREATE TABLE team_abbrev_mappings (
    mapping_id         BIGSERIAL PRIMARY KEY,
    season_end_year    INTEGER,
    raw_abbrev         TEXT NOT NULL,
    team_id            INTEGER REFERENCES teams(team_id),
    notes              TEXT
);

CREATE INDEX team_abbrev_mappings_raw_abbrev_idx ON team_abbrev_mappings (raw_abbrev);
CREATE INDEX team_abbrev_mappings_team_id_idx ON team_abbrev_mappings (team_id);

CREATE TABLE seasons (
    season_id          BIGSERIAL PRIMARY KEY,
    season_end_year    INTEGER NOT NULL,
    lg                 TEXT,
    is_lockout         BOOLEAN,
    notes              TEXT
);

CREATE UNIQUE INDEX seasons_season_end_year_unique_idx
    ON seasons (season_end_year, COALESCE(lg, 'NBA'));

-----------------------
-- GAMES / BOXSCORES
-----------------------

CREATE TABLE games (
    game_id            TEXT PRIMARY KEY,
    season_id          BIGINT REFERENCES seasons(season_id),
    season_end_year    INTEGER,
    lg                 TEXT,
    game_date_est      DATE NOT NULL,
    game_time_est      TIME,
    home_team_id       INTEGER REFERENCES teams(team_id),
    away_team_id       INTEGER REFERENCES teams(team_id),
    home_team_abbrev   TEXT,
    away_team_abbrev   TEXT,
    home_pts           INTEGER,
    away_pts           INTEGER,
    attendance         INTEGER,
    arena              TEXT,
    is_playoffs        BOOLEAN,
    is_neutral_site    BOOLEAN,
    data_source        TEXT
);

CREATE INDEX games_game_date_est_brin_idx
    ON games USING BRIN (game_date_est);

CREATE INDEX games_season_end_year_idx
    ON games (season_end_year);

CREATE TABLE boxscore_team (
    game_id            TEXT NOT NULL REFERENCES games(game_id),
    team_id            INTEGER REFERENCES teams(team_id),
    opponent_team_id   INTEGER REFERENCES teams(team_id),
    is_home            BOOLEAN NOT NULL,
    team_abbrev        TEXT,
    pts                INTEGER,
    fg                 INTEGER,
    fga                INTEGER,
    fg3                INTEGER,
    fg3a               INTEGER,
    ft                 INTEGER,
    fta                INTEGER,
    orb                INTEGER,
    drb                INTEGER,
    trb                INTEGER,
    ast                INTEGER,
    stl                INTEGER,
    blk                INTEGER,
    tov                INTEGER,
    pf                 INTEGER,
    pace               NUMERIC,
    ortg               NUMERIC,
    drtg               NUMERIC,
    PRIMARY KEY (game_id, team_id)
);

CREATE INDEX boxscore_team_game_team_idx
    ON boxscore_team (game_id, team_id);

CREATE INDEX boxscore_team_game_id_brin_idx
    ON boxscore_team USING BRIN (game_id);

CREATE TABLE boxscore_player (
    game_id            TEXT NOT NULL REFERENCES games(game_id),
    player_id          INTEGER REFERENCES players(player_id),
    team_id            INTEGER REFERENCES teams(team_id),
    is_starter         BOOLEAN,
    seconds            INTEGER,
    fg                 INTEGER,
    fga                INTEGER,
    fg3                INTEGER,
    fg3a               INTEGER,
    ft                 INTEGER,
    fta                INTEGER,
    orb                INTEGER,
    drb                INTEGER,
    trb                INTEGER,
    ast                INTEGER,
    stl                INTEGER,
    blk                INTEGER,
    tov                INTEGER,
    pf                 INTEGER,
    pts                INTEGER,
    plus_minus         INTEGER,
    PRIMARY KEY (game_id, player_id, team_id)
);

CREATE INDEX boxscore_player_game_player_idx
    ON boxscore_player (game_id, player_id);

CREATE INDEX boxscore_player_game_id_brin_idx
    ON boxscore_player USING BRIN (game_id);

-----------------------
-- PLAY-BY-PLAY EVENTS
-----------------------

CREATE TABLE pbp_events (
    game_id            TEXT NOT NULL REFERENCES games(game_id),
    eventnum           INTEGER NOT NULL,
    period             INTEGER,
    clk                TEXT,
    clk_remaining      NUMERIC,
    event_type         TEXT,
    option1            INTEGER,
    option2            INTEGER,
    option3            INTEGER,
    team_id            INTEGER REFERENCES teams(team_id),
    opponent_team_id   INTEGER REFERENCES teams(team_id),
    player1_id         INTEGER REFERENCES players(player_id),
    player2_id         INTEGER REFERENCES players(player_id),
    player3_id         INTEGER REFERENCES players(player_id),
    description        TEXT,
    score              TEXT,
    home_score         INTEGER,
    away_score         INTEGER,
    PRIMARY KEY (game_id, eventnum)
);

CREATE INDEX pbp_events_game_id_brin_idx
    ON pbp_events USING BRIN (game_id);

CREATE INDEX pbp_events_team_id_idx ON pbp_events (team_id);
CREATE INDEX pbp_events_player_ids_idx ON pbp_events (player1_id, player2_id, player3_id);

-----------------------
-- PLAYER-SEASON HUB + STATS
-----------------------

CREATE TABLE player_season (
    seas_id            BIGINT PRIMARY KEY,
    player_id          INTEGER NOT NULL REFERENCES players(player_id),
    season_id          BIGINT REFERENCES seasons(season_id),
    season_end_year    INTEGER NOT NULL,
    team_id            INTEGER REFERENCES teams(team_id),
    team_abbrev        TEXT,
    lg                 TEXT,
    age                INTEGER,
    position           TEXT,
    experience         INTEGER,
    is_total           BOOLEAN DEFAULT FALSE,
    is_league_average  BOOLEAN DEFAULT FALSE,
    is_playoffs        BOOLEAN DEFAULT FALSE
);

CREATE INDEX player_season_player_season_idx
    ON player_season (player_id, season_end_year);

CREATE INDEX player_season_team_season_idx
    ON player_season (team_id, season_end_year);

CREATE TABLE player_season_per_game (
    seas_id            BIGINT PRIMARY KEY REFERENCES player_season(seas_id),
    g                  INTEGER,
    gs                 INTEGER,
    mp_per_g           NUMERIC,
    fg_per_g           NUMERIC,
    fga_per_g          NUMERIC,
    fg3_per_g          NUMERIC,
    fg3a_per_g         NUMERIC,
    ft_per_g           NUMERIC,
    fta_per_g          NUMERIC,
    orb_per_g          NUMERIC,
    drb_per_g          NUMERIC,
    trb_per_g          NUMERIC,
    ast_per_g          NUMERIC,
    stl_per_g          NUMERIC,
    blk_per_g          NUMERIC,
    tov_per_g          NUMERIC,
    pf_per_g           NUMERIC,
    pts_per_g          NUMERIC
);

CREATE TABLE player_season_totals (
    seas_id            BIGINT PRIMARY KEY REFERENCES player_season(seas_id),
    g                  INTEGER,
    gs                 INTEGER,
    mp                 INTEGER,
    fg                 INTEGER,
    fga                INTEGER,
    fg3                INTEGER,
    fg3a               INTEGER,
    ft                 INTEGER,
    fta                INTEGER,
    orb                INTEGER,
    drb                INTEGER,
    trb                INTEGER,
    ast                INTEGER,
    stl                INTEGER,
    blk                INTEGER,
    tov                INTEGER,
    pf                 INTEGER,
    pts                INTEGER
);

CREATE TABLE player_season_per36 (
    seas_id            BIGINT PRIMARY KEY REFERENCES player_season(seas_id),
    mp_per_g           NUMERIC,
    fg_per36           NUMERIC,
    fga_per36          NUMERIC,
    fg3_per36          NUMERIC,
    fg3a_per36         NUMERIC,
    ft_per36           NUMERIC,
    fta_per36          NUMERIC,
    orb_per36          NUMERIC,
    drb_per36          NUMERIC,
    trb_per36          NUMERIC,
    ast_per36          NUMERIC,
    stl_per36          NUMERIC,
    blk_per36          NUMERIC,
    tov_per36          NUMERIC,
    pf_per36           NUMERIC,
    pts_per36          NUMERIC
);

CREATE TABLE player_season_per100 (
    seas_id            BIGINT PRIMARY KEY REFERENCES player_season(seas_id),
    mp_per_g           NUMERIC,
    fg_per100          NUMERIC,
    fga_per100         NUMERIC,
    fg3_per100         NUMERIC,
    fg3a_per100        NUMERIC,
    ft_per100          NUMERIC,
    fta_per100         NUMERIC,
    orb_per100         NUMERIC,
    drb_per100         NUMERIC,
    trb_per100         NUMERIC,
    ast_per100         NUMERIC,
    stl_per100         NUMERIC,
    blk_per100         NUMERIC,
    tov_per100         NUMERIC,
    pf_per100          NUMERIC,
    pts_per100         NUMERIC
);

CREATE TABLE player_season_advanced (
    seas_id            BIGINT PRIMARY KEY REFERENCES player_season(seas_id),
    per                NUMERIC,
    ts_pct             NUMERIC,
    fg3a_rate          NUMERIC,
    fta_rate           NUMERIC,
    orb_pct            NUMERIC,
    drb_pct            NUMERIC,
    trb_pct            NUMERIC,
    ast_pct            NUMERIC,
    stl_pct            NUMERIC,
    blk_pct            NUMERIC,
    tov_pct            NUMERIC,
    usg_pct            NUMERIC,
    ows                NUMERIC,
    dws                NUMERIC,
    ws                 NUMERIC,
    ws_per_48          NUMERIC,
    obpm               NUMERIC,
    dbpm               NUMERIC,
    bpm                NUMERIC,
    vorp               NUMERIC
);

-----------------------
-- TEAM-SEASON HUB + STATS
-----------------------

CREATE TABLE team_season (
    team_season_id     BIGSERIAL PRIMARY KEY,
    team_id            INTEGER REFERENCES teams(team_id),
    season_id          BIGINT REFERENCES seasons(season_id),
    season_end_year    INTEGER NOT NULL,
    lg                 TEXT,
    is_playoffs        BOOLEAN DEFAULT FALSE,
    is_league_average  BOOLEAN DEFAULT FALSE
);

CREATE UNIQUE INDEX team_season_team_year_scope_uniq
    ON team_season (team_id, season_end_year, COALESCE(is_playoffs, FALSE));

CREATE TABLE team_season_totals (
    team_season_id     BIGINT PRIMARY KEY REFERENCES team_season(team_season_id),
    g                  INTEGER,
    mp                 INTEGER,
    fg                 INTEGER,
    fga                INTEGER,
    fg3                INTEGER,
    fg3a               INTEGER,
    ft                 INTEGER,
    fta                INTEGER,
    orb                INTEGER,
    drb                INTEGER,
    trb                INTEGER,
    ast                INTEGER,
    stl                INTEGER,
    blk                INTEGER,
    tov                INTEGER,
    pf                 INTEGER,
    pts                INTEGER
);

CREATE TABLE team_season_per_game (
    team_season_id     BIGINT PRIMARY KEY REFERENCES team_season(team_season_id),
    g                  INTEGER,
    fg_per_g           NUMERIC,
    fga_per_g          NUMERIC,
    fg3_per_g          NUMERIC,
    fg3a_per_g         NUMERIC,
    ft_per_g           NUMERIC,
    fta_per_g          NUMERIC,
    orb_per_g          NUMERIC,
    drb_per_g          NUMERIC,
    trb_per_g          NUMERIC,
    ast_per_g          NUMERIC,
    stl_per_g          NUMERIC,
    blk_per_g          NUMERIC,
    tov_per_g          NUMERIC,
    pf_per_g           NUMERIC,
    pts_per_g          NUMERIC
);

CREATE TABLE team_season_per100 (
    team_season_id     BIGINT PRIMARY KEY REFERENCES team_season(team_season_id),
    fg_per100          NUMERIC,
    fga_per100         NUMERIC,
    fg3_per100         NUMERIC,
    fg3a_per100        NUMERIC,
    ft_per100          NUMERIC,
    fta_per100         NUMERIC,
    orb_per100         NUMERIC,
    drb_per100         NUMERIC,
    trb_per100         NUMERIC,
    ast_per100         NUMERIC,
    stl_per100         NUMERIC,
    blk_per100         NUMERIC,
    tov_per100         NUMERIC,
    pf_per100          NUMERIC,
    pts_per100         NUMERIC
);

CREATE TABLE team_season_opponent_totals (
    team_season_id     BIGINT PRIMARY KEY REFERENCES team_season(team_season_id),
    opp_fg             INTEGER,
    opp_fga            INTEGER,
    opp_fg3            INTEGER,
    opp_fg3a           INTEGER,
    opp_ft             INTEGER,
    opp_fta            INTEGER,
    opp_orb            INTEGER,
    opp_drb            INTEGER,
    opp_trb            INTEGER,
    opp_ast            INTEGER,
    opp_stl            INTEGER,
    opp_blk            INTEGER,
    opp_tov            INTEGER,
    opp_pf             INTEGER,
    opp_pts            INTEGER
);

CREATE TABLE team_season_opponent_per_game (
    team_season_id     BIGINT PRIMARY KEY REFERENCES team_season(team_season_id),
    opp_fg_per_g       NUMERIC,
    opp_fga_per_g      NUMERIC,
    opp_fg3_per_g      NUMERIC,
    opp_fg3a_per_g     NUMERIC,
    opp_ft_per_g       NUMERIC,
    opp_fta_per_g      NUMERIC,
    opp_orb_per_g      NUMERIC,
    opp_drb_per_g      NUMERIC,
    opp_trb_per_g      NUMERIC,
    opp_ast_per_g      NUMERIC,
    opp_stl_per_g      NUMERIC,
    opp_blk_per_g      NUMERIC,
    opp_tov_per_g      NUMERIC,
    opp_pf_per_g       NUMERIC,
    opp_pts_per_g      NUMERIC
);

CREATE TABLE team_season_opponent_per100 (
    team_season_id     BIGINT PRIMARY KEY REFERENCES team_season(team_season_id),
    opp_fg_per100      NUMERIC,
    opp_fga_per100     NUMERIC,
    opp_fg3_per100     NUMERIC,
    opp_fg3a_per100    NUMERIC,
    opp_ft_per100      NUMERIC,
    opp_fta_per100     NUMERIC,
    opp_orb_per100     NUMERIC,
    opp_drb_per100     NUMERIC,
    opp_trb_per100     NUMERIC,
    opp_ast_per100     NUMERIC,
    opp_stl_per100     NUMERIC,
    opp_blk_per100     NUMERIC,
    opp_tov_per100     NUMERIC,
    opp_pf_per100      NUMERIC,
    opp_pts_per100     NUMERIC
);

CREATE INDEX team_season_season_idx
    ON team_season (season_end_year, is_playoffs);

-----------------------
-- AWARDS
-----------------------

CREATE TABLE awards_all_star_selections (
    id                 BIGSERIAL PRIMARY KEY,
    season_id          BIGINT REFERENCES seasons(season_id),
    season_end_year    INTEGER,
    player_id          INTEGER REFERENCES players(player_id),
    team_id            INTEGER REFERENCES teams(team_id),
    league             TEXT,
    all_star_team      TEXT,
    is_starter         BOOLEAN
);

CREATE INDEX awards_all_star_selections_player_idx
    ON awards_all_star_selections (player_id, season_end_year);

CREATE TABLE awards_player_shares (
    id                 BIGSERIAL PRIMARY KEY,
    season_id          BIGINT REFERENCES seasons(season_id),
    season_end_year    INTEGER,
    player_id          INTEGER REFERENCES players(player_id),
    award_type         TEXT NOT NULL,
    points_won         NUMERIC,
    points_max         NUMERIC,
    votes_first        INTEGER
);

CREATE INDEX awards_player_shares_player_idx
    ON awards_player_shares (player_id, season_end_year, award_type);

CREATE TABLE awards_end_of_season_teams (
    id                 BIGSERIAL PRIMARY KEY,
    season_id          BIGINT REFERENCES seasons(season_id),
    season_end_year    INTEGER,
    player_id          INTEGER REFERENCES players(player_id),
    team_id            INTEGER REFERENCES teams(team_id),
    award_type         TEXT NOT NULL,
    team_designation   TEXT NOT NULL,
    position           TEXT
);

CREATE INDEX awards_end_of_season_teams_player_idx
    ON awards_end_of_season_teams (player_id, season_end_year, award_type);

CREATE TABLE awards_end_of_season_voting (
    id                 BIGSERIAL PRIMARY KEY,
    season_id          BIGINT REFERENCES seasons(season_id),
    season_end_year    INTEGER,
    player_id          INTEGER REFERENCES players(player_id),
    award_type         TEXT NOT NULL,
    rank               INTEGER,
    points             NUMERIC,
    ballots            INTEGER,
    max_points         NUMERIC
);

CREATE INDEX awards_end_of_season_voting_player_idx
    ON awards_end_of_season_voting (player_id, season_end_year, award_type);

-----------------------
-- DRAFT
-----------------------

CREATE TABLE draft_picks (
    draft_pick_id      BIGSERIAL PRIMARY KEY,
    season_end_year    INTEGER,
    round_number       INTEGER,
    pick_number        INTEGER,
    overall_pick       INTEGER,
    player_id          INTEGER REFERENCES players(player_id),
    player_name        TEXT,
    team_id            INTEGER REFERENCES teams(team_id),
    team_abbrev        TEXT,
    notes              TEXT
);

CREATE INDEX draft_picks_player_idx
    ON draft_picks (player_id);

CREATE INDEX draft_picks_season_idx
    ON draft_picks (season_end_year);

-----------------------
-- INACTIVE PLAYERS
-----------------------

CREATE TABLE inactive_players (
    game_id            TEXT NOT NULL REFERENCES games(game_id),
    player_id          INTEGER NOT NULL REFERENCES players(player_id),
    team_id            INTEGER REFERENCES teams(team_id),
    reason             TEXT,
    PRIMARY KEY (game_id, player_id)
);

CREATE INDEX inactive_players_game_id_idx ON inactive_players (game_id);
CREATE INDEX inactive_players_player_id_idx ON inactive_players (player_id);

-----------------------
-- METADATA / CONTROL
-----------------------

CREATE TABLE data_versions (
    data_version_id    BIGSERIAL PRIMARY KEY,
    source_name        TEXT NOT NULL,
    source_version     TEXT,
    loaded_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes              TEXT
);

CREATE UNIQUE INDEX data_versions_source_unique_idx
    ON data_versions (source_name, COALESCE(source_version, 'current'));

CREATE TABLE etl_runs (
    etl_run_id         BIGSERIAL PRIMARY KEY,
    started_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at       TIMESTAMPTZ,
    status             TEXT NOT NULL,
    data_version_id    BIGINT REFERENCES data_versions(data_version_id),
    description        TEXT
);

CREATE INDEX etl_runs_status_idx ON etl_runs (status);
CREATE INDEX etl_runs_started_at_idx ON etl_runs (started_at);