#!/bin/bash
# Start script for the RAG Agent FastAPI server

echo "🚀 Starting RAG Agent Server with CORS support..."
echo "----------------------------------------"

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "⚠️  Virtual environment not found. Creating one..."
    python3 -m venv .venv
fi

# Activate virtual environment
echo "📦 Activating virtual environment..."
source .venv/bin/activate

# Install/upgrade dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

# Set executable permissions for this script
chmod +x start_server.sh

# Check if environment variables are set
if [ -z "$GOOGLE_CLOUD_PROJECT" ]; then
    echo "⚠️  Warning: GOOGLE_CLOUD_PROJECT environment variable not set"
    echo "   Please set it with: export GOOGLE_CLOUD_PROJECT=your-project-id"
fi

if [ -z "$GOOGLE_CLOUD_LOCATION" ]; then
    echo "⚠️  Warning: GOOGLE_CLOUD_LOCATION environment variable not set"
    echo "   Please set it with: export GOOGLE_CLOUD_LOCATION=your-location (e.g., us-central1)"
fi

echo "----------------------------------------"
echo "🌐 Server will be available at:"
echo "   • Main API: http://localhost:8000"
echo "   • API Docs: http://localhost:8000/docs"
echo "   • Health: http://localhost:8000/health"
echo ""
echo "🔗 CORS enabled for:"
echo "   • http://localhost:3000 (React/Next.js)"
echo "   • http://localhost:5173 (Vite)"
echo ""
echo "Press Ctrl+C to stop the server"
echo "----------------------------------------"

# Start the server
python server.py 