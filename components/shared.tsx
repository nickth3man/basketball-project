"use client";

import React, { useEffect, useMemo, useState } from "react";
import type { TableColumn } from "../lib/types";

/**
 * Lightweight search bar with debounced onSearch callback.
 * Used on index pages like [`app/players/page.tsx`](app/players/page.tsx:1).
 */
export function EntitySearchBar(props: {
  placeholder?: string;
  initialQuery?: string;
  onSearch: (value: string) => void;
  delayMs?: number;
}) {
  const { placeholder, initialQuery = "", onSearch, delayMs = 300 } = props;
  const [value, setValue] = useState(initialQuery);

  useEffect(() => {
    setValue(initialQuery);
  }, [initialQuery]);

  useEffect(() => {
    const id = setTimeout(() => onSearch(value.trim()), delayMs);
    return () => clearTimeout(id);
  }, [value, delayMs, onSearch]);

  return (
    <input
      className="input"
      type="search"
      placeholder={placeholder ?? "Search..."}
      value={value}
      onChange={(e) => setValue(e.target.value)}
    />
  );
}

/**
 * Generic filters panel driven by a simple config.
 * Intended for tool pages like [`app/tools/player-season-finder/page.tsx`](app/tools/player-season-finder/page.tsx:1).
 */

export type FilterFieldType = "text" | "number" | "checkbox" | "select";

export interface FilterFieldConfig {
  name: string;
  label: string;
  type: FilterFieldType;
  placeholder?: string;
  options?: { label: string; value: string | number }[];
}

