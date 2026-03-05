#!/bin/bash
# Multi-cloud deployment script for Pulsechecks
# Supports both AWS and GCP deployments

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}       Pulsechecks Multi-Cloud Deployment${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Check if cloud provider is specified via environment variable
if [ -n "$CLOUD_PROVIDER" ]; then
    CHOICE=$(echo "$CLOUD_PROVIDER" | tr '[:upper:]' '[:lower:]')
    if [ "$CHOICE" = "aws" ]; then
        cloud_choice=1
    elif [ "$CHOICE" = "gcp" ]; then
        cloud_choice=2
    else
        print_error "Invalid CLOUD_PROVIDER: $CLOUD_PROVIDER (must be 'aws' or 'gcp')"
        exit 1
    fi
    print_info "Using cloud provider from environment: $CLOUD_PROVIDER"
else
    # Interactive selection
    echo "Select cloud provider:"
    echo "  1) AWS (Lambda, DynamoDB, Cognito, S3 + CloudFront)"
    echo "  2) GCP (Cloud Run, Firestore, Firebase Auth, Firebase Hosting)"
    echo ""
    read -r -p "Your choice [1-2]: " cloud_choice
    echo ""
fi

case $cloud_choice in
    1)
        print_info "Deploying to AWS..."
        exec "$SCRIPT_DIR/scripts/deploy_aws.sh"
        ;;
    2)
        print_info "Deploying to GCP..."
        exec "$SCRIPT_DIR/scripts/deploy_gcp.sh"
        ;;
    *)
        print_error "Invalid choice. Please select 1 (AWS) or 2 (GCP)"
        exit 1
        ;;
esac
