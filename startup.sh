#!/bin/bash
# Azure App Service startup script to handle typing_extensions conflicts

echo "🔧 Starting Azure App Service Python application with compatibility fixes..."

# Set environment variables
export PYTHONDONTWRITEBYTECODE=1
export PYTHONUNBUFFERED=1

# Create a local directory for our fixed packages
LOCAL_DEPS="/home/site/wwwroot/local_deps"
mkdir -p "$LOCAL_DEPS"

# Upgrade pip
echo "📦 Upgrading pip..."
python -m pip install --upgrade pip

# Install critical packages to local directory with force reinstall
echo "🔧 Installing critical packages to local directory..."
python -m pip install --force-reinstall --target "$LOCAL_DEPS" --no-deps typing_extensions==4.15.0
python -m pip install --force-reinstall --target "$LOCAL_DEPS" pydantic-core==2.41.5  
python -m pip install --force-reinstall --target "$LOCAL_DEPS" pydantic==2.12.4

# Install remaining requirements normally
echo "📦 Installing remaining requirements..."
python -m pip install -r requirements.txt

# Set Python path to prioritize our local packages
export PYTHONPATH="$LOCAL_DEPS:$PYTHONPATH"

echo "✅ Dependencies installed successfully!"
echo "🚀 Starting gunicorn server..."

# Start the application with our custom Python path
exec env PYTHONPATH="$LOCAL_DEPS:$PYTHONPATH" gunicorn --bind=0.0.0.0 --timeout 600 app:app