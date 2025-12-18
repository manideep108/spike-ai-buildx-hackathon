#!/bin/bash

set -e

echo "🚀 Starting Spike AI Hackathon deployment..."

# Check if credentials.json exists
if [ ! -f "credentials.json" ]; then
    echo "❌ Error: credentials.json not found!"
    echo "Please place your Google credentials.json file in the project root."
    exit 1
fi

echo "✅ credentials.json found"

# Check if .env file exists, if not copy from .env.example
if [ ! -f ".env" ]; then
    echo "⚠️  No .env file found. Please create one from .env.example"
    echo "   You can copy .env.example to .env and fill in your values."
fi

# Install dependencies
echo "📦 Installing dependencies..."

if command -v uv &> /dev/null; then
    echo "Using uv for faster installation..."
    uv pip install -r requirements.txt
else
    echo "Using pip for installation..."
    pip install -r requirements.txt
fi

echo "✅ Dependencies installed"

# Start the server
echo "🌐 Starting server on port 8080..."
echo "API will be available at: http://localhost:8080"
echo "Docs available at: http://localhost:8080/docs"

cd src && python -m uvicorn main:app --host 0.0.0.0 --port 8080
