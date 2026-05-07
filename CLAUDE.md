# F1 Regulations RAG Engine — Guía para Agentes Claude

> Este archivo es la fuente de verdad para cualquier agente Claude que trabaje en este proyecto.
> Léelo COMPLETO antes de hacer cualquier cambio.
> Última actualización: 2026-05-07

## Qué es este proyecto

Un sistema RAG (Retrieval-Augmented Generation) que permite consultar las regulaciones oficiales de la FIA de Formula 1 mediante lenguaje natural. El usuario pregunta algo como "¿Cuál es el peso mínimo del coche en 2026?" y el sistema busca en los PDFs reglamentarios indexados, devuelve la respuesta con citas exactas de artículos.

**Propósito:** Proyecto personal de portfolio para demostrar competencia en AI/ML engineering a recruiters y empresas de F1.

**Propietario:** Álvaro (aherarj@gmail.com)

## Stack técnico

| Capa | Tecnología | Notas |
|------|-----------|-------|
| Backend | FastAPI (Python 3.11) | Async, uvicorn |
| Frontend | Next.js 14 (TypeScript) | App router, inline styles |
| Base de datos | PostgreSQL + pgvector (Supabase) | Vectores 384-dim, búsqueda híbrida |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 | LOCAL en el backend, no API externa |
| LLM | OpenRouter API | Modelo configurable via `LLM_MODEL` |
| Deploy backend | Render (free tier) | `f1-regulations-engine.onrender.com` |
| Deploy frontend | Vercel | `f1-regulations-engine-project.vercel.app` |
| Deploy DB | Supabase | Proyecto: `nmftfbboxssonnvbjzef` |
| Dev local | Docker Compose | 3 servicios: db, backend, frontend |

## URLs de producción

- **Frontend:** https://f1-regulations-engine-project.vercel.app
- **Backend API:** https://f1-regulations-engine.onrender.com
- **Swagger docs:** https://f1-regulations-engine.onrender.com/docs
- **Supabase:** https://supabase.com/dashboard/project/nmftfbboxssonnvbjzef

## Arquitectura clave (NO cambiar sin razón)

### Flujo de una query al chat (`POST /api/chat`)

```
1. detect_intent() → REGULATIONS o CONVERSATIONAL  [LOCAL, sin LLM]
2. Si REGULATIONS:
   a. prepare_search() → UNA sola llamada LLM: extrae año+sección+query reescrita
   b. retrieve_articles() → búsqueda híbrida inicial
   c. Loop agentic (max 3 pasos):
      - retrieve_articles(top_k=8) → búsqueda híbrida (vector + FTS + RRF)
      - generate_reasoning_step() → LLM decide: SEARCH más o ANSWER
   d. Devuelve respuesta + citas + pasos + query_id (para feedback)
3. Si CONVERSATIONAL: respuesta directa sin DB
4. Toda query se registra en query_logs (para monitoring y feedback)
```

**IMPORTANTE:** `detect_intent()` es local (regex/keywords, 0 llamadas LLM). `prepare_search()` unifica el antiguo `extract_filters` + `rewrite_query` en 1 sola llamada.

### Búsqueda híbrida (retriever.py)

- Vector similarity (pgvector cosine distance, **threshold 0.75** — bajado desde 0.85 para mejor recall)
- Full-Text Search (PostgreSQL tsvector/tsquery)
- Merge con Reciprocal Rank Fusion (RRF, k=60) — **NO cambiar este parámetro**
- Deduplicación estricta: (article_code, section, year) → solo el issue más alto
- Enriquecimiento con artículos padre del mismo issue
- **top_k=8 por paso del agentic loop** (antes era 5)

### Ingestion pipeline

```
PDF → PyMuPDF → texto completo (TODAS las páginas juntas, no por página)
    → filtrar cabeceras/pies de página
    → regex extract articles → 3 niveles (Article/Sub/Clause)
    → filtrar entradas de TOC y contenido trivial
    → crear stubs para artículos padre faltantes
    → sentence-transformers embed → PostgreSQL (articles + article_embeddings)
```

**IMPORTANTE:** El parser procesa el documento completo como un stream continuo (no página a página). Esto es crítico para artículos que cruzan saltos de página.

### Query logging y feedback

- Toda query se inserta en `query_logs` con intent, año, sección, respuesta, tiempo, artículos citados
- `ChatResponse` devuelve `query_id` → el frontend usa ese ID para enviar feedback 👍/👎
- Endpoint: `POST /api/chat/feedback` con `{ query_id, was_helpful }`
- Métricas agregadas: `GET /api/stats`

## Estructura de archivos importante

