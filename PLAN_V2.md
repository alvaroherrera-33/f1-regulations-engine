# Plan de Mejoras V2 — F1 Regulations Engine

> Creado: 2026-05-22  
> Estado de la DB: 16,182 artículos, 19,801 embeddings, años 2023–2026  
> Este plan es ambicioso pero realista dentro de las limitaciones del free tier.

---

## Contexto y Estado Actual

El motor RAG funciona en producción con búsqueda híbrida (vector + FTS + RRF). Las mejoras documentadas aquí atacan tres áreas de alto impacto identificadas tras tener los 4 años completos en la DB:

1. **Frescura de datos** — Los reglamentos de la FIA se actualizan múltiples veces al año. El sistema actualmente requiere ingestion manual.
2. **Granularidad de búsqueda** — Los artículos tienen 3 niveles jerárquicos (Article → Sub-article → Clause) pero el retriever los trata todos igual.
3. **Validez temporal** — Una respuesta basada en regulación de 2023 puede estar obsoleta en 2026. El sistema no lo indica.

---

## MEJORA 1 — Monitor de actualizaciones FIA (Keep-data-fresh)

### Problema
La FIA publica nuevos issues de reglamento sin calendario fijo. Actualmente hay que detectarlos manualmente y ejecutar la ingestion a mano.

### Arquitectura propuesta

```
Cron job (diario) → FIA scraper → diff con DB → pipeline de ingestion → notificación
```

**Fase 1 — Scraper FIA**

La FIA publica PDFs en:
- `https://www.fia.com/regulation/category/110` (Technical)
- `https://www.fia.com/regulation/category/111` (Sporting)
- `https://www.fia.com/regulation/category/112` (Financial)

Cada PDF tiene un título con year + issue (e.g., "2026 Formula 1 Technical Regulations - Issue 15").

Script `backend/scripts/fia_scraper.py`:
```python
def fetch_fia_regulations() -> list[FIADocument]:
    """Devuelve lista de {url, year, section, issue, title, published_at}"""
    # BeautifulSoup o httpx para parsear la página de la FIA
    # Extraer links a PDFs con su metadata
    # Normalizar nombres → year/section/issue
```

**Fase 2 — Diff con DB**

```python
def find_new_documents(fia_docs: list, db_docs: list) -> list:
    """Compara por (year, section, issue). Devuelve solo los nuevos."""
    existing = {(d.year, d.section, d.issue) for d in db_docs}
    return [d for d in fia_docs if (d.year, d.section, d.issue) not in existing]
```

**Fase 3 — Auto-ingestion**

Si hay documentos nuevos → descarga PDF → ejecuta pipeline completo (parse → embed → upsert).
Usa `ON CONFLICT (article_code, year, section, issue) DO UPDATE` en vez de DO NOTHING para actualizar contenido si cambia.

**Fase 4 — Nueva tabla `fia_sync_log`**

```sql
CREATE TABLE fia_sync_log (
    id SERIAL PRIMARY KEY,
    checked_at TIMESTAMP DEFAULT NOW(),
    new_docs_found INTEGER DEFAULT 0,
    new_articles_indexed INTEGER DEFAULT 0,
    errors TEXT,
    status VARCHAR(20) -- 'ok', 'error', 'no_changes'
);
```

**Fase 5 — Indicador en el frontend**

En el Navbar o en `/stats`:
- "Regulations up to date as of [fecha]" 
- Badge "NEW" si se indexó algo en los últimos 7 días
- Endpoint `GET /api/sync/status` → `{last_checked, last_new_doc, is_stale}`

**Implementación estimada:** 3-4 días. Prioridad: ALTA (diferenciador técnico).

**Limitaciones a considerar:**
- La FIA puede cambiar su estructura HTML → hacer el scraper resiliente con múltiples fallback patterns
- Rate limiting: no más de 1 request/segundo a fia.com
- Los PDFs requieren autenticación para algunos documentos históricos

