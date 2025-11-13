# API Endpoints Documentation: Basketball Data Hub

**API Version**: FastAPI with async SQLAlchemy
**Base URL**: `http://localhost:8000/api/v1`
**Documentation**: Available at `/docs` (OpenAPI/Swagger)
**Authentication**: JWT-based (planned) + API key options

---

## Core Entity Endpoints

### Players
**Base Path**: `/players`

#### Get All Players
```
GET /api/v1/players
```
**Parameters**:
- `page` (int, default: 1): Pagination page number
- `limit` (int, default: 50): Results per page (max: 100)
- `position` (str, optional): Filter by player position
- `search` (str, optional): Search by name
- `season` (int, optional): Filter by season year

**Response**:
```json
{
  "players": [
    {
      "player_id": "uuid",
      "first_name": "LeBron",
      "last_name": "James",
      "birth_date": "1984-12-30",
      "height_inches": 80,
      "weight_lbs": 250,
      "position": "SF",
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 50,
    "total": 450,
    "pages": 9
  }
}
```

#### Get Player by ID
```
GET /api/v1/players/{player_id}
```
**Parameters**:
- `player_id` (UUID, required): Player identifier

**Response**:
```json
{
  "player_id": "uuid",
  "first_name": "LeBron",
  "last_name": "James",
  "birth_date": "1984-12-30",
  "height_inches": 80,
  "weight_lbs": 250,
  "position": "SF",
  "seasons": [
    {
      "season_id": "uuid",
      "year": 2023,
      "team_id": "uuid",
      "team_name": "Los Angeles Lakers",
      "games_played": 55,
      "points_per_game": 25.7,
      "rebounds_per_game": 7.3,
      "assists_per_game": 8.3
    }
  ],
  "career_stats": {
    "total_games": 1421,
    "career_ppg": 27.2,
    "career_rpg": 7.5,
    "career_apg": 7.3,
    "career_fg_pct": 0.504
  }
}
```

### Teams
**Base Path**: `/teams`

#### Get All Teams
```
GET /api/v1/teams
```
**Parameters**:
- `page` (int, default: 1): Pagination page number
- `limit` (int, default: 50): Results per page (max: 100)
- `league` (str, optional): Filter by league
- `search` (str, optional): Search by team name
- `season` (int, optional): Filter by season year

**Response**:
```json
{
  "teams": [
    {
      "team_id": "uuid",
      "name": "Los Angeles Lakers",
      "abbreviation": "LAL",
      "city": "Los Angeles",
      "state": "CA",
      "founded_year": 1947,
      "league": "NBA",
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 50,
    "total": 30,
    "pages": 1
  }
}
```

#### Get Team by ID
```
GET /api/v1/teams/{team_id}
```
**Parameters**:
- `team_id` (UUID, required): Team identifier

**Response**:
```json
{
  "team_id": "uuid",
  "name": "Los Angeles Lakers",
  "abbreviation": "LAL",
  "city": "Los Angeles",
  "state": "CA",
  "founded_year": 1947,
  "league": "NBA",
  "seasons": [
    {
      "season_id": "uuid",
      "year": 2023,
      "games_played": 82,
      "wins": 43,
      "losses": 39,
      "win_percentage": 0.524,
      "points_per_game": 118.9,
      "points_allowed_per_game": 117.2
    }
  ],
  "current_roster": [
    {
      "player_id": "uuid",
      "first_name": "LeBron",
      "last_name": "James",
      "position": "SF",
      "jersey_number": 23
    }
  ]
}
```

### Games
**Base Path**: `/games`

#### Get Games by Date Range
```
GET /api/v1/games
```
**Parameters**:
- `start_date` (date, required): Game start date (YYYY-MM-DD)
- `end_date` (date, required): Game end date (YYYY-MM-DD)
- `team_id` (UUID, optional): Filter by team
- `season` (int, optional): Filter by season year
- `page` (int, default: 1): Pagination page number
- `limit` (int, default: 50): Results per page (max: 100)

