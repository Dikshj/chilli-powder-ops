CREATE TABLE IF NOT EXISTS client_capabilities (
    client_id TEXT PRIMARY KEY,
    input_tier TEXT NOT NULL CHECK (input_tier IN ('manual', 'erp', 'sensor')),
    enabled_sources JSONB NOT NULL DEFAULT '[]',
    updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS target_definitions (
    id BIGSERIAL PRIMARY KEY,
    client_id TEXT NOT NULL,
    plant TEXT NOT NULL DEFAULT '',
    line_name TEXT NOT NULL,
    product TEXT NOT NULL DEFAULT '',
    metric TEXT NOT NULL,
    target_value DOUBLE PRECISION NOT NULL,
    unit TEXT NOT NULL,
    tolerance DOUBLE PRECISION NOT NULL DEFAULT 0,
    effective_from TIMESTAMPTZ,
    effective_to TIMESTAMPTZ,
    owner_name TEXT NOT NULL DEFAULT '',
    version INTEGER NOT NULL DEFAULT 1,
    UNIQUE(client_id, plant, line_name, product, metric, version)
);
CREATE TABLE IF NOT EXISTS canonical_production_records (
    fingerprint TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    plant TEXT NOT NULL DEFAULT '',
    line_name TEXT NOT NULL,
    shift_name TEXT NOT NULL DEFAULT '',
    recorded_at TIMESTAMPTZ NOT NULL,
    product TEXT NOT NULL DEFAULT '',
    quantity DOUBLE PRECISION NOT NULL,
    unit TEXT NOT NULL,
    data_source TEXT NOT NULL,
    source_record_id TEXT NOT NULL,
    measurements JSONB NOT NULL DEFAULT '{}',
    provenance JSONB NOT NULL DEFAULT '{}',
    ingested_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(client_id, data_source, source_record_id)
);
CREATE TABLE IF NOT EXISTS rca_incidents (
    incident_id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    line_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'OPEN',
    comparison JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS supervisor_reasons (
    id BIGSERIAL PRIMARY KEY,
    incident_id TEXT NOT NULL REFERENCES rca_incidents(incident_id),
    reason_category TEXT NOT NULL,
    reason_description TEXT NOT NULL,
    supervisor TEXT NOT NULL,
    submitted_at TIMESTAMPTZ NOT NULL,
    supporting_evidence JSONB NOT NULL DEFAULT '[]',
    audit_status TEXT NOT NULL DEFAULT 'reported'
);
CREATE TABLE IF NOT EXISTS rca_category_registry (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    definition TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'awaiting_definitions'
);
