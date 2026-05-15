"""LLM client for OpenRouter with citation enforcement and retry logic."""
import asyncio
import httpx
import json
import logging
import re
from typing import List

from app.config import settings
from app.models import Article, Citation
from app.llm.intent import detect_intent_local

logger = logging.getLogger(__name__)

# Retry configuration: delays between attempts (seconds)
_RETRY_DELAYS = [1.0, 3.0]

# Friendly message shown to users when OpenRouter is unreachable
_SERVICE_UNAVAILABLE_MSG = (
    "The AI service is temporarily unavailable. "
    "Please try again in a few moments."
)

AGENTIC_PROMPT = """You are an expert researcher specializing in FIA Formula 1 regulations.
Your goal is to answer the user's question with 100% accuracy using ONLY the provided articles.

You can perform up to 3 research steps. In each step, you can either:
1. SEARCH: If the current articles are insufficient, missing a cross-reference, or if you need to verify a specific detail mentioned (e.g., "as defined in Article X"), request a new search.
2. ANSWER: If you have sufficient information to provide a definitive, citation-backed answer.

CITATION RULES:
- ALWAYS cite articles using the exact article_code from the context, e.g. [Article C4.1] or [Article 54].
- Cite ONLY the articles that directly answer the question. Do NOT cite every article in context — only those whose content you actually reference in your answer.
- Aim for precision: typically 2-5 citations is appropriate. Only cite more if the question genuinely spans many articles.
- If you don't have enough information to answer accurately, say "I don't have enough information in the current regulations to answer this definitively" rather than guessing.
- Do NOT invent or hallucinate article numbers. Only cite codes that appear in CURRENT CONTEXT.
- Pay attention to the year and section of each article — do not mix regulations from different years unless the question asks for comparison.

CRITICAL: If you see a reference like "Article C3.14" or "Appendix 5" which is NOT in your context but seems vital, you MUST perform a SEARCH for that specific term.

RESPONSE FORMAT (JSON ONLY):
{
  "thought": "Brief explanation of what you found and what is missing.",
  "action": "SEARCH" or "ANSWER",
  "search_query": "Precise keywords for next search (if action is SEARCH)",
  "answer": "Your final detailed answer with [Article X.Y] citations (if action is ANSWER)"
}"""

CONVERSATIONAL_PROMPT = """You are a helpful and professional F1 regulations expert.
For non-technical queries or greetings, respond in a friendly manner.
Remind the user that you can answer specific questions about the FIA Formula 1 Technical, Sporting, and Financial Regulations."""


class OpenRouterError(Exception):
    """Raised when OpenRouter is unreachable after all retries."""


