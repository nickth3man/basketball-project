# Type 2 Slowly Changing Dimension Implementation for Team Data

## Overview

This implementation establishes a **Type 2 Slowly Changing Dimension** (SCD) for NBA team information, following industry best practices from dimensional modeling (Kimball methodology) and aligning with NBA official conventions.

## Files Created

1. **`db/migrations/002_team_dimension_scd.sql`** - Core schema migration
2. **`db/migrations/003_games_table_surrogate_keys.sql`** - Fact table FK migration  
3. **`etl/load_team_dimension.py`** - ETL loader with bootstrap data
4. **`docs/TEAM_DIMENSION_SCD.md`** - This documentation

## Design Principles

### Natural Key Persistence
- **NBA team_id** is the natural key (e.g., `1610612760`)
- Persists across relocations: Seattle SuperSonics → OKC Thunder use **same team_id**
- Aligns with NBA API, Basketball-Reference, and official NBA infrastructure

### Surrogate Keys
- **team_surrogate_key** (SERIAL PRIMARY KEY) uniquely identifies each dimension version
- Used in fact table foreign keys for query performance
- One surrogate key per "version" of a team (e.g., Seattle vs OKC = 2 surrogate keys, same team_id)

### Temporal Tracking
- **effective_start_date** / **effective_end_date**: Date boundaries for each version
- **is_current**: Boolean flag for active version (9999-12-31 end date)
- **change_reason**: Documents why new version was created

### Change Reasons
```sql
'relocation'                -- Physical move (Seattle → OKC)
'rebranding'                -- Name change same city (Bobcats → Hornets)
'conference_realignment'    -- Division/conference change
'shared_history_transfer'   -- Charlotte reclaiming 1988-2002 history
'expansion'                 -- New franchise creation
'name_change'               -- Minor name updates
```

## Real-World Examples

### Example 1: Seattle SuperSonics → OKC Thunder

| team_surrogate_key | team_id    | season_year | team_city      | team_name   | effective_start_date | effective_end_date | is_current | change_reason |
|--------------------|------------|-------------|----------------|-------------|----------------------|--------------------| -----------|---------------|
| 1                  | 1610612760 | 1967-68     | Seattle        | SuperSonics | 1967-10-13           | 2008-06-30         | FALSE      | NULL          |
| 2                  | 1610612760 | 2008-09     | Oklahoma City  | Thunder     | 2008-07-01           | 9999-12-31         | TRUE       | relocation    |

**Query Pattern:**
```sql
-- Get team info for a 2005 Seattle game
SELECT * FROM team_info_common 
WHERE team_id = 1610612760 
  AND '2005-03-20' BETWEEN effective_start_date AND effective_end_date;
-- Returns: Seattle SuperSonics (team_surrogate_key = 1)

-- Get team info for a 2010 OKC game
SELECT * FROM team_info_common 
WHERE team_id = 1610612760 
  AND '2010-01-15' BETWEEN effective_start_date AND effective_end_date;
-- Returns: Oklahoma City Thunder (team_surrogate_key = 2)
```

### Example 2: Charlotte Bobcats → Hornets

| team_surrogate_key | team_id    | season_year | team_city | team_name | effective_start_date | effective_end_date | is_current | change_reason |
|--------------------|------------|-------------|-----------|-----------|----------------------|--------------------|------------|---------------|
| 3                  | 1610612751 | 2004-05     | Charlotte | Bobcats   | 2004-11-04           | 2014-05-20         | FALSE      | NULL          |
| 4                  | 1610612751 | 2014-15     | Charlotte | Hornets   | 2014-10-29           | 9999-12-31         | TRUE       | rebranding    |

## ETL Workflow

### 1. Bootstrap Phase
```bash
python -m etl.load_team_dimension
```

Inserts known relocations/rebrandings:
- Seattle → OKC (team_id 1610612760)
- Charlotte Bobcats → Hornets (team_id 1610612751)

### 2. Fact Table Migration

**Step 1: Add surrogate key columns**
```sql
ALTER TABLE games 
    ADD COLUMN home_team_surrogate_key INTEGER,
    ADD COLUMN away_team_surrogate_key INTEGER;
```

**Step 2: Populate from natural keys + game_date**
```sql
UPDATE games SET home_team_surrogate_key = (
    SELECT team_surrogate_key
    FROM team_info_common
    WHERE team_id = games.home_team_id
      AND effective_start_date <= games.game_date_est
      AND effective_end_date >= games.game_date_est
    LIMIT 1
);
```

**Step 3: Validate before enforcing constraints**
```sql
SELECT COUNT(*) 
FROM games 
WHERE home_team_id IS NOT NULL 
  AND home_team_surrogate_key IS NULL;
-- Should return 0
```

### 3. Python Integration

**Lookup Function:**
```python
from etl.load_team_dimension import lookup_team_surrogate_key

# Resolve surrogate key for fact table insert
surrogate_key = lookup_team_surrogate_key(
    conn=conn,
    team_id=1610612760,  # Seattle/OKC franchise
    as_of_date='2010-01-15'  # Game date
)
# Returns: 2 (OKC Thunder version)
```

