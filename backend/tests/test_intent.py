"""Unit tests for local intent detection (no LLM, no DB)."""
import pytest

from app.llm.intent import detect_intent_local

# ---------------------------------------------------------------------------
# REGULATIONS intent
# ---------------------------------------------------------------------------

REGULATION_CASES = [
    # English
    ("What is the minimum car weight in 2026?", "REGULATIONS"),
    ("How many power units are allowed per season?", "REGULATIONS"),
    ("What changed in Article 3.7 for 2025?", "REGULATIONS"),
    ("Tell me about the cost cap", "REGULATIONS"),
    ("front wing dimensions Technical regulations", "REGULATIONS"),
    ("Can a driver use DRS in qualifying?", "REGULATIONS"),
    ("What is the fuel flow limit?", "REGULATIONS"),
    ("parc ferme rules", "REGULATIONS"),
    # French
    ("Quel est le poids minimum de la voiture en 2026?", "REGULATIONS"),
    ("Règlement technique 2025", "REGULATIONS"),
    ("Combien de moteurs par saison?", "REGULATIONS"),
    # German
    ("Was ist das Mindestgewicht des Autos?", "REGULATIONS"),
    ("Reglement 2026 technisch", "REGULATIONS"),
    # Italian
    ("Qual è il peso minimo dell'auto?", "REGULATIONS"),
    ("Regolamento tecnico 2026", "REGULATIONS"),
    # Article codes
    ("What does article 3.7 say?", "REGULATIONS"),
    ("Explain C4.1", "REGULATIONS"),
    # Year references
    ("2026 sporting regulations", "REGULATIONS"),
    ("compare 2024 and 2025 rules", "REGULATIONS"),
]

CONVERSATIONAL_CASES = [
    ("hello", "CONVERSATIONAL"),
    ("hi there", "CONVERSATIONAL"),
    ("bye", "CONVERSATIONAL"),
    ("thanks", "CONVERSATIONAL"),
    ("thank you so much", "CONVERSATIONAL"),
    ("ok", "CONVERSATIONAL"),
    ("okay", "CONVERSATIONAL"),
    ("great job", "CONVERSATIONAL"),
    ("perfect", "CONVERSATIONAL"),
    ("who are you?", "CONVERSATIONAL"),
    ("what can you do?", "CONVERSATIONAL"),
    ("bonjour", "CONVERSATIONAL"),
    ("guten morgen", "CONVERSATIONAL"),
    ("buongiorno", "CONVERSATIONAL"),
    ("merci", "CONVERSATIONAL"),
    ("danke", "CONVERSATIONAL"),
    ("grazie", "CONVERSATIONAL"),
    ("arrivederci", "CONVERSATIONAL"),
    ("sure", "CONVERSATIONAL"),
    ("got it", "CONVERSATIONAL"),
    ("vale, entendido", "CONVERSATIONAL"),
]


@pytest.mark.parametrize("query,expected", REGULATION_CASES)
def test_regulations_intent(query, expected):
    assert detect_intent_local(query) == expected, f"Failed for: {query!r}"


@pytest.mark.parametrize("query,expected", CONVERSATIONAL_CASES)
def test_conversational_intent(query, expected):
    assert detect_intent_local(query) == expected, f"Failed for: {query!r}"


def test_empty_query():
    assert detect_intent_local("") == "CONVERSATIONAL"


def test_very_short_query():
    assert detect_intent_local("hi") == "CONVERSATIONAL"


def test_default_regulations():
    """Unknown queries default to REGULATIONS for safety."""
    assert detect_intent_local("something completely unrelated lalala") == "REGULATIONS"
