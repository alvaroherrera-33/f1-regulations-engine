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
    
    # Matches: "1 Title", "C4.1 Title", "C4.1", "B3.5.a Title", etc.
    ARTICLE_PATTERN = re.compile(r'^([A-Z]*\d+)(?:\.(\d+))?(?:\.([a-z]))?(?:[\s\.\)]+(.*))?$', re.MULTILINE)
    # Matches: "ARTICLE C4: MASS", "ARTICLE 2: GENERAL"
    SECTION_HEADER_PATTERN = re.compile(r'^ARTICLE\s+([A-Z]*\d+)\s*[:\-]?\s*(.*)$', re.IGNORECASE)
    
    def __init__(self, pdf_path: str):
        """Initialize parser with PDF path."""
        self.pdf_path = pdf_path
        self.doc = fitz.open(pdf_path)
    
    def parse(self) -> List[ParsedArticle]:
        """
        Parse the PDF and extract all articles.
        
        Returns:
            List of ParsedArticle objects with hierarchical structure.
        """
        articles_dict = {} # code -> ParsedArticle (highest content wins)
        current_article = None
        current_text = []
        
        for page_num in range(len(self.doc)):
            page = self.doc[page_num]
            text = page.get_text("text")
            
            lines = text.split('\n')
            
            for i, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue
                
                # Check if this line is an article header
                section_match = self.SECTION_HEADER_PATTERN.match(line)
                match = self.ARTICLE_PATTERN.match(line)
                
                if section_match:
                    article_code = section_match.group(1)
                    title = section_match.group(2).strip()
                    if not title and i + 1 < len(lines):
                        title = lines[i+1].strip()
                        if self.ARTICLE_PATTERN.match(title) or self.SECTION_HEADER_PATTERN.match(title):
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
                        next_line = lines[i+1].strip()
                        if next_line and not (self.ARTICLE_PATTERN.match(next_line) or self.SECTION_HEADER_PATTERN.match(next_line)):
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
                    
                    if level == 1 and not title and len(major) < 3:
                        if current_article:
                            current_text.append(line)
                        continue

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
        
        return list(articles_dict.values())
    
    def _save_article(self, article_data: Dict, text_lines: List[str], articles_dict: Dict[str, ParsedArticle]):
        """Save article to dict if it has more content than existing entry."""
        content = '\n'.join(text_lines).strip()
        code = article_data['article_code']
        
        new_article = self._create_article({
            **article_data,
            'content': content
        })
        
        if code not in articles_dict or len(content) > len(articles_dict[code].content):
            articles_dict[code] = new_article

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
        """
        Extract tables from a specific page as markdown.
        
        Note: Basic implementation. FIA PDFs may need custom table handling.
        """
        page = self.doc[page_num]
        tables = []
        
        # PyMuPDF table detection (requires pymupdf >= 1.23.0)
        try:
            tab_list = page.find_tables()
            for table in tab_list:
                # Convert to markdown format
                markdown = table.to_markdown()
                tables.append(markdown)
        except AttributeError:
            # Fallback if find_tables not available
            pass
        
        return tables
    
    def close(self):
        """Close the PDF document."""
        if self.doc:
            self.doc.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


def parse_pdf(pdf_path: str) -> List[ParsedArticle]:
    """
    Convenience function to parse a PDF.
    
    Usage:
        articles = parse_pdf("/path/to/regulation.pdf")
    """
    with PDFParser(pdf_path) as parser:
        return parser.parse()