export function FiltersPanel(props: {
  fields: FilterFieldConfig[];
  initialValues?: Record<string, any>;
  onChange?: (values: Record<string, any>) => void;
  onSubmit?: (values: Record<string, any>) => void;
  submitLabel?: string;
}) {
  const { fields, initialValues = {}, onChange, onSubmit, submitLabel } = props;
  const [values, setValues] = useState<Record<string, any>>(() => ({
    ...initialValues,
  }));

  useEffect(() => {
    setValues((prev) => ({ ...prev, ...initialValues }));
  }, [initialValues]);

  const handleFieldChange = (name: string, value: any) => {
    setValues((prev) => {
      const next = { ...prev, [name]: value };
      onChange?.(next);
      return next;
    });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit?.(values);
  };

  return (
    <form className="filters-panel" onSubmit={handleSubmit}>
      <div className="filters-grid">
        {fields.map((field) => {
          const v = values[field.name] ?? "";
          if (field.type === "checkbox") {
            return (
              <label key={field.name} className="filter-field">
                <input
                  type="checkbox"
                  checked={Boolean(v)}
                  onChange={(e) =>
                    handleFieldChange(field.name, e.target.checked)
                  }
                />
                <span>{field.label}</span>
              </label>
            );
          }

          if (field.type === "select" && field.options) {
            return (
              <label key={field.name} className="filter-field">
                <span>{field.label}</span>
                <select
                  value={v}
                  onChange={(e) =>
                    handleFieldChange(field.name, e.target.value)
                  }
                >
                  <option value="">Any</option>
                  {field.options.map((opt) => (
                    <option key={String(opt.value)} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </label>
            );
          }

          return (
            <label key={field.name} className="filter-field">
              <span>{field.label}</span>
              <input
                type={field.type === "number" ? "number" : "text"}
                placeholder={field.placeholder}
                value={v}
                onChange={(e) =>
                  handleFieldChange(
                    field.name,
                    field.type === "number"
                      ? e.target.value === ""
                        ? ""
                        : Number(e.target.value)
                      : e.target.value,
                  )
                }
              />
            </label>
          );
        })}
      </div>
      {onSubmit && (
        <div className="filters-actions">
          <button type="submit" className="btn">
            {submitLabel ?? "Apply"}
          </button>
        </div>
      )}
    </form>
  );
}

/**
 * Pagination controls shared between tables and tool results.
 */
export function PaginationControls(props: {
  page: number;
  pageSize: number;
  totalRows: number;
  onPageChange: (page: number) => void;
}) {
  const { page, pageSize, totalRows, onPageChange } = props;
  const totalPages = Math.max(1, Math.ceil(totalRows / pageSize || 1));

  return (
    <div className="pagination">
      <button
        type="button"
        className="btn btn-sm"
        disabled={page <= 1}
        onClick={() => onPageChange(page - 1)}
      >
        Prev
      </button>
      <span className="pagination-label">
        Page {page} of {totalPages}
      </span>
      <button
        type="button"
        className="btn btn-sm"
        disabled={page >= totalPages}
        onClick={() => onPageChange(page + 1)}
      >
        Next
      </button>
    </div>
  );
}

/**
 * Generic DataTable.
 */
export function DataTable<T extends Record<string, any>>(props: {
  columns: TableColumn<T>[];
  rows: T[];
  // When provided, DataTable renders footer controls. The shape matches
  // the backend PaginationMeta type.
  pagination?: {
    page: number;
    page_size: number;
    total: number;
    onPageChange?: (page: number) => void;
  };
  getRowKey?: (row: T, index: number) => React.Key;
}) {
  const { columns, rows, pagination, getRowKey } = props;

  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  const sortedRows = useMemo(() => {
    if (!sortKey) return rows;
    return [...rows].sort((a, b) => {
      const av = a[sortKey as keyof T];
      const bv = b[sortKey as keyof T];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      if (av < bv) return sortDir === "asc" ? -1 : 1;
      if (av > bv) return sortDir === "asc" ? 1 : -1;
      return 0;
    });
  }, [rows, sortKey, sortDir]);

  const handleSort = (col: TableColumn<T>) => {
    if (!col.sortable || typeof col.key !== "string") return;
    if (sortKey === col.key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(col.key);
      setSortDir("asc");
    }
  };

  return (
    <div className="table-wrapper">
      <table className="table">
        <thead>
          <tr>
            {columns.map((col) => {
              const label = col.label;
              const sortable = col.sortable && typeof col.key === "string";
              const active = sortable && sortKey === col.key;
              return (
                <th
                  key={String(col.key)}
                  className={sortable ? "th-sortable" : undefined}
                  onClick={() => sortable && handleSort(col)}
                >
                  {label}
                  {active && (sortDir === "asc" ? " ▲" : " ▼")}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sortedRows.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="table-empty">
                No results.
              </td>
            </tr>
          ) : (
            sortedRows.map((row, idx) => (
              <tr key={getRowKey ? getRowKey(row, idx) : idx}>
                {columns.map((col) => (
                  <td key={String(col.key)}>
                    {col.render
                      ? col.render(row)
                      : (row[col.key as keyof T] as any)?.toString?.() ??
                      ""}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
      {pagination && pagination.onPageChange && (
        <PaginationControls
          page={pagination.page}
          pageSize={pagination.page_size}
          totalRows={pagination.total}
          onPageChange={pagination.onPageChange}
        />
      )}
    </div>
  );
}

/**
 * Simple loading and error states usable across pages.
 */

export function LoadingState({ message }: { message?: string }) {
  return (
    <div className="status status-loading">
      {message ?? "Loading..."}
    </div>
  );
}

export function ErrorState({ error }: { error: string }) {
  return (
    <div className="status status-error">
      {error}
    </div>
  );
}

/**
 * Tool result summary for /tools/* pages.
 */
export function ToolResultSummary(props: {
  pagination?: {
    page: number;
    page_size: number;
    total: number;
  };
  filters?: {
    raw: Record<string, unknown> | null;
  };
}) {
  const { pagination, filters } = props;

  if (!pagination && !filters) {
    return null;
  }

  return (
    <div className="tool-result-summary">
      {pagination && (
        <div>
          Rows {pagination.page_size} per page; total {pagination.total} on
          page {pagination.page}.
        </div>
      )}
      {filters && filters.raw && (
        <pre className="tool-filters-echo">
          {JSON.stringify(filters.raw, null, 2)}
        </pre>
      )}
    </div>
  );
}