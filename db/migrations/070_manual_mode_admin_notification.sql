-- 070: Send administrator notification when a customer in manual mode sends a new message.
-- Keeps the live 8-argument ingest_message signature, ensures idempotency, and keeps customer bot silent.

CREATE OR REPLACE FUNCTION whatsapp_ai.ingest_message(
    p_message_id text,
    p_sender_number text,
    p_sender_name text,
    p_message jsonb,
    p_command text DEFAULT NULL,
    p_webhook_token text DEFAULT NULL,
    p_auth_source text DEFAULT 'query',
    p_next_ai_attempt_at timestamptz DEFAULT NULL
) RETURNS TABLE(action text, pending_count integer, reason text)
LANGUAGE plpgsql
AS $$
DECLARE
    v_batch whatsapp_ai.batches%ROWTYPE;
    v_admin_phone_a text := COALESCE((SELECT value FROM whatsapp_ai.settings WHERE key = 'admin_phone_a'), '');
    v_admin_phone_b text := COALESCE((SELECT value FROM whatsapp_ai.settings WHERE key = 'admin_phone_b'), '');
    v_fingerprint text;
    v_msg_text text;
    v_customer_text text;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM whatsapp_ai.settings
        WHERE key = 'webhook_token' AND value <> '' AND value = COALESCE(p_webhook_token, '')
          AND (p_auth_source = 'header' OR COALESCE((SELECT value FROM whatsapp_ai.settings
              WHERE key = 'webhook_legacy_query_enabled'), 'false') = 'true')
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
        SET enabled = true, last_human_activity_at = clock_timestamp(), updated_at = clock_timestamp();
        UPDATE whatsapp_ai.batches SET status = 'manual', updated_at = clock_timestamp()
        WHERE sender_number = p_sender_number;
        v_fingerprint := 'cmd:pause:' || p_sender_number || ':' || extract(epoch from clock_timestamp())::text;
        v_msg_text := E'\U0001f512 SİSTEM MANUEL MODA GEÇTİ\n\U0001f464 Müşteri: ' || p_sender_name || ' (' || p_sender_number || E')\n\u26a1 Otomatik yanıtlar durduruldu\n\U0001f4ac Manuel yanıt bekleniyor';
        IF v_admin_phone_a <> '' AND v_admin_phone_a <> p_sender_number THEN
            INSERT INTO whatsapp_ai.deliveries(id, batch_token, sender_number, channel, destination, payload)
            VALUES (gen_random_uuid(), gen_random_uuid(), p_sender_number, 'phone_a', v_admin_phone_a, jsonb_build_object('number', v_admin_phone_a, 'text', v_msg_text, 'fingerprint', v_fingerprint))
            ON CONFLICT (batch_token, channel) DO NOTHING;
        END IF;
        IF v_admin_phone_b <> '' AND v_admin_phone_b <> p_sender_number THEN
            INSERT INTO whatsapp_ai.deliveries(id, batch_token, sender_number, channel, destination, payload)
            VALUES (gen_random_uuid(), gen_random_uuid(), p_sender_number, 'phone_b', v_admin_phone_b, jsonb_build_object('number', v_admin_phone_b, 'text', v_msg_text, 'fingerprint', v_fingerprint))
            ON CONFLICT (batch_token, channel) DO NOTHING;
        END IF;
        INSERT INTO whatsapp_ai.system_events(event_type, sender_number_masked, details)
        VALUES ('manual_pause', right(p_sender_number, 4), jsonb_build_object('source', 'command', 'mode', 'manual', 'authSource', p_auth_source));
        RETURN QUERY SELECT 'command'::text, 0, 'paused'::text;
        RETURN;
    ELSIF p_command = 'resume' THEN
        DELETE FROM whatsapp_ai.manual_modes WHERE sender_number = p_sender_number;
        UPDATE whatsapp_ai.batches
        SET status = CASE WHEN jsonb_array_length(pending_messages) > 0 THEN 'pending' ELSE status END,
            updated_at = clock_timestamp()
        WHERE sender_number = p_sender_number AND status = 'manual';
        v_fingerprint := 'cmd:resume:' || p_sender_number || ':' || extract(epoch from clock_timestamp())::text;
        v_msg_text := E'\U0001f513 SİSTEM OTOMATİK MODA GEÇTİ\n\U0001f464 Müşteri: ' || p_sender_name || ' (' || p_sender_number || E')\n\u26a1 AI yanıtları yeniden başladı\n\U0001f916 Otomatik mod aktif';
        IF v_admin_phone_a <> '' AND v_admin_phone_a <> p_sender_number THEN
            INSERT INTO whatsapp_ai.deliveries(id, batch_token, sender_number, channel, destination, payload)
            VALUES (gen_random_uuid(), gen_random_uuid(), p_sender_number, 'phone_a', v_admin_phone_a, jsonb_build_object('number', v_admin_phone_a, 'text', v_msg_text, 'fingerprint', v_fingerprint))
            ON CONFLICT (batch_token, channel) DO NOTHING;
        END IF;
        IF v_admin_phone_b <> '' AND v_admin_phone_b <> p_sender_number THEN
            INSERT INTO whatsapp_ai.deliveries(id, batch_token, sender_number, channel, destination, payload)
            VALUES (gen_random_uuid(), gen_random_uuid(), p_sender_number, 'phone_b', v_admin_phone_b, jsonb_build_object('number', v_admin_phone_b, 'text', v_msg_text, 'fingerprint', v_fingerprint))
            ON CONFLICT (batch_token, channel) DO NOTHING;
        END IF;
        INSERT INTO whatsapp_ai.system_events(event_type, sender_number_masked, details)
        VALUES ('manual_resume', right(p_sender_number, 4), jsonb_build_object('source', 'command', 'mode', 'automatic', 'authSource', p_auth_source));
        RETURN QUERY SELECT 'command'::text, 0, 'resumed'::text;
        RETURN;
    ELSIF p_command = 'check_mode' THEN
        v_fingerprint := 'cmd:check:' || p_sender_number || ':' || extract(epoch from clock_timestamp())::text;
        v_msg_text := E'\U0001f4ca SİSTEM DURUMU\n\U0001f464 Müşteri: ' || p_sender_name || E'\n' || CASE WHEN EXISTS (SELECT 1 FROM whatsapp_ai.manual_modes WHERE sender_number = p_sender_number AND enabled) THEN E'\U0001f916 Mod: MANUEL\n\u26a1 Durum: Manuel mod aktif' ELSE E'\U0001f916 Mod: OTOMATİK\n\u26a1 Durum: Aktif' END;
        IF v_admin_phone_a <> '' AND v_admin_phone_a <> p_sender_number THEN
            INSERT INTO whatsapp_ai.deliveries(id, batch_token, sender_number, channel, destination, payload) VALUES (gen_random_uuid(), gen_random_uuid(), p_sender_number, 'phone_a', v_admin_phone_a, jsonb_build_object('number', v_admin_phone_a, 'text', v_msg_text, 'fingerprint', v_fingerprint)) ON CONFLICT (batch_token, channel) DO NOTHING;
        END IF;
        IF v_admin_phone_b <> '' AND v_admin_phone_b <> p_sender_number THEN
            INSERT INTO whatsapp_ai.deliveries(id, batch_token, sender_number, channel, destination, payload) VALUES (gen_random_uuid(), gen_random_uuid(), p_sender_number, 'phone_b', v_admin_phone_b, jsonb_build_object('number', v_admin_phone_b, 'text', v_msg_text, 'fingerprint', v_fingerprint)) ON CONFLICT (batch_token, channel) DO NOTHING;
        END IF;
        INSERT INTO whatsapp_ai.system_events(event_type, sender_number_masked, details) VALUES ('manual_check', right(p_sender_number, 4), jsonb_build_object('source', 'command', 'authSource', p_auth_source));
        RETURN QUERY SELECT 'command'::text, 0, 'checked'::text;
        RETURN;
    END IF;

    IF EXISTS (
        SELECT 1 FROM whatsapp_ai.manual_modes
        WHERE sender_number = p_sender_number AND enabled
    ) THEN
        UPDATE whatsapp_ai.manual_modes
        SET last_human_activity_at = clock_timestamp(), updated_at = clock_timestamp()
        WHERE sender_number = p_sender_number;

        v_customer_text := COALESCE(p_message->>'text', p_message->>'conversation', '[Medya / Görsel]');
        v_fingerprint := 'manual_inbound:' || p_message_id;
        v_msg_text := E'\U0001f4e9 MANUEL MOD MÜŞTERİ MESAJI\n\U0001f464 Müşteri: ' || p_sender_name || ' (' || p_sender_number || E')\n\U0001f4ac Mesaj: "' || v_customer_text || E'"';

        IF v_admin_phone_a <> '' AND v_admin_phone_a <> p_sender_number THEN
            INSERT INTO whatsapp_ai.deliveries(id, batch_token, sender_number, channel, destination, payload)
            VALUES (gen_random_uuid(), gen_random_uuid(), p_sender_number, 'phone_a', v_admin_phone_a, jsonb_build_object('number', v_admin_phone_a, 'text', v_msg_text, 'fingerprint', v_fingerprint))
            ON CONFLICT (batch_token, channel) DO NOTHING;
        END IF;
        IF v_admin_phone_b <> '' AND v_admin_phone_b <> p_sender_number THEN
            INSERT INTO whatsapp_ai.deliveries(id, batch_token, sender_number, channel, destination, payload)
            VALUES (gen_random_uuid(), gen_random_uuid(), p_sender_number, 'phone_b', v_admin_phone_b, jsonb_build_object('number', v_admin_phone_b, 'text', v_msg_text, 'fingerprint', v_fingerprint))
            ON CONFLICT (batch_token, channel) DO NOTHING;
        END IF;

        RETURN QUERY SELECT 'ignore'::text, 0, 'manual_mode'::text;
        RETURN;
    END IF;

    INSERT INTO whatsapp_ai.batches(
        sender_number, sender_name, pending_messages, first_message_at, last_message_at, next_ai_attempt_at
    ) VALUES (
        p_sender_number, p_sender_name, jsonb_build_array(p_message), clock_timestamp(), clock_timestamp(), p_next_ai_attempt_at
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
        next_ai_attempt_at = CASE
            WHEN p_next_ai_attempt_at IS NULL THEN whatsapp_ai.batches.next_ai_attempt_at
            WHEN whatsapp_ai.batches.next_ai_attempt_at IS NULL THEN p_next_ai_attempt_at
            ELSE LEAST(whatsapp_ai.batches.next_ai_attempt_at, p_next_ai_attempt_at)
        END,
        status = CASE WHEN whatsapp_ai.batches.status = 'manual' THEN 'manual'
                      ELSE whatsapp_ai.batches.status END,
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