---

## MEJORA 2 — Búsqueda Jerárquica por Niveles

### Problema
Los artículos tienen 3 niveles:
- **Level 1:** Artículo principal (e.g., `Art. 3 — CHASSIS`)
- **Level 2:** Sub-artículo (e.g., `3.1 — Survival cell`)
- **Level 3:** Cláusula (e.g., `3.1.1 — Minimum dimensions`)

Actualmente el retriever devuelve cualquier nivel sin distinción. Esto causa dos problemas:
1. Preguntas amplias devuelven cláusulas muy específicas (Level 3) que no dan contexto suficiente.
2. Preguntas específicas devuelven artículos padre (Level 1) con contenido demasiado general.

### Arquitectura propuesta

**A. Clasificación de intención de granularidad**

En `prepare_search()`, añadir un campo `search_depth: "broad" | "specific" | "auto"`:

```python
# Prompt addition:
# - If the query asks "what are the rules for X" → broad (return overview + sub-articles)
# - If the query asks for a specific measurement/number/condition → specific (clause level)
# - Default: auto (let RRF decide)
```

**B. Retrieval multi-nivel**

En `retriever.py`, nueva estrategia `_retrieve_hierarchical()`:

```python
async def _retrieve_hierarchical(self, query_emb, query_text, filters, depth):
    if depth == "broad":
        # Paso 1: buscar en Level 1+2 con mayor peso
        # Paso 2: para cada Level 1 encontrado, incluir sus Level 2 children
        # Resultado: visión completa del artículo con sub-estructura
        
    elif depth == "specific":
        # Buscar principalmente Level 2+3
        # Enriquecer con Level 1 padre para contexto
        
    else:  # auto
        # Usar RRF normal pero ponderar Level 2 ligeramente más (sweet spot)
        # Level 1 pesa 0.8x, Level 2 pesa 1.0x, Level 3 pesa 0.9x
```

**C. Nuevo campo `level_weight` en RRF**

```python
LEVEL_WEIGHTS = {1: 0.85, 2: 1.0, 3: 0.90}  # Level 2 ligeramente preferido

def _merge_and_deduplicate(results, detected_section):
    for r in results:
        rrf_score = 1 / (k + rank)
        rrf_score *= LEVEL_WEIGHTS.get(r.level, 1.0)
        rrf_score *= 1.2 if r.section == detected_section else 1.0
```

**D. Agrupación en la respuesta**

En `ChatResponse`, añadir `article_tree`:

```python
class CitationGroup(BaseModel):
    parent_code: str
    parent_title: str
    articles: list[Citation]  # parent + children ordenados
```

Esto permite al frontend mostrar las citas agrupadas por artículo padre, mucho más legible.

**E. Filtro de profundidad en el frontend**

En `ChatInterface.tsx`, añadir un filtro adicional junto a year/section:

```
Depth: [Auto] [Overview] [Details]
```
- Overview → Level 1+2 preferido
- Details → Level 2+3 preferido
- Auto → comportamiento actual

**Implementación estimada:** 2-3 días. Prioridad: MEDIA-ALTA.

---

## MEJORA 3 — Validación Temporal de Artículos

### Problema
Cuando el sistema encuentra artículo `3.1` de 2023, no sabe si ese artículo:
- Sigue igual en 2026 ✅
- Fue modificado en 2025 ⚠️
- Fue eliminado en 2024 ❌

El LLM puede presentar una regla obsoleta como vigente, lo cual es el error más grave posible en este dominio.

### Arquitectura propuesta

**A. Tabla de diff entre versiones `article_diffs`**

```sql
CREATE TABLE article_diffs (
    id SERIAL PRIMARY KEY,
    article_code VARCHAR(50) NOT NULL,
    section VARCHAR(50) NOT NULL,
    year_from INTEGER NOT NULL,
    year_to INTEGER NOT NULL,
    issue_from INTEGER NOT NULL,
    issue_to INTEGER NOT NULL,
    similarity FLOAT,          -- embedding cosine similarity (0-1)
    change_type VARCHAR(20),   -- 'unchanged', 'minor', 'major', 'added', 'removed'
    computed_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(article_code, section, year_from, year_to)
);
```

