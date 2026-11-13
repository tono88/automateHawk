CREATE TABLE IF NOT EXISTS hub.detail_read_progress (
 principal text NOT NULL,
 opportunity_number text NOT NULL REFERENCES hub.opportunities(opportunity_number),
 state text NOT NULL CHECK (state IN ('reading','completed','failed')),
 attempts integer NOT NULL DEFAULT 0,
 error_code text NOT NULL DEFAULT '',
 schema_version integer NOT NULL DEFAULT 2,
 updated_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY (principal,opportunity_number)
);

-- Carry forward verified reads without granting access to expired detail values.
INSERT INTO hub.detail_read_progress(principal,opportunity_number,state)
SELECT p.principal,p.opportunity_number,'completed'
FROM hub.user_permissions p JOIN hub.record_details d USING(opportunity_number)
WHERE d.payload->>'schema_version'='2' AND p.detail_fields ? 'contact_link_status'
ON CONFLICT DO NOTHING;
