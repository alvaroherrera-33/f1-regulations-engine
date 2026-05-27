# Quick Start — Local Development

## Prerequisites

- Docker Desktop (includes Docker Compose)
- An [OpenRouter](https://openrouter.ai) API key

## Setup

**1. Clone the repository**

```bash
git clone https://github.com/alvaroherrera-33/f1-regulations-engine.git
cd f1-regulations-engine
```

**2. Configure environment variables**

```bash
cp .env.example .env
# Edit .env and set OPENROUTER_API_KEY=sk-or-...
```

**3. Start all services**

```bash
docker-compose up --build
```

This starts three containers: PostgreSQL + pgvector, the FastAPI backend, and the Next.js frontend.

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| Swagger docs | http://localhost:8000/docs |

Wait about 30 seconds on first run for the embedding model (`all-MiniLM-L6-v2`) to download.

## Ingest Regulation PDFs

The application ships without pre-loaded data. You need to ingest regulation PDFs before queries will return results.

**Option A — Ingest from the `archives/` directory (recommended)**

Place FIA regulation PDFs in `archives/` following the naming convention described in [docs/ARCHIVE_SETUP.md](ARCHIVE_SETUP.md), then run:

```bash
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/f1_regs \
  python -m scripts.ingest_archives
```

**Option B — Upload a single PDF via the API**

With the backend running:

```bash
curl -X POST http://localhost:8000/api/upload \
  -F "file=@/path/to/regulation.pdf" \
  -F "year=2026" \
  -F "section=Technical" \
  -F "issue=1"
```

## Verify the Setup

```bash
# Check indexed article count
curl http://localhost:8000/status

# Run a test query
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the minimum car weight in 2026?", "year": 2026}'
```

## Run Tests

```bash
cd backend
pytest tests/ -q
```

## Troubleshooting

**Backend exits immediately** — Check that `OPENROUTER_API_KEY` is set in `.env`.

**Queries return no results** — The database is empty. Run the ingestion step above.

**Port conflict** — Change the exposed ports in `docker-compose.yml` if 3000 or 8000 are already in use.
