"""Structural validation gate for ingestion (Priority 1, Fase 3).

Pure, deterministic checks (0 LLM, 0 DB) over a parsed document, plus a small
dataclass summarising the result. The pipeline calls these, persists the
summary into document_structure_audit, and decides whether to accept the
document (hard gate) or mark it degraded.

Mirrors the metrics in scripts/structural_audit.py so the per-document audit
written at ingestion time is comparable to the global baseline.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set

# Default acceptance thresholds for the hard gate (overridable per call).
MIN_TOC_COVERAGE = 0.95   # parsed must cover ≥95% of TOC-listed codes
MAX_ORPHANS = 0           # zero real orphans after stub-filling


# Splits a code into its numeric path for gap detection.
# "C4.2.a" -> prefix "C4.2", last numeric segment 2 (the 'a' clause is ignored
# for integer-gap purposes); "4.3" -> prefix "4", segment 3.
_SEG_PATTERN = re.compile(r"^(.*?)(\d+)(?:\.[a-z])?$")


@dataclass
class StructuralAudit:
    """Per-document structural audit summary."""
    total_articles: int = 0
    orphan_count: int = 0
    numbering_gap_count: int = 0
    toc_suspect_count: int = 0
    toc_coverage: Optional[float] = None     # None when no embedded TOC
    xref_total: int = 0
    xref_resolved: int = 0
    passed: bool = False
    orphans: List[str] = field(default_factory=list)
    gaps: List[str] = field(default_factory=list)        # "parent: missing 4.2"
    missing_from_toc: List[str] = field(default_factory=list)

    @property
    def xref_resolution_rate(self) -> float:
        return (self.xref_resolved / self.xref_total) if self.xref_total else 0.0


def find_orphans(articles: Sequence) -> List[str]:
    """Codes of non-root articles whose parent_code has no entry in the set."""
    codes: Set[str] = {a.article_code for a in articles}
    return [
        a.article_code
        for a in articles
        if a.parent_code and a.parent_code not in codes
    ]


def find_numbering_gaps(articles: Sequence) -> List[str]:
    """Detect missing integers in each parent's child sequence.

    Groups children by parent_code, reads the trailing numeric segment of each
    child code, and reports any integer missing between min and max observed.
    Returns human-readable strings like "4: missing 2".
    """
    by_parent: Dict[str, List[int]] = {}
    for a in articles:
        if not a.parent_code:
            continue
        m = _SEG_PATTERN.match(a.article_code)
        if not m:
            continue
        try:
            seg = int(m.group(2))
        except ValueError:
            continue
        by_parent.setdefault(a.parent_code, []).append(seg)

    gaps: List[str] = []
    for parent, segs in by_parent.items():
        uniq = sorted(set(segs))
        if len(uniq) < 2:
            continue
        present = set(uniq)
        for n in range(uniq[0], uniq[-1] + 1):
            if n not in present:
                gaps.append(f"{parent}: missing {parent}.{n}" if parent else f"missing {n}")
    return gaps


def toc_coverage(parsed_codes: Set[str], expected: Set[str]) -> Optional[float]:
    """Fraction of TOC-expected codes that were actually parsed.

    Returns None when the TOC is empty (no embedded TOC → coverage undefined).
    """
    if not expected:
        return None
    found = len(expected & parsed_codes)
    return found / len(expected)


def compute_audit(
    articles: Sequence,
    expected_from_toc: Set[str],
    *,
    min_toc_coverage: float = MIN_TOC_COVERAGE,
    max_orphans: int = MAX_ORPHANS,
) -> StructuralAudit:
    """Run all structural checks and decide pass/fail.

    xref counts are filled in later by the pipeline (after IDs are resolved),
    so they don't gate acceptance here. The gate is: zero orphans and TOC
    coverage at/above threshold (or no TOC, in which case coverage is skipped).
    """
    parsed_codes: Set[str] = {a.article_code for a in articles}
    orphans = find_orphans(articles)
    gaps = find_numbering_gaps(articles)
    cov = toc_coverage(parsed_codes, expected_from_toc)
    missing = sorted(expected_from_toc - parsed_codes) if expected_from_toc else []
    toc_suspect = sum(
        1 for a in articles if getattr(a, "structural_status", None) == "toc_suspect"
    )

    coverage_ok = (cov is None) or (cov >= min_toc_coverage)
    passed = (len(orphans) <= max_orphans) and coverage_ok

    return StructuralAudit(
        total_articles=len(articles),
        orphan_count=len(orphans),
        numbering_gap_count=len(gaps),
        toc_suspect_count=toc_suspect,
        toc_coverage=cov,
        passed=passed,
        orphans=orphans,
        gaps=gaps,
        missing_from_toc=missing,
    )
