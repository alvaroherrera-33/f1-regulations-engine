"""Local embedding generation using sentence-transformers.

Key design decisions:
- Singleton: the model (~400 MB) is loaded exactly once per process.
- Query cache: up to 256 recent query embeddings are cached in memory.
  Article embeddings are generated only during ingestion, never cached here.
"""
import logging
from typing import List, Optional

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Module-level singleton -- avoids reloading the model on every request.
_instance: Optional["LocalEmbeddingsGenerator"] = None


def get_embeddings_generator(model_name: str = "all-MiniLM-L6-v2") -> "LocalEmbeddingsGenerator":
    """Return the singleton LocalEmbeddingsGenerator (loads model once)."""
    global _instance
    if _instance is None:
        _instance = LocalEmbeddingsGenerator(model_name)
    return _instance


class LocalEmbeddingsGenerator:
    """Generate embeddings using a local sentence-transformers model.

    Use get_embeddings_generator() instead of instantiating directly so the
    model is loaded only once per process.
    """

    # Shared query cache (class-level so it survives across retriever instances).
    _query_cache: dict[str, list[float]] = {}
    _MAX_CACHE_SIZE: int = 256

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        logger.info("Loading local embedding model: %s", model_name)
        self.model = SentenceTransformer(model_name)
        logger.info(
            "Embedding model loaded. Dimension: %d",
            self.model.get_sentence_embedding_dimension(),
        )

    async def generate(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts (used during ingestion)."""
        if not texts:
            return []
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return [emb.tolist() for emb in embeddings]

    async def generate_one(self, text: str) -> List[float]:
        """Generate embedding for a single text, with LRU-style cache.

        The cache is intended for repeated query strings (e.g. the same
        question asked twice). Article embeddings bypass this path entirely.
        """
        cache = self.__class__._query_cache

        if text in cache:
            logger.debug("Embedding cache hit: '%s'", text[:60])
            return cache[text]

        result = await self.generate([text])
        embedding = result[0] if result else []

        # Simple FIFO eviction when cache is full
        if len(cache) >= self.__class__._MAX_CACHE_SIZE:
            oldest_key = next(iter(cache))
            del cache[oldest_key]

        cache[text] = embedding
        logger.debug("Embedding cache miss (size now %d): '%s'", len(cache), text[:60])
        return embedding


async def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """Convenience function used by the ingestion pipeline."""
    generator = get_embeddings_generator()
    return await generator.generate(texts)
