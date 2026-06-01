"""Unit tests for the structural parser's deterministic helpers (no PDF, no DB, no LLM).

The PDF-dependent path (TOC reading, full parse) is validated locally against
real archives/ PDFs; these tests cover the pure logic that runs on every PDF.
"""

from ingestion.structural_parser import (
    StructuralArticle,
    extract_refs,
    mark_stubs_and_status,
    toc_code_from_title,
)

# --------------------------------------------------------------------------- #
#  Cross-reference extraction                                                  #
# --------------------------------------------------------------------------- #

def test_extract_refs_finds_article_and_appendix():
    content = "This is subject to Article 3.2 and Appendix B4 as defined."
    refs = extract_refs(content, self_code="5.1")
    targets = {r.target_code for r in refs}
    assert "3.2" in targets
    assert "B4" in targets


def test_extract_refs_ignores_self_reference():
    refs = extract_refs("As per Article 5.1 this clause...", self_code="5.1")
    assert all(r.target_code != "5.1" for r in refs)


def test_extract_refs_dedupes():
    content = "Article 3.2 ... Article 3.2 ... Article 3.2"
    refs = extract_refs(content, self_code="9")
    assert len([r for r in refs if r.target_code == "3.2"]) == 1


def test_extract_refs_lettered_clause():
    refs = extract_refs("see Article C4.1.a", self_code="X1")
    assert any(r.target_code == "C4.1.a" for r in refs)


def test_extract_refs_empty_content():
    assert extract_refs("", self_code="1") == []
    assert extract_refs(None, self_code="1") == []


# --------------------------------------------------------------------------- #
#  TOC title → code                                                            #
# --------------------------------------------------------------------------- #

def test_toc_code_from_article_header():
    assert toc_code_from_title("ARTICLE C4: MASS") == "C4"


def test_toc_code_from_numbered_title():
    assert toc_code_from_title("4.1 Survival cell") == "4.1"


def test_toc_code_none_for_plain_title():
    assert toc_code_from_title("Foreword") is None
    assert toc_code_from_title("") is None


# --------------------------------------------------------------------------- #
#  Stub / structural_status marking                                            #
# --------------------------------------------------------------------------- #

def _art(code, content, parent=None, level=2):
    return StructuralArticle(
        article_code=code, title=f"T {code}", content=content,
        level=level, parent_code=parent,
    )


def test_mark_orphan_when_parent_missing():
    by_code = {"4.1": _art("4.1", "real content", parent="4")}  # no "4"
    mark_stubs_and_status(by_code, expected=set())
    assert by_code["4.1"].structural_status == "orphan"


def test_mark_ok_when_parent_present():
    by_code = {
        "4": _art("4", "header content", parent=None, level=1),
        "4.1": _art("4.1", "real content", parent="4"),
    }
    mark_stubs_and_status(by_code, expected=set())
    assert by_code["4.1"].structural_status == "ok"


def test_mark_toc_suspect_when_not_in_toc():
    by_code = {"9.9": _art("9.9", "content", parent=None, level=1)}
    mark_stubs_and_status(by_code, expected={"1", "2", "3"})
    assert by_code["9.9"].structural_status == "toc_suspect"


def test_stub_detected_from_placeholder_content():
    by_code = {"4": _art("4", "Article 4", parent=None, level=1)}
    mark_stubs_and_status(by_code, expected=set())
    assert by_code["4"].is_stub is True
