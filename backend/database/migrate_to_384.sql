-- Migration: Update embedding dimension from 1536 to 384
-- This migration drops and recreates the article_embeddings table with the new dimension

-- Drop the existing index
DROP INDEX IF EXISTS idx_embeddings_vector;

-- Drop the existing table (CASCADE will also drop foreign key constraints)
DROP TABLE IF EXISTS article_embeddings CASCADE;

-- Recreate with new dimension
CREATE TABLE article_embeddings (
    id SERIAL PRIMARY KEY,
    article_id INTEGER REFERENCES articles(id) ON DELETE CASCADE,
    embedding vector(384) NOT NULL,  -- sentence-transformers/all-MiniLM-L6-v2 dimension
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(article_id)
);

-- Recreate the index
CREATE INDEX idx_embeddings_vector ON article_embeddings 
USING hnsw (embedding vector_cosine_ops);
