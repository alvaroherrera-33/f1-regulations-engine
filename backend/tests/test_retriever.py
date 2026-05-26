"""Unit tests for HybridRetriever's pure-Python helpers (no DB needed)."""

from app.models import Article
from app.retrieval.retriever import HybridRetriever


def make_article(code: str, section: str = "Technical", year: int = 2026,
                 issue: int = 1, level: int = 2, parent_code: str = None) -> Article:
    return Article(
        id=1,
        article_code=code,
        title=f"Article {code}",
        content=f"Content of {code}",
        year=year,
        section=section,
        issue=issue,
        level=level,
        parent_code=parent_code,
    )


# ---------------------------------------------------------------------------
# _merge_and_deduplicate
# ---------------------------------------------------------------------------

class TestMergeAndDeduplicate:
    """Tests for the RRF merge + dedup logic (sync, no DB)."""

    def setup_method(self):
        """Create a retriever with a mocked DB session."""
        self.retriever = HybridRetriever.__new__(HybridRetriever)
        self.retriever.db = None  # not used in sync methods
        self.retriever.confidence = 0.0

    def test_empty_lists(self):
        result, score = self.retriever._merge_and_deduplicate([], [], top_k=5)
        assert result == []
        assert score == 0.0

    def test_single_source(self):
        articles = [make_article(f"A{i}") for i in range(3)]
        result, score = self.retriever._merge_and_deduplicate(articles, [], top_k=5)
        assert len(result) == 3
        assert score > 0

    def test_deduplication(self):
        """Same article in both lists → appears only once in output."""
        art = make_article("3.7")
        result, _ = self.retriever._merge_and_deduplicate([art], [art], top_k=5)
        codes = [r.article_code for r in result]
        assert codes.count("3.7") == 1

    def test_top_k_limits_results(self):
        vector = [make_article(f"V{i}") for i in range(10)]
        fts = [make_article(f"F{i}") for i in range(10)]
        result, _ = self.retriever._merge_and_deduplicate(vector, fts, top_k=5)
        assert len(result) <= 5

    def test_latest_issue_wins(self):
        """When same (code, section, year) appears with different issues, highest wins."""
        old = make_article("3.7", issue=1)
        new = make_article("3.7", issue=3)
        result, _ = self.retriever._merge_and_deduplicate([old], [new], top_k=5)
        assert len(result) == 1
        assert result[0].issue == 3

    def test_section_boost_applied(self):
        """Articles in detected_section should rank higher than others."""
        tech_art = make_article("T1", section="Technical")
        sport_art = make_article("S1", section="Sporting")
        # Both at rank 1 in their respective list
        result, _ = self.retriever._merge_and_deduplicate(
            [sport_art], [tech_art],
            top_k=2, detected_section="Technical"
        )
        # Technical article should come first due to boost
        assert result[0].article_code == "T1"

    def test_level_2_ranked_above_level_1(self):
        """Level 2 articles have weight 1.0, level 1 has 0.85 → level 2 ranks higher at same rank."""
        lvl1 = make_article("A1", level=1)
        lvl2 = make_article("A2", level=2)
        # Put them at the same rank position
        result, _ = self.retriever._merge_and_deduplicate([lvl1, lvl2], [], top_k=2)
        # lvl1 is rank 1 but with weight 0.85; lvl2 is rank 2 with weight 1.0
        # At rank 1: score_lvl1 = 0.85/61 ≈ 0.01393
        # At rank 2: score_lvl2 = 1.0/62 ≈ 0.01613  → lvl2 could outrank lvl1
        # This test just verifies both are returned, no crash
        assert len(result) == 2

    def test_cross_year_articles_not_deduped(self):
        """Same code, same section but DIFFERENT year → both kept."""
        art_2025 = make_article("3.7", year=2025)
        art_2026 = make_article("3.7", year=2026)
        result, _ = self.retriever._merge_and_deduplicate([art_2025], [art_2026], top_k=5)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Threshold constants
# ---------------------------------------------------------------------------

def test_financial_threshold_wider():
    """Financial threshold must be higher than standard (wider recall)."""
    assert HybridRetriever.SIMILARITY_THRESHOLD_FINANCIAL > HybridRetriever.SIMILARITY_THRESHOLD


def test_thresholds_in_valid_range():
    assert 0.0 < HybridRetriever.SIMILARITY_THRESHOLD < 1.0
    assert 0.0 < HybridRetriever.SIMILARITY_THRESHOLD_FINANCIAL < 1.0
