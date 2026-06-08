# Changelog

All notable changes to this project are documented here. This project adheres to
[Semantic Versioning](https://semver.org/).

## [0.1.0] — 2026-06-07

First public release. A self-hostable, structure-aware RAG engine over FIA Formula 1
regulations.

### Highlights

- **Structure-aware retrieval** — the regulation is modeled as a tree
  (Article → Sub-article → Clause) with explicit parent links and a deterministic
  cross-reference graph. Retrieval assembles the full subtree (ancestors + children)
  and follows cross-references one hop, so a clause never arrives without its header.
- **Hybrid search** — pgvector cosine similarity + PostgreSQL full-text search, fused
  with Reciprocal Rank Fusion (RRF), plus an agentic loop that decides when to search
  again vs. answer.
- **Cited, verifiable answers** — every claim maps to an exact article code; out-of-scope
  questions (e.g. historical race results) are declined instead of fabricated.
- **Compare across seasons** — see how a given article changed between years.
- **Local, free embeddings** — `all-MiniLM-L6-v2` via ONNX Runtime, vendored in the repo.
  No torch, no GPU, no HuggingFace download at runtime.
- **Run it fully free** — optional local LLM via Ollama (`LLM_BASE_URL`); OpenRouter is
  the default but optional. Embeddings and retrieval need no API key.
- **One-command demo** — `make demo` builds, starts everything, and loads a sample
  dataset with real embeddings, so search and Compare work immediately without ingesting
  any PDFs.

### Added

- Deterministic structural layer (0 LLM): TOC-aware parser, ingestion validation gate
  (orphans / numbering gaps / TOC coverage / cross-reference resolution), and an
  audit table. Enabled with `STRUCTURAL_PARSER=true`.
- Subtree assembly and cross-reference expansion in the retriever.
- `make` workflow (`demo`, `up`, `seed`, `ingest`, `test`, `lint`, …) and a demo seed.
- Configurable OpenAI-compatible LLM endpoint (OpenRouter / Ollama / any).
- Docs: `ARCHITECTURE.md`, `CONTRIBUTING.md`, updated `QUICKSTART`/`DEPLOYMENT`.
- Feedback (👍/👎) on answers and aggregate usage stats.

### Changed

- Embeddings moved from torch + sentence-transformers to ONNX Runtime (memory-frugal,
  fits a 512MB free tier).
- Answer prompt hardened: less conservative when relevant articles are present, and
  refuses to attribute non-regulation facts to articles.

### Fixed

- Missing `onnxruntime` dependency that crashed the worker on load.
- `ArticleEmbedding.embedding` and `validity`/`latest_year` ORM mappings that caused
  every query to 500.
- Compare now uses a single consistent section across both years and skips stub articles.
- Removed ~430 mis-parsed junk articles (4-digit / `0.x` codes) from the corpus.

### Security

- No credentials committed (verified across the full git history). Admin endpoints are
  key-protected, rate limiting is enabled, queries are parameterized, CORS is restricted,
  and error tracebacks are kept server-side.

### Known limitations

- Hosted demo runs on a free tier — first request after idle is slow (cold start).
- PDF parsing occasionally mis-titles articles; answers may contain errors — always
  verify against the official FIA regulations. Not affiliated with the FIA or Formula 1.

[0.1.0]: https://github.com/alvaroherrera-33/f1-regulations-engine/releases/tag/v0.1.0
