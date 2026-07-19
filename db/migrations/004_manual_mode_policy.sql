-- Manual mode is now explicit-only: it can be enabled by the authorized pause command.
-- Clear legacy rows created by the previous implicit AI handoff/dead-letter behavior.
DELETE FROM whatsapp_ai.manual_modes;

UPDATE whatsapp_ai.batches
SET status = 'pending',
    first_message_at = CASE
        WHEN jsonb_array_length(pending_messages) > 0 THEN clock_timestamp()
        ELSE NULL
    END,
    updated_at = clock_timestamp()
WHERE status = 'manual';
