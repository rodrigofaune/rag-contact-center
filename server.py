#!/usr/bin/env python3
"""
FastAPI server with CORS support for the RAG Agent.
This server integrates the Google ADK agent directly to enable CORS for frontend access.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import json
import uvicorn
import asyncio

from rag_agent.agent import root_agent
from google.adk.runners import InMemoryRunner
from google.genai import types
import time

app = FastAPI(
    title="RAG Agent API",
    description="API for interacting with the Vertex AI RAG Agent",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # React dev server
        "http://127.0.0.1:3000",
        "http://localhost:3001",  # Alternative port
        "http://127.0.0.1:3001",
        "http://localhost:5173",  # Vite dev server
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Pydantic models for request/response
class AgentRequest(BaseModel):
    message: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    
    # Allow extra fields for flexibility
    class Config:
        extra = "allow"

class FlexibleRequest(BaseModel):
    # Support multiple possible field names
    message: Optional[str] = None
    text: Optional[str] = None
    query: Optional[str] = None
    content: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    state: Optional[Dict[str, Any]] = None  # ADK state field
    
    class Config:
        extra = "allow"
    
    def get_message(self) -> str:
        """Extract message from any of the possible fields"""
        return self.message or self.text or self.query or self.content or ""
    
    def is_adk_state_request(self) -> bool:
        """Check if this is an ADK state-only request (like initialization)"""
        return (self.state is not None and 
                not any([self.message, self.text, self.query, self.content]))

class AgentResponse(BaseModel):
    response: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None

class ADKResponse(BaseModel):
    """ADK-compatible response format"""
    state: Dict[str, Any] = {}
    response: Optional[str] = None
    
    class Config:
        extra = "allow"

class ADKMessage(BaseModel):
    """ADK message format"""
    role: str
    parts: List[Dict[str, str]]

class ADKRunRequest(BaseModel):
    """ADK run_sse request format"""
    app_name: str
    user_id: str
    session_id: str
    new_message: ADKMessage
    streaming: bool = False
    
    class Config:
        extra = "allow"

class ADKRunResponse(BaseModel):
    """ADK run_sse response format"""
    response_messages: List[Dict[str, Any]]
    session_state: Dict[str, Any] = {}
    
    class Config:
        extra = "allow"

# Store for user sessions (in production, use a proper database)
sessions: Dict[str, Dict[str, Any]] = {}

# Define a consistent app name
APP_NAME = "rag_agent"

# Initialize ADK components
runner = InMemoryRunner(root_agent, app_name=APP_NAME)

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "RAG Agent API is running", "status": "ok"}

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "agent": "rag_agent_ready"}

@app.post("/chat", response_model=AgentResponse)
async def chat(request: AgentRequest):
    """
    Main chat endpoint for interacting with the RAG agent
    """
    try:
        print(f"Received message: {request.message}")
        
        # Use user_id and session_id or defaults
        user_id = request.user_id or "default_user"
        session_id = request.session_id or "default_session"
        
        # Ensure ADK session exists in the runner
        try:
            runner.session_service.get_session(
                app_name=APP_NAME, user_id=user_id, session_id=session_id
            )
        except Exception:
            print(f"Runner session not found. Creating for {user_id}/{session_id}")
            runner.session_service.create_session(
                app_name=APP_NAME, user_id=user_id, session_id=session_id
            )
        
        # Track sessions locally
        session_key = f"{user_id}_{session_id}"
        if session_key not in sessions:
            print(f"Creating new session for user {user_id}, session {session_id}")
            sessions[session_key] = {
                "messages": [], 
                "context": {}
            }
        
        # Create message content for ADK
        content = types.Content(
            role='user', 
            parts=[types.Part(text=request.message)]
        )
        
        # Run the agent using ADK InMemoryRunner
        events = runner.run_async(
            user_id=user_id,
            session_id=session_id, 
            new_message=content
        )
        
        # Process the response stream
        result = ""
        async for event in events:
            if event.is_final_response():
                if event.content and event.content.parts:
                    result = event.content.parts[0].text
                break
        
        if not result:
            result = "I'm sorry, I couldn't generate a response. Please try again."
        
        print(f"Agent response: {result}")
        
        # Store conversation in session
        sessions[session_key]["messages"].append({
            "user": request.message,
            "agent": result,
            "timestamp": None
        })
        
        return AgentResponse(
            response=result,
            user_id=user_id,
            session_id=session_id
        )
    
    except Exception as e:
        print(f"Error in chat endpoint: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {str(e)}")

@app.get("/apps/rag_agent/users/{user_id}/sessions/{session_id}")
async def get_session(user_id: str, session_id: str):
    """
    Get session history for a specific user and session
    This matches the URL pattern from your error message
    """
    session_key = f"{user_id}_{session_id}"
    
    if session_key not in sessions:
        return {"user_id": user_id, "session_id": session_id, "messages": []}
    
    return {
        "user_id": user_id,
        "session_id": session_id,
        "messages": sessions[session_key]["messages"]
    }

@app.post("/apps/rag_agent/users/{user_id}/sessions/{session_id}")
async def post_to_session(user_id: str, session_id: str, request: FlexibleRequest):
    """
    Post a message to a specific session
    This matches the URL pattern from your error message
    """
    try:
        session_key = f"{user_id}_{session_id}"
        
        # Handle ADK state-only requests (initialization)
        if request.is_adk_state_request():
            print(f"ADK state request for session {session_key}")
            print(f"Request state: {request.state}")
            
            # Create ADK session in the runner
            try:
                adk_session = runner.session_service.get_session(
                    app_name=APP_NAME,
                    user_id=user_id,
                    session_id=session_id
                )
                # Check if session actually exists (some implementations return None instead of raising exception)
                if adk_session is None:
                    raise ValueError("Session returned None")
                print(f"ADK session already exists: {adk_session}")
            except Exception as e:
                # Session doesn't exist, create it
                print(f"ADK session not found: {e}")
                print(f"Creating new ADK session for user {user_id}, session {session_id}")
                try:
                    adk_session = runner.session_service.create_session(
                        app_name=APP_NAME, 
                        user_id=user_id, 
                        session_id=session_id,
                        state=request.state or {}
                    )
                    print(f"ADK session created successfully: {adk_session}")
                except Exception as create_error:
                    print(f"Failed to create ADK session: {create_error}")
                    raise HTTPException(status_code=500, detail=f"Failed to create ADK session: {create_error}")
            
            # Initialize local session tracking if it doesn't exist
            if session_key not in sessions:
                sessions[session_key] = {
                    "messages": [], 
                    "context": {},
                    "initialized": True,
                    "adk_session": adk_session
                }
                print(f"Local session created for {session_key}")
            else:
                print(f"Local session already exists for {session_key}")
            
            # Return ADK-compatible response
            return ADKResponse(
                state=request.state or {},
                response="Session initialized successfully"
            )
        
        # Handle regular message requests
        message = request.get_message()
        
        if not message:
            print(f"Error in post_to_session: No message found in request.")
            print(f"Request data: message={request.message} text={request.text} query={request.query} content={request.content} user_id={request.user_id} session_id={request.session_id} state={request.state}")
            raise HTTPException(status_code=400, detail="No message found in request. Please provide 'message', 'text', 'query', or 'content' field.")
        
        # Use the ADK agent directly instead of creating AgentRequest
        try:
            # Ensure ADK session exists in the session service
            session_key = f"{user_id}_{session_id}"
            try:
                # Check if session exists in ADK session service
                adk_session = runner.session_service.get_session(
                    app_name=APP_NAME,
                    user_id=user_id,
                    session_id=session_id
                )
            except:
                # Session doesn't exist, create it
                print(f"Creating new ADK session for user {user_id}, session {session_id}")
                adk_session = runner.session_service.create_session(
                    app_name=APP_NAME, 
                    user_id=user_id, 
                    session_id=session_id
                )
            
            # Update local session tracking
            if session_key not in sessions:
                sessions[session_key] = {
                    "adk_session": adk_session,
                    "messages": [], 
                    "context": {}
                }
            
            # Create message content for ADK
            content = types.Content(
                role='user', 
                parts=[types.Part(text=message)]
            )
            
            # Run the agent using ADK Runner
            events = runner.run_async(
                user_id=user_id, 
                session_id=session_id, 
                new_message=content
            )
            
            # Process the response stream
            result = ""
            async for event in events:
                if event.is_final_response():
                    if event.content and event.content.parts:
                        result = event.content.parts[0].text
                    break
            
            if not result:
                result = "I'm sorry, I couldn't generate a response. Please try again."
            
            print(f"Agent response: {result}")
            
            # Store conversation in session
            sessions[session_key]["messages"].append({
                "user": message,
                "agent": result,
                "timestamp": None
            })
            
            return AgentResponse(
                response=result,
                user_id=user_id,
                session_id=session_id
            )
            
        except Exception as e:
            print(f"Error processing message with ADK agent: {str(e)}")
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Agent execution failed: {str(e)}")
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        print(f"Error in post_to_session: {str(e)}")
        print(f"Request data: {request}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.delete("/apps/rag_agent/users/{user_id}/sessions/{session_id}")
async def delete_session(user_id: str, session_id: str):
    """
    Delete a specific session
    """
    session_key = f"{user_id}_{session_id}"
    
    if session_key in sessions:
        del sessions[session_key]
        return {"message": f"Session {session_id} for user {user_id} deleted"}
    else:
        raise HTTPException(status_code=404, detail="Session not found")

@app.get("/sessions")
async def list_sessions():
    """
    List all active sessions
    """
    return {
        "sessions": list(sessions.keys()),
        "total": len(sessions)
    }

@app.post("/run_sse", response_model=ADKRunResponse)
async def run_sse(request: ADKRunRequest):
    """
    ADK-compatible endpoint for running the agent
    This matches the format used by Google ADK api_server
    """
    try:
        print(f"ADK run_sse request: app={request.app_name}, user={request.user_id}, session={request.session_id}")
        
        # Extract message text from ADK format
        message_text = ""
        if request.new_message.parts:
            for part in request.new_message.parts:
                if "text" in part:
                    message_text += part["text"]
        
        if not message_text:
            raise HTTPException(status_code=400, detail="No text found in message parts")
        
        print(f"Extracted message: {message_text}")
        
        session_key = f"{request.user_id}_{request.session_id}"
        
        # Track sessions locally
        if session_key not in sessions:
            print(f"Creating new session for user {request.user_id}, session {request.session_id}")
            sessions[session_key] = {
                "messages": [], 
                "context": {}
            }
        
        # Use the ADK agent to process the message
        try:
            # Create message content for ADK
            content = types.Content(
                role='user', 
                parts=[types.Part(text=message_text)]
            )
            
            # Use the global runner that has the session created in the other endpoint
            print(f"Using global runner for session {request.session_id}")
            
            # Run the agent using the global runner
            events = runner.run_async(
                user_id=request.user_id,
                session_id=request.session_id, 
                new_message=content
            )
            
            # Process the response stream
            result = ""
            async for event in events:
                if event.is_final_response():
                    if event.content and event.content.parts:
                        result = event.content.parts[0].text
                    break
            
            if not result:
                result = "I'm sorry, I couldn't generate a response. Please try again."
            
            print(f"Agent response: {result}")
            
            # Store conversation in session
            sessions[session_key]["messages"].append({
                "user": message_text,
                "agent": result,
                "timestamp": None
            })
            
            # Create ADK-compatible response
            response_message = {
                "role": "model",
                "parts": [{"text": result}]
            }
            
            return ADKRunResponse(
                response_messages=[response_message],
                session_state=sessions[session_key].get("context", {})
            )
            
        except Exception as e:
            print(f"Error processing message: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # Return error in ADK format
            error_response = {
                "role": "model", 
                "parts": [{"text": f"Sorry, I encountered an error processing your request: {str(e)}"}]
            }
            
            return ADKRunResponse(
                response_messages=[error_response],
                session_state={}
            )
        
    except Exception as e:
        print(f"Error in run_sse endpoint: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Debug endpoint to see what the frontend is sending
@app.post("/debug/request")
async def debug_request(request_data: dict):
    """Debug endpoint to see exactly what data is being sent"""
    print(f"DEBUG - Received request data: {request_data}")
    print(f"DEBUG - Request data type: {type(request_data)}")
    print(f"DEBUG - Request keys: {list(request_data.keys()) if isinstance(request_data, dict) else 'Not a dict'}")
    
    return {
        "received_data": request_data,
        "data_type": str(type(request_data)),
        "keys": list(request_data.keys()) if isinstance(request_data, dict) else None,
        "message": "Debug data received successfully"
    }

# Alternative endpoint that accepts raw request body
@app.post("/debug/raw")
async def debug_raw_request(request: Request):
    """Debug endpoint to see raw request data"""
    try:
        body = await request.body()
        content_type = request.headers.get("content-type", "unknown")
        
        print(f"DEBUG RAW - Content-Type: {content_type}")
        print(f"DEBUG RAW - Body: {body}")
        
        # Try to parse as JSON
        try:
            import json
            parsed_json = json.loads(body.decode('utf-8'))
            print(f"DEBUG RAW - Parsed JSON: {parsed_json}")
        except:
            parsed_json = None
            print("DEBUG RAW - Could not parse as JSON")
        
        return {
            "content_type": content_type,
            "body_raw": body.decode('utf-8') if body else None,
            "body_parsed": parsed_json,
            "headers": dict(request.headers)
        }
    except Exception as e:
        print(f"DEBUG RAW - Error: {str(e)}")
        return {"error": str(e)}

# Additional CORS preflight handler (backup)
@app.options("/{full_path:path}")
async def options_handler(full_path: str):
    """Handle OPTIONS requests for CORS preflight"""
    return {"message": "OK"}

if __name__ == "__main__":
    print("Starting RAG Agent FastAPI server...")
    print("Server will be available at: http://localhost:8000")
    print("API documentation at: http://localhost:8000/docs")
    
    uvicorn.run(
        "server:app",  # Import string for reload support
        host="0.0.0.0", 
        port=8000,
        reload=True,  # Enable auto-reload during development
        log_level="info"
    ) 