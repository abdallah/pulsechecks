# Getting Started

## Prerequisites

- AWS Account with appropriate permissions
- Terraform >= 1.5
- Python 3.13
- Node.js >= 18
- Google Workspace domain with OAuth credentials

## Required AWS Permissions

Your AWS user/role needs:
- IAM: Create/manage roles and policies
- Lambda: Create/manage functions
- API Gateway: Create/manage HTTP APIs
- DynamoDB: Create/manage tables and indexes
- SNS: Create/manage topics and subscriptions
- EventBridge: Create/manage rules
- CloudFront: Create/manage distributions
- S3: Create/manage buckets
- Cognito: Create/manage user pools
- CloudWatch: Create/manage log groups and alarms

## Setup

### 1. Clone Repository
```bash
git clone https://github.com/your-username/pulsechecks.git
cd pulsechecks
```

### 2. Configure Terraform Variables
```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values
```

### 3. Set up Google OAuth
- Go to [Google Cloud Console](https://console.cloud.google.com/)
- Create OAuth 2.0 credentials
- Add `https://pulsechecks.example.com/callback` to authorized redirect URIs
- Note the Client ID and Client Secret

### 4. Deploy

**Automated (Recommended):**
```bash
git add .
git commit -m "Initial deployment"
git push origin main  # Triggers CI pipeline
```

**Manual:**
```bash
./deploy.sh
```

## Post-Deployment

### Verify Installation
```bash
# Health check
curl https://api.pulsechecks.example.com/health

# Test ping endpoint
curl -X POST https://api.pulsechecks.example.com/ping/{test-token} \
  -d "Deployment test"
```

### Create Your First Check

1. Visit https://pulsechecks.example.com
2. Sign in with Google Workspace
3. Create a team
4. Add a new check with:
   - Name: "Daily Backup"
   - Period: 86400 seconds (24 hours)
   - Grace: 3600 seconds (1 hour)
5. Copy the ping URL and add to your job:
   ```bash
   curl https://api.pulsechecks.example.com/ping/{your-token}
   ```

## Environment Configuration

The system supports multiple environments via the `ENVIRONMENT` variable:

- `dev`: Development with debug logging
- `prod`: Production with optimized settings

Set during deployment:
```bash
export ENVIRONMENT=prod
./deploy.sh
```
