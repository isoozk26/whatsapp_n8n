BEGIN;

-- Emoji output uses chr() so the migration remains encoding-safe on every psql client.
CREATE OR REPLACE FUNCTION whatsapp_ai.run_daily_report() RETURNS jsonb
LANGUAGE plpgsql
AS $$
DECLARE
    v_received integer := 0;
    v_customer_sent integer := 0;
    v_customer_failed integer := 0;
    v_customer_dead integer := 0;
    v_manager_sent integer := 0;
    v_ai_dead integer := 0;
    v_recovered integer := 0;
    v_auth_failures integer := 0;
    v_pending integer := 0;
    v_avg numeric;
    v_p95 numeric;
    v_health text;
    v_text text;
BEGIN
    SELECT count(*) INTO v_received
    FROM whatsapp_ai.messages
    WHERE received_at > clock_timestamp() - interval '24 hours';

    SELECT
        count(*) FILTER (WHERE channel = 'customer' AND status = 'sent'),
        count(*) FILTER (WHERE channel = 'customer' AND status = 'failed'),
        count(*) FILTER (WHERE channel = 'customer' AND status = 'dead'),
        count(*) FILTER (WHERE channel IN ('phone_a', 'phone_b') AND status = 'sent')
    INTO v_customer_sent, v_customer_failed, v_customer_dead, v_manager_sent
    FROM whatsapp_ai.deliveries
    WHERE created_at > clock_timestamp() - interval '24 hours';

    SELECT count(*) INTO v_ai_dead
    FROM whatsapp_ai.system_events
    WHERE event_type = 'ai_dead'
      AND created_at > clock_timestamp() - interval '24 hours';

    SELECT count(*) INTO v_recovered
    FROM whatsapp_ai.system_events
    WHERE event_type = 'stale_delivery_recovery'
      AND created_at > clock_timestamp() - interval '24 hours';

    SELECT count(*) INTO v_auth_failures
    FROM whatsapp_ai.system_events
    WHERE event_type = 'webhook_auth_failure'
      AND created_at > clock_timestamp() - interval '24 hours';

    SELECT count(*) INTO v_pending
    FROM whatsapp_ai.batches
    WHERE status = 'pending'
      AND jsonb_array_length(pending_messages) > 0
      AND (next_ai_attempt_at IS NULL OR next_ai_attempt_at <= clock_timestamp());

    SELECT avg(latency_ms), percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms)
    INTO v_avg, v_p95
    FROM whatsapp_ai.deliveries
    WHERE channel = 'customer'
      AND status = 'sent'
      AND sent_at > clock_timestamp() - interval '24 hours'
      AND latency_ms IS NOT NULL;

    v_health := CASE
        WHEN v_customer_dead > 0 OR v_customer_failed > 0 OR v_ai_dead > 0
            THEN chr(128308) || ' Saglik: sorun var'
        WHEN v_pending > 0 OR v_recovered > 0
            THEN chr(128993) || ' Saglik: izlem gerekli'
        ELSE chr(128994) || ' Saglikli'
    END;

    v_text := array_to_string(ARRAY[
        v_health,
        format($report$
%s GUNLUK OTOMASYON RAPORU
%s Son 24 saat
--------------------
%s Musteri Trafigi
   %s Gelen mesaj: %s
   %s Yanit gonderildi: %s
   %s Yeniden denenen: %s
   %s Basarisiz (dead): %s
--------------------
%s Yapay Zeka
   %s AI hatasi: %s
   %s Manuel moda dusen: %s
--------------------
%s Sistem Sagligi
   %s Otomatik kurtarma: %s
   %s Auth reddi: %s
   %s Yoneticiye giden bildirim: %s
   %s Islenmeyi bekleyen: %s
   %s Ortalama yanit: %s sn
   %s P95 yanit: %s sn
--------------------
OtoFiltre Otomatik Sistem
$report$,
            chr(128202), chr(128336), chr(128172), chr(128229), v_received,
            chr(9989), v_customer_sent, chr(128260), v_customer_failed,
            chr(9940), v_customer_dead, chr(129302), chr(9888), v_ai_dead,
            chr(9995), v_ai_dead, chr(128737) || chr(65039), chr(9851), v_recovered,
            chr(128274), v_auth_failures, chr(128233), v_manager_sent,
            chr(9203), v_pending, chr(9889), round(COALESCE(v_avg, 0) / 1000, 1),
            chr(128200), round(COALESCE(v_p95, 0) / 1000, 1)
        )
    ], E'\n');

    PERFORM whatsapp_ai.enqueue_admin_alert(
        'daily_report:' || current_date::text,
        v_text,
        interval '23 hours'
    );

    RETURN jsonb_build_object(
        'received', v_received,
        'customerSent', v_customer_sent,
        'customerFailed', v_customer_failed,
        'customerDead', v_customer_dead,
        'managerSent', v_manager_sent,
        'adminSent', v_manager_sent,
        'health', v_health,
        'aiDead', v_ai_dead,
        'staleRecovery', v_recovered,
        'authFailures', v_auth_failures,
        'pending', v_pending,
        'avgLatencyMs', COALESCE(v_avg, 0),
        'p95LatencyMs', COALESCE(v_p95, 0)
    );
END;
$$;

COMMIT;
