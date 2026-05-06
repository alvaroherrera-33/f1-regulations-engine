# Plan de Finalización — F1 Regulations RAG Engine

> Última actualización: 2026-05-06
> Cada tarea incluye el archivo afectado y criterio de aceptación.
> Marcar con [x] conforme se completen.

## Resumen

4 fases, ~7-10 días de trabajo total. Prioridad: estabilizar → pulir UI → desplegar gratis → impresionar.

---

## FASE 1 — Estabilizar el Core (1-2 días)

**Objetivo:** Reducir costes por query, mejorar latencia, y hacer el sistema robusto.

### [ ] 1.1 Intent detection local (sin LLM)

**Archivo:** `backend/app/llm/client.py` → método `detect_intent()`
**Archivo nuevo:** `backend/app/llm/intent.py`

**Qué hacer:**
- Crear un clasificador basado en regex/keywords que detecte CONVERSATIONAL vs REGULATIONS sin llamar a OpenRouter.
- Patrones CONVERSATIONAL: saludos (hola, hello, hi, hey, thanks, gracias, bye, adiós), preguntas sobre el bot (qué puedes hacer, quién eres), frases cortas sin términos técnicos.
- Todo lo demás → REGULATIONS (por defecto, igual que ahora).
- Eliminar la llamada LLM de `detect_intent()`.

**Criterio:** Una query tipo "hola" no genera ninguna llamada a OpenRouter. Una query técnica sigue funcionando igual.

**Ahorro:** ~$0.005/query + ~2 segundos de latencia.

### [ ] 1.2 Unificar extract_filters + rewrite_query en una sola llamada LLM

**Archivo:** `backend/app/llm/client.py` → métodos `extract_query_filters()` y `rewrite_query()`
**Archivo:** `backend/app/routes/chat.py`

**Qué hacer:**
- Crear un nuevo método `prepare_search(query)` que con UNA sola llamada a OpenRouter devuelva:
  ```json
  {
    "year": 2026,
    "section": "Technical",
    "search_query": "minimum car weight regulations power unit"
  }
  ```
- Combinar los prompts de `extract_query_filters` y `rewrite_query` en uno solo.
- Actualizar `chat.py` para usar este nuevo método en vez de las dos llamadas separadas.
- Eliminar los métodos antiguos (o marcarlos como deprecated).

**Criterio:** Solo 2 llamadas LLM por query regulatoria: 1 prepare_search + 1 agentic loop (antes eran 4).

### [ ] 1.3 Error handling robusto

**Archivos:** `backend/app/llm/client.py`, `backend/app/routes/chat.py`

**Qué hacer:**
- Añadir retry con backoff exponencial para llamadas a OpenRouter (max 2 retries, backoff 1s → 3s).
- Si OpenRouter falla después de retries: devolver respuesta degradada amable en vez de error 500.
- Validar que `OPENROUTER_API_KEY` existe al startup (en `main.py` o `config.py`).
- Manejar timeout de la DB en el retriever.
- Logging estructurado: reemplazar `print()` por `logging.getLogger(__name__)`.

**Criterio:** Si OpenRouter está caído, el usuario ve "El servicio de IA no está disponible temporalmente" en vez de un error técnico.

### [ ] 1.4 Caché de embeddings de queries

**Archivo:** `backend/app/retrieval/retriever.py` → método `_retrieve_by_vector()`
**Archivo:** `backend/ingestion/local_embeddings.py`

**Qué hacer:**
- Añadir `functools.lru_cache` (o dict simple) al método de embedding de queries.
- Cache size: 256 queries más recientes.
- Solo para queries, NO para embeddings de artículos (esos se generan una vez en ingestion).

**Criterio:** La misma query repetida no recalcula el embedding. Verificar con un print/log que dice "cache hit".

### [ ] 1.5 Dockerfile frontend: build de producción

**Archivo:** `frontend/Dockerfile`

**Qué hacer:**
- Cambiar de:
  ```dockerfile
  CMD ["npm", "run", "dev"]
  ```
- A:
  ```dockerfile
  RUN npm run build
  CMD ["npm", "start"]
  ```
- Usar multi-stage build para reducir tamaño de imagen.

**Criterio:** `docker-compose up` sirve la app con Next.js en modo producción. Más rápido y sin hot-reload warnings.

### [ ] 1.6 Limpiar archivos de debug del repo

**Archivos a eliminar de la RAÍZ del proyecto:**
- `check_2026.py`, `check_db_sections.py`, `final_verify.py`
- `test_autofilter.py`, `test_parser_debug.py`
- `verify_b64.py`, `verify_fix.py`, `verify_search_quality.py`
- `routing_debug.log`

**Archivos a eliminar de `backend/`:**
- `check_2026.py`, `check_engine.py`, `diag_2026.py`, `diag_output.txt`
- `debug_routing.log`, `final_verify.py`
- `simple_llm_test.py`, `test_autofilter.py`, `test_parser_debug.py`
- `verify_search_quality.py`

