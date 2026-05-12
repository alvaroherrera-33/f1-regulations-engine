"""FastAPI main application."""
import logging
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.config import settings
from app.models import HealthResponse
from app.database import engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="F1 Regulations RAG Engine",
    description="Legal-grade RAG system for FIA Formula 1 regulations",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_checks():
    """Validate critical configuration at startup."""
    errors = []

    if not settings.openrouter_api_key or settings.openrouter_api_key.startswith("sk-or-REPLACE"):
        errors.append("OPENROUTER_API_KEY is missing or placeholder.")

    if not settings.database_url:
        errors.append("DATABASE_URL is missing.")

    if errors:
        for err in errors:
            logger.critical("Startup configuration error: %s", err)
        # Log but don't crash -- let health endpoint report the issue
    else:
        logger.info("Startup OK. Model=%s", settings.llm_model)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    db_status = "connected"
    try:
        async with engine.connect() as conn:
            await conn.execute(select(1))
    except Exception as e:
        logger.error("Database health check failed: %s", e)
        db_status = "unhealthy"

    return HealthResponse(
        status="healthy" if db_status == "connected" else "degraded",
        timestamp=datetime.now(),
        database=db_status
    )


from app.database import async_session
from app.models import StatusResponse, Document, ArticleDB, ArticleEmbedding
from sqlalchemy import func


@app.get("/status", response_model=StatusResponse)
async def system_status():
    """Get system indexing status."""
    async with async_session() as db:
        doc_count = await db.scalar(select(func.count(Document.id)))
        art_count = await db.scalar(select(func.count(ArticleDB.id)))
        emb_count = await db.scalar(select(func.count(ArticleEmbedding.id)))

    return StatusResponse(
        documents_count=doc_count or 0,
        articles_count=art_count or 0,
        embeddings_count=emb_count or 0
    )


@app.get("/warmup")
async def warmup():
    """
    Keep-alive / warm-up endpoint.

    Calling this endpoint ensures the embedding model is loaded in memory so
    that the first real user query doesn't pay the cold-start penalty.
    Set a cron job (e.g. UptimeRobot) to ping this every 10 minutes.
    """
    from ingestion.local_embeddings import get_embeddings_generator
    try:
        gen = get_embeddings_generator()
        # A tiny embed call to force the model weights into RAM
        gen.generate(["warmup"])
        return {"status": "warm", "model": "all-MiniLM-L6-v2"}
    except Exception as exc:
        logger.warning("Warmup failed: %s", exc)
        return {"status": "cold", "error": str(exc)}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "F1 Regulations RAG Engine API",
        "version": "0.1.0",
        "docs": "/docs"
    }


from app.routes import upload, chat, articles, admin
app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(articles.router, prefix="/api", tags=["articles"])
app.include_router(admin.router, prefix="/api", tags=["admin"])
