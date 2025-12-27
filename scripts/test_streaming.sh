#!/bin/bash

# Configuration
API_URL="https://wp.zimpricecheck.com:8081/api/v1"
USERNAME="admin@example.com"
PASSWORD="admin123"

echo "=== Testing Metrics Streaming ==="

# 1. Login
echo "[*] Logging in..."
TOKEN=$(curl -s -X POST "$API_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$USERNAME\",\"password\":\"$PASSWORD\"}" | jq -r '.access_token')

if [ -z "$TOKEN" ] || [ "$TOKEN" == "null" ]; then
    echo "[-] Login failed!"
    exit 1
fi
echo "[+] Login successful!"

# 2. Test Node Metrics Stream
echo
echo "[*] Connecting to Node Metrics Stream (will run for 5 seconds)..."
echo "--- Stream Output ---"
timeout 5 curl -N -s "$API_URL/metrics/node/stream?token=$TOKEN&interval=1"
echo
echo "--- End Stream ---"

# 3. Test Backup Stream (for a site)
echo
echo "[*] Connecting to Backup Stream for Site 1 (will run for 5 seconds)..."
echo "--- Stream Output ---"
timeout 5 curl -N -s "$API_URL/daemon/backup/stream/1?token=$TOKEN"
echo
echo "--- End Stream ---"

echo
echo "=== Test Complete ==="
