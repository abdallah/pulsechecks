#!/bin/bash
# AWS deployment script for Pulsechecks
# Deploys to AWS Lambda, S3, and CloudFront

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Configuration
export AWS_PROFILE=${AWS_PROFILE:-testing}
export AWS_REGION=${AWS_REGION:-us-east-1}
export ENVIRONMENT=${ENVIRONMENT:-prod}

print_header "Pulsechecks AWS Deployment"
echo "AWS Profile: $AWS_PROFILE"
echo "AWS Region: $AWS_REGION"
echo "Environment: $ENVIRONMENT"
echo ""

# Check prerequisites
if ! command -v aws &> /dev/null; then
    print_error "AWS CLI is not installed"
    exit 1
fi

if ! command -v terraform &> /dev/null; then
    print_error "Terraform is not installed"
    exit 1
fi

# Deploy infrastructure
print_header "1/3 - Deploying Infrastructure"
cd "$PROJECT_ROOT/infra/aws"
terraform init
terraform apply -auto-approve
print_info "Infrastructure deployed successfully"
echo ""

# Build and deploy backend
print_header "2/3 - Deploying Backend"
cd "$PROJECT_ROOT/backend"
print_info "Building Lambda package..."
./build_package.sh

# Get function names from Terraform
cd "$PROJECT_ROOT/infra/aws"
API_FUNCTION=$(terraform output -raw api_function_name)
PING_FUNCTION=$(terraform output -raw ping_function_name)
DETECTOR_FUNCTION=$(terraform output -raw late_detector_function_name)
cd "$PROJECT_ROOT/backend"

# Deploy Lambda functions
print_info "Updating Lambda functions..."
aws lambda update-function-code --function-name $API_FUNCTION --zip-file fileb://lambda.zip --no-cli-pager
aws lambda update-function-code --function-name $PING_FUNCTION --zip-file fileb://lambda.zip --no-cli-pager
aws lambda update-function-code --function-name $DETECTOR_FUNCTION --zip-file fileb://lambda.zip --no-cli-pager
print_info "Backend deployed successfully"
echo ""

# Deploy frontend
print_header "3/3 - Deploying Frontend"
cd "$PROJECT_ROOT/infra/aws"
S3_BUCKET=$(terraform output -raw s3_bucket_name)
CLOUDFRONT_ID=$(terraform output -raw cloudfront_distribution_id)
FRONTEND_URL=$(terraform output -raw cloudfront_url)
cd "$PROJECT_ROOT/frontend"

print_info "Installing dependencies..."
npm ci --silent

print_info "Building frontend for AWS..."
VITE_CLOUD_PROVIDER=aws npm run build

print_info "Uploading to S3..."
aws s3 sync dist/ s3://${S3_BUCKET}/ --delete --quiet

print_info "Invalidating CloudFront cache..."
aws cloudfront create-invalidation --distribution-id ${CLOUDFRONT_ID} --paths "/*" --no-cli-pager > /dev/null

print_info "Frontend deployed successfully"
echo ""

print_header "Deployment Complete"
echo -e "${GREEN}✅ All components deployed successfully!${NC}"
echo ""
echo "Frontend URL: $FRONTEND_URL"
echo ""
