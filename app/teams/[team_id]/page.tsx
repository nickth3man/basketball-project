import { LayoutShell } from "../../../components/LayoutShell";
import { DataTable } from "../../../components/shared";
import {
  fetchTeam,
  fetchTeamSeasons,
} from "../../../lib/apiClient";
import {
  Team,
  TeamSeasonSummary,
  PaginatedResponse,
  TableColumn,
} from "../../../lib/types";

/**
 * Team detail page.
 *
 * Server component:
 * - GET /api/v1/teams/{team_id}
 * - GET /api/v1/teams/{team_id}/seasons
 */
interface TeamPageProps {
  params: { team_id: string };
  searchParams?: {
    page?: string;
  };
}

const seasonColumns: TableColumn<TeamSeasonSummary>[] = [
  { key: "season_end_year", label: "Season" },
  { key: "g", label: "G" },
  { key: "pts", label: "PTS" },
  { key: "opp_pts", label: "OPP PTS" },
  { key: "is_playoffs", label: "PO" },
];

export default async function TeamPage({
  params,
  searchParams,
}: TeamPageProps) {
  const teamId = Number(params.team_id);
  const page = Number(searchParams?.page ?? "1") || 1;

  const team: Team = await fetchTeam(teamId);
  const seasons: PaginatedResponse<TeamSeasonSummary> =
    await fetchTeamSeasons(teamId, {
      page,
      page_size: 100,
    });

  const title =
    (team.team_city || "") && (team.team_name || "")
      ? `${team.team_city} ${team.team_name} (${team.team_abbrev ?? team.team_id})`
      : team.team_name
      ? `${team.team_name} (${team.team_abbrev ?? team.team_id})`
      : `Team ${team.team_id}`;

  const activeLabel =
    team.is_active === true
      ? "Active franchise"
      : team.is_active === false
      ? "Inactive / historical franchise"
      : "";

  return (
    <LayoutShell title={title}>
      <section>
        <div className="section-title">Franchise Summary</div>
        <div className="subtle">
          ID {team.team_id}
          {team.team_abbrev ? ` • ${team.team_abbrev}` : ""}
          {team.team_city ? ` • ${team.team_city}` : ""}
          {team.start_season
            ? ` • From ${team.start_season}`
            : ""}
          {team.end_season
            ? ` • To ${team.end_season}`
            : ""}
          {activeLabel ? ` • ${activeLabel}` : ""}
        </div>
      </section>

      <section style={{ marginTop: 12 }}>
        <div className="section-title">Season Summaries</div>
        <DataTable<TeamSeasonSummary>
          columns={seasonColumns}
          rows={seasons.data}
          pagination={{
            page: seasons.pagination.page,
            page_size: seasons.pagination.page_size,
            total: seasons.pagination.total,
            onPageChange: (nextPage) => {
              const params = new URLSearchParams(
                typeof window !== "undefined"
                  ? window.location.search
                  : "",
              );
              if (nextPage > 1) {
                params.set("page", String(nextPage));
              } else {
                params.delete("page");
              }
              if (typeof window !== "undefined") {
                window.location.search = params.toString();
              }
            },
          }}
          getRowKey={(row) => row.team_season_id}
        />
      </section>
    </LayoutShell>
  );
}