**B. Script de cálculo de diffs `scripts/compute_diffs.py`**

```python
async def compute_article_diffs():
    """
    Para cada artículo, compara su embedding con el mismo código en otros años.
    Clasifica el cambio por similitud coseno:
      > 0.98 → 'unchanged'
      0.90–0.98 → 'minor'  
      0.70–0.90 → 'major'
      Existe en A pero no en B → 'removed'
      Existe en B pero no en A → 'added'
    """
    # Ejecutar una sola vez al indexar nuevos docs, y periódicamente
```

Usar los embeddings ya almacenados en `article_embeddings` — no hace falta re-embedear.

**C. Enriquecimiento en el retriever**

En `_enrich_with_parent()`, añadir también `validity_context`:

```python
async def _get_validity_context(self, article_code, section, year):
    """
    Si hay artículos del mismo código en años posteriores:
    - Devuelve el tipo de cambio más relevante
    - Devuelve el año más reciente disponible
    """
    # SELECT * FROM article_diffs WHERE article_code=? AND section=? 
    #   AND year_from=? ORDER BY year_to DESC LIMIT 1
    return ValidityContext(
        latest_year=2026,
        change_type='minor',
        still_valid=True
    )
```

**D. Contexto de validez en el prompt del LLM**

En `_build_context()`, añadir nota de validez por artículo:

```
Article 3.1 (Technical, 2023, Issue 2):
[VALIDITY: Minor changes in 2024/2025/2026 — verify latest issue]
...content...

Article 22.1 (Sporting, 2025, Issue 4):
[VALIDITY: Identical in 2026 — still current]
...content...
```

**E. Badge de vigencia en `CitationCard.tsx`**

```tsx
// En CitationCard
const validityBadge = {
    'unchanged': { label: 'Current', color: '#22c55e' },
    'minor':     { label: 'Minor updates', color: '#f59e0b' },
    'major':     { label: 'Significant changes', color: '#ef4444' },
    'removed':   { label: 'May be obsolete', color: '#6b7280' },
};
```

**F. Lógica de priorización en búsqueda sin filtro de año**

Cuando el usuario no especifica año, el retriever debería preferir el año más reciente del mismo artículo, no devolver el mismo artículo en múltiples años. La deduplicación actual ya hace esto por (code, section, year) + max(issue), pero podría extenderse a "entre años, preferir el más reciente" como opción.

**Implementación estimada:** 3-4 días. Prioridad: ALTA (calidad de respuesta crítica).

---

## MEJORA 4 — Comparación IA entre Años (upgrade de la página Compare)

### Problema
La página `/compare` actual muestra los textos de dos años en paralelo, pero no explica qué cambió ni por qué importa.

### Propuesta

**Nuevo endpoint `POST /api/compare/explain`:**

```python
@router.post("/api/compare/explain")
async def explain_diff(article_code: str, year_a: int, year_b: int):
    """
    Dado un artículo en dos años, genera:
    - Resumen de los cambios principales
    - Si el cambio es técnico o editorial
    - Impacto práctico para los equipos
    """
    # Recuperar ambas versiones de la DB
    # Una sola llamada LLM con prompt específico de diff
    # Cachear el resultado en article_diffs.explanation
```

**En el frontend:**

Añadir botón "Explain changes" en la vista diff → muestra el análisis generado por el LLM debajo de los dos paneles.

**Implementación estimada:** 1-2 días. Prioridad: MEDIA.

---

## MEJORA 5 — Confianza y Transparencia del Retriever

### Problema
El sistema no indica cuándo tiene poca confianza. Una query sobre una regla muy específica que no aparece bien en la DB devuelve igual una respuesta.

