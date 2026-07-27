BEGIN;

INSERT INTO whatsapp_ai.settings(key, value)
VALUES
    ('admin_number_prefixes', '905360'),
    ('admin_filter_enabled', 'true')
ON CONFLICT (key) DO UPDATE
SET value = EXCLUDED.value,
    updated_at = clock_timestamp();

COMMIT;
