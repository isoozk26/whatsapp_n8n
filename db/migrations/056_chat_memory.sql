BEGIN;

CREATE TABLE IF NOT EXISTS whatsapp_ai.chat_memory (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  text NOT NULL,
    role        text NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content     text NOT NULL,
    source_key  text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT clock_timestamp()
);

ALTER TABLE whatsapp_ai.chat_memory
    ADD COLUMN IF NOT EXISTS source_key text;

UPDATE whatsapp_ai.chat_memory
SET source_key = md5(role || ':' || content || ':' || id::text)
WHERE source_key IS NULL OR source_key = '';

ALTER TABLE whatsapp_ai.chat_memory
    ALTER COLUMN source_key SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS chat_memory_session_role_source_key
    ON whatsapp_ai.chat_memory (session_id, role, source_key);

CREATE INDEX IF NOT EXISTS chat_memory_session_created_idx
    ON whatsapp_ai.chat_memory (session_id, created_at DESC);

CREATE OR REPLACE FUNCTION whatsapp_ai.cleanup_chat_memory(
    p_ttl_hours integer DEFAULT 24
) RETURNS integer
LANGUAGE plpgsql
AS $$
DECLARE
    v_count integer;
BEGIN
    IF p_ttl_hours IS NULL OR p_ttl_hours < 1 THEN
        RAISE EXCEPTION 'p_ttl_hours must be at least 1';
    END IF;

    DELETE FROM whatsapp_ai.chat_memory
    WHERE created_at < clock_timestamp() - make_interval(hours => p_ttl_hours);
    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$;

COMMIT;
