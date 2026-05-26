"""Pydantic models for API requests and responses."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

# ===== Request Models =====

class ChatRequest(BaseModel):
    """Chat query request."""

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "query": "What is the minimum car weight in 2026?",
                    "year": 2026,
                    "section": "Technical",
                }
            ]
        }
    }

    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Natural-language question about F1 regulations.",
        examples=["What is the minimum car weight in 2026?"],
    )
    year: Optional[int] = Field(
        None,
        ge=2000,
        le=2100,
        description="Filter to a specific regulation year (e.g. 2026).",
        examples=[2026],
    )
    section: Optional[str] = Field(
        None,
        description="Filter to a regulation section: Technical, Sporting, or Financial.",
        examples=["Technical"],
    )
    issue: Optional[int] = Field(
        None,
        ge=1,
        description="Filter to a specific issue/amendment number.",
        examples=[1],
    )


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
    # Validity fields (populated when article has cross-year diff data)
    validity: Optional[str] = None       # 'unchanged' | 'minor' | 'major' | 'removed' | None
    latest_year: Optional[int] = None    # most recent year this article exists in DB


class ChatResponse(BaseModel):
    """Chat query response with citations and agentic reasoning steps."""
    answer: str = Field(description="Markdown-formatted answer grounded in F1 regulation articles.")
    citations: List[Citation] = Field(description="Articles cited in the answer.")
    retrieved_count: int = Field(0, description="Total unique articles fetched across all search steps.")
    research_steps: List[dict] = Field([], description="Agentic reasoning steps: [{step, thought, action, query}].")
    query_id: Optional[int] = Field(None, description="Row ID in query_logs — use this to submit feedback.")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Normalized retrieval confidence (0–1).")


class FeedbackRequest(BaseModel):
    """User feedback on a chat response."""
    query_id: int
    was_helpful: bool


class StatsResponse(BaseModel):
    """Aggregate query statistics."""
    total_queries: int
    regulation_queries: int
    conversational_queries: int
    errors: int
    avg_response_ms: int
    positive_feedback: int
    negative_feedback: int
    last_query_at: Optional[datetime] = None


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
    # Validity (set by retriever after diff lookup)
    validity: Optional[str] = None
    latest_year: Optional[int] = None


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

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.database import Base


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


class ArticleDiff(Base):
    """Pre-computed cross-year similarity between articles with the same code."""
    __tablename__ = "article_diffs"

    id = Column(Integer, primary_key=True)
    article_code = Column(String(50), nullable=False)
    section = Column(String(50), nullable=False)
    year_from = Column(Integer, nullable=False)
    year_to = Column(Integer, nullable=False)
    similarity = Column(Float, nullable=False)
    change_type = Column(String(20), nullable=False)  # unchanged/minor/major/removed
    computed_at = Column(DateTime, server_default=func.now())


class FiaSyncLog(Base):
    """Log of FIA website sync checks."""
    __tablename__ = "fia_sync_log"

    id             = Column(Integer, primary_key=True)
    checked_at     = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    new_docs_found = Column(Integer, nullable=False, default=0)
    total_fia_docs = Column(Integer, nullable=False, default=0)
    error          = Column(Text)