**Response**:
```json
{
  "games": [
    {
      "game_id": "uuid",
      "season_id": "uuid",
      "home_team": {
        "team_id": "uuid",
        "name": "Los Angeles Lakers",
        "abbreviation": "LAL"
      },
      "away_team": {
        "team_id": "uuid",
        "name": "Boston Celtics",
        "abbreviation": "BOS"
      },
      "game_date": "2024-01-25T19:30:00Z",
      "home_score": 120,
      "away_score": 108,
      "venue": "Crypto.com Arena",
      "attendance": 18997,
      "status": "completed"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 50,
    "total": 1230,
    "pages": 25
  }
}
```

#### Get Game by ID
```
GET /api/v1/games/{game_id}
```
**Parameters**:
- `game_id` (UUID, required): Game identifier

**Response**:
```json
{
  "game_id": "uuid",
  "season_id": "uuid",
  "home_team": {
    "team_id": "uuid",
    "name": "Los Angeles Lakers",
    "abbreviation": "LAL"
  },
  "away_team": {
    "team_id": "uuid",
    "name": "Boston Celtics",
    "abbreviation": "BOS"
  },
  "game_date": "2024-01-25T19:30:00Z",
  "home_score": 120,
  "away_score": 108,
  "venue": "Crypto.com Arena",
  "attendance": 18997,
  "status": "completed",
  "play_by_play": [
    {
      "play_id": "uuid",
      "period": 1,
      "time_remaining": 720,
      "play_type": "field_goal",
      "description": "LeBron James makes 2-point shot",
      "player_id": "uuid",
      "team_id": "uuid",
      "points_scored": 2
    }
  ],
  "box_score": {
    "home_players": [
      {
        "player_id": "uuid",
        "first_name": "LeBron",
        "last_name": "James",
        "minutes_played": 38,
        "points": 28,
        "rebounds": 7,
        "assists": 8,
        "field_goals_made": 11,
        "field_goals_attempted": 22
      }
    ],
    "away_players": [...]
  }
}
```

### Seasons
**Base Path**: `/seasons`

#### Get All Seasons
```
GET /api/v1/seasons
```
**Parameters**:
- `page` (int, default: 1): Pagination page number
- `limit` (int, default: 50): Results per page (max: 100)
- `active` (bool, optional): Filter by active status

**Response**:
```json
{
  "seasons": [
    {
      "season_id": "uuid",
      "year": 2023,
      "start_date": "2023-10-24",
      "end_date": "2024-04-09",
      "is_active": false,
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 50,
    "total": 75,
    "pages": 2
  }
}
```

---

## Statistics Endpoints

### Player Season Stats
**Base Path**: `/stats/player-seasons`

#### Get Player Season Statistics
```
GET /api/v1/stats/player-seasons
```
**Parameters**:
- `player_id` (UUID, optional): Filter by player
- `season` (int, optional): Filter by season year
- `team_id` (UUID, optional): Filter by team
- `min_games` (int, default: 10): Minimum games played
- `sort_by` (str, default: "points_per_game"): Sort field
- `sort_order` (str, default: "desc"): Sort order (asc/desc)
- `page` (int, default: 1): Pagination page number
- `limit` (int, default: 50): Results per page (max: 100)

**Response**:
```json
{
  "stats": [
    {
      "player_season_id": "uuid",
      "player_id": "uuid",
      "season_id": "uuid",
      "team_id": "uuid",
      "player": {
        "first_name": "LeBron",
        "last_name": "James"
      },
      "team": {
        "name": "Los Angeles Lakers",
        "abbreviation": "LAL"
      },
      "season": {
        "year": 2023
      },
      "games_played": 55,
      "minutes_played": 35.4,
      "points_per_game": 25.7,
      "rebounds_per_game": 7.3,
      "assists_per_game": 8.3,
      "field_goal_percentage": 0.504,
      "three_point_percentage": 0.321,
      "free_throw_percentage": 0.768,
      "advanced_stats": {
        "player_efficiency_rating": 25.4,
        "true_shooting_percentage": 0.585,
        "assist_ratio": 0.312
      }
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 50,
    "total": 450,
    "pages": 9
  }
}
```

