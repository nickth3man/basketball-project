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
import { runSplits } from "../../../lib/apiClient";
import {
  SplitsRequest,
  SplitsResponseRow,
  PaginatedResponse,
  TableColumn,
} from "../../../lib/types";

/**
 * Splits Tool
 *
 * Minimal filters:
 * - subject_type: player | team
 * - subject_id
 * - split_type: home_away | versus_opponent
 */

const columns: TableColumn<SplitsResponseRow>[] = [
  { key: "split_key", label: "Split" },
  { key: "g", label: "G" },
  { key: "pts_per_g", label: "PTS/G" },
];

function parseInitialFilters(searchParams: URLSearchParams) {
  const subject_type =
    (searchParams.get("subject_type") as "player" | "team") || "player";
  const subject_id = searchParams.get("subject_id") || "";
  const split_type =
    (searchParams.get("split_type") as "home_away" | "versus_opponent") ||
    "home_away";
  const page = Number(searchParams.get("page") || "1") || 1;
  return { subject_type, subject_id, split_type, page };
}

function buildRequest(
  filters: ReturnType<typeof parseInitialFilters>,
): SplitsRequest {
  const req: SplitsRequest = {
    subject_type: filters.subject_type,
    subject_id: Number(filters.subject_id),
    split_type: filters.split_type,
    page: filters.page || 1,
    page_size: 50,
  };
  return req;
}

export default function SplitsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [filters, setFilters] = useState(() =>
    parseInitialFilters(new URLSearchParams(searchParams?.toString() || "")),
  );
  const [result, setResult] =
    useState<PaginatedResponse<SplitsResponseRow> | null>(null);
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
    if (next.subject_id) params.set("subject_id", String(next.subject_id));
    if (next.split_type) params.set("split_type", next.split_type);
    if (next.page > 1) params.set("page", String(next.page));

    const qs = params.toString();
    router.push(qs ? `/tools/splits?${qs}` : "/tools/splits");

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
      const res = await runSplits(req);
      setResult(res);
    } catch (e: any) {
      setError(e?.message || "Failed to run Splits tool.");
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  // Auto-run if URL already has complete filters
  useEffect(() => {
    if (filters.subject_id && !result && !loading && !error) {
      void runSearch();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const initialValues: Record<string, any> = {
    subject_type: filters.subject_type,
    subject_id: filters.subject_id,
    split_type: filters.split_type,
  };

  return (
    <div>
      <h1 className="page-title">Splits</h1>
      <p className="muted">
        View performance splits for a player or team, such as home vs. away or
        versus specific opponents.
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
            name: "split_type",
            label: "Split Type",
            type: "select",
            options: [
              { label: "Home / Away", value: "home_away" },
              { label: "Versus Opponent", value: "versus_opponent" },
            ],
          },
        ]}
        initialValues={initialValues}
        onSubmit={(values) => {
          void runSearch({
            subject_type: (values as any).subject_type || "player",
            subject_id: (values as any).subject_id
              ? String((values as any).subject_id)
              : "",
            split_type: (values as any).split_type || "home_away",
          });
        }}
        submitLabel="Run Splits"
      />

      {loading && <LoadingState message="Running Splits..." />}
      {error && <ErrorState error={error} />}

      {result && (
        <>
          <ToolResultSummary
            pagination={result.pagination}
            filters={result.filters}
          />
          <DataTable<SplitsResponseRow>
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
            getRowKey={(row, idx) => `${row.subject_id}-${row.split_key}-${idx}`}
          />
        </>
      )}
    </div>
  );
}