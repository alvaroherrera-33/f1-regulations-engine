"""Ingestion pipeline orchestration."""
from typing import Dict, List

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.models import (
    ArticleDB,
    ArticleEmbedding,
    ArticleReference,
    Document,
    DocumentStructureAudit,
)
from ingestion.chunker import chunk_articles
from ingestion.local_embeddings import LocalEmbeddingsGenerator
from ingestion.pdf_parser import ParsedArticle, parse_pdf
from ingestion.structural_parser import StructuralArticle, parse_pdf_structural
from ingestion.structural_validation import compute_audit


class IngestionPipeline:
    """Orchestrates PDF ingestion: parse → embed → store."""

    def __init__(self, db_session: AsyncSession):
        """Initialize with database session."""
        self.db = db_session
        self.embeddings_generator = LocalEmbeddingsGenerator()

    async def ingest_document(
        self,
        pdf_path: str,
        document_id: int,
        allow_degraded: bool = True,
    ) -> dict:
        """
        Ingest a document: parse PDF, generate embeddings, store in database.

        Args:
            pdf_path: Path to PDF file
            document_id: ID of document record in database
            allow_degraded: when False and the structural validation gate fails
                (orphans or TOC coverage below threshold), abort without storing.
                Only consulted when settings.structural_parser is True.

        Returns:
            Statistics about the ingestion
        """
        if settings.structural_parser:
            return await self._ingest_structural(pdf_path, document_id, allow_degraded)

        print(f"Starting ingestion for document {document_id}")

        # Step 1: Parse PDF
        print("Parsing PDF...")
        articles = parse_pdf(pdf_path)
        print(f"Extracted {len(articles)} articles")

        if not articles:
            return {
                "status": "error",
                "message": "No articles found in PDF",
                "articles_count": 0
            }

        # Step 2: Get document metadata
        stmt = select(Document).where(Document.id == document_id)
        result = await self.db.execute(stmt)
        document = result.scalar_one_or_none()

        if not document:
            return {
                "status": "error",
                "message": "Document not found",
                "articles_count": 0
            }

        # Step 3: Store articles first (we need article IDs for embeddings)
        print("Storing articles in database...")
        article_ids = await self._store_articles(articles, document)

        # Step 4: Chunk long articles for better embedding quality
        chunks = chunk_articles(articles)
        long_count = sum(1 for a in articles if len(a.content) > 1500)
        print(f"Chunked {len(articles)} articles into {len(chunks)} chunks "
              f"({long_count} articles were split)")

        # Step 5: Generate embeddings (one per chunk)
        # For Financial section: enrich short/numeric article titles with their parent title
        # so embeddings carry more semantic context (e.g. "D12" alone is not descriptive).
        print("Generating embeddings...")
        if document.section and document.section.lower() == "financial":
            parent_title_map = {
                a.article_code: a.title for a in articles if a.parent_code is None
            }
            enriched_texts = []
            for chunk, article in zip(chunks, [articles[c.article_index] for c in chunks]):
                if article.parent_code and article.parent_code in parent_title_map:
                    parent_title = parent_title_map[article.parent_code]
                    # Replace "title\ncontent" with "parent_title > title\ncontent"
                    enriched_text = chunk.text.replace(
                        f"{article.title}\n",
                        f"{parent_title} > {article.title}\n",
                        1,
                    )
                    enriched_texts.append(enriched_text)
                else:
                    enriched_texts.append(chunk.text)
            texts = enriched_texts
        else:
            texts = [chunk.text for chunk in chunks]
        embeddings = await self.embeddings_generator.generate(texts)
        print(f"Generated {len(embeddings)} embeddings")

        # Step 6: Store embeddings mapped to article IDs via chunk.article_index
        await self._store_chunk_embeddings(article_ids, chunks, embeddings)
        await self.db.commit()

        print(f"Ingestion complete for document {document_id}")

        return {
            "status": "success",
            "message": f"Successfully ingested {len(articles)} articles ({len(chunks)} chunks)",
            "articles_count": len(articles),
            "embeddings_count": len(embeddings)
        }

    async def _ingest_structural(
        self,
        pdf_path: str,
        document_id: int,
        allow_degraded: bool,
    ) -> dict:
        """Structural ingestion path (Fase 2/3): TOC-aware parse + validation gate.

        Stores parent_id / is_stub / structural_status, the cross-reference
        graph, and a per-document structural audit row. 0 LLM calls.
        """
        print(f"[structural] Starting ingestion for document {document_id}")

        result = parse_pdf_structural(pdf_path)
        articles: List[StructuralArticle] = result.articles
        print(f"[structural] Parsed {len(articles)} articles "
              f"(TOC available={result.toc_available}, "
              f"{len(result.expected_from_toc)} TOC codes)")

        if not articles:
            return {"status": "error", "message": "No articles found in PDF",
                    "articles_count": 0}

        # --- Validation gate (before any writes, so a failed doc stores nothing) ---
        audit = compute_audit(articles, result.expected_from_toc)
        cov_str = f"{audit.toc_coverage:.2%}" if audit.toc_coverage is not None else "n/a"
        print(f"[structural] Gate: orphans={audit.orphan_count} "
              f"gaps={audit.numbering_gap_count} toc_coverage={cov_str} "
              f"passed={audit.passed}")
        if not audit.passed and not allow_degraded:
            detail = {"orphans": audit.orphans[:20],
                      "missing_from_toc": audit.missing_from_toc[:20]}
            return {"status": "rejected",
                    "message": "Structural validation gate failed "
                               "(use allow_degraded to force).",
                    "articles_count": 0, "audit": detail}

        # --- Document metadata ---
        result_doc = await self.db.execute(
            select(Document).where(Document.id == document_id)
        )
        document = result_doc.scalar_one_or_none()
        if not document:
            return {"status": "error", "message": "Document not found",
                    "articles_count": 0}

        # --- Store articles, capture code -> id ---
        code_to_id = await self._store_articles_structural(articles, document)

        # --- Resolve parent_id from parent_code within this document ---
        await self._resolve_parent_ids(articles, code_to_id)

        # --- Store and resolve the cross-reference graph ---
        xref_total, xref_resolved = await self._store_references(articles, code_to_id)
        audit.xref_total = xref_total
        audit.xref_resolved = xref_resolved

        # --- Embeddings (same chunk → embed path as the legacy flow) ---
        parsed = [a.to_parsed_article() for a in articles]
        chunks = chunk_articles(parsed)
        texts = [c.text for c in chunks]
        embeddings = await self.embeddings_generator.generate(texts)
        article_ids = [code_to_id[a.article_code] for a in articles]
        await self._store_chunk_embeddings(article_ids, chunks, embeddings)

        # --- Persist the per-document audit ---
        await self._store_structure_audit(document, audit)

        await self.db.commit()
        print(f"[structural] Ingestion complete for document {document_id}")

        return {
            "status": "success" if audit.passed else "degraded",
            "message": f"Ingested {len(articles)} articles "
                       f"({len(chunks)} chunks); xref {xref_resolved}/{xref_total} resolved",
            "articles_count": len(articles),
            "embeddings_count": len(embeddings),
            "audit": {
                "orphan_count": audit.orphan_count,
                "numbering_gap_count": audit.numbering_gap_count,
                "toc_coverage": audit.toc_coverage,
                "xref_resolution_rate": audit.xref_resolution_rate,
                "passed": audit.passed,
            },
        }

    async def _store_articles_structural(
        self, articles: List[StructuralArticle], document: Document
    ) -> Dict[str, int]:
        """Insert structural articles, returning {article_code: id}."""
        code_to_id: Dict[str, int] = {}
        for a in articles:
            stmt = insert(ArticleDB).values(
                document_id=document.id,
                article_code=a.article_code,
                parent_code=a.parent_code,
                level=a.level,
                title=a.title,
                content=a.content,
                year=document.year,
                section=document.section,
                issue=document.issue,
                is_stub=a.is_stub,
                structural_status=a.structural_status,
            ).returning(ArticleDB.id)
            res = await self.db.execute(stmt)
            code_to_id[a.article_code] = res.scalar_one()
        return code_to_id

    async def _resolve_parent_ids(
        self, articles: List[StructuralArticle], code_to_id: Dict[str, int]
    ) -> None:
        """Set articles.parent_id from parent_code, within this document scope."""
        for a in articles:
            if a.parent_code and a.parent_code in code_to_id:
                await self.db.execute(
                    update(ArticleDB)
                    .where(ArticleDB.id == code_to_id[a.article_code])
                    .values(parent_id=code_to_id[a.parent_code])
                )

    async def _store_references(
        self, articles: List[StructuralArticle], code_to_id: Dict[str, int]
    ) -> tuple[int, int]:
        """Persist the cross-reference graph; resolve targets within this doc.

        Returns (total, resolved).
        """
        total = 0
        resolved = 0
        for a in articles:
            src_id = code_to_id[a.article_code]
            for ref in a.references:
                total += 1
                target_id = code_to_id.get(ref.target_code)
                if target_id is not None:
                    resolved += 1
                await self.db.execute(
                    insert(ArticleReference).values(
                        source_article_id=src_id,
                        target_code=ref.target_code,
                        target_article_id=target_id,
                        resolved=target_id is not None,
                        raw_text=ref.raw_text[:255],
                    )
                )
        return total, resolved

    async def _store_structure_audit(
        self, document: Document, audit
    ) -> None:
        """Write the per-document structural audit snapshot."""
        await self.db.execute(
            insert(DocumentStructureAudit).values(
                document_id=document.id,
                year=document.year,
                section=document.section,
                issue=document.issue,
                total_articles=audit.total_articles,
                orphan_count=audit.orphan_count,
                numbering_gap_count=audit.numbering_gap_count,
                toc_suspect_count=audit.toc_suspect_count,
                xref_total=audit.xref_total,
                xref_resolved=audit.xref_resolved,
                passed=audit.passed,
            )
        )

    async def _store_articles(
        self,
        articles: List[ParsedArticle],
        document: Document
    ) -> List[int]:
        """Store articles in database and return their IDs."""
        article_ids = []

        for article in articles:
            stmt = insert(ArticleDB).values(
                document_id=document.id,
                article_code=article.article_code,
                parent_code=article.parent_code,
                level=article.level,
                title=article.title,
                content=article.content,
                year=document.year,
                section=document.section,
                issue=document.issue
            ).returning(ArticleDB.id)

            result = await self.db.execute(stmt)
            article_id = result.scalar_one()
            article_ids.append(article_id)

        return article_ids

    async def _store_chunk_embeddings(
        self,
        article_ids: List[int],
        chunks: list,
        embeddings: List[List[float]],
    ):
        """Store embeddings mapped back to articles via chunk.article_index.

        Each chunk carries an article_index that points into article_ids.
        Multiple chunks can share the same article_id (long articles).
        """
        for chunk, embedding in zip(chunks, embeddings):
            article_id = article_ids[chunk.article_index]
            stmt = insert(ArticleEmbedding).values(
                article_id=article_id,
                embedding=embedding,
            )
            await self.db.execute(stmt)

    async def _store_embeddings(
        self,
        article_ids: List[int],
        embeddings: List[List[float]]
    ):
        """Store embeddings in database (legacy 1:1 mapping)."""
        for article_id, embedding in zip(article_ids, embeddings):
            stmt = insert(ArticleEmbedding).values(
                article_id=article_id,
                embedding=embedding
            )
            await self.db.execute(stmt)


async def ingest_document(pdf_path: str, document_id: int) -> dict:
    """
    Convenience function to ingest a document.

    Usage:
        result = await ingest_document("/path/to/pdf", doc_id)
    """
    async with async_session() as db:
        pipeline = IngestionPipeline(db)
        return await pipeline.ingest_document(pdf_path, document_id)


# For testing
if __name__ == "__main__":
    async def test():
        # This would require a real PDF and database
        result = await ingest_document("/path/to/test.pdf", 1)
        print(result)

    # asyncio.run(test())