### Team Season Stats
**Base Path**: `/stats/team-seasons`

#### Get Team Season Statistics
```
GET /api/v1/stats/team-seasons
```
**Parameters**:
- `team_id` (UUID, optional): Filter by team
- `season` (int, optional): Filter by season year
- `min_games` (int, default: 10): Minimum games played
- `sort_by` (str, default: "win_percentage"): Sort field
- `sort_order` (str, default: "desc"): Sort order (asc/desc)
- `page` (int, default: 1): Pagination page number
- `limit` (int, default: 50): Results per page (max: 100)

**Response**:
```json
{
  "stats": [
    {
      "team_season_id": "uuid",
      "team_id": "uuid",
      "season_id": "uuid",
      "team": {
        "name": "Los Angeles Lakers",
        "abbreviation": "LAL"
      },
      "season": {
        "year": 2023
      },
      "games_played": 82,
      "wins": 43,
      "losses": 39,
      "win_percentage": 0.524,
      "points_per_game": 118.9,
      "points_allowed_per_game": 117.2,
      "offensive_rating": 112.4,
      "defensive_rating": 110.7,
      "pace": 98.7
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 50,
    "total": 30,
    "pages": 1
  }
}
```

---

## Analytics Tools Endpoints

### Player Finder
**Base Path**: `/tools/player-finder`

#### Find Players by Criteria
```
GET /api/v1/tools/player-finder
```
**Parameters**:
- `position` (str, optional): Player position filter
- `min_height` (int, optional): Minimum height in inches
- `max_height` (int, optional): Maximum height in inches
- `min_weight` (int, optional): Minimum weight in lbs
- `max_weight` (int, optional): Maximum weight in lbs
- `min_ppg` (float, optional): Minimum points per game
- `max_ppg` (float, optional): Maximum points per game
- `min_rpg` (float, optional): Minimum rebounds per game
- `max_rpg` (float, optional): Maximum rebounds per game
- `min_apg` (float, optional): Minimum assists per game
- `max_apg` (float, optional): Maximum assists per game
- `season` (int, optional): Season year filter
- `team_id` (UUID, optional): Team filter
- `age_range` (str, optional): Age range (e.g., "25-30")
- `sort_by` (str, default: "points_per_game"): Sort field
- `sort_order` (str, default: "desc"): Sort order (asc/desc)
- `page` (int, default: 1): Pagination page number
- `limit` (int, default: 50): Results per page (max: 100)

**Response**: Similar to player season stats with filtering applied

### Team Finder
**Base Path**: `/tools/team-finder`

#### Find Teams by Criteria
```
GET /api/v1/tools/team-finder
```
**Parameters**:
- `conference` (str, optional): Conference filter
- `division` (str, optional): Division filter
- `min_wins` (int, optional): Minimum wins
- `max_wins` (int, optional): Maximum wins
- `min_win_pct` (float, optional): Minimum win percentage
- `max_win_pct` (float, optional): Maximum win percentage
- `min_ppg` (float, optional): Minimum points per game
- `max_ppg` (float, optional): Maximum points per game
- `season` (int, optional): Season year filter
- `sort_by` (str, default: "win_percentage"): Sort field
- `sort_order` (str, default: "desc"): Sort order (asc/desc)
- `page` (int, default: 1): Pagination page number
- `limit` (int, default: 50): Results per page (max: 100)

**Response**: Similar to team season stats with filtering applied

### Leaderboards
**Base Path**: `/tools/leaderboards`

#### Get Player Leaderboards
```
GET /api/v1/tools/leaderboards/players
```
**Parameters**:
- `stat_type` (str, required): Statistic type (points, rebounds, assists, steals, blocks)
- `season` (int, optional): Season year filter
- `min_games` (int, default: 10): Minimum games played
- `page` (int, default: 1): Pagination page number
- `limit` (int, default: 50): Results per page (max: 100)

