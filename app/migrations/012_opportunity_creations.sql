CREATE TABLE IF NOT EXISTS hub.opportunity_creations (
    id text PRIMARY KEY,
    actor text NOT NULL,
    payload jsonb NOT NULL,
    state text NOT NULL DEFAULT 'pending_validation',
    result_code text,
    opportunity_number text,
    contact_created boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    oracle_verified_at timestamptz
);
CREATE INDEX IF NOT EXISTS opportunity_creations_actor ON hub.opportunity_creations(actor,created_at DESC);
