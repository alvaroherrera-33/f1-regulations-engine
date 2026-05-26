# Plan de Mejora de Calidad — F1 Regulations RAG Engine

> Creado: 2026-05-07  
> Basado en: inspección real de la base de datos de producción (Supabase)  
> Estado de la DB al análisis: 3,982 artículos indexados, 14 issues, 100% con embeddings

---

## Resumen Ejecutivo

Tras una investigación profunda de la base de datos de producción, se han identificado **4 categorías de problemas** que afectan directamente la calidad de las respuestas:

1. **Datos sucios** — artículos mal parseados que contaminan los resultados de búsqueda
2. **Artículos truncados** — contenido cortado a mitad de frase porque el parser no filtra cabeceras/pies de página
3. **Estructura rota** — 45 artículos huérfanos sin padre en la DB (afecta al enrichment del retriever)
4. **Rendimiento** — cold start de 40s en Render free tier (única query registrada en logs)

Los problemas 1-3 son bugs de parseo que requieren fixes en `pdf_parser.py` + re-ingestión. El problema 4 requiere una solución de keep-alive.

---

## DATOS DE LA DB (Baseline)

| Section | Year | Issue | Total | < 50 chars | > 2000 chars | Avg len |
|---------|------|-------|-------|-----------|-------------|---------|
| Financial | 2025 | 23 | 131 | 0 | 4 | 484 |
| Financial | 2025 | 24 | 131 | 0 | 4 | 473 |
| Financial | 2026 | 2 | 53 | **9** | 4 | 753 |
| Financial | 2026 | 3 | 73 | **9** | 5 | 698 |
| Financial | 2026 | 4 | 76 | **10** | 5 | 703 |
| Financial | 2026 | 7 | 213 | 2 | 3 | 373 |
| Sporting | 2025 | 4 | 427 | **46** | 6 | 467 |
| Sporting | 2025 | 5 | 422 | **48** | 11 | 484 |
| Sporting | 2026 | 4 | 157 | **15** | 6 | 565 |
| Technical | 2025 | 2 | 325 | 10 | 8 | 523 |
| Technical | 2026 | 11-15 | ~494 avg | **31** avg | 10 avg | 453 |

---

## BUG 1 — Entradas de Tabla de Contenidos como Artículos (CRÍTICO)

### Diagnóstico

Los PDFs de Financial regulations tienen **apéndices** con tabla de contenidos propia. El parser los captura como artículos reales:

```
"ARTICLE E1: GENERAL PRINCIPLES\n3"     → guardado como artículo E1, content = 32 chars
"ARTICLE D4: THE COST CAP\n10"          → guardado como artículo D4, content = 27 chars
"49\nAPPENDIX D1: DEFINITIONS..."       → guardado como artículo 49, content = 47 chars
```

Estos artículos contienen únicamente el título + número de página. Si el RAG los recupera, devuelve contenido vacío e inútil al LLM.

**Afectados:** Financial 2026 issues 2, 3, 4 (≈28 artículos basura por issue)

### Fix

**Archivo:** `backend/ingestion/pdf_parser.py` → método `_save_article()`

Añadir filtro adicional: si el contenido es `"ARTICLE X: TITLE\nNUMBER"` donde NUMBER es un entero de 1-3 dígitos (número de página), descartar.

```python
# En _save_article(), después del check de MIN_CONTENT_LENGTH:
import re
# Detectar patrón: título de artículo + solo número de página
_TOC_ENTRY = re.compile(r'^ARTICLE\s+\S+:.*\n\d{1,3}\s*$', re.DOTALL)
if _TOC_ENTRY.match(content.strip()):
    return  # Es una entrada de TOC, no un artículo real
```

También añadir filtro para entradas numéricas puras (ya implementado parcialmente):

```python
# Descartar artículos cuyo contenido sea solo "NNN\nTexto corto" (= TOC line)
lines = content.strip().split('\n')
if len(lines) <= 2 and lines[0].strip().isdigit():
    return
```

---

## BUG 2 — Cabeceras/Pies de Página en el Contenido de Artículos (ALTO)

### Diagnóstico

El parser no distingue entre:
- **Texto de regulación** — el contenido real del artículo
- **Cabeceras de página** — e.g., `SECTION C: TECHNICAL REGULATIONS` (aparece en cada página)
- **Pies de página** — e.g., `Formula 1 Financial Regulations\n37` (nombre del doc + número de pág.)

