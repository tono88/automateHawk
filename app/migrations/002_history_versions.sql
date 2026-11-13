ALTER TABLE hub.opportunity_history ADD COLUMN IF NOT EXISTS source_version bigint NOT NULL DEFAULT 1;
ALTER TABLE hub.opportunity_history DROP CONSTRAINT IF EXISTS opportunity_history_opportunity_number_source_hash_key;
CREATE UNIQUE INDEX IF NOT EXISTS history_record_version ON hub.opportunity_history(opportunity_number,source_version);
