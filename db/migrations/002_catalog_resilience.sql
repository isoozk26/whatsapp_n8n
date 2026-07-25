BEGIN;

CREATE TABLE IF NOT EXISTS whatsapp_ai.catalog_imports (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    checksum text NOT NULL UNIQUE,
    source_name text NOT NULL,
    status text NOT NULL DEFAULT 'staging' CHECK (status IN ('staging', 'active', 'rejected')),
    row_count integer NOT NULL DEFAULT 0,
    brand_count integer NOT NULL DEFAULT 0,
    model_count integer NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    activated_at timestamptz
);

CREATE TABLE IF NOT EXISTS whatsapp_ai.mann_vehicle_catalog (
    import_id uuid NOT NULL REFERENCES whatsapp_ai.catalog_imports(id) ON DELETE CASCADE,
    source_id bigint NOT NULL,
    brand text NOT NULL,
    model_series text NOT NULL,
    engine text NOT NULL,
    engine_codes text[] NOT NULL DEFAULT '{}',
    power_kw integer,
    power_bhp integer,
    displacement_ccm integer,
    fuel_type_raw text,
    production_start integer,
    production_end integer,
    brand_norm text NOT NULL,
    model_norm text NOT NULL,
    engine_norm text NOT NULL,
    PRIMARY KEY (import_id, source_id)
);
CREATE INDEX IF NOT EXISTS mann_catalog_brand_model_idx
    ON whatsapp_ai.mann_vehicle_catalog(import_id, brand_norm, model_norm);
CREATE INDEX IF NOT EXISTS mann_catalog_engine_idx
    ON whatsapp_ai.mann_vehicle_catalog(import_id, engine_norm);

CREATE TABLE IF NOT EXISTS whatsapp_ai.customer_vehicle_context (
    sender_number text PRIMARY KEY,
    brand text,
    model_series text,
    engine text,
    engine_code text,
    power_kw integer,
    power_bhp integer,
    displacement_ccm integer,
    fuel_type text,
    production_year integer,
    vin text,
    candidate_count integer NOT NULL DEFAULT 0,
    match_status text,
    match_details jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    expires_at timestamptz NOT NULL DEFAULT clock_timestamp() + interval '24 hours'
);
CREATE INDEX IF NOT EXISTS vehicle_context_expiry_idx
    ON whatsapp_ai.customer_vehicle_context(expires_at);

