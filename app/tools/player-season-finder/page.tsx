"use client";

import { useState, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  DataTable,
  FiltersPanel,
  ToolResultSummary,
  LoadingState,
  ErrorState,
} from "../../../components/shared";
import {
  toolsPlayerSeasonFinder,
  type PlayerSeasonFinderRequest,
  type PlayerSeasonFinderResponseRow,
  type PaginatedResponse,
} from "../../../lib/apiClient";
import type { TableColumn } from "../../../lib/types";

/**
 * Player Season Finder
 *
 * Client-driven tool page:
 * - Reads initial filters from searchParams
 * - Uses FiltersPanel for input
 * - Calls POST /api/v1/tools/player-season-finder via runPlayerSeasonFinder
 * - Renders ToolResultSummary + DataTable
 */

const columns: TableColumn<PlayerSeasonFinderResponseRow>[] = [
  { key: "player_id", label: "Player ID" },
  { key: "season_end_year", label: "Season" },
  { key: "team_id", label: "Team ID" },
  { key: "g", label: "G" },
  { key: "pts_per_g", label: "PTS/G" },
];

function parseInitialFilters(searchParams: URLSearchParams): {
  player_ids: string;
  from_season: string;
  to_season: string;
  is_playoffs: string;
  page: number;
} {
  const player_ids = searchParams.get("player_ids") || "";
  const from_season = searchParams.get("from_season") || "";
  const to_season = searchParams.get("to_season") || "";
  const is_playoffs = searchParams.get("is_playoffs") || "";
  const page = Number(searchParams.get("page") || "1") || 1;

  return {
    player_ids,
    from_season,
    to_season,
    is_playoffs,
    page,
  };
}

function buildRequest(
  filters: ReturnType<typeof parseInitialFilters>,
): PlayerSeasonFinderRequest {
  const req: PlayerSeasonFinderRequest = {};

  if (filters.player_ids) {
    const ids = filters.player_ids
      .split(",")
      .map((v) => v.trim())
      .filter(Boolean)
      .map((v) => Number(v))
      .filter((n) => !Number.isNaN(n));
    if (ids.length > 0) req.player_ids = ids;
  }

  if (filters.from_season) {
    const v = Number(filters.from_season);
    if (!Number.isNaN(v)) req.from_season = v;
  }

  if (filters.to_season) {
    const v = Number(filters.to_season);
    if (!Number.isNaN(v)) req.to_season = v;
  }

  if (filters.is_playoffs === "true") req.is_playoffs = true;
  if (filters.is_playoffs === "false") req.is_playoffs = false;

  req.page = filters.page || 1;
  req.page_size = 50;

  return req;
}

export default function PlayerSeasonFinderPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [filters, setFilters] = useState(() =>
    parseInitialFilters(new URLSearchParams(searchParams?.toString() || "")),
  );
  const [result, setResult] = useState<
    PaginatedResponse<PlayerSeasonFinderResponseRow> | null
  >(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Sync local filters when URL changes (e.g. back/forward navigation)
  useEffect(() => {
    const next = parseInitialFilters(
      new URLSearchParams(searchParams?.toString() || ""),
    );
    setFilters(next);
  }, [searchParams]);

  const runSearch = async (override: Partial<typeof filters> = {}) => {
    const nextFilters = { ...filters, ...override, page: override.page ?? 1 };

    // Push filters to URL for bookmarkability
    const params = new URLSearchParams();
    if (nextFilters.player_ids) {
      params.set("player_ids", nextFilters.player_ids);
    }
    if (nextFilters.from_season) {
      params.set("from_season", nextFilters.from_season);
    }
    if (nextFilters.to_season) {
      params.set("to_season", nextFilters.to_season);
    }
    if (nextFilters.is_playoffs === "true" || nextFilters.is_playoffs === "false") {
      params.set("is_playoffs", nextFilters.is_playoffs);
    }
    if (nextFilters.page && nextFilters.page > 1) {
      params.set("page", String(nextFilters.page));
    }

    const qs = params.toString();
    router.push(qs ? `/tools/player-season-finder?${qs}` : "/tools/player-season-finder");

    setFilters(nextFilters);
    setLoading(true);
    setError(null);

    try {
      const req = buildRequest(nextFilters);
      const res = await toolsPlayerSeasonFinder(req);
      setResult(res);
    } catch (e: any) {
      setError(e?.message || "Failed to run Player Season Finder.");
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  // Auto-run on initial load if any filter is present
  useEffect(() => {
    const hasInitialFilters =
      !!filters.player_ids ||
      !!filters.from_season ||
      !!filters.to_season ||
      !!filters.is_playoffs;
    if (hasInitialFilters && !result && !loading && !error) {
      void runSearch();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const initialValues: Record<string, any> = {
    player_ids: filters.player_ids,
    from_season: filters.from_season,
    to_season: filters.to_season,
    is_playoffs: filters.is_playoffs,
  };

  return (
    <div>
      <h1 className="page-title">Player Season Finder</h1>
      <p className="muted">
        Query player-season lines by IDs, season range, and playoff flag.
        Enter a comma-separated list of player IDs or leave blank to search all.
      </p>

      <FiltersPanel
        fields={[
          {
            name: "player_ids",
            label: "Player IDs",
            type: "text",
            placeholder: "e.g. 201939, 2544",
          },
          {
            name: "from_season",
            label: "From Season",
            type: "number",
            placeholder: "e.g. 2010",
          },
          {
            name: "to_season",
            label: "To Season",
            type: "number",
            placeholder: "e.g. 2024",
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
        ]}
        initialValues={initialValues}
        onSubmit={(values) => {
          runSearch({
            player_ids: (values as any).player_ids || "",
            from_season: (values as any).from_season
              ? String((values as any).from_season)
              : "",
            to_season: (values as any).to_season
              ? String((values as any).to_season)
              : "",
            is_playoffs:
              (values as any).is_playoffs === "true" ||
                (values as any).is_playoffs === "false"
                ? String((values as any).is_playoffs)
                : "",
          });
        }}
        submitLabel="Run Search"
      />

      {loading && <LoadingState message="Running Player Season Finder..." />}
      {error && <ErrorState error={error} />}

      {result && (
        <>
          <ToolResultSummary
            pagination={result.pagination}
            filters={result.filters}
          />
          <DataTable<PlayerSeasonFinderResponseRow>
            columns={columns}
            rows={result.data}
            pagination={
              result.pagination
                ? {
                  page: result.pagination.page,
                  page_size: result.pagination.page_size,
                  total: result.pagination.total,
                  onPageChange: (nextPage) => {
                    runSearch({ page: nextPage });
                  },
                }
                : undefined
            }
            getRowKey={(row) => row.seas_id}
          />
        </>
      )}
    </div>
  );
}