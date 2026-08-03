-- 062: webhook_token'i GUC 'app.webhook_token' uzerinden idempotent set eder.
-- Sabit/lekeli token dosyada tutulmaz. Runner GUC'u su sekilde verir:
--   psql -v ON_ERROR_STOP=1 -c "SET app.webhook_token = :'tok';" -f 062_...sql   (ayni oturumda)
-- veya: SELECT set_config('app.webhook_token', :'tok', false); \i 062_...sql
DO $$
DECLARE v_tok text := current_setting('app.webhook_token', true);
BEGIN
    IF v_tok IS NULL OR length(trim(v_tok)) < 16 THEN
        RAISE NOTICE '062: app.webhook_token verilmedi, atlaniyor (mevcut deger korunuyor)';
        RETURN;
    END IF;
    INSERT INTO whatsapp_ai.settings(key, value)
    VALUES ('webhook_token', v_tok)
    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = clock_timestamp();
END$$;
