"""Unit tests for the structural validation gate (no PDF, no DB, no LLM)."""

from dataclasses import dataclass
from typing import Optional

from ingestion.structural_validation import (
    compute_audit,
    find_numbering_gaps,
    find_orphans,
    toc_coverage,
)


@dataclass
class A:
    article_code: str
    parent_code: Optional[str] = None
    structural_status: str = "ok"


# --- orphans -------------------------------------------------------------- #

def test_orphan_detected():
    arts = [A("4.1", parent_code="4")]  # parent "4" absent
    assert find_orphans(arts) == ["4.1"]


def test_no_orphan_when_parent_present():
    arts = [A("4"), A("4.1", parent_code="4")]
    assert find_orphans(arts) == []


# --- numbering gaps ------------------------------------------------------- #

def test_gap_detected():
    arts = [A("4"), A("4.1", "4"), A("4.2", "4"), A("4.4", "4")]  # missing 4.3
    gaps = find_numbering_gaps(arts)
    assert any("4.3" in g for g in gaps)


def test_no_gap_for_contiguous():
    arts = [A("4"), A("4.1", "4"), A("4.2", "4"), A("4.3", "4")]
    assert find_numbering_gaps(arts) == []


# --- toc coverage --------------------------------------------------------- #

def test_toc_coverage_partial():
    cov = toc_coverage({"1", "2"}, {"1", "2", "3", "4"})
    assert cov == 0.5


def test_toc_coverage_none_when_no_toc():
    assert toc_coverage({"1"}, set()) is None


# --- gate decision -------------------------------------------------------- #

def test_gate_passes_clean_doc():
    arts = [A("4"), A("4.1", "4"), A("4.2", "4")]
    audit = compute_audit(arts, expected_from_toc={"4", "4.1", "4.2"})
    assert audit.passed is True
    assert audit.orphan_count == 0


def test_gate_fails_on_orphan():
    arts = [A("4.1", parent_code="4")]
    audit = compute_audit(arts, expected_from_toc={"4.1"})
    assert audit.passed is False
    assert audit.orphan_count == 1


def test_gate_fails_on_low_toc_coverage():
    arts = [A("1")]
    audit = compute_audit(arts, expected_from_toc={"1", "2", "3", "4"})  # 25%
    assert audit.toc_coverage == 0.25
    assert audit.passed is False


def test_gate_skips_coverage_without_toc():
    arts = [A("1"), A("2")]
    audit = compute_audit(arts, expected_from_toc=set())
    assert audit.toc_coverage is None
    assert audit.passed is True
