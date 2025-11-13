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
  toolsPlayerGameFinder,
  type PlayerGameFinderRequest,
  type PlayerGameFinderResponseRow,
  type PaginatedResponse,
} from "../../../lib/apiClient";
import type { TableColumn } from "../../../lib/types";

/**
 * Player Game Finder
 *
 * Minimal filters:
 * - player_ids (comma-separated)
 * - from_season, to_season
 * Uses:
 * - POST /api/v1/tools/player-game-finder via runPlayerGameFinder
 */

const columns: TableColumn<PlayerGameFinderResponseRow>[] = [
  { key: "game_id", label: "Game ID" },
  { key: "player_id", label: "Player ID" },
  { key: "season_end_year", label: "Season" },
  { key: "pts", label: "PTS" },
  { key: "trb", label: "TRB" },
  { key: "ast", label: "AST" },
];

function parseInitialFilters(searchParams: URLSearchParams) {
  const player_ids = searchParams.get("player_ids") || "";
  const from_season = searchParams.get("from_season") || "";
  const to_season = searchParams.get("to_season") || "";
  const page = Number(searchParams.get("page") || "1") || 1;
  return { player_ids, from_season, to_season, page };
}

function buildRequest(
  filters: ReturnType<typeof parseInitialFilters>,
): PlayerGameFinderRequest {
  const req: PlayerGameFinderRequest = {};

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

  req.page = filters.page || 1;
  req.page_size = 50;

  return req;
}

export default function PlayerGameFinderPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [filters, setFilters] = useState(() =>
    parseInitialFilters(new URLSearchParams(searchParams?.toString() || "")),
  );
  const [result, setResult] = useState<
    PaginatedResponse<PlayerGameFinderResponseRow> | null
  >(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Sync filters when URL changes
  useEffect(() => {
    const next = parseInitialFilters(
      new URLSearchParams(searchParams?.toString() || ""),
    );
    setFilters(next);
  }, [searchParams]);

  const updateUrlAndRun = async (
    override: Partial<ReturnType<typeof parseInitialFilters>> = {},
  ) => {
    const next = {
      ...filters,
      ...override,
      page: override.page ?? 1,
    };

    const params = new URLSearchParams();
    if (next.player_ids) params.set("player_ids", next.player_ids);
    if (next.from_season) params.set("from_season", next.from_season);
    if (next.to_season) params.set("to_season", next.to_season);
    if (next.page > 1) params.set("page", String(next.page));

    const qs = params.toString();
    router.push(
      qs ? `/tools/player-game-finder?${qs}` : "/tools/player-game-finder",
    );

    setFilters(next);
    setLoading(true);
    setError(null);

    try {
      const req = buildRequest(next);
      const res = await toolsPlayerGameFinder(req);
      setResult(res);
    } catch (e: any) {
      setError(e?.message || "Failed to run Player Game Finder.");
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  // Auto-run if URL already has filters
  useEffect(() => {
    const hasInitial =
      !!filters.player_ids || !!filters.from_season || !!filters.to_season;
    if (hasInitial && !result && !loading && !error) {
      void updateUrlAndRun();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const initialValues: Record<string, any> = {
    player_ids: filters.player_ids,
    from_season: filters.from_season,
    to_season: filters.to_season,
  };

  return (
    <div>
      <h1 className="page-title">Player Game Finder</h1>
      <p className="muted">
        Find individual game lines for one or more players across a chosen
        season range. Use player IDs from the Players index.
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
        ]}
        initialValues={initialValues}
        onSubmit={(values) => {
          void updateUrlAndRun({
            player_ids: (values as any).player_ids || "",
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

      {loading && <LoadingState message="Running Player Game Finder..." />}
      {error && <ErrorState error={error} />}

      {result && (
        <>
          <ToolResultSummary
            pagination={result.pagination}
            filters={result.filters}
          />
          <DataTable<PlayerGameFinderResponseRow>
            columns={columns}
            rows={result.data}
            pagination={
              result.pagination
                ? {
                  page: result.pagination.page,
                  page_size: result.pagination.page_size,
                  total: result.pagination.total,
                  onPageChange: (nextPage) => {
                    void updateUrlAndRun({ page: nextPage });
                  },
                }
                : undefined
            }
            getRowKey={(row, idx) => `${row.game_id}-${row.player_id}-${idx}`}
          />
        </>
      )}
    </div>
  );
}