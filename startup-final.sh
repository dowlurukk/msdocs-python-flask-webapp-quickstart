#!/bin/bash

# Azure startup script for the Flask app with compatible dependencies
echo "Starting Azure deployment setup..."

python -m pip install --upgrade pip

# Install the compatible package versions
pip install --no-cache-dir -r requirements.txt

# Set Python path to include the current directory for proper imports
export PYTHONPATH=$PYTHONPATH:/home/site/wwwroot

# Start the Flask app with gunicorn
gunicorn --bind=0.0.0.0 --timeout 600 app:app