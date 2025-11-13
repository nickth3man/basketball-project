-- 003_etl_metadata.sql
-- Add ETL metadata tables. Additive-only; safe to run once.

BEGIN;

-- etl_runs: high-level ETL job tracking
CREATE TABLE IF NOT EXISTS etl_runs (
    etl_run_id          BIGSERIAL PRIMARY KEY,
    job_name            TEXT NOT NULL,
    mode                TEXT NOT NULL DEFAULT 'full',
    params              JSONB NOT NULL DEFAULT '{}'::jsonb,
    status              TEXT NOT NULL,
    started_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at         TIMESTAMPTZ,
    message             TEXT,
    created_by          TEXT DEFAULT 'local',
    expectations_version TEXT
);

-- etl_run_steps: per-step loader tracking
CREATE TABLE IF NOT EXISTS etl_run_steps (
    etl_run_step_id BIGSERIAL PRIMARY KEY,
    etl_run_id BIGINT NOT NULL REFERENCES etl_runs (etl_run_id) ON DELETE CASCADE,
    step_name TEXT NOT NULL,
    loader_module TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    rows_inserted BIGINT,
    rows_updated BIGINT,
    rows_deleted BIGINT,
    input_files JSONB,
    output_tables JSONB,
    error_message TEXT
);

-- etl_run_issues: structured issues associated with runs/steps
CREATE TABLE IF NOT EXISTS etl_run_issues (
    etl_run_issue_id BIGSERIAL PRIMARY KEY,
    etl_run_id BIGINT NOT NULL REFERENCES etl_runs (etl_run_id) ON DELETE CASCADE,
    step_name TEXT,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    issue_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    details JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMIT;