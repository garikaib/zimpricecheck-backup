#!/bin/bash
# Test SSE streaming endpoints for metrics and backup progress

API_URL="${API_URL:-https://wp.zimpricecheck.com:8081}/api/v1"
EMAIL="${EMAIL:-garikaib@gmail.com}"
PASSWORD="${PASSWORD:-Boh678p...}"
SITE_ID="${1:-1}"

echo "=== Testing Streaming Endpoints ==="

# 1. Login
echo "[*] Logging in..."
TOKEN=$(curl -s -X POST "$API_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" | jq -r '.access_token')

if [ -z "$TOKEN" ] || [ "$TOKEN" == "null" ]; then
    echo "[-] Login failed!"
    exit 1
fi
echo "[+] Login successful!"

# 2. Test Node Metrics Stream
echo
echo "[*] Connecting to Node Metrics Stream (will run for 5 seconds)..."
echo "    URL: $API_URL/metrics/node/stream?token=...&interval=1"
echo "--- Stream Output ---"
timeout 5 curl -N -s "$API_URL/metrics/node/stream?token=$TOKEN&interval=1"
echo
echo "--- End Stream ---"

# 3. Test Backup Stream (for a site)
echo
echo "[*] Connecting to Backup Stream for Site $SITE_ID (will run for 5 seconds)..."
echo "    URL: $API_URL/daemon/backup/stream/$SITE_ID?token=...&interval=2"
echo "--- Stream Output ---"
timeout 5 curl -N -s "$API_URL/daemon/backup/stream/$SITE_ID?token=$TOKEN&interval=2"
echo
echo "--- End Stream ---"

# 4. Test Log Stream (Super Admin only)
echo
echo "[*] Connecting to Log Stream (will run for 5 seconds)..."
echo "    URL: $API_URL/logs/stream?token=..."
echo "--- Stream Output ---"
timeout 5 curl -N -s "$API_URL/logs/stream?token=$TOKEN"
echo
echo "--- End Stream ---"

echo
echo "=== Test Complete ==="