Ejemplos de artículos truncados / con ruido al final:

```
Artículo 30 (Sporting 2025 i5, 5024 chars):
  termina con: "...laws require the maintaining of health and safety records or the engagement with"

Artículo 26 (Financial 2025 i23, 3219 chars):
  termina con: "...ordance with the International Sporting Code.\nFormula 1 Financial Regulations\n33"

Artículo 0 (Technical 2026 i11, 3520 chars):
  termina con: "...necessary for its safe and reliable operation.\nSECTION C: TECHNICAL REGULATIONS"

Artículo 2 (Sporting 2025 i5, 3394 chars):
  termina con: "...etitor or any external entity working on behalf of the Competitor or for its own"
  (cortado a mitad de frase — el parser no continúa en la siguiente página)
```

### Causa raíz

El parser procesa el texto página por página. Cuando un artículo abarca múltiples páginas, la cabecera de la nueva página (`SECTION C: TECHNICAL REGULATIONS`) interrumpe el artículo actual. El parser o bien lo ignora (si no hace match) o lo añade al body (contaminando el contenido).

Adicionalmente, los pies de página (`Formula 1 Financial Regulations\n37`) son líneas que no hacen match con ningún patrón y se acumulan en el artículo corriente.

### Fix

**Archivo:** `backend/ingestion/pdf_parser.py`

**Paso 1:** Añadir patrón para detectar y descartar cabeceras/pies de página:

```python
# Patrones de ruido a filtrar (no añadir a current_text)
PAGE_NOISE_PATTERNS = [
    re.compile(r'^SECTION\s+[A-Z]\s*:\s*\w.*REGULATIONS$', re.IGNORECASE),
    re.compile(r'^Formula\s+1\s+\w.*Regulations$', re.IGNORECASE),
    re.compile(r'^FIA\s+Formula\s+One\s+', re.IGNORECASE),
    re.compile(r'^\d{1,3}\s*$'),  # número de página solo
]

def _is_page_noise(self, line: str) -> bool:
    return any(p.match(line.strip()) for p in self.PAGE_NOISE_PATTERNS)
```

**Paso 2:** Usar `_is_page_noise()` en el loop principal antes de añadir al `current_text`:

```python
else:
    if current_article and not self._is_page_noise(line):
        current_text.append(line)
```

**Paso 3:** Para artículos que se cortan a mitad de frase (cross-page), el texto continúa en la página siguiente pero el parser reinicia el contexto. La solución es procesar el PDF completo de forma continua (concatenar todas las páginas antes de iterar líneas), no página a página:

```python
def parse(self) -> List[ParsedArticle]:
    # Extraer TODO el texto del documento como una sola cadena
    full_text = ""
    for page_num in range(len(self.doc)):
        page = self.doc[page_num]
        full_text += page.get_text("text") + "\n"
    
    lines = full_text.split('\n')
    # ... resto del loop igual
```

Este cambio solo es necesario para PDFs donde los artículos se parten entre páginas. El impacto es significativo para Sporting 2025 (artículos de 5000+ chars que se cortan).

---

## BUG 3 — Artículos Huérfanos: Parent Articles Faltantes (MEDIO)

### Diagnóstico

45 artículos tienen `parent_code` que apunta a un artículo que no existe en la DB para el mismo `(section, year, issue)`. Ejemplo:

```
Artículo 2.1  Financial 2025 issue 23  →  parent_code = "2"  (no existe en DB)
Artículo 2.2  Financial 2025 issue 23  →  parent_code = "2"  (no existe en DB)
...
Artículo 2.11 Financial 2025 issue 23  →  parent_code = "2"  (no existe en DB)
```

Esto afecta directamente al **parent enrichment** del retriever: cuando el retriever recupera el artículo 2.1 y trata de enriquecer con el contexto del artículo padre "2", no encuentra nada y devuelve solo el sub-artículo sin el contexto superior.

### Causa raíz probable

El artículo padre "2" en los Financial Regulations tiene como header:
```
ARTICLE 2: COST CAP OBLIGATIONS
```
Esto es capturado por `SECTION_HEADER_PATTERN` y guardado correctamente. Sin embargo, puede que la condición `if len(content) <= len(code) + 5` en `_save_article()` lo esté descartando si el artículo padre tiene muy poco contenido propio (e.g., solo el título antes de que empiece el 2.1).

