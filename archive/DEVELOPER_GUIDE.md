# Pulsechecks Developer Onboarding Guide

## Welcome to Pulsechecks! 🚀

This guide will help you get up and running with the Pulsechecks codebase quickly.

## Project Overview

Pulsechecks is a serverless, multi-tenant job monitoring service built on AWS. It allows teams to monitor scheduled jobs and receive alerts when they fail to check in on time.

**Key Technologies:**
- **Backend**: Python 3.13, FastAPI, Pydantic
- **Frontend**: React 18, TypeScript, Tailwind CSS
- **Infrastructure**: AWS (Lambda, DynamoDB, API Gateway, SNS, EventBridge)
- **IaC**: Terraform
- **CI/CD**: GitLab CI

## Architecture Quick Start

```
User Jobs → API Gateway → Lambda Functions → DynamoDB
                ↓
EventBridge (every 2min) → Late Detector → SNS/Mattermost Alerts
```

## Development Environment Setup

### 1. Prerequisites

Install the following tools:
```bash
# Required versions
python --version  # 3.13+
node --version    # 18+
terraform --version  # 1.5+
aws --version     # 2.0+
```

### 2. Clone and Setup

```bash
# Clone repository
git clone https://github.com/your-username/pulsechecks.git
cd pulsechecks

# Backend setup
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Frontend setup
cd ../frontend
npm install

# Infrastructure setup
cd ../infra
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your AWS settings
```

### 3. Local Development

**Backend (API Server):**
```bash
cd backend
source venv/bin/activate
./start_local.sh  # Starts FastAPI on http://localhost:8000
```

**Frontend (React App):**
```bash
cd frontend
npm run dev  # Starts React dev server on http://localhost:3000
```

**Run Tests:**
```bash
# Backend tests (87 tests)
cd backend
pytest tests/ -v

# Frontend tests (framework ready, needs fixes)
cd frontend
npm test
```

## Codebase Structure

```
pulsechecks/
├── backend/           # Python FastAPI application
│   ├── app/
│   │   ├── main.py           # FastAPI app + Lambda handler
│   │   ├── handlers.py       # Background job handlers
│   │   ├── routers/          # API route definitions
│   │   ├── db/              # DynamoDB client
│   │   ├── models/          # Pydantic models
│   │   └── utils/           # Helper functions
│   └── tests/         # Backend test suite
├── frontend/          # React TypeScript application
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── pages/          # Page components
│   │   ├── hooks/          # Custom React hooks
│   │   └── utils/          # Frontend utilities
│   └── public/        # Static assets
├── infra/            # Terraform infrastructure
│   ├── *.tf          # Terraform configuration files
│   └── terraform.tfvars  # Environment variables
└── docs/             # Documentation
```

## Key Concepts

### 1. Single Table Design (DynamoDB)

All data is stored in one DynamoDB table with different entity types:

| Entity | PK | SK | Purpose |
|--------|----|----|---------|
| Team | TEAM#{id} | METADATA | Team information |
| User | USER#{id} | PROFILE | User profiles |
| Check | TEAM#{id} | CHECK#{id} | Monitoring checks |
| Ping | CHECK#{id} | PING#{timestamp} | Check-in records |

### 2. Authentication Flow

1. User signs in via Google Workspace OAuth
2. Cognito validates and issues JWT
3. API validates JWT on each request
4. Domain allowlist enforced

### 3. Alert System

1. EventBridge triggers Late Detector every 2 minutes
2. Late Detector queries overdue checks
3. Sends alerts via SNS topics and Mattermost webhooks
4. Updates check status to "late"

## Development Workflow

### 1. Making Changes

```bash
# Create feature branch
git checkout -b feature/your-feature-name

# Make changes
# ... edit code ...

# Run tests
cd backend && pytest tests/ -v
cd frontend && npm test

# Commit changes
git add .
git commit -m "feat: add your feature description"
git push origin feature/your-feature-name
```

### 2. Testing Locally

**Test API endpoints:**
```bash
# Health check
curl http://localhost:8000/health

# Test ping (requires valid token)
curl -X POST http://localhost:8000/ping/{token} -d "test ping"
```

**Test with real AWS resources:**
```bash
# Deploy to dev environment
export ENVIRONMENT=dev
./deploy.sh

# Test against deployed API
curl https://api-dev.pulsechecks.example.com/health
```

### 3. Deployment

**Automatic (Recommended):**
```bash
git push origin main  # Triggers CI/CD pipeline
```

**Manual (Emergency):**
```bash
./deploy.sh --environment prod
```

## Common Development Tasks

### Adding a New API Endpoint

1. **Define Pydantic models** in `backend/app/models/`
2. **Add route handler** in `backend/app/routers/`
3. **Add database methods** in `backend/app/db/`
4. **Write tests** in `backend/tests/`
5. **Update frontend** to call new endpoint

