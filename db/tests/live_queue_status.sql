SELECT
  (SELECT count(*) FROM whatsapp_ai.batches WHERE status='pending') AS pending_batches,
  (SELECT count(*) FROM whatsapp_ai.batches WHERE status='processing') AS processing_batches,
  (SELECT count(*) FROM whatsapp_ai.deliveries WHERE status IN ('pending','failed','sending')) AS queued_deliveries,
  (SELECT count(*) FROM whatsapp_ai.deliveries WHERE status='dead') AS dead_deliveries;
