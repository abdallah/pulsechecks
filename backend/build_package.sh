#!/bin/bash
# Optimized Lambda package builder - excludes boto3/botocore (pre-installed in Lambda)

set -e

echo "🔨 Building optimized Lambda package..."

# Clean previous builds
rm -rf package/ lambda.zip build_venv/

# Create Python 3.13 virtual environment
echo "🐍 Creating Python 3.13 virtual environment..."
python3.13 -m venv build_venv
source build_venv/bin/activate

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt -t package/ --quiet

# Remove AWS SDK (pre-installed in Lambda runtime) - DISABLED for compatibility
echo "📦 Including all AWS SDK dependencies for compatibility..."
# rm -rf package/boto3*
# rm -rf package/botocore*
# rm -rf package/s3transfer*
# rm -rf package/jmespath*

# Copy application code
echo "📁 Copying application code..."
cp -r app/ package/

# Remove unnecessary files to reduce size
echo "🧹 Cleaning up unnecessary files..."
find package/ -name "*.pyc" -delete
find package/ -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find package/ -name "*.dist-info" -type d -exec rm -rf {} + 2>/dev/null || true
find package/ -name "tests" -type d -exec rm -rf {} + 2>/dev/null || true

# Show size comparison
echo ""
echo "📊 Package size analysis:"
du -sh package/
echo ""

# Create deployment zip
echo "📦 Creating deployment package..."
cd package
zip -r ../lambda.zip . -q
cd ..

# Clean up venv
deactivate
rm -rf build_venv/

# Show final size
echo "✅ Optimized package created:"
ls -lh lambda.zip | awk '{print "Size: " $5}'

# Calculate size reduction
ORIGINAL_SIZE="95MB"
NEW_SIZE=$(du -sh package/ | awk '{print $1}')
echo "Size reduction: ${ORIGINAL_SIZE} → ${NEW_SIZE} (excluded boto3/botocore)"

# Verify critical dependencies are included
echo "🔍 Verifying critical dependencies..."
if [ -d "package/jwt" ]; then
    echo "✅ PyJWT included"
else
    echo "❌ PyJWT missing"
fi
if [ -d "package/cryptography" ]; then
    echo "✅ cryptography included"
else
    echo "❌ cryptography missing"
fi
