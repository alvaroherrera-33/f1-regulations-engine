"""Local intent detection -- zero LLM calls, zero cost, zero latency.

Classifies a user query as REGULATIONS (should search the DB) or
CONVERSATIONAL (greeting / chitchat / bot question).

Strategy
--------
1. If any F1/regulation keyword is present -> REGULATIONS (checked first).
2. If any conversational pattern matches -> CONVERSATIONAL.
3. Default -> REGULATIONS (safer to search and find nothing than to
   silently drop a real regulation query).
"""

import re
from typing import Literal

# ---------------------------------------------------------------------------
# Patterns that immediately flag REGULATIONS intent
# Checked FIRST -- regulation keywords override everything else.
# ---------------------------------------------------------------------------
_REGULATION_PATTERNS: list[str] = [
    # Article / regulation vocabulary (EN + ES)
    r"\b(article|articulo|regulation|reglamento|rule|norma|clause|clausula|section|seccion|appendix|apendice)\b",
    # Technical -- weight, dimensions
    r"\b(weight|peso|minimo|minimum|maximum|maximo|dimension|medida)\b",
    # Technical -- aerodynamics / bodywork
    r"\b(aerodyn|aero\b|wing|ala\b|floor\b|suelo|diffuser|difusor|bodywork|carroceria|fairing)\b",
    # Technical -- powertrain
    r"\b(engine|motor|power\s*unit|pu\b|mgu[-\s]?[kh]|ers\b|drs\b|kers\b|turbocharg|compressor|intercool)\b",
    # Technical -- tyres, brakes, suspension
    r"\b(fuel|combustible|tyre|tire|neumatico|rim|rueda|brake|freno|suspension|damper)\b",
    # Technical -- chassis / safety structures
    r"\b(chassis|monocoque|safety\s*cell|cockpit|halo|survival\s*cell|roll\s*bar)\b",
    # Technical -- specific parts
    r"\b(power\s*unit|front\s*wing|rear\s*wing|side\s*pod|floor\s*edge|plank)\b",
    # Sporting
    r"\b(qualifying|clasificacion|parrilla|pit\s*stop|pit\s*lane|safety\s*car|vsc\b|virtual\s*safety)\b",
    r"\b(race\s*(director|steward|procedure|start)|steward|comisario)\b",
    r"\b(points|puntos|penalty|penalizacion|disqualif|descalif|drive\s*through)\b",
    r"\b(sprint|parc\s*ferme)\b",
    # Financial
    r"\b(cost\s*cap|budget\s*cap|presupuesto|financial\s*regulation|spending|audit)\b",
    # F1 / FIA universe
    r"\b(f1|formula[\s-]*1|formula\s*one|fia\b|grand\s*prix\b)\b",
    r"\b(constructor|driver|piloto|equipo)\b",
    # Year references (2023-2030)
    r"\b(202[3-9]|2030)\b",
    # Article code patterns: "3.7", "C3.14", "Art. 5"
    r"\b[A-Z]?\d+\.\d+\b",
    r"\bArt(?:icle|\.)\s*\d+",
    # Change / comparison questions
    r"\b(change|cambio|cambiar|differ|diferencia|update|actualiz|new\s+rule|nueva\s+norma)\b",
]

# ---------------------------------------------------------------------------
# Patterns that flag CONVERSATIONAL intent
# Only checked if NO regulation keyword matched.
# ---------------------------------------------------------------------------
_CONVERSATIONAL_PATTERNS: list[str] = [
    # Greetings
    r"^(hola|hello|hi|hey|ey|good\s+(morning|afternoon|evening|night|day)|buenos\s+dias?|buenas\s+(tardes?|noches?)|salut|ciao)\b",
    # Farewells
    r"^(bye|goodbye|adios|hasta\s+(luego|pronto|manana|la\s+vista)|see\s+you|ciao|chao)\b",
    # Thanks
    r"^(gracias|thanks?(\s+a\s+lot|\s+so\s+much)?|thank\s+you(\s+so\s+much)?|muchas?\s+gracias|de\s+nada|no\s+worries)\b",
    # Single acknowledgement word (exact, optional trailing punctuation)
    r"^(ok|okay|okey|vale|entendido|entiendo|understood|got\s+it|perfecto?|genial|great|cool|nice|super|np|makes?\s+sense)\s*[.!]?\s*$",
    # Combined acknowledgements: "vale, entendido" / "ok, perfecto" / "entendido, gracias"
    r"^(ok|okay|okey|vale|entendido|entiendo|understood|got\s+it|perfecto?|genial|great|cool|nice)\b[,.\s]+\s*(ok|okay|okey|vale|entendido|entiendo|understood|gracias|thanks?|perfecto?|genial|great|cool|nice)?\s*[.!]?\s*$",
    # Identity / capability questions about the bot
    r"(quien\s+eres|who\s+are\s+you|que\s+(eres|puedes|haces)|what\s+are\s+you|what\s+can\s+you\s+do|how\s+can\s+you\s+help)",
    # Pure help request (without technical context)
    r"^(help|ayuda|ayudame|socorro|assist\s+me)\s*[!?.]?\s*$",
    # Filler / conversation continuers
    r"^(sure|claro|por\s+supuesto|of\s+course|no\s+problem|sin\s+problema|adelante|go\s+ahead)\s*[.!]?\s*$",
    # Compliments / positive feedback
    r"^(great\s+(job|work|answer)|buen\s+(trabajo|respuesta)|excellent|excelente|muy\s+bien|well\s+done)\s*[.!]?\s*$",
]

# Compile once at import time
_REGULATION_RE: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in _REGULATION_PATTERNS
]
_CONVERSATIONAL_RE: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in _CONVERSATIONAL_PATTERNS
]


def detect_intent_local(query: str) -> Literal["REGULATIONS", "CONVERSATIONAL"]:
    """Classify query intent locally -- no LLM, no network, instant.

    Returns 'REGULATIONS' or 'CONVERSATIONAL'.
    """
    query = query.strip()

    # Very short or empty input -> conversational
    if len(query) < 3:
        return "CONVERSATIONAL"

    # Pass 1: regulation keywords (highest priority -- checked first)
    for pattern in _REGULATION_RE:
        if pattern.search(query):
            return "REGULATIONS"

    # Pass 2: conversational patterns
    for pattern in _CONVERSATIONAL_RE:
        if pattern.search(query):
            return "CONVERSATIONAL"

    # Default: REGULATIONS
    return "REGULATIONS"
