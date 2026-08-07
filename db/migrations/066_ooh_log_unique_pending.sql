BEGIN;

-- Add unique constraint to prevent duplicate OOH logs for same sender when customer_sent = false
-- This works with ON CONFLICT (sender_number) DO NOTHING in Claim OOH Notification
CREATE UNIQUE INDEX IF NOT EXISTS idx_ooh_log_sender_pending
ON whatsapp_ai.ooh_log (sender_number)
WHERE customer_sent = false;

COMMIT;