**Conservar:** `backend/test_api.py` y `backend/test_routing.py` (renombrarlos a `tests/` si se quiere).

**Qué hacer:**
- Eliminar los archivos listados.
- Verificar que `.gitignore` incluye `*.log`, `diag_output.txt`, etc.
- Actualizar `.gitignore` si es necesario.

**Criterio:** `git status` no muestra archivos sueltos de debug. La raíz del proyecto está limpia.

---

## FASE 2 — Pulir UI/UX (2-3 días)

**Objetivo:** Que el frontend se vea profesional y funcione en mobile.

### [ ] 2.1 Responsive design

**Archivos:** `frontend/app/chat/page.tsx`, `frontend/components/ChatInterface.tsx`

**Qué hacer:**
- Sidebar colapsable en mobile (< 768px): botón hamburguesa que muestra/oculta filtros.
- Chat full-width en mobile.
- Landing page: grid de 1 columna en mobile.
- Usar media queries inline o un hook `useMediaQuery`.

**Criterio:** La app es usable en un iPhone 12 (390px width).

### [ ] 2.2 Loading states mejorados

**Archivo:** `frontend/components/ChatInterface.tsx`

**Qué hacer:**
- Reemplazar los 3 dots estáticos por una animación CSS real (keyframes).
- Mostrar texto contextual: "Buscando en regulaciones...", "Analizando artículos...", "Generando respuesta...".
- Opcional (nice to have): streaming de la respuesta del LLM.

**Criterio:** El usuario sabe qué está pasando mientras espera. No ve una pantalla muerta.

### [ ] 2.3 Landing page con métricas reales

**Archivo:** `frontend/app/page.tsx`

**Qué hacer:**
- Fetch a `GET /status` al cargar la landing.
- Mostrar número real de documentos, artículos indexados, y embeddings.
- En las cards de features, quitar `opacity: 0.7` de las que funcionan.
- Añadir link a `/upload` desde la landing.

**Criterio:** La landing muestra datos reales del sistema, no texto estático.

### [ ] 2.4 Navbar con navegación

**Archivo nuevo:** `frontend/components/Navbar.tsx`
**Archivo:** `frontend/app/layout.tsx`

