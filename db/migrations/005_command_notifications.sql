-- Migration 005: Command notifications for ++/--/??
-- ++ → "SİSTEM MANUEL" bildirimi
-- -- → "SİSTEM OTOMATİK" bildirimi
-- ?? → Mevcut modu kontrol edip bildirim

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

    -- ++ komutu: SİSTEM MANUEL
    IF p_command = 'pause' THEN
        INSERT INTO whatsapp_ai.manual_modes(sender_number, enabled)
        VALUES (p_sender_number, true)
        ON CONFLICT (sender_number) DO UPDATE
        SET enabled = true, last_human_activity_at = clock_timestamp(), updated_at = clock_timestamp();
        UPDATE whatsapp_ai.batches SET status = 'manual', updated_at = clock_timestamp()
        WHERE sender_number = p_sender_number;

        -- Yöneticilere "SİSTEM MANUEL" bildirimi gönder
        v_fingerprint := 'cmd:pause:' || p_sender_number || ':' || extract(epoch from clock_timestamp())::text;
        IF v_admin_phone_a <> '' THEN
            INSERT INTO whatsapp_ai.deliveries(id, batch_token, sender_number, channel, destination, payload)
            VALUES (gen_random_uuid(), gen_random_uuid(), p_sender_number, 'phone_a', v_admin_phone_a,
                    jsonb_build_object('number', v_admin_phone_a, 'text', '🔒 SİSTEM MANUEL MODA GEÇTİ\n👤 ' || p_sender_name || ' (' || p_sender_number || ')\n⚡ Otomatik yanıtlar durduruldu\n💬 Manuel yanıt bekleniyor', 'fingerprint', v_fingerprint))
            ON CONFLICT (batch_token, channel) DO NOTHING;
        END IF;
        IF v_admin_phone_b <> '' THEN
            INSERT INTO whatsapp_ai.deliveries(id, batch_token, sender_number, channel, destination, payload)
            VALUES (gen_random_uuid(), gen_random_uuid(), p_sender_number, 'phone_b', v_admin_phone_b,
                    jsonb_build_object('number', v_admin_phone_b, 'text', '🔒 SİSTEM MANUEL MODA GEÇTİ\n👤 ' || p_sender_name || ' (' || p_sender_number || ')\n⚡ Otomatik yanıtlar durduruldu\n💬 Manuel yanıt bekleniyor', 'fingerprint', v_fingerprint))
            ON CONFLICT (batch_token, channel) DO NOTHING;
        END IF;

        RETURN QUERY SELECT 'command'::text, 0, 'paused'::text;
        RETURN;

    -- -- komutu: SİSTEM OTOMATİK
    ELSIF p_command = 'resume' THEN
        DELETE FROM whatsapp_ai.manual_modes WHERE sender_number = p_sender_number;
        UPDATE whatsapp_ai.batches
        SET status = CASE WHEN jsonb_array_length(pending_messages) > 0 THEN 'pending' ELSE status END,
            updated_at = clock_timestamp()
        WHERE sender_number = p_sender_number AND status = 'manual';

        -- Yöneticilere "SİSTEM OTOMATİK" bildirimi gönder
        v_fingerprint := 'cmd:resume:' || p_sender_number || ':' || extract(epoch from clock_timestamp())::text;
        IF v_admin_phone_a <> '' THEN
            INSERT INTO whatsapp_ai.deliveries(id, batch_token, sender_number, channel, destination, payload)
            VALUES (gen_random_uuid(), gen_random_uuid(), p_sender_number, 'phone_a', v_admin_phone_a,
                    jsonb_build_object('number', v_admin_phone_a, 'text', '🔓 SİSTEM OTOMATİK MODA GEÇTİ\n👤 ' || p_sender_name || ' (' || p_sender_number || ')\n⚡ AI yanıtları yeniden başladı\n🤖 Otomatik mod aktif', 'fingerprint', v_fingerprint))
            ON CONFLICT (batch_token, channel) DO NOTHING;
        END IF;
        IF v_admin_phone_b <> '' THEN
            INSERT INTO whatsapp_ai.deliveries(id, batch_token, sender_number, channel, destination, payload)
            VALUES (gen_random_uuid(), gen_random_uuid(), p_sender_number, 'phone_b', v_admin_phone_b,
                    jsonb_build_object('number', v_admin_phone_b, 'text', '🔓 SİSTEM OTOMATİK MODA GEÇTİ\n👤 ' || p_sender_name || ' (' || p_sender_number || ')\n⚡ AI yanıtları yeniden başladı\n🤖 Otomatik mod aktif', 'fingerprint', v_fingerprint))
            ON CONFLICT (batch_token, channel) DO NOTHING;
        END IF;

        RETURN QUERY SELECT 'command'::text, 0, 'resumed'::text;
        RETURN;

    -- ?? komutu: Mevcut modu kontrol et
    ELSIF p_command = 'check_mode' THEN
        SELECT EXISTS(SELECT 1 FROM whatsapp_ai.manual_modes WHERE sender_number = p_sender_number AND enabled) INTO v_mode_status;

        v_fingerprint := 'cmd:check:' || p_sender_number || ':' || extract(epoch from clock_timestamp())::text;
        IF v_admin_phone_a <> '' THEN
            INSERT INTO whatsapp_ai.deliveries(id, batch_token, sender_number, channel, destination, payload)
            VALUES (gen_random_uuid(), gen_random_uuid(), p_sender_number, 'phone_a', v_admin_phone_a,
                    jsonb_build_object('number', v_admin_phone_a, 'text',
                        CASE WHEN v_mode_status THEN '📊 SİSTEM DURUMU\n👤 ' || p_sender_name || ' (' || p_sender_number || ')\n🤖 Mod: MANUEL\n⚡ Durum: Manuel mod aktif' ELSE '📊 SİSTEM DURUMU\n👤 ' || p_sender_name || ' (' || p_sender_number || ')\n🤖 Mod: OTOMATİK\n⚡ Durum: Aktif' END,
                    'fingerprint', v_fingerprint))
            ON CONFLICT (batch_token, channel) DO NOTHING;
        END IF;
        IF v_admin_phone_b <> '' THEN
            INSERT INTO whatsapp_ai.deliveries(id, batch_token, sender_number, channel, destination, payload)
            VALUES (gen_random_uuid(), gen_random_uuid(), p_sender_number, 'phone_b', v_admin_phone_b,
                    jsonb_build_object('number', v_admin_phone_b, 'text',
                        CASE WHEN v_mode_status THEN '📊 SİSTEM DURUMU\n👤 ' || p_sender_name || ' (' || p_sender_number || ')\n🤖 Mod: MANUEL\n⚡ Durum: Manuel mod aktif' ELSE '📊 SİSTEM DURUMU\n👤 ' || p_sender_name || ' (' || p_sender_number || ')\n🤖 Mod: OTOMATİK\n⚡ Durum: Aktif' END,
                    'fingerprint', v_fingerprint))
            ON CONFLICT (batch_token, channel) DO NOTHING;
        END IF;

        RETURN QUERY SELECT 'command'::text, 0, CASE WHEN v_mode_status THEN 'manual' ELSE 'automatic' END::text;
        RETURN;
    END IF;

    IF EXISTS (
        SELECT 1 FROM whatsapp_ai.manual_modes
        WHERE sender_number = p_sender_number AND enabled
    ) THEN
        UPDATE whatsapp_ai.manual_modes
        SET last_human_activity_at = clock_timestamp(), updated_at = clock_timestamp()
        WHERE sender_number = p_sender_number;
        RETURN QUERY SELECT 'ignore'::text, 0, 'manual_mode'::text;
        RETURN;
    END IF;

    INSERT INTO whatsapp_ai.batches(
        sender_number, sender_name, pending_messages, first_message_at, last_message_at
    ) VALUES (
        p_sender_number, p_sender_name, jsonb_build_array(p_message), clock_timestamp(), clock_timestamp()
    )
    ON CONFLICT (sender_number) DO UPDATE
    SET sender_name = EXCLUDED.sender_name,
        pending_messages = CASE
            WHEN jsonb_array_length(whatsapp_ai.batches.pending_messages) >= 30
                THEN whatsapp_ai.batches.pending_messages
            ELSE whatsapp_ai.batches.pending_messages || EXCLUDED.pending_messages
        END,
        last_message_at = clock_timestamp(),
        updated_at = clock_timestamp()
    RETURNING * INTO v_batch;

    UPDATE whatsapp_ai.batches SET status = 'pending', updated_at = clock_timestamp()
    WHERE sender_number = p_sender_number AND status = 'new';

    RETURN QUERY SELECT 'queued'::text,
        (SELECT count(*)::integer FROM whatsapp_ai.batches
         WHERE sender_number = p_sender_number AND status IN ('pending', 'new')),
        NULL::text;
    RETURN;
END;
$$;
