CREATE TABLE IF NOT EXISTS hub.user_permissions (
    principal text NOT NULL,
    opportunity_number text NOT NULL REFERENCES hub.opportunities,
    basic_fields jsonb NOT NULL DEFAULT '[]',
    detail_fields jsonb NOT NULL DEFAULT '[]',
    capabilities jsonb NOT NULL DEFAULT '{}',
    activities_visible boolean NOT NULL DEFAULT false,
    read_until timestamptz NOT NULL,
    detail_until timestamptz,
    checked_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(principal,opportunity_number)
);
CREATE INDEX IF NOT EXISTS permission_expiry ON hub.user_permissions(principal,read_until);
