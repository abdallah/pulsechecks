#!/bin/bash
# Local development server for Pulsechecks backend

set -e

echo "🚀 Starting Pulsechecks Local Development Server"
echo "=============================================="

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📦 Installing dependencies..."
pip install -q -r requirements.txt
pip install -q uvicorn python-dotenv

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚙️  Creating .env file..."
    cat > .env << EOF
# Local development environment
DYNAMODB_TABLE=pulsechecks-local
API_KEY=local-dev-key-123
ALLOWED_EMAIL_DOMAINS=*
COGNITO_USER_POOL_ID=local
COGNITO_CLIENT_ID=local
API_URL=http://localhost:8000
AWS_REGION=us-east-1
EOF
    echo "✅ Created .env file with local settings"
fi

# Start the server
echo ""
echo "🌟 Starting FastAPI server on http://localhost:8000"
echo "📖 API docs available at http://localhost:8000/docs"
echo "🔍 Health check: http://localhost:8000/health"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Run with uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --log-level info
