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
import { runTeamGameFinder } from "../../../lib/apiClient";
import {
  TeamGameFinderRequest,
  TeamGameFinderResponseRow,
  PaginatedResponse,
  TableColumn,
} from "../../../lib/types";

/**
 * Team Game Finder
 *
 * Minimal filters:
 * - team_ids (comma-separated)
 * - from_season, to_season
 * Uses:
 * - POST /api/v1/tools/team-game-finder via runTeamGameFinder
 */

const columns: TableColumn<TeamGameFinderResponseRow>[] = [
  { key: "game_id", label: "Game ID" },
  { key: "team_id", label: "Team ID" },
  { key: "is_home", label: "Home?" },
  { key: "pts", label: "PTS" },
  { key: "opp_pts", label: "OPP PTS" },
];

function parseInitialFilters(searchParams: URLSearchParams) {
  const team_ids = searchParams.get("team_ids") || "";
  const from_season = searchParams.get("from_season") || "";
  const to_season = searchParams.get("to_season") || "";
  const page = Number(searchParams.get("page") || "1") || 1;
  return { team_ids, from_season, to_season, page };
}

function buildRequest(
  filters: ReturnType<typeof parseInitialFilters>,
): TeamGameFinderRequest {
  const req: TeamGameFinderRequest = {};

  if (filters.team_ids) {
    const ids = filters.team_ids
      .split(",")
      .map((v) => v.trim())
      .filter(Boolean)
      .map((v) => Number(v))
      .filter((n) => !Number.isNaN(n));
    if (ids.length > 0) req.team_ids = ids;
  }

  if (filters.from_season) {
    const v = Number(filters.from_season);
    if (!Number.isNaN(v)) req.from_season = v;
  }

  if (filters.to_season) {
    const v = Number(filters.to_season);
    if (!Number.isNaN(v)) req.to_season = v;
  }

  req.page = filters.page || 1;
  req.page_size = 50;

  return req;
}

export default function TeamGameFinderPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [filters, setFilters] = useState(() =>
    parseInitialFilters(new URLSearchParams(searchParams?.toString() || "")),
  );
  const [result, setResult] = useState<
    PaginatedResponse<TeamGameFinderResponseRow> | null
  >(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const next = parseInitialFilters(
      new URLSearchParams(searchParams?.toString() || ""),
    );
    setFilters(next);
  }, [searchParams]);

  const runSearch = async (
    override: Partial<ReturnType<typeof parseInitialFilters>> = {},
  ) => {
    const next = {
      ...filters,
      ...override,
      page: override.page ?? 1,
    };

    const params = new URLSearchParams();
    if (next.team_ids) params.set("team_ids", next.team_ids);
    if (next.from_season) params.set("from_season", next.from_season);
    if (next.to_season) params.set("to_season", next.to_season);
    if (next.page > 1) params.set("page", String(next.page));

    const qs = params.toString();
    router.push(
      qs ? `/tools/team-game-finder?${qs}` : "/tools/team-game-finder",
    );

    setFilters(next);
    setLoading(true);
    setError(null);

    try {
      const req = buildRequest(next);
      const res = await runTeamGameFinder(req);
      setResult(res);
    } catch (e: any) {
      setError(e?.message || "Failed to run Team Game Finder.");
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  // Auto-run when URL has filters
  useEffect(() => {
    const hasInitial =
      !!filters.team_ids || !!filters.from_season || !!filters.to_season;
    if (hasInitial && !result && !loading && !error) {
      void runSearch();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const initialValues: Record<string, any> = {
    team_ids: filters.team_ids,
    from_season: filters.from_season,
    to_season: filters.to_season,
  };

  return (
    <div>
      <h1 className="page-title">Team Game Finder</h1>
      <p className="muted">
        Find games for one or more teams across a season range. IDs can be
        obtained from the Teams index.
      </p>

      <FiltersPanel
        fields={[
          {
            name: "team_ids",
            label: "Team IDs",
            type: "text",
            placeholder: "e.g. 1610612744, 1610612747",
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
        ]}
        initialValues={initialValues}
        onSubmit={(values) => {
          void runSearch({
            team_ids: (values as any).team_ids || "",
            from_season: (values as any).from_season
              ? String((values as any).from_season)
              : "",
            to_season: (values as any).to_season
              ? String((values as any).to_season)
              : "",
          });
        }}
        submitLabel="Run Search"
      />

      {loading && <LoadingState message="Running Team Game Finder..." />}
      {error && <ErrorState error={error} />}

      {result && (
        <>
          <ToolResultSummary
            pagination={result.pagination}
            filters={result.filters}
          />
          <DataTable<TeamGameFinderResponseRow>
            columns={columns}
            rows={result.data}
            pagination={
              result.pagination
                ? {
                    page: result.pagination.page,
                    page_size: result.pagination.page_size,
                    total: result.pagination.total,
                    onPageChange: (nextPage) => {
                      void runSearch({ page: nextPage });
                    },
                  }
                : undefined
            }
            getRowKey={(row, idx) => `${row.game_id}-${row.team_id}-${idx}`}
          />
        </>
      )}
    </div>
  );
}