BEGIN;

-- Drop catalog tables
DROP TABLE IF EXISTS whatsapp_ai.mann_vehicle_catalog;
DROP TABLE IF EXISTS whatsapp_ai.catalog_imports;
DROP TABLE IF EXISTS whatsapp_ai.customer_vehicle_context;

-- Drop catalog functions
DROP FUNCTION IF EXISTS whatsapp_ai.norm_catalog_text(text);
DROP FUNCTION IF EXISTS whatsapp_ai.begin_catalog_import(text, text);
DROP FUNCTION IF EXISTS whatsapp_ai.refresh_catalog_import_stats(uuid);
DROP FUNCTION IF EXISTS whatsapp_ai.activate_catalog_import(uuid, text);
DROP FUNCTION IF EXISTS whatsapp_ai.resolve_vehicle_context(text, text, text, text, text, integer, integer, integer, text, integer, text);

-- Recreate non-catalog tables originally from migration 002
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

-- Recreate circuit breaker functions
CREATE OR REPLACE FUNCTION whatsapp_ai.circuit_allows(p_service text) RETURNS boolean
LANGUAGE plpgsql
AS $$
DECLARE v whatsapp_ai.service_circuits%ROWTYPE; v_now timestamptz := clock_timestamp();
BEGIN
    INSERT INTO whatsapp_ai.service_circuits(service) VALUES (p_service)
    ON CONFLICT (service) DO NOTHING;
    SELECT * INTO v FROM whatsapp_ai.service_circuits WHERE service=p_service FOR UPDATE;
    IF v.state = 'open' AND v.opened_until > v_now THEN RETURN FALSE; END IF;
    IF v.state = 'open' AND v.opened_until <= v_now THEN
        UPDATE whatsapp_ai.service_circuits SET state='half_open', probe_started_at=v_now, updated_at=v_now WHERE service=p_service;
        RETURN TRUE;
    END IF;
    IF v.state = 'half_open' AND v.probe_started_at IS NOT NULL AND v.probe_started_at > v_now - interval '30 seconds' THEN
        RETURN FALSE;
    END IF;
    UPDATE whatsapp_ai.service_circuits SET state='closed', consecutive_failures=0, updated_at=v_now WHERE service=p_service;
    RETURN TRUE;
END;
$$;

CREATE OR REPLACE FUNCTION whatsapp_ai.record_service_result(p_service text, p_success boolean, p_error_code text DEFAULT NULL) RETURNS text
LANGUAGE plpgsql
AS $$
DECLARE v whatsapp_ai.service_circuits%ROWTYPE; v_now timestamptz := clock_timestamp();
BEGIN
    INSERT INTO whatsapp_ai.service_circuits(service) VALUES (p_service) ON CONFLICT (service) DO NOTHING;
    SELECT * INTO v FROM whatsapp_ai.service_circuits WHERE service=p_service FOR UPDATE;
    IF p_success THEN
        UPDATE whatsapp_ai.service_circuits SET state='closed', consecutive_failures=0, window_started_at=NULL, opened_until=NULL, probe_started_at=NULL, last_error_code=NULL, updated_at=v_now WHERE service=p_service;
        RETURN 'closed';
    END IF;
    UPDATE whatsapp_ai.service_circuits SET consecutive_failures=v.consecutive_failures+1, last_error_code=p_error_code, updated_at=v_now WHERE service=p_service;
    IF v.consecutive_failures + 1 >= 5 THEN
        UPDATE whatsapp_ai.service_circuits SET state='open', opened_until=v_now + interval '60 seconds', window_started_at=v_now, updated_at=v_now WHERE service=p_service;
        RETURN 'open';
    END IF;
    RETURN v.state;
END;
$$;

COMMIT;
