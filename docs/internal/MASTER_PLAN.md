# Master Plan — F1 Regulations Engine

> Creado: 2026-05-25  
> Estado de la DB: 16,182 artículos, 19,801 embeddings, 2023–2026  
> Este documento es la fuente de verdad sobre qué viene a continuación.

---

## Estado real del sistema (auditoría pre-plan)

### Completado y en producción

| Componente | Estado | Notas |
|-----------|--------|-------|
| Hybrid search (vector + FTS + RRF) | ✅ | k=60, threshold=0.75, top_k=8 |
| Agentic loop (max 3 pasos) | ✅ | SEARCH / ANSWER con historial |
| Citation filtering + cap | ✅ | Solo artículos citados en el texto, MAX=8, pruning de padres |
| Chunking de artículos largos | ✅ | >1500 chars → chunks de ~800 con overlap 200 |
| Feedback 👍/👎 + query_logs | ✅ | query_id en ChatResponse, endpoint /feedback |
| Stats page (/stats) | ✅ | Métricas de uso en vivo |
| FIA scraper (fia_scraper.py) | ✅ código | Implementado (356 líneas), NO conectado a cron automático |
| Sync route (/api/sync/*) | ✅ código | sync.py implementado, usa fia_sync_log table |
| Compare + AI explain | ✅ | Supabase Edge Function, proxy en Next.js |
| PDF parser fixes | ✅ | TOC filter, page noise, fill_missing_parents, full-text stream |
| Warmup endpoint | ✅ | /warmup, keep-alive manual |
| Validity annotations retriever | ✅ código | _annotate_validity() implementado |
| Eval framework (4 rounds) | ✅ | Mejor F1=82.1%, Precision=44.1% |
| Professionalization (Mayo 2026) | ✅ hoy | Multiidioma, landing, about, README, CI, docs/ |

### Previously flagged — all resolved

All items below were identified during the May 2026 audit and fixed in the same sprint.

| Item | Status |
|------|--------|
| `article_diffs` / `fia_sync_log` missing from schema | Fixed — both tables added, validity badges live |
| `compute_diffs.py` did not exist | Fixed — weekly Render cron computes diffs every Sunday |
| FIA scraper not connected to cron | Fixed — `fia-sync-daily` cron in `render.yaml` |
| No CI / `pyproject.toml` | Fixed — GitHub Actions: ruff + pytest + tsc all green |
| Financial recall 17–30% | Fixed — embedding enrichment + section-aware RRF boost |
---

## BLOQUE 0 — Reparar lo que está roto (antes de cualquier feature nueva)

> Prioridad URGENTE. Son cosas que dicen estar hechas pero no funcionan en producción.

### 0.1 — Añadir `article_diffs` y `fia_sync_log` al schema SQL

**Archivo:** `backend/database/schema.sql`

```sql
-- Cross-year article diff (computed by compute_diffs.py)
CREATE TABLE IF NOT EXISTS article_diffs (
    id SERIAL PRIMARY KEY,
    article_code VARCHAR(50) NOT NULL,
    section VARCHAR(50) NOT NULL,
    year_from INTEGER NOT NULL,
    year_to INTEGER NOT NULL,
    issue_from INTEGER NOT NULL,
    issue_to INTEGER NOT NULL,
    similarity FLOAT,
    change_type VARCHAR(20),  -- 'unchanged' | 'minor' | 'major' | 'added' | 'removed'
    computed_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(article_code, section, year_from, year_to)
);

-- FIA auto-sync audit log
CREATE TABLE IF NOT EXISTS fia_sync_log (
    id SERIAL PRIMARY KEY,
    checked_at TIMESTAMP DEFAULT NOW(),
    new_docs_found INTEGER DEFAULT 0,
    new_articles_indexed INTEGER DEFAULT 0,
    total_fia_docs INTEGER DEFAULT 0,
    error TEXT,
    status VARCHAR(20) DEFAULT 'ok'
);
```

**Acción:** Aplicar la migración en Supabase via SQL Editor. No requiere re-ingestión.  
**Tiempo:** 15 minutos.

---

### 0.2 — Script `compute_diffs.py`

**Archivo nuevo:** `backend/scripts/compute_diffs.py`

Lógica:
1. Para cada `(article_code, section)` que existe en múltiples años: obtener los embeddings ya almacenados en `article_embeddings`.
2. Calcular similitud coseno entre pares de años consecutivos (2023→2024, 2024→2025, 2025→2026).
3. Clasificar:
   - `> 0.98` → `unchanged`
   - `0.90–0.98` → `minor`
   - `0.70–0.90` → `major`
   - Existe en año A pero no en B → `removed`
   - Existe en año B pero no en A → `added`
4. Insertar en `article_diffs` con `ON CONFLICT DO UPDATE`.

**NO re-embebe nada** — usa los vectores que ya están en `article_embeddings`. Coste: 0 llamadas LLM.  
**Tiempo de implementación:** 3-4 horas.  
**Tiempo de ejecución:** ~2-5 min en la DB actual.

---

### 0.3 — Conectar FIA scraper a cron automático

**Opción A — Render Cron Job (recomendada, gratis):**
En `render.yaml`, añadir un cron service:
```yaml
- type: cron
  name: fia-sync
  env: python
  schedule: "0 7 * * *"    # cada día a las 7 UTC
  buildCommand: pip install -r requirements.txt
  startCommand: python -m scripts.fia_scraper --check-only
```

**Opción B — Endpoint manual en `/api/sync/check`:**
Ya existe. Conectarlo a un cron externo (Cron-Job.org, UptimeRobot) con un POST diario.

**Acción recomendada:** Añadir el cron a `render.yaml` + documentar en `docs/DEPLOYMENT.md`.  
**Tiempo:** 1 hora.

---

### 0.4 — Ruff config para que CI no falle

**Archivo nuevo:** `pyproject.toml` en la raíz de `backend/`

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "W", "I"]
ignore = [
    "E501",   # line too long — manejado por el formatter
    "F841",   # local variable assigned but never used
]

[tool.ruff.lint.per-file-ignores]
"scripts/*" = ["E402"]    # module level imports not at top
"eval/*" = ["E402"]
```

**Tiempo:** 20 minutos (configurar + correr `ruff check . --fix` para limpiar issues existentes).

---

## BLOQUE 1 — Calidad de respuestas (mayor impacto técnico)

### 1.1 — Mejorar Financial recall (de 17% a >50%)

**Problema raíz:** Los artículos Financial tienen códigos como `D12`, `E4.1`, `F-A1` y títulos muy cortos (`"COST CAP AMOUNT"`, `"RELATED PARTY TRANSACTIONS"`). El FTS no los encuentra bien y el embedding de un título corto es poco informativo.

**Fix A — Enriquecer los embeddings de artículos Financial:**

En `pipeline.py`, antes de generar el embedding, concatenar el texto a embeber con el título del padre:

```python
def _build_embedding_text(article: ParsedArticle, parent: ParsedArticle | None) -> str:
    parts = []
    if parent:
        parts.append(f"Section: {parent.title}.")
    parts.append(f"Article {article.article_code}: {article.title}.")
    parts.append(article.content[:1200])
    return " ".join(parts)
```

Requiere re-embeber solo los artículos Financial (≈450 artículos). Coste: 0 llamadas LLM (embedding local).

**Fix B — Boost Financial en prepare_search:**

Cuando la query detecta Financial pero el retriever tarda en encontrar artículos D/E prefix, ampliar el search_query con sinónimos:

```python
# En client.py prepare_search, añadir al prompt:
# For Financial queries: also include common code prefixes: 
# "D" = Cost Cap Regulations, "E" = Constructors' Championship
# Include these prefixes in search_query when relevant
```

**Fix C — FTS con similarity threshold más bajo para Financial:**

En `retriever.py`, detectar si `section == "Financial"` y bajar el threshold de similitud vectorial de 0.75 a 0.65 (solo para ese caso).

**Tiempo total:** 2-3 horas. Requiere re-ingestión parcial (solo Financial, ~10 min).

---

### 1.2 — Búsqueda jerárquica por niveles (Level weighting)

**Problema:** Queries amplias devuelven cláusulas Level 3 sin contexto. Queries específicas devuelven artículos padre Level 1 demasiado generales.

**Archivo:** `backend/app/retrieval/retriever.py` → `_merge_and_deduplicate()`

```python
# Añadir weight por nivel al score RRF
LEVEL_WEIGHTS = {1: 0.85, 2: 1.0, 3: 0.90}

def _merge_and_deduplicate(self, vector_results, fts_results, section_boost):
    # ... RRF existente ...
    for result in merged:
        result.rrf_score *= LEVEL_WEIGHTS.get(result.level, 1.0)
        if result.section == detected_section:
            result.rrf_score *= 1.2  # ya existe
```

Opcional: añadir parámetro `depth: "auto" | "broad" | "specific"` al ChatRequest y pasarlo al retriever para pesar los niveles dinámicamente.

**Tiempo:** 2 horas. Sin re-ingestión.

---

### 1.3 — Fix para queries que no generan citas

**Problema:** El LLM a veces responde sin usar el formato `[Article X.Y]`, devolviendo 0 citation cards aunque la respuesta sea correcta. Ocurre especialmente en `tech_04` del eval.

**Fix en `generate_reasoning_step()`:**

```python
# Si el LLM devuelve ANSWER pero el texto no contiene [Article X.Y]:
result = json.loads(data["choices"][0]["message"]["content"])
if result.get("action") == "ANSWER":
    answer_text = result.get("answer", "")
    if "[Article" not in answer_text and articles:
        # Añadir nota al prompt y re-intentar UNA vez
        # o extraer las primeras N citations por score como fallback
        result["_citation_fallback"] = True
```

En `_extract_citations()`, si `cited_codes_ordered` está vacío después del fallback pattern, devolver los top-3 artículos por score en vez de lista vacía.

**Tiempo:** 1 hora. Sin re-ingestión.

---

### 1.4 — Timeout en tech_02 (coordinate conventions query)

**Problema:** La query sobre "coordinate conventions" dispara búsquedas muy amplias que agotan el tiempo de respuesta de Render (30s timeout).

**Fix:** En el agentic loop, añadir un timeout hard de 25s que corte el loop y devuelva lo que tenga hasta ese momento, junto con un flag `"truncated": true` en la respuesta.

```python
# En chat.py, agentic loop:
import asyncio
try:
    step_result = await asyncio.wait_for(
        llm_client.generate_reasoning_step(query, all_articles, history),
        timeout=22.0
    )
except asyncio.TimeoutError:
    break  # devuelve lo acumulado
```

**Tiempo:** 1 hora.

---

## BLOQUE 2 — Features nuevas de producto

### 2.1 — FIA Sync Status badge en el frontend

**Objetivo:** Mostrar al usuario que los datos están actualizados. Diferenciador técnico visible.

**Backend:** El endpoint `GET /api/sync/status` ya existe.  
**Frontend:** En `frontend/app/stats/page.tsx` (o en el footer de la landing), añadir:

```
Last updated: 14 May 2026 · Check for updates
```

El badge cambia a `Checking...` mientras hace el request y `Up to date` o `1 new issue indexed` al terminar.

**Componente nuevo:** `frontend/components/SyncStatus.tsx`  
**Tiempo:** 2 horas.

---

### 2.2 — Permalink / Share para respuestas

**Objetivo:** El usuario puede compartir un link a una respuesta específica. Muy útil en entrevistas ("mira esta respuesta que dio el sistema").

**Arquitectura:**

Opción A (simple, sin DB extra): Codificar la query + filtros como query params URL-encoded:
```
/chat?q=What+is+the+minimum+weight&year=2026&section=Technical
```
Al cargar la página con `?q=`, ejecutar la query automáticamente.

**Archivos:** `frontend/app/chat/page.tsx` — leer `searchParams` al montar.  
**Tiempo:** 2 horas. Zero backend changes.

---

### 2.3 — Modo oscuro / claro (toggle)

**Objetivo:** La UI actual es solo dark mode. Añadir un toggle en el navbar para cambiar a light mode.

**Implementación:** CSS variables en `globals.css` para los colores base, y un `data-theme` en el `<html>`. El toggle alterna el atributo y guarda la preferencia en localStorage.

**Tiempo:** 3 horas.  
**Prioridad:** BAJA — el dark mode es la identidad visual del proyecto.

---

### 2.4 — API pública documentada (Swagger improvements)

**Objetivo:** La API en `/docs` ya existe con Swagger. Mejorarla para que sea presentable como API pública de portfolio.

**Cambios en los modelos Pydantic:**
- Añadir `example=` a todos los campos de `ChatRequest` y `ChatResponse`.
- Añadir `description=` a los campos.
- Tag descriptions en FastAPI (`app.openapi_tags`).

```python
class ChatRequest(BaseModel):
    query: str = Field(..., example="What is the minimum car weight in 2026?",
                       description="Natural language question about F1 regulations")
    year: Optional[int] = Field(None, example=2026, ge=2023, le=2030)
    section: Optional[str] = Field(None, example="Technical",
                                    description="Technical | Sporting | Financial")
```

**Tiempo:** 2 horas. No requiere lógica nueva.

---

### 2.5 — Rate limiting básico

**Objetivo:** Evitar que un usuario abuse del endpoint `/api/chat` (que cuesta dinero en OpenRouter).

**Implementación con slowapi (ya compatible con FastAPI):**

```python
# backend/app/main.py
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# En chat.py:
@router.post("/api/chat")
@limiter.limit("10/minute")
async def chat(request: Request, ...):
```

`slowapi` es ligero y usa Redis o memoria in-process. En Render free tier, usar in-memory (se resetea con cada deploy, suficiente para el caso de uso).

**Tiempo:** 1 hora. 1 dependencia nueva (slowapi).

---

### 2.6 — Suggested queries basadas en datos reales

**Objetivo:** Las 4 suggested questions del estado vacío del chat son estáticas. Podrían venir de las queries más populares o mejor valoradas en `query_logs`.

**Endpoint nuevo:** `GET /api/stats/top-queries` — devuelve las N queries con más feedback positivo.

**Tiempo:** 2 horas. Bajo impacto visual, medio impacto técnico.

---

### 2.7 — Mejora UX mobile

**Problema:** El chat en móvil no está optimizado. El textarea ocupa demasiado espacio y las citation cards son difíciles de leer en pantallas pequeñas.

**Fixes en ChatInterface.tsx y CitationCard.tsx:**
- En pantallas < 600px: citation cards en columna completa, texto más pequeño.
- Input area fija en bottom con `position: sticky`.
- Navbar con hamburger menu en mobile.

**Tiempo:** 3 horas.

---

## BLOQUE 3 — Infraestructura y mantenimiento

### 3.1 — Migración de schema controlada

**Problema:** El schema.sql actual es un DDL completo. No hay historial de migraciones. Si alguien aplica el schema dos veces, falla.

**Fix mínimo:** Convertir el schema.sql a migraciones incrementales con numeración:

```
backend/database/migrations/
  001_initial_schema.sql
  002_add_article_diffs.sql      ← la del bloque 0.1
  003_add_fia_sync_log.sql       ← la del bloque 0.1
```

No es necesario usar Alembic (demasiado overhead para este proyecto). Un script simple `apply_migrations.py` que trackea qué migraciones se han aplicado en una tabla `_migrations` es suficiente.

**Tiempo:** 2 horas.

---

### 3.2 — Tests unitarios mínimos para el parser y retriever

**Problema:** El CI corre `pytest` pero no hay `tests/` directory. Si alguien toca `pdf_parser.py` o `retriever.py`, no hay red de seguridad.

**Archivos nuevos:**

```
backend/tests/
  test_intent.py       ← ya tenemos los 32 casos del plan multiidioma
  test_parser.py       ← casos básicos de parseo de texto de regulación
  test_retriever.py    ← mock de la DB, verificar que RRF produce el orden correcto
```

**Tiempo:** 4 horas (tests básicos, no exhaustivos).

---

### 3.3 — Monitoring de costes OpenRouter

**Problema:** No hay visibilidad del gasto en OpenRouter. Si hay un spike de uso, no hay alertas.

**Fix:** En `_call_openrouter()`, loggear el campo `usage.total_tokens` de la respuesta. Agregar en `query_logs` una columna `tokens_used INTEGER`. En `/api/stats`, incluir `avg_tokens_per_query` y `estimated_cost_usd_30d`.

**Tiempo:** 2 horas.

---

## Orden de implementación recomendado

### Sprint inmediato (< 1 día, son bugs reales)
1. **0.1** — Añadir tablas faltantes al schema.sql + aplicar en Supabase
2. **0.4** — pyproject.toml con ruff config (para que el CI no falle en el primer push)

### Sprint corto (2-3 días, máximo impacto en calidad)
3. **0.2** — compute_diffs.py (desbloquea validity badges en prod)
4. **0.3** — FIA scraper cron en render.yaml
5. **1.3** — Fix queries sin citas (fácil, alto impacto percibido)
6. **1.4** — Timeout hard en agentic loop

### Sprint medio (1 semana, features de producto)
7. **1.1** — Financial recall improvement (re-embed + threshold)
8. **1.2** — Level weighting en RRF
9. **2.2** — Permalink / share de respuestas
10. **2.4** — Swagger documentation improvements
11. **2.5** — Rate limiting

### Sprint largo (2 semanas, pulido final)
12. **3.2** — Tests unitarios mínimos
13. **3.3** — Monitoring de costes
14. **2.1** — FIA Sync status badge en frontend
15. **3.1** — Migraciones controladas
16. **2.6** — Suggested queries dinámicas
17. **2.7** — Mobile UX

---

## Criterios de éxito por bloque

| Bloque | Métrica | Target |
|--------|---------|--------|
| Bloque 0 | validity badges visibles en prod | 100% artículos con diff calculado |
| Bloque 0 | FIA sync cron | Al menos 1 run automático exitoso |
| Bloque 1 | Financial recall en eval v5 | > 50% (desde 17-30%) |
| Bloque 1 | Citation rate | 0 respuestas con 0 citas cuando hay artículos |
| Bloque 2 | Share URL | Link funcional con query pre-cargada |
| Bloque 2 | Rate limit | 10 req/min por IP sin errores en uso normal |
| Bloque 3 | CI verde | `ruff` + `pytest` pasan en primer push a main |
| Bloque 3 | Test coverage parser | >80% líneas del parser cubiertas |

---

## Lo que NO se va a implementar (y por qué)

| Feature | Razón |
|---------|-------|
| Autenticación de usuarios | Overhead enorme, no aporta al portfolio técnico |
| Base de datos de usuarios / historial persistente | Misma razón; GDPR innecesario |
| Búsqueda en lenguaje natural de múltiples documentos simultáneos | Scope creep; el agentic loop ya maneja esto |
| Fine-tuning del modelo de embeddings | No cabe en free tier; all-MiniLM es suficientemente bueno |
| Migración a Tailwind | Rompe el estilo existente sin beneficio claro |
| App móvil nativa | Fuera de scope para este proyecto |
| GraphQL API | REST es suficiente y más familiar para recruiters |
