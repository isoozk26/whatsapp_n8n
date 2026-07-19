BEGIN;

ALTER TABLE whatsapp_ai.deliveries
    ADD COLUMN IF NOT EXISTS first_attempt_at timestamptz,
    ADD COLUMN IF NOT EXISTS sent_at timestamptz,
    ADD COLUMN IF NOT EXISTS latency_ms bigint;

CREATE INDEX IF NOT EXISTS deliveries_age_idx
    ON whatsapp_ai.deliveries (status, created_at, updated_at);

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
    SET status = 'sending',
        claimed_at = clock_timestamp(),
        first_attempt_at = COALESCE(first_attempt_at, clock_timestamp()),
        attempt_count = attempt_count + 1,
        updated_at = clock_timestamp()
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
            sent_at = clock_timestamp(),
            latency_ms = GREATEST(0, (extract(epoch FROM (clock_timestamp() - created_at)) * 1000)::bigint),
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

CREATE OR REPLACE FUNCTION whatsapp_ai.run_queue_monitor() RETURNS jsonb
LANGUAGE plpgsql
AS $$
DECLARE
    v_pending integer; v_processing integer; v_dead integer; v_manual integer;
    v_sending integer; v_failed integer; v_sent boolean := false;
    v_oldest_pending integer := 0; v_oldest_processing integer := 0;
    v_oldest_delivery integer := 0;
BEGIN
    SELECT count(*) INTO v_pending FROM whatsapp_ai.batches
      WHERE status='pending' AND updated_at < clock_timestamp()-interval '7 minutes';
    SELECT count(*) INTO v_processing FROM whatsapp_ai.batches
      WHERE status='processing' AND processing_started_at < clock_timestamp()-interval '5 minutes';
    SELECT count(*) INTO v_dead FROM whatsapp_ai.deliveries
      WHERE status='dead' AND updated_at > clock_timestamp()-interval '24 hours';
    SELECT count(*) INTO v_manual FROM whatsapp_ai.batches b
      WHERE status='manual' AND b.last_error_code IS NOT NULL;
    SELECT count(*) FILTER (WHERE status='sending'), count(*) FILTER (WHERE status='failed')
      INTO v_sending, v_failed FROM whatsapp_ai.deliveries
      WHERE status IN ('sending','failed');
    SELECT COALESCE(extract(epoch FROM (clock_timestamp()-min(updated_at)))::integer,0)
      INTO v_oldest_pending FROM whatsapp_ai.batches WHERE status='pending';
    SELECT COALESCE(extract(epoch FROM (clock_timestamp()-min(processing_started_at)))::integer,0)
      INTO v_oldest_processing FROM whatsapp_ai.batches WHERE status='processing';
    SELECT COALESCE(extract(epoch FROM (clock_timestamp()-min(created_at)))::integer,0)
      INTO v_oldest_delivery FROM whatsapp_ai.deliveries WHERE status IN ('pending','failed','sending');

    IF v_pending+v_processing+v_dead+v_manual+v_sending > 0 THEN
        v_sent := whatsapp_ai.enqueue_admin_alert('queue_health',
          format('SISTEM KUYRUK ALARMI\nBekleyen: %s\nTakilan processing: %s\nSending: %s\nFailed: %s\nDead: %s\nAI manuel: %s',
                 v_pending,v_processing,v_sending,v_failed,v_dead,v_manual));
    END IF;
    INSERT INTO whatsapp_ai.system_events(event_type,details)
    VALUES('queue_monitor',jsonb_build_object(
      'pending',v_pending,'processing',v_processing,'sending',v_sending,'failed',v_failed,
      'dead',v_dead,'manual',v_manual,'oldestPendingAgeSeconds',v_oldest_pending,
      'oldestProcessingAgeSeconds',v_oldest_processing,'oldestDeliveryAgeSeconds',v_oldest_delivery,
      'alertQueued',v_sent));
    RETURN jsonb_build_object('pending',v_pending,'processing',v_processing,'sending',v_sending,
      'failed',v_failed,'dead',v_dead,'manual',v_manual,'oldestPendingAgeSeconds',v_oldest_pending,
      'oldestProcessingAgeSeconds',v_oldest_processing,'oldestDeliveryAgeSeconds',v_oldest_delivery,
      'alertQueued',v_sent);
END;
$$;

CREATE OR REPLACE FUNCTION whatsapp_ai.run_daily_report() RETURNS jsonb
LANGUAGE plpgsql
AS $$
DECLARE v_received integer; v_sent integer; v_failed integer; v_dead integer; v_ai_dead integer;
        v_recovered integer; v_auth_failures integer; v_avg numeric; v_p95 numeric; v_text text;
BEGIN
    SELECT count(*) INTO v_received FROM whatsapp_ai.messages WHERE received_at > clock_timestamp()-interval '24 hours';
    SELECT count(*) FILTER(WHERE status='sent'), count(*) FILTER(WHERE status='failed'),
           count(*) FILTER(WHERE status='dead') INTO v_sent,v_failed,v_dead
    FROM whatsapp_ai.deliveries WHERE created_at > clock_timestamp()-interval '24 hours';
    SELECT count(*) INTO v_ai_dead FROM whatsapp_ai.system_events
      WHERE event_type='ai_dead' AND created_at > clock_timestamp()-interval '24 hours';
    SELECT count(*) INTO v_recovered FROM whatsapp_ai.system_events
      WHERE event_type='stale_delivery_recovery' AND created_at > clock_timestamp()-interval '24 hours';
    SELECT count(*) INTO v_auth_failures FROM whatsapp_ai.system_events
      WHERE event_type='webhook_auth_failure' AND created_at > clock_timestamp()-interval '24 hours';
    SELECT avg(latency_ms), percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms)
      INTO v_avg, v_p95 FROM whatsapp_ai.deliveries
      WHERE status='sent' AND sent_at > clock_timestamp()-interval '24 hours' AND latency_ms IS NOT NULL;
    v_text := format('GUNLUK OTOMASYON RAPORU\nGelen mesaj: %s\nBasarili teslimat: %s\nRetry: %s\nDead: %s\nAI manuel: %s\nStale recovery: %s\nAuth hatasi: %s\nOrtalama latency ms: %s\nP95 latency ms: %s',
                     v_received,v_sent,v_failed,v_dead,v_ai_dead,v_recovered,v_auth_failures,
                     COALESCE(round(v_avg),0),COALESCE(round(v_p95),0));
    PERFORM whatsapp_ai.enqueue_admin_alert('daily_report:'||current_date::text,v_text,interval '23 hours');
    RETURN jsonb_build_object('received',v_received,'sent',v_sent,'failed',v_failed,'dead',v_dead,
      'aiManual',v_ai_dead,'staleRecovery',v_recovered,'authFailures',v_auth_failures,
      'avgLatencyMs',COALESCE(v_avg,0),'p95LatencyMs',COALESCE(v_p95,0));
END;
$$;

COMMIT;
