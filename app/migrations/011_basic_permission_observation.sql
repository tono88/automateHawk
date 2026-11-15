ALTER TABLE hub.user_permissions ADD COLUMN IF NOT EXISTS basic_checked_at timestamptz;
ALTER TABLE hub.user_permissions ADD COLUMN IF NOT EXISTS revoked_at timestamptz;
-- Do not infer a list observation from a configurable expiry. A fresh complete
-- inventory establishes these timestamps before any cache-policy transition.
