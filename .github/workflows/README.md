# GitHub Actions CI/CD

This directory contains GitHub Actions workflows for automated testing and deployment.

## Workflows

### 1. Test (`test.yml`)

Runs on every pull request and push to main branch.

**Jobs:**
- Backend tests with coverage
- Frontend tests with coverage
- Terraform validation for both AWS and GCP

**No secrets required** - runs automatically on PRs.

### 2. AWS Deployment (`aws-deploy.yml`)

Deploys the application to AWS Lambda, S3, and CloudFront.

**Triggers:**
- Push to `main` branch (paths: `backend/**`, `frontend/**`, `infra/aws/**`)
- Manual workflow dispatch

**Required Secrets:**
- `AWS_ROLE_ARN` - ARN of IAM role for GitHub Actions OIDC

**Setup Instructions:**

1. **Enable OIDC Provider in AWS**

   Create an OIDC identity provider in IAM:
   - Provider URL: `https://token.actions.githubusercontent.com`
   - Audience: `sts.amazonaws.com`

2. **Create IAM Role**

   Create a role with this trust policy:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Principal": {
           "Federated": "arn:aws:iam::<ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com"
         },
         "Action": "sts:AssumeRoleWithWebIdentity",
         "Condition": {
           "StringEquals": {
             "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
             "token.actions.githubusercontent.com:sub": "repo:<GITHUB_ORG>/<REPO>:ref:refs/heads/main"
           }
         }
       }
     ]
   }
   ```

   Attach these policies:
   - `AWSLambdaFullAccess`
   - `IAMFullAccess` (for Cognito)
   - `AmazonS3FullAccess`
   - `CloudFrontFullAccess`
   - `AmazonDynamoDBFullAccess`
   - `AmazonAPIGatewayAdministrator`
   - `CloudWatchFullAccess`
   - `AmazonEventBridgeFullAccess`

3. **Add GitHub Secret**

   Go to Settings > Secrets and variables > Actions > New repository secret:
   - Name: `AWS_ROLE_ARN`
   - Value: `arn:aws:iam::<ACCOUNT_ID>:role/<ROLE_NAME>`

### 3. GCP Deployment (`gcp-deploy.yml`)

Deploys the application to Cloud Run and Firebase Hosting.

**Triggers:**
- Push to `main` branch (paths: `backend/**`, `frontend/**`, `infra/gcp/**`)
- Manual workflow dispatch

**Required Secrets:**
- `GCP_WORKLOAD_IDENTITY_PROVIDER` - Workload Identity Provider resource name
- `GCP_SERVICE_ACCOUNT` - Service account email for Workload Identity
- `GCP_PROJECT_ID` - GCP project ID
- `FIREBASE_TOKEN` - Firebase deployment token
- `GCP_API_URL` - Cloud Run service URL (optional, for frontend build)
- `FIREBASE_API_KEY` - Firebase Web API key
- `FIREBASE_AUTH_DOMAIN` - Firebase auth domain

**Setup Instructions:**

1. **Enable Workload Identity Federation**

   ```bash
   # Create Workload Identity Pool
   gcloud iam workload-identity-pools create "github-actions" \
     --project="${PROJECT_ID}" \
     --location="global" \
     --display-name="GitHub Actions Pool"

   # Create Workload Identity Provider
   gcloud iam workload-identity-pools providers create-oidc "github-provider" \
     --project="${PROJECT_ID}" \
     --location="global" \
     --workload-identity-pool="github-actions" \
     --display-name="GitHub Provider" \
     --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
     --issuer-uri="https://token.actions.githubusercontent.com"
   ```

2. **Create Service Account**

   ```bash
   # Create service account
   gcloud iam service-accounts create github-actions \
     --project="${PROJECT_ID}" \
     --display-name="GitHub Actions"

   # Grant necessary roles
   gcloud projects add-iam-policy-binding ${PROJECT_ID} \
     --member="serviceAccount:github-actions@${PROJECT_ID}.iam.gserviceaccount.com" \
     --role="roles/run.admin"

   gcloud projects add-iam-policy-binding ${PROJECT_ID} \
     --member="serviceAccount:github-actions@${PROJECT_ID}.iam.gserviceaccount.com" \
     --role="roles/iam.serviceAccountUser"

   gcloud projects add-iam-policy-binding ${PROJECT_ID} \
     --member="serviceAccount:github-actions@${PROJECT_ID}.iam.gserviceaccount.com" \
     --role="roles/storage.admin"

   gcloud projects add-iam-policy-binding ${PROJECT_ID} \
     --member="serviceAccount:github-actions@${PROJECT_ID}.iam.gserviceaccount.com" \
     --role="roles/datastore.owner"

   # Allow GitHub Actions to impersonate service account
   gcloud iam service-accounts add-iam-policy-binding \
     github-actions@${PROJECT_ID}.iam.gserviceaccount.com \
     --project="${PROJECT_ID}" \
     --role="roles/iam.workloadIdentityUser" \
     --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-actions/attribute.repository/${GITHUB_ORG}/${REPO}"
   ```

3. **Get Firebase Token**

   ```bash
   firebase login:ci
   ```

   Save the token for the `FIREBASE_TOKEN` secret.

4. **Add GitHub Secrets**

   Go to Settings > Secrets and variables > Actions:
   - `GCP_WORKLOAD_IDENTITY_PROVIDER`:
     ```
     projects/<PROJECT_NUMBER>/locations/global/workloadIdentityPools/github-actions/providers/github-provider
     ```
   - `GCP_SERVICE_ACCOUNT`: `github-actions@<PROJECT_ID>.iam.gserviceaccount.com`
   - `GCP_PROJECT_ID`: Your GCP project ID
   - `FIREBASE_TOKEN`: Token from `firebase login:ci`
   - `FIREBASE_API_KEY`: From Firebase Console > Project Settings
   - `FIREBASE_AUTH_DOMAIN`: `<PROJECT_ID>.firebaseapp.com`
   - `GCP_API_URL`: Cloud Run URL (set after first deploy)

## Manual Deployment

You can trigger deployments manually:

1. Go to Actions tab
2. Select workflow (AWS Deploy or GCP Deploy)
3. Click "Run workflow"
4. Select environment (prod/staging)
5. Click "Run workflow"

## Monitoring

All workflows create deployment summaries with URLs and status information. Check the Actions tab for:
- Test results and coverage
- Deployment status
- Frontend/Backend URLs
- Error logs

## Troubleshooting

### AWS Deployment Fails with "Access Denied"
- Verify IAM role has all required permissions
- Check trust policy includes your repository
- Ensure OIDC provider is configured correctly

### GCP Deployment Fails with "Permission Denied"
- Verify service account has all required roles
- Check Workload Identity binding
- Ensure APIs are enabled (Cloud Run, Firestore, etc.)

### Terraform Validation Fails
- Run `terraform fmt -recursive` locally
- Check for syntax errors in `.tf` files
- Ensure all required variables are defined

## Cost Optimization

GitHub Actions offers:
- 2,000 minutes/month free for private repos
- Unlimited minutes for public repos

To optimize:
- Tests run only on changed paths
- Artifacts expire after 1 day
- Use caching for dependencies

## Comparison: GitHub Actions vs GitLab CI

| Feature | GitHub Actions | GitLab CI |
|---------|----------------|-----------|
| **Free Tier** | 2,000 min/month | 400 min/month |
| **Configuration** | `.github/workflows/` | `.gitlab-ci.yml` |
| **OIDC Support** | Native | Native |
| **Artifact Storage** | Built-in | Built-in |
| **Matrix Builds** | Yes | Yes |
| **Manual Triggers** | workflow_dispatch | Manual jobs |
| **Deployment Summaries** | GITHUB_STEP_SUMMARY | GitLab Environments |

Both CI/CD systems are fully supported and offer similar capabilities.
