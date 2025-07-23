# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a RAG (Retrieval Augmented Generation) contact center system built with:
- **Backend**: Python FastAPI server with Google Cloud Vertex AI RAG integration
- **Agent Framework**: Google Agent Development Kit (ADK)
- **Cloud Platform**: Google Cloud Platform (Vertex AI, Cloud Storage)

## Key Commands

### Development Server
```bash
# Start the FastAPI server (recommended)
./start_server.sh

# Or start directly with Python
python server.py
```

### Environment Setup
```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your Google Cloud project settings
```

### Google Cloud Authentication
```bash
# Initialize gcloud CLI
gcloud init

# Set up application default credentials
gcloud auth application-default login

# Enable required APIs
gcloud services enable aiplatform.googleapis.com
```

## Architecture Overview

### Core Components

1. **FastAPI Server** (`server.py`):
   - CORS-enabled REST API for frontend integration
   - Multiple endpoint patterns for compatibility
   - Session management with in-memory storage
   - Health checks and debug endpoints

2. **RAG Agent** (`rag_agent/agent.py`):
   - Google ADK-based agent using Gemini 2.5 Flash model
   - 8 specialized tools for RAG operations
   - Configured for Vertex AI document corpus management

3. **RAG Tools** (`rag_agent/tools/`):
   - `rag_query`: Query documents in a corpus
   - `list_corpora`: List available document corpora
   - `create_corpus`: Create new document collections
   - `add_data`: Add documents to existing corpora
   - `get_corpus_info`: Get detailed corpus information
   - `delete_document`: Remove specific documents
   - `delete_corpus`: Delete entire corpora
   - `bulk_upload_drive`: Mass upload from Google Drive

### Configuration

- **Environment Variables**: Defined in `.env` (use `.env.example` as template)
  - `GOOGLE_CLOUD_PROJECT`: Your GCP project ID
  - `GOOGLE_CLOUD_LOCATION`: GCP region (recommended: us-central1)
- **RAG Settings**: Configured in `rag_agent/config.py`
  - Embedding model: text-embedding-005
  - Default chunk size: 512 tokens
  - Default top-k: 3 results

### API Endpoints

The server provides multiple endpoint patterns:

1. **Simple Chat**: `POST /chat`
2. **Session-based**: `GET/POST /apps/rag_agent/users/{user_id}/sessions/{session_id}`
3. **ADK Compatible**: `POST /run_sse`
4. **Health Check**: `GET /health`

### CORS Configuration

Pre-configured for common frontend development servers:
- `http://localhost:3000` (React/Next.js)
- `http://localhost:5173` (Vite)
- `http://localhost:3001` (Alternative port)

## Development Notes

- The system uses Google ADK's InMemoryRunner for session management
- Sessions are tracked both in ADK and local memory store
- RAG operations require proper Google Cloud authentication
- The agent maintains a "current corpus" state for tool efficiency
- All RAG tools use Vertex AI's document corpus API

## Dependencies

Key Python packages:
- `google-adk==0.5.0` - Google Agent Development Kit
- `google-cloud-aiplatform==1.92.0` - Vertex AI integration
- `fastapi>=0.104.0` - Web framework
- `uvicorn>=0.24.0` - ASGI server
- `google-genai==1.14.0` - Gemini API client

## Authentication Requirements

- Google Cloud Project with billing enabled
- Vertex AI API enabled
- Application Default Credentials configured
- Optional: Service account key file (`service-account.json`)