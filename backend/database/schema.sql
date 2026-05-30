-- F1 Regulations RAG Engine - Database Schema
-- PostgreSQL with pgvector extension for hybrid retrieval

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Documents table: stores regulation PDF metadata
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    year INTEGER NOT NULL,
    section VARCHAR(50) NOT NULL,  -- 'Technical', 'Sporting', 'Financial', etc.
    issue INTEGER NOT NULL,
    file_path VARCHAR(500),
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(year, section, issue)
);

-- Articles table: core entity with hierarchical structure
CREATE TABLE articles (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    article_code VARCHAR(50) NOT NULL,  -- e.g., "33.3.b"
    parent_code VARCHAR(50),            -- e.g., "33.3" for hierarchical reference
    level INTEGER NOT NULL,             -- 1 = Article, 2 = Sub-article, 3 = Clause
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    year INTEGER NOT NULL,
    section VARCHAR(50) NOT NULL,
    issue INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(article_code, year, section, issue)
);

-- Article embeddings table: vector representations for semantic search
CREATE TABLE article_embeddings (
    id SERIAL PRIMARY KEY,
    article_id INTEGER REFERENCES articles(id) ON DELETE CASCADE,
    embedding vector(384) NOT NULL,  -- sentence-transformers/all-MiniLM-L6-v2 dimension
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- No UNIQUE on article_id: chunked articles have multiple embeddings
);

-- Indexes for performance

-- Fast filtering by year, section, issue
CREATE INDEX idx_articles_filters ON articles(year, section, issue);

-- Article code lookup
CREATE INDEX idx_articles_code ON articles(article_code);

-- Parent-child hierarchy navigation
CREATE INDEX idx_articles_parent ON articles(parent_code);

-- Vector similarity search (HNSW index for approximate nearest neighbor)
CREATE INDEX idx_embeddings_vector ON article_embeddings 
USING hnsw (embedding vector_cosine_ops);

-- Document lookup
CREATE INDEX idx_documents_year_section ON documents(year, section);

-- Query logs: every chat request + feedback
CREATE TABLE IF NOT EXISTS query_logs (
    id SERIAL PRIMARY KEY,
    query TEXT NOT NULL,
    intent VARCHAR(20),                -- 'REGULATIONS' | 'CONVERSATIONAL'
    year INTEGER,
    section VARCHAR(50),
    answer TEXT,
    retrieved_count INTEGER DEFAULT 0,
    response_time_ms INTEGER,
    was_helpful BOOLEAN,               -- NULL until user submits feedback
    error_occurred BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Cross-year article diffs (computed by scripts/compute_diffs.py, 0 LLM calls)
CREATE TABLE IF NOT EXISTS article_diffs (
    id SERIAL PRIMARY KEY,
    article_code VARCHAR(50) NOT NULL,
    section VARCHAR(50) NOT NULL,
    year_from INTEGER NOT NULL,
    year_to INTEGER NOT NULL,
    issue_from INTEGER NOT NULL,
    issue_to INTEGER NOT NULL,
    similarity FLOAT,                  -- cosine similarity of embeddings (0-1)
    change_type VARCHAR(20),           -- 'unchanged' | 'minor' | 'major' | 'added' | 'removed'
    computed_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(article_code, section, year_from, year_to)
);

CREATE INDEX IF NOT EXISTS idx_diffs_lookup
    ON article_diffs(article_code, section, year_from);

-- FIA auto-sync audit log (populated by scripts/fia_scraper.py cron)
CREATE TABLE IF NOT EXISTS fia_sync_log (
    id SERIAL PRIMARY KEY,
    checked_at TIMESTAMP DEFAULT NOW(),
    new_docs_found INTEGER DEFAULT 0,
    new_articles_indexed INTEGER DEFAULT 0,
    total_fia_docs INTEGER DEFAULT 0,
    error TEXT,
    status VARCHAR(20) DEFAULT 'ok'   -- 'ok' | 'error' | 'no_changes'
);

-- ============================================================================
-- STRUCTURAL LAYER (Priority 1) — additive, backward-compatible
-- See docs/internal/STRUCTURE_PLAN.md. All structural work is 0 LLM calls.
-- These statements are also emitted standalone in migrations/0001_structural_layer.sql
-- ============================================================================

-- Resolved parent pointer (FK to articles.id). Coexists with the legacy
-- string parent_code; structural retrieval prefers parent_id when present.
ALTER TABLE articles ADD COLUMN IF NOT EXISTS parent_id INTEGER
    REFERENCES articles(id) ON DELETE SET NULL;

-- TRUE for synthetic parent stubs created when a referenced parent has no
-- real content of its own (see pdf_parser._fill_missing_parents).
ALTER TABLE articles ADD COLUMN IF NOT EXISTS is_stub BOOLEAN NOT NULL DEFAULT FALSE;

-- Structural validation outcome for the article:
--   'ok' | 'orphan' | 'numbering_gap' | 'toc_suspect' | 'unvalidated'
ALTER TABLE articles ADD COLUMN IF NOT EXISTS structural_status VARCHAR(20)
    NOT NULL DEFAULT 'unvalidated';

CREATE INDEX IF NOT EXISTS idx_articles_parent_id ON articles(parent_id);
CREATE INDEX IF NOT EXISTS idx_articles_struct_status ON articles(structural_status);

-- Cross-references extracted deterministically from article content
-- (e.g. "see Article 3.2", "in accordance with C4.1"). 0 LLM calls.
CREATE TABLE IF NOT EXISTS article_references (
    id SERIAL PRIMARY KEY,
    source_article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    target_code VARCHAR(50) NOT NULL,         -- referenced article_code as written
    target_article_id INTEGER REFERENCES articles(id) ON DELETE SET NULL,  -- resolved, NULL if dangling
    resolved BOOLEAN NOT NULL DEFAULT FALSE,
    raw_text VARCHAR(255),                     -- the matched mention text
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(source_article_id, target_code)
);

CREATE INDEX IF NOT EXISTS idx_xref_source ON article_references(source_article_id);
CREATE INDEX IF NOT EXISTS idx_xref_target ON article_references(target_article_id);

-- Per-document structural audit snapshot (written by the validation gate
-- during ingestion). Mirrors scripts/structural_audit.py metrics per document.
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
    passed BOOLEAN DEFAULT FALSE,              -- did it clear the validation gate
    computed_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(document_id)
);

CREATE INDEX IF NOT EXISTS idx_struct_audit_doc
    ON document_structure_audit(year, section, issue);
