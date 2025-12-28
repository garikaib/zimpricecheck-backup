#!/bin/bash
# Backup Testing Scripts for WordPress Backup SaaS
# Usage: source these scripts or run them individually
#
# All scripts support environment variable configuration:
#   API_URL  - API base URL (default: https://wp.zimpricecheck.com:8081)
#   EMAIL    - Login email (default: garikaib@gmail.com)
#   PASSWORD - Login password (default: Boh678p...)
#
# Example:
#   EMAIL=myuser@domain.com PASSWORD=secret ./start_backup.sh 1

# Default Configuration
API_URL="${API_URL:-https://wp.zimpricecheck.com:8081}/api/v1"
EMAIL="${EMAIL:-garikaib@gmail.com}"  
PASSWORD="${PASSWORD:-Boh678p...}"
SITE_ID=1

# Get auth token
get_token() {
    curl -s -X POST "$API_URL/auth/login" \
        -H "Content-Type: application/json" \
        -d "{\"username\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" | jq -r '.access_token'
}

echo "=== WordPress Backup Testing Scripts ==="
echo "API: $API_URL"
echo "Site ID: $SITE_ID"
echo ""
echo "Configuration (via environment variables):"
echo "  API_URL=$API_URL"
echo "  EMAIL=$EMAIL"
echo "  PASSWORD=****"
echo ""
echo "Available commands:"
echo "  ./start_backup.sh [site_id]          - Start a backup for a site"
echo "  ./check_status.sh [site_id]          - Check backup status once"
echo "  ./monitor_backup.sh [site_id] [poll] - Monitor backup until complete"
echo "  ./reset_backup.sh [site_id]          - Reset stuck backup to idle"
echo "  ./view_logs.sh [limit] [search]      - View recent logs"
echo "  ./test_quota.sh                      - Test quota management"
echo "  ./test_streaming.sh [site_id]        - Test SSE streaming endpoints"
echo ""
echo "API Endpoints Used:"
echo "  POST /sites/{id}/backup/start   - Start backup"
echo "  GET  /sites/{id}/backup/status  - Check backup status"
echo "  POST /sites/{id}/backup/stop    - Stop running backup"
echo "  PUT  /sites/{id}/quota          - Update site quota"
echo "  GET  /sites/{id}/quota/status   - Get quota status"
echo "  POST /daemon/backup/reset/{id}  - Reset stuck backup"
echo "  GET  /logs                      - View logs"
echo "  GET  /logs/search               - Search logs"
