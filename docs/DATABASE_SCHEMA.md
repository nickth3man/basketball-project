# Database Schema Documentation: Basketball Data Hub

**Database**: PostgreSQL
**Schema Version**: Current (as of 2025-11-13)
**Migration Strategy**: Versioned migrations in `db/migrations/`

---

## Core Tables

### Players
**Table**: `players`
**Purpose**: Store player demographic and biographical information
**Primary Key**: `player_id` (UUID)

```sql
CREATE TABLE players (
    player_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    birth_date DATE,
    height_inches INTEGER,
    weight_lbs INTEGER,
    position VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_players_name ON players(last_name, first_name);
CREATE INDEX idx_players_position ON players(position);
```

**Key Relationships**:
- `player_seasons.player_id` → `players.player_id`
- `game_players.player_id` → `players.player_id`

### Teams
**Table**: `teams`
**Purpose**: Store team information and affiliations
**Primary Key**: `team_id` (UUID)

```sql
CREATE TABLE teams (
    team_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL,
    abbreviation VARCHAR(10) NOT NULL UNIQUE,
    city VARCHAR(100),
    state VARCHAR(50),
    founded_year INTEGER,
    league VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_teams_name ON teams(name);
CREATE INDEX idx_teams_abbreviation ON teams(abbreviation);
CREATE INDEX idx_teams_league ON teams(league);
```

**Key Relationships**:
- `team_seasons.team_id` → `teams.team_id`
- `games.home_team_id` → `teams.team_id`
- `games.away_team_id` → `teams.team_id`

### Seasons
**Table**: `seasons`
**Purpose**: Define season boundaries and metadata
**Primary Key**: `season_id` (UUID)

```sql
CREATE TABLE seasons (
    season_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    year INTEGER NOT NULL UNIQUE,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_seasons_year ON seasons(year);
CREATE INDEX idx_seasons_dates ON seasons(start_date, end_date);
```

**Key Relationships**:
- `player_seasons.season_id` → `seasons.season_id`
- `team_seasons.season_id` → `seasons.season_id`
- `games.season_id` → `seasons.season_id`

### Games
**Table**: `games`
**Purpose**: Store game information and results
**Primary Key**: `game_id` (UUID)

```sql
CREATE TABLE games (
    game_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    season_id UUID NOT NULL REFERENCES seasons(season_id),
    home_team_id UUID NOT NULL REFERENCES teams(team_id),
    away_team_id UUID NOT NULL REFERENCES teams(team_id),
    game_date TIMESTAMP WITH TIME ZONE NOT NULL,
    home_score INTEGER,
    away_score INTEGER,
    venue VARCHAR(200),
    attendance INTEGER,
    status VARCHAR(20) DEFAULT 'scheduled',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_games_date ON games(game_date);
CREATE INDEX idx_games_season ON games(season_id);
CREATE INDEX idx_games_teams ON games(home_team_id, away_team_id);
CREATE INDEX idx_games_status ON games(status);
```

**Key Relationships**:
- `game_players.game_id` → `games.game_id`
- `play_by_play.game_id` → `games.game_id`

---

## Statistics Tables

### Player Seasons
**Table**: `player_seasons`
**Purpose**: Aggregate player statistics by season
**Primary Key**: `player_season_id` (UUID)

```sql
CREATE TABLE player_seasons (
    player_season_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    player_id UUID NOT NULL REFERENCES players(player_id),
    season_id UUID NOT NULL REFERENCES seasons(season_id),
    team_id UUID REFERENCES teams(team_id),
    games_played INTEGER DEFAULT 0,
    minutes_played DECIMAL(10,2) DEFAULT 0,
    points_per_game DECIMAL(8,2) DEFAULT 0,
    rebounds_per_game DECIMAL(8,2) DEFAULT 0,
    assists_per_game DECIMAL(8,2) DEFAULT 0,
    steals_per_game DECIMAL(8,2) DEFAULT 0,
    blocks_per_game DECIMAL(8,2) DEFAULT 0,
    turnovers_per_game DECIMAL(8,2) DEFAULT 0,
    field_goal_percentage DECIMAL(5,3) DEFAULT 0,
    three_point_percentage DECIMAL(5,3) DEFAULT 0,
    free_throw_percentage DECIMAL(5,3) DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_player_seasons_player ON player_seasons(player_id);
CREATE INDEX idx_player_seasons_season ON player_seasons(season_id);
CREATE INDEX idx_player_seasons_team ON player_seasons(team_id);
CREATE UNIQUE INDEX idx_player_seasons_unique ON player_seasons(player_id, season_id, team_id);
```

### Team Seasons
**Table**: `team_seasons`
**Purpose**: Aggregate team statistics by season
**Primary Key**: `team_season_id` (UUID)

