"""Article lookup endpoint."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.database import get_db
from app.models import ArticleDB, Article

router = APIRouter(tags=["articles"])


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
        year=article_db.year,
        section=article_db.section,
        issue=article_db.issue,
        level=article_db.level,
        parent_code=article_db.parent_code
    )


@router.get("/articles", response_model=List[Article])
async def list_articles(
    year: int = None,
    section: str = None,
    issue: int = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """
    List articles with optional filters.
    
    Args:
        year: Filter by year
        section: Filter by section
        issue: Filter by issue number
        limit: Maximum number of results (default 50)
        db: Database session
        
    Returns:
        List of Article objects
    """
    stmt = select(ArticleDB)
    
    # Apply filters
    if year:
        stmt = stmt.where(ArticleDB.year == year)
    if section:
        stmt = stmt.where(ArticleDB.section == section)
    if issue:
        stmt = stmt.where(ArticleDB.issue == issue)
    
    # Order and limit
    stmt = stmt.order_by(ArticleDB.article_code).limit(limit)
    
    result = await db.execute(stmt)
    articles_db = result.scalars().all()
    
    return [
        Article(
            id=art.id,
            article_code=art.article_code,
            title=art.title,
            content=art.content,
            year=art.year,
            section=art.section,
            issue=art.issue,
            level=art.level,
            parent_code=art.parent_code
        )
        for art in articles_db
    ]
