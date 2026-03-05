# API Reference

## Authentication

All endpoints (except `/health` and `/ping/*`) require JWT authentication:
```
Authorization: Bearer <JWT_TOKEN>
```

## Base URLs

- **Production**: `https://api.pulsechecks.example.com`
- **Development**: `http://localhost:3001`

## Endpoints

### Health Check

#### GET /health
Health check endpoint (no authentication required)

**Response:**
```json
{"status": "ok"}
```

### User Management

#### GET /me
Get current user profile

**Response:**
```json
{
  "userId": "user_123",
  "email": "user@example.com",
  "name": "John Doe",
  "createdAt": "2024-01-01T00:00:00Z",
  "lastLoginAt": "2024-01-02T10:30:00Z"
}
```

### Team Management

#### POST /teams
Create a new team

**Request:**
```json
{"name": "Development Team"}
```

**Response:**
```json
{
  "teamId": "team_456",
  "name": "Development Team",
  "role": "admin",
  "createdAt": "2024-01-01T00:00:00Z"
}
```

#### GET /teams
List all teams for current user

**Response:**
```json
[
  {
    "teamId": "team_456",
    "name": "Development Team",
    "role": "admin",
    "memberCount": 3,
    "checkCount": 5
  }
]
```

#### GET /teams/{teamId}/members
List team members

**Response:**
```json
[
  {
    "userId": "user_123",
    "email": "admin@example.com",
    "name": "Admin User",
    "role": "admin",
    "joinedAt": "2024-01-01T00:00:00Z"
  }
]
```

#### POST /teams/{teamId}/members
Add team member

**Request:**
```json
{
  "email": "newuser@example.com",
  "role": "member"
}
```

### Check Management

#### GET /teams/{teamId}/checks
List checks for a team

**Response:**
```json
[
  {
    "checkId": "check_789",
    "name": "Daily Backup",
    "status": "up",
    "periodSeconds": 86400,
    "graceSeconds": 3600,
    "lastPingAt": "2024-01-02T09:00:00Z",
    "nextDueAt": "2024-01-03T10:00:00Z",
    "createdAt": "2024-01-01T00:00:00Z"
  }
]
```

#### POST /teams/{teamId}/checks
Create a new check

**Request:**
```json
{
  "name": "Daily Backup",
  "periodSeconds": 86400,
  "graceSeconds": 3600,
  "alertChannels": ["channel_123"]
}
```

**Response:**
```json
{
  "checkId": "check_789",
  "name": "Daily Backup",
  "status": "new",
  "periodSeconds": 86400,
  "graceSeconds": 3600,
  "token": "abc123def456",
  "pingUrl": "https://api.pulsechecks.example.com/ping/abc123def456",
  "alertChannels": ["channel_123"],
  "createdAt": "2024-01-02T10:00:00Z"
}
```

#### GET /teams/{teamId}/checks/{checkId}
Get check details

**Response:**
```json
{
  "checkId": "check_789",
  "name": "Daily Backup",
  "status": "up",
  "periodSeconds": 86400,
  "graceSeconds": 3600,
  "token": "abc123def456",
  "pingUrl": "https://api.pulsechecks.example.com/ping/abc123def456",
  "lastPingAt": "2024-01-02T09:00:00Z",
  "nextDueAt": "2024-01-03T10:00:00Z",
  "alertAfterAt": "2024-01-03T11:00:00Z",
  "alertChannels": ["channel_123"],
  "createdAt": "2024-01-01T00:00:00Z"
}
```

#### PATCH /teams/{teamId}/checks/{checkId}
Update check configuration

**Request:**
```json
{
  "name": "Updated Backup Job",
  "periodSeconds": 43200,
  "graceSeconds": 1800
}
```

#### POST /teams/{teamId}/checks/{checkId}/pause
Pause monitoring for a check

#### POST /teams/{teamId}/checks/{checkId}/resume
Resume monitoring for a check

#### POST /teams/{teamId}/checks/{checkId}/rotate-token
Generate new token for a check

**Response:**
```json
{
  "token": "new123token456",
  "pingUrl": "https://api.pulsechecks.example.com/ping/new123token456"
}
```

#### DELETE /teams/{teamId}/checks/{checkId}
Delete a check (removes all ping history)

### Ping History

#### GET /teams/{teamId}/checks/{checkId}/pings
Get ping history for a check

**Query Parameters:**
- `limit`: Number of pings to return (default: 50, max: 100)

**Response:**
```json
[
  {
    "receivedAt": "2024-01-02T09:00:00Z",
    "data": "Backup completed: 1.2GB"
  }
]
```

### Ping Endpoint (No Authentication)

#### GET /ping/{token}
#### POST /ping/{token}
Record a ping for monitoring

**POST Body (optional):**
Any text data describing the job status

**Response:**
```json
{"status": "ok"}
```

**Usage Examples:**
```bash
# Simple ping
curl https://api.pulsechecks.example.com/ping/abc123def456

# With status data
curl -X POST https://api.pulsechecks.example.com/ping/abc123def456 \
  -H "Content-Type: application/json" \
  -d '{"status": "Backup completed: 1.2GB"}'

# With plain text
curl -X POST https://api.pulsechecks.example.com/ping/abc123def456 \
  -d "Backup completed successfully"
```

### Alert Channels

#### GET /teams/{teamId}/alert-channels
List alert channels for a team

#### POST /teams/{teamId}/alert-channels
Create an alert channel

**Request:**
```json
{
  "name": "Email Alerts",
  "type": "email",
  "config": {
    "email": "alerts@example.com"
  }
}
```

#### GET /shared-alert-channels
List shared alert channels from all teams

## Error Responses

All errors follow this format:
```json
{
  "error": "Error message",
  "code": "ERROR_CODE"
}
```

Common HTTP status codes:
- `400`: Bad Request - Invalid input
- `401`: Unauthorized - Missing or invalid token
- `403`: Forbidden - Insufficient permissions
- `404`: Not Found - Resource doesn't exist
- `409`: Conflict - Resource already exists
- `500`: Internal Server Error
