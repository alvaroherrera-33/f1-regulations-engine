"""Pydantic models for API requests and responses."""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


# ===== Request Models =====

class ChatRequest(BaseModel):
    """Chat query request."""
    query: str = Field(..., min_length=1, max_length=1000)
    year: Optional[int] = Field(None, ge=2000, le=2100)
    section: Optional[str] = None
    issue: Optional[int] = Field(None, ge=1)


class UploadRequest(BaseModel):
    """PDF upload metadata."""
    year: int = Field(..., ge=2000, le=2100)
    section: str = Field(..., min_length=1)
    issue: int = Field(..., ge=1)


# ===== Response Models =====

class Citation(BaseModel):
    """Article citation."""
    article_code: str
    title: str
    excerpt: str
    year: int
    section: str
    issue: int


class ChatResponse(BaseModel):
    """Chat query response with citations and agentic reasoning steps."""
    answer: str
    citations: List[Citation]
    retrieved_count: int = 0
    research_steps: List[dict] = []  # List of {'thought': str, 'action': str, 'query': str}


class Article(BaseModel):
    """Article data."""
    id: int
    article_code: str
    title: str
    content: str
    year: int
    section: str
    issue: int
    level: int
    parent_code: Optional[str] = None


class UploadResponse(BaseModel):
    """Upload status response."""
    job_id: str
    status: str
    message: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: datetime
    database: str


class StatusResponse(BaseModel):
    """System indexing status response."""
    documents_count: int
    articles_count: int
    embeddings_count: int


# ===== Database ORM Models (SQLAlchemy) =====

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base
from pgvector.sqlalchemy import Vector


class Document(Base):
    """Document ORM model."""
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    year = Column(Integer, nullable=False)
    section = Column(String(50), nullable=False)
    issue = Column(Integer, nullable=False)
    file_path = Column(String(500))
    uploaded_at = Column(DateTime, server_default=func.now())


class ArticleDB(Base):
    """Article ORM model."""
    __tablename__ = "articles"
    
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"))
    article_code = Column(String(50), nullable=False)
    parent_code = Column(String(50))
    level = Column(Integer, nullable=False)
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    year = Column(Integer, nullable=False)
    section = Column(String(50), nullable=False)
    issue = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class ArticleEmbedding(Base):
    """Article embedding ORM model."""
    __tablename__ = "article_embeddings"
    
    id = Column(Integer, primary_key=True)
    article_id = Column(Integer, ForeignKey("articles.id"))
    embedding = Column(Vector(384))  # sentence-transformers/all-MiniLM-L6-v2
    created_at = Column(DateTime, server_default=func.now())
