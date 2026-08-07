BEGIN;

-- Add holidays configuration to settings table
-- Store as JSONB with year as key, array of date strings as value
-- Example: {"2026": ["2026-01-01", "2026-03-20"], "2027": ["2027-01-01", "2027-04-05"]}

ALTER TABLE whatsapp_ai.settings
ADD COLUMN IF NOT EXISTS value_jsonb jsonb;

-- Migrate existing string value to jsonb for holidays key
UPDATE whatsapp_ai.settings
SET value_jsonb = jsonb_build_object('2026', '["2026-01-01","2026-03-20","2026-03-21","2026-03-22","2026-04-23","2026-05-01","2026-05-19","2026-05-27","2026-05-28","2026-05-29","2026-07-15","2026-08-30","2026-10-28","2026-10-29"]'::jsonb)
WHERE key = 'holidays'
  AND value_jsonb IS NULL;

-- Insert default holidays for 2026 if not exists
INSERT INTO whatsapp_ai.settings(key, value, value_jsonb)
VALUES (
    'holidays',
    '{"2026": ["2026-01-01","2026-03-20","2026-03-21","2026-03-22","2026-04-23","2026-05-01","2026-05-19","2026-05-27","2026-05-28","2026-05-29","2026-07-15","2026-08-30","2026-10-28","2026-10-29"]}',
    '{"2026": ["2026-01-01","2026-03-20","2026-03-21","2026-03-22","2026-04-23","2026-05-01","2026-05-19","2026-05-27","2026-05-28","2026-05-29","2026-07-15","2026-08-30","2026-10-28","2026-10-29"]}'::jsonb
)
ON CONFLICT (key) DO NOTHING;

COMMIT;