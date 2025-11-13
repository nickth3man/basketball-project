import {
  fetchPlayer,
  fetchPlayerSeasons,
  type Player,
  type PlayerSeasonSummary,
  type PaginatedResponse,
} from "../../../lib/apiClient";
import { LayoutShell } from "../../../components/LayoutShell";
import { DataTable } from "../../../components/shared";

interface PlayerPageProps {
  params: { player_id: string };
}

/**
 * Player detail page:
 * - GET /api/v1/players/{player_id}
 * - GET /api/v1/players/{player_id}/seasons
 */
export default async function PlayerPage({ params }: PlayerPageProps) {
  const playerId = Number(params.player_id);
  const player: Player = await fetchPlayer(playerId);
  const seasons: PaginatedResponse<PlayerSeasonSummary> =
    await fetchPlayerSeasons(playerId, { page: 1, page_size: 200 });

  const seasonColumns = [
    { key: "season_end_year", label: "Season" },
    { key: "team_abbrev", label: "Team" },
    { key: "is_playoffs", label: "PO" },
    { key: "g", label: "G" },
    { key: "pts_per_g", label: "PTS/G" },
    { key: "trb_per_g", label: "TRB/G" },
    { key: "ast_per_g", label: "AST/G" },
  ];

  return (
    <LayoutShell
      title={
        player.full_name
          ? `${player.full_name} (${player.player_id})`
          : `Player ${player.player_id}`
      }
    >
      <section>
        <div className="section-title">Bio</div>
        <div className="subtle">
          ID {player.player_id}
          {player.slug ? ` • ${player.slug}` : ""}
          {player.rookie_year
            ? ` • ${player.rookie_year}-${player.final_year ?? ""}`
            : ""}
          {player.is_active ? " • Active" : ""}
          {player.hof_inducted ? " • Hall of Fame" : ""}
        </div>
      </section>

      <section style={{ marginTop: 12 }}>
        <div className="section-title">Season Summaries</div>
        <DataTable<PlayerSeasonSummary>
          columns={seasonColumns}
          rows={seasons.data}
          getRowKey={(row) => row.seas_id}
        />
      </section>
    </LayoutShell>
  );
}