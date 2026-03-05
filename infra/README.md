# Pulsechecks Infrastructure

Multi-cloud infrastructure supporting both AWS and Google Cloud Platform.

## Directory Structure

```
infra/
├── aws/          # AWS infrastructure (Lambda, DynamoDB, Cognito, etc.)
├── gcp/          # GCP infrastructure (Cloud Run, Firestore, Firebase Auth, etc.)
└── README.md     # This file
```

## Cloud Provider Options

### AWS Deployment
- **Compute**: AWS Lambda (Python 3.13)
- **Database**: DynamoDB with GSI indexes
- **Auth**: AWS Cognito User Pool
- **API**: API Gateway HTTP API
- **Frontend**: S3 + CloudFront CDN
- **Monitoring**: CloudWatch
- **Scheduling**: EventBridge
- **Notifications**: SNS

**Estimated Cost**: ~$10-15/month for low usage

### GCP Deployment
- **Compute**: Cloud Run (containerized)
- **Database**: Firestore (Native mode)
- **Auth**: Firebase Authentication
- **API**: Cloud Run (direct HTTPS)
- **Frontend**: Firebase Hosting
- **Monitoring**: Cloud Logging + Cloud Monitoring
- **Scheduling**: Cloud Scheduler
- **Notifications**: Cloud Pub/Sub

**Estimated Cost**: ~$0-2/month (within free tier)

## Deployment Instructions

### AWS
```bash
cd infra/aws
terraform init
terraform plan
terraform apply
```

### GCP
```bash
cd infra/gcp
terraform init
terraform plan
terraform apply
```

See cloud-specific README files in each directory for detailed setup instructions.
