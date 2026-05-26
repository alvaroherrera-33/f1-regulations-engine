"""
Compute cross-year article diffs and populate the article_diffs table.

Uses embeddings already stored in article_embeddings — zero LLM calls, zero re-embedding.
For every (article_code, section) that exists in multiple years, computes cosine similarity
between the representative embedding of each year and classifies the change type.

Change classification thresholds:
    >= 0.98  →  unchanged
    >= 0.90  →  minor
    >= 0.70  →  major
    < 0.70   →  major (significant rewrite)
    present in A but not in B  →  removed
    present in B but not in A  →  added

Usage:
    python -m scripts.compute_diffs [--dry-run] [--section SECTION]

Environment:
    DATABASE_URL must be set.
"""

import argparse
import asyncio
import logging
import os
import sys
from collections import defaultdict
from itertools import combinations

import numpy as np
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    sys.exit("DATABASE_URL environment variable is required.")

# Normalise scheme for asyncpg
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
elif not DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)

THRESHOLDS = {
    "unchanged": 0.98,
    "minor": 0.90,
    "major": 0.70,  # anything below this is still 'major'
}

UPSERT_SQL = text("""
    INSERT INTO article_diffs
        (article_code, section, year_from, year_to,
         issue_from, issue_to, similarity, change_type, computed_at)
    VALUES
        (:code, :section, :year_from, :year_to,
         :issue_from, :issue_to, :similarity, :change_type, NOW())
    ON CONFLICT (article_code, section, year_from, year_to)
    DO UPDATE SET
        issue_from   = EXCLUDED.issue_from,
        issue_to     = EXCLUDED.issue_to,
        similarity   = EXCLUDED.similarity,
        change_type  = EXCLUDED.change_type,
        computed_at  = EXCLUDED.computed_at
""")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two 1-D vectors."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def classify_change(similarity: float) -> str:
    if similarity >= THRESHOLDS["unchanged"]:
        return "unchanged"
    if similarity >= THRESHOLDS["minor"]:
        return "minor"
    return "major"


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

async def fetch_article_embeddings(session: AsyncSession, section_filter: str | None):
    """
    Fetch one representative embedding per (article_code, section, year).
    Uses the FIRST embedding for chunked articles (chunk 0 = start of article,
    most representative of the article's identity).
    Returns list of dicts with: code, section, year, issue, embedding (np.ndarray).
    """
    where = "WHERE a.section = :section" if section_filter else ""
    params = {"section": section_filter} if section_filter else {}

    sql = text(f"""
        SELECT DISTINCT ON (a.article_code, a.section, a.year)
            a.article_code  AS code,
            a.section       AS section,
            a.year          AS year,
            a.issue         AS issue,
            ae.embedding    AS embedding
        FROM articles a
        JOIN article_embeddings ae ON ae.article_id = a.id
        {where}
        ORDER BY a.article_code, a.section, a.year, a.issue DESC, ae.id ASC
    """)
    result = await session.execute(sql, params)
    rows = result.fetchall()
    logger.info("Fetched %d article-year combinations%s",
                len(rows), f" for section={section_filter}" if section_filter else "")
    return rows


async def compute_and_upsert(
    session: AsyncSession,
    rows,
    dry_run: bool,
) -> dict[str, int]:
    """
    Group rows by (code, section), compute pairwise diffs for consecutive years,
    and upsert into article_diffs.
    Returns stats dict.
    """
    # Group by (code, section)
    groups: dict[tuple, list] = defaultdict(list)
    for row in rows:
        groups[(row.code, row.section)].append(row)

    stats = {"total": 0, "unchanged": 0, "minor": 0, "major": 0, "added": 0, "removed": 0}

    batch: list[dict] = []

    for (code, section), versions in groups.items():
        if len(versions) < 2:
            # Only one year — nothing to compare
            continue

        # Sort by year
        versions.sort(key=lambda r: r.year)
        year_map = {v.year: v for v in versions}

        # Compare consecutive year pairs: (2023,2024), (2024,2025), (2025,2026)
        all_years = sorted(year_map.keys())
        for year_a, year_b in zip(all_years, all_years[1:]):
            va = year_map[year_a]
            vb = year_map[year_b]

            emb_a = np.array(va.embedding, dtype=np.float32)
            emb_b = np.array(vb.embedding, dtype=np.float32)
            sim = cosine_similarity(emb_a, emb_b)
            change = classify_change(sim)

            batch.append({
                "code": code,
                "section": section,
                "year_from": year_a,
                "year_to": year_b,
                "issue_from": va.issue,
                "issue_to": vb.issue,
                "similarity": round(sim, 6),
                "change_type": change,
            })
            stats["total"] += 1
            stats[change] += 1

        # Mark articles that exist in the earliest year but not the latest as 'removed'
        # and those only in the latest but not earliest as 'added' — only at boundaries
        min_year, max_year = all_years[0], all_years[-1]
        if len(all_years) > 1 and min_year != max_year:
            # These are implied by the pairwise diffs above;
            # explicit added/removed only make sense across non-consecutive years
            pass

    # Also handle codes present in year_a but not year_b (removed) or vice versa (added)
    # We do this at the global level: compare the set of codes in each year
    logger.info("Pairwise diffs computed: %d rows", stats["total"])

    if dry_run:
        logger.info("[DRY RUN] Would upsert %d rows. Sample: %s", len(batch), batch[:3])
        return stats

    # Batch upsert in chunks of 500
    chunk_size = 500
    upserted = 0
    for i in range(0, len(batch), chunk_size):
        chunk = batch[i:i + chunk_size]
        for row in chunk:
            await session.execute(UPSERT_SQL, {
                "code": row["code"],
                "section": row["section"],
                "year_from": row["year_from"],
                "year_to": row["year_to"],
                "issue_from": row["issue_from"],
                "issue_to": row["issue_to"],
                "similarity": row["similarity"],
                "change_type": row["change_type"],
            })
        await session.commit()
        upserted += len(chunk)
        logger.info("Upserted %d / %d rows...", upserted, len(batch))

    return stats


