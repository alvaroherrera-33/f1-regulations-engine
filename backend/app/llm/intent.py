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
    # Article / regulation vocabulary (EN + ES + FR + DE + IT)
    r"\b(article|articulo|regulation|reglamento|rule|norma|clause|clausula|section|seccion|appendix|apendice)\b",
    r"\b(règlement|règle|article|annexe|section|clause)\b",           # FR
    r"\b(Reglement|Vorschrift|Artikel|Anhang|Abschnitt|Klausel)\b",   # DE
    r"\b(regolamento|norma|articolo|appendice|sezione|clausola)\b",   # IT
    # Technical -- weight, dimensions (EN + ES + FR + DE + IT)
    r"\b(weight|peso|minimo|minimum|maximum|maximo|dimension|medida)\b",
    r"\b(poids|dimensions?|mesure|minimum|maximum)\b",                # FR
    r"\b(Gewicht|Mindest|Höchst|Maß|Dimension)\b",                    # DE
    r"\b(peso|dimensione|misura|minimo|massimo)\b",                   # IT
    # Technical -- aerodynamics / bodywork (EN + ES + FR + DE + IT)
    r"\b(aerodyn|aero\b|wing|ala\b|floor\b|suelo|diffuser|difusor|bodywork|carroceria|fairing)\b",
    r"\b(aileron|fond\s*plat|diffuseur|carrosserie|plancher)\b",      # FR
    r"\b(Flügel|Boden|Diffusor|Karosserie|Verkleidung)\b",            # DE
    r"\b(ala\b|fondo\b|diffusore|carrozzeria|deflettore)\b",          # IT
    # Technical -- powertrain (EN + ES + FR + DE + IT)
    r"\b(engine|motor|power\s*unit|pu\b|mgu[-\s]?[kh]|ers\b|drs\b|kers\b|turbocharg|compressor|intercool)\b",
    r"\b(moteur|groupe\s*propulseur|turbo|compresseur)\b",            # FR
    r"\b(Motor|Antriebseinheit|Turbolader|Kompressor)\b",             # DE
    r"\b(motore|unità\s*propulsiva|turbocompressore)\b",              # IT
    # Technical -- tyres, brakes, suspension (EN + ES + FR + DE + IT)
    r"\b(fuel|combustible|tyre|tire|neumatico|rim|rueda|brake|freno|suspension|damper)\b",
    r"\b(pneumatique|pneu|carburant|frein|jante|suspension)\b",       # FR
    r"\b(Reifen|Kraftstoff|Bremse|Felge|Fahrwerk|Dämpfer)\b",         # DE
    r"\b(pneumatico|gomma|carburante|freno|cerchio|sospensione)\b",   # IT
    # Technical -- chassis / safety structures
    r"\b(chassis|monocoque|safety\s*cell|cockpit|halo|survival\s*cell|roll\s*bar)\b",
    r"\b(châssis|cellule\s*de\s*survie|arceau)\b",                    # FR
    r"\b(Chassis|Überrollbügel|Sicherheitszelle)\b",                  # DE
    r"\b(telaio|cellula\s*di\s*sopravvivenza|rollbar)\b",             # IT
    # Technical -- specific parts
    r"\b(power\s*unit|front\s*wing|rear\s*wing|side\s*pod|floor\s*edge|plank)\b",
    # Sporting (EN + ES + FR + DE + IT)
    r"\b(qualifying|clasificacion|parrilla|pit\s*stop|pit\s*lane|safety\s*car|vsc\b|virtual\s*safety)\b",
    r"\b(qualification|voiture\s*de\s*sécurité|course|départ|arrêt\s*au\s*stand)\b",  # FR
    r"\b(Qualifikation|Sicherheitsauto|Rennen|Start|Boxenstopp)\b",   # DE
    r"\b(qualifica|macchina\s*di\s*sicurezza|gara|partenza|pit\s*stop)\b",  # IT
    r"\b(race\s*(director|steward|procedure|start)|steward|comisario)\b",
    r"\b(points|puntos|penalty|penalizacion|disqualif|descalif|drive\s*through)\b",
    r"\b(points?|pénalité|disqualification|exclusion)\b",             # FR
    r"\b(Punkte|Strafe|Disqualifikation|Ausschluss)\b",               # DE
    r"\b(punti|penalità|squalifica|esclusione)\b",                    # IT
    r"\b(sprint|parc\s*ferme)\b",
    # Financial (EN + ES + FR + DE + IT)
    r"\b(cost\s*cap|budget\s*cap|presupuesto|financial\s*regulation|spending|audit)\b",
    r"\b(plafond\s*budgétaire|budget|dépenses|audit|règlement\s*financier)\b",  # FR
    r"\b(Budgetobergrenze|Haushalt|Ausgaben|Prüfung|Finanzreglement)\b",        # DE
    r"\b(tetto\s*di\s*spesa|budget|spese|revisione|regolamento\s*finanziario)\b",  # IT
    # F1 / FIA universe
    r"\b(f1|formula[\s-]*1|formula\s*one|fia\b|grand\s*prix\b)\b",
    r"\b(constructor|driver|piloto|equipo)\b",
    # Year references (2023-2030)
    r"\b(202[3-9]|2030)\b",
    # Article code patterns: "3.7", "C3.14", "Art. 5"
    r"\b[A-Z]?\d+\.\d+\b",
    r"\bArt(?:icle|\.)\s*\d+",
    # Change / comparison questions (EN + ES + FR + DE + IT)
    r"\b(change|cambio|cambiar|differ|diferencia|update|actualiz|new\s+rule|nueva\s+norma)\b",
    r"\b(changement|modification|différence|mise\s*à\s*jour|nouvelle\s*règle)\b",  # FR
    r"\b(Änderung|Unterschied|Aktualisierung|neue\s*Regel)\b",                      # DE
    r"\b(cambiamento|modifica|differenza|aggiornamento|nuova\s*norma)\b",            # IT
]

