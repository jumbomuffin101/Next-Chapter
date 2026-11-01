-- Tables owned by the admin/onboarding features (not in work/database/models.py).
-- `python -m backend.app.init_db` runs this after the generated schema.sql. All statements are IF NOT EXISTS.

-- Education start year (added after the shared DB was created; CREATE TABLE IF NOT EXISTS won't add it)
ALTER TABLE education ADD COLUMN IF NOT EXISTS start_year INTEGER;
-- The job a salary entry was for (picked in the salary history); deleting the job keeps the salary, unlinked
ALTER TABLE salary_records ADD COLUMN IF NOT EXISTS work_experience_id UUID REFERENCES work_experience(id) ON DELETE SET NULL;

-- Career-team follow-up on an alumnus: the newest row is the current status.
CREATE TABLE IF NOT EXISTS action_log (
  id         UUID PRIMARY KEY,
  alumni_id  UUID NOT NULL REFERENCES alumni(id) ON DELETE CASCADE,
  status     VARCHAR(20) NOT NULL CHECK (status IN ('open', 'contacted', 'resolved')),
  note       TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_action_log_alumni ON action_log (alumni_id, created_at DESC);

-- "I'd like some help": an alumnus asking the career team for support.
CREATE TABLE IF NOT EXISTS support_requests (
  id         UUID PRIMARY KEY,
  alumni_id  UUID NOT NULL REFERENCES alumni(id) ON DELETE CASCADE,
  message    TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_support_requests_alumni ON support_requests (alumni_id, created_at DESC);

-- Alumni network: appearing to other alumni is opt-in (visible defaults to false). LinkedIn is self-entered and optional.
CREATE TABLE IF NOT EXISTS network_profiles (
  alumni_id    UUID PRIMARY KEY REFERENCES alumni(id) ON DELETE CASCADE,
  visible      BOOLEAN NOT NULL DEFAULT FALSE,
  linkedin_url TEXT,
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_network_profiles_visible ON network_profiles (visible) WHERE visible;

-- Personal invite links: one code per alumnus, made the first time their dashboard asks for it.
CREATE TABLE IF NOT EXISTS invite_codes (
  code       VARCHAR(16) PRIMARY KEY,
  alumni_id  UUID NOT NULL UNIQUE REFERENCES alumni(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- How a profile was created: through an alumnus's invite link, or the in-room QR code for a cohort.
CREATE TABLE IF NOT EXISTS signup_sources (
  alumni_id  UUID PRIMARY KEY REFERENCES alumni(id) ON DELETE CASCADE,
  source     VARCHAR(10) NOT NULL CHECK (source IN ('invite', 'room')),
  inviter_id UUID REFERENCES alumni(id) ON DELETE SET NULL,
  cohort     VARCHAR(20),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_signup_sources_inviter ON signup_sources (inviter_id);

-- TKH's alumni roster, including people who have no profile yet. Cohort invites go to roster people who have not joined.
CREATE TABLE IF NOT EXISTS alumni_roster (
  email      VARCHAR(255) PRIMARY KEY,
  first_name VARCHAR(100) NOT NULL,
  last_name  VARCHAR(100) NOT NULL DEFAULT '',
  cohort     VARCHAR(20) NOT NULL,
  is_demo    BOOLEAN NOT NULL DEFAULT FALSE
);

-- Automated emails. Every email is written here; nothing is sent yet (no mail provider is connected), so sent_at stays null.
-- A sender would read rows WHERE sent_at IS NULL, deliver them, and stamp sent_at.
CREATE TABLE IF NOT EXISTS email_outbox (
  id         UUID PRIMARY KEY,
  kind       VARCHAR(20) NOT NULL CHECK (kind IN ('cohort_invite', 'just_joined', 'invite_worked')),
  to_email   VARCHAR(255) NOT NULL,
  to_name    VARCHAR(201),
  subject    TEXT NOT NULL,
  body       TEXT NOT NULL,
  about_id   UUID NOT NULL REFERENCES alumni(id) ON DELETE CASCADE,  -- the alumnus whose joining triggered it
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  sent_at    TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_email_outbox_once ON email_outbox (kind, to_email, about_id);
-- A roster person is invited once, by the first cohort-mate who joins.
CREATE UNIQUE INDEX IF NOT EXISTS ux_email_outbox_invite_once ON email_outbox (to_email) WHERE kind = 'cohort_invite';
CREATE INDEX IF NOT EXISTS ix_email_outbox_created ON email_outbox (created_at DESC);

-- Switches the career team controls from the admin Automation page (no row = the default).
CREATE TABLE IF NOT EXISTS app_settings (
  key        VARCHAR(50) PRIMARY KEY,
  value      JSONB NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
