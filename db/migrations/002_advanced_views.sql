-- 002_advanced_views.sql
-- Advanced metrics and summary views for player and team seasons.

-- Player season advanced view -------------------------------------------------

DROP VIEW IF EXISTS vw_player_season_advanced CASCADE;

CREATE VIEW vw_player_season_advanced AS
SELECT
    ps.seas_id,
    ps.player_id,
    p.full_name AS player_name,
    ps.season_end_year,
    ps.team_id,
    ps.team_abbrev,
    ps.is_total,
    ps.is_playoffs,
    pst.g,
    pst.gs,
    pst.mp,
    pspg.pts_per_g,
    pspg.trb_per_g,
    pspg.ast_per_g,
    pspg.stl_per_g,
    pspg.blk_per_g,
    pspg.tov_per_g,
    pspg.fg3_per_g AS fg3m_per_g,
    CASE
        WHEN pst.fga > 0 THEN pst.fg::NUMERIC / pst.fga
        ELSE NULL
    END AS fg_pct,
    CASE
        WHEN pst.fg3a > 0 THEN pst.fg3::NUMERIC / pst.fg3a
        ELSE NULL
    END AS fg3_pct,
    CASE
        WHEN pst.fta > 0 THEN pst.ft::NUMERIC / pst.fta
        ELSE NULL
    END AS ft_pct,
    CASE
        WHEN (pst.fga + 0.44 * pst.fta) > 0
            THEN pst.pts::NUMERIC / (2 * (pst.fga + 0.44 * pst.fta))
        ELSE NULL
    END AS ts_pct,
    CASE
        WHEN pst.fga > 0
            THEN (pst.fg::NUMERIC + 0.5 * pst.fg3) / pst.fga
        ELSE NULL
    END AS efg_pct,
    psa.per,
    psa.ws,
    psa.ws_per_48,
    psa.bpm,
    psa.obpm,
    psa.dbpm
FROM player_season ps
JOIN players p
    ON p.player_id = ps.player_id
LEFT JOIN player_season_totals pst
    ON pst.seas_id = ps.seas_id
LEFT JOIN player_season_per_game pspg
    ON pspg.seas_id = ps.seas_id
LEFT JOIN player_season_advanced psa
    ON psa.seas_id = ps.seas_id;

-- Team season advanced view ---------------------------------------------------

DROP VIEW IF EXISTS vw_team_season_advanced CASCADE;

CREATE VIEW vw_team_season_advanced AS
SELECT
    ts.team_season_id,
    ts.team_id,
    t.team_abbrev,
    ts.season_end_year,
    ts.is_playoffs,
    tst.g,
    tst.pts,
    topt.opp_pts,
    CASE
        WHEN tst.g > 0
            THEN (tst.pts::NUMERIC - COALESCE(topt.opp_pts, 0)) / tst.g
        ELSE NULL
    END AS mov,
    CASE
        WHEN poss.possessions > 0
            THEN 100 * tst.pts::NUMERIC / poss.possessions
        ELSE NULL
    END AS ortg,
    CASE
        WHEN poss.possessions > 0
            THEN 100 * COALESCE(topt.opp_pts, 0)::NUMERIC / poss.possessions
        ELSE NULL
    END AS drtg,
    CASE
        WHEN poss.possessions > 0
            THEN 100 * (tst.pts::NUMERIC - COALESCE(topt.opp_pts, 0)) / poss.possessions
        ELSE NULL
    END AS nrtg
FROM team_season ts
JOIN teams t
    ON t.team_id = ts.team_id
LEFT JOIN team_season_totals tst
    ON tst.team_season_id = ts.team_season_id
LEFT JOIN team_season_opponent_totals topt
    ON topt.team_season_id = ts.team_season_id
LEFT JOIN LATERAL (
    SELECT
        (
            (
                COALESCE(tst.fga, 0)
                - COALESCE(tst.orb, 0)
                + COALESCE(tst.tov, 0)
                + 0.44 * COALESCE(tst.fta, 0)
            )
            +
            (
                COALESCE(topt.opp_fga, 0)
                - COALESCE(topt.opp_orb, 0)
                + COALESCE(topt.opp_tov, 0)
                + 0.44 * COALESCE(topt.opp_fta, 0)
            )
        ) / 2.0 AS possessions
) AS poss ON TRUE;

-- Note:
-- The above assumes team_season_opponent_totals includes opp_fga, opp_orb, opp_tov, opp_fta.
-- If those columns are not present, this view definition must be updated to match the actual schema.

-- Player career aggregates view ----------------------------------------------

DROP VIEW IF EXISTS vw_player_career_aggregates CASCADE;

CREATE VIEW vw_player_career_aggregates AS
SELECT
    ps.player_id,
    p.full_name AS player_name,
    SUM(COALESCE(pst.g, 0)) AS g,
    SUM(COALESCE(pst.mp, 0)) AS mp,
    SUM(COALESCE(pst.pts, 0)) AS pts,
    SUM(COALESCE(pst.trb, 0)) AS trb,
    SUM(COALESCE(pst.ast, 0)) AS ast,
    SUM(COALESCE(pst.stl, 0)) AS stl,
    SUM(COALESCE(pst.blk, 0)) AS blk,
    SUM(COALESCE(pst.fg3, 0)) AS fg3m,
    CASE
        WHEN SUM(COALESCE(pst.g, 0)) > 0
            THEN SUM(COALESCE(pst.pts, 0))::NUMERIC
                 / SUM(COALESCE(pst.g, 0))
        ELSE NULL
    END AS pts_per_g,
    CASE
        WHEN SUM(COALESCE(pst.g, 0)) > 0
            THEN SUM(COALESCE(pst.trb, 0))::NUMERIC
                 / SUM(COALESCE(pst.g, 0))
        ELSE NULL
    END AS trb_per_g,
    CASE
        WHEN SUM(COALESCE(pst.g, 0)) > 0
            THEN SUM(COALESCE(pst.ast, 0))::NUMERIC
                 / SUM(COALESCE(pst.g, 0))
        ELSE NULL
    END AS ast_per_g,
    CASE
        WHEN (SUM(COALESCE(pst.fga, 0)) + 0.44 * SUM(COALESCE(pst.fta, 0))) > 0
            THEN SUM(COALESCE(pst.pts, 0))::NUMERIC
                 / (2 * (SUM(COALESCE(pst.fga, 0)) + 0.44 * SUM(COALESCE(pst.fta, 0))))
        ELSE NULL
    END AS ts_pct
FROM player_season ps
JOIN players p
    ON p.player_id = ps.player_id
LEFT JOIN player_season_totals pst
    ON pst.seas_id = ps.seas_id
GROUP BY
    ps.player_id,
    p.full_name;