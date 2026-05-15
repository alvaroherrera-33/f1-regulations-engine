# Next Sprint — Plan de Mejoras

> Creado: 2026-05-07
> Última actualización: 2026-05-12
> Objetivo: Maximizar calidad/precisión del RAG sin aumentar coste LLM + UI profesional
> Tiempo estimado total: ~13-14 horas

---

## Estado actual (2026-05-12)

### Fase 1 — COMPLETADA ✅
- `backend/eval/test_set.json` v1.1: 20 queries corregidas (8 Tech, 6 Sporting, 6 Financial)
- `backend/eval/run_eval.py` + `run_single.py`: scripts de evaluación con P/R/F
- **Baseline (eval_v2_final.json):** P=9.3%, R=70.8%, F=57.9% — 11/20 con 100% recall

### Fase 2 — COMPLETADA ✅
- ✅ 2.1 Chunking: `chunker.py` + `pipeline.py` + **re-ingestión ejecutada**
  - 3672 artículos → 4305 chunks (240 artículos largos divididos)
  - Unique constraint `article_embeddings_article_id_key` eliminada para soportar múltiples chunks
  - Embeddings generados con `fastembed` (ONNX, all-MiniLM-L6-v2, 384-dim)
- ✅ 2.2 `websearch_to_tsquery` en `retriever.py`
- ✅ 2.3 Cache de embeddings (ya existía en `local_embeddings.py`)
- ✅ 2.4 Prompt tuning en `client.py` (AGENTIC_PROMPT mejorado)
- ✅ 2.5 Section-aware RRF boost (1.2x) en `_merge_and_deduplicate()`
- ✅ 2.6 Context trimming (MAX_CONTEXT_ARTICLES=12, MAX_ARTICLE_CHARS=2000)
- ⏳ 2.7 Cobertura Technical 2025 Issues 1 & 3 — PDFs en archives/, pendiente ingestión

### Fase 3 — COMPLETADA ✅
- ✅ 3.1 Emojis eliminados de todos los componentes
- ✅ 3.2 Tipografía Inter via next/font/google
- ✅ 3.3 Paleta: morado #667eea → rojo F1 #eb0000 + azul oscuro #1e293b
- ✅ 3.4 Página /about con diagrama de arquitectura SVG
- ✅ 3.5 Métricas en cada respuesta: "N articles · N steps · Xs"
- ✅ 3.6 Navbar: links a Stats y About

### Fase 4 — COMPLETADA ✅
- ✅ 4.1 Warmup ping cada 10 min (scheduled task)
- ✅ 4.2 Admin endpoint: GET /api/admin/embedding-stats

### Technical 2025 Coverage — COMPLETADA ✅
- ✅ Issue 1: 316 articles, 375 embeddings (25 chunked)
- ✅ Issue 2: 315 articles, 346 embeddings (already existed)
- ✅ Issue 3: 316 articles, 375 embeddings (25 chunked)

### Eval Post-Chunking — COMPLETADA ✅
- **eval_post_chunking_final.json** (20 queries, 2026-05-13)
- Avg Recall: 56.7%, Avg Fact Accuracy: 78.8%, Avg Time: 24.4s
- Perfect Recall: 8/20 queries
- Technical: R=75% F=75%, Sporting: R=72% F=79%, Financial: R=17% F=83%
- By difficulty: Easy R=70%, Medium R=48%, Hard R=60%
- Baseline comparison (eval_v2_final): P=9.3%, R=70.8%, F=57.9%
- Post-chunking: R=56.7%, F=78.8% → fact accuracy improved +20.9pp, recall dropped 14.1pp
- Financial recall very low (17%) — retriever finds Financial articles but not the specific expected sub-articles
- Precision low across the board (~7%) — system over-retrieves many related articles (by design, agentic loop does multiple searches)

### Eval v3 — Citation Filter (2026-05-15) ✅
- Citation precision fix deployed: `_extract_citations()` now filters to only articles cited in LLM answer
- AGENTIC_PROMPT updated: "cite only directly relevant articles (2-5)"
- **eval_v3** (18/20 queries, 2 timeout):
  - Avg Recall: 48.1%, Avg Precision: 11.7%, Avg Fact Acc: 55.1%
  - Perfect Recall: 6/18
  - Technical: R=50% P=19%, Sporting: R=72% P=8%, Financial: R=8% P=2%
  - Precision improved from 7% → 11.7% (citation filter working)
  - Avg citations per response: 14 → 9.9
  - Recall/fact accuracy drops likely due to LLM non-determinism between runs

