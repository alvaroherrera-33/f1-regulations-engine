"""FIA sync endpoint — check for new regulation PDFs and optionally ingest them."""
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin_key
from app.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["sync"])

# M-07: generic error constants — never store raw exception text in the DB.
# Raw exceptions can leak internal paths, DB URLs, or scraper internals.
_ERR_FIA_UNREACHABLE = "FIA website unreachable"
_ERR_SCRAPER_GENERIC = "Scraper error"


# ------------------------------------------------------------------ #
# Response models                                                      #
# ------------------------------------------------------------------ #

class NewDocInfo(BaseModel):
    year: int
    section: str
    issue: int
    filename: str


class SyncStatusResponse(BaseModel):
    """Latest FIA sync status — returned by GET /api/sync/status."""
    last_checked: Optional[str] = None   # ISO datetime string
    total_fia_docs: int = 0
    new_docs_found: int = 0              # last run
    last_error: Optional[str] = None
    db_total_docs: int = 0               # documents currently in our DB


class SyncCheckResponse(BaseModel):
    """Result of POST /api/sync/check — runs a live check against fia.com."""
    total_fia: int
    already_indexed: int
    new: int
    ingested: int
    new_docs: list[NewDocInfo]
    errors: list[str]
    dry_run: bool


# ------------------------------------------------------------------ #
# Endpoints                                                            #
# ------------------------------------------------------------------ #

@router.get("/sync/status", response_model=SyncStatusResponse)
async def sync_status(db: AsyncSession = Depends(get_db)):
    """
    Return the cached status of the last FIA sync check.

    This is cheap (single DB query) and safe to call on every page load.
    No authentication required — returns non-sensitive aggregate data only.
    """
    try:
        # Latest sync log entry
        log_result = await db.execute(text("""
            SELECT checked_at, total_fia_docs, new_docs_found, error
            FROM fia_sync_log
            ORDER BY checked_at DESC
            LIMIT 1
        """))
        log_row = log_result.fetchone()

        # Current doc count in our DB
        count_result = await db.execute(text("SELECT COUNT(*) FROM documents"))
        db_total = count_result.scalar() or 0

        if not log_row:
            return SyncStatusResponse(db_total_docs=db_total)

        return SyncStatusResponse(
            last_checked=log_row[0].isoformat() if log_row[0] else None,
            total_fia_docs=log_row[1] or 0,
            new_docs_found=log_row[2] or 0,
            last_error=log_row[3],
            db_total_docs=db_total,
        )
    except Exception as exc:
        logger.error("sync_status error: %s", exc)
        raise HTTPException(status_code=500, detail="Could not fetch sync status.")


@router.post("/sync/check", response_model=SyncCheckResponse)
async def sync_check(
    background_tasks: BackgroundTasks,
    ingest: bool = False,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin_key),
):
    """
    Live-check fia.com for new regulation PDFs. Requires X-Admin-Key.

    - `ingest=false` (default): dry-run — list what's new, no download.
    - `ingest=true`: download and ingest any new PDFs in the background.

    The live check runs synchronously so the caller gets immediate results.
    If `ingest=true`, the actual download+ingestion happens in the background.
    """
    try:
        from scripts.fia_scraper import check_for_new_regulations
    except ImportError as exc:
        logger.error("Could not import fia_scraper: %s", exc)
        raise HTTPException(status_code=500, detail="FIA scraper module not available.")

    try:
        # Always run a dry-run first to get the list
        summary = await check_for_new_regulations(dry_run=True)
    except Exception as exc:
        # M-07: log full detail internally but store only a generic constant in DB
        # to avoid leaking internal paths, DB URLs, or scraper internals.
        logger.error("FIA check failed: %s", exc, exc_info=True)
        try:
            await db.execute(text("""
                INSERT INTO fia_sync_log (new_docs_found, total_fia_docs, error)
                VALUES (0, 0, :error)
            """), {"error": _ERR_FIA_UNREACHABLE})
            await db.commit()
        except Exception:
            pass
        raise HTTPException(status_code=502, detail="Could not reach FIA website.")

    # Log successful check to fia_sync_log so /api/sync/status reflects it
    try:
        await db.execute(text("""
            INSERT INTO fia_sync_log (new_docs_found, total_fia_docs)
            VALUES (:new_docs, :total)
        """), {"new_docs": summary["new"], "total": summary["total_fia"]})
        await db.commit()
    except Exception as log_exc:
        logger.warning("Could not write sync log: %s", log_exc)

    if ingest and summary["new"] > 0:
        # Schedule the real ingestion in the background
        background_tasks.add_task(_background_ingest)

    return SyncCheckResponse(
        total_fia=summary["total_fia"],
        already_indexed=summary["already_indexed"],
        new=summary["new"],
        ingested=0,  # background task hasn't run yet
        new_docs=[NewDocInfo(**d) for d in summary["new_docs"]],
        errors=summary["errors"],
        dry_run=not ingest,
    )


async def _background_ingest():
    """Run full ingestion in the background (called by BackgroundTasks)."""
    try:
        from scripts.fia_scraper import check_for_new_regulations
        summary = await check_for_new_regulations(dry_run=False)
        logger.info(
            "Background FIA ingest complete: %d ingested, %d errors",
            summary["ingested"], len(summary["errors"]),
        )
    except Exception as exc:
        logger.error("Background FIA ingest failed: %s", exc, exc_info=True)
