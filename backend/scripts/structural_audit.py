"""
Structural audit of the articles table — Phase 0 baseline (read-only, 0 LLM).

Produces backend/eval/structural_baseline.json describing the current structural
health of the document tree, grouped by (section, year, issue):

    - orphan_rate       : articles whose parent_code is not NULL but no row with that
                          article_code exists in the same (section, year, issue).
    - numbering_gaps    : for each parent_code, children sorted by numeric suffix; any
                          jump in the sequence (4.1, 4.2, 4.4 -> missing 4.3) is a gap.
    - toc_contamination : articles with suspiciously short content (< THRESHOLD chars)
                          or whose content looks like a table-of-contents entry
                          (title + dotted leader + page number).
    - xref_resolution   : regex extracts "Article X(.Y)*" mentions in content; reports
                          the % that resolve to an existing article_code in the same
                          (section, year, issue).

Plus global totals and a ranked summary of which (section, year, issue) groups are
in the worst structural health.

This script is strictly READ-ONLY. It performs no INSERT/UPDATE/DDL and makes no LLM
calls.

Usage (from the backend/ directory):
    python -m scripts.structural_audit [--output PATH]

Environment:
    DATABASE_URL must be set.
"""

import argparse
import asyncio
import json
import logging
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

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

# Normalise scheme for asyncpg (mirrors scripts/compute_diffs.py)
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)

# Default output location (relative to backend/ where the script is run as a module).
DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "eval" / "structural_baseline.json"

# Content shorter than this many characters is considered suspiciously trivial.
SHORT_CONTENT_THRESHOLD = 40

# A content that matches a table-of-contents entry: text followed by dotted leader
# and/or a trailing page number (e.g. "Bodywork and Dimensions ........ 12").
TOC_PATTERN = re.compile(r"\.{3,}\s*\d+\s*$|^\s*[\w\s,&/\-]{1,80}\s+\d{1,3}\s*$")

# Cross-reference mentions like "Article 3", "Article 3.2", "Article D4.1.a".
# Captures an optional single-letter prefix + a dotted numeric/alpha code.
XREF_PATTERN = re.compile(
    r"\bArticle\s+([A-Z]?\d+(?:\.\w+)*)", re.IGNORECASE
)

# Trailing punctuation to strip from a captured cross-ref code.
_TRAILING_PUNCT = re.compile(r"[.,;:)\]]+$")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _suffix_sort_key(child_code: str, parent_code: str):
    """
    Return a sortable key for a child's numeric suffix relative to its parent.

    For parent "4" and child "4.3", the suffix is "3" -> (1, (3,), '').
    Mixed numeric/alpha suffixes (e.g. "4.3.a") sort numbers before letters.
    Returns (is_numeric_flag, tuple_of_ints, raw) so numeric suffixes sort first.
    """
    suffix = child_code
    if parent_code and child_code.startswith(parent_code + "."):
        suffix = child_code[len(parent_code) + 1:]
    # Take the FIRST segment of the suffix (the immediate child level).
    first_seg = suffix.split(".")[0]
    m = re.match(r"^(\d+)", first_seg)
    if m:
        return (0, int(m.group(1)), first_seg)
    return (1, 0, first_seg)


def _immediate_child_number(child_code: str, parent_code: str):
    """
    Return the integer of the immediate child level if numeric, else None.
    For parent "4", child "4.3.a" -> 3.  Child "4.b" -> None (alpha level).
    """
    suffix = child_code
    if parent_code and child_code.startswith(parent_code + "."):
        suffix = child_code[len(parent_code) + 1:]
    else:
        return None
    first_seg = suffix.split(".")[0]
    m = re.match(r"^(\d+)$", first_seg)
    return int(m.group(1)) if m else None


def looks_like_toc(content: str) -> bool:
    """Heuristic: does the content look like a table-of-contents entry?"""
    stripped = content.strip()
    if not stripped:
        return False
    # Dotted leaders are the strongest signal.
    if "...." in stripped:
        return True
    # Short single-line entry ending in a page number.
    if "\n" not in stripped and len(stripped) < 80:
        if TOC_PATTERN.search(stripped):
            return True
    return False


