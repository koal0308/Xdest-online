#!/bin/bash
# AEra Chat Server - Start Script

echo "🌀 Starting AEra Chat Server..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install/Update dependencies
echo "Installing dependencies..."
pip install -q -r requirements.txt

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "Creating .env from template..."
    cp .env.example .env
    echo "⚠️  Please configure your .env file!"
    exit 1
fi

# Start server
echo "Starting server on port 8850..."
python3 server.py
