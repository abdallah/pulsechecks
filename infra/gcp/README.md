# Pulsechecks GCP Infrastructure

Terraform configuration for deploying Pulsechecks on Google Cloud Platform.

## Architecture Overview

- **Compute**: Cloud Run (serverless containers)
- **Database**: Firestore (Native mode, NoSQL)
- **Authentication**: Firebase Authentication (Google OAuth)
- **Hosting**: Firebase Hosting (frontend)
- **Monitoring**: Cloud Monitoring + Cloud Logging
- **Scheduling**: Cloud Scheduler (late detection every 2 minutes)
- **Notifications**: Cloud Pub/Sub

## Cost Estimate

With free tier limits:
- **Cloud Run**: 2M requests/month FREE
- **Firestore**: 50K reads, 20K writes/day FREE
- **Firebase Auth**: 50K MAU FREE
- **Firebase Hosting**: 10GB storage, 360MB/day transfer FREE
- **Cloud Scheduler**: 3 jobs FREE
- **Cloud Logging**: 50GB/month FREE
- **Cloud DNS**: ~$0.20/zone (only paid component)

**Total**: ~$0-2/month for low usage

## Prerequisites

1. **GCP Project**
   ```bash
   gcloud projects create your-project-id
   gcloud config set project your-project-id
   ```

2. **Enable Billing**
   - Link a billing account to your project
   - Required even for free tier resources

3. **Install Tools**
   ```bash
   # Terraform
   brew install terraform  # or download from terraform.io

   # Google Cloud SDK
   brew install --cask google-cloud-sdk  # or from cloud.google.com/sdk

   # Firebase CLI
   npm install -g firebase-tools
   ```

4. **Authenticate**
   ```bash
   gcloud auth application-default login
   firebase login
   ```

5. **Google OAuth Credentials**
   - Go to: https://console.cloud.google.com/apis/credentials
   - Create OAuth 2.0 Client ID (Web application)
   - Add authorized domains
   - Save Client ID and Client Secret

## Setup Instructions

### 1. Configure Variables

```bash
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values
```

Required variables:
- `gcp_project_id`: Your GCP project ID
- `domain_name`: Your frontend domain
- `google_oauth_client_id`: From Google Console
- `google_oauth_client_secret`: From Google Console
- `container_image`: Will be set after building

### 2. Build Container Image

```bash
cd ../../backend
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/pulsechecks-api

# Or use local Docker:
docker build -f Dockerfile.cloudrun -t gcr.io/YOUR_PROJECT_ID/pulsechecks-api .
docker push gcr.io/YOUR_PROJECT_ID/pulsechecks-api
```

### 3. Update terraform.tfvars

```hcl
container_image = "gcr.io/YOUR_PROJECT_ID/pulsechecks-api:latest"
```

### 4. Deploy Infrastructure

```bash
terraform init
terraform plan
terraform apply
```

### 5. Deploy Frontend

```bash
cd ../../frontend

# Configure Firebase
firebase init hosting
# Select your GCP project
# Set public directory to: dist
# Configure as single-page app: Yes

# Build and deploy
VITE_CLOUD_PROVIDER=gcp npm run build
firebase deploy --only hosting
```

### 6. Configure Firestore Indexes

```bash
cd ../../backend
firebase deploy --only firestore:indexes
```

## Post-Deployment

### Get Cloud Run URL

```bash
terraform output cloudrun_url
```

### Configure Frontend Environment

Update frontend configuration with:
- API URL (from terraform output)
- Firebase config (from terraform output)

### Test Deployment

```bash
# Health check
curl $(terraform output -raw cloudrun_url)/health

# Check logs
gcloud run services logs read pulsechecks-api-prod --region=us-central1
```

## Monitoring

### View Dashboard

```bash
gcloud monitoring dashboards list
```

Visit: https://console.cloud.google.com/monitoring

### View Logs

```bash
# Real-time logs
gcloud run services logs tail pulsechecks-api-prod --region=us-central1

# Specific time range
gcloud logging read "resource.type=cloud_run_revision" --limit=50
```

### Check Costs

```bash
# Enable billing export (one-time setup)
gcloud beta billing export create \
  --project=YOUR_PROJECT_ID \
  --dataset=billing_export

# View in BigQuery or Billing console
```

Visit: https://console.cloud.google.com/billing

## Updating the Application

### Update Backend

```bash
cd ../../backend
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/pulsechecks-api:v2
terraform apply -var="container_image=gcr.io/YOUR_PROJECT_ID/pulsechecks-api:v2"
```

### Update Frontend

```bash
cd ../../frontend
VITE_CLOUD_PROVIDER=gcp npm run build
firebase deploy --only hosting
```

## Terraform Outputs

```bash
terraform output cloudrun_url              # Cloud Run service URL
terraform output firebase_web_api_key      # Firebase Web API key
terraform output firebase_auth_domain      # Auth domain
terraform output service_account_email     # Service account
```

## Troubleshooting

### Permission Denied Errors

```bash
# Grant yourself necessary roles
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="user:YOUR_EMAIL" \
  --role="roles/owner"
```

### API Not Enabled

```bash
# Enable specific API
gcloud services enable SERVICE_NAME.googleapis.com
```

### Cloud Run Not Accessible

- Check IAM permissions (allUsers should have run.invoker)
- Verify container image exists
- Check Cloud Run logs for errors

### Firestore Issues

- Ensure Firestore is in Native mode (not Datastore mode)
- Check indexes are created: `firebase deploy --only firestore:indexes`
- Verify service account has datastore.user role

## Cleanup

To destroy all resources:

```bash
terraform destroy
```

⚠️ **Warning**: This will delete all data including Firestore collections!

## Security Notes

1. **Secrets Management**
   - Never commit `terraform.tfvars`
   - Use Secret Manager for sensitive values
   - Rotate OAuth credentials regularly

2. **IAM**
   - Follow principle of least privilege
   - Use service accounts, not user accounts
   - Audit permissions regularly

3. **Network**
   - Cloud Run uses Google's network (encrypted)
   - Consider VPC connector for internal services
   - Use Cloud Armor for DDoS protection (if needed)

## Cost Optimization

1. **Scale to Zero**: Keep `min_instances = 0`
2. **Right-size Resources**: Monitor and adjust CPU/memory
3. **Set Budgets**: Configure billing alerts
4. **Use Free Tier**: Stay within quotas
5. **Clean Up**: Delete unused resources

## Support

For issues or questions:
- GCP Documentation: https://cloud.google.com/docs
- Terraform Google Provider: https://registry.terraform.io/providers/hashicorp/google
- Firebase Documentation: https://firebase.google.com/docs