**Change Detection:**
```python
# When loading new season data
if team_city_changed or team_name_changed:
    # Close previous version
    UPDATE team_info_common 
    SET effective_end_date = new_season_start - 1 day,
        is_current = FALSE
    WHERE team_id = X AND is_current = TRUE;
    
    # Insert new version
    INSERT INTO team_info_common (...) 
    VALUES (..., new_effective_start_date, '9999-12-31', TRUE, 'relocation');
```

## Validation Rules

### Rule 1: Single Current Version
Each team_id must have exactly **one** `is_current = TRUE` record.

```sql
SELECT team_id, COUNT(*) 
FROM team_info_common 
WHERE is_current = TRUE 
GROUP BY team_id 
HAVING COUNT(*) != 1;
```

### Rule 2: No Temporal Gaps
Versions must be contiguous (no date gaps).

```sql
WITH versions AS (
    SELECT team_id, effective_end_date,
           LEAD(effective_start_date) OVER (
               PARTITION BY team_id ORDER BY effective_start_date
           ) AS next_start_date
    FROM team_info_common
    WHERE is_current = FALSE
)
SELECT * FROM versions
WHERE effective_end_date + INTERVAL '1 day' != next_start_date;
```

### Rule 3: FK Integrity
All team_id values must exist in `teams` table.

```sql
SELECT DISTINCT team_id 
FROM team_info_common
WHERE team_id NOT IN (SELECT team_id FROM teams);
```

## Query Patterns

### Current Team Snapshot
```sql
SELECT * FROM v_teams_current
WHERE team_abbreviation = 'OKC';
```

### Historical Point-in-Time Query
```sql
-- What was the team called on a specific date?
SELECT team_city, team_name, team_abbreviation
FROM team_info_common
WHERE team_id = 1610612760
  AND '2007-06-15' BETWEEN effective_start_date AND effective_end_date;
-- Returns: Seattle SuperSonics
```

### Complete Franchise History
```sql
SELECT * FROM v_team_franchise_history
WHERE team_id = 1610612760
ORDER BY effective_start_date;
```

### Find All Relocations
```sql
SELECT team_id, season_year, 
       team_city, team_name,
       effective_start_date, change_reason
FROM team_info_common
WHERE change_reason = 'relocation'
ORDER BY effective_start_date;
```

## Convention Alignment

### NBA Official
- ✅ **team_id persistence**: 1610612760 persists Seattle → OKC
- ✅ **"Shared history" framework**: Administrative vs physical ownership separation
- ✅ **API endpoints**: FranchiseHistory provides temporal tracking

### Basketball-Reference
- ✅ **Current slug contains full history**: OKC page includes 1967-present
- ✅ **Uniform numbers**: Players listed from both Seattle and OKC eras
- ✅ **Championships**: OKC page credits 1979 Seattle title

### Sports Analytics Standard
- ✅ **Type 2 SCD**: Industry pattern from NFL/MLB (Chargers, Raiders examples)
- ✅ **Surrogate keys**: Sequential integers per version
- ✅ **Effective dates**: 9999-12-31 for current, date boundaries for historical
- ✅ **Change tracking**: change_reason field documents transitions

## Future Enhancements

1. **Full Team Coverage**
   - Bootstrap all 30 current teams
   - Import complete franchise history from nba_api.FranchiseHistory

2. **Automated Change Detection**
   - Compare incoming season data vs current dimension
   - Auto-insert new versions on changes

3. **Charlotte History Reclamation**
   - Handle 1988-2002 original Hornets history
   - Implement shared_history_transfer logic

4. **Conference Realignment Tracking**
   - Detect division/conference changes
   - Create versions with change_reason = 'conference_realignment'

5. **Season Metadata Integration**
   - Link to team_season tables
   - Enrich with performance metrics (w, l, pct, rankings)

## Testing

### Test Scenario 1: Seattle → OKC Lookup
```sql
-- Seattle game (2005)
SELECT team_surrogate_key FROM team_info_common
WHERE team_id = 1610612760 AND '2005-03-20' BETWEEN effective_start_date AND effective_end_date;
-- Expected: 1

-- OKC game (2010)
SELECT team_surrogate_key FROM team_info_common
WHERE team_id = 1610612760 AND '2010-01-15' BETWEEN effective_start_date AND effective_end_date;
-- Expected: 2
```

### Test Scenario 2: Charlotte Rebranding
```sql
-- Bobcats game (2012)
SELECT team_surrogate_key FROM team_info_common
WHERE team_id = 1610612751 AND '2012-02-10' BETWEEN effective_start_date AND effective_end_date;
-- Expected: 3

-- Hornets game (2015)
SELECT team_surrogate_key FROM team_info_common
WHERE team_id = 1610612751 AND '2015-11-20' BETWEEN effective_start_date AND effective_end_date;
-- Expected: 4
```

### Test Scenario 3: Validation
```bash
python -m etl.load_team_dimension
# Output should show:
# - 4 dimension versions inserted
# - Validation passed: temporal consistency OK
# - 0 errors
```

## References

- **Sequential Thinking Research**: 6-thought framework validating NBA conventions, Basketball-Reference patterns, and Type 2 SCD standards
- **NBA API Convention**: team_id 1610612760 persists across Seattle → OKC transition
- **Kimball Methodology**: Surrogate keys, effective dates, change tracking
- **Sports Analytics Examples**: NFL (Chargers, Raiders), MLB (Dodgers, Colts)
