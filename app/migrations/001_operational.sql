CREATE TABLE IF NOT EXISTS hub.opportunities (
    opportunity_number text PRIMARY KEY,
    payload jsonb NOT NULL,
    source_hash text NOT NULL,
    version bigint NOT NULL DEFAULT 1,
    first_seen timestamptz NOT NULL DEFAULT now(),
    last_seen timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS hub.sync_runs (
    id bigserial PRIMARY KEY,
    loaded_at timestamptz NOT NULL DEFAULT now(),
    scope text NOT NULL,
    partial boolean NOT NULL DEFAULT true,
    row_count integer NOT NULL,
    changed_count integer NOT NULL
);
CREATE TABLE IF NOT EXISTS hub.opportunity_history (
    id bigserial PRIMARY KEY,
    opportunity_number text NOT NULL REFERENCES hub.opportunities,
    observed_at timestamptz NOT NULL DEFAULT now(),
    source_hash text NOT NULL,
    payload jsonb NOT NULL,
    UNIQUE(opportunity_number,source_hash)
);
CREATE TABLE IF NOT EXISTS hub.record_details (
    opportunity_number text PRIMARY KEY REFERENCES hub.opportunities,
    payload jsonb NOT NULL,
    loaded_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS hub.change_requests (
    id text PRIMARY KEY,
    opportunity_number text NOT NULL REFERENCES hub.opportunities,
    field text NOT NULL,
    old_value text NOT NULL,
    new_value text NOT NULL,
    expected_version bigint NOT NULL,
    actor text NOT NULL,
    state text NOT NULL DEFAULT 'pending_validation',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS one_pending_field_change
ON hub.change_requests(opportunity_number,field)
WHERE state IN ('pending_validation','approved','applying');
CREATE TABLE IF NOT EXISTS hub.audit_events (
    id bigserial PRIMARY KEY,
    at timestamptz NOT NULL DEFAULT now(),
    actor text NOT NULL,
    action text NOT NULL,
    opportunity_number text,
    metadata jsonb NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS hub.settings (
    key text PRIMARY KEY,
    value jsonb NOT NULL
);
CREATE INDEX IF NOT EXISTS opportunity_payload_search ON hub.opportunities USING gin(payload);