# ---------------------------------------------------------------------------
# Patterns that flag CONVERSATIONAL intent
# Only checked if NO regulation keyword matched.
# ---------------------------------------------------------------------------
_CONVERSATIONAL_PATTERNS: list[str] = [
    # Greetings (EN + ES + FR + DE + IT)
    r"^(hola|hello|hi|hey|ey|good\s+(morning|afternoon|evening|night|day)|buenos\s+dias?|buenas\s+(tardes?|noches?)|salut|ciao)\b",
    r"^(bonjour|bonsoir|bonne\s+(nuit|journée|soirée))\b",           # FR
    r"^(guten\s+(tag|morgen|abend|nacht)|hallo|servus)\b",            # DE
    r"^(buongiorno|buonasera|buonanotte|salve)\b",                    # IT
    # Farewells (EN + ES + FR + DE + IT)
    r"^(bye|goodbye|adios|hasta\s+(luego|pronto|manana|la\s+vista)|see\s+you|ciao|chao)\b",
    r"^(au\s*revoir|à\s*bientôt|bonne\s*journée|bonne\s*soirée)\b",  # FR
    r"^(auf\s*wiedersehen|tschüss|bis\s*(bald|später|dann))\b",       # DE
    r"^(arrivederci|ciao|a\s*presto|buona\s*giornata)\b",             # IT
    # Thanks (EN + ES + FR + DE + IT)
    r"^(gracias|thanks?(\s+a\s+lot|\s+so\s+much)?|thank\s+you(\s+so\s+much)?|muchas?\s+gracias|de\s+nada|no\s+worries)\b",
    r"^(merci(\s+beaucoup)?|de\s+rien)\b",                            # FR
    r"^(danke(\s+schön|\s+sehr)?|bitte)\b",                           # DE
    r"^(grazie(\s+mille)?|prego)\b",                                  # IT
    # Single acknowledgement word (exact, optional trailing punctuation)
    r"^(ok|okay|okey|vale|entendido|entiendo|understood|got\s+it|perfecto?|genial|great|cool|nice|super|np|makes?\s+sense)\s*[.!]?\s*$",
    # Combined acknowledgements: "vale, entendido" / "ok, perfecto" / "entendido, gracias"
    r"^(ok|okay|okey|vale|entendido|entiendo|understood|got\s+it|perfecto?|genial|great|cool|nice)\b[,.\s]+\s*(ok|okay|okey|vale|entendido|entiendo|understood|gracias|thanks?|perfecto?|genial|great|cool|nice)?\s*[.!]?\s*$",
    # Identity / capability questions about the bot
    r"(quien\s+eres|who\s+are\s+you|que\s+(eres|puedes|haces)|what\s+are\s+you|what\s+can\s+you\s+do|how\s+can\s+you\s+help)",
    # Capability / meta questions ("what topics/subjects can you answer/cover/help with")
    r"what\s+(topics|subjects|kinds?|areas|things)\b.*\b(answer|help|cover|about|do|know)",
    r"what\s+(can|do)\s+you\s+(answer|help|tell|cover|know|do)\b",
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
