"""Hybrid retrieval: vector similarity + PostgreSQL full-text search + parent enrichment."""
import logging
from typing import Dict, List, Optional

from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Article, ArticleDB, ArticleDiff, ArticleEmbedding, ArticleReference
from ingestion.local_embeddings import get_embeddings_generator

logger = logging.getLogger(__name__)


class HybridRetriever:
    """Hybrid retrieval: vector similarity + full-text keyword search + parent enrichment."""

    # Cosine distance threshold — drop only articles that are truly unrelated.
    # (cosine distance: 0.0 = identical, 2.0 = opposite; 0.75 gives better recall
    # for most sections; Financial uses a wider threshold because D/E-prefix articles
    # have short, non-descriptive titles that produce lower similarity scores)
    #  while still filtering totally unrelated articles)
    SIMILARITY_THRESHOLD = 0.75
    # Financial articles have short/numeric titles → lower similarity scores → wider threshold
    SIMILARITY_THRESHOLD_FINANCIAL = 0.85

    def __init__(self, db: AsyncSession):
        """Initialize with database session."""
        self.db = db
        self.embeddings = get_embeddings_generator()
        self.confidence: float = 0.0  # set after _merge_and_deduplicate

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

        # Step 2: Run both retrieval passes sequentially on the same AsyncSession.
        # asyncio.gather would run them concurrently on the same self.db session,
        # which violates SQLAlchemy's requirement that an AsyncSession is not used
        # concurrently — causing intermittent InvalidRequestError / MissingGreenlet
        # 500s when two HTTP requests overlap on the single Render worker.
        # Sequential execution adds <200ms (negligible vs LLM latency of 5-30s).
        # candidate_k reduced from 30 to 20: corpus grew to 22k articles so 20 is
        # still more than enough candidates for the RRF merge while cutting DB scan time.
        candidate_k = 20
        vector_articles = await self._retrieve_by_vector(query, filters, candidate_k, section=section)
        fts_articles    = await self._retrieve_by_fulltext(query, filters, candidate_k)

        # Step 3: Merge & deduplicate (prefer latest issue and vector results)
        articles, top_score = self._merge_and_deduplicate(
            vector_articles, fts_articles, top_k=top_k, detected_section=section
        )
        # Normalize confidence: RRF max score ~1/61 ≈ 0.0164 at rank 1
        # We scale so that top score at rank 1 from both lists = 1.0
        max_possible = 2.0 / (60 + 1)  # two results at rank 1
        self.confidence = min(1.0, top_score / max_possible)
        logger.debug("Retrieval: deduped to %d unique articles (top_k=%d, confidence=%.2f)", len(articles), top_k, self.confidence)

        # Step 4: Expand context. With the structural layer (parent_id +
        # article_references populated by the structural pipeline) we assemble
        # the full subtree and follow cross-references deterministically.
        # Otherwise we fall back to the legacy single-level parent enrichment.
        if settings.structural_parser:
            articles = await self._assemble_subtree(articles)
            articles = await self._expand_xrefs(articles)
        else:
            articles = await self._enrich_with_parents(articles, filters)

        # Step 5: Annotate with cross-year validity info
        articles = await self._annotate_validity(articles)

        return articles

    # ------------------------------------------------------------------ #
    #  Private helpers                                                     #
    # ------------------------------------------------------------------ #

    async def _retrieve_by_vector(
        self, query: str, filters: list, top_k: int,
        section: Optional[str] = None,
    ) -> List[Article]:
        """Vector similarity search using pgvector cosine distance.

        Financial regulations use a wider distance threshold because articles
        in that section have short, non-descriptive titles (e.g. 'D12', 'E4.1')
        that produce lower embedding similarity scores even for relevant results.
        """
        # Pick threshold based on section
        threshold = (
            self.SIMILARITY_THRESHOLD_FINANCIAL
            if section and section.lower() == "financial"
            else self.SIMILARITY_THRESHOLD
        )

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
            if distance > threshold:
                logger.debug(
                    "[Vector] Dropping %s (distance=%.4f > %.2f threshold)",
                    article_db.article_code, distance, threshold,
                )
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
        # Level weights: Level 2 (sub-article) slightly preferred as the "sweet spot"
        # Level 1 is often a high-level overview; Level 3 can be too granular without context
        LEVEL_WEIGHTS = {1: 0.85, 2: 1.0, 3: 0.92}

        scores: dict[tuple[str, str, int], float] = {}
        # Map canonical key to the best actual Article object (highest issue)
        best_articles: dict[tuple[str, str, int], Article] = {}

        def process_results(results: List[Article]):
            for rank, article in enumerate(results, start=1):
                # Canonical key: (article_code, section, year)
                key = (article.article_code, article.section, article.year)

                # RRF score with level weighting
                level_w = LEVEL_WEIGHTS.get(article.level, 1.0)
                scores[key] = scores.get(key, 0.0) + (level_w / (k_rrf + rank))

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

        top_score = scores[sorted_keys[0]] if sorted_keys else 0.0
        return [best_articles[key] for key in sorted_keys[:top_k]], top_score

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

    # ------------------------------------------------------------------ #
    #  Structural assembly (Fase 4) — used when settings.structural_parser #
    # ------------------------------------------------------------------ #

    # Caps to keep the prompt (OpenRouter cost) and Render RAM bounded.
    MAX_CONTEXT_ARTICLES = 12  # was 24; smaller LLM context → faster steps, fewer timeouts
    MAX_ANCESTOR_DEPTH = 5

    async def _fetch_by_ids(self, ids: List[int]) -> List[Article]:
        """Fetch articles by primary key, preserving uniqueness."""
        ids = [i for i in dict.fromkeys(ids) if i is not None]
        if not ids:
            return []
        result = await self.db.execute(
            select(ArticleDB).where(ArticleDB.id.in_(ids))
        )
        return [self._to_article(r) for r in result.scalars().all()]

    async def _assemble_subtree(self, articles: List[Article]) -> List[Article]:
        """Assemble coherent subtrees around each hit.

        For every hit: climb the full ancestor chain (via parent_id) up to the
        root so a clause is never returned without its article header, and —
        when the hit is a header/sub-article (level 1 or 2) — pull its direct
        children so the specific sub-clause carrying the answer comes along.
        This is what lifts Financial recall (header hit → its D4.1/D4.2 children).

        Degrades gracefully: if parent_id is unpopulated (legacy data), the
        ancestor climb simply finds nothing and we keep the original hits.
        """
        by_id: Dict[int, Article] = {a.id: a for a in articles}

        # 1. Climb ancestors via parent_id (bounded depth).
        frontier = [a.parent_id for a in articles if a.parent_id]
        depth = 0
        while frontier and depth < self.MAX_ANCESTOR_DEPTH:
            missing = [pid for pid in frontier if pid not in by_id]
            fetched = await self._fetch_by_ids(missing)
            if not fetched:
                break
            for art in fetched:
                by_id[art.id] = art
            frontier = [art.parent_id for art in fetched if art.parent_id]
            depth += 1

        # 2. Descend to direct children for header/sub-article hits.
        header_ids = [a.id for a in articles if a.level in (1, 2)]
        if header_ids:
            result = await self.db.execute(
                select(ArticleDB).where(ArticleDB.parent_id.in_(header_ids))
            )
            for r in result.scalars().all():
                child = self._to_article(r)
                by_id.setdefault(child.id, child)

        assembled = list(by_id.values())
        # Dedupe by canonical key, keeping the highest issue.
        best: Dict[tuple, Article] = {}
        for a in assembled:
            key = (a.article_code, a.section, a.year)
            if key not in best or a.issue > best[key].issue:
                best[key] = a
        out = list(best.values())
        logger.debug("[Subtree] %d hits → %d articles after assembly", len(articles), len(out))
        return out[: self.MAX_CONTEXT_ARTICLES]

    async def _expand_xrefs(self, articles: List[Article]) -> List[Article]:
        """Follow resolved cross-references one hop (deterministic, 0 LLM).

        Replaces the LLM-driven cross-reference chasing inside the agentic loop:
        if an article says "subject to Article 3.2", we bring 3.2 into context
        directly. Respects the context budget.
        """
        if len(articles) >= self.MAX_CONTEXT_ARTICLES:
            return articles

        src_ids = [a.id for a in articles]
        if not src_ids:
            return articles

        result = await self.db.execute(
            select(ArticleReference.target_article_id)
            .where(
                and_(
                    ArticleReference.source_article_id.in_(src_ids),
                    ArticleReference.resolved.is_(True),
                    ArticleReference.target_article_id.isnot(None),
                )
            )
        )
        target_ids = [row[0] for row in result.all()]
        if not target_ids:
            return articles

        present = {a.id for a in articles}
        new_ids = [tid for tid in target_ids if tid not in present]
        budget = self.MAX_CONTEXT_ARTICLES - len(articles)
        extra = await self._fetch_by_ids(new_ids[:budget])
        if extra:
            logger.debug("[Xref] Added %d cross-referenced articles", len(extra))
        return articles + extra

    async def _annotate_validity(self, articles: List[Article]) -> List[Article]:
        """
        Batch-fetch cross-year validity from article_diffs and annotate each article.

        For each article at year Y < LATEST_YEAR, fetches the diff record with the
        highest year_to. Articles at LATEST_YEAR get validity='unchanged' automatically.
        Articles with no diff data keep validity=None.
        """
        if not articles:
            return articles

        LATEST_YEAR = 2026  # Update when a new season is indexed

        # Annotate latest-year articles directly — no DB lookup needed
        for article in articles:
            if article.year == LATEST_YEAR:
                article.validity = "unchanged"
                article.latest_year = LATEST_YEAR

        # For older articles, do a batch lookup
        older = [a for a in articles if a.year < LATEST_YEAR]
        if not older:
            return articles

        try:
            # Build tuples for SQL: collect unique (code, section, year) combos
            # We query by article_code IN (...) and then filter in Python — simpler
            codes = list({a.article_code for a in older})
            stmt = (
                select(
                    ArticleDiff.article_code,
                    ArticleDiff.section,
                    ArticleDiff.year_from,
                    ArticleDiff.year_to,
                    ArticleDiff.change_type,
                )
                .where(ArticleDiff.article_code.in_(codes))
                .order_by(ArticleDiff.year_to.desc())
            )
            result = await self.db.execute(stmt)
            rows = result.all()

            # Build lookup: (code, section, year_from) -> (change_type, latest year_to seen)
            diff_map: dict = {}
            for code, section, y_from, y_to, change_type in rows:
                key = (code, section, y_from)
                if key not in diff_map:  # already sorted by year_to desc — first is best
                    diff_map[key] = (change_type, y_to)

            for article in older:
                key = (article.article_code, article.section, article.year)
                if key in diff_map:
                    article.validity, article.latest_year = diff_map[key]

        except Exception as e:
            logger.warning("Validity annotation failed (non-critical): %s", e)

        return articles

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
            parent_id=getattr(db_row, "parent_id", None),
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
               
