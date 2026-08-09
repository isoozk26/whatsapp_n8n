BEGIN;

-- Reconcile live schema: batches has first_message_at/last_message_at, not created_at.
CREATE OR REPLACE FUNCTION whatsapp_ai.get_dashboard_stats()
RETURNS jsonb
LANGUAGE plpgsql
AS $$
DECLARE
    result jsonb;
BEGIN
    SELECT jsonb_build_object(
        'timestamp', clock_timestamp(),
        'batches', jsonb_build_object(
            'pending', (SELECT count(*) FROM whatsapp_ai.batches WHERE status = 'pending'),
            'processing', (SELECT count(*) FROM whatsapp_ai.batches WHERE status = 'processing'),
            'manual', (SELECT count(*) FROM whatsapp_ai.batches WHERE status = 'manual'),
            'total', (SELECT count(*) FROM whatsapp_ai.batches)
        ),
        'deliveries', jsonb_build_object(
            'pending', (SELECT count(*) FROM whatsapp_ai.deliveries WHERE status = 'pending'),
            'sending', (SELECT count(*) FROM whatsapp_ai.deliveries WHERE status = 'sending'),
            'sent', (SELECT count(*) FROM whatsapp_ai.deliveries WHERE status = 'sent'),
            'failed', (SELECT count(*) FROM whatsapp_ai.deliveries WHERE status = 'failed'),
            'dead', (SELECT count(*) FROM whatsapp_ai.deliveries WHERE status = 'dead')
        ),
        'circuit_breakers', jsonb_build_object(
            'openai', (SELECT state FROM whatsapp_ai.service_circuits WHERE service = 'openai'),
            'evolution', (SELECT state FROM whatsapp_ai.service_circuits WHERE service = 'evolution')
        ),
        'today_events', jsonb_build_object(
            'total', (SELECT count(*) FROM whatsapp_ai.system_events WHERE created_at > date_trunc('day', now())),
            'ai_dead', (SELECT count(*) FROM whatsapp_ai.system_events WHERE event_type = 'ai_dead' AND created_at > date_trunc('day', now())),
            'delivery_dead', (SELECT count(*) FROM whatsapp_ai.system_events WHERE event_type = 'delivery_dead' AND created_at > date_trunc('day', now())),
            'spam_limit', (SELECT count(*) FROM whatsapp_ai.system_events WHERE event_type = 'spam_limit' AND created_at > date_trunc('day', now()))
        ),
        'performance', jsonb_build_object(
            'avg_processing_time_ms', (
                SELECT COALESCE(AVG(EXTRACT(EPOCH FROM (updated_at - first_message_at)) * 1000), 0)::integer
                FROM whatsapp_ai.batches
                WHERE status IN ('processing', 'pending')
                  AND first_message_at IS NOT NULL
                  AND first_message_at > now() - interval '1 hour'
            ),
            'messages_last_hour', (
                SELECT count(*) FROM whatsapp_ai.messages
                WHERE received_at > now() - interval '1 hour'
            )
        )
    ) INTO result;

    RETURN result;
END;
$$;

-- Report the most recent observed inbound or successful outbound activity.
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

-- The 7-argument function is legacy. Current workflow resolves the 8-argument
-- function carrying next_ai_attempt_at; retain only that signature.
DROP FUNCTION IF EXISTS whatsapp_ai.ingest_message(text, text, text, jsonb, text, text, text);

COMMIT;