```
backend/
  app/
    main.py              ← FastAPI app, CORS, health, status, /warmup, routers
    config.py            ← Settings (pydantic-settings, lee .env)
    database.py          ← asyncpg engine + async session
    models.py            ← Pydantic models + SQLAlchemy ORM models (AMBOS aquí)
                           Incluye: ChatResponse (con query_id), FeedbackRequest, StatsResponse
    llm/
      client.py          ← LLMClient: detect_intent (local), prepare_search, generate_reasoning_step
      intent.py          ← Clasificador local CONVERSATIONAL/REGULATIONS (regex, 0 LLM calls)
    retrieval/retriever.py ← HybridRetriever: vector + FTS + RRF + parent enrichment
    routes/
      chat.py            ← POST /api/chat, POST /api/chat/feedback, GET /api/stats
      articles.py        ← GET /api/articles
      upload.py          ← POST /api/upload
  ingestion/
    pdf_parser.py        ← Extrae artículos de PDFs (ver sección de bugs conocidos)
    local_embeddings.py  ← Genera embeddings con all-MiniLM-L6-v2
    pipeline.py          ← Orquesta: parse → embed → store
  database/schema.sql    ← DDL: documents, articles, article_embeddings, query_logs
  scripts/ingest_archives.py ← Ingestión masiva de PDFs de archives/

frontend/
  app/
    page.tsx             ← Landing page
    chat/page.tsx        ← Chat con sidebar de filtros + enlace a /stats
    upload/page.tsx      ← Formulario de upload
    stats/page.tsx       ← Dashboard de métricas de uso y calidad
  components/
    ChatInterface.tsx    ← Chat principal + botones feedback 👍/👎
    CitationCard.tsx     ← Tarjeta de cita
    FilterControls.tsx   ← Controles de año/sección/issue
    ViewControls.tsx     ← Densidad, markdown, font size
  lib/api.ts             ← Cliente API: sendChatQuery, submitFeedback, getStats, getStatus

archives/                ← 98 PDFs de regulaciones FIA 2023-2026
docker-compose.yml       ← Dev local: db + backend + frontend
QUALITY_PLAN.md          ← Plan de mejora de calidad con todos los issues detectados
```

## Variables de entorno requeridas

```bash
# Development (docker-compose)
OPENROUTER_API_KEY=sk-or-...
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/f1_regs
LLM_MODEL=openai/gpt-oss-120b
ALLOWED_ORIGINS=http://localhost:3000

# Producción (Render)
DATABASE_URL=postgresql+asyncpg://postgres.nmftfbboxssonnvbjzef:<PASSWORD>@aws-1-eu-central-1.pooler.supabase.com:5432/postgres?ssl=require
# IMPORTANTE: usar Session Pooler de Supabase (no el direct connection)
# Render free tier es IPv4-only; el Session Pooler de Supabase tiene IPv4
```

## Cómo ejecutar en local

```bash
# Necesitas Docker + Docker Compose
docker-compose up --build

# Ingestar los PDFs (primera vez o después de cambios al parser)
cd backend
python -m venv venv && venv/Scripts/activate  # Windows
pip install -r requirements.txt
DATABASE_URL=postgresql+asyncpg://... python -m scripts.ingest_archives

# Frontend: http://localhost:3000
# Backend API: http://localhost:8000/docs
```

## Endpoints disponibles

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/health` | GET | Status de DB |
| `/status` | GET | Cuenta docs, articles, embeddings |
| `/warmup` | GET | Pre-carga modelo embeddings (para cron keep-alive) |
| `/` | GET | Info básica |
| `/docs` | GET | Swagger UI |
| `/api/chat` | POST | Endpoint principal RAG — devuelve `query_id` |
| `/api/chat/feedback` | POST | Feedback 👍/👎 por `query_id` |
| `/api/stats` | GET | Métricas agregadas de query_logs |
| `/api/articles` | GET | Lista artículos con filtros |
| `/api/articles/{code}` | GET | Artículo por código |
| `/api/upload` | POST | Upload + ingestion de PDF |

## Convenciones de código

- Backend: Python async, type hints, docstrings
- Frontend: TypeScript, inline styles (objeto `styles` al final del archivo), NO Tailwind
- Nombres de componentes: PascalCase
- Rutas API: /api/prefix (chat, upload, articles)
- Modelos Pydantic Y SQLAlchemy conviven en models.py

## Reglas para agentes

1. **NO cambiar la arquitectura de búsqueda híbrida (RRF)** sin discutirlo — es el diferenciador técnico del proyecto.
2. **NO añadir dependencias pesadas** — el proyecto debe caber en free tiers (~512MB RAM).
3. **Minimizar llamadas a OpenRouter** — cada call cuesta dinero. Preferir lógica local cuando sea posible.
4. **Mantener el repo limpio** — no dejar archivos de debug, test temporales, o logs en la raíz.
5. **Todo cambio debe ser testeable con `docker-compose up`** — no romper el flujo de desarrollo local.
6. **El frontend usa inline styles** — no migrar a Tailwind/CSS modules sin razón.
7. **Consultar PLAN.md y QUALITY_PLAN.md** antes de implementar features nuevas.
8. **NO cambiar el parser sin leer la sección de bugs en learnings.md** — es frágil y hay muchos edge cases documentados.
9. **La DB de producción está en Supabase Session Pooler** — no usar el direct connection URL (es IPv6, Render es IPv4-only).

## Estado actual del proyecto

Consultar `PLAN.md` para el plan de features, `QUALITY_PLAN.md` para el plan de mejora de calidad, y `.claude/learnings.md` para decisiones técnicas y problemas conocidos.
