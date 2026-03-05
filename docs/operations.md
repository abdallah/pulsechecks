# Operations Guide

## Monitoring

### Key Metrics

**Lambda Functions:**
- Invocation count and duration
- Error rate and throttling
- Memory utilization

**DynamoDB:**
- Read/write capacity consumption
- Throttling events
- Item count and storage size

**API Gateway:**
- Request count and latency
- 4xx/5xx error rates
- Cache hit ratio

**CloudFront:**
- Request count and data transfer
- Cache hit ratio
- Origin response time

### CloudWatch Alarms

The system includes pre-configured alarms for:
- Lambda function errors (>5% error rate)
- DynamoDB throttling
- API Gateway high latency (>5s)
- Late detection failures

### Health Checks

```bash
# API health
curl https://api.pulsechecks.example.com/health

# Frontend availability
curl -I https://pulsechecks.example.com

# Test ping endpoint
curl -X POST https://api.pulsechecks.example.com/ping/test-token \
  -d "Health check test"
```

## Troubleshooting

### Common Issues

#### 1. Authentication Failures
**Symptoms:** 401 errors, login redirects

**Diagnosis:**
```bash
# Check Cognito configuration
aws cognito-idp describe-user-pool --user-pool-id {pool-id}

# Verify Google OAuth settings
# - Authorized redirect URIs must include https://pulsechecks.example.com/callback
# - Domain allowlist configured correctly
```

**Resolution:**
- Update OAuth redirect URIs in Google Console
- Verify domain allowlist in Terraform variables
- Check Cognito domain configuration

#### 2. Ping Delivery Issues
**Symptoms:** Pings not recorded, 404 errors on ping URLs

**Diagnosis:**
```bash
# Check API Gateway logs
aws logs filter-log-events \
  --log-group-name /aws/apigateway/pulsechecks-api \
  --start-time $(date -d '1 hour ago' +%s)000

# Test ping endpoint directly
curl -v https://api.pulsechecks.example.com/ping/{token}
```

**Resolution:**
- Verify token exists in DynamoDB TokenIndex
- Check Lambda function logs for errors
- Ensure API Gateway routes are configured

#### 3. Late Detection Not Working
**Symptoms:** Checks stuck in "up" status despite missed pings

**Diagnosis:**
```bash
# Check EventBridge rule
aws events describe-rule --name pulsechecks-late-detector

# Check Lambda logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/pulsechecks-late-detector \
  --start-time $(date -d '1 hour ago' +%s)000
```

**Resolution:**
- Verify EventBridge rule is enabled
- Check DynamoDB DueIndex configuration
- Review Lambda function permissions

#### 4. Frontend Not Loading
**Symptoms:** Blank page, 404 errors

**Diagnosis:**
```bash
# Check S3 bucket contents
aws s3 ls s3://pulsechecks-frontend-prod/

# Check CloudFront distribution
aws cloudfront get-distribution --id {distribution-id}
```

**Resolution:**
- Redeploy frontend: `./deploy.sh --frontend-only`
- Create CloudFront invalidation
- Verify S3 bucket policy

### Log Analysis

**API Gateway Logs:**
```bash
aws logs filter-log-events \
  --log-group-name /aws/apigateway/pulsechecks-api \
  --filter-pattern "ERROR" \
  --start-time $(date -d '1 hour ago' +%s)000
```

**Lambda Function Logs:**
```bash
# API Handler
aws logs tail /aws/lambda/pulsechecks-api --follow

# Ping Handler
aws logs tail /aws/lambda/pulsechecks-ping --follow

# Late Detector
aws logs tail /aws/lambda/pulsechecks-late-detector --follow
```

**DynamoDB Metrics:**
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name ConsumedReadCapacityUnits \
  --dimensions Name=TableName,Value=Pulsechecks \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Sum
```

## Maintenance

### Backup and Recovery

**DynamoDB:**
- Point-in-time recovery enabled
- On-demand backups for major changes
- Cross-region replication for disaster recovery

**Configuration:**
- Terraform state in S3 with versioning
- Infrastructure as Code for reproducibility

### Updates and Deployments

**Automated Pipeline:**
```bash
git add .
git commit -m "Update description"
git push origin main  # Triggers CI/CD
```

**Manual Deployment:**
```bash
# Full deployment
./deploy.sh

# Component-specific
./deploy.sh --infrastructure-only
./deploy.sh --backend-only
./deploy.sh --frontend-only
```

**Rollback Procedures:**
```bash
# Infrastructure rollback
cd infra
terraform plan -destroy
terraform apply

# Lambda rollback
aws lambda update-function-code \
  --function-name pulsechecks-api-prod \
  --s3-bucket pulsechecks-deployments \
  --s3-key lambda-backup-{timestamp}.zip

# Frontend rollback
aws s3 sync s3://pulsechecks-frontend-backup/ s3://pulsechecks-frontend-prod/
aws cloudfront create-invalidation \
  --distribution-id {distribution-id} \
  --paths "/*"
```

### Performance Optimization

**DynamoDB:**
- Monitor hot partitions
- Optimize GSI usage
- Consider reserved capacity for predictable workloads

**Lambda:**
- Monitor cold starts
- Adjust memory allocation based on usage
- Use provisioned concurrency for critical functions

**CloudFront:**
- Optimize cache behaviors
- Monitor cache hit ratios
- Configure appropriate TTLs

### Security Maintenance

**Regular Tasks:**
- Rotate OAuth client secrets
- Review IAM permissions
- Update dependencies
- Monitor access logs

**Security Monitoring:**
```bash
# Check for unusual API activity
aws logs filter-log-events \
  --log-group-name /aws/apigateway/pulsechecks-api \
  --filter-pattern "[timestamp, requestId, ip, user, timestamp, method, resource, protocol, status=4*, size, referer, agent]" \
  --start-time $(date -d '24 hours ago' +%s)000

# Monitor failed authentication attempts
aws logs filter-log-events \
  --log-group-name /aws/lambda/pulsechecks-api \
  --filter-pattern "401" \
  --start-time $(date -d '24 hours ago' +%s)000
```

## Disaster Recovery

### RTO/RPO Targets
- **RTO**: 4 hours (infrastructure recreation)
- **RPO**: 1 hour (DynamoDB point-in-time recovery)

### Recovery Procedures

1. **Infrastructure Loss:**
   ```bash
   # Recreate from Terraform
   cd infra
   terraform init
   terraform plan
   terraform apply
   ```

2. **Data Loss:**
   ```bash
   # Restore DynamoDB from backup
   aws dynamodb restore-table-from-backup \
     --target-table-name Pulsechecks \
     --backup-arn {backup-arn}
   ```

3. **Regional Outage:**
   - Deploy to alternate region
   - Update DNS to point to new region
   - Restore data from cross-region backup
