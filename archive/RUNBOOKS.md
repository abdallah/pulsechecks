# Pulsechecks Operational Runbooks

## Incident Response Procedures

### Severity Levels

- **P0 (Critical)**: Complete system outage, no pings being processed
- **P1 (High)**: Alerts not being delivered, authentication failures
- **P2 (Medium)**: Performance degradation, partial functionality loss
- **P3 (Low)**: Minor bugs, cosmetic issues

### P0 - Critical System Outage

**Response Time**: Immediate (< 15 minutes)

**Symptoms:**
- API Gateway returning 5xx errors
- All Lambda functions failing
- DynamoDB unavailable

**Immediate Actions:**
1. **Acknowledge incident** - Update status page if available
2. **Check AWS Service Health** - https://status.aws.amazon.com/
3. **Verify infrastructure**:
   ```bash
   # Quick health check
   curl -f https://api.pulsechecks.example.com/health || echo "API DOWN"
   
   # Check Lambda functions
   aws lambda list-functions --query 'Functions[?contains(FunctionName, `pulsechecks`)].State'
   ```

4. **Emergency rollback** if recent deployment:
   ```bash
   # Rollback Lambda functions
   aws lambda update-function-code \
     --function-name pulsechecks-api-prod \
     --s3-bucket pulsechecks-deployments \
     --s3-key lambda-backup-stable.zip
   ```

5. **Escalate** if infrastructure issue

### P1 - Alert System Failure

**Response Time**: < 30 minutes

**Symptoms:**
- Checks going late but no alerts sent
- SNS publish failures
- Mattermost webhooks failing

**Investigation Steps:**
1. **Check late detector function**:
   ```bash
   aws logs filter-log-events \
     --log-group-name /aws/lambda/pulsechecks-late-detector-prod \
     --filter-pattern "ERROR" \
     --start-time $(date -d '1 hour ago' +%s)000
   ```

2. **Verify SNS topics**:
   ```bash
   aws sns list-topics --query 'Topics[?contains(TopicArn, `pulsechecks`)]'
   ```

3. **Test manual alert**:
   ```bash
   aws sns publish \
     --topic-arn arn:aws:sns:us-east-1:123456789:pulsechecks-alerts-team-123 \
     --subject "Test Alert" \
     --message "Manual test - ignore"
   ```

**Resolution:**
- Fix SNS permissions if needed
- Restart EventBridge rule
- Update webhook URLs if changed

### P2 - Performance Issues

**Response Time**: < 1 hour

**Symptoms:**
- API responses > 5 seconds
- Lambda timeouts
- DynamoDB throttling

**Investigation:**
1. **Check Lambda metrics**:
   ```bash
   aws cloudwatch get-metric-statistics \
     --namespace AWS/Lambda \
     --metric-name Duration \
     --dimensions Name=FunctionName,Value=pulsechecks-api-prod \
     --start-time $(date -d '1 hour ago' -u +%Y-%m-%dT%H:%M:%S) \
     --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
     --period 300 \
     --statistics Average,Maximum
   ```

2. **Check DynamoDB throttling**:
   ```bash
   aws cloudwatch get-metric-statistics \
     --namespace AWS/DynamoDB \
     --metric-name ConsumedReadCapacityUnits \
     --dimensions Name=TableName,Value=pulsechecks-prod
   ```

**Mitigation:**
- Increase Lambda memory/timeout
- Enable DynamoDB auto-scaling
- Add caching layer

## Maintenance Procedures

### Planned Maintenance Window

**Frequency**: Monthly (first Sunday, 2-4 AM UTC)

**Pre-maintenance Checklist:**
- [ ] Notify users via status page
- [ ] Backup DynamoDB table
- [ ] Create Lambda function snapshots
- [ ] Verify rollback procedures

**Maintenance Steps:**
1. **Create backups**:
   ```bash
   # DynamoDB backup
   aws dynamodb create-backup \
     --table-name pulsechecks-prod \
     --backup-name "maintenance-$(date +%Y%m%d)"
   
   # Lambda code backup
   aws lambda get-function --function-name pulsechecks-api-prod \
     --query 'Code.Location' --output text | xargs wget -O lambda-backup.zip
   ```

2. **Deploy updates**:
   ```bash
   ./deploy.sh --environment prod
   ```

3. **Verify deployment**:
   ```bash
   # Health checks
   curl https://api.pulsechecks.example.com/health
   
   # Test ping endpoint
   curl -X POST https://api.pulsechecks.example.com/ping/{test-token}
   
   # Verify late detection
   aws lambda invoke \
     --function-name pulsechecks-late-detector-prod \
     --payload '{}' response.json
   ```

### Database Maintenance

**Monthly Tasks:**
1. **Analyze table metrics**:
   ```bash
   aws dynamodb describe-table --table-name pulsechecks-prod \
     --query 'Table.{ItemCount:ItemCount,TableSizeBytes:TableSizeBytes}'
   ```

