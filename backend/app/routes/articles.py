"""Article lookup endpoint."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Article, ArticleDB

router = APIRouter(tags=["articles"])


async def _explain_diff_with_llm(
    code: str, version_a: dict, version_b: dict
) -> str:
    """Call LLM to explain the differences between two article versions."""
    from app.llm.client import LLMClient
    client = LLMClient()

    content_a = (version_a or {}).get("content", "Not available")
    content_b = (version_b or {}).get("content", "Not available")
    year_a = (version_a or {}).get("year", "?")
    year_b = (version_b or {}).get("year", "?")
    issue_a = (version_a or {}).get("issue", "?")
    issue_b = (version_b or {}).get("issue", "?")

    prompt = f"""You are an expert in FIA Formula 1 regulations. Compare these two versions of Article {code}:

---VERSION A ({year_a}, Issue {issue_a})---
{content_a[:2000]}

---VERSION B ({year_b}, Issue {issue_b})---
{content_b[:2000]}

Provide a concise explanation (3-5 sentences) covering:
1. What specifically changed between the two versions
2. Whether the change is TECHNICAL (affects car design/performance) or EDITORIAL (clarification/wording)
3. The practical impact for F1 teams

Be specific and factual. If the content is identical or very similar, say so."""

    payload = {
        "model": client.model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 400,
        "temperature": 0.2,
    }
    response = await client._call_openrouter(payload, timeout=20.0)
    return response["choices"][0]["message"]["content"].strip()


@router.get("/compare")
async def compare_articles(
    code: str = Query(..., description="Article code, e.g. 3.1 or C4.1"),
    year_a: int = Query(..., ge=2000, le=2100),
    year_b: int = Query(..., ge=2000, le=2100),
    section: Optional[str] = Query(None, description="Filter by section: Technical, Sporting, Financial"),
    db: AsyncSession = Depends(get_db),
):
    """
    Compare a regulation article between two years.

    Returns the highest-issue version of the article for each year.
    Either version may be null if no data is available for that year.

    Example: GET /api/compare?code=C4.1&year_a=2025&year_b=2026&section=Technical
    """
    async def _fetch(year: int) -> Optional[dict]:
        stmt = (
            select(ArticleDB)
            .where(ArticleDB.article_code == code, ArticleDB.year == year)
        )
        if section:
            stmt = stmt.where(ArticleDB.section == section)
        stmt = stmt.order_by(desc(ArticleDB.issue)).limit(1)
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


@router.post("/compare/explain")
async def explain_article_diff(
    code: str = Query(..., description="Article code"),
    year_a: int = Query(..., ge=2000, le=2100),
    year_b: int = Query(..., ge=2000, le=2100),
    section: Optional[str] = Query(None, description="Filter by section"),
    db: AsyncSession = Depends(get_db),
):
    """
    AI-powered explanation of changes between two versions of a regulation article.

    Calls LLM to summarize: what changed, whether it's technical/editorial,
    and the practical impact for F1 teams.

    Example: POST /api/compare/explain?code=C4.1&year_a=2025&year_b=2026&section=Technical
    """
    async def _fetch(year: int) -> Optional[dict]:
        stmt = (
            select(ArticleDB)
            .where(ArticleDB.article_code == code, ArticleDB.year == year)
        )
        if section:
            stmt = stmt.where(ArticleDB.section == section)
        stmt = stmt.order_by(desc(ArticleDB.issue)).limit(1)
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

    try:
        explanation = await _explain_diff_with_llm(code, version_a, version_b)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"LLM service error: {exc}",
        )

    return {
        "article_code": code,
        "year_a": year_a,
        "year_b": year_b,
        "section": section,
        "version_a": version_a,
        "version_b": version_b,
        "explanation": explanation,
    }


@router.get("/articles/{article_code}", response_model=Article)
async def get_article(
    article_code: str,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve a specific article by its code."""
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
    """List articles with optional filters."""
    stmt = select(ArticleDB)

    if year:
        stmt = stmt.where(ArticleDB.year == year)
    if section:
        stmt = stmt.where(ArticleDB.section == section)
    if issue:
        stmt = stmt.where(ArticleDB.issue == issue)

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
