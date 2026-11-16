#!/usr/bin/env bash
# Sends the sample message to a running server (default http://localhost:4000).
set -euo pipefail
BASE_URL="${BASE_URL:-http://localhost:4000}"
curl -sS -X POST "$BASE_URL/posting" \
  -H "Content-Type: application/json" \
  -d '{"message": "Check out our latest business platform and grow your online visibility. https://example.com"}' \
  | python3 -m json.tool
