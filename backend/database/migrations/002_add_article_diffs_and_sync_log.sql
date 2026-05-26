-- Migration 002: add article_diffs and fia_sync_log tables
-- Apply this on the Supabase SQL Editor if upgrading an existing database.
-- Safe to run multiple times (uses IF NOT EXISTS / ON CONFLICT DO NOTHING).

-- Cross-year article diffs (computed by scripts/compute_diffs.py)
CREATE TABLE IF NOT EXISTS article_diffs (
    id SERIAL PRIMARY KEY,
    article_code VARCHAR(50) NOT NULL,
    section VARCHAR(50) NOT NULL,
    year_from INTEGER NOT NULL,
    year_to INTEGER NOT NULL,
    issue_from INTEGER NOT NULL,
    issue_to INTEGER NOT NULL,
    similarity FLOAT,
    change_type VARCHAR(20),
    computed_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(article_code, section, year_from, year_to)
);

CREATE INDEX IF NOT EXISTS idx_diffs_lookup
    ON article_diffs(article_code, section, year_from);

-- FIA auto-sync audit log
CREATE TABLE IF NOT EXISTS fia_sync_log (
    id SERIAL PRIMARY KEY,
    checked_at TIMESTAMP DEFAULT NOW(),
    new_docs_found INTEGER DEFAULT 0,
    new_articles_indexed INTEGER DEFAULT 0,
    total_fia_docs INTEGER DEFAULT 0,
    error TEXT,
    status VARCHAR(20) DEFAULT 'ok'
);

-- query_logs (may already exist in prod — add missing columns defensively)
CREATE TABLE IF NOT EXISTS query_logs (
    id SERIAL PRIMARY KEY,
    query TEXT NOT NULL,
    intent VARCHAR(20),
    year INTEGER,
    section VARCHAR(50),
    answer TEXT,
    retrieved_count INTEGER DEFAULT 0,
    response_time_ms INTEGER,
    was_helpful BOOLEAN,
    error_occurred BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
