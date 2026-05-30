-- Migration 0001 — Structural layer (Priority 1)
-- Additive and backward-compatible: existing queries/ingestion keep working.
-- Safe to run multiple times (IF NOT EXISTS / DEFAULT guards everywhere).
-- 0 LLM calls anywhere in the structural pipeline.
-- See docs/internal/STRUCTURE_PLAN.md (Fase 1).

BEGIN;

-- 1. Resolved parent pointer (coexists with legacy string parent_code).
ALTER TABLE articles ADD COLUMN IF NOT EXISTS parent_id INTEGER
    REFERENCES articles(id) ON DELETE SET NULL;

-- 2. Synthetic-stub flag.
ALTER TABLE articles ADD COLUMN IF NOT EXISTS is_stub BOOLEAN NOT NULL DEFAULT FALSE;

-- 3. Structural validation outcome.
ALTER TABLE articles ADD COLUMN IF NOT EXISTS structural_status VARCHAR(20)
    NOT NULL DEFAULT 'unvalidated';

CREATE INDEX IF NOT EXISTS idx_articles_parent_id ON articles(parent_id);
CREATE INDEX IF NOT EXISTS idx_articles_struct_status ON articles(structural_status);

-- 4. Cross-references (deterministic extraction).
CREATE TABLE IF NOT EXISTS article_references (
    id SERIAL PRIMARY KEY,
    source_article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    target_code VARCHAR(50) NOT NULL,
    target_article_id INTEGER REFERENCES articles(id) ON DELETE SET NULL,
    resolved BOOLEAN NOT NULL DEFAULT FALSE,
    raw_text VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(source_article_id, target_code)
);

CREATE INDEX IF NOT EXISTS idx_xref_source ON article_references(source_article_id);
CREATE INDEX IF NOT EXISTS idx_xref_target ON article_references(target_article_id);

-- 5. Per-document structural audit snapshot.
CREATE TABLE IF NOT EXISTS document_structure_audit (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    year INTEGER NOT NULL,
    section VARCHAR(50) NOT NULL,
    issue INTEGER NOT NULL,
    total_articles INTEGER DEFAULT 0,
    orphan_count INTEGER DEFAULT 0,
    numbering_gap_count INTEGER DEFAULT 0,
    toc_suspect_count INTEGER DEFAULT 0,
    xref_total INTEGER DEFAULT 0,
    xref_resolved INTEGER DEFAULT 0,
    passed BOOLEAN DEFAULT FALSE,
    computed_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(document_id)
);

CREATE INDEX IF NOT EXISTS idx_struct_audit_doc
    ON document_structure_audit(year, section, issue);

COMMIT;
