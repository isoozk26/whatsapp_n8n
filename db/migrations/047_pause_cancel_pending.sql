CREATE OR REPLACE FUNCTION whatsapp_ai.ingest_message(
    p_message_id text,
    p_sender_number text,
    p_sender_name text,
    p_message jsonb,
    p_command text DEFAULT NULL,
    p_webhook_token text DEFAULT NULL,
    p_auth_source text DEFAULT 'query'
) RETURNS TABLE(action text, pending_count integer, reason text)
LANGUAGE plpgsql
AS $$
DECLARE
    v_batch whatsapp_ai.batches%ROWTYPE;
    v_admin_phone_a text := COALESCE((SELECT value FROM whatsapp_ai.settings WHERE key = 'admin_phone_a'), '');
    v_admin_phone_b text := COALESCE((SELECT value FROM whatsapp_ai.settings WHERE key = 'admin_phone_b'), '');
    v_mode_status boolean;
    v_fingerprint text;
    v_msg_text text;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM whatsapp_ai.settings
        WHERE key = 'webhook_token'
          AND value <> ''
          AND value = COALESCE(p_webhook_token, '')
          AND (
            p_auth_source = 'header'
            OR COALESCE((SELECT value FROM whatsapp_ai.settings WHERE key = 'webhook_legacy_query_enabled'), 'false') = 'true'
          )
    ) THEN
        INSERT INTO whatsapp_ai.system_events(event_type, details)
        VALUES ('webhook_auth_failure', jsonb_build_object('authSource', COALESCE(p_auth_source, 'unknown')));
        RETURN QUERY SELECT 'unauthorized'::text, 0, 'invalid_token'::text;
        RETURN;
    END IF;

    IF p_message_id IS NULL OR p_message_id = '' OR p_sender_number IS NULL OR p_sender_number = '' THEN
        RETURN QUERY SELECT 'ignore'::text, 0, 'invalid_payload'::text;
        RETURN;
    END IF;

    INSERT INTO whatsapp_ai.messages(message_id, sender_number, payload)
    VALUES (p_message_id, p_sender_number, p_message)
    ON CONFLICT (message_id) DO NOTHING;

    IF NOT FOUND THEN
        RETURN QUERY SELECT 'ignore'::text, 0, 'duplicate_message'::text;
        RETURN;
    END IF;

    IF p_command = 'pause' THEN
        INSERT INTO whatsapp_ai.manual_modes(sender_number, enabled)
        VALUES (p_sender_number, true)
        ON CONFLICT (sender_number) DO UPDATE
        SET enabled = true,
            last_human_activity_at = clock_timestamp(),
            updated_at = clock_timestamp();

        -- Race condition fix: Cancel any processing batches first
        UPDATE whatsapp_ai.batches
        SET status = 'manual',
            pending_messages = processing_messages || pending_messages,
            processing_messages = '[]'::jsonb,
            processing_token = NULL,
            processing_started_at = NULL,
            updated_at = clock_timestamp()
        WHERE sender_number = p_sender_number
          AND status = 'processing';

        -- Also set any pending batches to manual
        UPDATE whatsapp_ai.batches
        SET status = 'manual', updated_at = clock_timestamp()
        WHERE sender_number = p_sender_number
          AND status IN ('pending', 'processing');

        v_fingerprint := 'cmd:pause:' || p_sender_number || ':' || extract(epoch FROM clock_timestamp())::text;
        v_msg_text := E'\U0001f512 SİSTEM MANUEL MODA GEÇTİ\n\U0001f464 Müşteri: ' || p_sender_name || ' (' || p_sender_number || E')\n\u26a1 Otomatik AI yanıtları durduruldu\n\U0001f4ac Temsilci yanıtı bekleniyor';

        IF v_admin_phone_a <> '' AND v_admin_phone_a <> p_sender_number THEN
            INSERT INTO whatsapp_ai.deliveries(id, batch_token, sender_number, channel, destination, payload)
            VALUES (gen_random_uuid(), gen_random_uuid(), p_sender_number, 'phone_a', v_admin_phone_a, jsonb_build_object('number', v_admin_phone_a, 'text', v_msg_text, 'fingerprint', v_fingerprint)) ON CONFLICT (batch_token, channel) DO NOTHING;
        END IF;

        IF v_admin_phone_b <> '' AND v_admin_phone_b <> p_sender_number THEN
            INSERT INTO whatsapp_ai.deliveries(id, batch_token, sender_number, channel, destination, payload)
            VALUES (gen_random_uuid(), gen_random_uuid(), p_sender_number, 'phone_b', v_admin_phone_b, jsonb_build_object('number', v_admin_phone_b, 'text', v_msg_text, 'fingerprint', v_fingerprint)) ON CONFLICT (batch_token, channel) DO NOTHING;
        END IF;

        RETURN QUERY SELECT 'command'::text, 0, 'paused'::text;
        RETURN;

    ELSIF p_command = 'resume' THEN
        DELETE FROM whatsapp_ai.manual_modes WHERE sender_number = p_sender_number;

        UPDATE whatsapp_ai.batches
        SET status = CASE WHEN jsonb_array_length(pending_messages) > 0 THEN 'pending' ELSE status END,
            updated_at = clock_timestamp()
        WHERE sender_number = p_sender_number
          AND status = 'manual';

        v_fingerprint := 'cmd:resume:' || p_sender_number || ':' || extract(epoch FROM clock_timestamp())::text;
        v_msg_text := E'\U0001f513 SİSTEM OTOMATİK MODA GEÇTİ\n\U0001f464 Müşteri: ' || p_sender_name || ' (' || p_sender_number || E')\n\u26a1 Otomatik AI yanıtları aktif edildi';

        IF v_admin_phone_a <> '' AND v_admin_phone_a <> p_sender_number THEN
            INSERT INTO whatsapp_ai.deliveries(id, batch_token, sender_number, channel, destination, payload)
            VALUES (gen_random_uuid(), gen_random_uuid(), p_sender_number, 'phone_a', v_admin_phone_a, jsonb_build_object('number', v_admin_phone_a, 'text', v_msg_text, 'fingerprint', v_fingerprint)) ON CONFLICT (batch_token, channel) DO NOTHING;
        END IF;

        IF v_admin_phone_b <> '' AND v_admin_phone_b <> p_sender_number THEN
            INSERT INTO whatsapp_ai.deliveries(id, batch_token, sender_number, channel, destination, payload)
            VALUES (gen_random_uuid(), gen_random_uuid(), p_sender_number, 'phone_b', v_admin_phone_b, jsonb_build_object('number', v_admin_phone_b, 'text', v_msg_text, 'fingerprint', v_fingerprint)) ON CONFLICT (batch_token, channel) DO NOTHING;
        END IF;

        RETURN QUERY SELECT 'command'::text, 0, 'resumed'::text;
        RETURN;

    ELSIF p_command = 'check_mode' THEN
        SELECT EXISTS(
            SELECT 1
            FROM whatsapp_ai.manual_modes
            WHERE sender_number = p_sender_number
              AND enabled
        ) INTO v_mode_status;

        v_fingerprint := 'cmd:check:' || p_sender_number || ':' || extract(epoch FROM clock_timestamp())::text;

        IF v_mode_status THEN
            v_msg_text := E'\U0001f4ca MÜŞTERİ MODU: MANUEL\n\U0001f464 Müşteri: ' || p_sender_name || ' (' || p_sender_number || E')\n\U0001f534 AI yanıtları durduruldu\n\U0001f7e2 Temsilci müdahalesi bekleniyor';
        ELSE
            v_msg_text := E'\U0001f4ca MÜŞTERİ MODU: OTOMATİK\n\U0001f464 Müşteri: ' || p_sender_name || ' (' || p_sender_number || E')\n\U0001f7e2 AI yanıtları aktif';
        END IF;

        IF v_admin_phone_a <> '' AND v_admin_phone_a <> p_sender_number THEN
            INSERT INTO whatsapp_ai.deliveries(id, batch_token, sender_number, channel, destination, payload)
            VALUES (gen_random_uuid(), gen_random_uuid(), p_sender_number, 'phone_a', v_admin_phone_a, jsonb_build_object('number', v_admin_phone_a, 'text', v_msg_text, 'fingerprint', v_fingerprint)) ON CONFLICT (batch_token, channel) DO NOTHING;
        END IF;

        IF v_admin_phone_b <> '' AND v_admin_phone_b <> p_sender_number THEN
            INSERT INTO whatsapp_ai.deliveries(id, batch_token, sender_number, channel, destination, payload)
            VALUES (gen_random_uuid(), gen_random_uuid(), p_sender_number, 'phone_b', v_admin_phone_b, jsonb_build_object('number', v_admin_phone_b, 'text', v_msg_text, 'fingerprint', v_fingerprint)) ON CONFLICT (batch_token, channel) DO NOTHING;
        END IF;

        RETURN QUERY SELECT 'command'::text, 0, CASE WHEN v_mode_status THEN 'manual' ELSE 'automatic' END::text;
        RETURN;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM whatsapp_ai.manual_modes
        WHERE sender_number = p_sender_number
          AND enabled
    ) THEN
        UPDATE whatsapp_ai.manual_modes
        SET last_human_activity_at = clock_timestamp(),
            updated_at = clock_timestamp()
        WHERE sender_number = p_sender_number;

        RETURN QUERY SELECT 'ignore'::text, 0, 'manual_mode'::text;
        RETURN;
    END IF;

    INSERT INTO whatsapp_ai.batches(
        sender_number,
        sender_name,
        pending_messages,
        first_message_at,
        last_message_at
    ) VALUES (
        p_sender_number,
        p_sender_name,
        jsonb_build_array(p_message),
        clock_timestamp(),
        clock_timestamp()
    )
    ON CONFLICT (sender_number) DO UPDATE
    SET sender_name = EXCLUDED.sender_name,
        pending_messages = CASE
            WHEN jsonb_array_length(whatsapp_ai.batches.pending_messages) >= 30
                THEN whatsapp_ai.batches.pending_messages
            ELSE whatsapp_ai.batches.pending_messages || EXCLUDED.pending_messages
        END,
        first_message_at = COALESCE(whatsapp_ai.batches.first_message_at, clock_timestamp()),
        last_message_at = clock_timestamp(),
        status = CASE
            WHEN whatsapp_ai.batches.status = 'manual' THEN 'manual'
            ELSE whatsapp_ai.batches.status
        END,
        updated_at = clock_timestamp()
    RETURNING * INTO v_batch;

    IF jsonb_array_length(v_batch.pending_messages) >= 30 THEN
        INSERT INTO whatsapp_ai.system_events(event_type, sender_number_masked, details)
        VALUES ('spam_limit', right(p_sender_number, 4), jsonb_build_object('pendingCount', 30));
        RETURN QUERY SELECT 'rate_limited'::text, 30, 'message_limit'::text;
    ELSE
        RETURN QUERY SELECT 'queued'::text, jsonb_array_length(v_batch.pending_messages), NULL::text;
    END IF;
END;
$$;