Example:
```python
# backend/app/routers/example.py
from fastapi import APIRouter, Depends
from ..models.example import ExampleRequest, ExampleResponse
from ..dependencies import get_current_user

router = APIRouter(prefix="/example", tags=["example"])

@router.post("/", response_model=ExampleResponse)
async def create_example(
    request: ExampleRequest,
    user = Depends(get_current_user)
):
    # Implementation here
    pass
```

### Adding a New React Component

1. **Create component** in `frontend/src/components/`
2. **Add TypeScript types** if needed
3. **Write tests** in `frontend/src/components/__tests__/`
4. **Export from index** for easy imports

Example:
```tsx
// frontend/src/components/ExampleComponent.tsx
import React from 'react';

interface ExampleProps {
  title: string;
  onClick: () => void;
}

export const ExampleComponent: React.FC<ExampleProps> = ({ title, onClick }) => {
  return (
    <button onClick={onClick} className="btn btn-primary">
      {title}
    </button>
  );
};
```

### Adding Infrastructure Resources

1. **Create Terraform file** in `infra/`
2. **Define resources** using AWS provider
3. **Add outputs** if needed by application
4. **Test with terraform plan**

Example:
```hcl
# infra/example.tf
resource "aws_s3_bucket" "example" {
  bucket = "${var.project_name}-example-${var.environment}"
}

output "example_bucket_name" {
  value = aws_s3_bucket.example.bucket
}
```

## Debugging Tips

### Backend Issues

```bash
# Check Lambda logs
aws logs tail /aws/lambda/pulsechecks-api-prod --follow

# Local debugging with pdb
import pdb; pdb.set_trace()

# Check DynamoDB data
aws dynamodb scan --table-name pulsechecks-dev --limit 10
```

### Frontend Issues

```bash
# Check browser console for errors
# Use React DevTools extension
# Check network tab for API calls

# Debug with console.log
console.log('Debug info:', data);
```

### Infrastructure Issues

```bash
# Check Terraform plan
terraform plan

# Validate configuration
terraform validate

# Check AWS resources
aws lambda list-functions
aws dynamodb list-tables
```

## Testing Guidelines

### Backend Tests

- **Unit tests**: Test individual functions
- **Integration tests**: Test API endpoints
- **Database tests**: Test DynamoDB operations
- **Handler tests**: Test Lambda handlers

```bash
# Run specific test file
pytest tests/test_db.py -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html
```

### Frontend Tests

- **Component tests**: Test React components
- **Hook tests**: Test custom hooks
- **Integration tests**: Test user flows

```bash
# Run tests in watch mode
npm test

# Run with coverage
npm test -- --coverage
```

## Code Style Guidelines

### Python (Backend)

- Follow PEP 8
- Use type hints
- Use Pydantic for data validation
- Write docstrings for public functions

```python
from typing import List, Optional

async def get_user_teams(user_id: str) -> List[Team]:
    """Get all teams for a user.
    
    Args:
        user_id: The user's unique identifier
        
    Returns:
        List of Team objects the user belongs to
    """
    # Implementation
```

### TypeScript (Frontend)

- Use TypeScript strict mode
- Define interfaces for props
- Use functional components with hooks
- Follow React best practices

```tsx
interface UserTeamsProps {
  userId: string;
  onTeamSelect: (team: Team) => void;
}

export const UserTeams: React.FC<UserTeamsProps> = ({ userId, onTeamSelect }) => {
  // Implementation
};
```

## Useful Resources

### Documentation
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [React Docs](https://react.dev/)
- [AWS Lambda Docs](https://docs.aws.amazon.com/lambda/)
- [DynamoDB Docs](https://docs.aws.amazon.com/dynamodb/)

### Internal Docs
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Common issues and fixes
- [RUNBOOKS.md](RUNBOOKS.md) - Operational procedures
- [ARCHITECTURE.md](ARCHITECTURE.md) - Detailed architecture
- [API_ENDPOINTS.md](API_ENDPOINTS.md) - API documentation

### Tools
- [AWS CLI](https://aws.amazon.com/cli/)
- [Terraform](https://www.terraform.io/)
- [Postman](https://www.postman.com/) - API testing
- [DynamoDB Admin](https://github.com/aaronshaf/dynamodb-admin) - Local DynamoDB GUI

## Getting Help

1. **Check documentation** - Start with README.md and this guide
2. **Search existing issues** - Check GitLab issues
3. **Ask the team** - Use #pulsechecks channel
4. **Create an issue** - If you find a bug or need a feature

## Next Steps

1. **Set up your development environment** following the steps above
2. **Run the test suite** to ensure everything works
3. **Pick a small task** from the TODO.md file
4. **Make your first contribution** and submit a merge request

Welcome to the team! 🎉
