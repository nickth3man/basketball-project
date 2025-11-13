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
  toolsTeamSeasonFinder,
  type TeamSeasonFinderRequest,
  type TeamSeasonFinderResponseRow,
  type PaginatedResponse,
} from "../../../lib/apiClient";
import type { TableColumn } from "../../../lib/types";

/**
 * Team Season Finder
 *
 * Minimal filters:
 * - team_ids (comma-separated)
 * - from_season, to_season
 * - is_playoffs
 * Uses:
 * - POST /api/v1/tools/team-season-finder via runTeamSeasonFinder
 */

const columns: TableColumn<TeamSeasonFinderResponseRow>[] = [
  { key: "team_id", label: "Team ID" },
  { key: "season_end_year", label: "Season" },
  { key: "g", label: "G" },
  { key: "pts", label: "PTS" },
];

function parseInitialFilters(searchParams: URLSearchParams) {
  const team_ids = searchParams.get("team_ids") || "";
  const from_season = searchParams.get("from_season") || "";
  const to_season = searchParams.get("to_season") || "";
  const is_playoffs = searchParams.get("is_playoffs") || "";
  const page = Number(searchParams.get("page") || "1") || 1;
  return { team_ids, from_season, to_season, is_playoffs, page };
}

function buildRequest(
  filters: ReturnType<typeof parseInitialFilters>,
): TeamSeasonFinderRequest {
  const req: TeamSeasonFinderRequest = {};

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

  if (filters.is_playoffs === "true") req.is_playoffs = true;
  if (filters.is_playoffs === "false") req.is_playoffs = false;

  req.page = filters.page || 1;
  req.page_size = 50;

  return req;
}

export default function TeamSeasonFinderPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [filters, setFilters] = useState(() =>
    parseInitialFilters(new URLSearchParams(searchParams?.toString() || "")),
  );
  const [result, setResult] = useState<
    PaginatedResponse<TeamSeasonFinderResponseRow> | null
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
    if (next.is_playoffs === "true" || next.is_playoffs === "false") {
      params.set("is_playoffs", next.is_playoffs);
    }
    if (next.page > 1) params.set("page", String(next.page));

    const qs = params.toString();
    router.push(
      qs ? `/tools/team-season-finder?${qs}` : "/tools/team-season-finder",
    );

    setFilters(next);
    setLoading(true);
    setError(null);

    try {
      const req = buildRequest(next);
      const res = await toolsTeamSeasonFinder(req);
      setResult(res);
    } catch (e: any) {
      setError(e?.message || "Failed to run Team Season Finder.");
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  // Auto-run when filters exist in URL
  useEffect(() => {
    const hasInitial =
      !!filters.team_ids ||
      !!filters.from_season ||
      !!filters.to_season ||
      !!filters.is_playoffs;
    if (hasInitial && !result && !loading && !error) {
      void runSearch();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const initialValues: Record<string, any> = {
    team_ids: filters.team_ids,
    from_season: filters.from_season,
    to_season: filters.to_season,
    is_playoffs: filters.is_playoffs,
  };

  return (
    <div>
      <h1 className="page-title">Team Season Finder</h1>
      <p className="muted">
        Filter team seasons by team IDs, year range, and playoff flag.
        IDs can be discovered via the Teams index.
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
          void runSearch({
            team_ids: (values as any).team_ids || "",
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

      {loading && <LoadingState message="Running Team Season Finder..." />}
      {error && <ErrorState error={error} />}

      {result && (
        <>
          <ToolResultSummary
            pagination={result.pagination}
            filters={result.filters}
          />
          <DataTable<TeamSeasonFinderResponseRow>
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
            getRowKey={(row, idx) =>
              `${row.team_season_id}-${row.team_id}-${idx}`
            }
          />
        </>
      )}
    </div>
  );
}