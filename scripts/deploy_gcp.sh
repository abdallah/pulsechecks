#!/bin/bash
# GCP deployment script for Pulsechecks
# Deploys to Cloud Run and Firebase Hosting

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

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Configuration
export GCP_PROJECT_ID=${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}
export GCP_REGION=${GCP_REGION:-us-central1}
export ENVIRONMENT=${ENVIRONMENT:-prod}

print_header "Pulsechecks GCP Deployment"
echo "GCP Project: $GCP_PROJECT_ID"
echo "GCP Region: $GCP_REGION"
echo "Environment: $ENVIRONMENT"
echo ""

# Check prerequisites
if ! command -v gcloud &> /dev/null; then
    print_error "gcloud CLI is not installed"
    echo "Install from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

if ! command -v terraform &> /dev/null; then
    print_error "Terraform is not installed"
    exit 1
fi

if ! command -v firebase &> /dev/null; then
    print_error "Firebase CLI is not installed"
    echo "Install: npm install -g firebase-tools"
    exit 1
fi

if [ -z "$GCP_PROJECT_ID" ]; then
    print_error "GCP_PROJECT_ID is not set"
    echo "Run: gcloud config set project YOUR_PROJECT_ID"
    echo "Or: export GCP_PROJECT_ID=your-project-id"
    exit 1
fi

# Check authentication
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null | grep -q .; then
    print_error "Not authenticated with gcloud"
    echo "Run: gcloud auth login"
    exit 1
fi

# Ensure ADC quota project is set for APIs that require it (e.g. Identity Toolkit)
if gcloud auth application-default print-access-token >/dev/null 2>&1; then
    print_info "Setting ADC quota project to ${GCP_PROJECT_ID}..."
    if ! gcloud auth application-default set-quota-project "$GCP_PROJECT_ID" >/dev/null 2>&1; then
        print_warning "Could not set ADC quota project automatically. You may need to run:"
        echo "  gcloud auth application-default set-quota-project $GCP_PROJECT_ID"
    fi
else
    print_warning "Application Default Credentials are not initialized. Run: gcloud auth application-default login"
fi

# Build and push Docker image
print_header "1/4 - Building and Pushing Docker Image"
cd "$PROJECT_ROOT/backend"
print_info "Building Docker image for Cloud Run..."
./build_docker_gcp.sh "$GCP_PROJECT_ID" latest
echo ""

# Deploy infrastructure
print_header "2/4 - Deploying Infrastructure"
cd "$PROJECT_ROOT/infra/gcp"
print_info "Initializing Terraform..."
if [ -n "$TF_HTTP_ADDRESS" ]; then
    print_info "Using HTTP backend (TF_HTTP_ADDRESS is set)"
    terraform init
else
    print_warning "TF_HTTP_ADDRESS is not set; using local Terraform state for this deployment"
    terraform init -backend=false
fi

print_info "Applying Terraform configuration..."
terraform apply -auto-approve

# Get outputs
CLOUDRUN_URL=$(terraform output -raw cloudrun_url)
FIREBASE_WEB_API_KEY=$(terraform output -raw firebase_web_api_key)
FIREBASE_AUTH_DOMAIN=$(terraform output -raw firebase_auth_domain)
print_info "Infrastructure deployed successfully"
echo ""

# Deploy Firestore indexes
print_header "3/4 - Deploying Firestore Indexes"
cd "$PROJECT_ROOT/backend"
print_info "Deploying Firestore indexes and rules..."
firebase deploy \
    --only firestore:indexes,firestore:rules \
    --project "$GCP_PROJECT_ID" \
    --config "$PROJECT_ROOT/backend/firebase.json"
echo ""

# Deploy frontend
print_header "4/4 - Deploying Frontend"
cd "$PROJECT_ROOT/frontend"

print_info "Installing dependencies..."
npm ci --silent

print_info "Building frontend for GCP..."
API_URL_FOR_FRONTEND=${VITE_API_URL:-$CLOUDRUN_URL}
print_info "Using frontend API URL: ${API_URL_FOR_FRONTEND}"
VITE_CLOUD_PROVIDER=gcp \
VITE_API_URL="$API_URL_FOR_FRONTEND" \
VITE_FIREBASE_API_KEY="$FIREBASE_WEB_API_KEY" \
VITE_FIREBASE_AUTH_DOMAIN="$FIREBASE_AUTH_DOMAIN" \
VITE_FIREBASE_PROJECT_ID="$GCP_PROJECT_ID" \
npm run build

print_info "Deploying to Firebase Hosting..."
firebase deploy \
    --only hosting \
    --project "$GCP_PROJECT_ID" \
    --config "$PROJECT_ROOT/frontend/firebase.json"

FRONTEND_URL=$(firebase hosting:sites:list --project "$GCP_PROJECT_ID" 2>/dev/null | grep -Eo 'https://[^ ]+' | head -1)
if [ -z "$FRONTEND_URL" ]; then
    FRONTEND_URL="https://${GCP_PROJECT_ID}.web.app"
fi
echo ""

print_header "Deployment Complete"
echo -e "${GREEN}✅ All components deployed successfully!${NC}"
echo ""
echo "Backend URL:  $CLOUDRUN_URL"
echo "Frontend URL: $FRONTEND_URL"
echo ""
echo "Next steps:"
echo "1. Configure frontend environment variables with backend URL"
echo "2. Test authentication flow"
echo "3. Monitor Cloud Run logs: gcloud run services logs tail pulsechecks-api-${ENVIRONMENT}"
echo "4. Check costs: https://console.cloud.google.com/billing"
echo ""
