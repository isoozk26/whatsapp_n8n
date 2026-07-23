-- Migration 006: PostgreSQL Müşteri Talep & Stok Analitik Görünümleri (Views)
-- FiltreOto Müşteri İstekleri Havuzunun Analizi için

CREATE OR REPLACE VIEW whatsapp_ai.v_top_requested_codes AS
SELECT 
    elem->>'code' AS product_code,
    COUNT(*) AS total_requests,
    MAX(completed_at) AS last_requested_at
FROM whatsapp_ai.ai_audit_ledger,
LATERAL jsonb_array_elements(COALESCE(entities->'productCodes', '[]'::jsonb)) AS elem
WHERE elem->>'code' IS NOT NULL AND elem->>'code' <> ''
GROUP BY elem->>'code'
ORDER BY total_requests DESC;

CREATE OR REPLACE VIEW whatsapp_ai.v_top_requested_vehicles AS
SELECT 
    elem->>'brand' AS brand,
    elem->>'model' AS model,
    elem->>'year' AS year,
    elem->>'engine' AS engine,
    COUNT(*) AS total_requests,
    MAX(completed_at) AS last_requested_at
FROM whatsapp_ai.ai_audit_ledger,
LATERAL jsonb_array_elements(COALESCE(entities->'vehicles', '[]'::jsonb)) AS elem
WHERE elem->>'brand' IS NOT NULL OR elem->>'model' IS NOT NULL
GROUP BY elem->>'brand', elem->>'model', elem->>'year', elem->>'engine'
ORDER BY total_requests DESC;

CREATE OR REPLACE VIEW whatsapp_ai.v_customer_activity_summary AS
SELECT 
    b.sender_number,
    b.sender_name,
    COUNT(a.id) AS total_conversations,
    MAX(b.last_message_at) AS last_message_at,
    COALESCE(m.enabled, false) AS is_manual_mode
FROM whatsapp_ai.batches b
LEFT JOIN whatsapp_ai.ai_audit_ledger a ON a.sender_number = b.sender_number
LEFT JOIN whatsapp_ai.manual_modes m ON m.sender_number = b.sender_number
GROUP BY b.sender_number, b.sender_name, m.enabled
ORDER BY total_conversations DESC;
