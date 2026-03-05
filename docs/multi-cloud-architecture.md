# Multi-Cloud Architecture

Pulsechecks supports deployment to both AWS and GCP using a single codebase with cloud-specific abstractions.

## Overview

The application uses an abstraction layer pattern to support multiple cloud providers without code duplication. The core business logic remains unchanged, while cloud-specific implementations handle platform differences.

## Design Principles

1. **Single Codebase**: One backend, one frontend that works on both clouds
2. **Abstraction Layers**: Database and authentication interfaces with provider-specific implementations
3. **Configuration-Driven**: Cloud provider selection via environment variables
4. **Feature Parity**: All features work identically on both platforms
5. **No Vendor Lock-in**: Easy migration between clouds if needed

## Architecture Patterns

### Repository Pattern (Database)

All database operations go through a common `DatabaseInterface`:

```python
# Abstract interface
class DatabaseInterface(ABC):
    @abstractmethod
    async def create_check(self, check: Check) -> None:
        pass

    @abstractmethod
    async def get_check(self, check_id: str) -> Optional[Check]:
        pass
    # ... 39 more methods

# Cloud-specific implementations
class DynamoDBClient(DatabaseInterface):
    # AWS DynamoDB implementation
    pass

class FirestoreClient(DatabaseInterface):
    # GCP Firestore implementation
    pass
```

### Factory Pattern (Client Creation)

Clients are instantiated based on configuration:

```python
def create_db_client() -> DatabaseInterface:
    settings = get_settings()
    if settings.cloud_provider == "aws":
        return DynamoDBClient()
    elif settings.cloud_provider == "gcp":
        return FirestoreClient()
```

### Authentication Abstraction

JWT verification abstracted to support both Cognito and Firebase:

```python
class AuthInterface(ABC):
    @abstractmethod
    async def verify_token(self, token: str) -> Dict:
        pass

class CognitoAuth(AuthInterface):
    # AWS Cognito JWT verification
    pass

class FirebaseAuth(AuthInterface):
    # Firebase JWT verification
    pass
```

## Cloud Service Mapping

### AWS Stack

| Component          | Service                | Purpose                        |
| ------------------ | ---------------------- | ------------------------------ |
| **API**            | Lambda + API Gateway   | Request handling               |
| **Ping Handler**   | Lambda                 | Dedicated ping ingestion       |
| **Late Detector**  | Lambda + EventBridge   | Check late detection (2 min)   |
| **Database**       | DynamoDB               | Single-table design            |
| **Authentication** | Cognito                | Google OAuth via Identity Pool |
| **Frontend**       | S3 + CloudFront        | Static site hosting            |
| **Monitoring**     | CloudWatch             | Logs and metrics               |
| **Notifications**  | SNS                    | Alert delivery                 |

**Architecture:**
- 3 separate Lambda functions (API, Ping, Late Detector)
- DynamoDB single-table with GSI indexes
- EventBridge rule triggers late detector every 2 minutes
- Cognito Hosted UI for OAuth flow

### GCP Stack

| Component          | Service            | Purpose                        |
| ------------------ | ------------------ | ------------------------------ |
| **API**            | Cloud Run          | Single container service       |
| **Late Detector**  | Cloud Scheduler    | HTTP trigger to Cloud Run      |
| **Database**       | Firestore Native   | Collection-based structure     |
| **Authentication** | Firebase Auth      | Google OAuth via Identity      |
| **Frontend**       | Firebase Hosting   | Static site with CDN           |
| **Monitoring**     | Cloud Logging      | Structured logging             |
| **Notifications**  | Cloud Pub/Sub      | Alert delivery                 |

**Architecture:**
- Single Cloud Run service handling all routes
- Firestore with collection/subcollection structure
- Cloud Scheduler sends HTTP POST every 2 minutes
- Firebase Hosting with automatic CDN

## Data Model Mapping

### DynamoDB → Firestore

DynamoDB's single-table design maps to Firestore's collection structure:

```
DynamoDB Single Table              Firestore Collections
═══════════════════════════════    ═════════════════════════════════

PK: USER#{id}                  →   users/{userId}
SK: PROFILE                        (document fields)

PK: TEAM#{id}                  →   teams/{teamId}
SK: PROFILE                        (document fields)

PK: TEAM#{id}                  →   teams/{teamId}/members/{userId}
SK: MEMBER#{userId}                (subcollection)

PK: CHECK#{id}                 →   checks/{checkId}
SK: CHECK                          (document fields)

PK: CHECK#{id}                 →   checks/{checkId}/pings/{pingId}
SK: PING#{timestamp}               (subcollection with TTL)

PK: TEAM#{id}                  →   teams/{teamId}/channels/{channelId}
SK: CHANNEL#{id}                   (subcollection)

GSI1 (DueIndex)                →   Firestore composite index
PK: CHECK#{id}                     on (alertAfterAt, teamId)
SK: alertAfterAt

GSI2 (TokenIndex)              →   Firestore composite index
PK: token                          on (token)
```

### Key Differences

| Aspect              | DynamoDB                    | Firestore                      |
| ------------------- | --------------------------- | ------------------------------ |
| **Structure**       | Single table with PK/SK     | Collections + subcollections   |
| **Queries**         | GSI for secondary access    | Composite indexes              |
| **Transactions**    | ConditionExpression         | Firestore transactions         |
| **TTL**             | Item-level TTL attribute    | Collection-level TTL policy    |
| **Batch Ops**       | BatchWriteItem (25 items)   | Batch writes (500 operations)  |

## Frontend Configuration

The frontend selects cloud provider at build time:

```javascript
// Build for AWS
VITE_CLOUD_PROVIDER=aws npm run build

// Build for GCP
VITE_CLOUD_PROVIDER=gcp npm run build
```

Configuration files:
- `frontend/src/config/aws.config.js` - AWS Cognito settings
- `frontend/src/config/gcp.config.js` - Firebase settings
- `frontend/src/config.js` - Unified config loader

Authentication automatically uses correct provider:
- **AWS**: Cognito Hosted UI with PKCE
- **GCP**: Firebase signInWithRedirect

## Deployment Strategy

### Infrastructure as Code

Separate Terraform configurations:
- `infra/aws/` - AWS resources
- `infra/gcp/` - GCP resources

### CI/CD Pipeline

GitLab CI/CD variable controls target:
```yaml
variables:
  DEPLOY_TARGET: "aws"  # or "gcp"
```

Deployment jobs conditionally run based on `DEPLOY_TARGET`:
- AWS: Lambda packaging, S3/CloudFront deployment
- GCP: Docker build, Cloud Run deployment, Firebase Hosting

### Manual Deployment

```bash
# Interactive selection
./deploy.sh

# Or specify directly
CLOUD_PROVIDER=aws ./deploy.sh
CLOUD_PROVIDER=gcp ./deploy.sh
```

## Cost Optimization

### AWS Costs (~$10-15/month)

- Lambda: 1M invocations free, then $0.20/1M
- DynamoDB: On-demand pricing ~$1.25/million reads
- API Gateway: 1M requests free, then $1/million
- S3 + CloudFront: ~$1-2/month
- Cognito: 50K MAU free, then $0.0055/MAU

**Optimization strategies:**
- Use Lambda Reserved Concurrency
- Enable DynamoDB auto-scaling
- CloudFront caching aggressive
- Minimize API Gateway calls

### GCP Costs (~$0-2/month with free tier)

- Cloud Run: 2M requests/month FREE
- Firestore: 50K reads, 20K writes/day FREE
- Firebase Auth: 50K MAU FREE
- Firebase Hosting: 10GB storage, 360MB/day FREE
- Cloud Scheduler: 3 jobs FREE
- Cloud Logging: 50GB/month FREE

**Free tier maximization:**
- Cloud Run `min_instances = 0` (scale to zero)
- Stay within Firestore daily limits
- Use Firebase Hosting CDN aggressively
- Maximum 3 Cloud Scheduler jobs

## Migration Between Clouds

### Data Export/Import

1. **Export from source cloud:**
   - AWS: DynamoDB export to S3
   - GCP: Firestore export to Cloud Storage

2. **Transform data structure:**
   - Use provided migration scripts
   - Map single-table to collections (or vice versa)

3. **Import to target cloud:**
   - AWS: DynamoDB import from S3
   - GCP: Firestore import from Cloud Storage

### Configuration Updates

