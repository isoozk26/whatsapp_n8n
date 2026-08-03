-- Operator-only psql script. The secret is supplied at runtime, never stored here.
\if :{?webhook_token}
UPDATE whatsapp_ai.settings
SET value = :'webhook_token', updated_at = clock_timestamp()
WHERE key = 'webhook_token';

\if :ROW_COUNT = 0
  \echo 'webhook_token setting row is missing'
  \quit 1
\endif
\else
  \echo 'webhook_token variable is required'
  \quit 1
\endif
