"""Hybrid retrieval: vector similarity + PostgreSQL full-text search + parent enrichment."""
import asyncio
import logging
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, text

from app.models import ArticleDB, ArticleEmbedding, Article
from ingestion.local_embeddings import get_embeddings_generator

logger = logging.getLogger(__name__)


class HybridRetriever:
    """Hybrid retrieval: vector similarity + full-text keyword search + parent enrichment."""

    # Cosine distance threshold — drop only articles that are truly unrelated.
    # (cosine distance: 0.0 = identical, 2.0 = opposite; 0.75 gives better recall
    #  while still filtering totally unrelated articles)
    SIMILARITY_THRESHOLD = 0.75

    def __init__(self, db: AsyncSession):
        """Initialize with database session."""
        self.db = db
        self.embeddings = get_embeddings_generator()

    async def retrieve(
        self,
        query: str,
        year: Optional[int] = None,
        section: Optional[str] = None,
        issue: Optional[int] = None,
        top_k: int = 5  # Final number of unique articles desired as context
    ) -> List[Article]:
        """
        Retrieve relevant articles using a multi-stage hybrid approach with deduplication.
        """
        # Step 1: Build metadata filters
        filters = []
        if year:
            filters.append(ArticleDB.year == year)
        if section:
            filters.append(ArticleDB.section == section)
        if issue:
            filters.append(ArticleDB.issue == issue)

        # Step 2: Run both retrieval passes with a broad candidate set
        # We fetch up to 30 candidates from each to ensure we find the latest issues
        candidate_k = 30
        vector_articles, fts_articles = await asyncio.gather(
            self._retrieve_by_vector(query, filters, candidate_k),
            self._retrieve_by_fulltext(query, filters, candidate_k),
        )

        # Step 3: Merge & deduplicate (prefer latest issue and vector results)
        articles = self._merge_and_deduplicate(
            vector_articles, fts_articles, top_k=top_k, detected_section=section
        )
        logger.debug("Retrieval: deduped to %d unique articles (top_k=%d)", len(articles), top_k)

        # Step 4: Enrich with parent articles (increases context depth)
        articles = await self._enrich_with_parents(articles, filters)

        return articles

    # ------------------------------------------------------------------ #
    #  Private helpers                                                     #
    # ------------------------------------------------------------------ #

    async def _retrieve_by_vector(
        self, query: str, filters: list, top_k: int
    ) -> List[Article]:
        """Vector similarity search using pgvector cosine distance."""
        query_embedding = await self.embeddings.generate_one(query)

        stmt = (
            select(
                ArticleDB,
                ArticleEmbedding.embedding.cosine_distance(query_embedding).label("distance"),
            )
            .join(ArticleEmbedding, ArticleDB.id == ArticleEmbedding.article_id)
        )
        if filters:
            stmt = stmt.where(and_(*filters))
        stmt = stmt.order_by("distance").limit(top_k)

        result = await self.db.execute(stmt)
        rows = result.all()

        articles = []
        for row in rows:
            article_db, distance = row[0], row[1]
            if distance > self.SIMILARITY_THRESHOLD:
                logger.debug("[Vector] Dropping %s (distance=%.4f > %.2f)", article_db.article_code, distance, self.SIMILARITY_THRESHOLD)
                continue
            articles.append(self._to_article(article_db))

        return articles

    async def _retrieve_by_fulltext(
        self, query: str, filters: list, top_k: int
    ) -> List[Article]:
        """
        Keyword full-text search using PostgreSQL tsvector.
        Returns articles whose content matches ANY of the query words.
        Falls back gracefully to an empty list if the query produces no tsquery tokens.
        """
        try:
            ts_query = func.websearch_to_tsquery("english", query)
            ts_vector = func.to_tsvector("english", ArticleDB.content)
            ts_rank = func.ts_rank(ts_vector, ts_query).label("rank")

            stmt = (
                select(ArticleDB, ts_rank)
                .where(ts_vector.op("@@")(ts_query))
            )
            if filters:
                stmt = stmt.where(and_(*filters))
            stmt = stmt.order_by(text("rank DESC")).limit(top_k)

            result = await self.db.execute(stmt)
            rows = result.all()
            return [self._to_article(row[0]) for row in rows]

        except Exception as e:
            logger.warning("[FTS] Full-text search failed (falling back): %s", e)
            return []

    def _merge_and_deduplicate(
        self,
        vector_results: List[Article],
        fts_results: List[Article],
        top_k: int = 7,
        detected_section: Optional[str] = None,
    ) -> List[Article]:
        """
        Merge results using Reciprocal Rank Fusion (RRF).
        RRF Score = sum(1 / (k + rank_i)) where k=60.

        When detected_section is provided, articles matching that section
        get a 1.2x score boost to prioritize same-section results.

        Also handles strict deduplication: for the same (code, section, year),
        we ONLY keep the one with the highest issue number.
        """
        k_rrf = 60
        SECTION_BOOST = 1.2
        scores: dict[tuple[str, str, int], float] = {}
        # Map canonical key to the best actual Article object (highest issue)
        best_articles: dict[tuple[str, str, int], Article] = {}

        def process_results(results: List[Article]):
            for rank, article in enumerate(results, start=1):
                # Canonical key: (article_code, section, year)
                key = (article.article_code, article.section, article.year)

                # Update RRF score
                scores[key] = scores.get(key, 0.0) + (1.0 / (k_rrf + rank))

                # Keep the instance with the highest issue number
                if key not in best_articles or article.issue > best_articles[key].issue:
                    best_articles[key] = article

        process_results(vector_results)
        process_results(fts_results)

        # Apply section boost: articles matching detected_section get 1.2x
        if detected_section:
            for key in scores:
                _code, art_section, _year = key
                if art_section and art_section.lower() == detected_section.lower():
                    scores[key] *= SECTION_BOOST

        # Sort by RRF score descending
        sorted_keys = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

        # Take top_k
        return [best_articles[key] for key in sorted_keys[:top_k]]

    async def _enrich_with_parents(
        self, articles: List[Article], filters: list
    ) -> List[Article]:
        """
        Enrich with parent articles, ensuring only the LATEST issue is retrieved.
        """
        seen_keys = {(a.article_code, a.section, a.year) for a in articles}
        # Parent requests: (parent_code, section, year)
        to_fetch = {
            (a.parent_code, a.section, a.year)
            for a in articles
            if a.parent_code and (a.parent_code, a.section, a.year) not in seen_keys
        }

        if not to_fetch:
            return articles

        extra_articles = []
        for p_code, p_sec, p_year in to_fetch:
            # Query for all issues of this parent, order by issue DESC, limit 1
            stmt = (
                select(ArticleDB)
                .where(
                    and_(
                        ArticleDB.article_code == p_code,
                        ArticleDB.section == p_sec,
                        ArticleDB.year == p_year
                    )
                )
                .order_by(ArticleDB.issue.desc())
                .limit(1)
            )
            result = await self.db.execute(stmt)
            row = result.scalar_one_or_none()
            if row:
                extra_articles.append(self._to_article(row))

        logger.debug("[Parent enrichment] Added %d latest-issue parent articles", len(extra_articles))
        return articles + extra_articles

    @staticmethod
    def _to_article(db_row: ArticleDB) -> Article:
        """Convert an ArticleDB ORM row to an Article Pydantic model."""
        return Article(
            id=db_row.id,
            article_code=db_row.article_code,
            title=db_row.title,
            content=db_row.content,
            year=db_row.year,
            section=db_row.section,
            issue=db_row.issue,
            level=db_row.level,
            parent_code=db_row.parent_code,
        )


async def retrieve_articles(
    db: AsyncSession,
    query: str,
    year: Optional[int] = None,
    section: Optional[str] = None,
    issue: Optional[int] = None,
    top_k: int = 12,
) -> List[Article]:
    """
    Convenience function for article retrieval.

    Usage:
        articles = await retrieve_articles(db, "What is the minimum weight?")
    """
    retriever = HybridRetriever(db)
    return await retriever.retrieve(query, year, section, issue, top_k)
