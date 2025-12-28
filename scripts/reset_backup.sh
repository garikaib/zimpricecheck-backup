#!/bin/bash
# Reset a stuck backup to idle state
# Uses the daemon endpoint which includes temp file cleanup

API_URL="${API_URL:-https://wp.zimpricecheck.com:8081}/api/v1"
SITE_ID="${1:-1}"
EMAIL="${EMAIL:-garikaib@gmail.com}"
PASSWORD="${PASSWORD:-Boh678p...}"

echo "=== Resetting Backup Status for Site $SITE_ID ==="

# Get token
TOKEN=$(curl -s -X POST "$API_URL/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" | jq -r '.access_token')

if [ "$TOKEN" == "null" ] || [ -z "$TOKEN" ]; then
    echo "ERROR: Failed to get auth token"
    exit 1
fi

# Reset status (uses daemon endpoint for cleanup functionality)
RESULT=$(curl -s -X POST "$API_URL/daemon/backup/reset/$SITE_ID" -H "Authorization: Bearer $TOKEN")
echo "$RESULT" | jq .

SUCCESS=$(echo $RESULT | jq -r '.success')
if [ "$SUCCESS" == "true" ]; then
    echo ""
    echo "✅ Backup status reset to idle"
    # Show cleanup info if available
    DIRS_REMOVED=$(echo $RESULT | jq -r '.cleanup.dirs_removed // 0')
    SPACE_FREED=$(echo $RESULT | jq -r '.cleanup.space_freed_mb // 0')
    if [ "$DIRS_REMOVED" -gt 0 ]; then
        echo "   Cleaned up $DIRS_REMOVED temp directories, freed ${SPACE_FREED}MB"
    fi
else
    echo ""
    echo "❌ Reset failed"
fi
