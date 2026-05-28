"""Pydantic models for API requests and responses."""
from datetime import datetime
from typing import List, Literal, Optional

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
    section: Optional[Literal["Technical", "Sporting", "Financial"]] = Field(
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
    query_id: Optional[int] = Field(None, description="Row ID in query_logs -- use this to submit feedback.")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Normalized retrieval confidence (0-1).")
    feedback_token: Optional[str] = Field(None, description="HMAC token -- send this back with feedback to prove ownership.")  # A-03


class FeedbackRequest(BaseModel):
    """User feedback on a chat response."""
    query_id: int
    was_helpful: bool
    feedback_token: Optional[str] = None  # A-03: HMAC token returned in ChatResponse


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

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Document(Base):
    """Represents an ingested regulation PDF document."""
    __tablename__ = "documents"

    id         = Column(Integer, primary_key=True)
    name       = Column(String(255), nullable=False)
    year       = Column(Integer, nullable=False)
    section    = Column(String(50), nullable=False)
    issue      = Column(Integer, nullable=False, default=1)
    file_path  = Column(String(512))
    created_at = Column(DateTime)

    articles = relationship("ArticleDB", back_populates="document", cascade="all, delete-orphan")


class ArticleDB(Base):
    """Represents a single regulation article extracted from a document."""
    __tablename__ = "articles"

    id           = Column(Integer, primary_key=True)
    document_id  = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"))
    article_code = Column(String(50), nullable=False)
    title        = Column(Text)
    content      = Column(Text, nullable=False)
    year         = Column(Integer)
    section      = Column(String(50))
    issue        = Column(Integer)
    level        = Column(Integer, default=1)
    parent_code  = Column(String(50))
    # Validity annotation (populated by retriever, not stored in DB)
    validity     = Column(String(20), nullable=True)
    latest_year  = Column(Integer, nullable=True)

    document   = relationship("Document", back_populates="articles")
    embeddings = relationship("ArticleEmbedding", back_populates="article", cascade="all, delete-orphan")


class ArticleEmbedding(Base):
    """Stores the vector embedding for an article (or a chunk of an article)."""
    __tablename__ = "article_embeddings"

    id         = Column(Integer, primary_key=True)
    article_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"))
    chunk_index = Column(Integer, default=0)

    article = relationship("ArticleDB", back_populates="embeddings")


class ArticleDiff(Base):
    """Cross-year diff between two versions of an article."""
    __tablename__ = "article_diffs"

    id            = Column(Integer, primary_key=True)
    article_code  = Column(String(50), nullable=False)
    section       = Column(String(50))
    year_a        = Column(Integer, nullable=False)
    year_b        = Column(Integer, nullable=False)
    similarity    = Column(Float)
    change_type   = Column(String(20))


class FiaSyncLog(Base):
    """Records each time we checked fia.com for new regulation PDFs."""
    __tablename__ = "fia_sync_log"

    id             = Column(Integer, primary_key=True)
    checked_at     = Column(DateTime(timezone=True))
    total_fia_docs = Column(Integer, default=0)
    new_docs_found = Column(Integer, default=0)
    error_message  = Column(Text)