CREATE TABLE IF NOT EXISTS whatsapp_ai.service_circuits (
    service text PRIMARY KEY CHECK (service IN ('openai', 'evolution')),
    state text NOT NULL DEFAULT 'closed' CHECK (state IN ('closed', 'open', 'half_open')),
    consecutive_failures integer NOT NULL DEFAULT 0,
    window_started_at timestamptz,
    opened_until timestamptz,
    probe_started_at timestamptz,
    last_error_code text,
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
INSERT INTO whatsapp_ai.service_circuits(service) VALUES ('openai'), ('evolution')
ON CONFLICT (service) DO NOTHING;

CREATE TABLE IF NOT EXISTS whatsapp_ai.ops_cooldowns (
    alert_key text PRIMARY KEY,
    last_sent_at timestamptz NOT NULL DEFAULT '-infinity',
    details jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE OR REPLACE FUNCTION whatsapp_ai.norm_catalog_text(p_value text) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE
AS $$
SELECT trim(regexp_replace(upper(translate(COALESCE(p_value, ''),
    'ÇĞİÖŞÜçğıöşü', 'CGIOSUCGIOSU')), '[^A-Z0-9]+', ' ', 'g'));
$$;

CREATE OR REPLACE FUNCTION whatsapp_ai.begin_catalog_import(
    p_checksum text, p_source_name text
) RETURNS uuid
LANGUAGE plpgsql
AS $$
DECLARE v_id uuid;
BEGIN
    INSERT INTO whatsapp_ai.catalog_imports(checksum, source_name, status)
    VALUES (p_checksum, p_source_name, 'staging')
    ON CONFLICT (checksum) DO UPDATE SET source_name = EXCLUDED.source_name
    RETURNING id INTO v_id;
    DELETE FROM whatsapp_ai.mann_vehicle_catalog WHERE import_id = v_id
      AND NOT EXISTS (SELECT 1 FROM whatsapp_ai.catalog_imports WHERE id = v_id AND status = 'active');
    RETURN v_id;
END;
$$;

CREATE OR REPLACE FUNCTION whatsapp_ai.refresh_catalog_import_stats(p_import_id uuid) RETURNS jsonb
LANGUAGE plpgsql
AS $$
DECLARE v_rows integer; v_brands integer; v_models integer;
BEGIN
    SELECT count(*), count(DISTINCT brand_norm), count(DISTINCT brand_norm || ':' || model_norm)
      INTO v_rows, v_brands, v_models
    FROM whatsapp_ai.mann_vehicle_catalog WHERE import_id = p_import_id;
    UPDATE whatsapp_ai.catalog_imports
    SET row_count = v_rows, brand_count = v_brands, model_count = v_models
    WHERE id = p_import_id AND status = 'staging';
    RETURN jsonb_build_object('importId', p_import_id, 'rows', v_rows,
                              'brands', v_brands, 'models', v_models);
END;
$$;

CREATE OR REPLACE FUNCTION whatsapp_ai.activate_catalog_import(
    p_import_id uuid, p_checksum text
) RETURNS jsonb
LANGUAGE plpgsql
AS $$
DECLARE v_import whatsapp_ai.catalog_imports%ROWTYPE;
BEGIN
    SELECT * INTO v_import FROM whatsapp_ai.catalog_imports
    WHERE id = p_import_id AND checksum = p_checksum AND status = 'staging' FOR UPDATE;
    IF NOT FOUND OR v_import.row_count < 1 OR v_import.brand_count < 1 THEN
        RAISE EXCEPTION 'catalog import is not ready';
    END IF;
    UPDATE whatsapp_ai.catalog_imports SET status = 'rejected'
    WHERE status = 'active' AND id <> p_import_id;
    UPDATE whatsapp_ai.catalog_imports
    SET status = 'active', activated_at = clock_timestamp() WHERE id = p_import_id;
    RETURN jsonb_build_object('activated', true, 'importId', p_import_id,
                              'rows', v_import.row_count, 'brands', v_import.brand_count,
                              'models', v_import.model_count);
END;
$$;

CREATE OR REPLACE FUNCTION whatsapp_ai.resolve_vehicle_context(
    p_sender_number text,
    p_brand text DEFAULT NULL,
    p_model_series text DEFAULT NULL,
    p_engine text DEFAULT NULL,
    p_engine_code text DEFAULT NULL,
    p_power_kw integer DEFAULT NULL,
    p_power_bhp integer DEFAULT NULL,
    p_displacement_ccm integer DEFAULT NULL,
    p_fuel_type text DEFAULT NULL,
    p_production_year integer DEFAULT NULL,
    p_vin text DEFAULT NULL
) RETURNS jsonb
LANGUAGE plpgsql
AS $$
DECLARE
    v_ctx whatsapp_ai.customer_vehicle_context%ROWTYPE;
    v_import uuid;
    v_count integer := 0;
    v_missing text[] := '{}';
    v_optional text[] := '{}';
    v_status text;
    v_sample jsonb := '[]'::jsonb;
BEGIN
    DELETE FROM whatsapp_ai.customer_vehicle_context
    WHERE sender_number = p_sender_number AND expires_at < clock_timestamp();

    INSERT INTO whatsapp_ai.customer_vehicle_context(
        sender_number, brand, model_series, engine, engine_code, power_kw, power_bhp,
        displacement_ccm, fuel_type, production_year, vin
    ) VALUES (
        p_sender_number, NULLIF(trim(p_brand), ''), NULLIF(trim(p_model_series), ''),
        NULLIF(trim(p_engine), ''), NULLIF(trim(p_engine_code), ''), p_power_kw, p_power_bhp,
        p_displacement_ccm, NULLIF(trim(p_fuel_type), ''), p_production_year,
        CASE WHEN p_vin ~* '^[A-HJ-NPR-Z0-9]{17}$' THEN upper(p_vin) ELSE NULL END
    )
    ON CONFLICT (sender_number) DO UPDATE SET
        brand = COALESCE(EXCLUDED.brand, whatsapp_ai.customer_vehicle_context.brand),
        model_series = COALESCE(EXCLUDED.model_series, whatsapp_ai.customer_vehicle_context.model_series),
        engine = COALESCE(EXCLUDED.engine, whatsapp_ai.customer_vehicle_context.engine),
        engine_code = COALESCE(EXCLUDED.engine_code, whatsapp_ai.customer_vehicle_context.engine_code),
        power_kw = COALESCE(EXCLUDED.power_kw, whatsapp_ai.customer_vehicle_context.power_kw),
        power_bhp = COALESCE(EXCLUDED.power_bhp, whatsapp_ai.customer_vehicle_context.power_bhp),
        displacement_ccm = COALESCE(EXCLUDED.displacement_ccm, whatsapp_ai.customer_vehicle_context.displacement_ccm),
        fuel_type = COALESCE(EXCLUDED.fuel_type, whatsapp_ai.customer_vehicle_context.fuel_type),
        production_year = COALESCE(EXCLUDED.production_year, whatsapp_ai.customer_vehicle_context.production_year),
        vin = COALESCE(EXCLUDED.vin, whatsapp_ai.customer_vehicle_context.vin),
        updated_at = clock_timestamp(), expires_at = clock_timestamp() + interval '24 hours'
    RETURNING * INTO v_ctx;

    IF v_ctx.brand IS NULL THEN v_missing := array_append(v_missing, 'marka'); END IF;
    IF v_ctx.model_series IS NULL THEN v_missing := array_append(v_missing, 'model'); END IF;
    IF v_ctx.engine IS NULL THEN v_missing := array_append(v_missing, 'motor'); END IF;

    SELECT id INTO v_import FROM whatsapp_ai.catalog_imports WHERE status = 'active' LIMIT 1;
    IF v_import IS NULL THEN
        v_status := 'catalog_unavailable';
    ELSIF cardinality(v_missing) > 0 THEN
        v_status := 'missing_required';
    ELSE
        WITH candidates AS (
            SELECT c.*
            FROM whatsapp_ai.mann_vehicle_catalog c
            WHERE c.import_id = v_import
              AND c.brand_norm = whatsapp_ai.norm_catalog_text(v_ctx.brand)
              AND (c.model_norm LIKE '%' || whatsapp_ai.norm_catalog_text(v_ctx.model_series) || '%'
                   OR whatsapp_ai.norm_catalog_text(v_ctx.model_series) LIKE '%' || c.model_norm || '%')
              AND (c.engine_norm LIKE '%' || whatsapp_ai.norm_catalog_text(v_ctx.engine) || '%'
                   OR whatsapp_ai.norm_catalog_text(v_ctx.engine) LIKE '%' || c.engine_norm || '%')
              AND (v_ctx.production_year IS NULL OR
                   v_ctx.production_year BETWEEN COALESCE(c.production_start, v_ctx.production_year)
                                             AND COALESCE(c.production_end, v_ctx.production_year))
              AND (v_ctx.engine_code IS NULL OR EXISTS (
                    SELECT 1 FROM unnest(c.engine_codes) x
                    WHERE whatsapp_ai.norm_catalog_text(x) = whatsapp_ai.norm_catalog_text(v_ctx.engine_code)))
              AND (v_ctx.power_kw IS NULL OR c.power_kw IS NULL OR abs(c.power_kw - v_ctx.power_kw) <= 2)
              AND (v_ctx.power_bhp IS NULL OR c.power_bhp IS NULL OR abs(c.power_bhp - v_ctx.power_bhp) <= 3)
              AND (v_ctx.displacement_ccm IS NULL OR c.displacement_ccm IS NULL OR
                   abs(c.displacement_ccm - v_ctx.displacement_ccm) <= 50)
        ), totals AS (
            SELECT count(*)::integer AS candidate_count FROM candidates
        ), samples AS (
            SELECT COALESCE(jsonb_agg(jsonb_build_object(
            'sourceId', source_id, 'brand', brand, 'model', model_series, 'engine', engine,
            'engineCodes', engine_codes, 'kw', power_kw, 'bhp', power_bhp,
            'ccm', displacement_ccm, 'fuel', fuel_type_raw,
            'productionStart', production_start, 'productionEnd', production_end)
            ORDER BY source_id) FILTER (WHERE source_id IS NOT NULL), '[]'::jsonb) AS sample
            FROM (SELECT * FROM candidates ORDER BY source_id LIMIT 10) limited
        )
        SELECT totals.candidate_count, samples.sample INTO v_count, v_sample
        FROM totals CROSS JOIN samples;

        IF v_count = 1 THEN
            v_status := 'unique';
        ELSIF v_count = 0 THEN
            v_status := 'no_match';
            IF v_ctx.production_year IS NULL THEN v_optional := array_append(v_optional, 'üretim yılı'); END IF;
            IF v_ctx.displacement_ccm IS NULL THEN v_optional := array_append(v_optional, 'hacim (ccm)'); END IF;
            IF v_ctx.power_kw IS NULL AND v_ctx.power_bhp IS NULL THEN
                v_optional := array_append(v_optional, 'güç (kW veya BHP)');
            END IF;
        ELSE
            v_status := 'ambiguous';
            IF v_ctx.production_year IS NULL THEN v_optional := array_append(v_optional, 'üretim yılı'); END IF;
            IF v_ctx.displacement_ccm IS NULL THEN v_optional := array_append(v_optional, 'hacim (ccm)'); END IF;
            IF v_ctx.power_kw IS NULL AND v_ctx.power_bhp IS NULL THEN
                v_optional := array_append(v_optional, 'güç (kW veya BHP)');
            END IF;
            IF v_ctx.engine_code IS NULL THEN v_optional := array_append(v_optional, 'motor kodu'); END IF;
        END IF;
    END IF;

    UPDATE whatsapp_ai.customer_vehicle_context
    SET candidate_count = v_count, match_status = v_status,
        match_details = jsonb_build_object('candidates', v_sample, 'missingRequired', v_missing,
                                           'optionalFields', v_optional),
        updated_at = clock_timestamp(), expires_at = clock_timestamp() + interval '24 hours'
    WHERE sender_number = p_sender_number;

    RETURN jsonb_build_object(
        'status', v_status, 'candidateCount', v_count,
        'missingRequired', v_missing, 'optionalFields', v_optional,
        'vehicle', jsonb_build_object('brand', v_ctx.brand, 'model', v_ctx.model_series,
            'engine', v_ctx.engine, 'engineCode', v_ctx.engine_code, 'kw', v_ctx.power_kw,
            'bhp', v_ctx.power_bhp, 'ccm', v_ctx.displacement_ccm,
            'year', v_ctx.production_year, 'vin', v_ctx.vin),
        'candidates', v_sample
    );
END;
$$;

CREATE OR REPLACE FUNCTION whatsapp_ai.circuit_allows(p_service text) RETURNS boolean
LANGUAGE plpgsql
AS $$
DECLARE v whatsapp_ai.service_circuits%ROWTYPE; v_now timestamptz := clock_timestamp();
BEGIN
    INSERT INTO whatsapp_ai.service_circuits(service) VALUES (p_service)
    ON CONFLICT (service) DO NOTHING;
    SELECT * INTO v FROM whatsapp_ai.service_circuits WHERE service=p_service FOR UPDATE;
    IF v.state='closed' THEN RETURN true; END IF;
    IF v.state='open' AND v.opened_until <= v_now THEN
        UPDATE whatsapp_ai.service_circuits
        SET state='half_open', probe_started_at=v_now, updated_at=v_now WHERE service=p_service;
        RETURN true;
    END IF;
    IF v.state='half_open' AND v.probe_started_at < v_now-interval '30 seconds' THEN
        UPDATE whatsapp_ai.service_circuits SET probe_started_at=v_now, updated_at=v_now WHERE service=p_service;
        RETURN true;
    END IF;
    RETURN false;
END;
$$;

CREATE OR REPLACE FUNCTION whatsapp_ai.record_service_result(
    p_service text, p_success boolean, p_error_code text DEFAULT NULL
) RETURNS text
LANGUAGE plpgsql
AS $$
DECLARE v whatsapp_ai.service_circuits%ROWTYPE; v_now timestamptz := clock_timestamp();
BEGIN
    INSERT INTO whatsapp_ai.service_circuits(service) VALUES (p_service)
    ON CONFLICT (service) DO NOTHING;
    SELECT * INTO v FROM whatsapp_ai.service_circuits WHERE service = p_service FOR UPDATE;
    IF p_success THEN
        UPDATE whatsapp_ai.service_circuits SET state = 'closed', consecutive_failures = 0,
            window_started_at = NULL, opened_until = NULL, probe_started_at = NULL,
            last_error_code = NULL, updated_at = v_now
        WHERE service = p_service;
        RETURN 'closed';
    END IF;
    IF v.window_started_at IS NULL OR v.window_started_at < v_now - interval '2 minutes' THEN
        v.consecutive_failures := 1; v.window_started_at := v_now;
    ELSE
        v.consecutive_failures := v.consecutive_failures + 1;
    END IF;
    UPDATE whatsapp_ai.service_circuits
    SET consecutive_failures = v.consecutive_failures, window_started_at = v.window_started_at,
        state = CASE WHEN state='half_open' OR v.consecutive_failures >= 5 THEN 'open' ELSE state END,
        opened_until = CASE WHEN state='half_open' OR v.consecutive_failures >= 5 THEN v_now + interval '60 seconds' ELSE opened_until END,
        probe_started_at = NULL,
        last_error_code = p_error_code, updated_at = v_now
    WHERE service = p_service;
    IF v.state='half_open' OR v.consecutive_failures >= 5 THEN
        INSERT INTO whatsapp_ai.system_events(event_type, details)
        VALUES ('circuit_open', jsonb_build_object('service', p_service, 'code', p_error_code,
                                                   'failures', v.consecutive_failures));
        RETURN 'open';
    END IF;
    RETURN 'closed';
END;
$$;

CREATE OR REPLACE FUNCTION whatsapp_ai.enqueue_admin_alert(
    p_alert_key text, p_text text, p_cooldown interval DEFAULT interval '30 minutes'
) RETURNS boolean
LANGUAGE plpgsql
AS $$
DECLARE v_a text := COALESCE((SELECT value FROM whatsapp_ai.settings WHERE key='admin_phone_a'), '');
        v_b text := COALESCE((SELECT value FROM whatsapp_ai.settings WHERE key='admin_phone_b'), '');
        v_token uuid := gen_random_uuid();
        v_last_sent timestamptz;
BEGIN
    INSERT INTO whatsapp_ai.ops_cooldowns(alert_key) VALUES (p_alert_key) ON CONFLICT DO NOTHING;
    SELECT last_sent_at INTO v_last_sent FROM whatsapp_ai.ops_cooldowns
    WHERE alert_key=p_alert_key FOR UPDATE;
    IF v_last_sent > clock_timestamp()-p_cooldown THEN
        RETURN false;
    END IF;
    IF v_a <> '' THEN
        INSERT INTO whatsapp_ai.deliveries(id,batch_token,sender_number,channel,destination,payload)
        VALUES(gen_random_uuid(),v_token,'system','phone_a',v_a,jsonb_build_object('number',v_a,'text',p_text));
    END IF;
    IF v_b <> '' THEN
        INSERT INTO whatsapp_ai.deliveries(id,batch_token,sender_number,channel,destination,payload)
        VALUES(gen_random_uuid(),v_token,'system','phone_b',v_b,jsonb_build_object('number',v_b,'text',p_text));
    END IF;
    UPDATE whatsapp_ai.ops_cooldowns SET last_sent_at=clock_timestamp(),
        details=jsonb_build_object('lastTextHash',md5(p_text)) WHERE alert_key=p_alert_key;
    RETURN true;
END;
$$;

CREATE OR REPLACE FUNCTION whatsapp_ai.run_queue_monitor() RETURNS jsonb
LANGUAGE plpgsql
AS $$
DECLARE v_pending integer; v_processing integer; v_dead integer; v_manual integer; v_sent boolean := false;
BEGIN
    SELECT count(*) INTO v_pending FROM whatsapp_ai.batches
      WHERE status='pending' AND updated_at < clock_timestamp()-interval '7 minutes';
    SELECT count(*) INTO v_processing FROM whatsapp_ai.batches
      WHERE status='processing' AND processing_started_at < clock_timestamp()-interval '5 minutes';
    SELECT count(*) INTO v_dead FROM whatsapp_ai.deliveries
      WHERE status='dead' AND updated_at > clock_timestamp()-interval '24 hours';
    SELECT count(*) INTO v_manual FROM whatsapp_ai.batches b
      WHERE status='manual' AND b.last_error_code IS NOT NULL;
    IF v_pending+v_processing+v_dead+v_manual > 0 THEN
        v_sent := whatsapp_ai.enqueue_admin_alert('queue_health',
          format('⚠️ SİSTEM KUYRUK ALARMI\nBekleyen: %s\nTakılan processing: %s\nDead delivery: %s\nAI manuel: %s',
                 v_pending,v_processing,v_dead,v_manual));
    END IF;
    INSERT INTO whatsapp_ai.system_events(event_type,details)
    VALUES('queue_monitor',jsonb_build_object('pending',v_pending,'processing',v_processing,
           'dead',v_dead,'manual',v_manual,'alertQueued',v_sent));
    RETURN jsonb_build_object('pending',v_pending,'processing',v_processing,'dead',v_dead,
                              'manual',v_manual,'alertQueued',v_sent);
END;
$$;

CREATE OR REPLACE FUNCTION whatsapp_ai.run_daily_report() RETURNS jsonb
LANGUAGE plpgsql
AS $$
DECLARE v_received integer; v_sent integer; v_failed integer; v_dead integer; v_ai_dead integer; v_text text;
BEGIN
    SELECT count(*) INTO v_received FROM whatsapp_ai.messages WHERE received_at > clock_timestamp()-interval '24 hours';
    SELECT count(*) FILTER(WHERE status='sent'), count(*) FILTER(WHERE status='failed'),
           count(*) FILTER(WHERE status='dead') INTO v_sent,v_failed,v_dead
    FROM whatsapp_ai.deliveries WHERE created_at > clock_timestamp()-interval '24 hours';
    SELECT count(*) INTO v_ai_dead FROM whatsapp_ai.system_events
      WHERE event_type='ai_dead' AND created_at > clock_timestamp()-interval '24 hours';
    v_text := format('📊 GÜNLÜK OTOMASYON RAPORU\nGelen mesaj: %s\nBaşarılı teslimat: %s\nRetry bekleyen: %s\nDead: %s\nAI manuel: %s',
                     v_received,v_sent,v_failed,v_dead,v_ai_dead);
    PERFORM whatsapp_ai.enqueue_admin_alert('daily_report:'||current_date::text,v_text,interval '23 hours');
    RETURN jsonb_build_object('received',v_received,'sent',v_sent,'failed',v_failed,'dead',v_dead,'aiManual',v_ai_dead);
END;
$$;

CREATE OR REPLACE FUNCTION whatsapp_ai.run_retention() RETURNS jsonb
LANGUAGE plpgsql
AS $$
DECLARE v_context integer; v_redacted integer; v_dead integer; v_events integer;
BEGIN
    DELETE FROM whatsapp_ai.customer_vehicle_context WHERE expires_at < clock_timestamp();
    GET DIAGNOSTICS v_context = ROW_COUNT;
    WITH targets AS (SELECT id FROM whatsapp_ai.deliveries WHERE status='sent'
                     AND updated_at < clock_timestamp()-interval '7 days'
                     AND payload <> '{"redacted":true}'::jsonb LIMIT 1000)
    UPDATE whatsapp_ai.deliveries d SET payload='{"redacted":true}'::jsonb,
        destination=right(destination,4), sender_number=right(sender_number,4)
    FROM targets t WHERE d.id=t.id;
    GET DIAGNOSTICS v_redacted = ROW_COUNT;
    DELETE FROM whatsapp_ai.deliveries WHERE status='dead'
      AND updated_at < clock_timestamp()-interval '30 days';
    GET DIAGNOSTICS v_dead = ROW_COUNT;
    DELETE FROM whatsapp_ai.system_events WHERE created_at < clock_timestamp()-interval '30 days';
    GET DIAGNOSTICS v_events = ROW_COUNT;
    INSERT INTO whatsapp_ai.system_events(event_type,details)
    VALUES('retention',jsonb_build_object('contexts',v_context,'redacted',v_redacted,
                                          'deadDeleted',v_dead,'eventsDeleted',v_events));
    RETURN jsonb_build_object('contexts',v_context,'redacted',v_redacted,
                              'deadDeleted',v_dead,'eventsDeleted',v_events);
END;
$$;

INSERT INTO whatsapp_ai.settings(key,value) VALUES ('credentials_last_rotated_at', current_date::text)
ON CONFLICT (key) DO NOTHING;

CREATE OR REPLACE FUNCTION whatsapp_ai.run_rotation_reminder() RETURNS jsonb
LANGUAGE plpgsql
AS $$
DECLARE v_last date; v_due boolean; v_queued boolean := false;
BEGIN
    SELECT value::date INTO v_last FROM whatsapp_ai.settings WHERE key='credentials_last_rotated_at';
    v_due := v_last <= current_date-90;
    IF v_due THEN
        v_queued := whatsapp_ai.enqueue_admin_alert(
            'credential_rotation:'||v_last::text,
            format('CREDENTIAL ROTATION HATIRLATMASI\nSon kayitli yenileme: %s\nOpenAI, Evolution, n8n API ve PostgreSQL credentiallarini manuel yenileyin.',v_last),
            interval '23 hours');
    END IF;
    RETURN jsonb_build_object('lastRotatedAt',v_last,'due',v_due,'alertQueued',v_queued);
END;
$$;

COMMIT;