**Response**:
```json
{
  "leaderboard": [
    {
      "rank": 1,
      "player_id": "uuid",
      "player": {
        "first_name": "Giannis",
        "last_name": "Antetokounmpo"
      },
      "team": {
        "name": "Milwaukee Bucks",
        "abbreviation": "MIL"
      },
      "season": {
        "year": 2023
      },
      "stat_value": 31.1,
      "games_played": 63,
      "stat_type": "points_per_game"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 50,
    "total": 450,
    "pages": 9
  }
}
```

#### Get Team Leaderboards
```
GET /api/v1/tools/leaderboards/teams
```
**Parameters**:
- `stat_type` (str, required): Statistic type (wins, points_per_game, win_percentage)
- `season` (int, optional): Season year filter
- `page` (int, default: 1): Pagination page number
- `limit` (int, default: 50): Results per page (max: 100)

**Response**: Similar structure to player leaderboards

### Splits Analysis
**Base Path**: `/tools/splits`

#### Get Player Splits
```
GET /api/v1/tools/splits/players/{player_id}
```
**Parameters**:
- `player_id` (UUID, required): Player identifier
- `season` (int, optional): Season year filter
- `split_type` (str, default: "overall"): Split type (home/away, win/loss, month)
- `opponent_team_id` (UUID, optional): Opponent team filter

**Response**:
```json
{
  "player_id": "uuid",
  "player": {
    "first_name": "LeBron",
    "last_name": "James"
  },
  "season": {
    "year": 2023
  },
  "splits": [
    {
      "split_type": "home_away",
      "split_value": "home",
      "games_played": 28,
      "points_per_game": 27.8,
      "rebounds_per_game": 7.1,
      "assists_per_game": 8.4,
      "field_goal_percentage": 0.512
    },
    {
      "split_type": "home_away",
      "split_value": "away",
      "games_played": 27,
      "points_per_game": 23.6,
      "rebounds_per_game": 7.5,
      "assists_per_game": 8.2,
      "field_goal_percentage": 0.496
    }
  ]
}
```

### Streaks Analysis
**Base Path**: `/tools/streaks`

#### Get Player Streaks
```
GET /api/v1/tools/streaks/players/{player_id}
```
**Parameters**:
- `player_id` (UUID, required): Player identifier
- `season` (int, optional): Season year filter
- `streak_type` (str, default: "points"): Streak type (points, double_doubles, games)
- `min_length` (int, default: 3): Minimum streak length

**Response**:
```json
{
  "player_id": "uuid",
  "player": {
    "first_name": "LeBron",
    "last_name": "James"
  },
  "season": {
    "year": 2023
  },
  "streaks": [
    {
      "streak_type": "points",
      "start_date": "2023-11-25",
      "end_date": "2023-12-20",
      "length": 10,
      "values": [25, 30, 28, 32, 35, 27, 31, 29, 33, 30],
      "description": "10+ points for 10 consecutive games"
    }
  ]
}
```

### Versus Comparison
**Base Path**: `/tools/versus`

#### Compare Players
```
GET /api/v1/tools/versus/players
```
**Parameters**:
- `player1_id` (UUID, required): First player identifier
- `player2_id` (UUID, required): Second player identifier
- `season` (int, optional): Season year filter
- `stat_type` (str, default: "all"): Statistic type filter

**Response**:
```json
{
  "player1": {
    "player_id": "uuid",
    "first_name": "LeBron",
    "last_name": "James"
  },
  "player2": {
    "player_id": "uuid",
    "first_name": "Kevin",
    "last_name": "Durant"
  },
  "season": {
    "year": 2023
  },
  "comparison": {
    "head_to_head": {
      "player1_wins": 8,
      "player2_wins": 6,
      "player1_points": 245,
      "player2_points": 238
    },
    "season_stats": {
      "player1": {
        "games_played": 55,
        "points_per_game": 25.7,
        "rebounds_per_game": 7.3,
        "assists_per_game": 8.3
      },
      "player2": {
        "games_played": 57,
        "points_per_game": 29.1,
        "rebounds_per_game": 6.8,
        "assists_per_game": 5.2
      }
    }
  }
}
```

