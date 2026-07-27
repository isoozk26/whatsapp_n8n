BEGIN;

CREATE SCHEMA IF NOT EXISTS whatsapp_ai;

CREATE TABLE IF NOT EXISTS whatsapp_ai.settings (
    key text PRIMARY KEY,
    value text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

INSERT INTO whatsapp_ai.settings(key, value)
VALUES ('webhook_legacy_query_enabled', 'true')
ON CONFLICT (key) DO NOTHING;

UPDATE whatsapp_ai.settings
SET value = chr(304) || 'smail ' || chr(214) || 'zkaracan',
    updated_at = clock_timestamp()
WHERE key = 'assignee_name'
  AND value IN ('?smail ?zkaracan', 'Ä°smail Ã–zkaracan');

CREATE TABLE IF NOT EXISTS whatsapp_ai.batches (
    sender_number text PRIMARY KEY,
    sender_name text NOT NULL,
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'manual')),
    pending_messages jsonb NOT NULL DEFAULT '[]'::jsonb,
    processing_messages jsonb NOT NULL DEFAULT '[]'::jsonb,
    first_message_at timestamptz,
    last_message_at timestamptz,
    processing_started_at timestamptz,
    processing_token uuid,
    ai_attempt_count integer NOT NULL DEFAULT 0,
    next_ai_attempt_at timestamptz,
    last_error_code text,
    last_error text,
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS whatsapp_ai.messages (
    message_id text PRIMARY KEY,
    sender_number text NOT NULL,
    payload jsonb NOT NULL,
    received_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    expires_at timestamptz NOT NULL DEFAULT clock_timestamp() + interval '24 hours'
);
CREATE INDEX IF NOT EXISTS messages_expires_idx ON whatsapp_ai.messages (expires_at);

CREATE TABLE IF NOT EXISTS whatsapp_ai.manual_modes (
    sender_number text PRIMARY KEY,
    enabled boolean NOT NULL DEFAULT true,
    last_human_activity_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS whatsapp_ai.admin_notifications (
    sender_number text NOT NULL,
    channel text NOT NULL CHECK (channel IN ('phone_a', 'phone_b')),
    fingerprint text NOT NULL,
    sent_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (sender_number, channel)
);

CREATE TABLE IF NOT EXISTS whatsapp_ai.unclear_counts (
    sender_number text PRIMARY KEY,
    count integer NOT NULL DEFAULT 0,
    expires_at timestamptz NOT NULL DEFAULT clock_timestamp() + interval '24 hours'
);

CREATE TABLE IF NOT EXISTS whatsapp_ai.deliveries (
    id uuid PRIMARY KEY,
    batch_token uuid NOT NULL,
    sender_number text NOT NULL,
    channel text NOT NULL CHECK (channel IN ('phone_a', 'phone_b', 'customer')),
    destination text NOT NULL,
    payload jsonb NOT NULL,
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'sending', 'sent', 'failed', 'dead')),
    attempt_count integer NOT NULL DEFAULT 0,
    next_attempt_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    claimed_at timestamptz,
    provider_message_id text,
    last_error text,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (batch_token, channel)
);
CREATE INDEX IF NOT EXISTS deliveries_ready_idx
    ON whatsapp_ai.deliveries (status, next_attempt_at, created_at);

CREATE TABLE IF NOT EXISTS whatsapp_ai.system_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_type text NOT NULL,
    sender_number_masked text,
    batch_token uuid,
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX IF NOT EXISTS system_events_created_idx ON whatsapp_ai.system_events (created_at);

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
        RETURN QUERY SELECT 'command'::text, 0, 'paused'::text;
        RETURN;
    ELSIF p_command = 'resume' THEN
        DELETE FROM whatsapp_ai.manual_modes WHERE sender_number = p_sender_number;
        UPDATE whatsapp_ai.batches
        SET status = CASE WHEN jsonb_array_length(pending_messages) > 0 THEN 'pending' ELSE status END,
            updated_at = clock_timestamp()
        WHERE sender_number = p_sender_number AND status = 'manual';
        RETURN QUERY SELECT 'command'::text, 0, 'resumed'::text;
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