def extract_xref_codes(content: str) -> list[str]:
    """Extract normalised cross-referenced article codes from content."""
    codes = []
    for raw in XREF_PATTERN.findall(content or ""):
        code = _TRAILING_PUNCT.sub("", raw).strip()
        if code:
            codes.append(code)
    return codes


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

async def fetch_articles(session: AsyncSession):
    """Fetch every article's structural columns. Read-only."""
    sql = text("""
        SELECT
            article_code,
            parent_code,
            level,
            section,
            year,
            issue,
            COALESCE(title, '')   AS title,
            COALESCE(content, '') AS content
        FROM articles
        ORDER BY section, year, issue, article_code
    """)
    result = await session.execute(sql)
    rows = result.fetchall()
    logger.info("Fetched %d article rows.", len(rows))
    return rows


def audit(rows) -> dict:
    """Compute the structural audit grouped by (section, year, issue)."""
    # Group rows by (section, year, issue).
    groups: dict[tuple, list] = defaultdict(list)
    for r in rows:
        groups[(r.section, r.year, r.issue)].append(r)

    per_group = []
    global_tot = {
        "articles": 0,
        "orphans": 0,
        "numbering_gaps": 0,
        "toc_suspect": 0,
        "short_content": 0,
        "xref_mentions": 0,
        "xref_resolved": 0,
    }

    for (section, year, issue), arts in sorted(groups.items()):
        codes = {a.article_code for a in arts}
        total = len(arts)

        # --- Orphans ---
        orphan_codes = []
        for a in arts:
            if a.parent_code and a.parent_code not in codes:
                orphan_codes.append(a.article_code)
        orphan_count = len(orphan_codes)

        # --- Numbering gaps (per parent_code) ---
        children_by_parent: dict[str, list[str]] = defaultdict(list)
        for a in arts:
            if a.parent_code:
                children_by_parent[a.parent_code].append(a.article_code)

        gap_details = []
        gap_count = 0
        for parent, children in children_by_parent.items():
            nums = sorted(
                {n for c in children
                 if (n := _immediate_child_number(c, parent)) is not None}
            )
            if len(nums) < 2:
                continue
            missing = [n for n in range(nums[0], nums[-1] + 1) if n not in nums]
            if missing:
                gap_count += len(missing)
                gap_details.append({
                    "parent_code": parent,
                    "present": nums,
                    "missing": missing,
                })

        # --- TOC contamination / trivial content ---
        toc_codes = []
        short_codes = []
        for a in arts:
            content = a.content or ""
            if looks_like_toc(content):
                toc_codes.append(a.article_code)
            elif len(content.strip()) < SHORT_CONTENT_THRESHOLD:
                short_codes.append(a.article_code)
        toc_suspect = len(toc_codes)
        short_content = len(short_codes)

        # --- Cross-ref resolution ---
        xref_mentions = 0
        xref_resolved = 0
        unresolved_examples = []
        for a in arts:
            for code in extract_xref_codes(a.content):
                # Skip self-references and the bare article's own top number noise:
                # we count a mention as resolvable if the exact code exists in-group.
                xref_mentions += 1
                if code in codes:
                    xref_resolved += 1
                elif len(unresolved_examples) < 10:
                    unresolved_examples.append(code)

        xref_rate = (xref_resolved / xref_mentions) if xref_mentions else None

        # Health score: lower is worse. Normalised problem counts per article.
        problem_units = (
            orphan_count
            + gap_count
            + toc_suspect
            + short_content
            + (xref_mentions - xref_resolved)
        )
        health_score = round(problem_units / total, 4) if total else 0.0

        group_entry = {
            "section": section,
            "year": year,
            "issue": issue,
            "total_articles": total,
            "orphans": {
                "count": orphan_count,
                "rate": round(orphan_count / total, 4) if total else 0.0,
                "codes": sorted(orphan_codes)[:50],
            },
            "numbering_gaps": {
                "count": gap_count,
                "details": gap_details[:50],
            },
            "toc_contamination": {
                "toc_suspect_count": toc_suspect,
                "short_content_count": short_content,
                "toc_codes": sorted(toc_codes)[:50],
                "short_codes": sorted(short_codes)[:50],
            },
            "xref_resolution": {
                "mentions": xref_mentions,
                "resolved": xref_resolved,
                "resolution_rate": round(xref_rate, 4) if xref_rate is not None else None,
                "unresolved_examples": unresolved_examples,
            },
            "health_score": health_score,
        }
        per_group.append(group_entry)

        global_tot["articles"] += total
        global_tot["orphans"] += orphan_count
        global_tot["numbering_gaps"] += gap_count
        global_tot["toc_suspect"] += toc_suspect
        global_tot["short_content"] += short_content
        global_tot["xref_mentions"] += xref_mentions
        global_tot["xref_resolved"] += xref_resolved

    # Global aggregates.
    g_xref_rate = (
        global_tot["xref_resolved"] / global_tot["xref_mentions"]
        if global_tot["xref_mentions"] else None
    )
    global_summary = {
        "total_articles": global_tot["articles"],
        "total_groups": len(per_group),
        "total_orphans": global_tot["orphans"],
        "orphan_rate": round(global_tot["orphans"] / global_tot["articles"], 4)
        if global_tot["articles"] else 0.0,
        "total_numbering_gaps": global_tot["numbering_gaps"],
        "total_toc_suspect": global_tot["toc_suspect"],
        "total_short_content": global_tot["short_content"],
        "xref_mentions": global_tot["xref_mentions"],
        "xref_resolved": global_tot["xref_resolved"],
        "xref_resolution_rate": round(g_xref_rate, 4) if g_xref_rate is not None else None,
    }

    # Worst-health ranking (highest health_score = worst).
    worst = sorted(per_group, key=lambda g: g["health_score"], reverse=True)[:15]
    worst_summary = [
        {
            "group": f"{g['section']} {g['year']} issue {g['issue']}",
            "health_score": g["health_score"],
            "total_articles": g["total_articles"],
            "orphans": g["orphans"]["count"],
            "numbering_gaps": g["numbering_gaps"]["count"],
            "toc_suspect": g["toc_contamination"]["toc_suspect_count"],
            "short_content": g["toc_contamination"]["short_content_count"],
            "xref_resolution_rate": g["xref_resolution"]["resolution_rate"],
        }
        for g in worst
    ]

    return {
        "schema_version": 1,
        "thresholds": {
            "short_content_chars": SHORT_CONTENT_THRESHOLD,
            "xref_pattern": XREF_PATTERN.pattern,
        },
        "global": global_summary,
        "worst_groups": worst_summary,
        "by_group": per_group,
    }


