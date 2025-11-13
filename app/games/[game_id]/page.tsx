import { LayoutShell } from "../../../components/LayoutShell";
import { DataTable } from "../../../components/shared";
import {
  fetchGame,
  fetchGameBoxscoreTeam,
  fetchGamePbp,
} from "../../../lib/apiClient";
import {
  Game,
  BoxscoreTeamRow,
  PbpEventRow,
  PaginatedResponse,
  TableColumn,
} from "../../../lib/types";

/**
 * Game detail page.
 *
 * Server component:
 * - GET /api/v1/games/{game_id}
 * - GET /api/v1/games/{game_id}/boxscore-team
 * - GET /api/v1/games/{game_id}/pbp (first page only for now)
 */
interface GamePageProps {
  params: { game_id: string };
}

const boxscoreColumns: TableColumn<BoxscoreTeamRow>[] = [
  { key: "team_abbrev", label: "Team" },
  { key: "is_home", label: "Home?" },
  { key: "pts", label: "PTS" },
  { key: "opponent_team_id", label: "Opp Team ID" },
];

const pbpColumns: TableColumn<PbpEventRow>[] = [
  { key: "eventnum", label: "#" },
  { key: "period", label: "Q" },
  { key: "clk", label: "Time" },
  { key: "event_type", label: "Type" },
  { key: "team_id", label: "Team ID" },
  { key: "player1_id", label: "Player ID" },
  { key: "description", label: "Description" },
  { key: "home_score", label: "H" },
  { key: "away_score", label: "A" },
];

export default async function GamePage({ params }: GamePageProps) {
  const { game_id } = params;

  const game: Game = await fetchGame(game_id);
  const boxscoreTeams: BoxscoreTeamRow[] = await fetchGameBoxscoreTeam(game_id);

  // Best-effort: first page of PBP (e.g. 200 events)
  let pbp: PaginatedResponse<PbpEventRow> | null = null;
  try {
    pbp = await fetchGamePbp(game_id, { page: 1, page_size: 200 });
  } catch {
    pbp = null;
  }

  const titleParts: string[] = [];
  if (game.game_date_est) titleParts.push(game.game_date_est);
  if (game.is_playoffs) titleParts.push("Playoffs");
  if (game.season_end_year) titleParts.push(String(game.season_end_year));
  const title =
    titleParts.length > 0
      ? `Game ${game.game_id} • ${titleParts.join(" • ")}`
      : `Game ${game.game_id}`;

  const homeRow = boxscoreTeams.find((r) => r.is_home);
  const awayRow = boxscoreTeams.find((r) => !r.is_home);

  const headerLine =
    homeRow && awayRow
      ? `${awayRow.team_abbrev ?? awayRow.team_id} @ ${
          homeRow.team_abbrev ?? homeRow.team_id
        }`
      : "";

  const scoreLine =
    homeRow && awayRow && homeRow.pts != null && awayRow.pts != null
      ? `${awayRow.pts} - ${homeRow.pts}`
      : "";

  return (
    <LayoutShell title={title}>
      <section>
        <div className="section-title">Game Summary</div>
        <div className="subtle">
          {headerLine && <span>{headerLine}</span>}
          {scoreLine && <span>{` • Final: ${scoreLine}`}</span>}
          {game.is_playoffs && <span> • Playoffs</span>}
          {game.season_end_year && (
            <span>{` • Season ${game.season_end_year}`}</span>
          )}
        </div>
      </section>

      <section style={{ marginTop: 16 }}>
        <div className="section-title">Team Box Scores</div>
        <DataTable<BoxscoreTeamRow>
          columns={boxscoreColumns}
          rows={boxscoreTeams}
          getRowKey={(row, idx) =>
            `${row.game_id}-${row.team_id}-${row.is_home}-${idx}`
          }
        />
      </section>

      <section style={{ marginTop: 16 }}>
        <div className="section-title">Play-by-Play (first page)</div>
        {pbp && pbp.data.length > 0 ? (
          <DataTable<PbpEventRow>
            columns={pbpColumns}
            rows={pbp.data}
            getRowKey={(row) => `${row.game_id}-${row.eventnum}`}
          />
        ) : (
          <p className="muted">
            No play-by-play data available or failed to load.
          </p>
        )}
      </section>
    </LayoutShell>
  );
}