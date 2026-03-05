# Monitoring Cron Jobs and Repetitive Tasks with Pulsechecks

## Overview

Pulsechecks helps you monitor scheduled jobs, cron tasks, and any repetitive processes. Get alerted when jobs fail, run late, or don't run at all.

## Core Concepts

### Check
A monitored task with expected run frequency:
- **Period**: How often the job runs (e.g., every 24 hours)
- **Grace Period**: Extra time allowed before alerting (e.g., 1 hour leeway)
- **Token**: Unique URL your job pings

### Ping Types
- **Success** (`/ping/{token}`): Job completed successfully
- **Fail** (`/ping/{token}/fail`): Job ran but failed
- **Start** (`/ping/{token}/start`): Job started (optional)

### States
- **Up**: Job running on schedule
- **Late**: Job missed deadline or failed
- **Paused**: Monitoring temporarily disabled

---

## Quick Start

### 1. Create a Check

```bash
# Set your API credentials
API_URL="https://api.pulsechecks.example.com"
API_KEY="your-api-key-here"

# Create a team
TEAM_ID=$(curl -s -X POST "$API_URL/teams" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "Production"}' | jq -r '.teamId')

# Create a check for a daily backup job
CHECK=$(curl -s -X POST "$API_URL/teams/$TEAM_ID/checks" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Daily Database Backup",
    "period_seconds": 86400,
    "grace_seconds": 3600
  }')

# Save the ping token
TOKEN=$(echo $CHECK | jq -r '.token')
echo "Ping URL: $API_URL/ping/$TOKEN"
```

### 2. Add to Your Script

```bash
#!/bin/bash
# your-backup-script.sh

PING_URL="https://api.pulsechecks.example.com/ping/<your-token>"

# Run your backup
if pg_dump mydb > backup.sql; then
    # Success - send success ping
    curl -fsS -m 10 "$PING_URL" > /dev/null
else
    # Failed - send failure ping
    curl -fsS -m 10 "$PING_URL/fail" > /dev/null
    exit 1
fi
```

---

## Common Use Cases

### 1. Simple Cron Job (Success/Fail)

**Scenario**: Daily backup at 2 AM, should complete within 1 hour.

```bash
# Create check
curl -X POST "$API_URL/teams/$TEAM_ID/checks" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Daily Backup",
    "period_seconds": 86400,
    "grace_seconds": 3600
  }'

# Cron job (runs at 2 AM daily)
# 0 2 * * * /home/user/backup.sh

# backup.sh
#!/bin/bash
set -e
PING_URL="https://api/ping/TOKEN"

# Run backup
if /usr/local/bin/backup-database.sh; then
    curl -fsS "$PING_URL" > /dev/null
else
    curl -fsS "$PING_URL/fail" > /dev/null
fi
```

### 2. Long-Running Job with Start Signal

**Scenario**: Weekly data processing that takes 2-4 hours.

```bash
# Create check (runs weekly, allow 6 hours)
curl -X POST "$API_URL/teams/$TEAM_ID/checks" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Weekly Data Processing",
    "period_seconds": 604800,
    "grace_seconds": 21600
  }'

# process-data.sh
#!/bin/bash
PING_URL="https://api/ping/TOKEN"

# Signal start
curl -fsS "$PING_URL/start" \
  -H "Content-Type: application/json" \
  -d '{"data": "Started processing at '$(date)'"}' > /dev/null

# Run processing
if python process_data.py; then
    # Success
    curl -fsS "$PING_URL" \
      -H "Content-Type: application/json" \
      -d '{"data": "Processed 1.2M records"}' > /dev/null
else
    # Failed
    curl -fsS "$PING_URL/fail" \
      -H "Content-Type: application/json" \
      -d '{"data": "Error: '$(cat error.log)'"}' > /dev/null
    exit 1
fi
```

### 3. Multi-Step Pipeline

**Scenario**: ETL pipeline with multiple stages.

