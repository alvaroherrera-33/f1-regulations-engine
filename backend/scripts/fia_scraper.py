"""
FIA regulations scraper.

Fetches the FIA official regulations page, finds new F1 regulation PDFs,
downloads them, and triggers ingestion into the database.

Usage:
    python -m scripts.fia_scraper [--dry-run] [--download-dir PATH]

Environment:
    DATABASE_URL must be set.
"""
import argparse
import asyncio
import logging
import re
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Constants                                                            #
# ------------------------------------------------------------------ #

FIA_REGULATIONS_URL = "https://www.fia.com/regulation/category/110"
FIA_BASE_URL = "https://www.fia.com"

# Section letter → human-readable section name used in our DB
SECTION_MAP = {
    "b": "Sporting",
    "c": "Technical",
    "d": "Financial",
    "e": "Financial",   # PU manufacturers — we store as Financial too
}

# Sections we care about (ignore section A = General Provisions)
RELEVANT_SECTIONS = set(SECTION_MAP.keys())


# ------------------------------------------------------------------ #
# PDF link parsing                                                     #
# ------------------------------------------------------------------ #

def _parse_pdf_url(url: str) -> Optional[dict]:
    """
    Extract year / section / issue from a FIA PDF URL or filename.

    Handles both URL patterns observed on fia.com:
      - /system/files/documents/fia_2026_f1_regulations_-_section_c_technical_-_iss_17_-_2026-04-28.pdf
      - /sites/default/files/fia_2026_f1_regulations_-_section_c_technical_-_iss09_-_2024-10-17.pdf

    Returns a dict with keys: year, section, issue, url, filename
    Returns None if the URL doesn't match the expected pattern.
    """
    filename = url.rstrip("/").split("/")[-1].lower()

    # Must be an F1 regulation PDF
    if "f1_regulation" not in filename and "formula_1" not in filename:
        return None

    # Year — four consecutive digits (20XX)
    year_match = re.search(r"_?(20\d{2})_?", filename)
    if not year_match:
        return None
    year = int(year_match.group(1))

    # Section letter — "section_X" or "section_X_"
    sec_match = re.search(r"section[_\s]?([a-e])", filename)
    if not sec_match:
        return None
    sec_letter = sec_match.group(1).lower()
    if sec_letter not in RELEVANT_SECTIONS:
        return None

    # Issue number — "iss_17" or "iss17" or "iss_09" or "iss09"
    iss_match = re.search(r"iss[_\s]?(\d+)", filename)
    if not iss_match:
        return None
    issue = int(iss_match.group(1))

    section = SECTION_MAP[sec_letter]
    clean_filename = Path(url).name  # preserve original case for download

    return {
        "year": year,
        "section": section,
        "issue": issue,
        "url": url if url.startswith("http") else urljoin(FIA_BASE_URL, url),
        "filename": clean_filename,
    }


def fetch_fia_pdf_list() -> list[dict]:
    """
    Fetch the FIA regulations page and return a list of PDF metadata dicts.

    Each dict: { year, section, issue, url, filename }
    Sorted newest first (year DESC, issue DESC).
    """
    logger.info("Fetching FIA regulations page: %s", FIA_REGULATIONS_URL)

    req = urllib.request.Request(
        FIA_REGULATIONS_URL,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; F1RegBot/1.0; "
                "+https://github.com/alvaroherranz/f1-regulations-engine)"
            )
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", errors="replace")

    # Extract all .pdf href values
    pdf_links = re.findall(r'href=["\']([^"\']+\.pdf)["\']', html, re.IGNORECASE)
    logger.info("Found %d raw PDF links on FIA page", len(pdf_links))

    seen_keys: set[tuple] = set()
    results: list[dict] = []

    for link in pdf_links:
        parsed = _parse_pdf_url(link)
        if not parsed:
            continue
        key = (parsed["year"], parsed["section"], parsed["issue"])
        if key in seen_keys:
            continue
        seen_keys.add(key)
        results.append(parsed)

    # Sort: newest year first, highest issue first within same year+section
    results.sort(key=lambda d: (d["year"], d["issue"]), reverse=True)
    logger.info("Parsed %d unique F1 regulation PDFs", len(results))
    return results


# ------------------------------------------------------------------ #
# DB helpers                                                           #
# ------------------------------------------------------------------ #

async def _get_existing_docs(db) -> set[tuple]:
    """Return set of (year, section, issue) tuples already in DB."""
    from sqlalchemy import select

    from app.models import Document

    result = await db.execute(select(Document.year, Document.section, Document.issue))
    return {(row.year, row.section, row.issue) for row in result.all()}


async def _log_sync(db, *, new_count: int, total_found: int, error: Optional[str] = None):
    """Insert a row into fia_sync_log."""
    from sqlalchemy import text
    try:
        await db.execute(
            text("""
                INSERT INTO fia_sync_log (checked_at, new_docs_found, total_fia_docs, error)
                VALUES (:checked_at, :new_docs_found, :total_fia_docs, :error)
            """),
            {
                "checked_at": datetime.now(timezone.utc),
                "new_docs_found": new_count,
                "total_fia_docs": total_found,
                "error": error,
            },
        )
        await db.commit()
    except Exception as exc:
        logger.warning("Could not write sync log: %s", exc)


# ------------------------------------------------------------------ #
# Core sync logic                                                      #
# ------------------------------------------------------------------ #

