# Learnings y Decisiones Técnicas — F1 Regulations Engine

> Registro de decisiones de arquitectura, problemas detectados, y conocimiento acumulado.
> Última actualización: 2026-05-07

---

## Decisiones de arquitectura tomadas

### 1. Embeddings locales vs API
- **Decisión:** Usar `sentence-transformers/all-MiniLM-L6-v2` ejecutando localmente en el backend.
- **Por qué:** Elimina dependencia de API externa para embeddings, reduce latencia, coste $0.
- **Trade-off:** Consume ~400-500MB RAM. Esto limita las opciones de free tier.
- **Si el free tier no aguanta:** Alternativa → usar OpenRouter embeddings API (`openai/text-embedding-3-small`). Requiere cambiar `backend/ingestion/local_embeddings.py` y `backend/app/retrieval/retriever.py`. Ya existe un archivo `backend/ingestion/embeddings.py` con una implementación de OpenRouter embeddings (no activa).

### 2. Búsqueda híbrida con RRF
- **Decisión:** Combinar vector search (pgvector) + Full-Text Search (PostgreSQL) con Reciprocal Rank Fusion.
- **Por qué:** Mejor recall que solo vector search. FTS captura coincidencias exactas de términos técnicos que los embeddings pueden perder.
- **Parámetro RRF k=60:** Es el estándar académico. **No tocar sin benchmarks.**
- **SIMILARITY_THRESHOLD = 0.75:** Cosine distance (0=idéntico, 2=opuesto). Bajado de 0.85 a 0.75 para mejor recall. 0.85 era demasiado estricto para preguntas formuladas de forma diferente al texto de las regulaciones.
- **top_k=8 por paso:** Subido de 5 a 8. Con top_k=5 se perdían artículos relacionados en queries complejas.

### 3. Deduplicación por (code, section, year) + max(issue)
- **Decisión:** Si hay múltiples versiones del mismo artículo (diferentes issues), solo mostrar la más reciente.
- **Por qué:** Las regulaciones se actualizan varias veces al año (issues). El usuario siempre quiere la versión vigente.
- **Implementación:** En `_merge_and_deduplicate()` del retriever.

### 4. Loop agentic de hasta 3 pasos
- **Decisión:** El LLM puede decidir buscar más información (SEARCH) o responder (ANSWER), hasta 3 iteraciones.
- **Por qué:** Permite resolver cross-references entre artículos (e.g., "según lo definido en el Artículo C3.14").
- **Trade-off:** Cada paso SEARCH añade una llamada LLM + una búsqueda. En la práctica, la mayoría de queries se resuelven en 1-2 pasos.

### 5. Frontend con inline styles
- **Decisión:** No usar Tailwind ni CSS modules. Todo con objetos `styles` en TypeScript.
- **Por qué:** Decisión del desarrollador original. Funciona, es explícito, y no requiere configuración de Tailwind.
- **Trade-off:** Verbose. Para responsive hay que usar hooks (ya implementado con `isMobile` en chat/page.tsx).

### 6. Intent detection local
- **Decisión:** `detect_intent()` usa un clasificador regex en `llm/intent.py` — cero llamadas LLM.
- **Por qué:** Ahorra ~$0.005 por query conversacional y ~2 segundos de latencia.
- **Patrones:** Saludos, preguntas sobre el bot, frases cortas sin términos técnicos → CONVERSATIONAL. Todo lo demás → REGULATIONS.

### 7. prepare_search() unifica filters + rewrite
- **Decisión:** Una sola llamada LLM devuelve `{ year, section, search_query }`.
- **Por qué:** Antes eran 2 llamadas separadas (`extract_filters` + `rewrite_query`). Ahora es 1, ahorrando ~$0.01 y ~2s por query.

