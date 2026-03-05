# Pulsechecks Documentation

## Quick Links

- [Getting Started](getting-started.md) - Setup and deployment guide
- [Multi-Cloud Architecture](multi-cloud-architecture.md) - AWS and GCP comparison
- [GCP Deployment](gcp-deployment.md) - Google Cloud Platform deployment guide
- [Architecture](architecture.md) - System design and components
- [API Reference](api-reference.md) - Complete API documentation
- [Alert Channels](alert-channels.md) - Creating and managing notifications
- [Operations](operations.md) - Monitoring, troubleshooting, and runbooks
- [Development](development.md) - Developer guide and contributing

## Overview

Pulsechecks is a serverless, multi-tenant job monitoring service with multi-cloud support (AWS and GCP). It provides:

- **Interval-based monitoring** with configurable periods and grace times
- **Multi-tenant architecture** with team-based isolation
- **Google Workspace authentication** with domain allowlists
- **Real-time alerting** via email and webhooks
- **Cost-optimized design** targeting <$10/month at low usage

## Quick Start

```bash
# Clone and deploy
git clone https://github.com/your-username/pulsechecks.git
cd pulsechecks
./deploy.sh

# Create a check and start monitoring
curl https://api.pulsechecks.example.com/ping/{your-token}
```

For detailed setup instructions, see [Getting Started](getting-started.md).
