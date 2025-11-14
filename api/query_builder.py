from pypika import Query, Table, Field, functions as fn

# Example: Build a leaderboard query for player points

def build_leaderboard_query(table_name: str, metric: str, season: str = None, limit: int = 10):
    table = Table(table_name)
    q = (
        Query.from_(table)
        .select(table.player_id, fn.Sum(Field(metric)).as_('total_metric'))
        .groupby(table.player_id)
        .orderby(fn.Sum(Field(metric)), order='desc')
        .limit(limit)
    )
    if season:
        q = q.where(Field('season') == season)
    return q.get_sql()

# Example usage:
# sql = build_leaderboard_query('player_stats', 'points', season='2024', limit=10)
