BEGIN;

-- Fix enqueue_ooh_manager_alert to support retries with ON CONFLICT DO UPDATE
CREATE OR REPLACE FUNCTION whatsapp_ai.enqueue_ooh_manager_alert(
    p_ooh_log_id uuid,
    p_text text
) RETURNS boolean
LANGUAGE plpgsql
AS $$
DECLARE
    v_sender_number text;
    v_correlation_id text;
    v_queued boolean := false;
    v_channel text;
    v_destination text;
    v_delivery_id uuid;
BEGIN
    SELECT sender_number, COALESCE(correlation_id, '')
    INTO v_sender_number, v_correlation_id
    FROM whatsapp_ai.ooh_log
    WHERE id = p_ooh_log_id;

    IF NOT FOUND OR NULLIF(trim(COALESCE(p_text, '')), '') IS NULL THEN
        RETURN false;
    END IF;

    FOREACH v_channel IN ARRAY ARRAY['phone_a', 'phone_b']::text[] LOOP
        SELECT value INTO v_destination
        FROM whatsapp_ai.settings
        WHERE key = v_channel;

        IF NULLIF(trim(COALESCE(v_destination, '')), '') IS NULL THEN
            CONTINUE;
        END IF;

        v_delivery_id := gen_random_uuid();
        INSERT INTO whatsapp_ai.deliveries(
            id, batch_token, sender_number, channel, destination, payload, priority
        )
        VALUES (
            v_delivery_id,
            p_ooh_log_id,
            v_sender_number,
            v_channel,
            v_destination,
            jsonb_build_object(
                'number', v_destination,
                'text', left(p_text, 4096),
                'kind', 'ooh_manager',
                'correlationId', v_correlation_id,
                '_deliveryType', 'ooh_manager'
            ),
            50
        )
        ON CONFLICT (batch_token, channel) DO UPDATE SET
            payload = EXCLUDED.payload,
            status = 'pending',
            next_attempt_at = clock_timestamp(),
            attempt_count = 0,
            last_error = NULL,
            updated_at = clock_timestamp();

        INSERT INTO whatsapp_ai.ooh_manager_dispatch(ooh_log_id, channel, delivery_id)
        SELECT p_ooh_log_id, v_channel, COALESCE(
            (SELECT id FROM whatsapp_ai.deliveries WHERE batch_token = p_ooh_log_id AND channel = v_channel),
            v_delivery_id
        )
        ON CONFLICT (ooh_log_id, channel) DO NOTHING;

        IF EXISTS (
            SELECT 1 FROM whatsapp_ai.deliveries
            WHERE batch_token = p_ooh_log_id AND channel = v_channel
        ) THEN
            v_queued := true;
        END IF;
    END LOOP;

    UPDATE whatsapp_ai.ooh_log
    SET manager_sent = v_queued
    WHERE id = p_ooh_log_id;

    RETURN v_queued;
END;
$$;

COMMIT;