"""Ingestion pipeline orchestration."""
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert, select
from typing import List

from app.database import async_session
from app.models import Document, ArticleDB, ArticleEmbedding
from ingestion.pdf_parser import parse_pdf, ParsedArticle
from ingestion.local_embeddings import LocalEmbeddingsGenerator


class IngestionPipeline:
    """Orchestrates PDF ingestion: parse → embed → store."""
    
    def __init__(self, db_session: AsyncSession):
        """Initialize with database session."""
        self.db = db_session
        self.embeddings_generator = LocalEmbeddingsGenerator()
    
    async def ingest_document(
        self,
        pdf_path: str,
        document_id: int
    ) -> dict:
        """
        Ingest a document: parse PDF, generate embeddings, store in database.
        
        Args:
            pdf_path: Path to PDF file
            document_id: ID of document record in database
            
        Returns:
            Statistics about the ingestion
        """
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
        
        # Step 3: Generate embeddings
        print("Generating embeddings...")
        texts = [f"{art.title}\n{art.content}" for art in articles]
        embeddings = await self.embeddings_generator.generate(texts)
        print(f"Generated {len(embeddings)} embeddings")
        
        # Step 4: Store articles and embeddings
        print("Storing in database...")
        article_ids = await self._store_articles(articles, document)
        await self._store_embeddings(article_ids, embeddings)
        await self.db.commit()
        
        print(f"Ingestion complete for document {document_id}")
        
        return {
            "status": "success",
            "message": f"Successfully ingested {len(articles)} articles",
            "articles_count": len(articles),
            "embeddings_count": len(embeddings)
        }
    
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
    
    async def _store_embeddings(
        self,
        article_ids: List[int],
        embeddings: List[List[float]]
    ):
        """Store embeddings in database."""
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
