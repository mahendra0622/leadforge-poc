-- ============================================================
-- LeadForge Update — Database Migration
-- Apply with: psql $DATABASE_URL -f migrations/apply_leadforge_updates.sql
-- ============================================================

-- ── 1. Signal source reference columns ──────────────────────
ALTER TABLE signals ADD COLUMN IF NOT EXISTS source_url   VARCHAR(500);
ALTER TABLE signals ADD COLUMN IF NOT EXISTS source_file  VARCHAR(255);
ALTER TABLE signals ADD COLUMN IF NOT EXISTS source_page  INTEGER;
ALTER TABLE signals ADD COLUMN IF NOT EXISTS source_label VARCHAR(120);

-- ── 2. User Gmail + extended profile columns ─────────────────
ALTER TABLE users ADD COLUMN IF NOT EXISTS gmail_email         VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS gmail_refresh_token TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS gmail_connected_at  TIMESTAMP WITH TIME ZONE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_provider       VARCHAR(50) DEFAULT 'password';
ALTER TABLE users ADD COLUMN IF NOT EXISTS tagline             VARCHAR(500);
ALTER TABLE users ADD COLUMN IF NOT EXISTS products            JSONB;
ALTER TABLE users ADD COLUMN IF NOT EXISTS case_studies        JSONB;
ALTER TABLE users ADD COLUMN IF NOT EXISTS integrations        JSONB;

-- Make hashed_password nullable (Google-login users have no password)
ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL;

-- ── 3. AIMessage Gmail send tracking columns ─────────────────
ALTER TABLE ai_messages ADD COLUMN IF NOT EXISTS sent_at          TIMESTAMP WITH TIME ZONE;
ALTER TABLE ai_messages ADD COLUMN IF NOT EXISTS gmail_message_id VARCHAR(255);

-- ── 4. Email thread links table ──────────────────────────────
CREATE TABLE IF NOT EXISTS email_thread_links (
    id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id      UUID         NOT NULL REFERENCES companies(id),
    user_id         UUID         NOT NULL REFERENCES users(id),
    gmail_thread_id VARCHAR(255) NOT NULL,
    match_method    VARCHAR(50)  DEFAULT 'auto',
    linked_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- After applying: run python backfill_signal_sources.py --dry-run
-- ============================================================
