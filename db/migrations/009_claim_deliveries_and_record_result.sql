CREATE OR REPLACE FUNCTION whatsapp_ai.claim_deliveries(p_limit integer DEFAULT 20)
RETURNS SETOF whatsapp_ai.deliveries
LANGUAGE sql
AS $$
WITH candidates AS (
    SELECT d.id
    FROM whatsapp_ai.deliveries d
    WHERE d.status IN ('pending', 'failed')
      AND d.next_attempt_at <= clock_timestamp()
    ORDER BY d.created_at
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
    ELSIF v.attempt_count >= 3 THEN
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
                ELSE interval '2 minutes'
            END,
            updated_at = clock_timestamp()
        WHERE id = p_id;

        RETURN 'retry';
    END IF;
END;
$$;