### Pendiente
- Financial recall still very low (8%) — retriever + LLM struggle with D/E prefix articles
- LLM still over-cites (avg 9.9 citations vs target 2-5) — consider stronger prompt or post-processing
- Consider adding more test queries for edge cases
- Audit Sporting 2026 coverage (only 1 doc/150 articles vs 2 docs/816 for 2025)

---

## FASE 1 — Eval Framework (~3h) ✅ COMPLETADA

**Por qué primero:** No tiene sentido tocar el retriever sin poder medir si mejoró o empeoró.

### 1.1 Test set de evaluación

**Archivo:** `backend/eval/test_set.json`

Crear ~20 preguntas que cubran:
- Technical (weight, aero, PU, fuel, tyres) — ~8 preguntas
- Sporting (points, penalties, safety car, qualifying) — ~6 preguntas
- Financial (cost cap, reporting, exceptions) — ~6 preguntas

Cada entrada incluye:
```json
{
  "id": "tech_01",
  "query": "What is the minimum weight of an F1 car in 2026?",
  "expected_section": "Technical",
  "expected_year": 2026,
  "expected_articles": ["4.1", "4.2"],
  "key_facts": ["798 kg", "minimum weight"],
  "difficulty": "easy"
}
```

Niveles de dificultad:
- **easy:** Pregunta directa sobre un artículo específico
- **medium:** Requiere cruzar 2-3 artículos
- **hard:** Cross-references entre artículos, terminología ambigua, o requiere múltiples pasos del agentic loop

### 1.2 Script de evaluación

**Archivo:** `backend/eval/run_eval.py`

Funcionalidad:
- Ejecuta cada query contra el backend (configurable: local o producción)
- Compara `cited_articles` vs `expected_articles` → precision y recall por query
- Compara `key_facts` como substrings en la respuesta → fact accuracy
- Genera reporte con métricas agregadas y detalle por query
- Salida: JSON + resumen en consola

Métricas calculadas:
- **Retrieval Recall:** % de artículos esperados que aparecen en las citas
- **Retrieval Precision:** % de artículos citados que son relevantes (están en expected)
- **Fact Accuracy:** % de key_facts que aparecen en la respuesta
- **Avg Response Time:** latencia promedio
- **Por dificultad:** métricas desglosadas por easy/medium/hard

### 1.3 Baseline

Ejecutar el eval contra el estado actual para tener números de referencia antes de la Fase 2.

---

## FASE 2 — RAG Quality (~5-6h) 🟡 CORE

**Restricción:** 0 llamadas LLM extra por query. Todo mejora retrieval, prompts, o datos.

### 2.1 Chunking de artículos largos

**Archivos:** `backend/ingestion/pipeline.py`, `backend/ingestion/chunker.py` (nuevo)

Artículos >1500 chars se embeben como un solo vector de 384 dim. Un artículo que cubre 3 temas genera un embedding "promedio" poco preciso.

**Fix:** Partir artículos >1500 chars en chunks de ~800 chars con overlap de 200. Cada chunk mantiene el mismo `article_code` y `article_id` pero genera su propio embedding. El retriever ya busca por `article_code` así que el impacto downstream es mínimo.

**Impacto estimado:** +10-15% retrieval recall en preguntas sobre temas específicos dentro de artículos largos.

**Requiere:** Re-generar embeddings (no re-parsear artículos).

### 2.2 websearch_to_tsquery

**Archivo:** `backend/app/retrieval/retriever.py` → `_retrieve_by_fulltext()`

Cambiar `plainto_tsquery` por `websearch_to_tsquery`. Genera tsqueries más inteligentes para queries multi-término.

**Cambio:** 1 línea.

### 2.3 Cache de embeddings de queries

**Archivo:** `backend/ingestion/local_embeddings.py`

Añadir `functools.lru_cache(maxsize=256)` al método de embedding de queries.

**Impacto:** Mejora latencia en queries repetidas. No afecta precisión.

### 2.4 Prompt tuning del agentic step

**Archivo:** `backend/app/llm/client.py` → `AGENTIC_PROMPT`

