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
import { runLeaderboards } from "../../../lib/apiClient";
import {
  LeaderboardsRequest,
  LeaderboardsResponseRow,
  PaginatedResponse,
  TableColumn,
} from "../../../lib/types";

/**
 * Leaderboards Tool
 *
 * Minimal filters:
 * - dimension/scope
 * - metric/stat
 * - from_season, to_season (mapped via season_end_year if provided)
 * - is_playoffs
 */

const columns: TableColumn<LeaderboardsResponseRow>[] = [
  { key: "label", label: "Subject" },
  { key: "stat", label: "Value" },
  { key: "season_end_year", label: "Season" },
];

function parseInitialFilters(searchParams: URLSearchParams) {
  const scope = searchParams.get("scope") || "player_season";
  const stat = searchParams.get("stat") || "pts_per_g";
  const season_end_year = searchParams.get("season_end_year") || "";
  const is_playoffs = searchParams.get("is_playoffs") || "";
  const page = Number(searchParams.get("page") || "1") || 1;
  return { scope, stat, season_end_year, is_playoffs, page };
}

function buildRequest(
  filters: ReturnType<typeof parseInitialFilters>,
): LeaderboardsRequest {
  const req: LeaderboardsRequest = {
    scope: filters.scope,
    stat: filters.stat,
    page: filters.page || 1,
    page_size: 50,
  };

  if (filters.season_end_year) {
    const v = Number(filters.season_end_year);
    if (!Number.isNaN(v)) req.season_end_year = v;
  }

  if (filters.is_playoffs === "true") req.is_playoffs = true;
  if (filters.is_playoffs === "false") req.is_playoffs = false;

  return req;
}

export default function LeaderboardsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [filters, setFilters] = useState(() =>
    parseInitialFilters(new URLSearchParams(searchParams?.toString() || "")),
  );
  const [result, setResult] =
    useState<PaginatedResponse<LeaderboardsResponseRow> | null>(null);
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
    if (next.scope) params.set("scope", next.scope);
    if (next.stat) params.set("stat", next.stat);
    if (next.season_end_year) {
      params.set("season_end_year", next.season_end_year);
    }
    if (next.is_playoffs === "true" || next.is_playoffs === "false") {
      params.set("is_playoffs", next.is_playoffs);
    }
    if (next.page > 1) params.set("page", String(next.page));

    const qs = params.toString();
    router.push(qs ? `/tools/leaderboards?${qs}` : "/tools/leaderboards");

    setFilters(next);
    setLoading(true);
    setError(null);

    try {
      const req = buildRequest(next);
      const res = await runLeaderboards(req);
      setResult(res);
    } catch (e: any) {
      setError(e?.message || "Failed to run Leaderboards.");
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  // Auto-run if URL already has filters
  useEffect(() => {
    const hasInitial = !!filters.scope || !!filters.stat;
    if (hasInitial && !result && !loading && !error) {
      void runSearch();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const initialValues: Record<string, any> = {
    scope: filters.scope,
    stat: filters.stat,
    season_end_year: filters.season_end_year,
    is_playoffs: filters.is_playoffs,
  };

  return (
    <div>
      <h1 className="page-title">Leaderboards</h1>
      <p className="muted">
        Rank players or teams by a selected metric. Choose a scope, metric, and
        optional season and playoff flag.
      </p>

      <FiltersPanel
        fields={[
          {
            name: "scope",
            label: "Scope",
            type: "select",
            options: [
              { label: "Player Seasons", value: "player_season" },
              { label: "Team Seasons", value: "team_season" },
            ],
          },
          {
            name: "stat",
            label: "Metric",
            type: "select",
            options: [
              { label: "Points Per Game", value: "pts_per_g" },
              { label: "Rebounds Per Game", value: "trb_per_g" },
              { label: "Assists Per Game", value: "ast_per_g" },
            ],
          },
          {
            name: "season_end_year",
            label: "Season (optional)",
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
            scope: (values as any).scope || "player_season",
            stat: (values as any).stat || "pts_per_g",
            season_end_year: (values as any).season_end_year
              ? String((values as any).season_end_year)
              : "",
            is_playoffs:
              (values as any).is_playoffs === "true" ||
              (values as any).is_playoffs === "false"
                ? String((values as any).is_playoffs)
                : "",
          });
        }}
        submitLabel="Run Leaderboard"
      />

      {loading && <LoadingState message="Loading leaderboards..." />}
      {error && <ErrorState error={error} />}

      {result && (
        <>
          <ToolResultSummary
            pagination={result.pagination}
            filters={result.filters}
          />
          <DataTable<LeaderboardsResponseRow>
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
            getRowKey={(row, idx) => `${row.subject_id}-${idx}`}
          />
        </>
      )}
    </div>
  );
}