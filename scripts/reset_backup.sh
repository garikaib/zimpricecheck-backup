#!/bin/bash
# Reset a stuck backup to idle state

API_URL="https://wp.zimpricecheck.com:8081/api/v1"
SITE_ID="${1:-1}"

echo "=== Resetting Backup Status for Site $SITE_ID ==="

# Get token
TOKEN=$(curl -s -X POST "$API_URL/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"username":"admin@example.com","password":"admin123"}' | jq -r '.access_token')

if [ "$TOKEN" == "null" ] || [ -z "$TOKEN" ]; then
    echo "ERROR: Failed to get auth token"
    exit 1
fi

# Reset status
RESULT=$(curl -s -X POST "$API_URL/daemon/backup/reset/$SITE_ID" -H "Authorization: Bearer $TOKEN")
echo "$RESULT" | jq .
