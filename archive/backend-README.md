# Pulsechecks Backend

FastAPI-based serverless backend for job monitoring.

## Quick Start

### Local Development
```bash
./start_local.sh  # Starts FastAPI server on localhost:8000
```

### Testing
```bash
pytest tests/ -v  # Run all tests (87 tests)
```

### Deployment
```bash
./build_package.sh  # Create optimized Lambda package
```

## Structure

- `app/` - Application code
  - `main.py` - FastAPI app and Lambda handler
  - `models.py` - Pydantic models
  - `db/` - DynamoDB client
  - `handlers/` - Lambda handlers (late detector)
- `tests/` - Test suite (87 tests, 93% pass rate)
- `requirements.txt` - Production dependencies
- `.env` - Local environment variables

## Environment Variables

- `DYNAMODB_TABLE` - DynamoDB table name
- `API_KEY` - API authentication key
- `COGNITO_USER_POOL_ID` - Cognito user pool
- `COGNITO_CLIENT_ID` - Cognito client ID
- `ALLOWED_EMAIL_DOMAINS` - Comma-separated allowed domains
- `API_URL` - Base API URL

## API Documentation

When running locally, visit:
- http://localhost:8000/docs - Interactive API docs
- http://localhost:8000/health - Health check
