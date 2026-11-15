ALTER TABLE hub.detail_read_progress ADD COLUMN IF NOT EXISTS source_version bigint;
-- Legacy reads remain comparable through their completion time and the current
-- opportunity-history version; do not claim a version that was never observed.
