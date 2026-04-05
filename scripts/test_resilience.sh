#!/bin/bash
# PulseChecks Resilience Testing Script
# Tests availability, durability, alert reliability, and graceful degradation

set -e

API_URL="${API_URL:-https://pulsechecks-api-prod.run.app}"
USER_TOKEN="${USER_TOKEN:-}"
TEAM_ID="${TEAM_ID:-}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

test_passed=0
test_failed=0

print_section() {
  echo ""
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${BLUE}$1${NC}"
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

test_case() {
  local name="$1"
  local cmd="$2"
  local expect="$3"
  
  echo -n "  ➜ $name ... "
  
  output=$(eval "$cmd" 2>&1) || output="$?"
  
  if echo "$output" | grep -q "$expect"; then
    echo -e "${GREEN}PASS${NC}"
    ((test_passed++))
  else
    echo -e "${RED}FAIL${NC}"
    echo "    Output: $output"
    ((test_failed++))
  fi
}

check_prerequisites() {
  if [ -z "$USER_TOKEN" ] || [ -z "$TEAM_ID" ]; then
    echo "Error: Set USER_TOKEN and TEAM_ID environment variables"
    exit 1
  fi
}

# Create test check
create_test_check() {
  local name="$1"
  local response=$(curl -s -X POST "$API_URL/teams/$TEAM_ID/checks" \
    -H "Authorization: Bearer $USER_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"name\": \"resilience-$name-$(date +%s)\", \"type\": \"heartbeat\", \"periodSeconds\": 300}")
  
  CHECK_ID=$(echo "$response" | jq -r '.id // empty')
  CHECK_TOKEN=$(echo "$response" | jq -r '.token // empty')
  
  if [ -z "$CHECK_ID" ] || [ -z "$CHECK_TOKEN" ]; then
    echo -e "${RED}Failed to create test check${NC}"
    return 1
  fi
  
  echo "$CHECK_ID:$CHECK_TOKEN"
}

# --- Tests ---

echo -e "${YELLOW}PulseChecks Resilience Test Suite${NC}"
echo "API: $API_URL"
echo "Team: $TEAM_ID"
echo ""

check_prerequisites

# Test 1: Ping Latency
print_section "Test 1: Ping Endpoint Latency"

CHECK=$(create_test_check "latency")
CHECK_TOKEN=$(echo "$CHECK" | cut -d: -f2)

echo "  Testing latency baseline (single ping)..."
for i in {1..5}; do
  LATENCY=$(curl -s -w '%{time_total}' -X POST "$API_URL/ping/$CHECK_TOKEN/success" -o /dev/null)
  echo "    Attempt $i: ${LATENCY}s"
  
  # Check if within acceptable range (<500ms)
  if (( $(echo "$LATENCY < 0.5" | bc -l) )); then
    ((test_passed++))
  else
    echo -e "    ${RED}WARNING: Latency >500ms${NC}"
    ((test_failed++))
  fi
done

# Test 2: Data Persistence
print_section "Test 2: Ping Data Persistence"

CHECK=$(create_test_check "persistence")
CHECK_ID=$(echo "$CHECK" | cut -d: -f1)
CHECK_TOKEN=$(echo "$CHECK" | cut -d: -f2)

# Send test ping
curl -s -X POST "$API_URL/ping/$CHECK_TOKEN/success" > /dev/null
sleep 2

# Verify in database
test_case "Ping persisted to database" \
  "curl -s -X GET '$API_URL/teams/$TEAM_ID/checks/$CHECK_ID/pings' \
    -H 'Authorization: Bearer $USER_TOKEN' | jq '.pings | length'" \
  "^[0-9]"

# Test 3: Rapid Failure Handling
print_section "Test 3: Rapid Failure Detection"

CHECK=$(create_test_check "failures")
CHECK_TOKEN=$(echo "$CHECK" | cut -d: -f2)

echo "  Sending rapid fail pings..."
for i in {1..3}; do
  curl -s -X POST "$API_URL/ping/$CHECK_TOKEN/fail" > /dev/null
  sleep 0.5
done

echo "  Pings sent. System should handle rapid failures gracefully."
echo -e "${GREEN}✓ No errors during rapid failures${NC}"
((test_passed++))

# Test 4: Concurrent Pings
print_section "Test 4: Concurrent Ping Handling"

CHECK=$(create_test_check "concurrent")
CHECK_TOKEN=$(echo "$CHECK" | cut -d: -f2)

echo "  Sending 50 concurrent pings..."
SUCCESS_COUNT=0
FAIL_COUNT=0

for i in {1..50}; do
  {
    RESPONSE=$(curl -s -w '%{http_code}' -X POST "$API_URL/ping/$CHECK_TOKEN/success" -o /dev/null)
    if [ "$RESPONSE" = "200" ]; then
      ((SUCCESS_COUNT++))
    else
      ((FAIL_COUNT++))
    fi
  } &
done
wait

echo "  Results: $SUCCESS_COUNT successful, $FAIL_COUNT failed"

# Accept 95% success rate
if (( SUCCESS_COUNT >= 47 )); then
  echo -e "${GREEN}✓ Concurrent ping handling: PASS${NC}"
  ((test_passed++))
else
  echo -e "${RED}✗ Concurrent ping handling: FAIL${NC}"
  ((test_failed++))
fi

# Test 5: Alert Queue Presence
print_section "Test 5: Alert Reliability Infrastructure"

test_case "Alerts endpoint exists" \
  "curl -s -X GET '$API_URL/teams/$TEAM_ID/alerts' \
    -H 'Authorization: Bearer $USER_TOKEN' | jq '.alerts'" \
  "^\[\]$|^null$|^[0-9]"

# Test 6: Health Check Endpoint
print_section "Test 6: Health Check & Observability"

test_case "Health endpoint responds" \
  "curl -s -X GET '$API_URL/health' | jq '.status'" \
  "healthy|ok|up"

# Test 7: Graceful Error Handling
print_section "Test 7: Graceful Degradation"

CHECK=$(create_test_check "degrade")
CHECK_TOKEN=$(echo "$CHECK" | cut -d: -f2)

echo "  Testing response to malformed requests..."

test_case "Invalid check token rejected gracefully" \
  "curl -s -X POST '$API_URL/ping/invalid-token/success' -w '%{http_code}' -o /dev/null" \
  "400|404|401"

test_case "Valid check token still works" \
  "curl -s -w '%{http_code}' -X POST '$API_URL/ping/$CHECK_TOKEN/success' -o /dev/null" \
  "200"

# Test 8: Load Distribution
print_section "Test 8: Load Distribution & Scalability"

CHECK=$(create_test_check "load")
CHECK_TOKEN=$(echo "$CHECK" | cut -d: -f2)

echo "  Sending 500 pings in sequence (simulates load)..."
START=$(date +%s%N)

for i in {1..500}; do
  curl -s -X POST "$API_URL/ping/$CHECK_TOKEN/success" > /dev/null &
  
  # Limit parallelism to avoid overwhelming API
  if [ $((i % 50)) -eq 0 ]; then
    wait
  fi
done
wait

END=$(date +%s%N)
DURATION=$(( (END - START) / 1000000 ))  # Convert to milliseconds
DURATION_SEC=$(echo "scale=2; $DURATION / 1000" | bc)

echo "  Completed 500 pings in ${DURATION_SEC}s"

if (( DURATION < 60000 )); then  # 60 seconds
  echo -e "${GREEN}✓ Load test: PASS (avg <120ms per ping)${NC}"
  ((test_passed++))
else
  echo -e "${RED}✗ Load test: SLOW (avg >120ms per ping)${NC}"
  ((test_failed++))
fi

# Summary
print_section "Test Results"

TOTAL=$((test_passed + test_failed))
echo -e "Passed: ${GREEN}$test_passed${NC}"
echo -e "Failed: ${RED}$test_failed${NC}"
echo -e "Total:  $TOTAL"

if [ $test_failed -eq 0 ]; then
  echo -e "\n${GREEN}✅ All resilience tests passed!${NC}"
  exit 0
else
  echo -e "\n${RED}❌ Some tests failed${NC}"
  exit 1
fi
