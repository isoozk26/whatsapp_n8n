BEGIN;

CREATE OR REPLACE FUNCTION whatsapp_ai.run_queue_monitor() RETURNS jsonb
LANGUAGE plpgsql
AS $$
DECLARE
    v_pending integer := 0;
    v_deferred integer := 0;
    v_processing integer := 0;
    v_dead integer := 0;
    v_manual integer := 0;
    v_sending integer := 0;
    v_failed integer := 0;
    v_alert_queued boolean := false;
    v_oldest_pending integer := 0;
    v_oldest_processing integer := 0;
    v_oldest_delivery integer := 0;
BEGIN
    SELECT count(*) INTO v_pending
    FROM whatsapp_ai.batches
    WHERE status = 'pending'
      AND jsonb_array_length(pending_messages) > 0
      AND (next_ai_attempt_at IS NULL OR next_ai_attempt_at <= clock_timestamp())
      AND updated_at < clock_timestamp() - interval '7 minutes';

    SELECT count(*) INTO v_deferred
    FROM whatsapp_ai.batches
    WHERE status = 'pending'
      AND jsonb_array_length(pending_messages) > 0
      AND next_ai_attempt_at > clock_timestamp();

    SELECT count(*) INTO v_processing
    FROM whatsapp_ai.batches
    WHERE status = 'processing'
      AND processing_started_at < clock_timestamp() - interval '5 minutes';

    SELECT count(*) INTO v_dead
    FROM whatsapp_ai.deliveries
    WHERE status = 'dead'
      AND updated_at > clock_timestamp() - interval '24 hours';

    SELECT count(*) INTO v_manual
    FROM whatsapp_ai.batches
    WHERE status = 'manual'
      AND last_error_code IS NOT NULL;

    SELECT count(*) FILTER (WHERE status = 'sending'), count(*) FILTER (WHERE status = 'failed')
    INTO v_sending, v_failed
    FROM whatsapp_ai.deliveries
    WHERE status IN ('sending', 'failed');

    SELECT COALESCE(extract(epoch FROM (clock_timestamp() - min(updated_at)))::integer, 0)
    INTO v_oldest_pending
    FROM whatsapp_ai.batches
    WHERE status = 'pending'
      AND (next_ai_attempt_at IS NULL OR next_ai_attempt_at <= clock_timestamp());

    SELECT COALESCE(extract(epoch FROM (clock_timestamp() - min(processing_started_at)))::integer, 0)
    INTO v_oldest_processing
    FROM whatsapp_ai.batches
    WHERE status = 'processing';

    SELECT COALESCE(extract(epoch FROM (clock_timestamp() - min(created_at)))::integer, 0)
    INTO v_oldest_delivery
    FROM whatsapp_ai.deliveries
    WHERE status IN ('pending', 'failed', 'sending');

    IF v_pending + v_processing + v_dead + v_manual + v_sending + v_failed > 0 THEN
        v_alert_queued := whatsapp_ai.enqueue_admin_alert(
            'queue_health',
            format(
                E'🚨 *SİSTEM KUYRUK ALARMI*\nBekleyen: %s\nErtelenmiş: %s\nTakılan processing: %s\nSending: %s\nFailed: %s\nDead: %s\nAI manuel: %s',
                v_pending, v_deferred, v_processing, v_sending, v_failed, v_dead, v_manual
            )
        );
    END IF;

    INSERT INTO whatsapp_ai.system_events(event_type, details)
    VALUES (
        'queue_monitor',
        jsonb_build_object(
            'pending', v_pending,
            'deferred', v_deferred,
            'processing', v_processing,
            'sending', v_sending,
            'failed', v_failed,
            'dead', v_dead,
            'manual', v_manual,
            'oldestPendingAgeSeconds', v_oldest_pending,
            'oldestProcessingAgeSeconds', v_oldest_processing,
            'oldestDeliveryAgeSeconds', v_oldest_delivery,
            'alertQueued', v_alert_queued
        )
    );

    RETURN jsonb_build_object(
        'pending', v_pending,
        'deferred', v_deferred,
        'processing', v_processing,
        'sending', v_sending,
        'failed', v_failed,
        'dead', v_dead,
        'manual', v_manual,
        'oldestPendingAgeSeconds', v_oldest_pending,
        'oldestProcessingAgeSeconds', v_oldest_processing,
        'oldestDeliveryAgeSeconds', v_oldest_delivery,
        'alertQueued', v_alert_queued
    );
END;
$$;

COMMIT;
