-- Migration 003: enable Row Level Security on all tables
-- Apply this on the Supabase SQL Editor.
-- Safe to run multiple times (uses IF NOT EXISTS / DO blocks).
-- Origen: security_review.docx hallazgo C-02, plan docs/internal/SECURITY_PLAN.md

-- ──────────────────────────────────────────────
-- Tablas de contenido público (lectura anon OK)
-- ──────────────────────────────────────────────
ALTER TABLE articles            ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents           ENABLE ROW LEVEL SECURITY;
ALTER TABLE article_embeddings  ENABLE ROW LEVEL SECURITY;
ALTER TABLE article_diffs       ENABLE ROW LEVEL SECURITY;

-- Crear policies de lectura pública solo si no existen
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'articles' AND policyname = 'anon_read'
    ) THEN
        CREATE POLICY anon_read ON articles
            FOR SELECT TO anon USING (true);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'documents' AND policyname = 'anon_read'
    ) THEN
        CREATE POLICY anon_read ON documents
            FOR SELECT TO anon USING (true);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'article_embeddings' AND policyname = 'anon_read'
    ) THEN
        CREATE POLICY anon_read ON article_embeddings
            FOR SELECT TO anon USING (true);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'article_diffs' AND policyname = 'anon_read'
    ) THEN
        CREATE POLICY anon_read ON article_diffs
            FOR SELECT TO anon USING (true);
    END IF;
END
$$;

-- ──────────────────────────────────────────────────────────────────────────────
-- Tablas sensibles (logs/sync): cero acceso anon; solo service-role del backend
-- ──────────────────────────────────────────────────────────────────────────────
ALTER TABLE query_logs    ENABLE ROW LEVEL SECURITY;
ALTER TABLE fia_sync_log  ENABLE ROW LEVEL SECURITY;
-- Sin CREATE POLICY → ningún rol excepto service_role puede acceder.
-- El backend usa la DATABASE_URL con credenciales de service-role, por lo que
-- no se ve afectado por RLS.
