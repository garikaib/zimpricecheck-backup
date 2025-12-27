#!/bin/bash
# Test Quota Management System
# Usage: ./scripts/test_quota.sh

set -e

BASE_URL="${API_URL:-https://wp.zimpricecheck.com:8081}"
EMAIL="admin@example.com"
PASSWORD="admin123"

echo "=== Quota Management Test Suite ==="
echo "API: $BASE_URL"
echo ""

# Get token
echo "[1/5] Authenticating..."
TOKEN=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" | jq -r '.access_token')

if [ "$TOKEN" == "null" ] || [ -z "$TOKEN" ]; then
    echo "ERROR: Authentication failed"
    exit 1
fi
echo "  ✓ Authenticated"

# Get site info with node_uuid
echo ""
echo "[2/5] Testing site endpoint returns node_uuid..."
SITE=$(curl -s "$BASE_URL/api/v1/sites/" -H "Authorization: Bearer $TOKEN" | jq '.sites[0]')
SITE_ID=$(echo "$SITE" | jq -r '.id')
NODE_UUID=$(echo "$SITE" | jq -r '.node_uuid')
SITE_UUID=$(echo "$SITE" | jq -r '.uuid')

if [ "$NODE_UUID" != "null" ] && [ -n "$NODE_UUID" ]; then
    echo "  ✓ Site has node_uuid: $NODE_UUID"
else
    echo "  ✗ FAIL: node_uuid not returned"
fi

if [ "$SITE_UUID" != "null" ] && [ -n "$SITE_UUID" ]; then
    echo "  ✓ Site has uuid: $SITE_UUID"
else
    echo "  ✗ FAIL: uuid not returned"
fi

# Test quota update with valid value
echo ""
echo "[3/5] Testing valid quota update..."
RESPONSE=$(curl -s -X PUT "$BASE_URL/api/v1/sites/$SITE_ID/quota?quota_gb=15" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json")

SUCCESS=$(echo "$RESPONSE" | jq -r '.success')
if [ "$SUCCESS" == "true" ]; then
    echo "  ✓ Quota updated successfully"
    echo "$RESPONSE" | jq '.'
else
    echo "  ✗ Quota update failed"
    echo "$RESPONSE" | jq '.'
fi

# Test quota validation (try to exceed node quota)
echo ""
echo "[4/5] Testing quota validation (should reject 500GB)..."
RESPONSE=$(curl -s -X PUT "$BASE_URL/api/v1/sites/$SITE_ID/quota?quota_gb=500" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json")

if echo "$RESPONSE" | jq -e '.detail.message' > /dev/null 2>&1; then
    echo "  ✓ Correctly rejected excessive quota"
    echo "    Error: $(echo "$RESPONSE" | jq -r '.detail.message')"
else
    echo "  ✗ FAIL: Should have rejected quota > node limit"
    echo "$RESPONSE" | jq '.'
fi

# Show current storage status
echo ""
echo "[5/5] Current storage status..."
echo "$SITE" | jq '{
  site_name: .name,
  site_uuid: .uuid,
  node_uuid: .node_uuid,
  storage_used_gb: .storage_used_gb,
  storage_quota_gb: .storage_quota_gb
}'

echo ""
echo "=== Test Complete ==="
