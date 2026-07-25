BEGIN;

CREATE OR REPLACE FUNCTION whatsapp_ai.run_batch_readiness_probe(
    p_limit integer DEFAULT 10
) RETURNS jsonb
LANGUAGE plpgsql
AS $$
DECLARE
    v_now timestamptz := clock_timestamp();
    v_timezone text := current_setting('TimeZone');
    v_pending_count integer := 0;
    v_claimable_count integer := 0;
    v_processing_count integer := 0;
    v_stale_processing_count integer := 0;
    v_manual_batch_count integer := 0;
    v_manual_mode_count integer := 0;
    v_oldest_pending_age_seconds integer := 0;
    v_oldest_claimable_age_seconds integer := 0;
    v_oldest_processing_age_seconds integer := 0;
    v_next_claim_in_seconds integer := 0;
    v_preview jsonb := '[]'::jsonb;
BEGIN
    WITH batch_state AS (
        SELECT
            b.sender_number,
            b.sender_name,
            b.first_message_at,
            b.next_ai_attempt_at,
            b.ai_attempt_count,
            GREATEST(
                0,
                COALESCE(FLOOR(EXTRACT(EPOCH FROM (v_now - b.first_message_at)))::integer, 0)
            ) AS age_seconds,
            CASE
                WHEN b.ai_attempt_count > 0 AND b.next_ai_attempt_at IS NOT NULL AND b.next_ai_attempt_at > v_now THEN
                    GREATEST(0, CEIL(EXTRACT(EPOCH FROM (b.next_ai_attempt_at - v_now)))::integer)
                WHEN b.ai_attempt_count = 0 AND b.first_message_at IS NOT NULL AND b.first_message_at > v_now - interval '120 seconds' THEN
                    GREATEST(0, CEIL(EXTRACT(EPOCH FROM ((b.first_message_at + interval '120 seconds') - v_now)))::integer)
                ELSE 0
            END AS ready_in_seconds,
            CASE
                WHEN b.ai_attempt_count > 0 THEN
                    b.next_ai_attempt_at IS NULL OR b.next_ai_attempt_at <= v_now
                ELSE
                    b.first_message_at IS NOT NULL AND b.first_message_at <= v_now - interval '120 seconds'
            END AS claimable
        FROM whatsapp_ai.batches b
        WHERE b.status = 'pending'
          AND jsonb_array_length(b.pending_messages) > 0
    )
    SELECT
        count(*),
        count(*) FILTER (WHERE claimable),
        COALESCE(MAX(age_seconds), 0),
        COALESCE(MAX(age_seconds) FILTER (WHERE claimable), 0),
        COALESCE(MIN(ready_in_seconds) FILTER (WHERE ready_in_seconds > 0), 0),
        COALESCE(
            (
                SELECT jsonb_agg(jsonb_build_object(
                    'senderNumber', limited.sender_number,
                    'senderName', limited.sender_name,
                    'aiAttemptCount', limited.ai_attempt_count,
                    'ageSeconds', limited.age_seconds,
                    'readyInSeconds', limited.ready_in_seconds,
                    'claimable', limited.claimable,
                    'firstMessageAt', limited.first_message_at,
                    'nextAttemptAt', limited.next_ai_attempt_at
                ))
                FROM (
                    SELECT *
                    FROM batch_state
                    ORDER BY claimable DESC, first_message_at NULLS LAST, sender_number
                    LIMIT GREATEST(1, LEAST(p_limit, 25))
                ) limited
            ),
            '[]'::jsonb
        )
    INTO
        v_pending_count,
        v_claimable_count,
        v_oldest_pending_age_seconds,
        v_oldest_claimable_age_seconds,
        v_next_claim_in_seconds,
        v_preview
    FROM batch_state;

    SELECT count(*) INTO v_processing_count
    FROM whatsapp_ai.batches
    WHERE status = 'processing';

    SELECT count(*) INTO v_stale_processing_count
    FROM whatsapp_ai.batches
    WHERE status = 'processing'
      AND processing_started_at IS NOT NULL
      AND processing_started_at < v_now - interval '10 minutes';

    SELECT count(*) INTO v_manual_batch_count
    FROM whatsapp_ai.batches
    WHERE status = 'manual';

    SELECT count(*) INTO v_manual_mode_count
    FROM whatsapp_ai.manual_modes
    WHERE enabled = true;

    SELECT COALESCE(
        MAX(GREATEST(0, FLOOR(EXTRACT(EPOCH FROM (v_now - processing_started_at)))::integer)),
        0
    )
    INTO v_oldest_processing_age_seconds
    FROM whatsapp_ai.batches
    WHERE status = 'processing'
      AND processing_started_at IS NOT NULL;

    RETURN jsonb_build_object(
        'timezone', v_timezone,
        'dbNow', v_now,
        'dbNowUtc', v_now AT TIME ZONE 'UTC',
        'dbNowIstanbul', v_now AT TIME ZONE 'Europe/Istanbul',
        'pendingCount', v_pending_count,
        'claimableCount', v_claimable_count,
        'processingCount', v_processing_count,
        'staleProcessingCount', v_stale_processing_count,
        'manualBatchCount', v_manual_batch_count,
        'manualModeCount', v_manual_mode_count,
        'oldestPendingAgeSeconds', v_oldest_pending_age_seconds,
        'oldestClaimableAgeSeconds', v_oldest_claimable_age_seconds,
        'oldestProcessingAgeSeconds', v_oldest_processing_age_seconds,
        'nextClaimInSeconds', v_next_claim_in_seconds,
        'pendingPreview', v_preview
    );
END;
$$;

COMMIT;
