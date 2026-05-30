"""Local embedding generation using ONNX Runtime (memory-frugal).

Why ONNX instead of torch + sentence-transformers:
- The torch runtime (~200-250MB RSS) plus the model weights overflowed the
  512MB free-tier worker on load (OOM / 502s). ONNX Runtime (~50MB) running
  the SAME all-MiniLM-L6-v2 model keeps the whole web process well under 512MB.
- The ONNX export (Xenova/all-MiniLM-L6-v2) is the same model, so the 384-dim
  embeddings live in the SAME vector space as the ones already stored — no
  re-ingestion needed. (Verified: an ONNX query embedding retrieves the correct
  articles from the torch-generated embeddings already in the DB.)

Pipeline replicated from sentence-transformers: tokenize -> model ->
mean-pool over the attention mask -> L2-normalize.

Key design decisions:
- Singleton: the session + tokenizer are loaded exactly once per process.
- Query cache: up to 256 recent query embeddings are cached in memory.
"""
import logging
import os
from typing import List, Optional

import numpy as np

# Keep the math single-threaded: per-thread memory arenas are what blow past
# the free-tier limit. (For ONNX the footprint is small, but this stays safe.)
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import onnxruntime as ort
from huggingface_hub import hf_hub_download
from tokenizers import Tokenizer

logger = logging.getLogger(__name__)

# ONNX export of sentence-transformers/all-MiniLM-L6-v2 (same vector space).
_ONNX_REPO = "Xenova/all-MiniLM-L6-v2"
_ONNX_FILE = "onnx/model.onnx"
_MAX_SEQ_LEN = 256  # all-MiniLM-L6-v2 max sequence length

# Module-level singleton -- avoids reloading the model on every request.
_instance: Optional["LocalEmbeddingsGenerator"] = None


def get_embeddings_generator(model_name: str = "all-MiniLM-L6-v2") -> "LocalEmbeddingsGenerator":
    """Return the singleton LocalEmbeddingsGenerator (loads model once)."""
    global _instance
    if _instance is None:
        _instance = LocalEmbeddingsGenerator(model_name)
    return _instance


class LocalEmbeddingsGenerator:
    """Generate embeddings with a local ONNX model (all-MiniLM-L6-v2).

    Use get_embeddings_generator() instead of instantiating directly so the
    model is loaded only once per process.
    """

    # Shared query cache (class-level so it survives across retriever instances).
    _query_cache: dict[str, list[float]] = {}
    _MAX_CACHE_SIZE: int = 256

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        logger.info("Loading ONNX embedding model: %s", _ONNX_REPO)
        model_path = hf_hub_download(_ONNX_REPO, _ONNX_FILE)
        tokenizer_path = hf_hub_download(_ONNX_REPO, "tokenizer.json")

        self.tokenizer = Tokenizer.from_file(tokenizer_path)
        self.tokenizer.enable_truncation(_MAX_SEQ_LEN)
        self.tokenizer.enable_padding()

        so = ort.SessionOptions()
        so.intra_op_num_threads = 1
        so.inter_op_num_threads = 1
        self.session = ort.InferenceSession(
            model_path, sess_options=so, providers=["CPUExecutionProvider"]
        )
        self._input_names = {i.name for i in self.session.get_inputs()}
        logger.info("ONNX embedding model loaded. Dimension: 384")

    def _embed(self, texts: List[str]) -> np.ndarray:
        """Tokenize -> run model -> mean-pool -> normalize. Returns (N, 384)."""
        encodings = self.tokenizer.encode_batch(texts)
        input_ids = np.array([e.ids for e in encodings], dtype=np.int64)
        attention_mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)

        inputs = {"input_ids": input_ids, "attention_mask": attention_mask}
        # Some exports also require token_type_ids (all zeros for single-segment).
        if "token_type_ids" in self._input_names:
            inputs["token_type_ids"] = np.zeros_like(input_ids)

        token_embeddings = self.session.run(None, inputs)[0]  # (N, T, 384)

        # Mean pooling weighted by the attention mask (sentence-transformers default).
        mask = attention_mask[..., None].astype(np.float32)
        summed = (token_embeddings * mask).sum(axis=1)
        counts = np.clip(mask.sum(axis=1), 1e-9, None)
        pooled = summed / counts

        # L2 normalize so cosine distance matches the stored embeddings.
        norms = np.linalg.norm(pooled, axis=1, keepdims=True)
        norms = np.clip(norms, 1e-12, None)
        return pooled / norms

    async def generate(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts (used during ingestion)."""
        if not texts:
            return []
        out: List[List[float]] = []
        BATCH = 16
        for i in range(0, len(texts), BATCH):
            vecs = self._embed(texts[i:i + BATCH])
            out.extend(v.tolist() for v in vecs)
        return out

    async def generate_one(self, text: str) -> List[float]:
        """Generate embedding for a single text, with FIFO query cache."""
        cache = self.__class__._query_cache

        if text in cache:
            logger.debug("Embedding cache hit: '%s'", text[:60])
            return cache[text]

        result = await self.generate([text])
        embedding = result[0] if result else []

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
