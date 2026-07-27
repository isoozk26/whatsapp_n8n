BEGIN;

CREATE OR REPLACE FUNCTION whatsapp_ai.run_stale_batch_monitor(
    p_age interval DEFAULT interval '10 minutes',
    p_alert_cooldown interval DEFAULT interval '5 minutes'
) RETURNS jsonb
LANGUAGE plpgsql
AS $$
DECLARE
    v_stale_count integer := 0;
    v_oldest_age_seconds integer := 0;
    v_alert_queued boolean := false;
    v_alert_text text := '';
BEGIN
    SELECT
        count(*),
        COALESCE(
            MAX(GREATEST(0, FLOOR(EXTRACT(EPOCH FROM (clock_timestamp() - processing_started_at)))::integer)),
            0
        )
    INTO v_stale_count, v_oldest_age_seconds
    FROM whatsapp_ai.batches
    WHERE status = 'processing'
      AND processing_started_at IS NOT NULL
      AND processing_started_at < clock_timestamp() - p_age;

    IF v_stale_count > 0 THEN
        v_alert_text := format(
            'STALE BATCH ALERT\nCount: %s\nOldest age seconds: %s\nThreshold minutes: %s',
            v_stale_count,
            v_oldest_age_seconds,
            extract(epoch FROM p_age) / 60
        );
        v_alert_queued := whatsapp_ai.enqueue_admin_alert(
            'stale_batch_monitor',
            v_alert_text,
            p_alert_cooldown
        );

        INSERT INTO whatsapp_ai.system_events(event_type, details)
        VALUES (
            'stale_batch_monitor',
            jsonb_build_object(
                'staleCount', v_stale_count,
                'oldestAgeSeconds', v_oldest_age_seconds,
                'ageSeconds', extract(epoch FROM p_age),
                'alertQueued', v_alert_queued
            )
        );
    END IF;

    RETURN jsonb_build_object(
        'staleCount', v_stale_count,
        'oldestAgeSeconds', v_oldest_age_seconds,
        'ageSeconds', extract(epoch FROM p_age),
        'alertQueued', v_alert_queued
    );
END;
$$;

COMMIT;