### 8. Deploy: Supabase Session Pooler (no Direct Connection)
- **Decisión:** Usar el Session Pooler de Supabase: `aws-1-eu-central-1.pooler.supabase.com:5432`
- **Por qué:** Render free tier es **IPv4-only**. La URL de direct connection de Supabase es IPv6. El Session Pooler tiene soporte IPv4.
- **URL format:** `postgresql+asyncpg://postgres.<project_ref>:<password>@aws-1-eu-central-1.pooler.supabase.com:5432/postgres?ssl=require`
- **CRÍTICO:** Nunca usar `db.<project_ref>.supabase.co` en Render free tier — es IPv6 y falla con "connection refused".

### 9. Python version en Render
- **Decisión:** Fijar Python 3.11.6 via `backend/.python-version` y env var `PYTHON_VERSION=3.11.6`
- **Por qué:** Render defaulteaba a Python 3.14 que rompía la compilación de pymupdf y torch.

### 10. torch CPU-only en Render
- **Build command en render.yaml:** `pip install torch==2.9.0+cpu --index-url https://download.pytorch.org/whl/cpu`
- **Por qué:** torch full (~2GB) no cabe en el free tier. CPU-only (~200MB) es suficiente para sentence-transformers.
- **Nota:** La versión exacta cambia. Si falla, buscar la última disponible en `https://download.pytorch.org/whl/cpu`.

### 11. Query logging con tabla query_logs
- **Decisión:** Toda query se registra con intent, año, sección, respuesta, tiempo, artículos citados, error.
- **Por qué:** Permite monitorizar calidad en producción, detectar errores, y recopilar feedback.
- **`ChatResponse` incluye `query_id`** — el frontend lo usa para enviar feedback 👍/👎 sin necesitar otro lookup.
- **`_log_query()` nunca lanza excepciones** — el logging no puede romper la respuesta al usuario.

---

## Conocimiento sobre el PDF Parser (LEER ANTES DE TOCAR pdf_parser.py)

El parser es frágil porque los PDFs de la FIA tienen formatos muy distintos entre secciones (Technical, Sporting, Financial). Documentamos los bugs encontrados en producción real:

### Bug 1 — Entradas de TOC como artículos (Financial appendices)
- **Síntoma:** Artículos como `E1`, `D4` con content = `"ARTICLE E1: TITLE\n3"` (solo título + página).
- **Causa:** Los apéndices de Financial regs tienen tabla de contenidos propia con el mismo formato que los artículos.
- **Fix:** `_is_toc_entry()` en `_save_article()` — detecta patrón `ARTICLE X: TITLE\n<número_página>` y descarta.

### Bug 2 — Cabeceras/pies de página en el body del artículo
- **Síntoma:** Artículos terminan con `"SECTION C: TECHNICAL REGULATIONS"` o `"Formula 1 Financial Regulations\n37"`.
- **Causa:** El parser añadía todas las líneas sin match al artículo actual, incluyendo running headers de página.
- **Fix:** `PAGE_NOISE_PATTERNS` + `_is_page_noise()` — filtra estas líneas antes de añadirlas al body.

### Bug 3 — Artículos truncados a mitad de frase (cross-page)
- **Síntoma:** Artículos largos (>3000 chars) terminan en medio de una frase.
- **Causa:** El parser procesaba página a página. Cuando un artículo cruzaba un salto de página, la cabecera de la nueva página interrumpía el flow.
- **Fix:** Procesar el documento completo como un stream (`full_text = "\n".join(page.get_text() for page in doc)`). Esto es la solución más impactante del Sprint 1.

### Bug 4 — Artículos padre faltantes (orphan sub-articles)
- **Síntoma:** Artículos 2.1, 2.2... 2.11 en Financial tienen `parent_code="2"` pero artículo "2" no existe en la DB.
- **Causa:** El artículo padre "2" tiene muy poco contenido (solo su header line) y es descartado por el filtro de contenido mínimo.
- **Fix:** `_fill_missing_parents()` — post-proceso que crea stubs para cualquier `parent_code` referenciado que no tenga entrada. El stub tiene content mínimo pero existe, permitiendo que el retriever lo encuentre.

