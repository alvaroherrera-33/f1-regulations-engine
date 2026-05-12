#!/usr/bin/env python3
"""
Evaluation framework for F1 Regulations RAG Engine.

Runs a test set of queries against the backend, compares retrieved articles
and answer content against expected values, and reports precision/recall metrics.

Usage:
    # Against local backend (default)
    python -m eval.run_eval

    # Against production
    python -m eval.run_eval --url https://f1-regulations-engine.onrender.com

    # Only run specific difficulty levels
    python -m eval.run_eval --difficulty easy medium

    # Save results to file
    python -m eval.run_eval --output eval_results.json

    # Verbose mode (show each query result)
    python -m eval.run_eval -v
"""

import argparse
import json
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

try:
    import httpx
except ImportError:
    print("httpx is required: pip install httpx")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class QueryResult:
    """Result of evaluating a single query."""
    id: str
    query: str
    difficulty: str
    expected_articles: list[str]
    retrieved_articles: list[str]
    retrieval_precision: float
    retrieval_recall: float
    key_facts_total: int
    key_facts_found: int
    fact_accuracy: float
    response_time_ms: int
    research_steps: int
    answer_length: int
    error: Optional[str] = None


@dataclass
class EvalReport:
    """Aggregate evaluation report."""
    timestamp: str
    backend_url: str
    total_queries: int
    successful_queries: int
    failed_queries: int
    # Aggregate metrics
    avg_retrieval_precision: float = 0.0
    avg_retrieval_recall: float = 0.0
    avg_fact_accuracy: float = 0.0
    avg_response_time_ms: float = 0.0
    # By difficulty
    metrics_by_difficulty: dict = field(default_factory=dict)
    # By section
    metrics_by_section: dict = field(default_factory=dict)
    # Individual results
    results: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Core evaluation logic
# ---------------------------------------------------------------------------

def _normalize_code(code: str) -> str:
    """Strip single-letter section prefix from article codes.

    Technical regs use 'C' prefix (e.g. C4.1 -> 4.1), so expected '4.1'
    can match retrieved 'C4.1'.
    """
    if len(code) > 1 and code[0].isalpha() and not code[1].isalpha():
        return code[1:]
    return code


def run_query(client: httpx.Client, url: str, query_data: dict) -> QueryResult:
    """Execute a single query and evaluate the results."""
    query = query_data["query"]
    expected_articles = set(query_data["expected_articles"])
    key_facts = query_data.get("key_facts", [])

    payload = {"query": query}
    # Don't pass year/section filters — we want to test the auto-detection
    # (prepare_search should figure these out)

    t_start = time.monotonic()
    try:
        response = client.post(f"{url}/api/chat", json=payload, timeout=120.0)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        elapsed = int((time.monotonic() - t_start) * 1000)
        return QueryResult(
            id=query_data["id"],
            query=query,
            difficulty=query_data["difficulty"],
            expected_articles=list(expected_articles),
            retrieved_articles=[],
            retrieval_precision=0.0,
            retrieval_recall=0.0,
            key_facts_total=len(key_facts),
            key_facts_found=0,
            fact_accuracy=0.0,
            response_time_ms=elapsed,
            research_steps=0,
            answer_length=0,
            error=str(e),
        )

    elapsed = int((time.monotonic() - t_start) * 1000)

    # Extract cited article codes from the response
    citations = data.get("citations", [])
    retrieved_codes = set()
    for c in citations:
        code = c.get("article_code", "")
        retrieved_codes.add(code)
        # Also match parent codes: if expected has "4" and we got "4.1",
        # the parent matches
        parts = code.split(".")
        if len(parts) > 1:
            retrieved_codes.add(parts[0])

    # Normalize codes for comparison (strip section prefix like C, A, etc.)
    norm_expected = {_normalize_code(c) for c in expected_articles}
    norm_retrieved = {_normalize_code(c) for c in retrieved_codes}

    # Retrieval precision: of the articles we cited, how many were expected?
    if norm_retrieved:
        precision_hits = len(norm_expected & norm_retrieved)
        precision = precision_hits / len(norm_retrieved) if norm_retrieved else 0.0
    else:
        precision = 0.0

    # Retrieval recall: of the expected articles, how many did we retrieve?
    if norm_expected:
        recall_hits = len(norm_expected & norm_retrieved)
        recall = recall_hits / len(norm_expected)
    else:
        recall = 1.0  # No expected articles = trivially correct

    # Fact accuracy: check if key facts appear in the answer
    answer = data.get("answer", "").lower()
    facts_found = sum(1 for fact in key_facts if fact.lower() in answer)
    fact_acc = facts_found / len(key_facts) if key_facts else 1.0

    research_steps = data.get("research_steps", [])

    return QueryResult(
        id=query_data["id"],
        query=query,
        difficulty=query_data["difficulty"],
        expected_articles=list(expected_articles),
        retrieved_articles=list(retrieved_codes),
        retrieval_precision=round(precision, 4),
        retrieval_recall=round(recall, 4),
        key_facts_total=len(key_facts),
        key_facts_found=facts_found,
        fact_accuracy=round(fact_acc, 4),
        response_time_ms=elapsed,
        research_steps=len(research_steps),
        answer_length=len(answer),
    )