2. **Clean up old pings** (automated via TTL, verify working):
   ```bash
   # Check TTL status
   aws dynamodb describe-time-to-live --table-name pulsechecks-prod
   ```

3. **Review GSI usage**:
   ```bash
   aws dynamodb describe-table --table-name pulsechecks-prod \
     --query 'Table.GlobalSecondaryIndexes[*].{IndexName:IndexName,ItemCount:ItemCount}'
   ```

### Security Updates

**Quarterly Tasks:**
1. **Update Lambda runtime**:
   ```bash
   # Check current runtime
   aws lambda get-function --function-name pulsechecks-api-prod \
     --query 'Configuration.Runtime'
   
   # Update if needed
   aws lambda update-function-configuration \
     --function-name pulsechecks-api-prod \
     --runtime python3.13
   ```

2. **Rotate secrets**:
   ```bash
   # Generate new API key
   openssl rand -hex 32
   
   # Update in Parameter Store
   aws ssm put-parameter \
     --name "/pulsechecks/prod/api-key" \
     --value "{new-key}" \
     --overwrite
   ```

3. **Review IAM permissions**:
   ```bash
   # Check Lambda execution role
   aws iam get-role-policy \
     --role-name pulsechecks-lambda-exec-prod \
     --policy-name pulsechecks-lambda-policy
   ```

## Monitoring & Alerting Setup

### CloudWatch Alarms

**Critical Alarms:**
```bash
# Lambda errors
aws cloudwatch put-metric-alarm \
  --alarm-name "pulsechecks-lambda-errors" \
  --alarm-description "Lambda function errors" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=FunctionName,Value=pulsechecks-api-prod \
  --evaluation-periods 2

# DynamoDB throttling
aws cloudwatch put-metric-alarm \
  --alarm-name "pulsechecks-dynamodb-throttles" \
  --alarm-description "DynamoDB throttling events" \
  --metric-name UserErrors \
  --namespace AWS/DynamoDB \
  --statistic Sum \
  --period 300 \
  --threshold 1 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=TableName,Value=pulsechecks-prod
```

### Log Monitoring

**Key Log Patterns:**
- `ERROR` - Application errors
- `late_detection_run` - Late detection execution
- `alert_sent` - Alert delivery attempts
- `ConsumedCapacity` - DynamoDB usage

**Log Retention:**
- Lambda logs: 30 days
- Application logs: 90 days
- Audit logs: 1 year

## Disaster Recovery

### RTO/RPO Targets
- **RTO (Recovery Time Objective)**: 4 hours
- **RPO (Recovery Point Objective)**: 1 hour

### Backup Strategy

**Automated Backups:**
- DynamoDB: Point-in-time recovery enabled
- Lambda code: Stored in S3 with versioning
- Infrastructure: Terraform state in S3 with versioning

**Recovery Procedures:**

1. **DynamoDB Recovery**:
   ```bash
   # Restore from point-in-time
   aws dynamodb restore-table-to-point-in-time \
     --source-table-name pulsechecks-prod \
     --target-table-name pulsechecks-recovery \
     --restore-date-time $(date -d '1 hour ago' -u +%Y-%m-%dT%H:%M:%S)
   ```

2. **Lambda Recovery**:
   ```bash
   # Deploy from backup
   aws lambda update-function-code \
     --function-name pulsechecks-api-prod \
     --s3-bucket pulsechecks-backups \
     --s3-key lambda-stable.zip
   ```

3. **Infrastructure Recovery**:
   ```bash
   # Redeploy infrastructure
   cd infra
   terraform init
   terraform plan
   terraform apply
   ```

### Cross-Region Failover

**Manual Failover Process:**
1. Update DNS to point to backup region
2. Deploy infrastructure in backup region
3. Restore DynamoDB from backup
4. Update configuration for new region
5. Verify functionality

## Capacity Planning

### Growth Projections
- **Current**: ~100 checks, 1000 pings/day
- **6 months**: ~500 checks, 5000 pings/day
- **1 year**: ~1000 checks, 10000 pings/day

### Scaling Thresholds
- **Lambda**: Auto-scales, monitor concurrent executions
- **DynamoDB**: On-demand pricing, monitor consumed capacity
- **API Gateway**: 10,000 requests/second limit

### Cost Monitoring
```bash
# Monthly cost estimate
aws ce get-cost-and-usage \
  --time-period Start=$(date -d 'last month' +%Y-%m-01),End=$(date +%Y-%m-01) \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --group-by Type=DIMENSION,Key=SERVICE
```

## Contact Information

**On-Call Rotation:**
- Primary: System administrator
- Secondary: Development team lead
- Escalation: AWS Support

**Communication Channels:**
- Incidents: #pulsechecks-incidents
- Maintenance: #pulsechecks-ops
- General: #pulsechecks

**External Dependencies:**
- AWS Support: Enterprise plan
- DNS Provider: Route 53
- Monitoring: CloudWatch
