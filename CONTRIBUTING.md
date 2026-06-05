# Contributing

Thanks for your interest! This is a personal portfolio project, but issues and pull
requests are welcome.

## Local setup

```bash
cp .env.example .env          # set POSTGRES_PASSWORD
make demo                     # build, start, and load the sample dataset
```

Everything runs in Docker (`db` + `backend` + `frontend`). Embeddings run locally with
a vendored ONNX model, so no GPU, HuggingFace download, or torch is needed. An LLM is
only required to generate chat answers — use OpenRouter (`OPENROUTER_API_KEY`) or a local
Ollama server (`make` + the `ollama` compose profile; see `.env.example`).

## Common commands

```bash
make help      # list all targets
make up        # start services (foreground)
make seed      # (re)load the demo dataset
make ingest    # ingest your own PDFs from archives/
make test      # run the backend test suite
make lint      # ruff
make clean     # stop and wipe the database volume
```

Without Docker you can run the backend directly:

```bash
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install pytest ruff
pytest tests/ -q
ruff check .
uvicorn app.main:app --reload
```

## Project layout

```
backend/
  app/            FastAPI app: routes, retrieval, LLM client, models, config
  ingestion/      PDF parsing, chunking, local embeddings, pipeline
  database/       schema.sql, migrations/, seed.sql
  models/         vendored ONNX embedding model (all-MiniLM-L6-v2)
  scripts/        ingest_archives, fia_scraper, compute_diffs, structural_audit
  tests/          pytest (no DB/LLM needed — heavy deps are stubbed in conftest)
frontend/         Next.js 14 (App Router, TypeScript, inline styles)
docs/             ARCHITECTURE, QUICKSTART, DEPLOYMENT, ARCHIVE_SETUP
```

See `docs/ARCHITECTURE.md` for how the pipeline fits together.

## Guidelines

- Keep changes small and focused; one concern per PR.
- Run `make test` and `make lint` before opening a PR (CI runs both).
- The hybrid retriever's RRF (`k=60`) is the core differentiator — discuss before changing.
- Don't add heavy runtime dependencies; the backend must fit common free tiers (~512MB).
- Ingestion runs locally/offline, never as part of serving requests.
- Be mindful of copyright: do **not** commit FIA regulation PDFs or their verbatim text.

## Tests

Unit tests stub the heavy ML/PDF/DB libraries (see `backend/tests/conftest.py`), so they
run fast without a database or model. Add tests for new deterministic logic
(parsing, validation, retrieval helpers).
