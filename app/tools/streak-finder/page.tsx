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
  toolsStreakFinder,
  type StreakFinderRequest,
  type StreakFinderResponseRow,
  type PaginatedResponse,
} from "../../../lib/apiClient";
import type { TableColumn } from "../../../lib/types";

/**
 * Streak Finder
 *
 * Minimal filters:
 * - subject_type: player or team (inferred from which id is set)
 * - subject_id: player_id or team_id
 * - metric: free-text metric key understood by backend
 * - threshold, min_games
 */

const columns: TableColumn<StreakFinderResponseRow>[] = [
  { key: "subject_id", label: "Subject ID" },
  { key: "length", label: "Length" },
  { key: "stat", label: "Metric" },
  { key: "value", label: "Value" },
  { key: "start_game_id", label: "Start Game" },
  { key: "end_game_id", label: "End Game" },
];

function parseInitialFilters(searchParams: URLSearchParams) {
  const subject_type = searchParams.get("subject_type") || "player";
  const subject_id = searchParams.get("subject_id") || "";
  const metric = searchParams.get("metric") || "pts";
  const threshold = searchParams.get("threshold") || "";
  const min_games = searchParams.get("min_games") || "";
  const page = Number(searchParams.get("page") || "1") || 1;
  return { subject_type, subject_id, metric, threshold, min_games, page };
}

function buildRequest(
  filters: ReturnType<typeof parseInitialFilters>,
): StreakFinderRequest {
  const req: StreakFinderRequest = {
    page: filters.page || 1,
    page_size: 50,
  };

  const sid = Number(filters.subject_id);
  if (!Number.isNaN(sid) && sid > 0) {
    if (filters.subject_type === "team") {
      req.team_id = sid;
      delete req.player_id;
    } else {
      req.player_id = sid;
      delete req.team_id;
    }
  }

  // Backend may interpret metric/threshold/min_games via its own schema;
  // we pass through as part of query if supported fields exist.
  const th = Number(filters.threshold);
  if (!Number.isNaN(th)) {
    // @ts-expect-error: backend may support threshold field
    req.threshold = th;
  }

  const mg = Number(filters.min_games);
  if (!Number.isNaN(mg)) {
    req.min_length = mg;
  }

  // @ts-expect-error: backend may support metric field
  if (filters.metric) req.metric = filters.metric;

  return req;
}

export default function StreakFinderPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [filters, setFilters] = useState(() =>
    parseInitialFilters(new URLSearchParams(searchParams?.toString() || "")),
  );
  const [result, setResult] =
    useState<PaginatedResponse<StreakFinderResponseRow> | null>(null);
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
    if (next.subject_type) params.set("subject_type", next.subject_type);
    if (next.subject_id) params.set("subject_id", next.subject_id);
    if (next.metric) params.set("metric", next.metric);
    if (next.threshold) params.set("threshold", next.threshold);
    if (next.min_games) params.set("min_games", next.min_games);
    if (next.page > 1) params.set("page", String(next.page));

    const qs = params.toString();
    router.push(qs ? `/tools/streak-finder?${qs}` : "/tools/streak-finder");

    if (!next.subject_id) {
      setError("subject_id is required.");
      setResult(null);
      return;
    }

    setFilters(next);
    setLoading(true);
    setError(null);

    try {
      const req = buildRequest(next);
      const res = await toolsStreakFinder(req);
      setResult(res);
    } catch (e: any) {
      setError(e?.message || "Failed to run Streak Finder.");
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  // Auto-run when URL has required filters
  useEffect(() => {
    if (filters.subject_id && !result && !loading && !error) {
      void runSearch();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const initialValues: Record<string, any> = {
    subject_type: filters.subject_type,
    subject_id: filters.subject_id,
    metric: filters.metric,
    threshold: filters.threshold,
    min_games: filters.min_games,
  };

  return (
    <div>
      <h1 className="page-title">Streak Finder</h1>
      <p className="muted">
        Find streaks for a player or team that meet minimum metric and length
        criteria (for example, consecutive games with at least N points).
      </p>

      <FiltersPanel
        fields={[
          {
            name: "subject_type",
            label: "Subject Type",
            type: "select",
            options: [
              { label: "Player", value: "player" },
              { label: "Team", value: "team" },
            ],
          },
          {
            name: "subject_id",
            label: "Subject ID",
            type: "number",
            placeholder: "Required. Player or Team ID.",
          },
          {
            name: "metric",
            label: "Metric",
            type: "text",
            placeholder: "e.g. pts",
          },
          {
            name: "threshold",
            label: "Threshold",
            type: "number",
            placeholder: "e.g. 30",
          },
          {
            name: "min_games",
            label: "Min Games",
            type: "number",
            placeholder: "e.g. 5",
          },
        ]}
        initialValues={initialValues}
        onSubmit={(values) => {
          void runSearch({
            subject_type: (values as any).subject_type || "player",
            subject_id: (values as any).subject_id
              ? String((values as any).subject_id)
              : "",
            metric: (values as any).metric || "pts",
            threshold: (values as any).threshold
              ? String((values as any).threshold)
              : "",
            min_games: (values as any).min_games
              ? String((values as any).min_games)
              : "",
          });
        }}
        submitLabel="Run Streak Search"
      />

      {loading && <LoadingState message="Running Streak Finder..." />}
      {error && <ErrorState error={error} />}

      {result && (
        <>
          <ToolResultSummary
            pagination={result.pagination}
            filters={result.filters}
          />
          <DataTable<StreakFinderResponseRow>
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
              `${row.subject_id}-${row.start_game_id}-${row.end_game_id}-${idx}`
            }
          />
        </>
      )}
    </div>
  );
}