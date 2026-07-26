BEGIN;

CREATE OR REPLACE FUNCTION whatsapp_ai.recover_stale_batches(
    p_age interval DEFAULT interval '10 minutes'
) RETURNS jsonb
LANGUAGE plpgsql
AS $$
DECLARE
    v_recovered integer := 0;
BEGIN
    WITH stale AS (
        SELECT sender_number, processing_token
        FROM whatsapp_ai.batches
        WHERE status = 'processing'
          AND processing_started_at IS NOT NULL
          AND processing_started_at < clock_timestamp() - p_age
        FOR UPDATE SKIP LOCKED
    ), moved AS (
        UPDATE whatsapp_ai.batches b
        SET status = 'pending',
            pending_messages = b.processing_messages || b.pending_messages,
            processing_messages = '[]'::jsonb,
            processing_token = NULL,
            processing_started_at = NULL,
            ai_attempt_count = 0,
            next_ai_attempt_at = NULL,
            last_error_code = 'WORKER_CRASH',
            last_error = 'stale_processing_recovered',
            first_message_at = clock_timestamp() - interval '120 seconds',
            updated_at = clock_timestamp()
        FROM stale s
        WHERE b.sender_number = s.sender_number
          AND b.processing_token = s.processing_token
          AND b.status = 'processing'
        RETURNING b.sender_number
    )
    SELECT count(*) INTO v_recovered FROM moved;

    IF v_recovered > 0 THEN
        INSERT INTO whatsapp_ai.system_events(event_type, details)
        VALUES ('stale_batch_recovery', jsonb_build_object(
            'recovered', v_recovered,
            'ageSeconds', extract(epoch FROM p_age)
        ));
    END IF;

    RETURN jsonb_build_object('recovered', v_recovered, 'ageSeconds', extract(epoch FROM p_age));
END;
$$;

CREATE OR REPLACE FUNCTION whatsapp_ai.claim_ready_batches(p_limit integer DEFAULT 10)
RETURNS TABLE(
    sender_number text, sender_name text, batch_token uuid,
    messages jsonb, message_count integer, all_messages_text text,
    ai_attempt_count integer, assignee_name text
)
LANGUAGE plpgsql
AS $$
BEGIN
    PERFORM whatsapp_ai.recover_stale_batches(interval '10 minutes');

    RETURN QUERY
    WITH candidates AS (
        SELECT b.sender_number
        FROM whatsapp_ai.batches b
        WHERE b.status = 'pending'
          AND jsonb_array_length(b.pending_messages) > 0
          AND (b.next_ai_attempt_at IS NULL OR b.next_ai_attempt_at <= clock_timestamp())
          AND (
              b.ai_attempt_count > 0
              OR b.first_message_at <= clock_timestamp() - interval '120 seconds'
          )
        ORDER BY b.first_message_at
        FOR UPDATE SKIP LOCKED
        LIMIT GREATEST(1, LEAST(p_limit, 50))
    ), claimed AS (
        UPDATE whatsapp_ai.batches b
        SET status = 'processing',
            processing_messages = b.pending_messages,
            pending_messages = '[]'::jsonb,
            processing_token = gen_random_uuid(),
            processing_started_at = clock_timestamp(),
            first_message_at = NULL,
            next_ai_attempt_at = NULL,
            updated_at = clock_timestamp()
        FROM candidates c
        WHERE b.sender_number = c.sender_number
        RETURNING b.*
    )
    SELECT c.sender_number, c.sender_name, c.processing_token,
           c.processing_messages, jsonb_array_length(c.processing_messages),
           COALESCE((SELECT string_agg(
                        format('%s. [%s] %s', x.ord,
                            to_char(to_timestamp(COALESCE(NULLIF(x.item->>'timestamp', '')::double precision, 0) / 1000)
                                AT TIME ZONE 'Europe/Istanbul', 'HH24:MI'),
                            x.item->>'text'),
                        E'\n' ORDER BY x.ord)
                     FROM jsonb_array_elements(c.processing_messages) WITH ORDINALITY x(item, ord)), ''),
           c.ai_attempt_count,
           COALESCE((SELECT value FROM whatsapp_ai.settings WHERE key = 'assignee_name'), 'Ä°smail Ã–zkaracan')
    FROM claimed c;
END;
$$;

CREATE OR REPLACE FUNCTION whatsapp_ai.complete_ai_batch(
    p_sender_number text,
    p_batch_token uuid,
    p_customer_reply text,
    p_admin_message text,
    p_notify_admins boolean,
    p_reply_customer boolean,
    p_pause_automation boolean,
    p_fingerprint text,
    p_case_type text,
    p_correlation_id text DEFAULT ''
) RETURNS boolean
LANGUAGE plpgsql
AS $$
DECLARE
    v_pending jsonb;
    v_unclear_count integer;
    p_admin_phone_a text := COALESCE((SELECT value FROM whatsapp_ai.settings WHERE key = 'admin_phone_a'), '');
    p_admin_phone_b text := COALESCE((SELECT value FROM whatsapp_ai.settings WHERE key = 'admin_phone_b'), '');