### Fix

**Opción A (conservadora):** Relajar el filtro de contenido mínimo para artículos padre: no descartar artículos nivel 1 con título aunque tengan poco contenido.

```python
def _save_article(self, article_data, text_lines, articles_dict):
    content = '\n'.join(text_lines).strip()
    code = article_data['article_code']
    
    # Para artículos nivel 1 con título: guardar aunque el content sea solo el header
    is_parent = article_data['level'] == 1 and article_data.get('title')
    min_len = len(code) + 5 if not is_parent else len(code)
    
    if len(content) <= min_len:
        return
```

**Opción B (robusta):** Después de parsear todos los artículos, hacer un post-proceso que cree artículos padre sintéticos para cualquier `parent_code` referenciado que no tenga entrada propia:

```python
def _fill_missing_parents(self, articles_dict: Dict) -> None:
    """Create stub parent articles for any referenced parent_code that doesn't exist."""
    for code, article in list(articles_dict.items()):
        if article.parent_code and article.parent_code not in articles_dict:
            stub_content = f"Article {article.parent_code} (parent section)"
            articles_dict[article.parent_code] = ParsedArticle(
                article_code=article.parent_code,
                title=f"Article {article.parent_code}",
                content=stub_content,
                level=article.level - 1,
                parent_code=None
            )
```

Se recomienda **Opción A** para investigar primero y **Opción B** como fallback.

---

## BUG 4 — Artículo Código "0" y Ruido del Preámbulo (BAJO)

### Diagnóstico

En Technical 2026 aparece `article_code = "0"` con contenido mezclado del preámbulo del documento:
- Contiene texto de copyright, definiciones generales, y termina con `"SECTION C: TECHNICAL REGULATIONS"`
- Este "artículo" no corresponde a ninguna regulación real — es el texto introductorio del PDF

### Fix

Filtrar artículos con código "0" explícitamente, o aplicar el filtro de `major.isdigit()` también a códigos con valor "0":

```python
# En parse(), extender el filtro existente:
if level == 1 and major.isdigit():
    # Siempre skip para códigos 0, o skip si no hay título
    if major == "0" or not title:
        if current_article:
            current_text.append(line)
        continue
```

---

## MEJORA 5 — Cobertura de Regulaciones: Issues Faltantes (MEDIO)

### Diagnóstico

Estado actual de cobertura por sección:

| Section | Years | Issues en DB |
|---------|-------|-------------|
| Financial | 2025 | Issues 23, 24 |
| Financial | 2026 | Issues 2, 3, 4, 7 |
| Sporting | 2025 | Issues 4, 5 |
| Sporting | 2026 | Issue 4 |
| Technical | 2025 | Issue 2 **solo** |
| Technical | 2026 | Issues 11, 12, 14, 15 |

**Gap crítico:** Technical 2025 solo tiene el issue 2, que es muy antiguo. Los teams usan la versión del issue más reciente disponible. Hay múltiples issues entre el 2 y el estado final de 2025 que no están indexados.

**Gap relevante:** Sporting 2026 solo tiene el issue 4. A medida que avance la temporada habrá nuevos issues.

### Fix

1. Auditar el directorio `archives/` para identificar qué PDFs existen pero no están indexados
2. Re-ejecutar el script de ingestión con los PDFs que faltan
3. Verificar que el sistema de deduplicación por RRF prioriza correctamente el issue más alto

```bash
# Auditoría rápida:
ls archives/ | grep -i technical | grep 2025
# Ver qué issues existen para Technical 2025
```

---

## MEJORA 6 — Rendimiento: Cold Start de 40 Segundos (CRÍTICO para UX)

### Diagnóstico

Query logs muestran la única query registrada en producción:
- Intent: REGULATIONS
- Response time: **40,943 ms** (40 segundos)
- Retrieved count: 8 artículos

El cold start de Render free tier (el servicio "duerme" tras 15 minutos de inactividad) explica completamente esta latencia. Una vez "despertado", las queries siguientes serían ~3-8s.

El problema es que el **primer usuario real** siempre experimenta los 40s, lo cual es inaceptable para un portfolio project que se demuestra en una entrevista.

### Fix: Cron Ping para Keep-Alive

**Opción A (gratis, inmediata):** Usar UptimeRobot o Cron-Job.org para hacer ping al health endpoint cada 10 minutos:

