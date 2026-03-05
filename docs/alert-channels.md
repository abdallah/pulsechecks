# Alert Channels Guide

Alert channels define how and where notifications are sent when checks fail or recover. Pulsechecks supports multiple notification types and allows sharing channels across teams.

## Channel Types

### SNS (Amazon Simple Notification Service)
Send notifications via AWS SNS topics to email, SMS, or other AWS services.

**Configuration:**
```json
{
  "name": "email-alerts",
  "displayName": "Email Alerts",
  "type": "sns",
  "configuration": {
    "topicArn": "arn:aws:sns:us-east-1:123456789012:pulsechecks-alerts",
    "region": "us-east-1"
  },
  "shared": false
}
```

**Setup Steps:**
1. Create SNS topic in AWS Console
2. Add email/SMS subscriptions to the topic
3. Note the topic ARN
4. Create alert channel with the ARN

### Mattermost
Send notifications to Mattermost channels via webhooks.

**Configuration:**
```json
{
  "name": "dev-team-alerts",
  "displayName": "Dev Team Alerts",
  "type": "mattermost",
  "configuration": {
    "webhookUrl": "https://mattermost.company.com/hooks/abc123def456",
    "channel": "#alerts",
    "username": "Pulsechecks"
  },
  "shared": true
}
```

**Setup Steps:**
1. Go to Mattermost → Integrations → Incoming Webhooks
2. Create new webhook for your channel
3. Copy the webhook URL
4. Create alert channel with the webhook URL

### Telegram
Send notifications to Telegram chats via bot API.

**Configuration:**
```json
{
  "name": "ops-telegram",
  "displayName": "Operations Telegram",
  "type": "telegram",
  "configuration": {
    "botToken": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
    "chatId": "-1001234567890"
  },
  "shared": false
}
```

**Setup Steps:**
1. Create Telegram bot via @BotFather
2. Get bot token
3. Add bot to your group/channel
4. Get chat ID (use @userinfobot or API)
5. Create alert channel with bot token and chat ID

## Managing Alert Channels

### Create Alert Channel

**API Endpoint:** `POST /teams/{teamId}/alert-channels`

**Request:**
```bash
curl -X POST https://api.pulsechecks.example.com/teams/team_123/alert-channels \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "email-alerts",
    "displayName": "Email Alerts",
    "type": "sns",
    "configuration": {
      "topicArn": "arn:aws:sns:us-east-1:123456789012:alerts"
    },
    "shared": false
  }'
```

**Response:**
```json
{
  "channelId": "channel_456",
  "teamId": "team_123",
  "name": "email-alerts",
  "displayName": "Email Alerts",
  "type": "sns",
  "configuration": {
    "topicArn": "arn:aws:sns:us-east-1:123456789012:alerts"
  },
  "shared": false,
  "createdAt": "2024-01-02T10:00:00Z",
  "createdBy": "user_789"
}
```

### List Alert Channels

**API Endpoint:** `GET /teams/{teamId}/alert-channels`

**Request:**
```bash
curl https://api.pulsechecks.example.com/teams/team_123/alert-channels \
  -H "Authorization: Bearer $JWT_TOKEN"
```

**Response:**
```json
[
  {
    "channelId": "channel_456",
    "teamId": "team_123",
    "name": "email-alerts",
    "displayName": "Email Alerts",
    "type": "sns",
    "configuration": {
      "topicArn": "arn:aws:sns:us-east-1:123456789012:alerts"
    },
    "shared": false,
    "createdAt": "2024-01-02T10:00:00Z",
    "createdBy": "user_789"
  }
]
```

### List Shared Alert Channels

**API Endpoint:** `GET /shared-alert-channels`

**Request:**
```bash
curl https://api.pulsechecks.example.com/shared-alert-channels \
  -H "Authorization: Bearer $JWT_TOKEN"
```

**Response:**
```json
[
  {
    "channelId": "channel_789",
    "teamId": "team_456",
    "teamName": "Operations Team",
    "name": "ops-mattermost",
    "displayName": "Operations Mattermost",
    "type": "mattermost",
    "shared": true,
    "createdAt": "2024-01-01T12:00:00Z"
  }
]
```

### Update Alert Channel

**API Endpoint:** `PATCH /teams/{teamId}/alert-channels/{channelId}`

**Request:**
```bash
curl -X PATCH https://api.pulsechecks.example.com/teams/team_123/alert-channels/channel_456 \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "displayName": "Updated Email Alerts",
    "shared": true
  }'
```

### Delete Alert Channel