class LLMClient:
    """Client for OpenRouter LLM API with agentic research and citation enforcement."""

    def __init__(self):
        self.api_key = settings.openrouter_api_key
        self.model = settings.llm_model
        self.base_url = "https://openrouter.ai/api/v1"

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _call_openrouter(self, payload: dict, timeout: float = 30.0) -> dict:
        """POST to OpenRouter with exponential backoff retry (max 2 retries).

        Raises OpenRouterError if all attempts fail.
        """
        last_exc: Exception = RuntimeError("No attempt made")
        for attempt in range(len(_RETRY_DELAYS) + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
                    response.raise_for_status()
                    return response.json()
            except Exception as exc:
                last_exc = exc
                if attempt < len(_RETRY_DELAYS):
                    delay = _RETRY_DELAYS[attempt]
                    logger.warning(
                        "OpenRouter attempt %d/%d failed: %s. Retrying in %.0fs.",
                        attempt + 1, len(_RETRY_DELAYS) + 1, exc, delay,
                    )
                    await asyncio.sleep(delay)

        logger.error("OpenRouter unreachable after %d attempts: %s", len(_RETRY_DELAYS) + 1, last_exc)
        raise OpenRouterError(str(last_exc)) from last_exc

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    async def detect_intent(self, query: str) -> str:
        """Classify intent locally -- no LLM call, instant, free.

        Returns: 'REGULATIONS' or 'CONVERSATIONAL'
        """
        intent = detect_intent_local(query)
        logger.debug("Intent detected locally: '%s' -> %s", query[:80], intent)
        return intent

    async def prepare_search(self, query: str) -> dict:
        """Single LLM call: extract year/section filters + rewrite query.

        Returns:
            {"year": int|None, "section": str|None, "search_query": str}

        Falls back to safe defaults on error so the pipeline can continue.
        """
        prompt = (
            "You are an F1 regulations search assistant. Given a user query, return a JSON object with:\n"
            "1. \"year\": a 4-digit year (2023-2026) if mentioned, otherwise null.\n"
            "2. \"section\": one of \"Technical\", \"Sporting\", or \"Financial\" based on the topic, otherwise null.\n"
            "   - Technical: car design, weight, dimensions, aerodynamics, wings, floor, engine, power unit, MGU-K, MGU-H, fuel, tyres, chassis.\n"
            "   - Sporting: race procedures, points, penalties, qualifying, safety car, pit stops, flags.\n"
            "   - Financial: cost cap, budget, spending, audit, reporting.\n"
            "3. \"search_query\": a short, keyword-rich rewrite using precise FIA regulatory terminology. Omit conversational filler.\n\n"
            "EXAMPLES:\n"
            "{\"year\": 2026, \"section\": \"Technical\", \"search_query\": \"minimum car weight power unit 2026\"}\n"
            "{\"year\": null, \"section\": \"Technical\", \"search_query\": \"DRS drag reduction system activation zone\"}\n"
            "{\"year\": null, \"section\": \"Sporting\", \"search_query\": \"points scoring system race classification\"}\n"
            "{\"year\": null, \"section\": \"Financial\", \"search_query\": \"cost cap limit financial regulations\"}\n\n"
            f"Query: {query}\n\nRespond with JSON only:"
        )
        try:
            data = await self._call_openrouter(
                payload={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.0,
                    "max_tokens": 120,
                    "response_format": {"type": "json_object"},
                },
                timeout=20.0,
            )
            result = json.loads(data["choices"][0]["message"]["content"])
            year = result.get("year")
            section = result.get("section")
            search_query = result.get("search_query", "").strip() or query
            if section not in ("Technical", "Sporting", "Financial"):
                section = None
            logger.debug("prepare_search: year=%s section=%s query='%s'", year, section, search_query)
            return {"year": year, "section": section, "search_query": search_query}
        except OpenRouterError:
            raise  # propagate so chat.py can return a graceful response
        except Exception as e:
            logger.warning("prepare_search parse error (%s), using original query", e)
            return {"year": None, "section": None, "search_query": query}

    async def generate_reasoning_step(
        self,
        query: str,
        articles: List[Article],
        history: List[dict] = [],
    ) -> dict:
        """Perform a single agentic reasoning step.

        Returns dict with 'thought', 'action', and 'search_query' or 'answer'.
        Falls back to a safe ANSWER on error.
        """
        context = self._build_context(articles)

        history_text = ""
        if history:
            history_text = "\nPREVIOUS RESEARCH STEPS:\n" + "\n".join([
                f"Step {i+1}: Thought: {h['thought']}\nQuery: {h.get('search_query', 'N/A')}"
                for i, h in enumerate(history)
            ])

        user_prompt = (
            f"{history_text}\n"
            f"CURRENT CONTEXT (FIA Formula 1 Regulations):\n{context}\n\n"
            f"ORIGINAL QUESTION: {query}\n\n"
            "Decide if you need to SEARCH more or can ANSWER now. Respond in JSON."
        )

        try:
            data = await self._call_openrouter(
                payload={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": AGENTIC_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.0,
                    "max_tokens": 1500,
                    "response_format": {"type": "json_object"},
                },
                timeout=60.0,
            )
            return json.loads(data["choices"][0]["message"]["content"])
        except OpenRouterError:
            raise
        except Exception as e:
            logger.error("Reasoning step parse error: %s", e)
            return {
                "thought": "Error parsing LLM response.",
                "action": "ANSWER",
                "answer": _SERVICE_UNAVAILABLE_MSG,
            }

    async def generate_answer(
        self,
        query: str,
        articles: List[Article],
    ) -> tuple[str, List[Citation]]:
        """Non-agentic answer generation (fallback path)."""
        if not articles:
            return "No relevant regulations found for your query.", []

        context = self._build_context(articles)
        user_prompt = (
            f"CONTEXT (FIA Formula 1 Regulations):\n{context}\n\n"
            f"QUESTION: {query}\n\nProvide a detailed answer with citations."
        )

        try:
            data = await self._call_openrouter(
                payload={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "You are an expert F1 regulations assistant. Cite articles using [Article X.Y]."},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 2000,
                },
                timeout=60.0,
            )
            answer = data["choices"][0]["message"]["content"]
            return answer, self._extract_citations(articles, answer)
        except OpenRouterError:
            raise

    async def generate_conversational_response(self, query: str) -> str:
        """Generate a response for non-regulation queries."""
        try:
            data = await self._call_openrouter(
                payload={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": CONVERSATIONAL_PROMPT},
                        {"role": "user", "content": query},
                    ],
                    "temperature": 0.7,
                    "max_tokens": 500,
                },
                timeout=30.0,
            )
            return data["choices"][0]["message"]["content"]
        except OpenRouterError:
            logger.warning("Conversational response unavailable.")
            return "I'm here to help with F1 regulations. How can I assist you today?"

    # ------------------------------------------------------------------
    # Deprecated helpers (kept for backwards compatibility)
    # ------------------------------------------------------------------

    async def extract_query_filters(self, query: str) -> dict:
        """Deprecated: use prepare_search() instead."""
        result = await self.prepare_search(query)
        return {"year": result["year"], "section": result["section"]}

    async def rewrite_query(self, query: str) -> str:
        """Deprecated: use prepare_search() instead."""
        result = await self.prepare_search(query)
        return result["search_query"]

    # ------------------------------------------------------------------
    # Private utilities
    # ------------------------------------------------------------------

    # Maximum number of articles to include in LLM context
    MAX_CONTEXT_ARTICLES = 12
    # Truncate individual article content beyond this length
    MAX_ARTICLE_CHARS = 2000

    def _build_context(self, articles: List[Article]) -> str:
        # Trim to top N articles if we have too many
        trimmed = articles[:self.MAX_CONTEXT_ARTICLES]

        context_parts = []
        for rank, article in enumerate(trimmed, start=1):
            lines = [
                f"[Relevance #{rank}] Article {article.article_code}",
                f"Section: {article.section} Regulations {article.year} (Issue {article.issue})",
                f"Title: {article.title}",
            ]
            if article.parent_code:
                lines.append(f"Parent Article: {article.parent_code}")

            content = article.content
            if len(content) > self.MAX_ARTICLE_CHARS:
                # Truncate at a sentence boundary if possible
                truncated = content[:self.MAX_ARTICLE_CHARS]
                last_period = max(truncated.rfind(". "), truncated.rfind(".\n"))
                if last_period > self.MAX_ARTICLE_CHARS // 2:
                    truncated = truncated[:last_period + 1]
                content = truncated + "\n[...truncated]"

            context_parts.append("\n".join(lines) + f"\n\n{content}\n")
        return "\n---\n".join(context_parts)

    # Pattern to find [Article X.Y.z] citations in LLM answers
    _CITATION_PATTERN = re.compile(r'\[Article\s+([A-Za-z]*\d+(?:\.\d+)*(?:\.[a-z])?)\]')

    # Hard cap on citation cards returned to the frontend
    MAX_CITATIONS = 8

    def _extract_cited_codes_ordered(self, answer: str) -> list[str]:
        """Extract article codes cited in the answer, in order of first appearance, deduplicated."""
        seen: set[str] = set()
        ordered: list[str] = []
        for code in self._CITATION_PATTERN.findall(answer):
            if code not in seen:
                seen.add(code)
                ordered.append(code)
        return ordered

    @staticmethod
    def _prune_parent_codes(codes: list[str]) -> list[str]:
        """Remove parent codes when a more specific child is also cited.

        E.g. if both 'C3' and 'C3.9' are cited, drop 'C3' because
        the child is more specific and the parent adds noise.
        """
        code_set = set(codes)
        pruned = []
        for code in codes:
            # Check if any other code starts with this code + "."
            is_parent = any(
                other.startswith(code + ".") for other in code_set if other != code
            )
            if not is_parent:
                pruned.append(code)
        return pruned

    def _extract_citations(
        self, articles: List[Article], answer: str | None = None
    ) -> List[Citation]:
        """Build Citation objects from articles.

        If *answer* is provided, only articles whose code appears as
        ``[Article X.Y]`` in the text are included (precision filter).
        Parent codes are pruned when children exist, and a hard cap
        of MAX_CITATIONS is applied.
        Falls back to all articles when *answer* is None or empty.
        """
        cited_codes_ordered: list[str] | None = None
        if answer:
            raw_codes = self._extract_cited_codes_ordered(answer)
            cited_codes_ordered = self._prune_parent_codes(raw_codes)

        # Build a lookup for