```
https://f1-regulations-engine.onrender.com/health
Intervalo: 10 minutos
```

Esto mantiene el servicio despierto 24/7 sin coste adicional. Es la solución estándar para Render free tier.

**Opción B (elegante):** Crear un endpoint de "warm-up" que pre-cargue el modelo de embeddings al primer ping:

```python
@router.get("/warmup")
async def warmup():
    """Pre-loads embedding model. Called by cron job to prevent cold starts."""
    from app.retrieval.retriever import HybridRetriever
    # El modelo ya se carga en singleton, solo verificamos que está listo
    return {"status": "warm", "model_loaded": True}
```

**Recomendación:** Implementar Opción A inmediatamente (5 minutos de trabajo). Opción B es complementaria.

---

## MEJORA 7 — Calidad de Retrieval: top_k y Threshold (MEDIO)

### Diagnóstico

El retriever usa `top_k=5` por paso del agentic loop (max 3 pasos = 15 artículos posibles). Para preguntas que cruzan múltiples artículos relacionados (e.g., "¿cuál es el proceso completo de homologación de neumáticos?"), puede que 5 artículos por paso no sean suficientes.

El threshold de similaridad coseno es 0.85. Esto puede ser demasiado estricto para preguntas formuladas de forma diferente al texto de las regulaciones.

### Fix

**Ajuste 1:** Incrementar `top_k` a 8 en el agentic loop para queries de REGULATIONS. El coste adicional es mínimo (búsqueda vectorial es barata).

```python
# En chat.py, en el agentic loop:
new_articles = await retrieve_articles(
    db=db,
    query=current_step_query,
    year=query_year,
    section=query_section,
    issue=request.issue,
    top_k=8  # Antes: 5
)
```

**Ajuste 2:** Bajar el threshold de cosine similarity de 0.85 a 0.75 en `retriever.py`. Esto aumenta el recall a costa de un poco de precisión, pero el LLM puede filtrar el ruido.

```python
# En retriever.py:
SIMILARITY_THRESHOLD = 0.75  # Antes: 0.85
```

**Ajuste 3:** Para la búsqueda Full-Text, considerar habilitar `websearch_to_tsquery` en vez de `plainto_tsquery` para queries de múltiples términos. Permite operadores booleanos implícitos.

---

## MEJORA 8 — Feedback del Usuario (BAJO, alto impacto para portfolio)

### Diagnóstico

La tabla `query_logs` tiene la columna `was_helpful BOOLEAN` pero nunca se popula. No hay ningún botón de feedback en el frontend. Esto significa que no hay datos de calidad real más allá del retrieval count.

### Fix

**Backend:** Añadir endpoint `POST /api/chat/feedback`:

```python
@router.post("/chat/feedback")
async def submit_feedback(
    query_id: int,
    was_helpful: bool,
    db: AsyncSession = Depends(get_db)
):
    await db.execute(
        text("UPDATE query_logs SET was_helpful = :helpful WHERE id = :id"),
        {"helpful": was_helpful, "id": query_id}
    )
    await db.commit()
    return {"status": "ok"}
```

**Modelo:** Incluir `query_id` en `ChatResponse` para que el frontend pueda enviar feedback.

**Frontend:** Añadir botones 👍 / 👎 debajo de cada respuesta en `ChatInterface.tsx`.

**Impacto portfolio:** Poder mostrar en una entrevista "tenemos X queries con feedback positivo" es muy llamativo.

---

## MEJORA 9 — Monitoring Dashboard (BAJO)

### Diagnóstico

Actualmente los logs están en Supabase pero no hay ninguna vista agregada de métricas de calidad. Para un portfolio project, poder mostrar un dashboard de uso real es muy valorado.

### Fix

Crear un endpoint `GET /api/stats` que devuelva métricas de uso:

```python
@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    result = await db.execute(text("""
        SELECT 
            COUNT(*) as total_queries,
            COUNT(CASE WHEN intent = 'REGULATIONS' THEN 1 END) as regulation_queries,
            COUNT(CASE WHEN error_occurred THEN 1 END) as errors,
            ROUND(AVG(response_time_ms)) as avg_response_ms,
            COUNT(CASE WHEN was_helpful = true THEN 1 END) as positive_feedback,
            MAX(created_at) as last_query_at
        FROM query_logs
    """))
    return dict(result.fetchone())
```

Añadir una página `/stats` simple en el frontend con estas métricas.