DROP FUNCTION IF EXISTS whatsapp_ai.claim_ready_batches(integer);
CREATE FUNCTION whatsapp_ai.claim_ready_batches(p_limit integer DEFAULT 10)
RETURNS TABLE(
    sender_number text, sender_name text, batch_token uuid,
    messages jsonb, message_count integer, all_messages_text text,
    ai_attempt_count integer, assignee_name text
)
LANGUAGE sql
AS $$
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
       COALESCE((SELECT value FROM whatsapp_ai.settings WHERE key = 'assignee_name'), 'İsmail Özkaracan')
FROM claimed c;
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
    p_case_type text
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
                jsonb_build_object('number', p_admin_phone_a, 'text', p_admin_message, 'fingerprint', p_fingerprint))
        ON CONFLICT (batch_token, channel) DO NOTHING;
    END IF;
    IF p_notify_admins AND p_admin_phone_b <> '' AND NOT EXISTS (
        SELECT 1 FROM whatsapp_ai.admin_notifications
        WHERE sender_number = p_sender_number AND channel = 'phone_b'
          AND fingerprint = p_fingerprint AND sent_at > clock_timestamp() - interval '3 minutes'
    ) THEN
        INSERT INTO whatsapp_ai.deliveries(id, batch_token, sender_number, channel, destination, payload)
        VALUES (gen_random_uuid(), p_batch_token, p_sender_number, 'phone_b', p_admin_phone_b,
                jsonb_build_object('number', p_admin_phone_b, 'text', p_admin_message, 'fingerprint', p_fingerprint))
        ON CONFLICT (batch_token, channel) DO NOTHING;
    END IF;
    IF p_reply_customer AND p_customer_reply <> '' THEN
        INSERT INTO whatsapp_ai.deliveries(id, batch_token, sender_number, channel, destination, payload)
        VALUES (gen_random_uuid(), p_batch_token, p_sender_number, 'customer', p_sender_number,
                jsonb_build_object('number', p_sender_number, 'text', p_customer_reply))
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
            INSERT INTO whatsapp_ai.deliveries(id, batch_token, sender_number, channel, destination, payload)
            VALUES (gen_random_uuid(), p_batch_token, p_sender_number, 'phone_a', p_admin_phone_a,
                    jsonb_build_object('number', p_admin_phone_a, 'text', 'AI işlemi 3 kez başarısız oldu. Müşteri manuel incelemeye alındı: ' || p_sender_number))
            ON CONFLICT (batch_token, channel) DO NOTHING;
        END IF;
        IF p_admin_phone_b <> '' THEN
            INSERT INTO whatsapp_ai.deliveries(id, batch_token, sender_number, channel, destination, payload)
            VALUES (gen_random_uuid(), p_batch_token, p_sender_number, 'phone_b', p_admin_phone_b,
                    jsonb_build_object('number', p_admin_phone_b, 'text', 'AI işlemi 3 kez başarısız oldu. Müşteri manuel incelemeye alındı: ' || p_sender_number))
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

CREATE OR REPLACE FUNCTION whatsapp_ai.claim_deliveries(p_limit integer DEFAULT 20)
RETURNS SETOF whatsapp_ai.deliveries
LANGUAGE sql
AS $$
WITH candidates AS (
    SELECT d.id FROM whatsapp_ai.deliveries d
    WHERE d.status IN ('pending', 'failed')
      AND d.next_attempt_at <= clock_timestamp()
    ORDER BY d.created_at
    FOR UPDATE SKIP LOCKED
    LIMIT GREATEST(1, LEAST(p_limit, 100))
), claimed AS (
    UPDATE whatsapp_ai.deliveries d
    SET status = 'sending', claimed_at = clock_timestamp(),
        attempt_count = attempt_count + 1, updated_at = clock_timestamp()
    FROM candidates c WHERE d.id = c.id
    RETURNING d.*
)
SELECT * FROM claimed;
$$;

