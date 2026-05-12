"""Chunking strategy for long articles.

Articles >CHUNK_THRESHOLD chars get split into overlapping chunks for
better embedding quality.  Each chunk is embedded separately but still
maps back to the same article_id, so the retriever returns the full
article when any of its chunks match.

Design constraints (from NEXT_SPRINT.md):
- Chunk size ~800 chars, overlap ~200 chars
- Threshold: only chunk articles >1500 chars
- Embedding text = article title + "\\n" + chunk content
  (title is prepended to every chunk so the embedding carries context)
"""
from dataclasses import dataclass
from typing import List


# Only chunk articles whose content exceeds this length
CHUNK_THRESHOLD = 1500

# Target size per chunk (characters)
CHUNK_SIZE = 800

# Overlap between consecutive chunks
CHUNK_OVERLAP = 200


@dataclass
class EmbeddingChunk:
    """A piece of text ready to be embedded, linked to its source article."""
    article_index: int          # position in the articles list
    text: str                   # the text to embed (title + chunk content)


def chunk_articles(
    articles: list,
    *,
    threshold: int = CHUNK_THRESHOLD,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> List[EmbeddingChunk]:
    """Convert a list of parsed articles into embedding chunks.

    Short articles (≤ threshold) produce a single chunk whose text is
    ``title + "\\n" + content`` (same as the old behaviour).

    Long articles are split into overlapping windows of *content*,
    each prefixed with the title so every chunk carries context about
    which article it belongs to.

    Parameters
    ----------
    articles : list
        Objects with ``.title`` and ``.content`` attributes
        (ParsedArticle from pdf_parser or ArticleDB rows).
    threshold : int
        Minimum content length to trigger chunking.
    chunk_size : int
        Target characters per chunk.
    overlap : int
        Characters of overlap between consecutive chunks.

    Returns
    -------
    List[EmbeddingChunk]
        One or more chunks per article, each carrying the article index
        so callers can map chunks back to article IDs.
    """
    chunks: List[EmbeddingChunk] = []

    for idx, article in enumerate(articles):
        title = getattr(article, "title", "") or ""
        content = getattr(article, "content", "") or ""

        if len(content) <= threshold:
            # Short article → single chunk (same as before)
            chunks.append(EmbeddingChunk(
                article_index=idx,
                text=f"{title}\n{content}",
            ))
        else:
            # Long article → split content into overlapping windows
            step = max(chunk_size - overlap, 1)
            start = 0
            while start < len(content):
                end = start + chunk_size

                # Try to break at a sentence boundary
                window = content[start:end]
                if end < len(content):
                    # Look for the last period within the window
                    last_period = max(
                        window.rfind(". "),
                        window.rfind(".\n"),
                    )
                    if last_period > chunk_size // 3:
                        end = start + last_period + 1
                        window = content[start:end]

                chunks.append(EmbeddingChunk(
                    article_index=idx,
                    text=f"{title}\n{window}",
                ))

                start += step
                # If the remaining text is very short, merge it with the
                # last chunk to avoid tiny trailing fragments
                if start < len(content) and len(content) - start < overlap:
                    break

    return chunks
