#!/bin/bash
# Eval via curl — one query at a time, saves results incrementally.
# Works around sandbox 45s timeout by using curl directly.
# Usage: bash eval/run_curl_eval.sh [start_index]

URL="https://f1-regulations-engine.onrender.com"
RESULTS="/tmp/eval_results"
START_IDX=${1:-0}

mkdir -p "$RESULTS"

# Extract queries from test_set.json
QUERIES=$(python3 -c "
import json
with open('eval/test_set.json') as f:
    qs = json.load(f)['queries']
for i, q in enumerate(qs):
    print(f\"{i}|{q['id']}|{q['query']}\")
")

IDX=0
while IFS='|' read -r i qid query; do
    if [ "$i" -lt "$START_IDX" ]; then
        continue
    fi

    OUTFILE="$RESULTS/q${i}.json"
    if [ -f "$OUTFILE" ] && [ -s "$OUTFILE" ]; then
        echo "SKIP [$qid] (already done)"
        continue
    fi

    echo -n "[$((i+1))/20] $qid: ${query:0:60}... "

    # Escape query for JSON
    ESCAPED=$(python3 -c "import json; print(json.dumps('$query'))" 2>/dev/null || echo "\"$query\"")

    curl -s --max-time 120 -X POST "$URL/api/chat" \
        -H 'Content-Type: application/json' \
        -d "{\"query\":$ESCAPED}" \
        > "$OUTFILE" 2>/dev/null

    if [ -s "$OUTFILE" ]; then
        echo "OK ($(wc -c < "$OUTFILE") bytes)"
    else
        echo "FAILED"
        rm -f "$OUTFILE"
    fi

    sleep 1
done <<< "$QUERIES"

echo ""
echo "Done. Process results with: python3 eval/process_curl_results.py"
