BEGIN;

-- Maintenance schedules are safe by default. Set to false only after a
-- separate operator approval and outbound-impact review.
INSERT INTO whatsapp_ai.settings(key, value)
VALUES ('ops_dry_run', 'true')
ON CONFLICT (key) DO UPDATE
SET value = 'true', updated_at = clock_timestamp();

COMMIT;