### Bug 5 — Códigos numéricos puros como artículos (page numbers)
- **Síntoma:** Artículos con code `"0"`, `"103"`, `"104"` que son números de página o referencias de TOC.
- **Causa:** `ARTICLE_PATTERN = re.compile(r'^([A-Z]*\d+)...')` — `[A-Z]*` matchea cero letras, así que "103" es un match válido con `major="103"`.
- **Fix 1 (original):** `if level == 1 and not title and len(major) < 3: continue` — solo filtró códigos de 1-2 dígitos.
- **Fix 2 (actual):** `if level == 1 and major.isdigit() and not title: continue` — filtra TODOS los códigos numéricos puros sin título.
- **Importante:** Artículos numéricos CON título (e.g., "2 COST CAP OBLIGATIONS") son legítimos en Financial regs y NO deben filtrarse.

### Cobertura de regulaciones en producción (post-ingestión)
```
Financial 2025: Issues 23, 24
Financial 2026: Issues 2, 3, 4, 7
Sporting 2025: Issues 4, 5
Sporting 2026: Issue 4
Technical 2025: Issue 2 (solo uno — gap conocido)
Technical 2026: Issues 11, 12, 14, 15
```

---

## Problemas conocidos (pendientes)

### ✅ RESUELTO — P1: Demasiadas llamadas LLM por query
- `detect_intent()` ahora es local (0 LLM calls).
- `prepare_search()` unifica filters + rewrite en 1 sola llamada.
- Total: 2 llamadas por query regulatoria (antes eran 4).

### ✅ RESUELTO — P2: Dockerfile frontend usa dev mode
- Ahora usa `RUN npm run build` + `CMD ["npm", "start"]`.

### ✅ RESUELTO — P3: Archivos de debug sueltos
- Limpiados en la fase de preparación del deploy.

### ✅ RESUELTO — P4: Parser crea artículos basura (1623 artículos vacíos)
- Bugs 1-5 documentados arriba, todos corregidos en `pdf_parser.py`.
- Re-ingestión completa realizada con el parser corregido.

### PENDIENTE — Cold start de Render free tier
- **Síntoma:** Primera query tarda ~40 segundos (Render duerme tras 15 min de inactividad).
- **Solución:** Configurar UptimeRobot (o similar) para hacer ping a `/warmup` cada 10 minutos.
- **Endpoint `/warmup`** existe en main.py — pre-carga el modelo de embeddings.
- **URL para el ping:** `https://f1-regulations-engine.onrender.com/warmup`

### PENDIENTE — Technical 2025 solo tiene Issue 2
- Hay múltiples issues posteriores en `archives/` que no están indexados.
- Ejecutar auditoría: `find archives/ -name "*Technical*2025*" -o -name "*2025*technical*"`.

### PENDIENTE — Artículos cortos residuales en Financial 2026
- Después del fix del parser, aún puede haber entradas de TOC que no matcheen el patrón exacto.
- Verificar post-ingestión con: `SELECT * FROM articles WHERE section='Financial' AND LENGTH(content) < 50`.

---

## Mejoras de retrieval implementadas (2026-05-12)

### 12. websearch_to_tsquery en FTS
- **Decisión:** Cambiar `plainto_tsquery` por `websearch_to_tsquery` en `_retrieve_by_fulltext()`.
- **Por qué:** `websearch_to_tsquery` genera queries más inteligentes: respeta comillas para frases exactas, interpreta `-` como exclusión, y maneja multi-término mejor.
- **Cambio:** 1 línea en `retriever.py`.

### 13. Section-aware RRF boost
- **Decisión:** Cuando `prepare_search()` detecta una sección, multiplicar el RRF score por 1.2x para artículos de esa sección.
- **Por qué:** Sin esto, artículos de otras secciones con terminología similar (e.g., "weight" aparece en Technical Y Financial) contaminan los resultados.
- **Implementación:** `detected_section` se pasa a `_merge_and_deduplicate()`. NO cambia k=60.

