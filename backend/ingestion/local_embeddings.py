"""Local embedding generation using sentence-transformers.

Key design decisions:
- Singleton: the model (~400 MB) is loaded exactly once per process.
- Query cache: up to 256 recent query embeddings are cached in memory.
  Article embeddings are generated only during ingestion, never cached here.
"""
import logging
import os
from typing import List, Optional

# --- Memory frugality for the 512MB free tier (must run BEFORE torch import) ---
# torch allocates per-thread memory arenas; pinning to a single thread cuts the
# resident set substantially and prevents the worker from being OOM-killed when
# the embedding model loads. Set only if the deployer hasn't overridden them.
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from sentence_transformers import SentenceTransformer

try:
    import torch
    torch.set_num_threads(1)
    torch.set_grad_enabled(False)  # inference only — no autograd buffers
except Exception:  # pragma: no cover - torch always present in prod
    torch = None

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
        self.model = SentenceTransformer(model_name, device="cpu")
        logger.info(
            "Embedding model loaded. Dimension: %d",
            self.model.get_sentence_embedding_dimension(),
        )

    async def generate(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts (used during ingestion)."""
        if not texts:
            return []
        embeddings = self.model.encode(
            texts, convert_to_numpy=True, batch_size=16, show_progress_bar=False
        )
        return [emb.tolist() for emb in embeddings]

    async def generate_one(self, text: str) -> List[float]:
        """Generate embedding for a single text, with LRU-style cache.

        The cache is intended for repeated query strings (e.g. the same
        question asked twice). Article embeddings bypass this path entirely.
        """
        cache = self.__class__._query_cache