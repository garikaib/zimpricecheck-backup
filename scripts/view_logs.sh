#!/bin/bash
# View recent logs (filtered to backup-related entries)
# Uses the /logs endpoint with optional search

API_URL="${API_URL:-https://wp.zimpricecheck.com:8081}/api/v1"
LIMIT="${1:-50}"
SEARCH="${2:-}"
EMAIL="${EMAIL:-garikaib@gmail.com}"
PASSWORD="${PASSWORD:-Boh678p...}"

echo "=== Recent Logs (limit: $LIMIT) ==="

# Get token
TOKEN=$(curl -s -X POST "$API_URL/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" | jq -r '.access_token')

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