async def check_for_new_regulations(dry_run: bool = True) -> dict:
    """
    Main entry point: compare FIA PDFs against DB, ingest any new ones.

    Returns a summary dict:
      { total_fia: int, already_indexed: int, new: int, ingested: int,
        new_docs: [{ year, section, issue, filename }], errors: [str] }
    """
    from app.database import async_session

    fia_docs = fetch_fia_pdf_list()
    total_fia = len(fia_docs)

    async with async_session() as db:
        existing = await _get_existing_docs(db)

    new_docs = [d for d in fia_docs if (d["year"], d["section"], d["issue"]) not in existing]
    already_indexed = total_fia - len(new_docs)

    logger.info(
        "FIA sync: %d total, %d already indexed, %d new",
        total_fia, already_indexed, len(new_docs),
    )

    summary = {
        "total_fia": total_fia,
        "already_indexed": already_indexed,
        "new": len(new_docs),
        "ingested": 0,
        "new_docs": [
            {"year": d["year"], "section": d["section"], "issue": d["issue"], "filename": d["filename"]}
            for d in new_docs
        ],
        "errors": [],
    }

    if dry_run or not new_docs:
        return summary

    # Ingest new docs
    with tempfile.TemporaryDirectory() as tmpdir:
        for doc in new_docs:
            try:
                logger.info("Downloading %s → %s", doc["url"], doc["filename"])
                local_path = Path(tmpdir) / doc["filename"]
                req = urllib.request.Request(
                    doc["url"],
                    headers={"User-Agent": "Mozilla/5.0 (compatible; F1RegBot/1.0)"},
                )
                with urllib.request.urlopen(req, timeout=60) as resp:
                    raw = resp.read()

                # B-01: validate magic bytes before ingestion — a malformed or
                # HTML error page served as a PDF would crash the parser.
                if not raw[:5] == b"%PDF-":
                    raise ValueError(
                        f"Downloaded file is not a valid PDF (bad magic bytes). "
                        f"First bytes: {raw[:8]!r}"
                    )

                local_path.write_bytes(raw)

                logger.info(
                    "Ingesting %s (year=%d, section=%s, issue=%d)",
                    doc["filename"], doc["year"], doc["section"], doc["issue"],
                )
                await _ingest_document(local_path, doc)
                summary["ingested"] += 1

            except Exception as exc:
                msg = f"{doc['filename']}: {exc}"
                logger.error("Ingestion failed — %s", msg)
                summary["errors"].append(msg)

    # Log this sync run
    error_str = "; ".join(summary["errors"]) or None
    async with async_session() as db:
        await _log_sync(db, new_count=summary["ingested"], total_found=total_fia, error=error_str)

    return summary


async def _ingest_document(local_path: Path, meta: dict):
    """Parse + embed + store a single downloaded PDF."""
    from sqlalchemy import insert, select

    from app.database import async_session
    from app.models import Document
    from ingestion.pipeline import IngestionPipeline

    async with async_session() as db:
        # Check again (race guard)
        result = await db.execute(
            select(Document).where(
                Document.year == meta["year"],
                Document.section == meta["section"],
                Document.issue == meta["issue"],
            )
        )
        if result.scalar_one_or_none():
            logger.info("Already in DB (race guard): %s", meta["filename"])
            return

        stmt = (
            insert(Document)
            .values(
                name=meta["filename"],
                year=meta["year"],
                section=meta["section"],
                issue=meta["issue"],
                file_path=str(local_path),
            )
            .returning(Document.id)
        )
        result = await db.execute(stmt)
        document_id = result.scalar_one()
        await db.commit()

        pipeline = IngestionPipeline(db)
        result = await pipeline.ingest_document(str(local_path), document_id)

    if result["status"] != "success":
        raise RuntimeError(result.get("message", "Ingestion pipeline error"))

    logger.info(
        "Ingested %s → %d articles",
        meta["filename"], result.get("articles_count", 0),
    )


# ------------------------------------------------------------------ #
# CLI entry-point                                                      #
# ------------------------------------------------------------------ #

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="Sync FIA regulations into the DB")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Only list new PDFs; do not download or ingest (default: True)",
    )
    parser.add_argument(
        "--ingest",
        action="store_true",
        help="Actually download and ingest new PDFs (overrides --dry-run)",
    )
    args = parser.parse_args()

    dry_run = not args.ingest

    summary = asyncio.run(check_for_new_regulations(dry_run=dry_run))

    print("\n" + "=" * 60)
    print("🏎  FIA Regulations Sync")
    print("=" * 60)
    print(f"  FIA docs found:    {summary['total_fia']}")
    print(f"  Already indexed:   {summary['already_indexed']}")
    print(f"  New:               {summary['new']}")
    if not dry_run:
        print(f"  Ingested:          {summary['ingested']}")

    if summary["new_docs"]:
        print("\n  New documents:")
        for d in summary["new_docs"]:
            tag = "✓ ingested" if (not dry_run and d in summary.get("ingested_docs", [])) else ""
            print(f"    • {d['year']} {d['section']} Issue {d['issue']:>3}  ({d['filename'][:60]}) {tag}")

    if summary["errors"]:
        print("\n  Errors:")
        for err in summary["errors"]:
            print(f"    ✗ {err}")

    if dry_run:
        print("\n  (Dry-run mode — use --ingest to actually download and ingest)")

    print("=" * 60 + "\n")
    return 0 if not summary["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