```sql
CREATE TABLE team_seasons (
    team_season_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id UUID NOT NULL REFERENCES teams(team_id),
    season_id UUID NOT NULL REFERENCES seasons(season_id),
    games_played INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    points_per_game DECIMAL(8,2) DEFAULT 0,
    points_allowed_per_game DECIMAL(8,2) DEFAULT 0,
    field_goal_percentage DECIMAL(5,3) DEFAULT 0,
    three_point_percentage DECIMAL(5,3) DEFAULT 0,
    free_throw_percentage DECIMAL(5,3) DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_team_seasons_team ON team_seasons(team_id);
CREATE INDEX idx_team_seasons_season ON team_seasons(season_id);
CREATE UNIQUE INDEX idx_team_seasons_unique ON team_seasons(team_id, season_id);
```

### Game Players
**Table**: `game_players`
**Purpose**: Individual player statistics for each game
**Primary Key**: `game_player_id` (UUID)

```sql
CREATE TABLE game_players (
    game_player_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_id UUID NOT NULL REFERENCES games(game_id),
    player_id UUID NOT NULL REFERENCES players(player_id),
    team_id UUID NOT NULL REFERENCES teams(team_id),
    minutes_played INTEGER DEFAULT 0,
    points INTEGER DEFAULT 0,
    field_goals_made INTEGER DEFAULT 0,
    field_goals_attempted INTEGER DEFAULT 0,
    three_pointers_made INTEGER DEFAULT 0,
    three_pointers_attempted INTEGER DEFAULT 0,
    free_throws_made INTEGER DEFAULT 0,
    free_throws_attempted INTEGER DEFAULT 0,
    offensive_rebounds INTEGER DEFAULT 0,
    defensive_rebounds INTEGER DEFAULT 0,
    total_rebounds INTEGER DEFAULT 0,
    assists INTEGER DEFAULT 0,
    steals INTEGER DEFAULT 0,
    blocks INTEGER DEFAULT 0,
    turnovers INTEGER DEFAULT 0,
    fouls INTEGER DEFAULT 0,
    plus_minus INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_game_players_game ON game_players(game_id);
CREATE INDEX idx_game_players_player ON game_players(player_id);
CREATE INDEX idx_game_players_team ON game_players(team_id);
CREATE UNIQUE INDEX idx_game_players_unique ON game_players(game_id, player_id);
```

---

## Play-by-Play Data

### Play by Play
**Table**: `play_by_play`
**Purpose**: Detailed play-by-play events for games
**Primary Key**: `play_id` (UUID)

```sql
CREATE TABLE play_by_play (
    play_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_id UUID NOT NULL REFERENCES games(game_id),
    period INTEGER NOT NULL,
    time_remaining INTEGER NOT NULL, -- seconds remaining in period
    play_type VARCHAR(50) NOT NULL,
    description TEXT,
    player_id UUID REFERENCES players(player_id),
    team_id UUID REFERENCES teams(team_id),
    points_scored INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_pbp_game ON play_by_play(game_id);
CREATE INDEX idx_pbp_period ON play_by_play(game_id, period);
CREATE INDEX idx_pbp_time ON play_by_play(game_id, time_remaining);
CREATE INDEX idx_pbp_type ON play_by_play(play_type);
```

---

## ETL Metadata Tables

### ETL Runs
**Table**: `etl_runs`
**Purpose**: Track ETL execution history and status
**Primary Key**: `etl_run_id` (UUID)

```sql
CREATE TABLE etl_runs (
    etl_run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_type VARCHAR(50) NOT NULL, -- 'full', 'incremental', 'manual'
    status VARCHAR(20) NOT NULL DEFAULT 'running', -- 'running', 'completed', 'failed'
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    records_processed INTEGER DEFAULT 0,
    records_failed INTEGER DEFAULT 0,
    error_message TEXT,
    metadata JSONB, -- additional run information
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_etl_runs_status ON etl_runs(status);
CREATE INDEX idx_etl_runs_started ON etl_runs(started_at);
CREATE INDEX idx_etl_runs_type ON etl_runs(run_type);
```

### Data Sources
**Table**: `data_sources`
**Purpose**: Track external data source information
**Primary Key**: `source_id` (UUID)

```sql
CREATE TABLE data_sources (
    source_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    base_url VARCHAR(500),
    api_key_required BOOLEAN DEFAULT FALSE,
    last_sync_at TIMESTAMP WITH TIME ZONE,
    sync_frequency VARCHAR(20), -- 'daily', 'weekly', 'monthly'
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_data_sources_active ON data_sources(is_active);
CREATE INDEX idx_data_sources_sync ON data_sources(last_sync_at);
```

---

## Views for Analytics

### Player Career Stats
**View**: `player_career_stats`
**Purpose**: Aggregate player statistics across all seasons

