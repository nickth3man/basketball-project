import { LayoutShell } from "../../../components/LayoutShell";
import { DataTable } from "../../../components/shared";
import {
  fetchSeason,
  fetchSeasons,
  runLeaderboards,
} from "../../../lib/apiClient";
import {
  Season,
  LeaderboardsResponseRow,
  PaginatedResponse,
  TableColumn,
} from "../../../lib/types";

/**
 * Season detail page.
 *
 * Server component:
 * - GET /api/v1/seasons/{season}
 * - Uses /tools/leaderboards to show top players and teams for the season.
 */
interface SeasonPageProps {
  params: { season: string };
}

const playerLbColumns: TableColumn<LeaderboardsResponseRow>[] = [
  { key: "label", label: "Player" },
  { key: "stat", label: "PTS/G" },
];

const teamLbColumns: TableColumn<LeaderboardsResponseRow>[] = [
  { key: "label", label: "Team" },
  { key: "stat", label: "PTS Diff" },
];

export default async function SeasonPage({ params }: SeasonPageProps) {
  const seasonYear = Number(params.season);

  // Fetch canonical season
  const season: Season = await fetchSeason(seasonYear);

  // Fallback: if season fetch fails (unlikely), keep page minimal via try/catch
  let topPlayers: PaginatedResponse<LeaderboardsResponseRow> | null = null;
  let topTeams: PaginatedResponse<LeaderboardsResponseRow> | null = null;

  try {
    topPlayers = await runLeaderboards({
      scope: "player_season",
      stat: "pts_per_g",
      season_end_year: seasonYear,
      page: 1,
      page_size: 25,
    });
  } catch {
    topPlayers = null;
  }

  try {
    topTeams = await runLeaderboards({
      scope: "team_season",
      stat: "pts_diff",
      season_end_year: seasonYear,
      page: 1,
      page_size: 25,
    });
  } catch {
    topTeams = null;
  }

  const title = `${season.season_end_year} Season${
    season.lg ? ` (${season.lg})` : ""
  }`;

  return (
    <LayoutShell title={title}>
      <section>
        <div className="section-title">Season Overview</div>
        <div className="subtle">
          ID {season.season_id}
          {season.lg ? ` • League: ${season.lg}` : ""}
          {season.is_lockout ? " • Lockout season" : ""}
        </div>
      </section>

      <section style={{ marginTop: 16 }}>
        <div className="section-title">Top Players (Points Per Game)</div>
        {topPlayers && topPlayers.data.length > 0 ? (
          <DataTable<LeaderboardsResponseRow>
            columns={playerLbColumns}
            rows={topPlayers.data}
            getRowKey={(row, idx) =>
              `${row.subject_id}-${row.game_id ?? "ps"}-${idx}`
            }
          />
        ) : (
          <p className="muted">No leaderboard data available for this season.</p>
        )}
      </section>

      <section style={{ marginTop: 16 }}>
        <div className="section-title">Top Teams (Point Differential)</div>
        {topTeams && topTeams.data.length > 0 ? (
          <DataTable<LeaderboardsResponseRow>
            columns={teamLbColumns}
            rows={topTeams.data}
            getRowKey={(row, idx) =>
              `${row.subject_id}-${row.game_id ?? "ts"}-${idx}`
            }
          />
        ) : (
          <p className="muted">No team leaderboard data available for this season.</p>
        )}
      </section>
    </LayoutShell>
  );
}