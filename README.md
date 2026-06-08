# F1 Regulations Engine

**AI-powered search across FIA Formula 1 regulations**

![Python 3.11](https://img.shields.io/badge/python-3.11-blue?logo=python&logoColor=white)
![License MIT](https://img.shields.io/badge/license-MIT-green)
![FastAPI](https://img.shields.io/badge/FastAPI-async-009688?logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-14-black?logo=next.js)
![CI](https://github.com/alvaroherrera-33/f1-regulations-engine/actions/workflows/ci.yml/badge.svg)

Ask questions about Formula 1 regulations in plain language and receive precise, citation-backed answers grounded in official FIA documents. Every response references the exact articles it draws from, so you can verify each claim against the source. Always confirm critical decisions against the official regulation.

Live demo: [f1-regulations-engine-project.vercel.app](https://f1-regulations-engine-project.vercel.app)

> **Why this is different from a generic RAG:** regulations aren't flat text — they're a
> numbered, cross-referenced tree where the hierarchy *is* the meaning. This engine models
> that tree explicitly (Article → Sub-article → Clause), retrieves whole **subtrees** instead
> of loose chunks, and follows cross-references deterministically — so a clause never arrives
> without its header, and "subject to Article 3.2" pulls 3.2 into context.

---

![F1 Regulations Engine — chat interface showing a question about minimum car weight with cited article](docs/screenshot.png)

---

## Features

- **Structure-aware retrieval** — Models the regulation hierarchy (Article → Sub-article → Clause) with an explicit cross-reference graph; assembles full subtrees and follows references one hop (optional, `STRUCTURAL_PARSER=true`).
- **Hybrid search** — Combines vector similarity (pgvector) and full-text search (PostgreSQL), merged with Reciprocal Rank Fusion (RRF) for best-of-both recall and precision.
- **Agentic research loop** — Search-reason cycles that follow cross-references between articles before committing to an answer.
- **Mandatory citations** — Every answer includes exact article codes, section, year, and issue, and declines out-of-scope questions instead of fabricating them.
- **Compare across seasons** — See how a given article changed between years.
- **Local, free embeddings** — `all-MiniLM-L6-v2` via ONNX Runtime, vendored in the repo. No torch, no GPU, no third-party embedding API.
- **Self-host for free** — One-command demo (`make demo`); optional local LLM via Ollama, so the whole stack can run with no paid API.
- **Multilingual queries** — Accepts questions in English, Spanish, French, German, and Italian.
- **Feedback loop** — Thumbs up/down on each answer feeds a `query_logs` table for ongoing quality monitoring.

---

## Architecture

```
Browser
  |
  | HTTP
  v
Next.js 14  (Vercel)
  - Chat interface with citation cards
  - Year / section / issue filters
  |
  | REST
  v
FastAPI  (Render)
  |
  |-- detect_intent()        local regex classifier, zero LLM calls
  |-- prepare_search()       1 LLM call: extract year + section + rewritten query
  |
  `-- Agentic loop (max 3 steps)
        |
        |-- HybridRetriever
        |     |- embed query         all-MiniLM-L6-v2, 384 dims, local
        |     |- vector search       pgvector cosine distance (threshold 0.75)
        |     |- full-text search    PostgreSQL tsvector / tsquery
        |     `- merge               Reciprocal Rank Fusion (k=60)
        |
        `-- generate_reasoning_step()   LLM: SEARCH | ANSWER
              `-- if ANSWER --> return response + citations
  |
  | asyncpg
  v
PostgreSQL + pgvector  (Supabase)
  - documents            PDF metadata
  - articles             extracted articles with year / section / issue
  - article_embeddings   384-dim vectors (one per article)
  - query_logs           request history and feedback
```

---

## Quick Start

Requires Docker and Docker Compose. An [OpenRouter](https://openrouter.ai) API key is
needed only for generating chat answers — retrieval, the demo, and the Compare view
work without one (embeddings run locally, no API or GPU needed).

### Fastest: run the built-in demo (no PDFs required)

```bash
git clone https://github.com/alvaroherrera-33/f1-regulations-engine.git
cd f1-regulations-engine
cp .env.example .env          # set POSTGRES_PASSWORD (and OPENROUTER_API_KEY for chat answers)
make demo                     # builds, starts everything, and loads a sample dataset
# → Frontend: http://localhost:3000   ·   API docs: http://localhost:8000/docs
```

`make demo` seeds ~30 illustrative sample articles **with real embeddings**, so search and
Compare work immediately. Run `make help` to see all commands.

### Full setup: ingest your own regulation PDFs

```bash
docker-compose up --build                 # or: make up
# Place FIA regulation PDFs under archives/ (see docs/ARCHIVE_SETUP.md), then:
docker-compose exec backend python -m scripts.ingest_archives   # or: make ingest
```

The PDFs are **not** distributed with this repo (you provide your own). Embeddings are
generated locally with a vendored ONNX model (`backend/models/`) — no HuggingFace download
or torch at runtime. See [docs/QUICKSTART.md](docs/QUICKSTART.md) for details and
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for production deployment (Render + Supabase + Vercel).

---

## Tech Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Backend | FastAPI (Python 3.11) | Async, uvicorn |
| Frontend | Next.js 14 (TypeScript) | App router, inline styles |
| Database | PostgreSQL + pgvector | 384-dim vectors, hybrid search |
| Embeddings | all-MiniLM-L6-v2 | Runs locally on backend, no external API |
| LLM | OpenRouter API | Model configurable via `LLM_MODEL` env var |
| Backend hosting | Render (free tier) | |
| Frontend hosting | Vercel | |
| Database hosting | Supabase | Session Pooler for IPv4 compatibility |
| Local dev | Docker Compose | Three services: db, backend, frontend |

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Database connectivity check |
| GET | `/status` | Article and embedding counts |
| GET | `/warmup` | Pre-load embedding model (cron keep-alive) |
| POST | `/api/chat` | Main RAG query — returns answer, citations, query_id |
| POST | `/api/chat/feedback` | Submit thumbs up/down for a query_id |
| GET | `/api/stats` | Aggregated quality metrics from query_logs |
| GET | `/api/articles` | List articles with optional filters |
| GET | `/api/articles/{code}` | Article by code |
| POST | `/api/upload` | Upload a PDF and trigger ingestion |
| GET | `/docs` | Swagger UI |

### Example request

```bash
curl -X POST https://f1-regulations-engine.onrender.com/api/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the minimum car weight in 2026?", "year": 2026, "section": "Technical"}'
```

```json
{
  "answer": "In 2026 the minimum car weight (mass) is defined as follows: During Sprint Qualifying and Qualifying sessions the Minimum Mass is **726 kg plus the Nominal Tyre Mass**. In all other sessions the Minimum Mass is **724 kg plus the Nominal Tyre Mass**. [Article C4.1]",
  "citations": [
    {
      "article_code": "C4.1",
      "title": "Minimum mass",
      "excerpt": "C4.1 Minimum mass During the Sprint Qualifying and Qualifying sessions, the Minimum Mass is 726kg plus the Nominal Tyre Mass...",
      "year": 2026,
      "section": "Technical",
      "issue": 18
    }
  ],
  "retrieved_count": 4,
  "query_id": 1042
}
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `POSTGRES_PASSWORD` | Yes (docker) | Password for the bundled Postgres container |
| `OPENROUTER_API_KEY` | For chat answers | LLM API key (not needed with a keyless local server) |
| `LLM_BASE_URL` | No | OpenAI-compatible endpoint (default: OpenRouter; e.g. `http://ollama:11434/v1`) |
| `LLM_MODEL` | No | Model name (default: `openai/gpt-oss-120b`) |
| `DATABASE_URL` | No (docker) | Async PostgreSQL URL; built automatically by docker-compose |
| `ALLOWED_ORIGINS` | No | CORS origins, comma-separated (default: `http://localhost:3000`) |
| `STRUCTURAL_PARSER` | No | Enable TOC-aware parsing + subtree retrieval (default: `false`) |

See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for how the pipeline works and
[CONTRIBUTING.md](CONTRIBUTING.md) to run the tests and contribute.

---

## Disclaimer

This is an independent, unofficial project. It is **not affiliated with, endorsed by,
or associated with the FIA or Formula 1**. "Formula 1", "F1", and related marks belong
to their respective owners. The tool is for informational purposes only, may contain
errors, and is **not legal advice** — always verify against the official FIA regulations.
Regulation PDFs are not distributed with this repository; you supply your own.

---

## License

MIT. Built by [Álvaro Herrera](https://github.com/alvaroherrera-33).