```sql
CREATE VIEW player_career_stats AS
SELECT 
    p.player_id,
    p.first_name,
    p.last_name,
    COUNT(ps.season_id) as seasons_played,
    SUM(ps.games_played) as total_games,
    AVG(ps.points_per_game) as career_ppg,
    AVG(ps.rebounds_per_game) as career_rpg,
    AVG(ps.assists_per_game) as career_apg,
    AVG(ps.field_goal_percentage) as career_fg_pct,
    MAX(ps.points_per_game) as best_ppg_season,
    MIN(seasons.year) as rookie_year,
    MAX(seasons.year) as latest_year
FROM players p
LEFT JOIN player_seasons ps ON p.player_id = ps.player_id
LEFT JOIN seasons s ON ps.season_id = s.season_id
GROUP BY p.player_id, p.first_name, p.last_name;
```

### Team Season Performance
**View**: `team_season_performance`
**Purpose**: Team performance metrics with rankings

```sql
CREATE VIEW team_season_performance AS
SELECT 
    t.team_id,
    t.name as team_name,
    t.abbreviation,
    s.year as season_year,
    ts.games_played,
    ts.wins,
    ts.losses,
    CASE 
        WHEN ts.games_played > 0 THEN 
            ROUND((ts.wins::DECIMAL / ts.games_played) * 100, 2)
        ELSE 0 
    END as win_percentage,
    ts.points_per_game,
    ts.points_allowed_per_game,
    RANK() OVER (PARTITION BY s.year ORDER BY (ts.wins::DECIMAL / NULLIF(ts.games_played, 0)) DESC) as win_rank,
    RANK() OVER (PARTITION BY s.year ORDER BY ts.points_per_game DESC) as points_rank
FROM teams t
JOIN team_seasons ts ON t.team_id = ts.team_id
JOIN seasons s ON ts.season_id = s.season_id
WHERE ts.games_played > 0;
```

---

## Indexing Strategy

### Primary Indexes
1. **Foreign Key Indexes**: All foreign keys have corresponding indexes
2. **Query Pattern Indexes**: Optimized for common query patterns
3. **Composite Indexes**: Multi-column indexes for frequent joins

### Performance Considerations
1. **Player Search**: `(last_name, first_name)` composite index
2. **Game Queries**: Date-based indexes for time-series queries
3. **Statistics Queries**: Season and team-based indexes
4. **ETL Tracking**: Status and timestamp indexes for monitoring

---

## Data Integrity Constraints

### Business Rules
1. **Player-Season Uniqueness**: One record per player per team per season
2. **Game-Player Uniqueness**: One record per player per game
3. **Season Overlap**: Seasons cannot have overlapping date ranges
4. **Game Scores**: Cannot be negative values
5. **Percentage Ranges**: All percentages between 0.000 and 1.000

### Referential Integrity
1. **Cascading Deletes**: Generally disabled to preserve historical data
2. **Null Handling**: Appropriate NULL values for missing data
3. **Default Values**: Sensible defaults for all numeric fields

---

## Migration History

### Current Migrations
1. `001_initial_schema.sql` - Core tables and relationships
2. `002_advanced_views.sql` - Analytics views and performance optimizations
3. `003_etl_metadata.sql` - ETL tracking and data source management

### Migration Strategy
1. **Versioned Files**: Each migration in separate SQL file
2. **Forward Compatibility**: New migrations maintain backward compatibility
3. **Rollback Support**: Each migration includes rollback procedure
4. **Testing**: All migrations tested on staging before production

---

## Performance Optimization

### Query Patterns
1. **Player Statistics**: Season-based aggregation with player joins
2. **Team Comparisons**: Head-to-head game results
3. **Historical Analysis**: Time-series game data queries
4. **Real-time Updates**: Game-in-progress statistics

### Optimization Techniques
1. **Partitioning**: Consider partitioning large tables by season
2. **Materialized Views**: For complex analytics calculations
3. **Connection Pooling**: Configured for concurrent access
4. **Query Caching**: Frequently accessed statistics cached

---

## Data Retention Policy

### Historical Data
1. **Game Data**: Permanent retention for historical analysis
2. **ETL Logs**: 90-day retention for run history
3. **Temporary Data**: Session data cleaned up regularly

### Archive Strategy
1. **Cold Storage**: Older seasons moved to archive tables
2. **Compression**: Large text fields compressed
3. **Backup Strategy**: Daily backups with 30-day retention

---

## Security Considerations

### Access Control
1. **Read-Only Analytics**: Most users have read-only access to views
2. **ETL Access**: Limited service accounts for data loading
3. **Admin Access**: Full access for schema modifications

### Data Privacy
1. **PII Handling**: No personal identifying information stored
2. **Data Anonymization**: Sensitive data masked where required
3. **Audit Logging**: All data modifications tracked

---

## Monitoring and Maintenance

### Health Checks
1. **Connection Monitoring**: Database connection pool status
2. **Query Performance**: Slow query identification and optimization
3. **Storage Monitoring**: Table size and growth tracking
4. **ETL Status**: Real-time ETL run monitoring

### Maintenance Tasks
1. **Index Rebuilding**: Regular index maintenance for performance
2. **Statistics Updates**: Scheduled view refreshes
3. **Backup Verification**: Regular backup integrity checks
4. **Cleanup Tasks**: Automated cleanup of temporary data