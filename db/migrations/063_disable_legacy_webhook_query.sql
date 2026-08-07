BEGIN;

-- Disable legacy query token authentication by default
-- Header-based authentication (x-webhook-secret) is now required
UPDATE whatsapp_ai.settings
SET value = 'false',
    updated_at = clock_timestamp()
WHERE key = 'webhook_legacy_query_enabled'
  AND value = 'true';

-- Ensure setting exists with false default
INSERT INTO whatsapp_ai.settings(key, value)
VALUES ('webhook_legacy_query_enabled', 'false')
ON CONFLICT (key) DO NOTHING;

COMMIT;