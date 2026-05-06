# F1 Regulations RAG Engine — Guía para Agentes Claude

> Este archivo es la fuente de verdad para cualquier agente Claude que trabaje en este proyecto.
> Léelo COMPLETO antes de hacer cualquier cambio.

## Qué es este proyecto

Un sistema RAG (Retrieval-Augmented Generation) que permite consultar las regulaciones oficiales de la FIA de Formula 1 mediante lenguaje natural. El usuario pregunta algo como "¿Cuál es el peso mínimo del coche en 2026?" y el sistema busca en los PDFs reglamentarios indexados, devuelve la respuesta con citas exactas de artículos.

**Propósito:** Proyecto personal de portfolio para demostrar competencia en AI/ML engineering a recruiters y empresas de F1.

**Propietario:** Álvaro (aherarj@gmail.com)

## Stack técnico

| Capa | Tecnología | Notas |
|------|-----------|-------|
| Backend | FastAPI (Python 3.11) | Async, uvicorn |
| Frontend | Next.js 14 (TypeScript) | App router, inline styles |
| Base de datos | PostgreSQL + pgvector | Vectores 384-dim, búsqueda híbrida |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 | LOCAL, no API externa |
| LLM | OpenRouter API | Modelo configurable via `LLM_MODEL` |
| Containerización | Docker Compose | 3 servicios: db, backend, frontend |

## Arquitectura clave (NO cambiar sin razón)

### Flujo de una query al chat (`POST /api/chat`)

```
1. detect_intent() → REGULATIONS o CONVERSATIONAL
2. Si REGULATIONS:
   a. extract_query_filters() → año, sección auto-detectados
   b. rewrite_query() → query optimizada para búsqueda
   c. Loop agentic (max 3 pasos):
      - retrieve_articles() → búsqueda híbrida (vector + FTS + RRF)
      - generate_reasoning_step() → LLM decide: SEARCH más o ANSWER
   d. Devuelve respuesta + citas + pasos de investigación
3. Si CONVERSATIONAL: respuesta directa sin DB
```

### Búsqueda híbrida (retriever.py)

- Vector similarity (pgvector cosine distance, threshold 0.85)
- Full-Text Search (PostgreSQL tsvector/tsquery)
- Merge con Reciprocal Rank Fusion (RRF, k=60)
- Deduplicación estricta: (article_code, section, year) → solo el issue más alto
- Enriquecimiento con artículos padre del mismo issue

### Ingestion pipeline

```
PDF → PyMuPDF → regex extract articles → 3 niveles (Article/Sub/Clause)
    → sentence-transformers embed → PostgreSQL (articles + article_embeddings)
```

## Estructura de archivos importante

```
backend/
  app/
    main.py              ← FastAPI app, CORS, health, status, routers
    config.py            ← Settings (pydantic-settings, lee .env)
    database.py          ← asyncpg engine + async session
    models.py            ← Pydantic models + SQLAlchemy ORM models (AMBOS aquí)
    llm/client.py        ← LLMClient: 4 métodos (intent, filters, rewrite, reasoning)
    retrieval/retriever.py ← HybridRetriever: vector + FTS + RRF + parent enrichment
    routes/
      chat.py            ← POST /api/chat (endpoint principal)
      articles.py        ← GET /api/articles
      upload.py          ← POST /api/upload
  ingestion/
    pdf_parser.py        ← Extrae artículos de PDFs
    local_embeddings.py  ← Genera embeddings con all-MiniLM-L6-v2
    pipeline.py          ← Orquesta: parse → embed → store
  database/schema.sql    ← DDL: documents, articles, article_embeddings
  scripts/ingest_archives.py ← Ingestión masiva de PDFs de archives/

frontend/
  app/
    page.tsx             ← Landing page
    chat/page.tsx        ← Chat con sidebar de filtros
    upload/page.tsx      ← Formulario de upload
  components/
    ChatInterface.tsx    ← Componente principal del chat
    CitationCard.tsx     ← Tarjeta de cita
    FilterControls.tsx   ← Controles de año/sección/issue
    ViewControls.tsx     ← Densidad, markdown, font size
  lib/api.ts             ← Cliente API (fetch al backend)

archives/                ← 98 PDFs de regulaciones FIA 2023-2026
docker-compose.yml       ← Dev local: db + backend + frontend
```

## Variables de entorno requeridas

```bash
OPENROUTER_API_KEY=sk-or-...  # Obligatoria
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/f1_regs
LLM_MODEL=openai/gpt-oss-120b  # Configurable
ALLOWED_ORIGINS=http://localhost:3000
```

## Cómo ejecutar en local

```bash
# Necesitas Docker + Docker Compose
docker-compose up --build

# Ingestar los PDFs (primera vez)
docker-compose exec backend python -m scripts.ingest_archives

# Frontend: http://localhost:3000
# Backend API: http://localhost:8000/docs
```

## Convenciones de código

- Backend: Python async, type hints, docstrings
- Frontend: TypeScript, inline styles (objeto `styles` al final del archivo), NO Tailwind
- Nombres de componentes: PascalCase
- Rutas API: /api/prefix (chat, upload, articles)
- Modelos Pydantic Y SQLAlchemy conviven en models.py

## Estado actual del proyecto

Consultar `PLAN.md` para el plan completo y `.claude/learnings.md` para decisiones técnicas y problemas conocidos.

## Reglas para agentes

1. **NO cambiar la arquitectura de búsqueda híbrida (RRF)** sin discutirlo — es el diferenciador técnico del proyecto.
2. **NO añadir dependencias pesadas** — el proyecto debe caber en free tiers (~512MB RAM).
3. **Minimizar llamadas a OpenRouter** — cada call cuesta dinero. Preferir lógica local cuando sea posible.
4. **Mantener el repo limpio** — no dejar archivos de debug, test temporales, o logs en la raíz.
5. **Todo cambio debe ser testeable con `docker-compose up`** — no romper el flujo de desarrollo local.
6. **El frontend usa inline styles** — no migrar a Tailwind/CSS modules sin razón.
7. **Consultar PLAN.md** antes de implementar features nuevas para seguir el orden de prioridad.