def aggregate_metrics(results: list[QueryResult]) -> dict:
    """Compute average metrics from a list of results."""
    if not results:
        return {"precision": 0, "recall": 0, "fact_accuracy": 0, "avg_time_ms": 0, "count": 0}

    successful = [r for r in results if r.error is None]
    if not successful:
        return {"precision": 0, "recall": 0, "fact_accuracy": 0, "avg_time_ms": 0, "count": 0}

    return {
        "precision": round(sum(r.retrieval_precision for r in successful) / len(successful), 4),
        "recall": round(sum(r.retrieval_recall for r in successful) / len(successful), 4),
        "fact_accuracy": round(sum(r.fact_accuracy for r in successful) / len(successful), 4),
        "avg_time_ms": int(sum(r.response_time_ms for r in successful) / len(successful)),
        "count": len(successful),
    }


def build_report(results: list[QueryResult], url: str) -> EvalReport:
    """Build a complete evaluation report."""
    successful = [r for r in results if r.error is None]
    failed = [r for r in results if r.error is not None]
    agg = aggregate_metrics(successful)

    # By difficulty
    difficulties = set(r.difficulty for r in results)
    by_diff = {}
    for d in sorted(difficulties):
        subset = [r for r in successful if r.difficulty == d]
        by_diff[d] = aggregate_metrics(subset)

    # By section (inferred from query ID prefix)
    section_map = {"tech": "Technical", "sport": "Sporting", "fin": "Financial"}
    by_section = {}
    for prefix, section_name in section_map.items():
        subset = [r for r in successful if r.id.startswith(prefix)]
        if subset:
            by_section[section_name] = aggregate_metrics(subset)

    return EvalReport(
        timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
        backend_url=url,
        total_queries=len(results),
        successful_queries=len(successful),
        failed_queries=len(failed),
        avg_retrieval_precision=agg["precision"],
        avg_retrieval_recall=agg["recall"],
        avg_fact_accuracy=agg["fact_accuracy"],
        avg_response_time_ms=agg["avg_time_ms"],
        metrics_by_difficulty=by_diff,
        metrics_by_section=by_section,
        results=[asdict(r) for r in results],
    )


# ---------------------------------------------------------------------------
# Output / display
# ---------------------------------------------------------------------------

def print_result(result: QueryResult, verbose: bool = False):
    """Print a single query result."""
    status = "FAIL" if result.error else "OK"
    icon = "✗" if result.error else "✓"

    # Color: green for good, yellow for partial, red for bad/error
    recall_str = f"R={result.retrieval_recall:.0%}"
    fact_str = f"F={result.fact_accuracy:.0%}"
    time_str = f"{result.response_time_ms / 1000:.1f}s"

    print(f"  {icon} [{result.id}] {status}  {recall_str}  {fact_str}  {time_str}")

    if result.error:
        print(f"    ERROR: {result.error}")
    elif verbose:
        print(f"    Query: {result.query}")
        print(f"    Expected: {result.expected_articles}")
        print(f"    Retrieved: {result.retrieved_articles}")
        print(f"    Precision: {result.retrieval_precision:.0%}  |  Recall: {result.retrieval_recall:.0%}")
        print(f"    Facts: {result.key_facts_found}/{result.key_facts_total}")
        print(f"    Steps: {result.research_steps}  |  Answer: {result.answer_length} chars")
        print()


