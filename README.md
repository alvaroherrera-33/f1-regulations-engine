# 🏎️ F1 Regulations RAG Engine

A legal-grade Retrieval-Augmented Generation (RAG) system for querying FIA Formula 1 regulations. It combines semantic vector search with SQL filtering, intelligent query routing, and mandatory article citation enforcement.

---

## ✨ Key Features

| Feature | Description |
|---|---|
| **Best Possible Search** | Hybrid RRF (Vector + FTS) search with strict latest-issue deduplication |
| **Agentic Research** | Multi-step research loop (SEARCH vs ANSWER) resolving cross-references |
| **Premium F1 UI** | High-performance, branded dashboard with real-time research visualization |
| **Mandatory Citations** | Every response includes exact article references with context excerpts |
| **Intent Routing** | Distinguishes regulation queries from casual conversation |
| **Local Embeddings** | `all-MiniLM-L6-v2` model running locally on the backend |
| **Interactive Chat** | Next.js interface with Markdown rendering and view densities |
| **PDF Ingestion** | Hierarchical parsing pipeline for complex regulation structures |

---

## 🏗️ System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                         USER                                  │
└─────────────────────────┬────────────────────────────────────┘
                          │  HTTP / Browser
                          ▼
┌──────────────────────────────────────────────────────────────┐
│              FRONTEND  (Next.js 14 · Port 3000)              │
│  • Interactive chat interface                                 │
│  • Filters: year, section, issue                             │
│  • PDF upload panel                                          │
└─────────────────────────┬────────────────────────────────────┘
                          │  REST API
                          ▼
┌──────────────────────────────────────────────────────────────┐
│              BACKEND  (FastAPI · Port 8000)                   │
│                                                              │
│  ┌──────────────────┐  ┌────────────────────────────────┐   │
│  │  /api/chat        │  │  /api/upload                   │   │
│  │                   │  │  /api/articles                 │   │
│  │  1. detect_intent │  │  /health   /status             │   │
│  │  2. retrieve      │  │                                │   │
│  │  3. generate      │  │                                │   │
│  └─────────┬─────────┘  └────────────────────────────────┘  │
│            │                                                  │
│  ┌─────────▼──────────────────────────────────────────────┐  │
│  │              LLM Client  (OpenRouter)                   │  │
│  │  • detect_intent()  → REGULATIONS / CONVERSATIONAL     │  │
│  │  • generate_answer() → answer + citations               │  │
│  │  • generate_conversational_response()                   │  │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │              HybridRetriever                          │    │
│  │  1. Embed query  (local model, 384 dims)             │    │
│  │  2. SQL filters  (year, section, issue)              │    │
│  │  3. Cosine distance search  (pgvector)               │    │
│  │  4. Return top-5 articles                            │    │
│  └──────────────────────────────────────────────────────┘    │
└──────────────────────────┬───────────────────────────────────┘
                           │  asyncpg / SQLAlchemy
                           ▼
┌──────────────────────────────────────────────────────────────┐
│         PostgreSQL + pgvector  (Port 5432)                   │
│  • documents          — PDF metadata                         │
│  • articles           — extracted articles + year/section     │
│  • article_embeddings — 384-dim vectors per article          │
└──────────────────────────────────────────────────────────────┘
```

---

## 🔄 Chat Query Flow

```
User types: "What is the minimum weight of the car in 2026?"
                      │
                      ▼
        [1] detect_intent()  (LLM call)
            → "REGULATIONS"
                      │
                      ▼
        [2] Agentic Research Loop (max 3 steps)
            • generate_reasoning_step() → Action: SEARCH
            • HybridRetriever.retrieve()
              - Vector Search (pgvector)
              - Full-Text Search (ts_rank)
              - Merge results via **RRF**
              - Deduplicate by (code, year, section) + Max(issue)
            • (Optional) Follow-up SEARCH if cross-references found
                      │
                      ▼
        [3] LLMClient.generate_answer()
            • Build context from retrieved/enriched articles
            • System prompt enforces citing exact articles
            • Populate `research_steps` for frontend feedback
                      │
                      ▼
        ChatResponse { answer, citations[], research_steps, retrieved_count }
```

If the query is conversational ("hello", "thanks"…):
```
        [1] detect_intent() → "CONVERSATIONAL"
        [2] generate_conversational_response()  (no DB lookup)
            → Friendly reply, no vector search performed
