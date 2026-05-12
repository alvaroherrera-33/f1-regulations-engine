"""Admin endpoints for maintenance operations."""
import logging
import time
from fastapi import APIRouter, BackgroundTasks
from sqlalchemy import text, select

from app.database import async_session
from app.models import ArticleDB

logger = logging.getLogger(__name__)
router = APIRouter(tags=["admin"])

# Simple in-memory status tracker for the background job
_reembed_status = {"running": False, "progress": "", "last_result": None}


async def _run_reembed():
    """Background task: truncate old embeddings, chunk articles, re-embed."""
    from ingestion.local_embeddings import get_embeddings_generator
    from ingestion.chunker import chunk_articles, EmbeddingChunk

    _reembed_status["running"] = True
    _reembed_status["progress"] = "Starting..."
    t0 = time.time()

    try:
        async with async_session() as db:
            # 1. Truncate
            _reembed_status["progress"] = "Truncating old embeddings..."
            await db.execute(text("TRUNCATE article_embeddings"))
            await db.commit()
            logger.info("Truncated article_embeddings")

            # 2. Fetch all articles
            _reembed_status["progress"] = "Fetching articles..."
            result = await db.execute(
                select(ArticleDB.id, ArticleDB.title, ArticleDB.content)
                .order_by(ArticleDB.id)
            )
            rows = result.all()
            logger.info("Fetched %d articles", len(rows))

            # Build lightweight objects with .title and .content for the chunker
            class _Art:
                def __init__(self, title, content):
                    self.title = title or ""
                    self.content = content or ""

            articles = [_Art(r.title, r.content) for r in rows]
            article_ids = [r.id for r in rows]

            # 3. Chunk
            _reembed_status["progress"] = "Chunking articles..."
            chunks = chunk_articles(articles)
            long_count = sum(1 for a in articles if len(a.content) > 1500)
            logger.info(
                "Chunked %d articles into %d chunks (%d split)",
                len(articles), len(chunks), long_count,
            )

            # 4. Generate embeddings in batches
            gen = get_embeddings_generator()
            BATCH = 256
            all_embeddings = []
            for i in range(0, len(chunks), BATCH):
                batch_chunks = chunks[i : i + BATCH]
                texts = [c.text for c in batch_chunks]
                embs = await gen.generate(texts)
                all_embeddings.extend(embs)
                _reembed_status["progress"] = (
                    f"Embedding... {len(all_embeddings)}/{len(chunks)}"
                )
                logger.info("Embedded %d/%d chunks", len(all_embeddings), len(chunks))

            # 5. Insert embeddings
            _reembed_status["progress"] = "Inserting embeddings..."
            INSERT_BATCH = 200
            for i in range(0, len(chunks), INSERT_BATCH):
                batch_c = chunks[i : i + INSERT_BATCH]
                batch_e = all_embeddings[i : i + INSERT_BATCH]
                values = []
                for chunk, emb in zip(batch_c, batch_e):
                    aid = article_ids[chunk.article_index]
                    values.append({"article_id": aid, "embedding": emb})
                await db.execute(
                    text(
                        "INSERT INTO article_embeddings (article_id, embedding) "
                        "VALUES (:article_id, :embedding)"
                    ),
                    values,
                )
                await db.commit()
                _reembed_status["progress"] = (
                    f"Inserted {min(i + INSERT_BATCH, len(chunks))}/{len(chunks)}"
                )

        elapsed = time.time() - t0
        result_msg = (
            f"Done: {len(articles)} articles -> {len(chunks)} chunks "
            f"({long_count} split) in {elapsed:.1f}s"
        )
        _reembed_status["last_result"] = result_msg
        _reembed_status["progress"] = result_msg
        logger.info("Re-embed complete: %s", result_msg)

    except Exception as exc:
        logger.exception("Re-embed failed")
        _reembed_status["progress"] = f"FAILED: {exc}"
        _reembed_status["last_result"] = f"FAILED: {exc}"
    finally:
        _reembed_status["running"] = False


@router.post("/admin/reembed")
async def reembed(background_tasks: BackgroundTasks):
    """Truncate article_embeddings and regenerate with chunking.

    Runs in the background — poll GET /api/admin/reembed/status to monitor.
    """
    if _reembed_status["running"]:
        return {"status": "already_running", "progress": _reembed_status["progress"]}

    background_tasks.add_task(_run_reembed)
    return {"status": "started", "message": "Re-embedding started in background"}


@router.get("/admin/reembed/status")
async def reembed_status():
    """Check progress of a running re-embed job."""
    return {
        "running": _reembed_status["running"],
        "progress": _reembed_status["progress"],
        "last_result": _reembed_status["last_result"],
    }
