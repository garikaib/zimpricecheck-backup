#!/bin/bash
# Start a WordPress backup via API
# Uses the modern /sites/{id}/backup/start endpoint

API_URL="${API_URL:-https://wp.zimpricecheck.com:8081}/api/v1"
SITE_ID="${1:-1}"
EMAIL="${EMAIL:-garikaib@gmail.com}"
PASSWORD="${PASSWORD:-Boh678p...}"

echo "=== Starting Backup for Site $SITE_ID ==="

# Get token
TOKEN=$(curl -s -X POST "$API_URL/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" | jq -r '.access_token')

if [ "$TOKEN" == "null" ] || [ -z "$TOKEN" ]; then
    echo "ERROR: Failed to get auth token"
    exit 1
fi

echo "Token acquired: ${TOKEN:0:20}..."

# Get site details first
echo ""
echo "Fetching site details..."
SITE_INFO=$(curl -s "$API_URL/sites/$SITE_ID" -H "Authorization: Bearer $TOKEN")
SITE_NAME=$(echo $SITE_INFO | jq -r '.name')
SITE_PATH=$(echo $SITE_INFO | jq -r '.wp_path')

if [ "$SITE_NAME" == "null" ]; then
    echo "ERROR: Site not found or access denied"
    echo "$SITE_INFO" | jq .
    exit 1
fi

echo "Site: $SITE_NAME"
echo "Path: $SITE_PATH"

# Start backup using the sites API endpoint
echo ""
echo "Starting backup..."
RESULT=$(curl -s -X POST "$API_URL/sites/$SITE_ID/backup/start" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json")

echo "$RESULT" | jq .

# Check if it was successful
SUCCESS=$(echo $RESULT | jq -r '.success')
if [ "$SUCCESS" == "true" ]; then
    echo ""
    echo "✅ Backup started! Run ./check_status.sh or ./monitor_backup.sh to track progress."
else
    ERROR=$(echo $RESULT | jq -r '.detail // .message // "Unknown error"')
    echo ""
    echo "❌ Failed to start backup: $ERROR"
fi
