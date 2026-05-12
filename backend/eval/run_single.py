#!/usr/bin/env python3
"""Run a single eval query by index. Appends result to eval_baseline.json."""
import json, sys, time
from pathlib import Path

import httpx

URL = "https://f1-regulations-engine.onrender.com"
TEST_SET = Path(__file__).parent / "test_set.json"
RESULTS_FILE = Path(__file__).parent / "eval_baseline.json"


def _normalize_code(code: str) -> str:
    """Strip single-letter section prefix from article codes.

    Technical regs use 'C' prefix (e.g. C4.1 → 4.1), Sporting/Financial
    may use other prefixes. This lets expected codes like '4.1' match
    retrieved codes like 'C4.1'.
    """
    if len(code) > 1 and code[0].isalpha() and not code[1].isalpha():
        return code[1:]
    return code


def evaluate_query(q: dict) -> dict:
    expected = set(q["expected_articles"])
    key_facts = q.get("key_facts", [])
    t0 = time.monotonic()
    try:
        r = httpx.post(f"{URL}/api/chat", json={"query": q["query"]}, timeout=120)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        elapsed = int((time.monotonic() - t0) * 1000)
        return {"id": q["id"], "diff": q["difficulty"], "section": q["expected_section"],
                "P": 0, "R": 0, "F": 0, "ms": elapsed, "error": str(e)}

    elapsed = int((time.monotonic() - t0) * 1000)
    citations = data.get("citations", [])
    retrieved_raw = set()
    for c in citations:
        code = c.get("article_code", "")
        retrieved_raw.add(code)
        parts = code.split(".")
        if len(parts) > 1:
            retrieved_raw.add(parts[0])

    # Normalize both sets for comparison (strip section prefix)
    norm_expected = {_normalize_code(c) for c in expected}
    norm_retrieved = {_normalize_code(c) for c in retrieved_raw}

    prec = len(norm_expected & norm_retrieved) / len(norm_retrieved) if norm_retrieved else 0
    rec = len(norm_expected & norm_retrieved) / len(norm_expected) if norm_expected else 1
    answer = data.get("answer", "").lower()
    ff = sum(1 for f in key_facts if f.lower() in answer)
    fa = ff / len(key_facts) if key_facts else 1
    steps = len(data.get("research_steps", []))

    return {
        "id": q["id"], "diff": q["difficulty"], "section": q["expected_section"],
        "P": round(prec, 4), "R": round(rec, 4), "F": round(fa, 4),
        "ms": elapsed, "steps": steps,
        "expected": sorted(expected), "retrieved": sorted(retrieved_raw),
    }


def main():
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0

    with open(TEST_SET) as f:
        queries = json.load(f)["queries"]

    if idx >= len(queries):
        print(f"Index {idx} out of range (max {len(queries)-1})")
        sys.exit(1)

    # Load existing results
    if RESULTS_FILE.exists():
        with open(RESULTS_FILE) as f:
            existing = json.load(f)
    else:
        existing = {"timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "results": []}

    # S