# Architecture

A Retrieval-Augmented Generation (RAG) system over FIA Formula 1 regulation PDFs. You ask
a question in natural language; the system retrieves the relevant regulation articles and
generates an answer with exact citations.

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI (Python 3.11), async, uvicorn |
| Frontend | Next.js 14 (TypeScript, App Router, inline styles) |
| Database | PostgreSQL + pgvector (384-dim vectors, hybrid search) |
| Embeddings | `all-MiniLM-L6-v2` via **ONNX Runtime**, vendored in `backend/models/` (local, free) |
| LLM | Any OpenAI-compatible endpoint (OpenRouter by default, or local Ollama) |
| Dev | Docker Compose (db + backend + frontend) |

Embeddings are deterministic and run locally — no API, GPU, or HuggingFace download at
runtime. Only answer *generation* needs an LLM.

## Query flow (`POST /api/chat`)

```
1. detect_intent()      local regex classifier → REGULATIONS or CONVERSATIONAL (0 LLM)
2. prepare_search()     one LLM call → extract year + section + rewritten query
3. agentic loop (≤2 steps):
     retrieve_articles()        hybrid search (below)
     generate_reasoning_step()  LLM decides: SEARCH again or ANSWER
4. returns answer + citations + query_id (for feedback)
```

`CONVERSATIONAL` queries skip the database and answer directly.

## Hybrid retrieval (`app/retrieval/retriever.py`)

- **Vector** similarity (pgvector cosine distance) +
- **Full-text search** (PostgreSQL `tsvector`/`tsquery`), merged with
- **Reciprocal Rank Fusion** (RRF, `k=60`) — the core ranking differentiator.
- Strict deduplication by `(article_code, section, year)`, keeping the latest issue.
- Context assembly: pull the parent/ancestor articles so a clause never arrives without
  its header.

## Structural layer (optional, `STRUCTURAL_PARSER=true`)

A deterministic (0 LLM) layer that makes the document tree a first-class citizen:

- `structural_parser.py` uses the embedded PDF table of contents as ground truth and
  extracts cross-references.
- A validation gate (`structural_validation.py`) checks orphans, numbering gaps, TOC
  coverage, and cross-reference resolution at ingestion time.
- Retrieval assembles the full subtree (ancestors + children) and follows resolved
  cross-references one hop — improving recall on deeply nested sections (e.g. Financial).

When the flag is off, the legacy regex parser and single-level parent enrichment are used.

## Ingestion (`backend/ingestion/`, run locally)

```
PDF → PyMuPDF text → regex/structural parse → articles (3 levels)
    → chunk long articles → ONNX embeddings → PostgreSQL (articles + article_embeddings)
```

Ingestion runs from `scripts/ingest_archives.py` against PDFs you place in `archives/`
(see `docs/ARCHIVE_SETUP.md`). It never runs as part of serving requests.

## Data model (`backend/database/schema.sql`)

- `documents` — one per (year, section, issue)
- `articles` — `article_code`, `parent_code`/`parent_id`, `level`, `content`, plus
  structural fields (`is_stub`, `structural_status`)
- `article_embeddings` — `vector(384)` per chunk
- `article_references` — deterministic cross-reference graph
- `query_logs`, `article_diffs`, `document_structure_audit`, `fia_sync_log`

`schema.sql` creates everything; `make seed` loads a small demo dataset with real
embeddings so the app works without ingesting any PDFs.
