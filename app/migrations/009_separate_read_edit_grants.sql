ALTER TABLE hub.user_permissions ADD COLUMN IF NOT EXISTS detail_checked_at timestamptz;
ALTER TABLE hub.user_permissions ADD COLUMN IF NOT EXISTS edit_until timestamptz;
-- Previous detail grants were issued for exactly thirty minutes. A list
-- refresh must not be mistaken for a new observation of detail permissions.
UPDATE hub.user_permissions SET detail_checked_at=detail_until-interval '30 minutes',
  edit_until=detail_until WHERE detail_until IS NOT NULL AND detail_checked_at IS NULL;
