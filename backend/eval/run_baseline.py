#!/usr/bin/env python3
"""Run eval queries one at a time, saving results incrementally."""
import json, time, sys
from pathlib import Path

try:
    import httpx
except ImportError:
    print("pip install httpx first")
    sys.exit(1)

URL = "https://f1-regulations-engine.onrender.com"
TEST_SET = Path(__file__).parent / "test_set.json"
OUTPUT = Path(__file__).parent / "eval_baseline.json"

with open(TEST_SET) as f:
    queries = json.load(f)["queries"]

client = httpx.Client(proxy=None)
results = []

for i, q in enumerate(queries):
    qid = q["id"]
    print(f"[{i+1}/{len(queries)}] {qid}: {q['query'][:60]}...", flush=True)
    
    expected = set(q["expected_articles"])
    key_facts = q.get("key_facts", [])
    
    t0 = time.monotonic()
    try:
        r = client.post(f"{URL}/api/chat", json={"query": q["query"]}, timeout=120)
        r.raise_for_status()
        data = r.json()
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        
        citations = data.get("citations", [])
        retrieved = set()
        for c in citations:
            code = c.get("article_code", "")
            retrieved.add(code)
            parts = code.split(".")
            if len(parts) > 1:
                retrieved.add(parts[0])
        
        precision = len(expected & retrieved) / len(retrieved) if retrieved else 0
        recall = len(expected & retrieved) / len(expected) if expected else 1
        
        answer = data.get("answer", "").lower()
        facts_found = sum(1 for f in key_facts if f.lower() in answer)
        fact_acc = facts_found / len(key_facts) if key_facts else 1
        
        steps = len(data.get("research_steps", []))
        
        result = {
            "id": qid, "difficulty": q["difficulty"],
            "expected": list(expected), "retrieved": list(retrieved),
            "precision": round(precision, 4), "recall": round(recall, 4),
            "fact_accuracy": round(fact_acc, 4),
            "time_ms": elapsed_ms, "steps": steps,
            "answer_len": len(answer), "error": None
        }
        status = f"P={precision:.0%} R={recall:.0%} F={fact_acc:.0%} {elapsed_ms/1000:.1f}s"
        
    except Exception as e:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        result = {
            "id": qid, "difficulty": q["difficulty"],
            "expected": list(expected), "retrieved": [],
            "precision": 0, "recall": 0, "fact_accuracy": 0,
            "time_ms": elapsed_ms, "steps": 0,
            "answer_len": 0, "error": str(e)
        }
        status = f"ERROR: {e}"
    
    results.append(result)
    print(f"  → {status}", flush=True)
    
    # Save incrementally
    with open(OUTPUT, "w") as f:
        json.dump({"timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "results": results}, f, indent=2)
    
    if i < len(queries) - 1:
        time.sleep(1)

client.close()

# Print summary
ok = [r for r in results if r["error"] is None]
print(f"\n{'='*60}")
print(f"BASELINE RESULTS ({len(ok)}/{len(results)} successful)")
print(f"  Avg Precision:  {sum(r['precision'] for r in ok)/len(ok):.1%}")
print(f"  Avg Recall:     {sum(r['recall'] for r in ok)/len(ok):.1%}")
print(f"  Avg Fact Acc:   {sum(r['fact_accuracy'] for r in ok)/len(ok):.1%}")
print(f"  Avg Time:       {sum(r['time_ms'] for r in ok)/len(ok)/1000:.1f}s")

for diff in ["easy", "medium", "hard"]:
    subset = [r for r in ok if r["difficulty"] == diff]
    if subset:
        print(f"  {diff:8s} P={sum(r['precision'] for r in subset)/len(subset):.0%} "
              f"R={sum(r['recall'] for r in subset)/len(subset):.0%} "
              f"F={sum(r['fact_accuracy'] for r in subset)/len(subset):.0%} "
              f"(n={len(subset)})")
print(f"{'='*60}")
print(f"Results saved to: {OUTPUT}")
