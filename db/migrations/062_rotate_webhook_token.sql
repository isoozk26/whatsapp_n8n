-- 062: fresh-install/korumali operator senaryosu icin GUC 'app.webhook_token'
-- uzerinden idempotent settings kurulumu. Canli token rotation icin bu migration
-- kullanilmaz; db/ops/rotate_webhook.sql parametreli operator prosedurudur.
-- GUC ve migration ayni psql oturumunda calistirilmalidir.
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