```

---

## 📁 Project Structure

```
f1-regulations-engine/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI: /health, /status + router includes
│   │   ├── config.py            # Settings loaded from .env (pydantic-settings)
│   │   ├── database.py          # asyncpg engine + async SQLAlchemy session
│   │   ├── models.py            # Pydantic models (API) and SQLAlchemy ORM models
│   │   ├── llm/
│   │   │   └── client.py        # LLMClient: intent detection + RAG answers
│   │   ├── retrieval/
│   │   │   └── retriever.py     # HybridRetriever: SQL + vector search
│   │   └── routes/
│   │       ├── chat.py          # POST /api/chat  — main endpoint
│   │       ├── articles.py      # GET /api/articles, GET /api/articles/{code}
│   │       └── upload.py        # POST /api/upload — PDF upload + pipeline trigger
│   ├── ingestion/
│   │   ├── pdf_parser.py        # PDFParser: extracts hierarchical articles from PDFs
│   │   ├── local_embeddings.py  # LocalEmbeddingsGenerator (all-MiniLM-L6-v2)
│   │   ├── pipeline.py          # IngestionPipeline: parse → embed → store
│   │   └── embeddings.py        # (OpenRouter embedding alternative, not active)
│   ├── database/
│   │   └── schema.sql           # DDL: documents, articles, article_embeddings
│   ├── scripts/
│   │   └── ingest_archives.py   # Bulk ingest script for PDFs in archives/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── app/
│   │   ├── page.tsx             # Main page (chat)
│   │   ├── layout.tsx           # Global layout
│   │   ├── chat/                # /chat route
│   │   └── upload/              # /upload route
│   ├── components/              # React components
│   ├── lib/                     # API client (fetches to backend)
│   ├── package.json
│   └── Dockerfile
├── archives/                    # Regulation PDFs (organised by year)
├── data/                        # PDFs uploaded via /api/upload
├── docker-compose.yml           # Local dev: db + backend + frontend
├── .env                         # Environment variables (not committed)
└── .env.example                 # Template of required variables
```

---

## 🗄️ Database Schema

```sql
-- Ingested PDF documents
documents
  id          SERIAL PRIMARY KEY
  name        VARCHAR(255)    -- original filename
  year        INTEGER         -- regulation year (e.g. 2024)
  section     VARCHAR(50)     -- "Technical" | "Sporting" | "Financial"
  issue       INTEGER         -- regulation issue number
  file_path   VARCHAR(500)
  uploaded_at TIMESTAMP

-- Articles extracted from PDFs
articles
  id           SERIAL PRIMARY KEY
  document_id  → documents.id
  article_code VARCHAR(50)    -- e.g. "3.7", "12.4.a"
  parent_code  VARCHAR(50)    -- parent article code
  level        INTEGER        -- 1=Article, 2=Sub-article, 3=Clause
  title        TEXT
  content      TEXT
  year         INTEGER
  section      VARCHAR(50)
  issue        INTEGER

-- Vector embeddings (1 per article)
article_embeddings
  id         SERIAL PRIMARY KEY
  article_id → articles.id
  embedding  VECTOR(384)     -- all-MiniLM-L6-v2, cosine similarity
```

---

## 🧠 LLM Module: `app/llm/client.py`

`LLMClient` handles three types of calls to **OpenRouter**:

### 1. `detect_intent(query)` → `"REGULATIONS"` | `"CONVERSATIONAL"`
- Fast call (max_tokens=50, temperature=0.1)
- Avoids unnecessary DB lookups for non-technical questions
- Default fallback: `"REGULATIONS"` for safety

### 2. `generate_answer(query, articles)` → `(answer, citations)`
- Very low temperature (0.1) for factual, deterministic responses
- Builds a formatted context: `[Article X.Y] Title\nContent`
- System prompt enforces citing exact articles and not hallucinating
- Extracts citations (first 200 chars of each retrieved article)

### 3. `generate_conversational_response(query)` → `answer`
- Higher temperature (0.7) for natural, friendly replies
- Does not access the database at all
- Reminds the user what regulations it can help with

---

## 🔍 Retrieval Module: `app/retrieval/retriever.py`

```python
HybridRetriever.retrieve(query, year, section, issue, top_k=5)
```

1. **Embed the query** using `all-MiniLM-L6-v2` locally
2. **Build optional SQL filters** for `year`, `section`, `issue`
3. **Execute Hybrid Search**:
   - **Vector similarity** via pgvector (cosine distance)
   - **Full-Text search** via PostgreSQL `ts_rank_cd`
4. **Reciprocal Rank Fusion (RRF)**: Mathematically merge results from both ranked lists to maximize relevance.
5. **Strict Deduplication**: Resolve results to unique `(article_code, section, year)` keys, prioritizing the **MAX(issue)** to ensure data from the latest regulation update.
6. **Parent Enrichment**: Automatically fetch parent articles from the same latest issue to provide complete context.

---

## ⚙️ Ingestion Pipeline: `ingestion/pipeline.py`

Steps to add a new PDF to the system:

```
PDF ──► PDFParser ──► hierarchical articles
             │
             ▼
  LocalEmbeddingsGenerator (all-MiniLM-L6-v2)
             │
             ▼
  INSERT INTO articles + article_embeddings
