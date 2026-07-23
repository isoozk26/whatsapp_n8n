-- 048_new_casetype_priority.sql
-- Updates complete_ai_batch priority logic for new caseTypes:
--   complaint (via non_product + ŞİKAYET): priority 95
--   return_request (via non_product + İADE): priority 90
--   human_request (via non_product + TEMSİLCİ): priority 85
--   handoff: priority 90
--   customer reply: priority 100
--   admin notification (default): priority 50
-- Also updates record_ai_failure to use priority 40.

BEGIN;

-- Priority reference:
--   40  = command / AI failure notification
--   50  = admin notification (default)
--   85  = human_request (TEMSİLCİ)
--   90  = return_request (İADE) / handoff alert
--   95  = complaint (ŞİKAYET)
--  100  = customer reply

CREATE OR REPLACE FUNCTION whatsapp_ai.complete_ai_batch(
    p_sender_number text,
    p_batch_token uuid,
    p_customer_reply text,
    p_admin_message text,
    p_notify_admins boolean,
    p_reply_customer boolean,
    p_pause_automation boolean,
    p_fingerprint text,
    p_case_type text
) RETURNS boolean
LANGUAGE plpgsql
AS $$
DECLARE
    v_pending jsonb;
    v_unclear_count integer;
    v_admin_priority integer;
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

    -- Compute admin notification priority based on caseType and message content.
    -- non_product messages carry sub-type keywords in the admin text.
    IF p_pause_automation THEN
        v_admin_priority := 90;  -- handoff alert
    ELSIF p_case_type = 'non_product' THEN
        v_admin_priority := CASE
            WHEN upper(p_admin_message) LIKE '%ŞİKAYET%'  THEN 95  -- complaint (urgent)
            WHEN upper(p_admin_message) LIKE '%İADE%'     THEN 90  -- return request
            WHEN upper(p_admin_message) LIKE '%TEMSİLCİ%' THEN 85  -- human request
            ELSE 50                                                  -- default admin notification
        END;
    ELSE
        v_admin_priority := 50;  -- regular admin notification
    END IF;

    -- Admin notification delivery
    IF p_notify_admins AND p_admin_phone_a <> '' AND NOT EXISTS (
        SELECT 1 FROM whatsapp_ai.admin_notifications
        WHERE sender_number = p_sender_number AND channel = 'phone_a'
          AND fingerprint = p_fingerprint AND sent_at > clock_timestamp() - interval '3 minutes'
    ) THEN
        INSERT INTO whatsapp_ai.deliveries(id, batch_token, sender_number, channel, destination, payload, priority)
        VALUES (gen_random_uuid(), p_batch_token, p_sender_number, 'phone_a', p_admin_phone_a,
                jsonb_build_object('number', p_admin_phone_a, 'text', p_admin_message, 'fingerprint', p_fingerprint,
                                   '_deliveryType', CASE WHEN p_pause_automation THEN 'handoff_alert' ELSE 'admin_notification' END),
                v_admin_priority)
        ON CONFLICT (batch_token, channel) DO NOTHING;
    END IF;
    IF p_notify_admins AND p_admin_phone_b <> '' AND NOT EXISTS (
        SELECT 1 FROM whatsapp_ai.admin_notifications
        WHERE sender_number = p_sender_number AND channel = 'phone_b'
          AND fingerprint = p_fingerprint AND sent_at > clock_timestamp() - interval '3 minutes'
    ) THEN
        INSERT INTO whatsapp_ai.deliveries(id, batch_token, sender_number, channel, destination, payload, priority)
        VALUES (gen_random_uuid(), p_batch_token, p_sender_number, 'phone_b', p_admin_phone_b,
                jsonb_build_object('number', p_admin_phone_b, 'text', p_admin_message, 'fingerprint', p_fingerprint,
                                   '_deliveryType', CASE WHEN p_pause_automation THEN 'handoff_alert' ELSE 'admin_notification' END),
                v_admin_priority)
        ON CONFLICT (batch_token, channel) DO NOTHING;
    END IF;

    -- Customer reply always gets highest priority
    IF p_reply_customer AND p_customer_reply <> '' THEN
        INSERT INTO whatsapp_ai.deliveries(id, batch_token, sender_number, channel, destination, payload, priority)
        VALUES (gen_random_uuid(), p_batch_token, p_sender_number, 'customer', p_sender_number,
                jsonb_build_object('number', p_sender_number, 'text', p_customer_reply, '_deliveryType', 'customer_reply'),
                100)
        ON CONFLICT (batch_token, channel) DO NOTHING;
    END IF;

    UPDATE whatsapp_ai.batches
    SET status = 'pending',
        processing_messages = '[]'::jsonb,
        processing_token = NULL,
        processing_started_at = NULL,
        ai_attempt_count = 0,
        last_error_code = NULL,
        last_error = NULL,
        first_message_at = CASE WHEN jsonb_array_length(v_pending) > 0 THEN clock_timestamp() ELSE NULL END,
        updated_at = clock_timestamp()
    WHERE sender_number = p_sender_number AND processing_token = p_batch_token;

    DELETE FROM whatsapp_ai.batches
    WHERE sender_number = p_sender_number
      AND status = 'pending'
      AND jsonb_array_length(pending_messages) = 0
      AND processing_token IS NULL;
    RETURN true;
END;
$$;

-- record_ai_failure: priority 40 for command/AI-failure admin notifications
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

    IF v_attempt >= 3 THEN
        UPDATE whatsapp_ai.batches
        SET status = 'pending', pending_messages = v_messages || pending_messages,
            ai_attempt_count = 0, first_message_at = NULL,
            last_error_code = p_error_code, last_error = left(p_error, 2000),
            processing_token = NULL, processing_started_at = NULL, updated_at = clock_timestamp()
        WHERE sender_number = p_sender_number AND processing_token = p_batch_token;
        IF p_admin_phone_a <> '' THEN
            INSERT INTO whatsapp_ai.deliveries(id, batch_token, sender_number, channel, destination, payload, priority)
            VALUES (gen_random_uuid(), p_batch_token, p_sender_number, 'phone_a', p_admin_phone_a,
                    jsonb_build_object('number', p_admin_phone_a, 'text',
                        'AI islemi 3 kez basarisiz oldu. Musteri manuel incelemeye alindi: ' || p_sender_number,
                        '_deliveryType', 'command_notification'),
                    40)
            ON CONFLICT (batch_token, channel) DO NOTHING;
        END IF;
        IF p_admin_phone_b <> '' THEN
            INSERT INTO whatsapp_ai.deliveries(id, batch_token, sender_number, channel, destination, payload, priority)
            VALUES (gen_random_uuid(), p_batch_token, p_sender_number, 'phone_b', p_admin_phone_b,
                    jsonb_build_object('number', p_admin_phone_b, 'text',
                        'AI islemi 3 kez basarisiz oldu. Musteri manuel incelemeye alindi: ' || p_sender_number,
                        '_deliveryType', 'command_notification'),
                    40)
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
            WHEN 1 THEN interval '30 seconds' ELSE interval '2 minutes' END,
        last_error_code = p_error_code,
        last_error = left(p_error, 2000),
        first_message_at = clock_timestamp(),
        updated_at = clock_timestamp()
    WHERE sender_number = p_sender_number AND processing_token = p_batch_token;
    RETURN 'retry';
END;
$$;

COMMIT;
