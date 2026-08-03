-- Dashboard Stats Function
-- Provides real-time metrics for monitoring dashboard

CREATE OR REPLACE FUNCTION whatsapp_ai.get_dashboard_stats()
RETURNS jsonb AS $$
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
            'openai', (SELECT state FROM whatsapp_ai.circuit_breakers WHERE service_name = 'openai'),
            'evolution', (SELECT state FROM whatsapp_ai.circuit_breakers WHERE service_name = 'evolution')
        ),
        'today_events', jsonb_build_object(
            'total', (SELECT count(*) FROM whatsapp_ai.system_events WHERE created_at > date_trunc('day', now())),
            'ai_dead', (SELECT count(*) FROM whatsapp_ai.system_events WHERE event_type = 'ai_dead' AND created_at > date_trunc('day', now())),
            'delivery_dead', (SELECT count(*) FROM whatsapp_ai.system_events WHERE event_type = 'delivery_dead' AND created_at > date_trunc('day', now())),
            'spam_limit', (SELECT count(*) FROM whatsapp_ai.system_events WHERE event_type = 'spam_limit' AND created_at > date_trunc('day', now()))
        ),
        'performance', jsonb_build_object(
            'avg_processing_time_ms', (
                SELECT COALESCE(AVG(EXTRACT(EPOCH FROM (updated_at - created_at)) * 1000), 0)::integer
                FROM whatsapp_ai.batches 
                WHERE status IN ('processing', 'pending') 
                AND created_at > now() - interval '1 hour'
            ),
            'messages_last_hour', (
                SELECT count(*) FROM whatsapp_ai.messages 
                WHERE received_at > now() - interval '1 hour'
            )
        )
    ) INTO result;
    
    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- Dead Letter Queue Table
CREATE TABLE IF NOT EXISTS whatsapp_ai.dead_letters (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_token uuid,
    sender_number text,
    channel text,
    error_code text,
    error_message text,
    payload jsonb,
    attempt_count integer NOT NULL DEFAULT 0,
    last_attempt_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    resolved_at timestamptz
);
CREATE INDEX IF NOT EXISTS dead_letters_unresolved_idx 
    ON whatsapp_ai.dead_letters (created_at) 
    WHERE resolved_at IS NULL;

-- Dead Letter Recording Function
CREATE OR REPLACE FUNCTION whatsapp_ai.record_dead_letter(
    p_batch_token uuid,
    p_sender_number text,
    p_channel text,
    p_error_code text,
    p_error_message text,
    p_payload jsonb
) RETURNS uuid AS $$
DECLARE
    v_id uuid;
BEGIN
    INSERT INTO whatsapp_ai.dead_letters (
        batch_token, sender_number, channel, error_code, error_message, payload
    ) VALUES (
        p_batch_token, p_sender_number, p_channel, p_error_code, p_error_message, p_payload
    ) RETURNING id INTO v_id;
    
    INSERT INTO whatsapp_ai.system_events(event_type, sender_number_masked, batch_token, details)
    VALUES ('dead_letter', right(p_sender_number, 4), p_batch_token,
            jsonb_build_object('channel', p_channel, 'error_code', p_error_code));
    
    RETURN v_id;
END;
$$ LANGUAGE plpgsql;

-- Dead Letter Recovery Function
CREATE OR REPLACE FUNCTION whatsapp_ai.recover_dead_letters(
    p_limit integer DEFAULT 10
) RETURNS TABLE(
    id uuid,
    batch_token uuid,
    sender_number text,
    channel text,
    payload jsonb
) AS $$
BEGIN
    RETURN QUERY
    WITH candidates AS (
        SELECT dl.id, dl.batch_token, dl.sender_number, dl.channel, dl.payload
        FROM whatsapp_ai.dead_letters dl
        WHERE dl.resolved_at IS NULL
          AND dl.attempt_count < 3
          AND dl.last_attempt_at < clock_timestamp() - interval '5 minutes'
        ORDER BY dl.created_at
        LIMIT p_limit
        FOR UPDATE SKIP LOCKED
    ), recovered AS (
        UPDATE whatsapp_ai.dead_letters d
        SET attempt_count = attempt_count + 1,
            last_attempt_at = clock_timestamp()
        FROM candidates c
        WHERE d.id = c.id
        RETURNING d.id, d.batch_token, d.sender_number, d.channel, d.payload
    )
    SELECT r.id, r.batch_token, r.sender_number, r.channel, r.payload FROM recovered r;
END;
$$ LANGUAGE plpgsql;

-- Health Check Function
-- Returns system health status for monitoring

CREATE OR REPLACE FUNCTION whatsapp_ai.get_health_status()
RETURNS jsonb AS $$
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
    SELECT state INTO v_circuit_openai FROM whatsapp_ai.circuit_breakers WHERE service_name = 'openai';
    SELECT state INTO v_circuit_evolution FROM whatsapp_ai.circuit_breakers WHERE service_name = 'evolution';
    SELECT MAX(updated_at) INTO v_last_processed FROM whatsapp_ai.batches WHERE status IN ('processing', 'pending');
    
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
        'uptime_seconds', EXTRACT(EPOCH FROM (clock_timestamp() - v_last_processed))::integer
    ) INTO result;
    
    RETURN result;
END;
$$ LANGUAGE plpgsql;
