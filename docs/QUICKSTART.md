# Quick Start — Local Development

## Prerequisites

- Docker (with Docker Compose). `make` is optional but convenient.
- An LLM endpoint **only for generating chat answers**: an
  [OpenRouter](https://openrouter.ai) API key, or a local [Ollama](https://ollama.com)
  server. Retrieval, the demo, and the Compare view work without one — embeddings run
  locally with a vendored ONNX model (no API key, GPU, or download).

## 1. Clone and configure

```bash
git clone https://github.com/alvaroherrera-33/f1-regulations-engine.git
cd f1-regulations-engine
cp .env.example .env
# Set POSTGRES_PASSWORD (any value). For chat answers, also set OPENROUTER_API_KEY.
```

## 2. Run the demo (fastest — no PDFs needed)

```bash
make demo        # builds, starts db + backend + frontend, loads a sample dataset
```

`make demo` seeds ~30 illustrative sample articles **with real embeddings**, so search and
Compare work immediately. (No `make`? Run `docker compose up -d --build`, then
`docker compose exec -T db psql -U postgres -d f1_regs < backend/database/seed.sql`.)

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| Swagger docs | http://localhost:8000/docs |

## 3. (Optional) Run fully local & free with Ollama

No OpenRouter key required:

```bash
docker compose --profile ollama up -d
docker compose exec ollama ollama pull llama3.1
```

Then in `.env`: `OPENROUTER_API_KEY=` (blank), `LLM_MODEL=llama3.1`,
`LLM_BASE_URL=http://ollama:11434/v1`, and restart the backend.

## Ingest your own regulation PDFs

The demo dataset is just a sample. To index real regulations, place FIA PDFs in
`archives/` (see [ARCHIVE_SETUP.md](ARCHIVE_SETUP.md)) — they are **not** distributed with
this repo — then:

```bash
make ingest        # or: docker compose exec backend python -m scripts.ingest_archives
```

You can also upload a single PDF via the API (requires `ADMIN_API_KEY`):

```bash
curl -X POST http://localhost:8000/api/upload \
  -H "X-Admin-Key: $ADMIN_API_KEY" \
  -F "file=@/path/to/regulation.pdf" -F "year=2026" -F "section=Technical" -F "issue=1"
```

## Verify

```bash
curl http://localhost:8000/status          # document/article/embedding counts
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the minimum car weight?"}'
```

## Tests

```bash
make test          # or, without Docker:
cd backend && pip install -r requirements.txt pytest ruff && pytest tests/ -q
```

## Troubleshooting

- **`POSTGRES_PASSWORD is required`** — set it in `.env` (compose needs it).
- **Chat answers fail but search works** — the LLM endpoint isn't configured. Set
  `OPENROUTER_API_KEY`, or use the Ollama setup above. Retrieval/Compare don't need it.
- **Queries return no results after ingesting** — make sure your PDFs are under `archives/`
  with the expected naming (see ARCHIVE_SETUP.md), then re-run `make ingest`.
- **Port conflict** — change the published ports in `docker-compose.yml` (3000 / 8000).