---

## Event Finder
**Base Path**: `/tools/event-finder`

#### Find Specific Game Events
```
GET /api/v1/tools/event-finder
```
**Parameters**:
- `event_type` (str, required): Event type (triple_double, 50_point_game, buzzer_beater)
- `season` (int, optional): Season year filter
- `team_id` (UUID, optional): Team filter
- `player_id` (UUID, optional): Player filter
- `start_date` (date, optional): Start date range
- `end_date` (date, optional): End date range
- `page` (int, default: 1): Pagination page number
- `limit` (int, default: 50): Results per page (max: 100)

**Response**:
```json
{
  "events": [
    {
      "event_id": "uuid",
      "event_type": "triple_double",
      "game_id": "uuid",
      "game_date": "2024-01-25T19:30:00Z",
      "player_id": "uuid",
      "player": {
        "first_name": "Nikola",
        "last_name": "Jokić"
      },
      "team": {
        "name": "Denver Nuggets",
        "abbreviation": "DEN"
      },
      "opponent": {
        "name": "Phoenix Suns",
        "abbreviation": "PHX"
      },
      "stats": {
        "points": 25,
        "rebounds": 12,
        "assists": 10,
        "blocks": 2,
        "steals": 1
      },
      "description": "25 points, 12 rebounds, 10 assists, 2 blocks vs Phoenix Suns"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 50,
    "total": 156,
    "pages": 4
  }
}
```

---

## Health and Monitoring

### Health Check
**Base Path**: `/health`

#### System Health
```
GET /api/v1/health
```
**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-25T12:00:00Z",
  "version": "1.0.0",
  "uptime": 86400,
  "database": {
    "status": "connected",
    "connection_pool": {
      "active": 5,
      "idle": 15,
      "total": 20
    }
  },
  "etl": {
    "last_run": "2024-01-25T02:00:00Z",
    "status": "completed",
    "records_processed": 15420
  }
}
```

### Metrics
**Base Path**: `/metrics`

#### System Metrics
```
GET /api/v1/metrics
```
**Response**:
```json
{
  "timestamp": "2024-01-25T12:00:00Z",
  "requests": {
    "total": 15420,
    "success_rate": 0.998,
    "average_response_time": 145,
    "requests_per_second": 12.5
  },
  "database": {
    "connection_pool": {
      "active": 5,
      "idle": 15,
      "total": 20
    },
    "query_performance": {
      "average_time": 45,
      "slow_queries": 12
    }
  },
  "cache": {
    "hit_rate": 0.85,
    "memory_usage": 0.65
  }
}
```

---

## Authentication Endpoints (Planned)

### Login
**Base Path**: `/auth`

#### User Authentication
```
POST /api/v1/auth/login
```
**Request Body**:
```json
{
  "email": "user@example.com",
  "password": "password"
}
```
**Response**:
```json
{
  "access_token": "jwt_token_here",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "user_id": "uuid",
    "email": "user@example.com",
    "name": "John Doe"
  }
}
```

### Refresh Token
```
POST /api/v1/auth/refresh
```
**Request Headers**:
- `Authorization: Bearer {access_token}`

**Response**:
```json
{
  "access_token": "new_jwt_token_here",
  "token_type": "bearer",
  "expires_in": 3600
}
```

---

## Error Responses

### Standard Error Format
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid parameter value",
    "details": {
      "field": "player_id",
      "value": "invalid_uuid",
      "constraint": "Must be a valid UUID"
    }
  },
  "timestamp": "2024-01-25T12:00:00Z",
  "request_id": "req_123456"
}
```