1. Update infrastructure: Run Terraform for target cloud
2. Update application config: Set `CLOUD_PROVIDER` env var
3. Rebuild frontend: Use correct `VITE_CLOUD_PROVIDER`
4. Update DNS: Point to new backend/frontend URLs

## Testing Strategy

### Unit Tests

Tests use mock implementations of interfaces:
```python
class MockDatabase(DatabaseInterface):
    # In-memory implementation for testing
    pass

def test_create_check():
    db = MockDatabase()
    check = Check(...)
    await db.create_check(check)
    assert ...
```

### Integration Tests

- **AWS**: Use DynamoDB Local + Cognito test pool
- **GCP**: Use Firestore Emulator + Firebase Auth Emulator

### End-to-End Tests

Separate test environments for each cloud:
- AWS: `pulsechecks-test` stack
- GCP: `pulsechecks-test` project

## Monitoring and Observability

### Structured Logging

Both platforms use JSON structured logging:
```python
logger.info("Check created", extra={
    "checkId": check.check_id,
    "teamId": check.team_id,
    "cloud_provider": settings.cloud_provider
})
```

### Metrics

- **AWS**: CloudWatch custom metrics
- **GCP**: Cloud Monitoring custom metrics

Common metrics tracked:
- Request count and latency
- Check late detection time
- Alert delivery success rate
- Database operation latency

### Alerts

Platform-specific alert policies:
- **AWS**: CloudWatch Alarms
- **GCP**: Cloud Monitoring Alert Policies

Common alerts:
- High error rate (>5%)
- High latency (>2s p99)
- Late detector failures

## Security Considerations

### Authentication

- Both use OAuth 2.0 with Google as IdP
- JWT tokens verified server-side
- Domain allowlist for organization isolation

### Authorization

- Team-based RBAC (Owner, Member)
- Backend validates all operations
- Frontend config is public, security on backend

### Secrets Management

- **AWS**: SSM Parameter Store or Secrets Manager
- **GCP**: Secret Manager

Never commit:
- OAuth client secrets
- Terraform variable files
- Service account keys

### Network Security

- **AWS**: API Gateway throttling, WAF optional
- **GCP**: Cloud Armor optional, Cloud Run IAM

Both:
- HTTPS only (TLS 1.2+)
- CORS properly configured
- Rate limiting middleware

## Performance Comparison

| Metric           | AWS Lambda      | GCP Cloud Run    |
| ---------------- | --------------- | ---------------- |
| Cold Start       | ~500-800ms      | ~1-2s            |
| Warm Latency     | ~10-50ms        | ~10-30ms         |
| Concurrency      | 1000/function   | 80/container     |
| Scale to Zero    | Yes             | Yes              |
| Max Duration     | 15 minutes      | 60 minutes       |

**Recommendation:**
- **AWS**: Better for spiky, short-duration workloads
- **GCP**: Better for steady, longer-duration workloads

For Pulsechecks (mostly quick requests), both perform similarly.

## Limitations and Trade-offs

### AWS

**Pros:**
- Mature ecosystem with extensive services
- Fine-grained control over infrastructure
- Better VPC networking options

**Cons:**
- Higher cost at low usage
- More complex infrastructure (3 Lambdas vs 1 Cloud Run)
- DynamoDB single-table design has learning curve

### GCP

**Pros:**
- Generous free tier (can run at $0/month)
- Simpler infrastructure (1 Cloud Run service)
- Firebase ecosystem integration

**Cons:**
- Smaller ecosystem than AWS
- Firestore has lower write throughput limits
- Fewer regions than AWS

## Future Enhancements

Potential multi-cloud improvements:

1. **Multi-Cloud Deployment**: Run on both clouds simultaneously with global load balancing
2. **Cross-Cloud Disaster Recovery**: Automatic failover between providers
3. **Hybrid Deployment**: Frontend on one cloud, backend on another
4. **Azure Support**: Add third cloud provider option
5. **Database Replication**: Real-time sync between DynamoDB and Firestore

## Conclusion

The abstraction layer approach provides true multi-cloud portability while maintaining a single codebase. Choose AWS for mature enterprise environments, or GCP for cost optimization and Firebase ecosystem benefits.

Both platforms deliver identical functionality to end users - the choice is purely operational and cost-based.
