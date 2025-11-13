import { fetchSeasons } from "../../lib/apiClient";
import { Season, PaginatedResponse } from "../../lib/types";
import { LayoutShell } from "../../components/LayoutShell";
import { DataTable, FiltersPanel } from "../../components/shared";

interface SeasonsPageProps {
  searchParams?: {
    from_season?: string;
    to_season?: string;
    lg?: string;
    page?: string;
  };
}

/**
 * /seasons index:
 * - GET /api/v1/seasons with from_season, to_season, lg filters.
 */
export default async function SeasonsPage({ searchParams }: SeasonsPageProps) {
  const from_season = searchParams?.from_season
    ? Number(searchParams.from_season)
    : undefined;
  const to_season = searchParams?.to_season
    ? Number(searchParams.to_season)
    : undefined;
  const lg = searchParams?.lg ?? "";
  const page = Number(searchParams?.page ?? "1") || 1;

  const response: PaginatedResponse<Season> = await fetchSeasons({
    from_season,
    to_season,
    lg: lg || undefined,
    page,
    page_size: 50,
  });

  const columns = [
    { key: "season_end_year", label: "Season" },
    { key: "lg", label: "League" },
    { key: "is_lockout", label: "Lockout" },
  ];

  const initialValues: Record<string, any> = {
    from_season: from_season ?? "",
    to_season: to_season ?? "",
    lg,
  };

  return (
    <LayoutShell title="Seasons">
      <FiltersPanel
        fields={[
          {
            name: "from_season",
            label: "From Season",
            type: "number",
            placeholder: "e.g. 1980",
          },
          {
            name: "to_season",
            label: "To Season",
            type: "number",
            placeholder: "e.g. 2024",
          },
          {
            name: "lg",
            label: "League",
            type: "text",
            placeholder: "NBA, ABA...",
          },
        ]}
        initialValues={initialValues}
        onSubmit={(values) => {
          const params = new URLSearchParams(window.location.search);
          const fs = (values as any).from_season;
          const ts = (values as any).to_season;
          const league = (values as any).lg;

          if (fs) params.set("from_season", String(fs));
          else params.delete("from_season");

          if (ts) params.set("to_season", String(ts));
          else params.delete("to_season");

          if (league) params.set("lg", String(league));
          else params.delete("lg");

          params.delete("page");
          window.location.search = params.toString();
        }}
        submitLabel="Filter"
      />

      <DataTable<Season>
        columns={columns}
        rows={response.data}
        pagination={{
          page: response.pagination.page,
          page_size: response.pagination.page_size,
          total: response.pagination.total,
          onPageChange: (nextPage) => {
            const params = new URLSearchParams(window.location.search);
            if (nextPage > 1) params.set("page", String(nextPage));
            else params.delete("page");
            window.location.search = params.toString();
          },
        }}
        getRowKey={(row) => row.season_id}
      />
    </LayoutShell>
  );
}