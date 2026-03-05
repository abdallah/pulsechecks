# Pulsechecks Troubleshooting Guide

## Common Issues

### 1. Ping Endpoint Returns 500 Error

**Symptoms:**
- `POST /ping/{token}` returns HTTP 500
- CloudWatch logs show validation errors

**Causes & Solutions:**
```bash
# Check Lambda logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/pulsechecks-ping-prod \
  --start-time $(date -d '1 hour ago' +%s)000

# Common fixes:
# 1. Invalid token format
# 2. Pydantic validation errors
# 3. DynamoDB connection issues
```

**Resolution:**
- Verify token exists in database
- Check request payload format
- Validate DynamoDB table permissions

### 2. Authentication Failures

**Symptoms:**
- `/me` endpoint returns 401 Unauthorized
- JWT validation errors in logs

**Causes:**
- Expired JWT tokens
- Missing cryptography dependency
- Cognito configuration issues

**Resolution:**
```bash
# Check Cognito configuration
aws cognito-idp describe-user-pool --user-pool-id {pool-id}

# Verify JWT algorithm support
# Ensure cryptography==44.0.0 is in Lambda package
```

### 3. Late Detection Not Working

**Symptoms:**
- Checks remain "up" when they should be "late"
- No alerts being sent

**Diagnosis:**
```bash
# Check EventBridge rule
aws events describe-rule --name pulsechecks-late-detector-prod

# Check Lambda invocations
aws logs filter-log-events \
  --log-group-name /aws/lambda/pulsechecks-late-detector-prod \
  --filter-pattern "checksProcessed"
```

**Common Fixes:**
- Verify EventBridge rule is enabled
- Check DynamoDB GSI permissions
- Validate alert topic ARNs

### 4. Alerts Not Being Delivered

**Symptoms:**
- Checks go late but no notifications received
- SNS publish errors in logs

**Diagnosis:**
```bash
# Check SNS topic subscriptions
aws sns list-subscriptions-by-topic --topic-arn {topic-arn}

# Check SNS delivery status
aws sns get-topic-attributes --topic-arn {topic-arn}
```

**Resolution:**
- Verify SNS topic permissions
- Check email subscription confirmations
- Test Mattermost webhook URLs

### 5. Frontend Not Loading

**Symptoms:**
- Blank page or loading spinner
- Console errors in browser

**Diagnosis:**
```bash
# Check CloudFront distribution
aws cloudfront get-distribution --id {distribution-id}

# Check S3 bucket contents
aws s3 ls s3://pulsechecks-frontend-prod/
```

**Common Fixes:**
- Verify S3 bucket policy
- Check CloudFront cache invalidation
- Validate API Gateway CORS settings

## Performance Issues

### High Lambda Cold Start Times

**Symptoms:**
- API responses > 5 seconds
- Timeout errors

**Solutions:**
- Increase Lambda memory (current: 256MB)
- Enable provisioned concurrency for critical functions
- Optimize package size (current: ~64MB)

### DynamoDB Throttling

**Symptoms:**
- `ProvisionedThroughputExceededException` errors
- Slow query responses

**Diagnosis:**
```bash
# Check table metrics
aws dynamodb describe-table --table-name pulsechecks-prod

# Monitor consumed capacity
aws logs filter-log-events \
  --log-group-name /aws/lambda/pulsechecks-api-prod \
  --filter-pattern "ConsumedCapacity"
```

**Solutions:**
- Switch to on-demand billing mode
- Add DynamoDB auto-scaling
- Optimize query patterns

## Monitoring & Debugging

### Key CloudWatch Metrics

```bash
# Lambda errors
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=pulsechecks-api-prod \
  --start-time $(date -d '1 hour ago' -u +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum

# DynamoDB throttles
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name UserErrors \
  --dimensions Name=TableName,Value=pulsechecks-prod \
  --start-time $(date -d '1 hour ago' -u +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum
```

### Log Analysis

```bash
# Find recent errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/pulsechecks-api-prod \
  --filter-pattern "ERROR" \
  --start-time $(date -d '1 hour ago' +%s)000

# Track business events
aws logs filter-log-events \
  --log-group-name /aws/lambda/pulsechecks-late-detector-prod \
  --filter-pattern "late_detection_run" \
  --start-time $(date -d '24 hours ago' +%s)000
```

### Health Checks

```bash
# API health
curl https://api.pulsechecks.example.com/health

# Test ping endpoint
curl -X POST https://api.pulsechecks.example.com/ping/{test-token} \
  -d "Health check test"

# Check late detection
aws lambda invoke \
  --function-name pulsechecks-late-detector-prod \
  --payload '{}' \
  response.json && cat response.json
```

## Emergency Procedures

### System Down - Complete Outage

1. **Check AWS Service Health**
   - Visit AWS Service Health Dashboard
   - Check region-specific issues

2. **Verify Core Services**
   ```bash
   # API Gateway
   aws apigateway get-rest-apis
   
   # Lambda functions
   aws lambda list-functions --query 'Functions[?contains(FunctionName, `pulsechecks`)]'
   
   # DynamoDB
   aws dynamodb describe-table --table-name pulsechecks-prod
   ```

3. **Emergency Rollback**
   ```bash
   # Revert to previous Lambda version
   aws lambda update-function-code \
     --function-name pulsechecks-api-prod \
     --s3-bucket {backup-bucket} \
     --s3-key lambda-backup-{timestamp}.zip
   ```

### Mass Alert Failure

1. **Stop Late Detection**
   ```bash
   aws events disable-rule --name pulsechecks-late-detector-prod
   ```

2. **Check SNS Topics**
   ```bash
   aws sns list-topics --query 'Topics[?contains(TopicArn, `pulsechecks`)]'
   ```

3. **Manual Alert Test**
   ```bash
   aws sns publish \
     --topic-arn {topic-arn} \
     --subject "Test Alert" \
     --message "Manual test message"
   ```

## Contact Information

- **Primary**: Check CloudWatch alarms first
- **Escalation**: Review this troubleshooting guide
- **Emergency**: AWS Support (if infrastructure issue)

## Useful Commands Reference

```bash
# Quick system status
./scripts/health-check.sh

# View recent logs
./scripts/tail-logs.sh [function-name]

# Deploy emergency fix
./deploy.sh --emergency

# Database backup
./scripts/backup-dynamodb.sh
```
