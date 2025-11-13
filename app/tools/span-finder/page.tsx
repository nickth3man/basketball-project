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
  toolsSpanFinder,
  type SpanFinderRequest,
  type SpanFinderResponseRow,
  type PaginatedResponse,
} from "../../../lib/apiClient";
import type { TableColumn } from "../../../lib/types";

/**
 * Span Finder
 *
 * Minimal filters:
 * - subject_type: player or team (via which ID is set)
 * - subject_id
 * - span_length
 * - metric
 */

const columns: TableColumn<SpanFinderResponseRow>[] = [
  { key: "subject_id", label: "Subject ID" },
  { key: "span_length", label: "Span Length" },
  { key: "stat", label: "Metric" },
  { key: "value", label: "Value" },
  { key: "start_game_id", label: "Start Game" },
  { key: "end_game_id", label: "End Game" },
];

function parseInitialFilters(searchParams: URLSearchParams) {
  const subject_type = searchParams.get("subject_type") || "player";
  const subject_id = searchParams.get("subject_id") || "";
  const span_length = searchParams.get("span_length") || "";
  const metric = searchParams.get("metric") || "pts";
  const page = Number(searchParams.get("page") || "1") || 1;
  return { subject_type, subject_id, span_length, metric, page };
}

function buildRequest(
  filters: ReturnType<typeof parseInitialFilters>,
): SpanFinderRequest {
  const req: SpanFinderRequest = {
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

  const sl = Number(filters.span_length);
  if (!Number.isNaN(sl) && sl > 0) {
    req.span_length = sl;
  }

  // metric is not part of SpanFinderRequest schema; omit for now.

  return req;
}

export default function SpanFinderPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [filters, setFilters] = useState(() =>
    parseInitialFilters(new URLSearchParams(searchParams?.toString() || "")),
  );
  const [result, setResult] =
    useState<PaginatedResponse<SpanFinderResponseRow> | null>(null);
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
    if (next.span_length) params.set("span_length", next.span_length);
    if (next.metric) params.set("metric", next.metric);
    if (next.page > 1) params.set("page", String(next.page));

    const qs = params.toString();
    router.push(qs ? `/tools/span-finder?${qs}` : "/tools/span-finder");

    if (!next.subject_id || !next.span_length) {
      setError("subject_id and span_length are required.");
      setResult(null);
      return;
    }

    setFilters(next);
    setLoading(true);
    setError(null);

    try {
      const req = buildRequest(next);
      const res = await toolsSpanFinder(req);
      setResult(res);
    } catch (e: any) {
      setError(e?.message || "Failed to run Span Finder.");
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  // Auto-run when URL has required filters
  useEffect(() => {
    if (
      filters.subject_id &&
      filters.span_length &&
      !result &&
      !loading &&
      !error
    ) {
      void runSearch();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const initialValues: Record<string, any> = {
    subject_type: filters.subject_type,
    subject_id: filters.subject_id,
    span_length: filters.span_length,
    metric: filters.metric,
  };

  return (
    <div>
      <h1 className="page-title">Span Finder</h1>
      <p className="muted">
        Find the best spans of consecutive games for a player or team over a
        specified length and metric.
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
            name: "span_length",
            label: "Span Length",
            type: "number",
            placeholder: "Required. Number of games in span.",
          },
          {
            name: "metric",
            label: "Metric",
            type: "text",
            placeholder: "e.g. pts",
          },
        ]}
        initialValues={initialValues}
        onSubmit={(values) => {
          void runSearch({
            subject_type: (values as any).subject_type || "player",
            subject_id: (values as any).subject_id
              ? String((values as any).subject_id)
              : "",
            span_length: (values as any).span_length
              ? String((values as any).span_length)
              : "",
            metric: (values as any).metric || "pts",
          });
        }}
        submitLabel="Run Span Search"
      />

      {loading && <LoadingState message="Running Span Finder..." />}
      {error && <ErrorState error={error} />}

      {result && (
        <>
          <ToolResultSummary
            pagination={result.pagination}
            filters={result.filters}
          />
          <DataTable<SpanFinderResponseRow>
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