### Propuesta

**A. Score de confianza en `ChatResponse`**

```python
class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    confidence: float  # 0-1, calculado del top RRF score normalizado
    confidence_reason: str  # "High: 8 highly relevant articles found"
                           # "Low: best match has only 62% relevance"
```

**B. Indicador visual en el frontend**

Barra de confianza debajo del loading indicator — solo visible si < 0.7:
```
⚠️ Low confidence — this topic may not be well covered in the indexed regulations
```

**C. "No sé" cuando aplica**

Cuando `confidence < 0.5`, el LLM recibe instrucción adicional:
```
Note: Retrieved articles have low relevance scores. 
If you cannot answer with confidence from these sources, say so explicitly 
rather than extrapolating.
```

**Implementación estimada:** 1 día. Prioridad: MEDIA.

---

## MEJORA 6 — Ingestion Incremental Automática desde UI

### Problema
Añadir un nuevo PDF de reglamento requiere acceso al servidor o conocimiento técnico.

### Propuesta

La página `/upload` ya existe. Extenderla para que al detectar el año/sección/issue del PDF nuevo, ejecute solo el delta (artículos que no existen ya en la DB) y muestre progreso en tiempo real via Server-Sent Events.

```
[Upload PDF] → parse → show preview (X articles found, Y already in DB) 
             → confirm → embed → insert → done
```

**Implementación estimada:** 2 días. Prioridad: BAJA (solo útil si la FIA scraper no cubre todos los docs).

---

## Orden de Implementación Recomendado

| # | Mejora | Impacto | Esfuerzo | Prioridad |
|---|--------|---------|----------|-----------|
| 1 | Validación temporal (Mejora 3) | Alto | 3-4d | 🔴 Primero |
| 2 | Monitor FIA (Mejora 1) | Alto | 3-4d | 🔴 Segundo |
| 3 | Búsqueda jerárquica (Mejora 2) | Medio-Alto | 2-3d | 🟡 Tercero |
| 4 | Compare con IA (Mejora 4) | Medio | 1-2d | 🟡 Cuarto |
| 5 | Confianza del retriever (Mejora 5) | Medio | 1d | 🟢 Quinto |
| 6 | Upload incremental (Mejora 6) | Bajo | 2d | 🟢 Sexto |

**Justificación del orden:**
- La validación temporal es urgente porque ahora tenemos 4 años y una respuesta de 2023 sin contexto de vigencia puede confundir al usuario.
- El monitor FIA es el que más valor de portfolio tiene (scraping + RAG + auto-update = sistema completo).
- La búsqueda jerárquica mejora la calidad de cada respuesta individual.
- El resto son mejoras incrementales de UX y confianza.

---

## Consideraciones Técnicas Globales

### Límites del free tier

Con 16,182 artículos y crecimiento proyectado:
- **Supabase:** ~45MB usados de 500MB — hay margen para los diffs y sync_log
- **Render:** El modelo de embeddings local consume ~400MB RAM. Añadir lógica de diffs en memoria no debería ser problema si se procesa en streaming.
- **OpenRouter:** Los endpoints nuevos (`compare/explain`, validación de vigencia en el agentic loop) añaden ~1-2 llamadas LLM por query. Evaluar si merece la pena cachear los explain diffs.

### Caching de diffs

Los diffs entre artículos son estáticos una vez calculados. Cachearlos en `article_diffs` evita recalcular en cada query. El script `compute_diffs.py` se ejecuta una vez al indexar nuevos docs, no en tiempo real.

### Testing

Antes de cada mejora, añadir al eval framework (`backend/scripts/run_eval.py`) nuevos casos de prueba que validen específicamente:
- Para Mejora 3: queries donde la respuesta correcta requiere reconocer que una regla cambió
- Para Mejora 2: queries que necesitan context de artículo padre para tener sentido
- Para Mejora 1: verificar que tras auto-ingestion, el sistema responde correctamente sobre el nuevo issue
