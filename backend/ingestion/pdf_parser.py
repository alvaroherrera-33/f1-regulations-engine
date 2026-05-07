"""PDF parsing using PyMuPDF (fitz)."""
import fitz  # PyMuPDF
import re
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class ParsedArticle:
    """Represents a parsed article from a regulation PDF."""
    article_code: str
    title: str
    content: str
    level: int  # 1 = Article, 2 = Sub-article, 3 = Clause
    parent_code: Optional[str] = None


class PDFParser:
    """Parser for FIA Formula 1 regulation PDFs."""

    # Matches: "C4.1 Title", "B3.5.a Title", "2.1 Title", etc.
    # Pure numeric level-1 codes without title (page numbers) are skipped below.
    ARTICLE_PATTERN = re.compile(
        r'^([A-Z]*\d+)(?:\.(\d+))?(?:\.([a-z]))?(?:[\s\.\)]+(.*))?$',
        re.MULTILINE
    )
    # Matches: "ARTICLE C4: MASS", "ARTICLE 2: GENERAL"
    SECTION_HEADER_PATTERN = re.compile(
        r'^ARTICLE\s+([A-Z]*\d+)\s*[:\-]?\s*(.*)$',
        re.IGNORECASE
    )

    # Running page headers/footers to strip from article content.
    # These lines appear on every page but are not regulation text.
    PAGE_NOISE_PATTERNS = [
        # "SECTION C: TECHNICAL REGULATIONS", "SECTION B: SPORTING REGULATIONS"
        re.compile(r'^SECTION\s+[A-Z]\s*[:\-]\s*\w.*REGULATIONS\s*$', re.IGNORECASE),
        # "Formula 1 Financial Regulations", "Formula 1 Power Unit Financial Regulations"
        re.compile(r'^Formula\s+1\b.*\bRegulations\s*$', re.IGNORECASE),
        # "FIA Formula One World Championship" page headers
        re.compile(r'^FIA\s+Formula\s+(One|1)\b', re.IGNORECASE),
        # Standalone page numbers: "37", "103"
        re.compile(r'^\d{1,3}\s*$'),
    ]

    # TOC appendix entry: "ARTICLE E1: GENERAL PRINCIPLES\n3"
    # The content is just title + page-number, not regulation text.
    _TOC_ARTICLE_PATTERN = re.compile(
        r'^ARTICLE\s+\S+:?.*\n\d{1,3}\s*$',
        re.DOTALL
    )

    # Minimum meaningful content length (chars).
    MIN_CONTENT_LENGTH = 20

    def __init__(self, pdf_path: str):
        """Initialize parser with PDF path."""
        self.pdf_path = pdf_path
        self.doc = fitz.open(pdf_path)

    def _is_page_noise(self, line: str) -> bool:
        """Return True if line is a running header/footer, not regulation text."""
        stripped = line.strip()
        return any(p.match(stripped) for p in self.PAGE_NOISE_PATTERNS)

    def parse(self) -> List[ParsedArticle]:
        """
        Parse the PDF and extract all articles.

        Concatenates all pages into a single text stream before iterating so
        that articles spanning a page boundary are captured in full.

        Returns:
            List of ParsedArticle objects with hierarchical structure.
        """
        articles_dict: Dict[str, ParsedArticle] = {}
        current_article: Optional[Dict] = None
        current_text: List[str] = []

        # ── Process the entire document as one stream (fixes cross-page articles) ─
        full_text_parts = []
        for page_num in range(len(self.doc)):
            page = self.doc[page_num]
            full_text_parts.append(page.get_text("text"))
        full_text = "\n".join(full_text_parts)

        lines = full_text.split('\n')

        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            # ── Skip running page headers/footers ──────────────────────────────
            if self._is_page_noise(line):
                continue

            # Check if this line is an article header
            section_match = self.SECTION_HEADER_PATTERN.match(line)
            match = self.ARTICLE_PATTERN.match(line)

            if section_match:
                article_code = section_match.group(1)
                title = section_match.group(2).strip()
                if not title and i + 1 < len(lines):
                    title = lines[i + 1].strip()
                    if (self.ARTICLE_PATTERN.match(title)
                            or self.SECTION_HEADER_PATTERN.match(title)):
                        title = ""

                if current_article:
                    self._save_article(current_article, current_text, articles_dict)

                current_article = {
                    'article_code': article_code,
                    'title': title or f"Article {article_code}",
                    'parent_code': None,
                    'level': 1
                }
                current_text = [line]

            elif match:
                major = match.group(1)
                minor = match.group(2)
                clause = match.group(3)
                title = (match.group(4) or "").strip()

                if not title and i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line and not (
                        self.ARTICLE_PATTERN.match(next_line)
                        or self.SECTION_HEADER_PATTERN.match(next_line)
                    ):
                        title = next_line

                if clause and minor:
                    article_code = f"{major}.{minor}.{clause}"
                    parent_code = f"{major}.{minor}"
                    level = 3
                elif minor:
                    article_code = f"{major}.{minor}"
                    parent_code = major
                    level = 2
                else:
                    article_code = major
                    parent_code = None
                    level = 1

                # ── Skip bare numeric level-1 codes: page numbers, TOC refs ───
                # "0" (preamble noise), "103", "104"... have no title and are not
                # real articles. A valid numeric top-level article (e.g. "2") MUST
                # have an explicit title on the same or next line.
                if level == 1 and major.isdigit() and not title:
                    if current_article:
                        current_text.append(line)
                    continue

                # Legacy guard: very short codes without a title
                if level == 1 and not title and len(major) < 3:
                    if current_article:
                        current_text.append(line)
                    continue
                # ──────────────────────────────────────────────────────────────

                if current_article:
                    self._save_article(current_article, current_text, articles_dict)

                current_article = {
                    'article_code': article_code,
                    'title': title or f"Article {article_code}",
                    'parent_code': parent_code,
                    'level': level
                }
                current_text = [line]
            else:
                if current_article:
                    current_text.append(line)

        # Don't forget the last article
        if current_article:
            self._save_article(current_article, current_text, articles_dict)

        # Post-process: ensure every referenced parent exists
        self._fill_missing_parents(articles_dict)

        return list(articles_dict.values())

    def _is_toc_entry(self, content: str, code: str) -> bool:
        """
        Return True if content looks like a table-of-contents entry.

        A TOC entry is: article header text + a single page number.
        Example: "ARTICLE E1: GENERAL PRINCIPLES\\n3"
        """
        if not self._TOC_ARTICLE_PATTERN.match(content.strip()):
            return False
        lines = content.strip().split('\n')
        if len(lines) <= 2:
            last = lines[-1].strip()
            if last.isdigit():
                return True
        return False

    def _save_article(
        self,
        article_data: Dict,
        text_lines: List[str],
        articles_dict: Dict[str, ParsedArticle]
    ):
        """Save article to dict if it has meaningful content."""
        content = '\n'.join(text_lines).strip()
        code = article_data['article_code']

        # ── Discard trivially empty articles ──────────────────────────────────
        if len(content) <= len(code) + 5:
            return

        # ── Discard table-of-contents appendix entries ────────────────────────
        if self._is_toc_entry(content, code):
            return

        # ── Discard below minimum meaningful length ───────────────────────────
        if len(content) < self.MIN_CONTENT_LENGTH:
            return
        # ──────────────────────────────────────────────────────────────────────

        new_article = self._create_article({**article_data, 'content': content})

        if code not in articles_dict or len(content) > len(articles_dict[code].content):
            articles_dict[code] = new_article

    def _fill_missing_parents(self, articles_dict: Dict[str, ParsedArticle]) -> None:
        """
        Create stub parent articles for any parent_code reference that has no
        entry in the dict.

        This happens when a top-level article's content is minimal (just its
        header line) and gets discarded by the content-length filter, leaving
        all its sub-articles as orphans.  The stub gives the retriever something
        to enrich with.
        """
        stubs_to_add: Dict[str, ParsedArticle] = {}
        for article in articles_dict.values():
            if article.parent_code and article.parent_code not in articles_dict:
                parent = article.parent_code
                if parent not in stubs_to_add:
                    stubs_to_add[parent] = ParsedArticle(
                        article_code=parent,
                        title=f"Article {parent}",
                        content=f"Article {parent}",
                        level=article.level - 1,
                        parent_code=None,
                    )
        articles_dict.update(stubs_to_add)

    def _create_article(self, data: Dict) -> ParsedArticle:
        """Create ParsedArticle from dictionary."""
        return ParsedArticle(
            article_code=data['article_code'],
            title=data['title'],
            content=data['content'],
            level=data['level'],
            parent_code=data.get('parent_code')
        )

    def extract_tables(self, page_num: int) -> List[str]:
        """Extract tables from a specific page as markdown."""
        page = self.doc[page_num]
        tables = []
        try:
            tab_list = page.find_tables()
            for table in tab_list:
                tables.append(table.to_markdown())
        except AttributeError:
            pass
        return tables

    def close(self):
        """Close the PDF document."""
        if self.doc:
            self.doc.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def parse_pdf(pdf_path: str) -> List[ParsedArticle]:
    """
    Convenience function to parse a PDF.

    Usage:
        articles = parse_pdf("/path/to/regulation.pdf")
    """
    with PDFParser(pdf_path) as parser:
        return parser.parse()