CREATE OR REPLACE FUNCTION whatsapp_ai.record_delivery_result(
    p_id uuid, p_success boolean, p_provider_message_id text DEFAULT NULL, p_error text DEFAULT NULL
) RETURNS text
LANGUAGE plpgsql
AS $$
DECLARE v whatsapp_ai.deliveries%ROWTYPE;
BEGIN
    SELECT * INTO v FROM whatsapp_ai.deliveries WHERE id = p_id FOR UPDATE;
    IF NOT FOUND OR v.status <> 'sending' THEN RETURN 'stale'; END IF;
    IF p_success THEN
        UPDATE whatsapp_ai.deliveries
        SET status = 'sent', provider_message_id = p_provider_message_id,
            last_error = NULL, updated_at = clock_timestamp()
        WHERE id = p_id;
        IF v.channel IN ('phone_a', 'phone_b') THEN
            INSERT INTO whatsapp_ai.admin_notifications(sender_number, channel, fingerprint)
            VALUES (v.sender_number, v.channel, COALESCE(v.payload->>'fingerprint', ''))
            ON CONFLICT (sender_number, channel) DO UPDATE
            SET fingerprint = EXCLUDED.fingerprint, sent_at = clock_timestamp();
        END IF;
        RETURN 'sent';
    ELSIF v.attempt_count >= 3 THEN
        UPDATE whatsapp_ai.deliveries SET status = 'dead', last_error = left(p_error, 2000),
            updated_at = clock_timestamp() WHERE id = p_id;
        INSERT INTO whatsapp_ai.system_events(event_type, sender_number_masked, batch_token, details)
        VALUES ('delivery_dead', right(v.sender_number, 4), v.batch_token,
                jsonb_build_object('channel', v.channel, 'attempt', v.attempt_count));
        RETURN 'dead';
    ELSE
        UPDATE whatsapp_ai.deliveries
        SET status = 'failed', last_error = left(p_error, 2000),
            next_attempt_at = clock_timestamp() + CASE v.attempt_count
                WHEN 1 THEN interval '30 seconds' ELSE interval '2 minutes' END,
            updated_at = clock_timestamp()
        WHERE id = p_id;
        RETURN 'retry';
    END IF;
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
                              'staleDeliveries', whatsapp_ai.recover_stale_deliveries());
END;
$$;

CREATE OR REPLACE FUNCTION whatsapp_ai.recover_stale_deliveries(
    p_age interval DEFAULT interval '2 minutes'
) RETURNS jsonb
LANGUAGE plpgsql
AS $$
DECLARE
    v_recovered integer := 0;
    v_dead integer := 0;
BEGIN
    WITH stale AS (
        SELECT id, batch_token, sender_number, channel, attempt_count
        FROM whatsapp_ai.deliveries
        WHERE status = 'sending'
          AND claimed_at IS NOT NULL
          AND claimed_at < clock_timestamp() - p_age
        FOR UPDATE SKIP LOCKED
    ), moved AS (
        UPDATE whatsapp_ai.deliveries d
        SET status = CASE WHEN d.attempt_count >= 3 THEN 'dead' ELSE 'failed' END,
            next_attempt_at = clock_timestamp(),
            claimed_at = NULL,
            last_error = CASE WHEN d.attempt_count >= 3
                              THEN 'stale_delivery_dead_lettered'
                              ELSE 'stale_delivery_recovered' END,
            updated_at = clock_timestamp()
        FROM stale s
        WHERE d.id = s.id
        RETURNING d.*
    )
    SELECT count(*) FILTER (WHERE status = 'failed'),
           count(*) FILTER (WHERE status = 'dead')
    INTO v_recovered, v_dead
    FROM moved;

    IF v_recovered + v_dead > 0 THEN
        INSERT INTO whatsapp_ai.system_events(event_type, details)
        VALUES ('stale_delivery_recovery', jsonb_build_object(
            'recovered', v_recovered, 'dead', v_dead, 'ageSeconds', extract(epoch FROM p_age)
        ));
    END IF;
    RETURN jsonb_build_object('recovered', v_recovered, 'dead', v_dead);
END;
$$;

COMMIT;
