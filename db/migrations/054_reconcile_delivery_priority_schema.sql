BEGIN;

-- Live schema drift guard:
-- Some deployments have the updated functions but missed the delivery.priority
-- column and the priority-aware delivery claim index/order. Reconcile both here.

ALTER TABLE whatsapp_ai.deliveries
    ADD COLUMN IF NOT EXISTS priority integer NOT NULL DEFAULT 50;

ALTER TABLE whatsapp_ai.deliveries
    ALTER COLUMN priority SET DEFAULT 50;

UPDATE whatsapp_ai.deliveries
SET priority = CASE
    WHEN channel = 'customer' THEN 100
    ELSE 50
END
WHERE priority IS NULL OR priority = 50;

ALTER TABLE whatsapp_ai.deliveries
    ALTER COLUMN priority SET NOT NULL;

DROP INDEX IF EXISTS whatsapp_ai.deliveries_ready_idx;
CREATE INDEX deliveries_ready_idx
    ON whatsapp_ai.deliveries (status, priority DESC, next_attempt_at, created_at);

CREATE OR REPLACE FUNCTION whatsapp_ai.claim_deliveries(p_limit integer DEFAULT 20)
RETURNS SETOF whatsapp_ai.deliveries
LANGUAGE sql
AS $$
WITH candidates AS (
    SELECT d.id
    FROM whatsapp_ai.deliveries d
    WHERE d.status IN ('pending', 'failed')
      AND d.next_attempt_at <= clock_timestamp()
    ORDER BY d.priority DESC, d.created_at
    FOR UPDATE SKIP LOCKED
    LIMIT GREATEST(1, LEAST(p_limit, 100))
), claimed AS (
    UPDATE whatsapp_ai.deliveries d
    SET status = 'sending',
        claimed_at = clock_timestamp(),
        attempt_count = attempt_count + 1,
        updated_at = clock_timestamp()
    FROM candidates c
    WHERE d.id = c.id
    RETURNING d.*
)
SELECT * FROM claimed;
$$;

COMMIT;
