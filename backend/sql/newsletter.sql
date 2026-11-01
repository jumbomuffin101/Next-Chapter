-- Prompt 2: additive migration. APPLY ONLY WITH SEPARATE OWNER APPROVAL.
-- No alumni backfill or automatic consent. Missing preference row means OFF.
BEGIN;
CREATE TABLE IF NOT EXISTS newsletter_subscriptions (
  alumni_id UUID PRIMARY KEY REFERENCES alumni(id) ON DELETE CASCADE,
  subscribed BOOLEAN NOT NULL DEFAULT false,
  token_nonce VARCHAR(64) NOT NULL UNIQUE,
  subscribed_at TIMESTAMPTZ,
  unsubscribed_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS newsletter_deliveries (
  id UUID PRIMARY KEY,
  alumni_id UUID NOT NULL REFERENCES alumni(id) ON DELETE CASCADE,
  month DATE NOT NULL,
  status VARCHAR(20) NOT NULL,
  error_code VARCHAR(50),
  provider_message_id VARCHAR(255),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_newsletter_alumni_month UNIQUE (alumni_id, month),
  CONSTRAINT newsletter_delivery_status CHECK (status IN ('dry_run','attempting','accepted','retryable','failed','unknown'))
);
-- No anonymous REST policies: consent and dispatch go through the backend.
ALTER TABLE newsletter_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE newsletter_deliveries ENABLE ROW LEVEL SECURITY;
COMMIT;
