import { fetchPlayers } from "../../lib/apiClient";
import { Player, PaginatedResponse } from "../../lib/types";
import { LayoutShell } from "../../components/LayoutShell";
import {
  EntitySearchBar,
  DataTable,
  FiltersPanel,
} from "../../components/shared";

/**
 * /players index page (server component).
 * Reads searchParams, fetches players from /api/v1/players
 * and renders FiltersPanel + DataTable via client components.
 */
interface PlayersPageProps {
  searchParams?: {
    q?: string;
    is_active?: string;
    hof?: string;
    page?: string;
  };
}

export default async function PlayersPage({ searchParams }: PlayersPageProps) {
  const q = searchParams?.q ?? "";
  const is_active = searchParams?.is_active ?? "";
  const hof = searchParams?.hof ?? "";
  const page = Number(searchParams?.page ?? "1") || 1;

  const response: PaginatedResponse<Player> = await fetchPlayers({
    q: q || undefined,
    is_active: is_active || undefined,
    hof: hof || undefined,
    page,
    page_size: 50,
  });

  const columns = [
    { key: "player_id", label: "ID" },
    { key: "full_name", label: "Player" },
    { key: "is_active", label: "Active" },
    { key: "hof_inducted", label: "HOF" },
    { key: "rookie_year", label: "From" },
    { key: "final_year", label: "To" },
  ];

  const initialFilters = {
    q,
    is_active,
    hof,
  };

  return (
    <LayoutShell title="Players">
      <EntitySearchBar
        placeholder="Search players by name or slug"
        initialQuery={q}
        onSearch={(value) => {
          const params = new URLSearchParams(window.location.search);
          if (value) {
            params.set("q", value);
          } else {
            params.delete("q");
          }
          params.delete("page");
          window.location.search = params.toString();
        }}
      />

      <FiltersPanel
        fields={[
          {
            name: "is_active",
            label: "Active only",
            type: "select",
            options: [
              { label: "Any", value: "" },
              { label: "Yes", value: "true" },
              { label: "No", value: "false" },
            ],
          },
          {
            name: "hof",
            label: "Hall of Fame",
            type: "select",
            options: [
              { label: "Any", value: "" },
              { label: "Yes", value: "true" },
              { label: "No", value: "false" },
            ],
          },
        ]}
        initialValues={initialFilters}
        onSubmit={(values) => {
          const params = new URLSearchParams(window.location.search);
          ["is_active", "hof"].forEach((key) => {
            const v = (values as any)[key];
            if (v === "" || v == null) {
              params.delete(key);
            } else {
              params.set(key, String(v));
            }
          });
          params.delete("page");
          window.location.search = params.toString();
        }}
        submitLabel="Filter"
      />

      <DataTable<Player>
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
        getRowKey={(row) => row.player_id}
      />
    </LayoutShell>
  );
}