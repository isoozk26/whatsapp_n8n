BEGIN;

-- A non-empty dead-letter queue is an observable degradation even below the
-- critical threshold. Keep circuit/pending failures at degraded priority.
CREATE OR REPLACE FUNCTION whatsapp_ai.get_health_status()
RETURNS jsonb
LANGUAGE plpgsql
AS $$
DECLARE
    result jsonb;
    v_pending_batches integer;
    v_processing_batches integer;
    v_pending_deliveries integer;
    v_dead_deliveries integer;
    v_circuit_openai text;
    v_circuit_evolution text;
    v_last_processed timestamptz;
BEGIN
    SELECT count(*) INTO v_pending_batches FROM whatsapp_ai.batches WHERE status = 'pending';
    SELECT count(*) INTO v_processing_batches FROM whatsapp_ai.batches WHERE status = 'processing';
    SELECT count(*) INTO v_pending_deliveries FROM whatsapp_ai.deliveries WHERE status = 'pending';
    SELECT count(*) INTO v_dead_deliveries FROM whatsapp_ai.deliveries WHERE status = 'dead';
    SELECT state INTO v_circuit_openai FROM whatsapp_ai.service_circuits WHERE service = 'openai';
    SELECT state INTO v_circuit_evolution FROM whatsapp_ai.service_circuits WHERE service = 'evolution';
    SELECT GREATEST(
        COALESCE((SELECT max(sent_at) FROM whatsapp_ai.deliveries WHERE status = 'sent'), '-infinity'::timestamptz),
        COALESCE((SELECT max(received_at) FROM whatsapp_ai.messages), '-infinity'::timestamptz)
    ) INTO v_last_processed;
    IF v_last_processed = '-infinity'::timestamptz THEN
        v_last_processed := NULL;
    END IF;

    SELECT jsonb_build_object(
        'status', CASE
            WHEN v_dead_deliveries > 10 THEN 'degraded'
            WHEN v_circuit_openai = 'open' OR v_circuit_evolution = 'open' THEN 'degraded'
            WHEN v_dead_deliveries > 0 THEN 'warning'
            WHEN v_pending_batches > 100 THEN 'warning'
            ELSE 'ok'
        END,
        'timestamp', clock_timestamp(),
        'queue_depth', jsonb_build_object(
            'pending_batches', v_pending_batches,
            'processing_batches', v_processing_batches,
            'pending_deliveries', v_pending_deliveries,
            'dead_deliveries', v_dead_deliveries
        ),
        'circuit_breakers', jsonb_build_object(
            'openai', v_circuit_openai,
            'evolution', v_circuit_evolution
        ),
        'last_processed_at', v_last_processed,
        'uptime_seconds', CASE
            WHEN v_last_processed IS NULL THEN NULL
            ELSE EXTRACT(EPOCH FROM (clock_timestamp() - v_last_processed))::integer
        END
    ) INTO result;

    RETURN result;
END;
$$;

COMMIT;
