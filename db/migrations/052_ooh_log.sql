BEGIN;

CREATE TABLE IF NOT EXISTS whatsapp_ai.ooh_log (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    sender_number text NOT NULL,
    sender_name text,
    scenario text NOT NULL CHECK (scenario IN ('sunday', 'holiday', 'early_morning', 'evening')),
    istanbul_day text NOT NULL,
    istanbul_time text NOT NULL,
    customer_sent boolean NOT NULL DEFAULT false,
    manager_sent boolean NOT NULL DEFAULT false,
    correlation_id text,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX IF NOT EXISTS idx_ooh_log_created ON whatsapp_ai.ooh_log (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ooh_log_sender ON whatsapp_ai.ooh_log (sender_number);

COMMIT;
