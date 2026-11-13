CREATE TABLE IF NOT EXISTS hub.local_activities (
    id text PRIMARY KEY,
    opportunity_number text NOT NULL REFERENCES hub.opportunities,
    kind text NOT NULL CHECK (kind IN ('tasks','appointments','interactions')),
    payload jsonb NOT NULL,
    version bigint NOT NULL DEFAULT 1,
    actor text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS local_activity_opportunity ON hub.local_activities(opportunity_number);
