import { LayoutShell } from "../../components/LayoutShell";
import {
  DataTable,
  FiltersPanel,
} from "../../components/shared";
import {
  fetchGames,
} from "../../lib/apiClient";
import {
  Game,
  PaginatedResponse,
  TableColumn,
} from "../../lib/types";

/**
 * Games index page.
 *
 * Server component:
 * - GET /api/v1/games with filters:
 *   season, from_date, to_date, is_playoffs, team_id, page
 */
interface GamesPageProps {
  searchParams?: {
    season?: string;
    from_date?: string;
    to_date?: string;
    is_playoffs?: string;
    team_id?: string;
    page?: string;
  };
}

const columns: TableColumn<Game & { opponent_team_id?: number | null }>[] = [
  { key: "game_date_est", label: "Date" },
  { key: "season_end_year", label: "Season" },
  { key: "home_team_id", label: "Home Team ID" },
  { key: "away_team_id", label: "Away Team ID" },
  { key: "home_pts", label: "Home PTS" },
  { key: "away_pts", label: "Away PTS" },
  { key: "is_playoffs", label: "PO" },
];

export default async function GamesPage({ searchParams }: GamesPageProps) {
  const season = searchParams?.season
    ? Number(searchParams.season)
    : undefined;
  const from_date = searchParams?.from_date || "";
  const to_date = searchParams?.to_date || "";
  const is_playoffs =
    searchParams?.is_playoffs === "true"
      ? true
      : searchParams?.is_playoffs === "false"
      ? false
      : undefined;
  const team_id = searchParams?.team_id
    ? Number(searchParams.team_id)
    : undefined;
  const page = Number(searchParams?.page ?? "1") || 1;

  const response: PaginatedResponse<Game> = await fetchGames({
    season,
    from_date: from_date || undefined,
    to_date: to_date || undefined,
    is_playoffs,
    team_id,
    page,
    page_size: 50,
  });

  const initialValues: Record<string, any> = {
    season: season ?? "",
    from_date,
    to_date,
    is_playoffs:
      searchParams?.is_playoffs === "true"
        ? "true"
        : searchParams?.is_playoffs === "false"
        ? "false"
        : "",
    team_id: team_id ?? "",
  };

  return (
    <LayoutShell title="Games">
      <FiltersPanel
        fields={[
          {
            name: "season",
            label: "Season",
            type: "number",
            placeholder: "e.g. 2024",
          },
          {
            name: "from_date",
            label: "From Date",
            type: "text",
            placeholder: "YYYY-MM-DD",
          },
          {
            name: "to_date",
            label: "To Date",
            type: "text",
            placeholder: "YYYY-MM-DD",
          },
          {
            name: "is_playoffs",
            label: "Playoffs?",
            type: "select",
            options: [
              { label: "Any", value: "" },
              { label: "Regular season only", value: "false" },
              { label: "Playoffs only", value: "true" },
            ],
          },
          {
            name: "team_id",
            label: "Team ID",
            type: "number",
            placeholder: "Filter by team",
          },
        ]}
        initialValues={initialValues}
        onSubmit={(values) => {
          const params = new URLSearchParams(
            typeof window !== "undefined"
              ? window.location.search
              : "",
          );

          const s = (values as any).season;
          const fd = (values as any).from_date;
          const td = (values as any).to_date;
          const po = (values as any).is_playoffs;
          const tid = (values as any).team_id;

          if (s) params.set("season", String(s));
          else params.delete("season");

          if (fd) params.set("from_date", String(fd));
          else params.delete("from_date");

          if (td) params.set("to_date", String(td));
          else params.delete("to_date");

          if (po === "true" || po === "false") {
            params.set("is_playoffs", po);
          } else {
            params.delete("is_playoffs");
          }

          if (tid) params.set("team_id", String(tid));
          else params.delete("team_id");

          params.delete("page");

          if (typeof window !== "undefined") {
            window.location.search = params.toString();
          }
        }}
        submitLabel="Filter"
      />

      <DataTable<Game>
        columns={[
          {
            key: "game_date_est",
            label: "Date",
            sortable: true,
          },
          {
            key: "season_end_year",
            label: "Season",
            sortable: true,
          },
          {
            key: "home_team_id",
            label: "Home",
            sortable: true,
          },
          {
            key: "away_team_id",
            label: "Away",
            sortable: true,
          },
          {
            key: "home_pts",
            label: "H PTS",
            sortable: true,
          },
          {
            key: "away_pts",
            label: "A PTS",
            sortable: true,
          },
          {
            key: "is_playoffs",
            label: "PO",
          },
        ]}
        rows={response.data}
        pagination={{
          page: response.pagination.page,
          page_size: response.pagination.page_size,
          total: response.pagination.total,
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
        getRowKey={(row) => row.game_id}
      />
    </LayoutShell>
  );
}