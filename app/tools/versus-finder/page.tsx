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
  toolsVersusFinder,
  type VersusFinderRequest,
  type VersusFinderResponseRow,
  type PaginatedResponse,
} from "../../../lib/apiClient";
import type { TableColumn } from "../../../lib/types";

/**
 * Versus Finder
 *
 * Minimal filters:
 * - entity_type: "player" or "team"
 * - subject_id
 * - opponent_ids (comma-separated)
 *
 * Uses:
 * - POST /api/v1/tools/versus-finder via runVersusFinder
 */

const columns: TableColumn<VersusFinderResponseRow>[] = [
  { key: "subject_id", label: "Subject ID" },
  { key: "opponent_id", label: "Opponent ID" },
  { key: "g", label: "G" },
  { key: "pts_per_g", label: "PTS/G" },
];

function parseInitialFilters(searchParams: URLSearchParams) {
  const entity_type = searchParams.get("entity_type") || "player";
  const subject_id = searchParams.get("subject_id") || "";
  const opponent_ids = searchParams.get("opponent_ids") || "";
  const page = Number(searchParams.get("page") || "1") || 1;
  return { entity_type, subject_id, opponent_ids, page };
}

function buildRequest(
  filters: ReturnType<typeof parseInitialFilters>,
): VersusFinderRequest {
  const req: VersusFinderRequest = {
    page: filters.page || 1,
    page_size: 50,
  };

  const sid = Number(filters.subject_id);
  if (!Number.isNaN(sid) && sid > 0) {
    if (filters.entity_type === "team") {
      req.team_id = sid;
      delete req.player_id;
    } else {
      req.player_id = sid;
      delete req.team_id;
    }
  }

  if (filters.opponent_ids) {
    const ids = filters.opponent_ids
      .split(",")
      .map((v) => v.trim())
      .filter(Boolean)
      .map((v) => Number(v))
      .filter((n) => !Number.isNaN(n));
    if (ids.length > 0) {
      req.opponent_ids = ids;
    }
  }

  return req;
}

export default function VersusFinderPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [filters, setFilters] = useState(() =>
    parseInitialFilters(new URLSearchParams(searchParams?.toString() || "")),
  );
  const [result, setResult] =
    useState<PaginatedResponse<VersusFinderResponseRow> | null>(null);
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
    if (next.entity_type) params.set("entity_type", next.entity_type);
    if (next.subject_id) params.set("subject_id", next.subject_id);
    if (next.opponent_ids) params.set("opponent_ids", next.opponent_ids);
    if (next.page > 1) params.set("page", String(next.page));

    const qs = params.toString();
    router.push(qs ? `/tools/versus-finder?${qs}` : "/tools/versus-finder");

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
      const res = await toolsVersusFinder(req);
      setResult(res);
    } catch (e: any) {
      setError(e?.message || "Failed to run Versus Finder.");
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
    entity_type: filters.entity_type,
    subject_id: filters.subject_id,
    opponent_ids: filters.opponent_ids,
  };

  return (
    <div>
      <h1 className="page-title">Versus Finder</h1>
      <p className="muted">
        Compare a player or team's performance versus specific opponents.
      </p>

      <FiltersPanel
        fields={[
          {
            name: "entity_type",
            label: "Entity Type",
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
            name: "opponent_ids",
            label: "Opponent IDs",
            type: "text",
            placeholder: "Optional comma-separated opponent IDs.",
          },
        ]}
        initialValues={initialValues}
        onSubmit={(values) => {
          void runSearch({
            entity_type: (values as any).entity_type || "player",
            subject_id: (values as any).subject_id
              ? String((values as any).subject_id)
              : "",
            opponent_ids: (values as any).opponent_ids || "",
          });
        }}
        submitLabel="Run Versus Search"
      />

      {loading && <LoadingState message="Running Versus Finder..." />}
      {error && <ErrorState error={error} />}

      {result && (
        <>
          <ToolResultSummary
            pagination={result.pagination}
            filters={result.filters}
          />
          <DataTable<VersusFinderResponseRow>
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
              `${row.subject_id}-${row.opponent_id}-${idx}`
            }
          />
        </>
      )}
    </div>
  );
}