#!/bin/bash
# Monitor backup progress until complete (polls every 30 seconds)

API_URL="https://wp.zimpricecheck.com:8081/api/v1"
SITE_ID="${1:-1}"
POLL_INTERVAL="${2:-30}"  # seconds between polls

echo "=== Monitoring Backup for Site $SITE_ID ==="
echo "Poll interval: ${POLL_INTERVAL}s"
echo "Press Ctrl+C to stop monitoring"
echo ""

# Get token
TOKEN=$(curl -s -X POST "$API_URL/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"username":"admin@example.com","password":"admin123"}' | jq -r '.access_token')

if [ "$TOKEN" == "null" ] || [ -z "$TOKEN" ]; then
    echo "ERROR: Failed to get auth token"
    exit 1
fi

START_TIME=$(date +%s)

while true; do
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))
    ELAPSED_MIN=$((ELAPSED / 60))
    ELAPSED_SEC=$((ELAPSED % 60))
    
    # Get status
    RESULT=$(curl -s "$API_URL/daemon/backup/status/$SITE_ID" -H "Authorization: Bearer $TOKEN")
    
    STATUS=$(echo $RESULT | jq -r '.status')
    PROGRESS=$(echo $RESULT | jq -r '.progress')
    MESSAGE=$(echo $RESULT | jq -r '.message')
    ERROR=$(echo $RESULT | jq -r '.error')
    
    # Print status line
    printf "\r[%02d:%02d] Status: %-12s Progress: %3s%%  Stage: %-30s" \
        "$ELAPSED_MIN" "$ELAPSED_SEC" "$STATUS" "$PROGRESS" "$MESSAGE"
    
    # Check terminal conditions
    case "$STATUS" in
        "completed")
            echo ""
            echo ""
            echo "✅ Backup completed successfully!"
            echo "$RESULT" | jq .
            exit 0
            ;;
        "failed")
            echo ""
            echo ""
            echo "❌ Backup failed!"
            echo "Error: $ERROR"
            echo "$RESULT" | jq .
            exit 1
            ;;
        "stopped")
            echo ""
            echo ""
            echo "⏹️  Backup was stopped"
            echo "$RESULT" | jq .
            exit 0
            ;;
        "idle")
            echo ""
            echo ""
            echo "⚪ No backup running (status: idle)"
            exit 0
            ;;
    esac
    
    # Wait before next poll
    sleep $POLL_INTERVAL
done