```bash
# Create checks for each stage
# Stage 1: Extract (every 6 hours)
# Stage 2: Transform (every 6 hours, 30 min after extract)
# Stage 3: Load (every 6 hours, 1 hour after extract)

# etl-pipeline.sh
#!/bin/bash
set -e

EXTRACT_URL="https://api/ping/TOKEN1"
TRANSFORM_URL="https://api/ping/TOKEN2"
LOAD_URL="https://api/ping/TOKEN3"

# Extract
curl -fsS "$EXTRACT_URL/start" > /dev/null
if ./extract.sh; then
    curl -fsS "$EXTRACT_URL" > /dev/null
else
    curl -fsS "$EXTRACT_URL/fail" \
      -d '{"data": "Extract failed: see logs"}' > /dev/null
    exit 1
fi

# Transform
curl -fsS "$TRANSFORM_URL/start" > /dev/null
if ./transform.sh; then
    curl -fsS "$TRANSFORM_URL" > /dev/null
else
    curl -fsS "$TRANSFORM_URL/fail" > /dev/null
    exit 1
fi

# Load
curl -fsS "$LOAD_URL/start" > /dev/null
if ./load.sh; then
    curl -fsS "$LOAD_URL" \
      -d '{"data": "Loaded 50K rows"}' > /dev/null
else
    curl -fsS "$LOAD_URL/fail" > /dev/null
    exit 1
fi
```

### 4. Conditional Execution

**Scenario**: Job only runs if data is available.

```bash
#!/bin/bash
PING_URL="https://api/ping/TOKEN"

# Check if there's work to do
if [ ! -f /tmp/data-ready ]; then
    # No data to process - still send success ping
    curl -fsS "$PING_URL" \
      -d '{"data": "No data to process"}' > /dev/null
    exit 0
fi

# Process data
if process-data.sh; then
    curl -fsS "$PING_URL" \
      -d '{"data": "Processed data successfully"}' > /dev/null
else
    curl -fsS "$PING_URL/fail" \
      -d '{"data": "Processing failed"}' > /dev/null
    exit 1
fi
```

### 5. Monitoring External Services

**Scenario**: Check if external API is responding.

```bash
#!/bin/bash
# api-health-check.sh (runs every 5 minutes)
# 0 */5 * * * /home/user/api-health-check.sh

PING_URL="https://api/ping/TOKEN"

# Check external API
if curl -fsS -m 10 "https://external-api.com/health" > /dev/null; then
    curl -fsS "$PING_URL" > /dev/null
else
    curl -fsS "$PING_URL/fail" \
      -d '{"data": "API unreachable"}' > /dev/null
fi
```

### 6. Retry Logic with Monitoring

**Scenario**: Retry failed operations but still track attempts.

```bash
#!/bin/bash
PING_URL="https://api/ping/TOKEN"
MAX_RETRIES=3

for i in $(seq 1 $MAX_RETRIES); do
    if ./sync-data.sh; then
        # Success
        MSG="Succeeded on attempt $i"
        curl -fsS "$PING_URL" -d "{\"data\": \"$MSG\"}" > /dev/null
        exit 0
    fi
    
    if [ $i -eq $MAX_RETRIES ]; then
        # Final failure
        curl -fsS "$PING_URL/fail" \
          -d '{"data": "Failed after 3 attempts"}' > /dev/null
        exit 1
    fi
    
    sleep 60  # Wait before retry
done
```

### 7. Database Backup with Rotation

**Scenario**: Daily backup with log data.

```bash
#!/bin/bash
# backup.sh
set -e

PING_URL="https://api/ping/TOKEN"
BACKUP_DIR="/backups"
DATE=$(date +%Y%m%d)

# Start signal
curl -fsS "$PING_URL/start" > /dev/null

# Backup
if pg_dump mydb | gzip > "$BACKUP_DIR/backup-$DATE.sql.gz"; then
    SIZE=$(du -h "$BACKUP_DIR/backup-$DATE.sql.gz" | cut -f1)
    
    # Rotate old backups (keep 7 days)
    find $BACKUP_DIR -name "backup-*.sql.gz" -mtime +7 -delete
    
    # Success with details
    curl -fsS "$PING_URL" \
      -H "Content-Type: application/json" \
      -d "{\"data\": \"Backup completed: $SIZE\"}" > /dev/null
else
    # Failure
    curl -fsS "$PING_URL/fail" \
      -d '{"data": "Backup failed"}' > /dev/null
    exit 1
fi
```

