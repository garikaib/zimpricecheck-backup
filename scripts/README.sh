#!/bin/bash
# Backup Testing Scripts for WordPress Backup SaaS
# Usage: source these scripts or run them individually

# Configuration
API_URL="https://wp.zimpricecheck.com:8081/api/v1"
USERNAME="admin@example.com"
PASSWORD="admin123"
SITE_ID=1

# Get auth token
get_token() {
    curl -s -X POST "$API_URL/auth/login" \
        -H "Content-Type: application/json" \
        -d "{\"username\":\"$USERNAME\",\"password\":\"$PASSWORD\"}" | jq -r '.access_token'
}

echo "=== WordPress Backup Testing Scripts ==="
echo "API: $API_URL"
echo "Site ID: $SITE_ID"
echo ""
echo "Available commands:"
echo "  ./start_backup.sh    - Start a backup"
echo "  ./check_status.sh    - Check backup status once"
echo "  ./monitor_backup.sh  - Monitor backup until complete (polls every 30s)"
echo "  ./reset_backup.sh    - Reset stuck backup to idle"
echo "  ./view_logs.sh       - View recent logs"
