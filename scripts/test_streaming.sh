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

# 2. Test Master-Only SSE Stream (OLD - single node, local only)
echo
echo "=== STAGE 1: Master-Only SSE Stream (Legacy) ==="
echo "[*] Connecting to MASTER Node Metrics Stream (will run for 3 seconds)..."
echo "    URL: $API_URL/metrics/node/stream?token=...&interval=1"
echo "    NOTE: This stream ONLY shows the Master server's metrics (local psutil)."
echo "--- Stream Output ---"
timeout 3 curl -N -s "$API_URL/metrics/node/stream?token=$TOKEN&interval=1" | head -5
echo
echo "--- End Stream ---"

# 3. Test Unified Node Stats Stream (NEW - ALL nodes in one stream)
echo
echo "=== STAGE 2: Unified Node Stats Stream (NEW) ==="
echo "[*] Connecting to UNIFIED Node Stats Stream (will run for 5 seconds)..."
echo "    URL: $API_URL/metrics/nodes/stats/stream?token=...&interval=2"
echo "    NOTE: This stream shows stats for ALL nodes (Master + Remote) in one unified format."
echo "--- Stream Output ---"
timeout 5 curl -N -s "$API_URL/metrics/nodes/stats/stream?token=$TOKEN&interval=2"
echo
echo "--- End Stream ---"

# 4. Quick REST check for /nodes/ API (backward compat)
echo
echo "[*] Verifying /nodes/ REST API (backward compat)..."
NODES_JSON=$(curl -s -X GET "$API_URL/nodes/" -H "Authorization: Bearer $TOKEN")
echo "$NODES_JSON" | jq -r '.[] | "-> Node: \(.hostname) (ID \(.id)) | Status: \(.status)"'



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
