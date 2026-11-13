ALTER TABLE hub.detail_read_progress DROP CONSTRAINT detail_read_progress_state_check;
ALTER TABLE hub.detail_read_progress ADD CONSTRAINT detail_read_progress_state_check CHECK(state IN ('reading','completed','partial','failed'));