### 14. Context trimming para el LLM
- **Decisión:** Limitar el contexto enviado al LLM a MAX_CONTEXT_ARTICLES=12 artículos, y truncar artículos individuales >2000 chars a ~1500 (en boundary de frase).
- **Por qué:** Con el agentic loop acumulando artículos de múltiples pasos, el contexto crecía demasiado. El LLM responde mejor con menos contexto pero más relevante.
- **Implementación:** En `_build_context()` de `client.py`.

### 15. Prompt tuning del agentic step
- **Decisión:** Actualizar AGENTIC_PROMPT con reglas de citación estrictas y guard contra hallucinations.
- **Cambios clave:** (1) Exigir citas con article_code exacto, (2) instrucción de "I don't have enough info" en vez de inventar, (3) no mezclar regulaciones de diferentes años.

### 16. Chunking de artículos largos para embeddings
- **Decisión:** Artículos >1500 chars se dividen en chunks de ~800 chars con overlap de 200. Cada chunk genera su propio embedding pero mantiene el mismo article_id.
- **Por qué:** Un embedding de 384 dims no captura bien un artículo de 3000+ chars que cubre múltiples temas.
- **Implementación:** `ingestion/chunker.py` + cambios en `pipeline.py`.
- **Requiere:** Re-generar embeddings (no re-parsear). La tabla `article_embeddings` ya soporta múltiples rows por article_id.

### 17. Eval framework — normalización de códigos de artículo
- **Bug encontrado:** Los artículos técnicos en la DB usan prefijo de sección (C4.1, C3.5) pero el test set esperaba códigos sin prefijo (4.1, 3.5). El eval daba 0% precision/recall artificialmente.
- **Fix:** `_normalize_code()` en `run_eval.py` y `run_single.py` — strip single-letter prefix antes de comparar.
- **Nota:** Sporting y Financial pueden usar códigos diferentes (números planos como "55", "6").

---

## Datos del proyecto

- **98 PDFs** de regulaciones FIA en `archives/` (2023-2026)
- **Embeddings:** 384 dimensiones (all-MiniLM-L6-v2)
- **PostgreSQL tables:** documents, articles, article_embeddings, query_logs
- **Índices en Supabase:** HNSW para vector search (creado por schema.sql)

## Modelo LLM actual

- **Configurado:** `openai/gpt-oss-120b` via OpenRouter
- **Nota:** Para reducir costes, el modelo de `prepare_search` podría ser más barato (e.g., `meta-llama/llama-3.1-8b-instruct`). El agentic reasoning sí necesita un modelo potente.

## Schema de query_logs

```sql
CREATE TABLE query_logs (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    query TEXT NOT NULL,
    intent VARCHAR(20) NOT NULL DEFAULT 'REGULATIONS',
    year INTEGER,
    section VARCHAR(50),
    answer TEXT,
    retrieved_count INTEGER DEFAULT 0,
    research_steps INTEGER DEFAULT 0,
    response_time_ms INTEGER,
    cited_articles TEXT,        -- comma-separated article codes
    was_helpful BOOLEAN,        -- populated via POST /api/chat/feedback
    error_occurred BOOLEAN DEFAULT FALSE
);
```

## Notas para debugging en producción

- **Ver logs de Render:** Dashboard Render → Service → Logs
- **Ver query_logs en Supabase:** SQL Editor → `SELECT * FROM query_logs ORDER BY created_at DESC LIMIT 20`
- **Ver artículos cortos/basura:** `SELECT article_code, section, year, LENGTH(content) as len, LEFT(content,100) FROM articles WHERE LENGTH(content) < 50 ORDER BY section, year`
- **Verificar orphans:** `SELECT a.article_code, a.parent_code FROM articles a LEFT JOIN articles p ON a.parent_code=p.article_code AND a.section=p.section AND a.year=p.year AND a.issue=p.issue WHERE a.parent_code IS NOT NULL AND p.article_code IS NULL`
- **El index.lock de git** a veces queda bloqueado desde sesiones de Cowork. Borrarlo manualmente: `del .git\index.lock` (Windows) o `rm .git/index.lock` (Linux/Mac).
