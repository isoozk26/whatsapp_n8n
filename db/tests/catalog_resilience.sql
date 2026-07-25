\set ON_ERROR_STOP on

INSERT INTO whatsapp_ai.settings(key,value) VALUES
  ('webhook_token','test-token'),('admin_phone_a','9001'),('admin_phone_b','9002')
ON CONFLICT (key) DO UPDATE SET value=excluded.value;

DO $$
DECLARE v_import uuid; v_result jsonb;
BEGIN
  v_import := whatsapp_ai.begin_catalog_import('test-checksum','fixture.csv');
  INSERT INTO whatsapp_ai.mann_vehicle_catalog(
    import_id,source_id,brand,model_series,engine,engine_codes,power_kw,power_bhp,
    displacement_ccm,fuel_type_raw,production_start,production_end,brand_norm,model_norm,engine_norm)
  VALUES
    (v_import,1,'Fiat','Egea','1.6 Multijet',ARRAY['55280444'],96,130,1598,'Dizel',2020,2024,'FIAT','EGEA','1 6 MULTIJET'),
    (v_import,2,'Fiat','Egea','1.3 Multijet',ARRAY['55266963'],70,95,1248,'Dizel',2020,2024,'FIAT','EGEA','1 3 MULTIJET');
  PERFORM whatsapp_ai.refresh_catalog_import_stats(v_import);
  PERFORM whatsapp_ai.activate_catalog_import(v_import,'test-checksum');
  v_result := whatsapp_ai.resolve_vehicle_context('905000000001','Fiat','Egea','1.6 Multijet',NULL,NULL,NULL,NULL,NULL,2022,NULL);
  IF v_result->>'status' <> 'unique' OR (v_result->>'candidateCount')::integer <> 1 THEN
    RAISE EXCEPTION 'unique catalog match failed: %',v_result;
  END IF;
  v_result := whatsapp_ai.resolve_vehicle_context('905000000002','Fiat','Egea',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL);
  IF v_result->>'status' <> 'missing_required' THEN RAISE EXCEPTION 'required fields failed: %',v_result; END IF;
END $$;

DO $$
BEGIN
  PERFORM whatsapp_ai.record_service_result('openai',false,'fixture') FROM generate_series(1,5);
  IF whatsapp_ai.circuit_allows('openai') THEN RAISE EXCEPTION 'open circuit allowed request'; END IF;
  UPDATE whatsapp_ai.service_circuits SET opened_until=clock_timestamp()-interval '1 second' WHERE service='openai';
  IF NOT whatsapp_ai.circuit_allows('openai') THEN RAISE EXCEPTION 'half-open probe not allowed'; END IF;
  IF whatsapp_ai.circuit_allows('openai') THEN RAISE EXCEPTION 'second half-open probe allowed'; END IF;
  PERFORM whatsapp_ai.record_service_result('openai',true,NULL);
END $$;

SELECT 'catalog_resilience: PASS';
