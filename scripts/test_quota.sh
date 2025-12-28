#!/bin/bash
# Test Quota Management System
# Usage: ./scripts/test_quota.sh

set -e

API_URL="${API_URL:-https://wp.zimpricecheck.com:8081}/api/v1"
EMAIL="${EMAIL:-garikaib@gmail.com}"
PASSWORD="${PASSWORD:-Boh678p...}"

echo "=== Quota Management Test Suite ==="
echo "API: $API_URL"
echo ""

# Get token
echo "[1/6] Authenticating..."
TOKEN=$(curl -s -X POST "$API_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" | jq -r '.access_token')

if [ "$TOKEN" == "null" ] || [ -z "$TOKEN" ]; then
    echo "ERROR: Authentication failed"
    exit 1
fi
echo "  ✓ Authenticated"

# Get site info with node_uuid
echo ""
echo "[2/6] Testing site endpoint returns node_uuid..."
SITE=$(curl -s "$API_URL/sites/" -H "Authorization: Bearer $TOKEN" | jq '.sites[0]')
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

# Test quota status endpoint
echo ""
echo "[3/6] Testing quota status endpoint..."
QUOTA_STATUS=$(curl -s "$API_URL/sites/$SITE_ID/quota/status" -H "Authorization: Bearer $TOKEN")
USAGE_PERCENT=$(echo "$QUOTA_STATUS" | jq -r '.usage_percent')
CAN_BACKUP=$(echo "$QUOTA_STATUS" | jq -r '.can_backup')

if [ "$USAGE_PERCENT" != "null" ] && [ -n "$USAGE_PERCENT" ]; then
    echo "  ✓ Quota status returned: ${USAGE_PERCENT}% used"
    echo "  ✓ Can backup: $CAN_BACKUP"
else
    echo "  ✗ FAIL: quota status endpoint error"
    echo "$QUOTA_STATUS" | jq '.'
fi

# Test quota update with valid value
echo ""
echo "[4/6] Testing valid quota update..."
RESPONSE=$(curl -s -X PUT "$API_URL/sites/$SITE_ID/quota?quota_gb=15" \
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
echo "[5/6] Testing quota validation (should reject 500GB)..."
RESPONSE=$(curl -s -X PUT "$API_URL/sites/$SITE_ID/quota?quota_gb=500" \
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
echo "[6/6] Current storage status..."
echo "$SITE" | jq '{
  site_name: .name,
  site_uuid: .uuid,
  node_uuid: .node_uuid,
  storage_used_gb: .storage_used_gb,
  storage_quota_gb: .storage_quota_gb
}'

echo ""
echo "=== Test Complete ==="
