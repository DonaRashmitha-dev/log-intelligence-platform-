-- ─────────────────────────────────────────
-- Extensions
-- ─────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ─────────────────────────────────────────
-- Core log table
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS logs (
    id              BIGSERIAL PRIMARY KEY,
    source          TEXT NOT NULL,          -- 'cpp_metrics' | 'flask_fault' | 'node_alerts'
    event_type      TEXT NOT NULL,          -- 'metric' | 'fault_injected' | 'anomaly' | 'recovery'
    severity        TEXT NOT NULL DEFAULT 'info',
    message         TEXT NOT NULL,
    raw_payload     JSONB NOT NULL,
    embedding       vector(768),            -- nomic-embed-text = 768 dims
    source_ts       TIMESTAMPTZ NOT NULL,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    process_id      TEXT,
    host            TEXT
);

CREATE INDEX IF NOT EXISTS logs_embedding_hnsw
    ON logs USING hnsw (embedding vector_cosine_ops)
    WITH (m=16, ef_construction=128);

CREATE INDEX IF NOT EXISTS logs_source_ts      ON logs (source_ts DESC);
CREATE INDEX IF NOT EXISTS logs_event_type     ON logs (event_type);
CREATE INDEX IF NOT EXISTS logs_severity       ON logs (severity) WHERE severity IN ('error','critical');
CREATE INDEX IF NOT EXISTS logs_raw_payload_gin ON logs USING gin (raw_payload);

-- ─────────────────────────────────────────
-- Fault events
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fault_events (
    id              BIGSERIAL PRIMARY KEY,
    log_id          BIGINT REFERENCES logs(id),
    fault_type      TEXT NOT NULL,
    target_pid      INT,
    injected_at     TIMESTAMPTZ NOT NULL,
    recovered_at    TIMESTAMPTZ,
    mttr_seconds    FLOAT,
    crash_count     INT DEFAULT 0,
    recovery_count  INT DEFAULT 0,
    parameters      JSONB
);

CREATE INDEX IF NOT EXISTS fault_events_type  ON fault_events (fault_type);
CREATE INDEX IF NOT EXISTS fault_events_ts    ON fault_events (injected_at DESC);

-- ─────────────────────────────────────────
-- System metrics
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS system_metrics (
    id              BIGSERIAL PRIMARY KEY,
    log_id          BIGINT REFERENCES logs(id),
    host            TEXT NOT NULL,
    cpu_pct         FLOAT,
    mem_pct         FLOAT,
    latency_ms      FLOAT,
    ewma_cpu        FLOAT,
    ewma_mem        FLOAT,
    is_anomaly      BOOLEAN DEFAULT false,
    recorded_at     TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS metrics_anomaly ON system_metrics (recorded_at DESC) WHERE is_anomaly = true;
CREATE INDEX IF NOT EXISTS metrics_host_ts ON system_metrics (host, recorded_at DESC);

-- ─────────────────────────────────────────
-- Agent conversation history
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    messages        JSONB NOT NULL DEFAULT '[]',
    metadata        JSONB
);
