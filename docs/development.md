# Development Guide

## Development Environment

### Prerequisites
- Python 3.13
- Node.js >= 18
- AWS CLI configured
- Terraform >= 1.5

### Local Setup

#### Backend Development
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run tests
pytest tests/ -v

# Start local server
python -m uvicorn main:app --reload --port 3001
```

#### Frontend Development
```bash
cd frontend
npm install
npm run dev  # Starts on http://localhost:5173
```

### Project Structure

```
pulsechecks/
├── backend/           # Python FastAPI backend
│   ├── src/          # Source code
│   ├── tests/        # Test suite (87 tests)
│   └── requirements.txt
├── frontend/         # React SPA
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   └── lib/
│   └── package.json
├── infra/           # Terraform infrastructure
│   ├── main.tf
│   └── variables.tf
└── docs/           # Documentation
```

## Testing

### Backend Tests
```bash
cd backend
pytest tests/ -v --cov=src --cov-report=html

# Run specific test categories
pytest tests/test_api.py -v
pytest tests/test_auth.py -v
pytest tests/test_late_detector.py -v
```

**Test Coverage:** 93% (87 tests passing)

### Frontend Tests
```bash
cd frontend
npm test
npm run test:coverage
```

### Integration Tests
```bash
# Test full deployment
./deploy.sh --test

# Test API endpoints
curl https://api.pulsechecks.example.com/health
curl -X POST https://api.pulsechecks.example.com/ping/test-token
```

## Code Standards

### Python (Backend)
- **Style**: Black formatter, isort imports
- **Linting**: Ruff
- **Type hints**: Required for all functions
- **Docstrings**: Google style

```bash
# Format code
black src/ tests/
isort src/ tests/

# Lint
ruff check src/ tests/
```

### JavaScript (Frontend)
- **Style**: Prettier
- **Linting**: ESLint
- **Framework**: React with hooks
- **Styling**: Tailwind CSS

```bash
# Format and lint
npm run format
npm run lint
```

### Git Workflow
- **Main branch**: Production deployments
- **Feature branches**: `feature/description`
- **Commit messages**: Conventional commits format
- **PR required**: For all changes to main

## Architecture Patterns

### Backend Patterns

#### Single Table Design (DynamoDB)
```python
# Entity structure
{
    "PK": "TEAM#team_123",
    "SK": "CHECK#check_456", 
    "GSI1PK": "DUE",
    "GSI1SK": "2024-01-02T10:00:00Z",
    "name": "Daily Backup",
    "status": "up"
}
```

#### Lambda Handler Pattern
```python
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # JWT validation for protected routes
    if request.url.path.startswith("/ping/"):
        return await call_next(request)
    # ... auth logic
    
@app.get("/teams/{team_id}/checks")
async def list_checks(team_id: str, user: User = Depends(get_current_user)):
    # Team authorization
    # Business logic
    return checks
```

#### Error Handling
```python
from fastapi import HTTPException

class PulsechecksError(Exception):
    def __init__(self, message: str, code: str = "UNKNOWN"):
        self.message = message
        self.code = code

@app.exception_handler(PulsechecksError)
async def handle_error(request: Request, exc: PulsechecksError):
    return JSONResponse(
        status_code=400,
        content={"error": exc.message, "code": exc.code}
    )
```

### Frontend Patterns

#### API Client
```javascript
// lib/api.js
class ApiClient {
  async request(endpoint, options = {}) {
    const token = await this.getToken()
    const response = await fetch(`${config.apiUrl}${endpoint}`, {
      ...options,
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
        ...options.headers
      }
    })
    
    if (!response.ok) {
      throw new Error(`API Error: ${response.status}`)
    }
    
    return response.json()
  }
}
```

#### Component Structure
```javascript
// pages/CheckDetailPage.jsx
export default function CheckDetailPage({ user, onLogout }) {
  const [check, setCheck] = useState(null)
  const [loading, setLoading] = useState(true)
  
  useEffect(() => {
    loadCheckData()
  }, [teamId, checkId])
  
  // Event handlers
  // Render logic
}
```

## Deployment

### CI/CD Pipeline
The GitLab CI pipeline automatically:
1. Runs tests on all components
2. Builds optimized packages
3. Deploys changed components only
4. Invalidates CloudFront cache
5. Runs post-deployment verification

### Manual Deployment
```bash
# Deploy everything
./deploy.sh

# Deploy specific components
./deploy.sh --infrastructure-only
./deploy.sh --backend-only  
./deploy.sh --frontend-only

# Deploy to specific environment
export ENVIRONMENT=dev
./deploy.sh
```

### Environment Variables

**Backend:**
- `ENVIRONMENT`: dev/prod
- `DYNAMODB_TABLE`: Table name
- `COGNITO_USER_POOL_ID`: For JWT validation
- `GOOGLE_CLIENT_ID`: OAuth configuration

**Frontend:**
- `VITE_API_URL`: Backend API endpoint
- `VITE_COGNITO_*`: Cognito configuration
- `VITE_REDIRECT_URI`: OAuth callback

## Contributing

### Adding New Features

1. **Create feature branch:**
   ```bash
   git checkout -b feature/new-feature
   ```

2. **Backend changes:**
   - Add API endpoints in `backend/src/`
   - Write tests in `backend/tests/`
   - Update API documentation

3. **Frontend changes:**
   - Add components/pages in `frontend/src/`
   - Update routing if needed
   - Add error handling

4. **Infrastructure changes:**
   - Update Terraform in `infra/`
   - Test with `terraform plan`

5. **Documentation:**
   - Update relevant docs in `docs/`
   - Update API reference if needed

6. **Submit PR:**
   - Ensure all tests pass
   - Update CHANGELOG.md
   - Request review

### Debugging

#### Backend Debugging
```bash
# Local development with debugger
python -m debugpy --listen 5678 --wait-for-client -m uvicorn main:app --reload

# AWS Lambda logs
aws logs tail /aws/lambda/pulsechecks-api --follow
```

#### Frontend Debugging
```bash
# React DevTools
# Browser developer tools
# Network tab for API calls

# Build analysis
npm run build -- --analyze
```

#### Infrastructure Debugging
```bash
# Terraform debugging
export TF_LOG=DEBUG
terraform plan

# AWS resource inspection
aws apigateway get-rest-apis
aws lambda list-functions
aws dynamodb describe-table --table-name Pulsechecks
```

## Performance Considerations

### Backend Optimization
- Use DynamoDB batch operations
- Implement proper pagination
- Cache frequently accessed data
- Optimize Lambda cold starts

### Frontend Optimization
- Code splitting with React.lazy()
- Optimize bundle size
- Use React.memo for expensive components
- Implement proper loading states

### Infrastructure Optimization
- Monitor DynamoDB capacity
- Optimize Lambda memory allocation
- Use CloudFront caching effectively
- Implement proper monitoring and alerting
