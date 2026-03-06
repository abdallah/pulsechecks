# GCP Deployment Guide

Complete guide to deploying Pulsechecks on Google Cloud Platform.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Initial Setup](#initial-setup)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Post-Deployment](#post-deployment)
- [Monitoring](#monitoring)
- [Cost Management](#cost-management)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Tools

Install the following tools before deployment:

```bash
# Google Cloud SDK
# macOS
brew install --cask google-cloud-sdk

# Linux
curl https://sdk.cloud.google.com | bash
exec -l $SHELL

# Windows
# Download from https://cloud.google.com/sdk/docs/install

# Terraform
brew install terraform  # macOS/Linux
# or download from terraform.io

# Firebase CLI
npm install -g firebase-tools

# Docker (for building Cloud Run images)
# Download from https://docs.docker.com/get-docker/
```

### GCP Project Setup

1. **Create GCP Project:**
   ```bash
   gcloud projects create your-project-id --name="Pulsechecks"
   gcloud config set project your-project-id
   ```

2. **Enable Billing:**
   - Go to [GCP Console](https://console.cloud.google.com/billing)
   - Link a billing account to your project
   - Required even for free tier resources

3. **Authenticate:**
   ```bash
   # Authenticate with your Google account
   gcloud auth login

   # Set application default credentials for Terraform
   gcloud auth application-default login

  # Set quota project for ADC (required by identitytoolkit.googleapis.com)
  gcloud auth application-default set-quota-project your-project-id

   # Authenticate Firebase CLI
   firebase login
   ```

### Google OAuth Setup

Create OAuth 2.0 credentials for authentication:

1. Go to [Google Cloud Console > APIs & Services > Credentials](https://console.cloud.google.com/apis/credentials)

2. Click "Create Credentials" → "OAuth 2.0 Client ID"

3. Configure OAuth consent screen:
   - User type: Internal (for workspace) or External
   - App name: Pulsechecks
   - Scopes: email, profile, openid

4. Create OAuth 2.0 Client ID:
   - Application type: Web application
   - Name: Pulsechecks Web
   - Authorized JavaScript origins:
     - `http://localhost:3000` (development)
     - `https://your-domain.com` (production)
   - Authorized redirect URIs:
     - `http://localhost:3000/callback`
     - `https://your-domain.com/callback`

5. Save the **Client ID** and **Client Secret**

## Initial Setup

### 1. Clone Repository

```bash
git clone https://github.com/your-username/pulsechecks.git
cd pulsechecks
```

### 2. Configure Terraform Variables

```bash
cd infra/gcp
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` with your values:

```hcl
# GCP Configuration
gcp_project_id = "your-project-id"
gcp_region     = "us-central1"  # Choose closest region
environment    = "prod"

# Domain Configuration
domain_name     = "pulsechecks.example.com"      # Your frontend domain
api_domain_name = "api.pulsechecks.example.com"  # Your API domain

# Authentication
allowed_email_domains = "example.com,company.com"  # Allowed email domains

# Google OAuth (from previous step)
google_oauth_client_id     = "123456789.apps.googleusercontent.com"
google_oauth_client_secret = "your-client-secret"

# Container Image (will set after building)
container_image = "gcr.io/your-project-id/pulsechecks-api:latest"

# Auto-scaling Configuration
min_instances = 0   # Scale to zero for cost savings
max_instances = 10  # Maximum concurrent instances

# Resource Limits
cpu_limit    = "1000m"  # 1 vCPU
memory_limit = "512Mi"  # 512 MB RAM
```

### 3. Configure Firebase

```bash
cd ../../frontend
```

Update `.firebaserc` with your project:

```json
{
  "projects": {
    "default": "your-project-id"
  }
}
```

## Configuration

### Backend Environment Variables

The Cloud Run service will be configured with these environment variables (set automatically by Terraform):

- `CLOUD_PROVIDER=gcp`
- `GCP_PROJECT=your-project-id`
- `FIRESTORE_DATABASE=(default)`
- `FIREBASE_PROJECT_ID=your-project-id`
- `ALLOWED_EMAIL_DOMAINS=example.com`
- `DEBUG=false`

### Frontend Environment Variables

Create `.env.production` in `frontend/`:

```bash
VITE_CLOUD_PROVIDER=gcp
VITE_API_URL=https://api.pulsechecks.example.com
VITE_FIREBASE_API_KEY=your-firebase-api-key
VITE_FIREBASE_AUTH_DOMAIN=your-project-id.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your-project-id
```

## Deployment

### Option 1: Automated Deployment Script (Recommended)

```bash
# From project root
./deploy.sh

# Select option 2 (GCP) when prompted
# Or set environment variable:
CLOUD_PROVIDER=gcp ./deploy.sh
```

The script will:
1. Build and push Docker image to GCR
2. Deploy infrastructure with Terraform
3. Deploy Firestore indexes
4. Build and deploy frontend to Firebase Hosting

### Option 2: Manual Step-by-Step Deployment

#### Step 1: Build and Push Docker Image

```bash
cd backend
./build_docker_gcp.sh your-project-id latest
```

This will:
- Build Docker image with tag `gcr.io/your-project-id/pulsechecks-api:latest`
- Push to Google Container Registry
- Display next steps

#### Step 2: Update Terraform Configuration

Update `infra/gcp/terraform.tfvars`:

```hcl
container_image = "gcr.io/your-project-id/pulsechecks-api:latest"
```

#### Step 3: Deploy Infrastructure

```bash
cd ../../infra/gcp
# Option A: local state (default if TF_HTTP_ADDRESS is not configured)
terraform init -backend=false

# Option B: HTTP remote state (GitLab/state service)
# export TF_HTTP_ADDRESS=...
# export TF_HTTP_LOCK_ADDRESS=...
# export TF_HTTP_UNLOCK_ADDRESS=...
# terraform init

terraform plan  # Review changes
terraform apply
```

This creates:
- Firestore database
- Cloud Run service
- Firebase project and authentication
- Cloud Scheduler job
- Pub/Sub topics
- Monitoring dashboard and alerts

**Save the outputs:**
```bash
terraform output
```

#### Step 4: Deploy Firestore Configuration

```bash
cd ../../backend
firebase deploy \
  --only firestore:indexes,firestore:rules \
  --project your-project-id \
  --config firebase.json
```

This deploys:
- Composite indexes for queries
- Security rules (deny all - backend enforces access)

#### Step 5: Build and Deploy Frontend

```bash
cd ../frontend

# Install dependencies
npm ci

# Build for GCP
VITE_CLOUD_PROVIDER=gcp npm run build

# Deploy to Firebase Hosting
firebase deploy --only hosting --project your-project-id
```

## Post-Deployment

### Verify Deployment

1. **Check Cloud Run Service:**
   ```bash
   # Get service URL
   gcloud run services describe pulsechecks-api-prod \
     --region us-central1 \
     --format='value(status.url)'

   # Test health endpoint
   curl https://your-cloudrun-url.run.app/health
   ```

2. **Check Firestore:**
   ```bash
   # List databases
   gcloud firestore databases list

   # Verify indexes
   firebase firestore:indexes --project your-project-id
   ```

3. **Check Cloud Scheduler:**
   ```bash
   # List scheduled jobs
   gcloud scheduler jobs list

   # Manually trigger late detector
   gcloud scheduler jobs run pulsechecks-late-detector-prod
   ```

4. **Test Frontend:**
   - Visit your Firebase Hosting URL
   - Test login flow
   - Create a team and health check

### Configure DNS (Optional)

To use custom domains:

1. **Backend (Cloud Run):**
   ```bash
   gcloud beta run domain-mappings create \
     --service pulsechecks-api-prod \
     --domain api.pulsechecks.example.com \
     --region us-central1
   ```

2. **Frontend (Firebase Hosting):**
   ```bash
   firebase hosting:channel:create live --project your-project-id
   ```

   Then add custom domain in Firebase Console.

## Monitoring

### View Logs

```bash
# Real-time logs
gcloud run services logs tail pulsechecks-api-prod --region us-central1

# Specific time range
gcloud logging read "resource.type=cloud_run_revision" \
  --limit=50 \
  --format=json

# Filter by severity
gcloud logging read "resource.type=cloud_run_revision AND severity>=ERROR" \
  --limit=20
```

### View Metrics

```bash
# List monitoring dashboards
gcloud monitoring dashboards list

# View in console
echo "https://console.cloud.google.com/monitoring/dashboards"
```

Key metrics to monitor:
- **Request Count**: Ensure within 2M requests/month free tier
- **Error Rate**: Should be <1%
- **Latency**: p99 <2 seconds
- **Firestore Operations**: Stay within 50K reads, 20K writes/day

### Set Up Alerts

Alerts are created automatically by Terraform:
- High Error Rate (>5%)
- High Latency (>2000ms)

Add email notifications:
```bash
# Create notification channel
gcloud alpha monitoring channels create \
  --display-name="Email" \
  --type=email \
  --channel-labels=email_address=your-email@example.com

# Link to alert policy (update monitoring.tf)
```

## Cost Management

### Free Tier Limits

Monitor usage to stay within free tier:

| Service                | Free Tier Limit              | Monitor Via                  |
| ---------------------- | ---------------------------- | ---------------------------- |
| Cloud Run              | 2M requests/month            | Cloud Console > Cloud Run    |
| Firestore Reads        | 50K/day                      | Firestore Console            |
| Firestore Writes       | 20K/day                      | Firestore Console            |
| Firebase Auth          | 50K MAU                      | Firebase Console > Auth      |
| Firebase Hosting       | 10GB storage, 360MB/day      | Firebase Console > Hosting   |
| Cloud Scheduler        | 3 jobs                       | Cloud Console > Scheduler    |
| Cloud Logging          | 50GB/month                   | Logging Console              |

### Set Budget Alerts

```bash
# Create budget
gcloud billing budgets create \
  --billing-account=YOUR_BILLING_ACCOUNT_ID \
  --display-name="Pulsechecks Monthly Budget" \
  --budget-amount=5USD \
  --threshold-rule=percent=50 \
  --threshold-rule=percent=90 \
  --threshold-rule=percent=100
```

### Cost Optimization Tips

1. **Scale to Zero:** Keep `min_instances = 0` in terraform.tfvars
2. **Batch Operations:** Group Firestore reads/writes when possible
3. **CDN Caching:** Firebase Hosting CDN is free - use aggressively
4. **Log Retention:** Reduce logging verbosity in production
5. **Right-size Resources:** Start with 512MB RAM, adjust based on metrics

### View Costs

```bash
# Current month's costs
gcloud billing projects describe your-project-id

# Detailed billing (requires BigQuery export)
# Set up: https://cloud.google.com/billing/docs/how-to/export-data-bigquery
```

Or visit: [GCP Billing Console](https://console.cloud.google.com/billing)

## Troubleshooting

### Common Issues

#### 1. API Not Enabled

**Error:** `API [service.googleapis.com] not enabled`

**Solution:**
```bash
gcloud services enable [service-name].googleapis.com
```

Common services:
- `run.googleapis.com`
- `firestore.googleapis.com`
- `firebase.googleapis.com`
- `scheduler.googleapis.com`

#### 2. Permission Denied

**Error:** `Permission denied` or `403 Forbidden`

**Solution:**
```bash
# Grant yourself Owner role
gcloud projects add-iam-policy-binding your-project-id \
  --member="user:your-email@example.com" \
  --role="roles/owner"

# Or use service account with required roles
```

#### 3. Cloud Run Not Accessible

**Error:** `Service not found` or `404`

**Checks:**
```bash
# Verify service exists
gcloud run services list

# Check IAM permissions
gcloud run services get-iam-policy pulsechecks-api-prod --region us-central1

# Ensure allUsers has run.invoker role (for public access)
gcloud run services add-iam-policy-binding pulsechecks-api-prod \
  --region=us-central1 \
  --member="allUsers" \
  --role="roles/run.invoker"
```

#### 4. Firestore Issues

**Error:** `FAILED_PRECONDITION` or `Database not found`

**Solutions:**
```bash
# Verify Firestore is in Native mode (not Datastore mode)
gcloud firestore databases describe --database='(default)'

# Deploy indexes
firebase deploy --only firestore:indexes --project your-project-id

# Check service account permissions
# Ensure Cloud Run SA has datastore.user role
```

#### 5. Cloud Scheduler Not Triggering

**Error:** Late detection not working

**Checks:**
```bash
# View scheduler logs
gcloud scheduler jobs describe pulsechecks-late-detector-prod

# Manually trigger
gcloud scheduler jobs run pulsechecks-late-detector-prod

# Check Cloud Run logs for incoming requests
gcloud run services logs read pulsechecks-api-prod \
  --region us-central1 \
  --filter='resource.labels.service_name="pulsechecks-api-prod"'
```

#### 6. Docker Build Fails

**Error:** `docker: command not found` or build errors

**Solutions:**
```bash
# Ensure Docker is running
docker info

# Authenticate Docker with GCR
gcloud auth configure-docker

# Use Cloud Build instead (alternative)
gcloud builds submit \
  --tag gcr.io/your-project-id/pulsechecks-api \
  --timeout=10m \
  backend/
```

### Getting Help

1. **Check Logs:**
   ```bash
   # Cloud Run logs
   gcloud run services logs tail pulsechecks-api-prod --region us-central1

   # Cloud Scheduler logs
   gcloud logging read "resource.type=cloud_scheduler_job"
   ```

2. **View Error Details:**
   ```bash
   gcloud logging read "severity>=ERROR" --limit=50 --format=json
   ```

3. **GCP Status:** Check [GCP Status Dashboard](https://status.cloud.google.com/)

4. **Documentation:**
   - [Cloud Run Docs](https://cloud.google.com/run/docs)
   - [Firestore Docs](https://cloud.google.com/firestore/docs)
   - [Firebase Auth Docs](https://firebase.google.com/docs/auth)

## Cleanup

To delete all resources:

```bash
cd infra/gcp
terraform destroy
```

⚠️ **Warning:** This will delete:
- All Firestore data
- Cloud Run service
- Firebase project configuration
- All monitoring and logs

Make backups before destroying!

## Next Steps

After successful deployment:

1. **Test End-to-End:** Create checks, send pings, verify alerts
2. **Configure Monitoring:** Set up email notifications for alerts
3. **Optimize Costs:** Review usage and adjust resources
4. **Security Audit:** Review IAM permissions and security rules
5. **Documentation:** Document your specific configuration

## Additional Resources

- [Multi-Cloud Architecture](multi-cloud-architecture.md)
- [GCP Infrastructure README](../infra/gcp/README.md)
- [Operations Guide](operations.md)
- [Development Guide](development.md)