BEGIN
    SELECT pending_messages INTO v_pending
    FROM whatsapp_ai.batches
    WHERE sender_number = p_sender_number
      AND status = 'processing'
      AND processing_token = p_batch_token
    FOR UPDATE;
    IF NOT FOUND THEN
        RETURN false;
    END IF;

    IF p_case_type = 'unclear' THEN
        INSERT INTO whatsapp_ai.unclear_counts(sender_number, count, expires_at)
        VALUES (p_sender_number, 1, clock_timestamp() + interval '24 hours')
        ON CONFLICT (sender_number) DO UPDATE
        SET count = CASE WHEN whatsapp_ai.unclear_counts.expires_at < clock_timestamp() THEN 1
                         ELSE whatsapp_ai.unclear_counts.count + 1 END,
            expires_at = clock_timestamp() + interval '24 hours'
        RETURNING count INTO v_unclear_count;
        IF v_unclear_count >= 2 THEN
            p_notify_admins := true;
            p_pause_automation := true;
        END IF;
    ELSE
        DELETE FROM whatsapp_ai.unclear_counts WHERE sender_number = p_sender_number;
    END IF;

    IF p_notify_admins AND p_admin_phone_a <> '' AND NOT EXISTS (
        SELECT 1 FROM whatsapp_ai.admin_notifications
        WHERE sender_number = p_sender_number AND channel = 'phone_a'
          AND fingerprint = p_fingerprint AND sent_at > clock_timestamp() - interval '3 minutes'
    ) THEN
        INSERT INTO whatsapp_ai.deliveries(id, batch_token, sender_number, channel, destination, payload)
        VALUES (gen_random_uuid(), p_batch_token, p_sender_number, 'phone_a', p_admin_phone_a,
                jsonb_build_object('number', p_admin_phone_a, 'text', p_admin_message, 'fingerprint', p_fingerprint, 'correlationId', p_correlation_id))
        ON CONFLICT (batch_token, channel) DO NOTHING;
    END IF;
    IF p_notify_admins AND p_admin_phone_b <> '' AND NOT EXISTS (
        SELECT 1 FROM whatsapp_ai.admin_notifications
        WHERE sender_number = p_sender_number AND channel = 'phone_b'
          AND fingerprint = p_fingerprint AND sent_at > clock_timestamp() - interval '3 minutes'
    ) THEN
        INSERT INTO whatsapp_ai.deliveries(id, batch_token, sender_number, channel, destination, payload)
        VALUES (gen_random_uuid(), p_batch_token, p_sender_number, 'phone_b', p_admin_phone_b,
                jsonb_build_object('number', p_admin_phone_b, 'text', p_admin_message, 'fingerprint', p_fingerprint, 'correlationId', p_correlation_id))
        ON CONFLICT (batch_token, channel) DO NOTHING;
    END IF;
    IF p_reply_customer AND p_customer_reply <> '' THEN
        INSERT INTO whatsapp_ai.deliveries(id, batch_token, sender_number, channel, destination, payload)
        VALUES (gen_random_uuid(), p_batch_token, p_sender_number, 'customer', p_sender_number,
                jsonb_build_object('number', p_sender_number, 'text', p_customer_reply, 'correlationId', p_correlation_id))
        ON CONFLICT (batch_token, channel) DO NOTHING;
    END IF;

    UPDATE whatsapp_ai.batches
    SET status = CASE WHEN p_pause_automation THEN 'manual' ELSE 'pending' END,
        processing_messages = '[]'::jsonb,
        processing_token = NULL,
        processing_started_at = NULL,
        ai_attempt_count = 0,
        last_error_code = NULL,
        last_error = NULL,
        first_message_at = CASE WHEN jsonb_array_length(v_pending) > 0 THEN clock_timestamp() ELSE NULL END,
        updated_at = clock_timestamp()
    WHERE sender_number = p_sender_number AND processing_token = p_batch_token;

    IF p_pause_automation THEN
        INSERT INTO whatsapp_ai.system_events(event_type, sender_number_masked, batch_token, details)
        VALUES ('ai_handoff', right(p_sender_number, 4), p_batch_token,
                jsonb_build_object('pauseAutomation', true, 'caseType', p_case_type));
    END IF;

    DELETE FROM whatsapp_ai.batches
    WHERE sender_number = p_sender_number
      AND status = 'pending'
      AND jsonb_array_length(pending_messages) = 0
      AND processing_token IS NULL;
    RETURN true;
END;
$$;

CREATE OR REPLACE FUNCTION whatsapp_ai.cleanup_expired_state() RETURNS jsonb
LANGUAGE plpgsql
AS $$
DECLARE v_messages integer; v_events integer;
BEGIN
    DELETE FROM whatsapp_ai.messages WHERE expires_at < clock_timestamp();
    GET DIAGNOSTICS v_messages = ROW_COUNT;
    DELETE FROM whatsapp_ai.unclear_counts WHERE expires_at < clock_timestamp();
    DELETE FROM whatsapp_ai.system_events WHERE created_at < clock_timestamp() - interval '30 days';
    GET DIAGNOSTICS v_events = ROW_COUNT;
    RETURN jsonb_build_object('messages', v_messages, 'events', v_events,
                              'staleDeliveries', whatsapp_ai.recover_stale_deliveries(),
                              'staleBatches', whatsapp_ai.recover_stale_batches());
END;
$$;

COMMIT;
