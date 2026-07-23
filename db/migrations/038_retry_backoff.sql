-- Migration 038: Update retry backoff curves for AI and delivery functions
-- AI retry curve: 30s → 2min → 10min → dead-letter (4 failures)
-- Delivery retry curve: 30s → 2min → 10min → 30min → dead-letter (5 failures)

CREATE OR REPLACE FUNCTION whatsapp_ai.record_ai_failure(
    p_sender_number text, p_batch_token uuid, p_error_code text, p_error text
) RETURNS text
LANGUAGE plpgsql
AS $$
DECLARE
    v_attempt integer;
    v_messages jsonb;
    p_admin_phone_a text := COALESCE((SELECT value FROM whatsapp_ai.settings WHERE key = 'admin_phone_a'), '');
    p_admin_phone_b text := COALESCE((SELECT value FROM whatsapp_ai.settings WHERE key = 'admin_phone_b'), '');
BEGIN
    SELECT ai_attempt_count + 1, processing_messages
    INTO v_attempt, v_messages
    FROM whatsapp_ai.batches
    WHERE sender_number = p_sender_number AND processing_token = p_batch_token
    FOR UPDATE;
    IF NOT FOUND THEN RETURN 'stale'; END IF;

    IF v_attempt >= 4 THEN
        UPDATE whatsapp_ai.batches
        SET status = 'pending', pending_messages = v_messages || pending_messages,
            ai_attempt_count = 0, first_message_at = NULL,
            last_error_code = p_error_code, last_error = left(p_error, 2000),
            processing_token = NULL, processing_started_at = NULL, updated_at = clock_timestamp()
        WHERE sender_number = p_sender_number AND processing_token = p_batch_token;
        IF p_admin_phone_a <> '' THEN
            INSERT INTO whatsapp_ai.deliveries(id, batch_token, sender_number, channel, destination, payload)
            VALUES (gen_random_uuid(), p_batch_token, p_sender_number, 'phone_a', p_admin_phone_a,
                    jsonb_build_object('number', p_admin_phone_a, 'text', 'AI işlemi 4 kez başarısız oldu. Müşteri manuel incelemeye alındı: ' || p_sender_number))
            ON CONFLICT (batch_token, channel) DO NOTHING;
        END IF;
        IF p_admin_phone_b <> '' THEN
            INSERT INTO whatsapp_ai.deliveries(id, batch_token, sender_number, channel, destination, payload)
            VALUES (gen_random_uuid(), p_batch_token, p_sender_number, 'phone_b', p_admin_phone_b,
                    jsonb_build_object('number', p_admin_phone_b, 'text', 'AI işlemi 4 kez başarısız oldu. Müşteri manuel incelemeye alındı: ' || p_sender_number))
            ON CONFLICT (batch_token, channel) DO NOTHING;
        END IF;
        INSERT INTO whatsapp_ai.system_events(event_type, sender_number_masked, batch_token, details)
        VALUES ('ai_dead', right(p_sender_number, 4), p_batch_token,
                jsonb_build_object('code', p_error_code, 'attempt', v_attempt));
        RETURN 'manual';
    END IF;

    UPDATE whatsapp_ai.batches
    SET status = 'pending',
        pending_messages = v_messages || pending_messages,
        processing_messages = '[]'::jsonb,
        processing_token = NULL,
        processing_started_at = NULL,
        ai_attempt_count = v_attempt,
        next_ai_attempt_at = clock_timestamp() + CASE v_attempt
            WHEN 1 THEN interval '30 seconds'
            WHEN 2 THEN interval '2 minutes'
            ELSE interval '10 minutes'
        END,
        last_error_code = p_error_code,
        last_error = left(p_error, 2000),
        first_message_at = clock_timestamp(),
        updated_at = clock_timestamp()
    WHERE sender_number = p_sender_number AND processing_token = p_batch_token;
    RETURN 'retry';
END;
$$;

CREATE OR REPLACE FUNCTION whatsapp_ai.record_delivery_result(
    p_id uuid,
    p_success boolean,
    p_provider_message_id text DEFAULT NULL,
    p_error text DEFAULT NULL
) RETURNS text
LANGUAGE plpgsql
AS $$
DECLARE
    v whatsapp_ai.deliveries%ROWTYPE;
BEGIN
    SELECT * INTO v
    FROM whatsapp_ai.deliveries
    WHERE id = p_id
    FOR UPDATE;

    IF NOT FOUND OR v.status <> 'sending' THEN
        RETURN 'stale';
    END IF;

    IF p_success THEN
        UPDATE whatsapp_ai.deliveries
        SET status = 'sent',
            provider_message_id = p_provider_message_id,
            last_error = NULL,
            updated_at = clock_timestamp()
        WHERE id = p_id;

        IF v.channel IN ('phone_a', 'phone_b') THEN
            INSERT INTO whatsapp_ai.admin_notifications(sender_number, channel, fingerprint)
            VALUES (v.sender_number, v.channel, COALESCE(v.payload->>'fingerprint', ''))
            ON CONFLICT (sender_number, channel) DO UPDATE
            SET fingerprint = EXCLUDED.fingerprint,
                sent_at = clock_timestamp();
        END IF;

        RETURN 'sent';
    ELSIF v.attempt_count >= 5 THEN
        UPDATE whatsapp_ai.deliveries
        SET status = 'dead',
            last_error = left(p_error, 2000),
            updated_at = clock_timestamp()
        WHERE id = p_id;

        INSERT INTO whatsapp_ai.system_events(event_type, sender_number_masked, batch_token, details)
        VALUES (
            'delivery_dead',
            right(v.sender_number, 4),
            v.batch_token,
            jsonb_build_object('channel', v.channel, 'attempt', v.attempt_count)
        );

        RETURN 'dead';
    ELSE
        UPDATE whatsapp_ai.deliveries
        SET status = 'failed',
            last_error = left(p_error, 2000),
            next_attempt_at = clock_timestamp() + CASE v.attempt_count
                WHEN 1 THEN interval '30 seconds'
                WHEN 2 THEN interval '2 minutes'
                WHEN 3 THEN interval '10 minutes'
                ELSE interval '30 minutes'
            END,
            updated_at = clock_timestamp()
        WHERE id = p_id;

        RETURN 'retry';
    END IF;
END;
$$;
