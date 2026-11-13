DROP INDEX IF EXISTS hub.one_pending_field_change;
CREATE UNIQUE INDEX IF NOT EXISTS one_pending_field_change ON hub.change_requests(opportunity_number,field)
WHERE state IN ('pending_validation','queued','applying','approved','uncertain');

ALTER TABLE hub.change_requests ADD COLUMN IF NOT EXISTS result_code text;
ALTER TABLE hub.change_requests ADD COLUMN IF NOT EXISTS oracle_verified_at timestamptz;