```

**PDF Parser** (`pdf_parser.py`):
- Uses **PyMuPDF** to read plain text page by page
- Detects article headers with regex: `^\d+(?:\.\d+)?(?:\.[a-z])?\s+.*`
- Builds 3-level hierarchy: Article → Sub-article → Clause
- Deduplicates using a `seen_codes` set to avoid false positives on numbered lists

---

## 🌐 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | API info |
| `GET` | `/health` | Service + database health check |
| `GET` | `/status` | Index stats: documents, articles, embeddings |
| `POST` | `/api/chat` | **Main RAG query endpoint** |
| `GET` | `/api/articles` | List articles (filters: year, section, issue, limit) |
| `GET` | `/api/articles/{code}` | Article by code (e.g. `3.7.1`) |
| `POST` | `/api/upload` | Upload a PDF for ingestion |
| `GET` | `/api/upload/status/{job_id}` | Ingestion job status |
| `GET` | `/docs` | Interactive Swagger UI |

### Example: POST `/api/chat`

```json
// Request
{
  "query": "What is the minimum weight of the car?",
  "year": 2024,
  "section": "Technical",
  "issue": 1
}

// Response
{
  "answer": "According to Article 4.1, the minimum weight of the car...",
  "citations": [
    {
      "article_code": "4.1",
      "title": "Weight",
      "excerpt": "The weight of the car, inclusive of the driver...",
      "year": 2024,
      "section": "Technical",
      "issue": 1
    }
  ],
  "retrieved_count": 5
}
```

---

## 🚀 Quick Start (local with Docker)

### Prerequisites
- Docker & Docker Compose
- [OpenRouter](https://openrouter.ai) API key

### Steps

```bash
# 1. Clone the repository
git clone <repo-url>
cd f1-regulations-engine

# 2. Configure environment variables
echo "OPENROUTER_API_KEY=sk-or-..." > .env

# 3. Start all services
docker-compose up --build

# 4. Ingest the PDFs in archives/
docker-compose exec backend python -m scripts.ingest_archives

# 5. Access
#    Frontend:  http://localhost:3000
#    API docs:  http://localhost:8000/docs
#    Health:    http://localhost:8000/health
```

### `archives/` folder structure

```
archives/
├── 2024/
│   ├── Technical_Regulations_2024_Issue_1.pdf
│   └── Sporting_Regulations_2024_Issue_1.pdf
└── 2023/
    └── ...
```

---

## 🔧 Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENROUTER_API_KEY` | ✅ | — | OpenRouter API key |
| `DATABASE_URL` | ✅ | — | Async PostgreSQL URL (`postgresql+asyncpg://...`) |
| `LLM_MODEL` | ❌ | `openai/gpt-oss-120b` | Model to use via OpenRouter |
| `ALLOWED_ORIGINS` | ❌ | `http://localhost:3000` | CORS allowed origins (comma-separated) |
| `MAX_UPLOAD_SIZE` | ❌ | `52428800` (50 MB) | Maximum PDF size in bytes |
| `UPLOAD_DIR` | ❌ | `data/regulations` | Directory where uploaded PDFs are saved |
| `PORT` | ❌ | `8000` | Backend server port |

---

## 🧪 Tests

```bash
# Chat endpoint test
python backend/test_api.py

# Intent routing test
python backend/test_routing.py

# Quick LLM connectivity test
python backend/simple_llm_test.py
```

---

## 🚢 Production Deployment (Railway)

See [DEPLOYMENT.md](./DEPLOYMENT.md) for the full guide.

**Summary**:
1. Create a Railway project with a **PostgreSQL + pgvector** service
2. Deploy the **backend** from the `backend/` directory
3. Deploy the **frontend** from the `frontend/` directory
4. Set environment variables in the Railway dashboard
5. Initialise the schema: `psql ... -f backend/database/schema.sql`
6. Ingest PDFs: `python -m scripts.ingest_archives`

---

## 📄 License

MIT — Portfolio project. Feel free to fork and adapt for your own use!
