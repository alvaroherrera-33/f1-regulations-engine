# Learnings y Decisiones Técnicas — F1 Regulations Engine

> Registro de decisiones de arquitectura, problemas detectados, y conocimiento acumulado.
> Actualizar este archivo conforme se avance en el proyecto.

## Decisiones de arquitectura ya tomadas

### 1. Embeddings locales vs API
- **Decisión:** Usar `sentence-transformers/all-MiniLM-L6-v2` ejecutando localmente en el backend.
- **Por qué:** Elimina dependencia de API externa para embeddings, reduce latencia, coste $0.
- **Trade-off:** Consume ~400-500MB RAM. Esto limita las opciones de free tier.
- **Si el free tier no aguanta:** Alternativa → usar OpenRouter embeddings API (`openai/text-embedding-3-small`). Requiere cambiar `backend/ingestion/local_embeddings.py` y `backend/app/retrieval/retriever.py`. Ya existe un archivo `backend/ingestion/embeddings.py` con una implementación de OpenRouter embeddings (no activa).

### 2. Búsqueda híbrida con RRF
- **Decisión:** Combinar vector search (pgvector) + Full-Text Search (PostgreSQL) con Reciprocal Rank Fusion.
- **Por qué:** Mejor recall que solo vector search. FTS captura coincidencias exactas de términos técnicos que los embeddings pueden perder.
- **Parámetro RRF k=60:** Es el estándar académico. No tocar sin benchmarks.
- **SIMILARITY_THRESHOLD = 0.85:** Cosine distance (0=idéntico, 2=opuesto). 0.85 es permisivo a propósito para no perder resultados relevantes.

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
- **Trade-off:** Verbose, no responsive por defecto (hay que añadir media queries manualmente o con hooks).

## Problemas detectados (pendientes de resolver)

### P1: Demasiadas llamadas LLM por query (CRÍTICO)
- **Estado:** Pendiente (PLAN.md 1.1 + 1.2)
- **Detalle:** Cada query regulatoria hace 4 llamadas a OpenRouter:
  1. `detect_intent()` — clasificar si es conversational o regulations
  2. `extract_query_filters()` — extraer año y sección
  3. `rewrite_query()` — reformular la query para búsqueda
  4. `generate_reasoning_step()` — loop agentic (1-3 veces)
- **Impacto:** ~8-12 segundos de latencia, ~$0.02-0.05 por query.
- **Solución:** Intent local con regex (0 calls) + unificar filters+rewrite en 1 call.

### P2: Dockerfile frontend usa dev mode en producción
- **Estado:** Pendiente (PLAN.md 1.5)
- **Detalle:** `CMD ["npm", "run", "dev"]` en `frontend/Dockerfile`. Esto es lento, muestra warnings de hot-reload, y no optimiza el bundle.
- **Solución:** `RUN npm run build` + `CMD ["npm", "start"]`.

### P3: Archivos de debug sueltos en el repo
- **Estado:** Pendiente (PLAN.md 1.6)
- **Detalle:** ~15 archivos de test/debug en la raíz y en `backend/` que dan mala impresión en GitHub.
- **Lista completa en PLAN.md tarea 1.6.**

### P4: No hay responsive design
- **Estado:** Pendiente (PLAN.md 2.1)
- **Detalle:** La sidebar del chat tiene `width: 320px` fijo. En mobile queda inutilizable.

### P5: Landing page con datos estáticos
- **Estado:** Pendiente (PLAN.md 2.3)
- **Detalle:** La sección de métricas muestra texto fijo ("Latest", "Semantic", "Citations") en vez de datos reales del endpoint `/status`.

### P6: No hay navegación entre páginas
- **Estado:** Pendiente (PLAN.md 2.4)
- **Detalle:** No existe Navbar. Para ir de Chat a Upload hay que cambiar la URL manualmente.

## Datos del proyecto

- **98 PDFs** de regulaciones FIA en `archives/` (2023-2026)
  - Organizados por año y tipo: `archives/2026/technical/`, `archives/2025/sporting/`, etc.
  - Tres secciones: Technical, Sporting, Financial
  - Múltiples issues por año (actualizaciones del reglamento)
- **Embeddings:** 384 dimensiones (all-MiniLM-L6-v2)
- **PostgreSQL tables:** documents, articles, article_embeddings
- **Índices:** HNSW para vector search, B-tree para filtros, GIN potencial para FTS

## Modelo LLM actual

- **Configurado:** `openai/gpt-oss-120b` via OpenRouter
- **Alternativas probadas o consideradas:**
  - `anthropic/claude-3.5-sonnet` (mencionado en DEPLOYMENT.md)
  - Cualquier modelo de OpenRouter sirve (el código es model-agnostic)
- **Nota:** Para reducir costes, considerar modelos más baratos para intent+filters (e.g., `meta-llama/llama-3-8b-instruct`) y reservar el modelo potente para el agentic reasoning.

## APIs y endpoints existentes

| Endpoint | Método | Funciona | Notas |
|----------|--------|----------|-------|
| `/health` | GET | ✅ | Devuelve status DB |
| `/status` | GET | ✅ | Cuenta docs, articles, embeddings |
| `/` | GET | ✅ | Info básica de la API |
| `/api/chat` | POST | ✅ | Endpoint principal RAG |
| `/api/articles` | GET | ✅ | Lista artículos con filtros |
| `/api/articles/{code}` | GET | ✅ | Artículo por código |
| `/api/upload` | POST | ✅ | Upload + ingestion de PDF |
| `/api/upload/status/{job_id}` | GET | ⚠️ | No verificado |
| `/docs` | GET | ✅ | Swagger UI automático |

## Notas para debugging

- Los logs del backend usan `print()` (pendiente migrar a `logging`).
- El archivo `debug_routing.log` se crea automáticamente en `detect_intent()` — eliminar esa lógica al limpiar.
- Si el embedding model no carga, verificar que `torch` CPU está instalado (el Dockerfile ya lo hace).
- Si pgvector no funciona, verificar que la extensión está creada: `CREATE EXTENSION IF NOT EXISTS vector;`
