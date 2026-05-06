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
    UNIQUE(article_id)
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