### 8. Certificate Renewal Monitoring

**Scenario**: Let's Encrypt renewal (monthly check).

```bash
#!/bin/bash
# certbot-renew.sh
PING_URL="https://api/ping/TOKEN"

# Attempt renewal
OUTPUT=$(certbot renew 2>&1)

if [ $? -eq 0 ]; then
    # Success
    curl -fsS "$PING_URL" \
      -d "{\"data\": \"Certs checked/renewed\"}" > /dev/null
else
    # Failed
    curl -fsS "$PING_URL/fail" \
      -d "{\"data\": \"Renewal failed: $OUTPUT\"}" > /dev/null
    exit 1
fi
```

---

## Best Practices

### 1. Choose the Right Period and Grace Time

```bash
# Hourly job - allow 10 minutes grace
period_seconds=3600
grace_seconds=600

# Daily job at 2 AM - allow 1 hour grace
period_seconds=86400
grace_seconds=3600

# Weekly job on Sunday - allow 4 hours grace
period_seconds=604800
grace_seconds=14400

# Every 5 minutes - allow 2 minutes grace
period_seconds=300
grace_seconds=120
```

### 2. Always Use Timeouts

```bash
# Good - will timeout after 10 seconds
curl -fsS -m 10 "$PING_URL" > /dev/null

# Bad - might hang forever
curl "$PING_URL"
```

### 3. Include Useful Log Data

```bash
# Good - provides context
curl -fsS "$PING_URL" \
  -H "Content-Type: application/json" \
  -d "{\"data\": \"Processed 1000 rows in 45s\"}" > /dev/null

# Also good for failures
curl -fsS "$PING_URL/fail" \
  -H "Content-Type: application/json" \
  -d "{\"data\": \"Error: $(tail -1 error.log)\"}" > /dev/null
```

### 4. Handle Ping Failures Gracefully

```bash
# Good - don't fail the job if ping fails
curl -fsS -m 10 "$PING_URL" > /dev/null || true

# Better - retry once
ping_with_retry() {
    curl -fsS -m 10 "$1" > /dev/null || \
    sleep 5 && curl -fsS -m 10 "$1" > /dev/null || true
}

ping_with_retry "$PING_URL"
```

### 5. Use Start Signals for Long Jobs

```bash
# For jobs > 30 minutes, signal start
if [ $EXPECTED_DURATION -gt 1800 ]; then
    curl -fsS "$PING_URL/start" > /dev/null
fi
```

---

## Integration Patterns

### Systemd Service

```ini
# /etc/systemd/system/backup.service
[Unit]
Description=Daily Backup
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/backup.sh
Environment="PING_URL=https://api/ping/TOKEN"

[Install]
WantedBy=multi-user.target
```

```bash
# /etc/systemd/system/backup.timer
[Unit]
Description=Daily Backup Timer

[Timer]
OnCalendar=daily
OnCalendar=02:00
Persistent=true

[Install]
WantedBy=timers.target
```

### Docker Container

```dockerfile
FROM alpine:latest
RUN apk add --no-cache curl
COPY backup.sh /backup.sh
ENV PING_URL=""
CMD ["/backup.sh"]
```

### Python Script

```python
#!/usr/bin/env python3
import requests
import sys

PING_URL = "https://api/ping/TOKEN"

try:
    # Your task here
    result = run_task()
    
    # Success
    requests.post(f"{PING_URL}", 
                  json={"data": f"Processed {result['count']} items"},
                  timeout=10)
except Exception as e:
    # Failure
    requests.post(f"{PING_URL}/fail",
                  json={"data": str(e)},
                  timeout=10)
    sys.exit(1)
```

### Node.js Script

