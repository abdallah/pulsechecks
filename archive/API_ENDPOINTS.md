# Pulsechecks API Endpoints

## Authentication
All endpoints (except `/health` and `/ping/*`) require JWT authentication via Cognito:
```text
Authorization: Bearer <JWT_TOKEN>
```

## Endpoints

### Health Check
- **GET /health** - Health check endpoint (no auth required)
  - Response: `{"status": "ok"}`

### User Endpoints
- **GET /me** - Get current user profile
  - Response: User profile with userId, email, name, createdAt, lastLoginAt

### Team Endpoints
- **POST /teams** - Create a new team
  - Body: `{"name": "Team Name"}`
  - Response: Team object with teamId, name, role (admin), createdAt

- **GET /teams** - List all teams for current user
  - Response: Array of team objects

### Team Member Management
- **GET /teams/{team_id}/members** - List team members
  - Response: Array of member objects with roles

- **POST /teams/{team_id}/members** - Add member by email
  - Body: `{"email": "user@domain.com", "role": "member"}`
  - Response: Member object or pending invitation

- **DELETE /teams/{team_id}/members/{user_id}** - Remove member
  - Response: `{"ok": true, "message": "Member removed"}`

- **PATCH /teams/{team_id}/members/{user_id}** - Update member role
  - Body: `{"role": "admin"}`
  - Response: Updated member object

### Check Endpoints
All check endpoints are prefixed with `/teams/{team_id}/checks`

- **POST /teams/{team_id}/checks** - Create a check
  - Body: `{"name": "Check Name", "periodSeconds": 3600, "graceSeconds": 300, "alertTopics": ["arn:aws:sns:..."]}`
  - Response: Check detail with checkId, token, status, etc.

- **GET /teams/{team_id}/checks** - List all checks for a team
  - Response: Array of check objects

- **GET /teams/{team_id}/checks/{check_id}** - Get check details
  - Response: Full check details including token

- **PATCH /teams/{team_id}/checks/{check_id}** - Update check
  - Body: `{"name": "New Name", "periodSeconds": 7200, "alertTopics": [...]}`
  - Response: Updated check details

- **POST /teams/{team_id}/checks/{check_id}/pause** - Pause a check
  - Response: `{"ok": true, "message": "Check paused"}`

- **POST /teams/{team_id}/checks/{check_id}/resume** - Resume a check
  - Response: `{"ok": true, "message": "Check resumed"}`

- **POST /teams/{team_id}/checks/{check_id}/rotate-token** - Rotate check token
  - Response: `{"ok": true, "token": "new-token"}`

- **DELETE /teams/{team_id}/checks/{check_id}** - Delete check (cascade deletes pings)
  - Response: `{"ok": true, "message": "Check deleted"}`

- **GET /teams/{team_id}/checks/{check_id}/pings** - List pings for a check
  - Query params: `?limit=20` (optional)
  - Response: Array of ping records

### Alert Management
- **GET /teams/{team_id}/alerts** - List SNS alert topics
  - Response: Array of SNS topic objects

- **POST /teams/{team_id}/alerts** - Create SNS alert topic
  - Body: `{"name": "AlertTopic"}`
  - Response: SNS topic ARN and details

- **DELETE /teams/{team_id}/alerts/{topic_arn}** - Delete alert topic
  - Response: `{"ok": true, "message": "Topic deleted"}`

- **POST /teams/{team_id}/alerts/{topic_arn}/subscribe** - Subscribe to alerts
  - Body: `{"protocol": "email", "endpoint": "user@domain.com"}`
  - Response: Subscription details

### Ping Endpoints
No authentication required - uses token in URL

- **GET /ping/{token}** - Record a ping (GET method)
  - Response: `{"ok": true, "message": "Ping recorded"}`

- **POST /ping/{token}** - Record a ping (POST method)
  - Body: Optional ping data (up to 1000 chars)
  - Response: `{"ok": true, "message": "Ping recorded"}`

- **GET /ping/{token}/start** - Record start ping
- **POST /ping/{token}/start** - Record start ping with data
- **GET /ping/{token}/fail** - Record failure ping
- **POST /ping/{token}/fail** - Record failure ping with data

## Response Status Codes
- **200** - Success
- **201** - Created (for POST requests creating resources)
- **400** - Bad Request (invalid input)
- **401** - Unauthorized (invalid or missing JWT)
- **403** - Forbidden (insufficient permissions)
- **404** - Not Found (resource doesn't exist)
- **422** - Validation Error (invalid request data)
- **500** - Internal Server Error

## Example Usage

### Create a monitoring check
```bash
# 1. Get JWT token from Cognito (via frontend login)
JWT_TOKEN="your-jwt-token"

# 2. Create a team
TEAM_ID=$(curl -s -X POST "https://api.example.com/teams" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "My Team"}' | jq -r '.teamId')

# 3. Create SNS alert topic
TOPIC_ARN=$(curl -s -X POST "https://api.example.com/teams/${TEAM_ID}/alerts" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "DatabaseAlerts"}' | jq -r '.topicArn')

# 4. Create a check with alerts
RESPONSE=$(curl -s -X POST "https://api.example.com/teams/${TEAM_ID}/checks" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"Database Backup\",
    \"periodSeconds\": 86400,
    \"graceSeconds\": 3600,
    \"alertTopics\": [\"$TOPIC_ARN\"]
  }")

TOKEN=$(echo $RESPONSE | jq -r '.token')

# 5. Send pings from your job
curl "https://api.example.com/ping/${TOKEN}"
```

## Testing

Run backend tests:
```bash
cd backend
pytest tests/ -v  # 87 tests, 93% pass rate
```
