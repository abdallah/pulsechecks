#!/bin/bash
set -e

# Build and push Docker image to Google Container Registry for Cloud Run
# Usage: ./build_docker_gcp.sh [PROJECT_ID] [TAG]
#   PROJECT_ID: GCP project ID (optional - uses gcloud config if not provided)
#   TAG: Image tag (optional - defaults to 'latest')

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Get GCP project ID
if [ -n "$1" ]; then
    PROJECT_ID="$1"
    print_info "Using provided project ID: $PROJECT_ID"
elif [ -n "$GCP_PROJECT_ID" ]; then
    PROJECT_ID="$GCP_PROJECT_ID"
    print_info "Using GCP_PROJECT_ID environment variable: $PROJECT_ID"
else
    PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
    if [ -z "$PROJECT_ID" ]; then
        print_error "No GCP project ID provided or configured"
        echo "Usage: $0 [PROJECT_ID] [TAG]"
        echo "  Or set GCP_PROJECT_ID environment variable"
        echo "  Or configure: gcloud config set project YOUR_PROJECT_ID"
        exit 1
    fi
    print_info "Using gcloud configured project: $PROJECT_ID"
fi

# Get image tag (default to latest)
TAG="${2:-latest}"
print_info "Using image tag: $TAG"

# Image name
IMAGE_NAME="pulsechecks-api"
FULL_IMAGE="gcr.io/${PROJECT_ID}/${IMAGE_NAME}:${TAG}"

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    print_error "gcloud CLI is not installed"
    echo "Install from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed"
    echo "Install from: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if authenticated with gcloud
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null | grep -q .; then
    print_error "Not authenticated with gcloud"
    echo "Run: gcloud auth login"
    exit 1
fi

# Configure Docker to use gcloud as credential helper
print_info "Configuring Docker authentication for GCR..."
gcloud auth configure-docker --quiet

# Build Docker image
print_info "Building Docker image: $FULL_IMAGE"
docker build \
    -f Dockerfile.cloudrun \
    -t "$FULL_IMAGE" \
    --platform linux/amd64 \
    .

if [ $? -ne 0 ]; then
    print_error "Docker build failed"
    exit 1
fi

print_info "Docker build successful!"

# Push to Google Container Registry
print_info "Pushing image to Google Container Registry..."
docker push "$FULL_IMAGE"

if [ $? -ne 0 ]; then
    print_error "Docker push failed"
    exit 1
fi

print_info "Successfully pushed image to GCR!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Image: $FULL_IMAGE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
print_info "Next steps:"
echo "  1. Update infra/gcp/terraform.tfvars:"
echo "     container_image = \"$FULL_IMAGE\""
echo ""
echo "  2. Deploy infrastructure:"
echo "     cd ../infra/gcp"
echo "     terraform apply"
echo ""
echo "  3. Or use Cloud Build (alternative):"
echo "     gcloud builds submit --tag $FULL_IMAGE"
echo ""

# Also tag as latest if a specific version was provided
if [ "$TAG" != "latest" ]; then
    LATEST_IMAGE="gcr.io/${PROJECT_ID}/${IMAGE_NAME}:latest"
    print_info "Tagging as latest: $LATEST_IMAGE"
    docker tag "$FULL_IMAGE" "$LATEST_IMAGE"
    docker push "$LATEST_IMAGE"
fi

print_info "Build and push complete!"