```javascript
#!/usr/bin/env node
const https = require('https');

const PING_URL = 'https://api/ping/TOKEN';

async function ping(path = '', data = null) {
  const url = new URL(path, PING_URL);
  const options = {
    method: data ? 'POST' : 'GET',
    timeout: 10000
  };
  
  if (data) {
    options.headers = {'Content-Type': 'application/json'};
  }
  
  return new Promise((resolve, reject) => {
    const req = https.request(url, options, resolve);
    req.on('error', reject);
    if (data) req.write(JSON.stringify({data}));
    req.end();
  });
}

async function main() {
  try {
    await runTask();
    await ping('', 'Task completed successfully');
  } catch (error) {
    await ping('/fail', `Error: ${error.message}`);
    process.exit(1);
  }
}

main();
```

---

## Timing Recommendations

| Job Frequency | Period | Grace Period | Use Case |
|--------------|--------|--------------|----------|
| Every 5 min | 300s | 60-120s | Health checks, monitoring |
| Every 15 min | 900s | 180s | Frequent syncs |
| Hourly | 3600s | 600s | Regular processing |
| Every 6 hours | 21600s | 1800s | Periodic updates |
| Daily | 86400s | 3600s | Backups, reports |
| Weekly | 604800s | 14400s | Maintenance, cleanups |
| Monthly | 2592000s | 86400s | Billing, archival |

---

## Troubleshooting

### Job Runs But No Ping Received

```bash
# Test ping manually
curl -v "https://api/ping/TOKEN"

# Check for network issues
curl -v -m 10 "https://api/ping/TOKEN" || echo "Timeout or failure"

# Verify token is correct
echo $TOKEN
```

### False Alerts

```bash
# Job takes longer than expected
# Solution: Increase grace period

# Job runs at irregular times
# Solution: Use start signal + longer grace period

# Network issues prevent ping
# Solution: Add retry logic
```

### Monitoring the Monitor

```bash
# Create a check to verify ping infrastructure
# Simple script that just sends a ping every 5 minutes

#!/bin/bash
# meta-monitor.sh (runs every 5 minutes)
PING_URL="https://api/ping/META_TOKEN"
curl -fsS -m 10 "$PING_URL" > /dev/null || true
```

---

## API Reference

### Create Check

```bash
curl -X POST "$API_URL/teams/$TEAM_ID/checks" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Check",
    "period_seconds": 86400,
    "grace_seconds": 3600
  }'
```

### Send Pings

```bash
# Success (GET)
curl "$PING_URL"

# Success (POST with data)
curl -X POST "$PING_URL" \
  -H "Content-Type: application/json" \
  -d '{"data": "Job completed: 1000 records"}'

# Failure
curl -X POST "$PING_URL/fail" \
  -H "Content-Type: application/json" \
  -d '{"data": "Error: database connection failed"}'

# Start
curl -X POST "$PING_URL/start" \
  -H "Content-Type: application/json" \
  -d '{"data": "Starting long-running process"}'
```

### View Ping History

```bash
curl "$API_URL/teams/$TEAM_ID/checks/$CHECK_ID/pings" \
  -H "Authorization: Bearer $API_KEY"
```

### Pause/Resume Monitoring

```bash
# Pause (during maintenance)
curl -X POST "$API_URL/teams/$TEAM_ID/checks/$CHECK_ID/pause" \
  -H "Authorization: Bearer $API_KEY"

# Resume
curl -X POST "$API_URL/teams/$TEAM_ID/checks/$CHECK_ID/resume" \
  -H "Authorization: Bearer $API_KEY"
```

---

## Security Notes

1. **Keep tokens secret** - they allow unauthenticated pings
2. **Use HTTPS** - tokens are sent in URL
3. **Rotate tokens** if compromised (update check to generate new token)
4. **Don't log tokens** in verbose cron output
5. **Store in environment variables** not in code

```bash
# Good - token in environment
export PING_TOKEN="your-secret-token"
curl "https://api/ping/$PING_TOKEN"

# Bad - token in script
curl "https://api/ping/exposed-in-version-control"
```