def print_report(report: EvalReport):
    """Print a formatted evaluation report to the console."""
    print()
    print("=" * 64)
    print("  F1 RAG Engine — Evaluation Report")
    print("=" * 64)
    print(f"  Backend:  {report.backend_url}")
    print(f"  Time:     {report.timestamp}")
    print(f"  Queries:  {report.successful_queries}/{report.total_queries} successful")
    print("-" * 64)
    print()
    print("  AGGREGATE METRICS")
    print(f"    Retrieval Precision:  {report.avg_retrieval_precision:.1%}")
    print(f"    Retrieval Recall:     {report.avg_retrieval_recall:.1%}")
    print(f"    Fact Accuracy:        {report.avg_fact_accuracy:.1%}")
    print(f"    Avg Response Time:    {report.avg_response_time_ms}ms")
    print()

    if report.metrics_by_difficulty:
        print("  BY DIFFICULTY")
        for diff, metrics in report.metrics_by_difficulty.items():
            print(f"    {diff:8s}  P={metrics['precision']:.0%}  R={metrics['recall']:.0%}  "
                  f"F={metrics['fact_accuracy']:.0%}  T={metrics['avg_time_ms']}ms  (n={metrics['count']})")
        print()

    if report.metrics_by_section:
        print("  BY SECTION")
        for section, metrics in report.metrics_by_section.items():
            print(f"    {section:12s}  P={metrics['precision']:.0%}  R={metrics['recall']:.0%}  "
                  f"F={metrics['fact_accuracy']:.0%}  T={metrics['avg_time_ms']}ms  (n={metrics['count']})")
        print()

    print("=" * 64)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Evaluate F1 RAG Engine quality")
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Backend URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--difficulty",
        nargs="+",
        choices=["easy", "medium", "hard"],
        help="Only run queries of these difficulty levels",
    )
    parser.add_argument(
        "--section",
        nargs="+",
        choices=["tech", "sport", "fin"],
        help="Only run queries for these sections (prefix match on ID)",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="Save full results as JSON to this path",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed results per query",
    )
    parser.add_argument(
        "--test-set",
        type=str,
        default=None,
        help="Path to test set JSON (default: eval/test_set.json)",
    )
    args = parser.parse_args()

    # Load test set
    test_set_path = args.test_set or (Path(__file__).parent / "test_set.json")
    with open(test_set_path) as f:
        test_data = json.load(f)

    queries = test_data["queries"]

    # Filter by difficulty
    if args.difficulty:
        queries = [q for q in queries if q["difficulty"] in args.difficulty]

    # Filter by section prefix
    if args.section:
        queries = [q for q in queries if any(q["id"].startswith(s) for s in args.section)]

    if not queries:
        print("No queries match the specified filters.")
        sys.exit(1)

    url = args.url.rstrip("/")

    # Check backend health first
    print(f"\nConnecting to {url}...")
    client = httpx.Client(proxy=None)
    try:
        health = client.get(f"{url}/health", timeout=30.0)
        health.raise_for_status()
        print(f"Backend is healthy: {health.json()}")
    except Exception as e:
        print(f"WARNING: Backend health check failed: {e}")
        print("Continuing anyway — queries may fail.\n")

    # Run queries
    print(f"\nRunning {len(queries)} evaluation queries...\n")
    results: list[QueryResult] = []

    for i, query_data in enumerate(queries, 1):
        print(f"  [{i}/{len(queries)}] {query_data['id']}: {query_data['query'][:60]}...")
        result = run_query(client, url, query_data)
        results.append(result)
        print_result(result, verbose=args.verbose)

        # Small delay between queries to avoid hammering the backend
        if i < len(queries):
            time.sleep(1.0)

    client.close()

    # Build and display report
    report = build_report(results, url)
    print_report(report)

    # Save to file if requested
    if args.output:
        output_path = Path(args.output)
        with open(output_path, "w") as f:
            json.dump(asdict(report), f, indent=2, default=str)
        print(f"Full results saved to: {output_path}")

    # Exit code: 1 if any queries failed completely
    if report.failed_queries > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
