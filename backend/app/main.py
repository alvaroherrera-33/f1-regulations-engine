"""FastAPI main application."""
import logging
import time
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import select

from app.config import settings
from app.database import engine
from app.models import HealthResponse
from app.rate_limit import get_client_ip  # A-01: real IP from X-Forwarded-For

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Rate limiter -- uses real client IP; default 100 req/min across all routes
limiter = Limiter(key_func=get_client_ip, default_limits=["100/minute"])

app = FastAPI(
    title="F1 Regulations RAG Engine",
    description="Legal-grade RAG system for FIA Formula 1 regulations",
    version="0.1.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST"],                                   # M-01: no wildcard
    allow_headers=["Authorization", "Content-Type", "X-Admin-Key"], # M-01: explicit list
)


# A-05: Security response headers
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-site"
    return response


@app.on_event("startup")
async def startup_checks():
    """Validate critical configuration at startup."""
    errors = []

    # API key only required for hosted providers (OpenRouter). Keyless local
    # servers like Ollama don't need one.
    _is_openrouter = "openrouter.ai" in settings.llm_base_url
    if _is_openrouter and (not settings.openrouter_api_key or settings.openrouter_api_key.startswith("sk-or-REPLACE")):
        errors.append("OPENROUTER_API_KEY is missing or placeholder.")

    if not settings.database_url:
        errors.append("DATABASE_URL is missing.")

    # M-01: wildcard origins + credentials is a security misconfiguration
    if "*" in settings.cors_origins_list:
        errors.append(
            "ALLOWED_ORIGINS contains '*' but allow_credentials=True -- "
            "this combination is forbidden by the CORS spec and is a security risk."
        )

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


# M-08: /status TTL cache — avoids a DB round-trip on every frontend page load.
# The status counts change only when PDFs are ingested (rare), so a 60-second
# cache is safe and prevents scraping the endpoint for enumeration.
_status_cache: dict = {"ts": 0.0, "data": None}
_STATUS_TTL = 60  # seconds

from sqlalchemy import func

from app.database import async_session
from app.models import ArticleDB, ArticleEmbedding, Document, StatusResponse


@app.get("/status", response_model=StatusResponse)
async def system_status():
    """Get system indexing status (cached for 60 s)."""
    now = time.monotonic()
    if _status_cache["data"] is not None and (now - _status_cache["ts"]) < _STATUS_TTL:
        return _status_cache["data"]

    async with async_session() as db:
        doc_count = await db.scalar(select(func.count(Document.id)))
        art_count = await db.scalar(select(func.count(ArticleDB.id)))
        emb_count = await db.scalar(select(func.count(ArticleEmbedding.id)))

    result = StatusResponse(
        documents_count=doc_count or 0,
        articles_count=art_count or 0,
        embeddings_count=emb_count or 0
    )
    _status_cache["ts"] = now
    _status_cache["data"] = result
    return result


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
        await gen.generate(["warmup"])
        return {"status": "warm", "model": "all-MiniLM-L6-v2"}
    except Exception as exc:
        logger.warning("Warmup failed: %s", exc)
        return {"status": "cold", "error": "Embedding model failed to load."}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "F1 Regulations RAG Engine API",
        "version": "0.1.0",
        "docs": "/docs"
    }


from app.routes import admin, articles, chat, sync, upload

app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(articles.router, prefix="/api", tags=["articles"])
app.include_router(admin.router, prefix="/api", tags=["admin"])
app.include_router(sync.router, prefix="/api", tags=["sync"])
