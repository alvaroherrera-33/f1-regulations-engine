"""Admin endpoints for maintenance operations.

Note: The re-embedding task is run externally (not via this endpoint)
because the Render free tier has only 512MB RAM, which is insufficient
to embed all articles in a single process alongside the web server.

All admin endpoints require X-Admin-Key authentication.
"""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text

from app.auth import require_admin_key
from app.database import async_session
from app.models import ArticleDB, ArticleEmbedding

logger = logging.getLogger(__name__)
router = APIRouter(tags=["admin"])


@router.get("/admin/embedding-stats")
async def embedding_stats(_: None = Depends(require_admin_key)):
    """Check embedding coverage and chunking stats. Requires X-Admin-Key."""
    async with async_session() as db:
        total_articles = await db.scalar(select(func.count(ArticleDB.id)))
        total_embeddings = await db.scalar(select(func.count(ArticleEmbedding.id)))
        unique_articles = await db.scalar(
            select(func.count(func.distinct(ArticleEmbedding.article_id)))
        )
        multi_embed = await db.scalar(text(
            "SELECT count(*) FROM ("
            "  SELECT article_id FROM article_embeddings"
            "  GROUP BY article_id HAVING count(*) > 1"
            ") sub"
        ))

    return {
        "total_articles": total_articles,
        "total_embeddings": total_embeddings,
        "unique_articles_with_embeddings": unique_articles,
        "articles_with_multiple_chunks": multi_embed,
        "coverage_pct": round(100 * unique_articles / total_articles, 1) if total_articles else 0,
    }