**Qué hacer:**
- Crear componente Navbar con links: Home, Chat, Upload, API Docs (link externo a /docs).
- Estilo: barra superior oscura con acento rojo (#eb0000), logo/nombre a la izquierda.
- Indicador de página activa.
- Integrar en `layout.tsx`.

**Criterio:** Se puede navegar entre páginas sin usar la URL directamente.

### [ ] 2.5 Mejorar CitationCard

**Archivo:** `frontend/components/CitationCard.tsx`

**Qué hacer:**
- Expandir/colapsar el excerpt (por defecto colapsado a 3 líneas).
- Botón "Copiar cita" al clipboard.
- Mostrar badge con año y sección (e.g., "Technical 2026").
- Highlight de keywords de la query en el excerpt.

**Criterio:** Las citas son legibles y útiles, no un bloque enorme de texto.

### [ ] 2.6 Queries de ejemplo precargadas

**Archivo:** `frontend/components/ChatInterface.tsx`

**Qué hacer:**
- En el empty state, mostrar 4-6 botones con queries de ejemplo:
  - "What is the minimum weight of an F1 car in 2026?"
  - "How does the DRS system work?"
  - "What are the power unit fuel flow limits?"
  - "Explain the cost cap regulations"
  - "What changed in 2026 technical regulations?"
- Click en uno → se envía como query automáticamente.

**Criterio:** Un usuario nuevo puede interactuar sin pensar qué preguntar.

---

## FASE 3 — Desplegar GRATIS (1 día)

**Objetivo:** Tener una URL live para poner en CV/LinkedIn/GitHub.

### [ ] 3.1 Base de datos: Supabase free tier

**Qué hacer:**
- Crear cuenta en Supabase (free: 500MB DB, pgvector incluido).
- Ejecutar `schema.sql` en el SQL editor de Supabase.
- Obtener connection string y guardarla.
- **IMPORTANTE:** Supabase usa `postgresql://` (sync). El backend necesita `postgresql+asyncpg://`. Reemplazar el prefijo al configurar.

**Criterio:** `GET /health` devuelve `database: connected` contra Supabase.

### [ ] 3.2 Backend: Render.com free tier

**Qué hacer:**
- Crear cuenta en Render.com.
- New Web Service → conectar repo GitHub → root directory: `backend`.
- Build command: `pip install torch==2.1.2+cpu --index-url https://download.pytorch.org/whl/cpu && pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Env vars: `DATABASE_URL`, `OPENROUTER_API_KEY`, `LLM_MODEL`, `ALLOWED_ORIGINS`.
- **ATENCIÓN:** Free tier tiene 512MB RAM. sentence-transformers necesita ~400MB. Monitorear.
- **ALTERNATIVA si no cabe:** Usar Fly.io free (256MB) y mover embeddings a API (OpenRouter embeddings) en vez de local. Esto requiere cambiar `local_embeddings.py`.

**Criterio:** `curl https://tu-backend.onrender.com/health` devuelve 200.

### [ ] 3.3 Frontend: Vercel free tier

**Qué hacer:**
- Crear cuenta en Vercel.
- Import project → root directory: `frontend`.
- Env var: `NEXT_PUBLIC_API_URL=https://tu-backend.onrender.com`.
- Deploy automático.

**Criterio:** La app carga en `https://tu-app.vercel.app` y el chat funciona.

### [ ] 3.4 Ingestar los 98 PDFs en producción

**Qué hacer:**
- Desde local, ejecutar el script de ingestion apuntando a la DB de Supabase:
  ```bash
  DATABASE_URL=postgresql+asyncpg://... python -m scripts.ingest_archives
  ```
- Verificar con `GET /status` que muestra documentos y artículos indexados.
- Esto se hace UNA VEZ. Los datos quedan en Supabase.

**Criterio:** `/status` muestra >0 documentos, >0 artículos, >0 embeddings.

### [ ] 3.5 Actualizar CORS y URLs cruzadas

**Qué hacer:**
- Backend `ALLOWED_ORIGINS`: añadir la URL de Vercel.
- Frontend `NEXT_PUBLIC_API_URL`: apuntar al backend en Render.
- Verificar que no hay errores CORS en la consola del navegador.

**Criterio:** El chat funciona end-to-end desde la URL de Vercel.

---

## FASE 4 — Impresionar a Recruiters y Empresas F1 (2-3 días)

**Objetivo:** Que el proyecto destaque en un portfolio y en entrevistas técnicas.

### [ ] 4.1 README espectacular

**Archivo:** `README.md`

**Qué hacer:**
- Mantener el contenido técnico actual (es bueno).
- Añadir al inicio: badges (Python, TypeScript, FastAPI, pgvector, License).
- Añadir GIF demo de una sesión de chat real (grabar con LICEcap o similar).
- Añadir link prominente a la demo live.
- Añadir sección "Why this project?" explicando la motivación.
- Arquitectura: el diagrama ASCII actual está bien, pero considerar un diagrama SVG/Mermaid.

**Criterio:** Un recruiter entiende qué hace el proyecto en 10 segundos mirando el README.

### [ ] 4.2 Página "About / How it works" en el frontend

**Archivo nuevo:** `frontend/app/about/page.tsx`

**Qué hacer:**
- Explicar visualmente: qué es RAG, cómo funciona la búsqueda híbrida, qué es RRF.
- Diagrama del flujo de una query (puede ser SVG inline o imagen).
- Métricas: latencia promedio, precisión de búsqueda.
- Stack tecnológico con logos.

**Criterio:** Un entrevistador técnico puede entender la arquitectura sin leer código.

### [ ] 4.3 Métricas visibles en la UI

**Archivos:** `frontend/components/ChatInterface.tsx`, `backend/app/routes/chat.py`

**Qué hacer:**
- Devolver `response_time_ms` desde el backend (medir con `time.time()`).
- Mostrar en el frontend bajo cada respuesta: "X artículos consultados · Y pasos de investigación · Zms".
- Esto demuestra rigor técnico y transparencia.

**Criterio:** Cada respuesta del chat muestra métricas de rendimiento.

### [ ] 4.4 Comparador de regulaciones entre años (KILLER FEATURE — Opcional)

**Archivos nuevos:** `frontend/app/compare/page.tsx`, `backend/app/routes/compare.py`

**Qué hacer:**
- Endpoint: `GET /api/compare?code=3.7&year_a=2025&year_b=2026`
- Devuelve el texto de ambas versiones del artículo.
- Frontend: vista diff lado a lado con cambios resaltados.
- Esto NO existe en ningún producto público para F1.

**Criterio:** Se puede ver qué cambió en un artículo entre dos años. Los cambios están resaltados.

---

## Resumen de costes operativos

| Servicio | Coste | Notas |
|----------|-------|-------|
| Supabase (DB) | $0/mes | Free tier, 500MB, pgvector incluido |
| Render (Backend) | $0/mes | Free tier, 512MB RAM, se apaga tras inactividad |
| Vercel (Frontend) | $0/mes | Free tier, CDN global, deploy automático |
| OpenRouter (LLM) | ~$0.01-0.05/query | Según modelo elegido |
| **Total infraestructura** | **$0/mes** | Solo pagas por uso de LLM |

## Orden recomendado si hay poco tiempo

Si solo tienes 3-4 días, haz: 1.1 → 1.2 → 1.5 → 1.6 → 3.x (deploy) → 2.6 → 4.1
Esto te da: sistema más barato, desplegado live, con queries de ejemplo, y README bonito.
