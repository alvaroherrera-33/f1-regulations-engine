"""TOC-aware structural parser for FIA regulation PDFs (Priority 1, Fase 2).

This is an additive layer that runs only when settings.structural_parser is True.
It does NOT replace pdf_parser.py — the legacy regex parser remains the fallback.
Everything here is deterministic (0 LLM calls).

What it adds over the legacy parser:
  1. Ground truth from the embedded PDF table of contents (doc.get_toc()):
     the authoritative list of which articles must exist.
  2. An explicit tree: each node knows its parent_code and level, so parents
     are verifiable rather than merely inferred.
  3. Deterministic cross-reference extraction: "Article 3.2", "Appendix B4" →
     stored so the pipeline can resolve them to article ids after insertion.

The result (StructuralParseResult) is intentionally compatible with the legacy
ParsedArticle shape (article_code/title/content/level/parent_code) so the
pipeline can store it through the same path, plus the structural extras.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import fitz  # PyMuPDF

from ingestion.pdf_parser import PDFParser, ParsedArticle


# Matches cross-references in body text: "Article 3.2", "Article C4.1.a",
# "Appendix B4". Captures the bare code so it can be resolved later.
XREF_PATTERN = re.compile(
    r"\b(?:Article|Appendix)\s+([A-Z]?\d+(?:\.\d+)*(?:\.[a-z])?)\b",
    re.IGNORECASE,
)

# Code embedded in a TOC entry title, e.g. "ARTICLE C4: MASS" or "4.1 Survival cell".
_TOC_CODE_PATTERN = re.compile(
    r"(?:ARTICLE\s+)?([A-Z]?\d+(?:\.\d+)*(?:\.[a-z])?)\b",
    re.IGNORECASE,
)


@dataclass
class CrossRef:
    """A reference from one article to another, found deterministically."""
    target_code: str          # code as written in the text, e.g. "3.2"
    raw_text: str             # the matched snippet, e.g. "Article 3.2"


@dataclass
class StructuralArticle:
    """A parsed article enriched with structural metadata.

    The first five fields mirror ParsedArticle so this can flow through the
    existing storage path unchanged.
    """
    article_code: str
    title: str
    content: str
    level: int
    parent_code: Optional[str] = None
    # Structural extras
    is_stub: bool = False
    structural_status: str = "unvalidated"
    page_range: Optional[Tuple[int, int]] = None
    references: List[CrossRef] = field(default_factory=list)

    def to_parsed_article(self) -> ParsedArticle:
        """Down-cast to the legacy shape used by the storage layer."""
        return ParsedArticle(
            article_code=self.article_code,
            title=self.title,
            content=self.content,
            level=self.level,
            parent_code=self.parent_code,
        )


@dataclass
class StructuralParseResult:
    """Output of the structural parser."""
    articles: List[StructuralArticle]
    expected_from_toc: Set[str]   # article codes the embedded TOC says should exist
    toc_available: bool           # False when the PDF has no embedded TOC


# --------------------------------------------------------------------------- #
#  Pure helpers (no PDF needed — unit-testable in isolation)                   #
# --------------------------------------------------------------------------- #
def extract_refs(content: str, self_code: str) -> List[CrossRef]:
    """Find deterministic cross-references in an article's body."""
    refs: List[CrossRef] = []
    seen: Set[str] = set()
    for m in XREF_PATTERN.finditer(content or ""):
        target = m.group(1)
        if target == self_code or target in seen:
            continue
        seen.add(target)
        refs.append(CrossRef(target_code=target, raw_text=m.group(0)))
    return refs


def toc_code_from_title(title: str) -> Optional[str]:
    """Extract the leading article code from a TOC entry title, if any."""
    if not title:
        return None
    m = _TOC_CODE_PATTERN.match(title.strip())
    return m.group(1) if m else None


def mark_stubs_and_status(
    by_code: Dict[str, "StructuralArticle"], expected: Set[str]
) -> None:
    """Set is_stub / structural_status using parent presence and the TOC.

    Status values:
      'ok'           — has resoluble parent (or is root) and no red flags
      'orphan'       — non-root node whose parent_code is missing
      'toc_suspect'  — not present in the embedded TOC (when TOC available)
    The numbering-gap status is assigned later by the pipeline validation gate,
    which has the full per-parent ordering.
    """
    for code, art in by_code.items():
        if art.content.strip() == f"Article {code}":
            art.is_stub = True

        if art.parent_code and art.parent_code not in by_code:
            art.structural_status = "orphan"
        elif expected and code not in expected:
            art.structural_status = "toc_suspect"
        else:
            art.structural_status = "ok"


class StructuralParser:
    """Parses a regulation PDF into a validated tree with cross-references."""

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.doc = fitz.open(pdf_path)

    # ------------------------------------------------------------------ #
    #  Public API                                                         #
    # ------------------------------------------------------------------ #
    def parse(self) -> StructuralParseResult:
        expected, toc_available = self._expected_from_toc()

        # Reuse the proven hierarchical-code extraction from the legacy parser.
        # We layer structural metadata on top rather than re-deriving codes,
        # keeping the fragile regex logic in one place.
        with PDFParser(self.pdf_path) as legacy:
            base = legacy.parse()

        by_code: Dict[str, StructuralArticle] = {}
        for pa in base:
            sa = StructuralArticle(
                article_code=pa.article_code,
                title=pa.title,
                content=pa.content,
                level=pa.level,
                parent_code=pa.parent_code,
                references=extract_refs(pa.content, pa.article_code),
            )
            by_code[sa.article_code] = sa

        mark_stubs_and_status(by_code, expected)
        return StructuralParseResult(
            articles=list(by_code.values()),
            expected_from_toc=expected,
            toc_available=toc_available,
        )

    # ------------------------------------------------------------------ #
    #  Internals                                                          #
    # ------------------------------------------------------------------ #
    def _expected_from_toc(self) -> Tuple[Set[str], bool]:
        """Read the embedded TOC and return the set of article codes it lists.

        Returns (codes, toc_available). When the PDF has no embedded TOC the
        set is empty and toc_available is False, so the pipeline degrades to
        numbering-continuity checks instead of TOC reconciliation.
        """
        try:
            toc = self.doc.get_toc(simple=True)  # [[level, title, page], ...]
        except Exception:
            return set(), False

        if not toc:
            return set(), False

        codes: Set[str] = set()
        for _level, title, _page in toc:
            code = toc_code_from_title(title)
            if code:
                codes.add(code)
        return codes, True

    def close(self) -> None:
        if self.doc:
            self.doc.close()

    def __enter__(self) -> "StructuralParser":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


def parse_pdf_structural(pdf_path: str) -> StructuralParseResult:
    """Convenience wrapper mirroring pdf_parser.parse_pdf()."""
    with StructuralParser(pdf_path) as p:
        return p.parse()
