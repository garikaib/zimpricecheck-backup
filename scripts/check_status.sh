#!/bin/bash
# Check backup status once

API_URL="https://wp.zimpricecheck.com:8081/api/v1"
SITE_ID="${1:-1}"

# Get token
TOKEN=$(curl -s -X POST "$API_URL/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"username":"admin@example.com","password":"admin123"}' | jq -r '.access_token')

if [ "$TOKEN" == "null" ] || [ -z "$TOKEN" ]; then
    echo "ERROR: Failed to get auth token"
    exit 1
fi

# Get status
echo "=== Backup Status for Site $SITE_ID ==="
curl -s "$API_URL/daemon/backup/status/$SITE_ID" -H "Authorization: Bearer $TOKEN" | jq .
