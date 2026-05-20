"""Article lookup endpoint."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional

from app.database import get_db
from app.models import ArticleDB, Article

router = APIRouter(tags=["articles"])


@router.get("/compare")
async def compare_articles(
    code: str = Query(..., description="Article code, e.g. 3.1 or C4.1"),
    year_a: int = Query(..., ge=2000, le=2100),
    year_b: int = Query(..., ge=2000, le=2100),
    db: AsyncSession = Depends(get_db),
):
    """
    Compare a regulation article between two years.

    Returns the highest-issue version of the article for each year.
    Either version may be null if no data is available for that year.

    Example: GET /api/compare?code=3.1&year_a=2025&year_b=2026
    """
    async def _fetch(year: int) -> Optional[dict]:
        stmt = (
            select(ArticleDB)
            .where(ArticleDB.article_code == code, ArticleDB.year == year)
            .order_by(desc(ArticleDB.issue))
            .limit(1)
        )
        result = await db.execute(stmt)
        art = result.scalar_one_or_none()
        if not art:
            return None
        return {
            "article_code": art.article_code,
            "title": art.title,
            "content": art.content,
            "year": art.year,
            "section": art.section,
            "issue": art.issue,
        }

    version_a = await _fetch(year_a)
    version_b = await _fetch(year_b)

    if version_a is None and version_b is None:
        raise HTTPException(
            status_code=404,
            detail=f"Article '{code}' not found for {year_a} or {year_b}.",
        )

    return {"version_a": version_a, "version_b": version_b}


@router.get("/articles/{article_code}", response_model=Article)
async def get_article(
    article_code: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve a specific article by its code.
    
    Example: GET /api/articles/3.7.1
    
    Args:
        article_code: The article code (e.g., "3.7", "12.4.a")
        db: Database session
        
    Returns:
        Article object with full content
    """
    stmt = select(ArticleDB).where(ArticleDB.article_code == article_code)
    result = await db.execute(stmt)
    article_db = result.scalar_one_or_none()
    
    if not article_db:
        raise HTTPException(
            status_code=404,
            detail=f"Article {article_code} not found"
        )
    
    return Article(
        id=article_db.id,
        article_code=article_db.article_code,
        title=article_db.title,
        content=article_db.content,
      