**API Endpoint:** `DELETE /teams/{teamId}/alert-channels/{channelId}`

**Request:**
```bash
curl -X DELETE https://api.pulsechecks.example.com/teams/team_123/alert-channels/channel_456 \
  -H "Authorization: Bearer $JWT_TOKEN"
```

## Using Alert Channels with Checks

### Assign Channels to Check

When creating or updating a check, specify alert channels:

```bash
curl -X POST https://api.pulsechecks.example.com/teams/team_123/checks \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Daily Backup",
    "periodSeconds": 86400,
    "graceSeconds": 3600,
    "alertChannels": ["channel_456", "channel_789"]
  }'
```

### Multiple Channel Types

You can assign multiple channels of different types to a single check:

```json
{
  "alertChannels": [
    "sns-email-channel",
    "mattermost-dev-channel", 
    "telegram-ops-channel"
  ]
}
```

## Shared Alert Channels

Shared channels can be used by any team, allowing centralized notification management.

### Benefits
- **Centralized Management**: Operations team manages shared channels
- **Consistency**: Same notification format across teams
- **Reduced Duplication**: Avoid creating identical channels per team

### Permissions
- **Create Shared**: Only team admins can create shared channels
- **Use Shared**: Any team can use existing shared channels
- **Modify Shared**: Only the owning team can modify shared channels

### Example Workflow
1. Operations team creates shared Mattermost channel for `#alerts`
2. Development teams can use this channel for their checks
3. All alerts go to the same place for centralized monitoring

## Notification Format

### SNS Notifications
```json
{
  "Subject": "Pulsechecks Alert: Daily Backup is DOWN",
  "Message": {
    "checkName": "Daily Backup",
    "teamName": "Development Team",
    "status": "DOWN",
    "lastPingAt": "2024-01-02T09:00:00Z",
    "nextDueAt": "2024-01-03T10:00:00Z",
    "alertAfterAt": "2024-01-03T11:00:00Z",
    "checkUrl": "https://pulsechecks.example.com/teams/team_123/checks/check_456"
  }
}
```

### Mattermost Notifications
```markdown
🔴 **ALERT: Daily Backup is DOWN**

**Team:** Development Team
**Last Ping:** 2024-01-02 09:00:00 UTC
**Expected By:** 2024-01-03 10:00:00 UTC
**Grace Period:** 1 hour

[View Check](https://pulsechecks.example.com/teams/team_123/checks/check_456)
```

### Telegram Notifications
```
🔴 ALERT: Daily Backup is DOWN

Team: Development Team
Last Ping: 2024-01-02 09:00:00 UTC
Expected By: 2024-01-03 10:00:00 UTC

View: https://pulsechecks.example.com/teams/team_123/checks/check_456
```

## Best Practices

### Channel Naming
- Use descriptive names: `email-critical-alerts`, `slack-dev-team`
- Include team/purpose: `ops-mattermost`, `dev-telegram`
- Avoid generic names: `alerts`, `notifications`

### Channel Organization
- **Critical Alerts**: Use SNS for email/SMS to ensure delivery
- **Team Notifications**: Use Mattermost/Telegram for team channels
- **Escalation**: Create separate channels for escalated alerts

### Shared Channel Strategy
- Create shared channels for common destinations
- Use team-specific channels for sensitive alerts
- Document shared channel purposes and ownership

### Testing
Always test new alert channels:

```bash
# Create a test check with short period
curl -X POST https://api.pulsechecks.example.com/teams/team_123/checks \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -d '{
    "name": "Test Alert Channel",
    "periodSeconds": 300,
    "graceSeconds": 60,
    "alertChannels": ["your-new-channel-id"]
  }'

# Let it fail to trigger alert, then delete the test check
```

## Troubleshooting

### SNS Issues
- **Permission Denied**: Ensure Pulsechecks has `sns:Publish` permission
- **Topic Not Found**: Verify topic ARN and region
- **No Notifications**: Check topic subscriptions and filters

### Mattermost Issues
- **Webhook Failed**: Verify webhook URL and channel permissions
- **Messages Not Appearing**: Check channel name format (`#channel` or `@user`)
- **Bot Permissions**: Ensure webhook can post to the channel

### Telegram Issues
- **Bot Token Invalid**: Regenerate token from @BotFather
- **Chat ID Wrong**: Use @userinfobot to get correct chat ID
- **Bot Not in Group**: Add bot to group and give posting permissions

### General Issues
- **Channel Not Found**: Verify channel ID exists and team has access
- **Permission Denied**: Ensure user has admin role to manage channels
- **Configuration Invalid**: Check required fields for channel type