async def main(output_path: Path) -> None:
    engine = create_async_engine(DATABASE_URL, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    logger.info("=== structural_audit starting (read-only, 0 LLM) ===")
    async with factory() as session:
        rows = await fetch_articles(session)
        report = audit(rows)

    await engine.dispose()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    g = report["global"]
    logger.info("=== Done ===")
    logger.info("Articles        : %d across %d groups", g["total_articles"], g["total_groups"])
    logger.info("Orphans         : %d (rate %.2f%%)", g["total_orphans"], (g["orphan_rate"] or 0) * 100)
    logger.info("Numbering gaps  : %d", g["total_numbering_gaps"])
    logger.info("TOC suspect     : %d  |  short content: %d", g["total_toc_suspect"], g["total_short_content"])
    rate = g["xref_resolution_rate"]
    logger.info("Cross-ref resol.: %s (%d/%d)",
                f"{rate*100:.1f}%" if rate is not None else "n/a",
                g["xref_resolved"], g["xref_mentions"])
    if report["worst_groups"]:
        w = report["worst_groups"][0]
        logger.info("Worst group     : %s (health_score=%.3f)", w["group"], w["health_score"])
    logger.info("Wrote baseline  : %s", output_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Read-only structural audit of the articles table (Phase 0 baseline)."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output JSON path (default: {DEFAULT_OUTPUT}).",
    )
    args = parser.parse_args()

    asyncio.run(main(output_path=args.output))
