#!/bin/bash
# Check backup status once
# Uses the modern /sites/{id}/backup/status endpoint

API_URL="${API_URL:-https://wp.zimpricecheck.com:8081}/api/v1"
SITE_ID="${1:-1}"
EMAIL="${EMAIL:-garikaib@gmail.com}"
PASSWORD="${PASSWORD:-Boh678p...}"

# Get token
TOKEN=$(curl -s -X POST "$API_URL/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" | jq -r '.access_token')

if [ "$TOKEN" == "null" ] || [ -z "$TOKEN" ]; then
    echo "ERROR: Failed to get auth token"
    exit 1
fi

# Get status using the sites API endpoint
echo "=== Backup Status for Site $SITE_ID ==="
curl -s "$API_URL/sites/$SITE_ID/backup/status" -H "Authorization: Bearer $TOKEN" | jq .