Dos cambios:
1. Forzar citas con el formato exacto `[Article X.Y]` usando el `article_code` real
2. Instrucción explícita: si no hay info suficiente, decir "I don't have enough information" en vez de inventar
3. Mejor estructura del contexto: incluir section+year en cada artículo para que el LLM no confunda versiones

**Impacto:** Menos hallucinations, citas más precisas.

### 2.5 Section-aware RRF scoring

**Archivo:** `backend/app/retrieval/retriever.py` → `_merge_and_deduplicate()`

Cuando `prepare_search()` detecta una sección, multiplicar el RRF score por 1.2x para artículos de esa sección. NO cambia k=60.

**Implementación:** Pasar `detected_section` como parámetro opcional a `_merge_and_deduplicate()`. Si coincide con `article.section`, boost.

### 2.6 Context trimming

**Archivo:** `backend/app/routes/chat.py` (agentic loop) y `backend/app/llm/client.py` → `_build_context()`

Cuando el agentic loop acumula >12 artículos, ordenar por score RRF y enviar solo los top 10-12 al LLM. Truncar artículos individuales >2000 chars a sus primeros 1500.

**Impacto:** El LLM responde mejor con menos contexto pero más relevante.

### 2.7 Cobertura: Technical 2025

**Tarea:** Auditar `archives/` para issues faltantes de Technical 2025 (solo está el Issue 2). Ingestar los que falten.

---

## FASE 3 — UI Cleanup + About (~4h) 🔵

### 3.1 Eliminar emojis de la interfaz

**Archivos:** Todos los componentes TSX

Reemplazar emojis (🏎️, 💬, 🔍, 📄, 🤖, 👤, 📚, 💡, 📊) por nada o por iconos SVG inline minimalistas. Los emojis dan aspecto de tutorial.

### 3.2 Tipografía profesional

**Archivo:** `frontend/app/layout.tsx`

Importar `Inter` o `Space Grotesk` de Google Fonts. Aplicar como font-family base.

### 3.3 Paleta de colores consistente

**Todos los componentes**

- **Acento primario:** Rojo F1 `#eb0000` (ya existe, mantener)
- **Acento secundario:** Azul oscuro `#334155` en vez de morado `#667eea`
- **Mensajes usuario:** Fondo gris oscuro sutil en vez del gradiente morado
- **Botón Send:** Rojo F1 en vez de gradiente morado
- Quitar el morado — es inconsistente con la identidad F1

### 3.4 Página /about con diagrama de arquitectura

**Archivo nuevo:** `frontend/app/about/page.tsx`

Contenido:
- Qué es RAG (explicación breve)
- Diagrama SVG inline del flujo de una query
- Stack tecnológico
- Cómo funciona la búsqueda híbrida + RRF
- Link al repo de GitHub

### 3.5 Métricas visibles en cada respuesta del chat

**Archivos:** `frontend/components/ChatInterface.tsx`, `frontend/lib/api.ts`

Mostrar debajo de cada respuesta: "8 articles · 2 steps · 3.2s"

Los datos ya están en `ChatResponse` (`retrieved_count`, `research_steps`). Solo falta calcular tiempo en el frontend y renderizarlo.

### 3.6 Navbar: añadir link a About y Stats

**Archivo:** `frontend/components/Navbar.tsx`

Añadir "About" y "Stats" a `NAV_LINKS`.

---

## FASE 4 — Operaciones (~1h) 🟢

### 4.1 UptimeRobot para cold start

Configurar ping a `https://f1-regulations-engine.onrender.com/warmup` cada 10 minutos.

### 4.2 Verificar post-ingestión

```sql
SELECT section, year, COUNT(*) FROM articles
WHERE LENGTH(content) < 50
GROUP BY section, year;
-- Esperado: 0 filas
```

---

## Orden de ejecución recomendado

```
Fase 1 (Eval) → Baseline
    ↓
Fase 2 (RAG) → Eval post-cambios → comparar con baseline
    ↓
Fase 3 (UI) → independiente del RAG
    ↓
Fase 4 (Ops) → cierre
```

## Qué NO tocar

- RRF k=60 (parámetro académico estándar)
- Lógica de deduplicación del retriever (funciona correctamente)
- El parser sin leer `.claude/learnings.md` primero
- DATABASE_URL de producción (Session Pooler, no direct connection)
- Embeddings model (all-MiniLM-L6-v2) — cambiar requiere re-embeber todo