### Common Error Codes
- `VALIDATION_ERROR`: Invalid input parameters
- `NOT_FOUND`: Resource not found
- `UNAUTHORIZED`: Authentication required/invalid
- `RATE_LIMITED`: Too many requests
- `INTERNAL_ERROR`: Server error
- `DATABASE_ERROR`: Database operation failed
- `SERVICE_UNAVAILABLE`: External service unavailable

---

## Rate Limiting

### Limits
- **Anonymous Users**: 100 requests per minute
- **Authenticated Users**: 1000 requests per minute
- **Premium Users**: 5000 requests per minute

### Headers
- `X-RateLimit-Limit`: Request limit per window
- `X-RateLimit-Remaining`: Remaining requests in window
- `X-RateLimit-Reset`: Time when limit resets (Unix timestamp)

---

## Caching Strategy

### Cache Keys
- **Player Data**: `player:{player_id}:{season}` (TTL: 1 hour)
- **Team Data**: `team:{team_id}:{season}` (TTL: 1 hour)
- **Game Data**: `game:{game_id}` (TTL: 30 minutes)
- **Statistics**: `stats:{type}:{season}:{entity_id}` (TTL: 6 hours)
- **Leaderboards**: `leaderboard:{stat_type}:{season}` (TTL: 15 minutes)

### Cache Invalidation
- **Player Updates**: Invalidate player cache on stat changes
- **Game Completion**: Invalidate game cache when final score posted
- **ETL Runs**: Invalidate relevant caches after data updates
- **Manual Refresh**: Admin endpoint to clear specific cache keys

---

## API Versioning

### Version Strategy
- **URL Versioning**: `/api/v1/`, `/api/v2/`
- **Header Versioning**: `Accept: application/vnd.basketball.v1+json`
- **Backward Compatibility**: Maintain previous versions for 6 months
- **Depreciation Notice**: 3 months before version removal

### Version Differences
- **v1**: Current implementation
- **v2**: Planned features (real-time updates, advanced analytics)
- **v3**: Future (AI-powered insights, predictive analytics)

---

## WebSocket Endpoints (Planned)

### Real-time Updates
**Base Path**: `/ws`

#### Game Updates
```
WS /api/v1/ws/game/{game_id}
```
**Message Types**:
- `score_update`: Score changes
- `play_update`: New play events
- `status_change`: Game status updates
- `player_stats`: Player statistics updates

#### Live Leaderboards
```
WS /api/v1/ws/leaderboards
```
**Message Types**:
- `leaderboard_update`: Ranking changes
- `stat_update`: Player statistic updates
- `game_completion`: Final game results

---

## OpenAPI Documentation

### Interactive Docs
- **URL**: `/docs`
- **Format**: Swagger UI with interactive testing
- **Authentication**: API key authentication for testing
- **Code Examples**: Auto-generated for all endpoints

### Schema Download
- **JSON Schema**: `/openapi.json`
- **YAML Schema**: `/openapi.yaml`
- **Postman Collection**: `/postman-collection.json`

---

## Testing Endpoints

### Smoke Tests
**Base Path**: `/test/smoke`

#### API Health Check
```
GET /api/v1/test/smoke
```
**Response**:
```json
{
  "status": "passed",
  "timestamp": "2024-01-25T12:00:00Z",
  "tests": {
    "database_connection": "passed",
    "authentication": "passed",
    "external_apis": "passed",
    "cache_functionality": "passed"
  }
}
```

### Load Tests
**Base Path**: `/test/load`

#### Performance Testing
```
POST /api/v1/test/load
```
**Request Body**:
```json
{
  "test_type": "player_search",
  "concurrent_users": 100,
  "duration_seconds": 60
  "endpoint": "/api/v1/players"
}
```

**Response**:
```json
{
  "test_id": "uuid",
  "status": "running",
  "started_at": "2024-01-25T12:00:00Z",
  "estimated_completion": "2024-01-25T12:01:00Z"
}