---

## PLAN DE IMPLEMENTACIÓN (Orden Recomendado)

### Sprint 1 — Fix de Datos (2-3 horas)
> Impacto: eliminar ~200 artículos basura, recuperar artículos truncados

| # | Tarea | Archivo | Dificultad |
|---|-------|---------|-----------|
| 1a | Filtro TOC appendix entries | `pdf_parser.py` → `_save_article()` | Fácil |
| 1b | Filtro page headers/footers | `pdf_parser.py` → `parse()` | Fácil |
| 1c | Parse texto completo (no por página) | `pdf_parser.py` → `parse()` | Medio |
| 1d | Fix artículos padre faltantes | `pdf_parser.py` → `_save_article()` | Fácil |
| 1e | Filtro artículo código "0" | `pdf_parser.py` | Fácil |
| 1f | Re-ingestar todos los PDFs | `scripts/ingest_archives.py` | Trivial |

### Sprint 2 — Rendimiento (30 minutos)
> Impacto: eliminar cold start de 40s para usuarios nuevos

| # | Tarea | Dificultad |
|---|-------|-----------|
| 2a | Configurar UptimeRobot para ping cada 10 min | Trivial |
| 2b | (Opcional) Endpoint `/warmup` | Fácil |

### Sprint 3 — Retrieval Quality (1 hora)
> Impacto: mejora de recall en queries complejas

| # | Tarea | Archivo | Dificultad |
|---|-------|---------|-----------|
| 3a | top_k de 5 → 8 en agentic loop | `chat.py` | Trivial |
| 3b | Threshold 0.85 → 0.75 | `retriever.py` | Trivial |

### Sprint 4 — Feedback y Monitoring (2-3 horas)
> Impacto: datos reales de calidad para portfolio

| # | Tarea | Archivos | Dificultad |
|---|-------|---------|-----------|
| 4a | Endpoint POST /feedback | `routes/chat.py` | Fácil |
| 4b | query_id en ChatResponse | `models.py`, `chat.py` | Fácil |
| 4c | Botones 👍/👎 en frontend | `ChatInterface.tsx` | Medio |
| 4d | Endpoint GET /stats | `routes/` nuevo | Fácil |
| 4e | Página /stats en frontend | `app/stats/page.tsx` | Medio |

### Sprint 5 — Cobertura (1-2 horas)
> Impacto: respuestas más completas para 2025

| # | Tarea | Dificultad |
|---|-------|-----------|
| 5a | Auditar archives/ para issues faltantes de Technical 2025 | Trivial |
| 5b | Ingestar issues adicionales | Trivial |

---

## Impacto Estimado por Fix

| Fix | Artículos afectados | Mejora esperada |
|-----|-------------------|-----------------|
| BUG 1 (TOC entries) | ~80 artículos eliminados | Menos ruido en respuestas sobre Financial appendices |
| BUG 2 (page headers/footers) | ~50 artículos mejorados | Contenido más limpio y completo |
| BUG 3 (orphan parents) | 45 artículos con contexto restaurado | Mejor enrichment en Financial queries |
| BUG 4 (article "0") | 4 artículos eliminados | Menos ruido en Technical queries |
| MEJORA 6 (cold start) | 100% de cold starts | First impression 40s → <3s |
| MEJORA 7 (retrieval tuning) | Todas las queries | +15-20% recall estimado |

---

## Checks de Verificación Post-Fix

Después de cada sprint, verificar en Supabase:

```sql
-- Sprint 1: verificar que desaparecen los artículos cortos
SELECT section, year, COUNT(*) as too_short
FROM articles WHERE LENGTH(content) < 50
GROUP BY section, year;
-- Esperado: 0 filas con artículos basura

-- Sprint 1: verificar que no hay artículos huérfanos en Financial 2025
SELECT COUNT(*) FROM articles a
LEFT JOIN articles p ON a.parent_code = p.article_code 
  AND a.section = p.section AND a.year = p.year AND a.issue = p.issue
WHERE a.parent_code IS NOT NULL AND p.article_code IS NULL;
-- Esperado: 0

-- Sprint 3: verificar query logs después de 5 queries de prueba
SELECT AVG(retrieved_count), AVG(response_time_ms) FROM query_logs
WHERE created_at > NOW() - INTERVAL '1 hour';
-- Esperado: retrieved_count > 5, response_time < 10000ms (en caliente)
```
