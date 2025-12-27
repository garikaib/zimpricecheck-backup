#!/bin/bash
# View recent logs (filtered to backup-related entries)

API_URL="https://wp.zimpricecheck.com:8081/api/v1"
LIMIT="${1:-50}"
SEARCH="${2:-}"

echo "=== Recent Logs (limit: $LIMIT) ==="

# Get token
TOKEN=$(curl -s -X POST "$API_URL/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"username":"admin@example.com","password":"admin123"}' | jq -r '.access_token')

if [ "$TOKEN" == "null" ] || [ -z "$TOKEN" ]; then
    echo "ERROR: Failed to get auth token"
    exit 1
fi

# Get logs
if [ -n "$SEARCH" ]; then
    echo "Search filter: $SEARCH"
    curl -s "$API_URL/logs/search?query=$SEARCH&limit=$LIMIT" -H "Authorization: Bearer $TOKEN" | jq '.entries[] | {timestamp, level, message}'
else
    curl -s "$API_URL/logs?limit=$LIMIT" -H "Authorization: Bearer $TOKEN" | jq '.entries[] | {timestamp, level, message}'
fi
