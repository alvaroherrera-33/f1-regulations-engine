"""Unit tests for the article chunker (no DB, no LLM)."""

from ingestion.chunker import CHUNK_SIZE, EmbeddingChunk, chunk_articles


class FakeArticle:
    def __init__(self, title: str, content: str):
        self.title = title
        self.content = content


# ---------------------------------------------------------------------------
# Short articles
# ---------------------------------------------------------------------------

def test_short_article_single_chunk():
    """Articles shorter than threshold produce exactly one chunk."""
    article = FakeArticle("Art 3.7", "Short content here.")
    chunks = chunk_articles([article])
    assert len(chunks) == 1
    assert chunks[0].article_index == 0
    assert "Art 3.7" in chunks[0].text
    assert "Short content here." in chunks[0].text


def test_multiple_short_articles():
    articles = [FakeArticle(f"Art {i}", f"Content {i}") for i in range(5)]
    chunks = chunk_articles(articles)
    assert len(chunks) == 5
    for i, chunk in enumerate(chunks):
        assert chunk.article_index == i


def test_empty_title_and_content():
    article = FakeArticle("", "")
    chunks = chunk_articles([article])
    assert len(chunks) == 1


# ---------------------------------------------------------------------------
# Long articles
# ---------------------------------------------------------------------------

def test_long_article_multiple_chunks():
    """Articles over threshold are split into multiple chunks."""
    long_content = "This is a sentence. " * 200  # ~4000 chars
    article = FakeArticle("Article 10", long_content)
    chunks = chunk_articles([article])
    assert len(chunks) > 1


def test_all_chunks_carry_title():
    """Every chunk for a long article should include the title prefix."""
    long_content = "Regulation text. " * 200
    article = FakeArticle("My Title", long_content)
    chunks = chunk_articles([article])
    for chunk in chunks:
        assert "My Title" in chunk.text


def test_chunks_reference_same_article_index():
    """All chunks from one article share the same article_index."""
    long_content = "X " * 1500
    article = FakeArticle("Art", long_content)
    chunks = chunk_articles([article])
    assert all(c.article_index == 0 for c in chunks)


def test_chunk_size_respected():
    """No chunk text should be much larger than CHUNK_SIZE + title overhead."""
    long_content = "A" * 5000
    article = FakeArticle("T", long_content)
    chunks = chunk_articles([article])
    # Each chunk content window <= CHUNK_SIZE, plus title + newline
    max_expected = CHUNK_SIZE + len("T\n") + 50  # small buffer for sentence break
    for chunk in chunks:
        assert len(chunk.text) <= max_expected, f"Chunk too large: {len(chunk.text)}"


def test_mixed_articles():
    """Mix of short and long articles are indexed correctly."""
    articles = [
        FakeArticle("Short", "tiny"),
        FakeArticle("Long", "word " * 500),
        FakeArticle("Short2", "also tiny"),
    ]
    chunks = chunk_articles(articles)
    # Short articles → 1 chunk each; long article → multiple
    short1_chunks = [c for c in chunks if c.article_index == 0]
    long_chunks = [c for c in chunks if c.article_index == 1]
    short2_chunks = [c for c in chunks if c.article_index == 2]
    assert len(short1_chunks) == 1
    assert len(long_chunks) > 1
    assert len(short2_chunks) == 1


def test_chunk_returns_embedding_chunk_type():
    article = FakeArticle("T", "content")
    chunks = chunk_articles([article])
    assert all(isinstance(c, EmbeddingChunk) for c in chunks)
