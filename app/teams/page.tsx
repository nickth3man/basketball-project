import { fetchTeams } from "../../lib/apiClient";
import { Team, PaginatedResponse } from "../../lib/types";
import { LayoutShell } from "../../components/LayoutShell";
import {
  EntitySearchBar,
  DataTable,
  FiltersPanel,
} from "../../components/shared";

interface TeamsPageProps {
  searchParams?: {
    q?: string;
    is_active?: string;
    page?: string;
  };
}

/**
 * /teams index:
 * - GET /api/v1/teams with q, is_active, page filters.
 */
export default async function TeamsPage({ searchParams }: TeamsPageProps) {
  const q = searchParams?.q ?? "";
  const is_active = searchParams?.is_active ?? "";
  const page = Number(searchParams?.page ?? "1") || 1;

  const response: PaginatedResponse<Team> = await fetchTeams({
    q: q || undefined,
    is_active: is_active ? is_active === "true" : undefined,
    page,
    page_size: 50,
  });

  const columns = [
    { key: "team_id", label: "ID" },
    { key: "team_abbrev", label: "Abbrev" },
    { key: "team_name", label: "Team" },
    { key: "team_city", label: "City" },
    { key: "is_active", label: "Active" },
    { key: "start_season", label: "From" },
    { key: "end_season", label: "To" },
  ];

  const initialFilters = { q, is_active };

  return (
    <LayoutShell title="Teams">
      <EntitySearchBar
        placeholder="Search teams by name/city/abbrev"
        initialQuery={q}
        onSearch={(value) => {
          const params = new URLSearchParams(window.location.search);
          if (value) params.set("q", value);
          else params.delete("q");
          params.delete("page");
          window.location.search = params.toString();
        }}
      />

      <FiltersPanel
        fields={[
          {
            name: "is_active",
            label: "Active franchises",
            type: "select",
            options: [
              { label: "Any", value: "" },
              { label: "Active only", value: "true" },
            ],
          },
        ]}
        initialValues={initialFilters}
        onSubmit={(values) => {
          const params = new URLSearchParams(window.location.search);
          const v = (values as any).is_active;
          if (!v) params.delete("is_active");
          else params.set("is_active", String(v));
          params.delete("page");
          window.location.search = params.toString();
        }}
        submitLabel="Filter"
      />

      <DataTable<Team>
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
        getRowKey={(row) => row.team_id}
      />
    </LayoutShell>
  );
}