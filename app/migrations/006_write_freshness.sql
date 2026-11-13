ALTER TABLE hub.opportunities ADD COLUMN IF NOT EXISTS last_write_verified_at timestamptz;