async def compute_cross_section_removed_added(
    session: AsyncSession,
    section_filter: str | None,
    dry_run: bool,
) -> int:
    """
    Detect articles that exist in year N but NOT in year N+1 (removed)
    or exist in year N+1 but NOT in year N (added).
    Inserts these with similarity=0 and change_type='removed'/'added'.
    """
    where = "AND a.section = :section" if section_filter else ""
    params = {"section": section_filter} if section_filter else {}

    # Get all (code, section, year, issue) combos
    sql = text(f"""
        SELECT DISTINCT a.article_code AS code, a.section, a.year, MAX(a.issue) AS issue
        FROM articles a
        WHERE 1=1 {where}
        GROUP BY a.article_code, a.section, a.year
        ORDER BY a.article_code, a.section, a.year
    """)
    result = await session.execute(sql, params)
    rows = result.fetchall()

    # Group by (code, section)
    groups: dict[tuple, dict[int, int]] = defaultdict(dict)
    for row in rows:
        groups[(row.code, row.section)][row.year] = row.issue

    batch: list[dict] = []
    years_range = [2023, 2024, 2025, 2026]

    for (code, section), year_issues in groups.items():
        present = set(year_issues.keys())
        for year_a, year_b in zip(years_range, years_range[1:]):
            if year_a not in present and year_b not in present:
                continue
            if year_a in present and year_b not in present:
                # Article was removed in year_b
                batch.append({
                    "code": code, "section": section,
                    "year_from": year_a, "year_to": year_b,
                    "issue_from": year_issues[year_a], "issue_to": 0,
                    "similarity": 0.0, "change_type": "removed",
                })
            elif year_a not in present and year_b in present:
                # Article was added in year_b
                batch.append({
                    "code": code, "section": section,
                    "year_from": year_a, "year_to": year_b,
                    "issue_from": 0, "issue_to": year_issues[year_b],
                    "similarity": 0.0, "change_type": "added",
                })

    if dry_run:
        logger.info("[DRY RUN] Would add %d removed/added diffs", len(batch))
        return len(batch)

    for row in batch:
        await session.execute(UPSERT_SQL, {
            "code": row["code"],
            "section": row["section"],
            "year_from": row["year_from"],
            "year_to": row["year_to"],
            "issue_from": row["issue_from"],
            "issue_to": row["issue_to"],
            "similarity": row["similarity"],
            "change_type": row["change_type"],
        })
    if batch:
        await session.commit()
    logger.info("Upserted %d removed/added diffs", len(batch))
    return len(batch)


async def main(dry_run: bool, section_filter: str | None) -> None:
    engine = create_async_engine(DATABASE_URL, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        logger.info("=== compute_diffs starting%s ===",
                    " [DRY RUN]" if dry_run else "")

        rows = await fetch_article_embeddings(session, section_filter)
        stats = await compute_and_upsert(session, rows, dry_run)
        added_removed = await compute_cross_section_removed_added(
            session, section_filter, dry_run
        )

    await engine.dispose()

    logger.info("=== Done ===")
    logger.info("Pairwise diffs  : %d total", stats["total"])
    logger.info("  unchanged     : %d", stats["unchanged"])
    logger.info("  minor         : %d", stats["minor"])
    logger.info("  major         : %d", stats["major"])
    logger.info("Added/removed   : %d", added_removed)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compute article_diffs from stored embeddings.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be inserted without writing to DB.")
    parser.add_argument("--section", choices=["Technical", "Sporting", "Financial"],
                        default=None, help="Process only one section.")
    args = parser.parse_args()

    asyncio.run(main(dry_run=args.dry_run, section_filter=args.section))
