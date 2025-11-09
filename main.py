"""FastAPI server for NL2SQL backend"""

import os
import logging
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from src.core.converter import NL2SQLConverter
from src.models.sql_query import DatabaseType
from src.services.chat_service import ChatService
from src.api.models import (
    ChatRequest,
    ChatResponse,
    SchemaResponse,
    HealthResponse,
    ErrorResponse,
    ConversationHistoryRequest,
    ConversationHistoryResponse,
    BatchChatRequest,
    BatchChatResponse,
    ChatMessage
)

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global variables for converter and chat service
converter: Optional[NL2SQLConverter] = None
chat_service: Optional[ChatService] = None


def get_database_type(connection_string: str) -> DatabaseType:
    """Detect database type from connection string"""
    if connection_string.startswith("postgresql://"):
        return DatabaseType.POSTGRESQL
    elif connection_string.startswith("mysql://") or connection_string.startswith("mysql+pymysql://"):
        return DatabaseType.MYSQL
    else:
        raise ValueError("Unsupported database type")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown"""
    global converter, chat_service
    
    # Startup
    logger.info("Starting NL2SQL backend server...")
    
    try:
        # Initialize converter
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            raise ValueError("DATABASE_URL not set")
        
        db_type = get_database_type(db_url)
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        default_limit = int(os.getenv("DEFAULT_LIMIT", "100"))
        
        converter = NL2SQLConverter(
            connection_string=db_url,
            database_type=db_type,
            model=model,
            enable_few_shot=True,
            default_limit=default_limit
        )
        
        # Load schema
        logger.info("Loading database schema...")
        converter.load_schema()
        logger.info("Schema loaded successfully")
        
        # Initialize chat service
        chat_service = ChatService(converter)
        logger.info("Chat service initialized")
        
        logger.info("✓ NL2SQL backend server started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down NL2SQL backend server...")
    if converter:
        converter.close()
    logger.info("✓ Server shut down successfully")


# Create FastAPI app
app = FastAPI(
    title="NL2SQL Backend API",
    description="Natural Language to SQL Converter API",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint"""
    return {
        "message": "NL2SQL Backend API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint"""
    global converter
    
    db_connected = False
    openai_configured = False
    
    try:
        if converter:
            db_connected = converter.test_connection()
            openai_configured = True
    except Exception as e:
        logger.error(f"Health check error: {e}")
    
    status_value = "healthy" if (db_connected and openai_configured) else "unhealthy"
    
    return HealthResponse(
        status=status_value,
        database_connected=db_connected,
        openai_configured=openai_configured
    )


@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest):
    """
    Process a natural language question and generate SQL
    
    - **message**: Natural language question
    - **session_id**: Optional session ID for conversation tracking
    - **execute_query**: Whether to execute the generated query
    - **temperature**: Model temperature (0.0-1.0)
    """
    global chat_service
    
    if not chat_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat service not initialized"
        )
    
    try:
        response = await chat_service.process_message(
            message=request.message,
            session_id=request.session_id,
            execute_query=request.execute_query,
            temperature=request.temperature
        )
        return response
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/chat/batch", response_model=BatchChatResponse, tags=["Chat"])
async def batch_chat(request: BatchChatRequest):
    """
    Process multiple questions in batch
    
    - **messages**: List of natural language questions (max 10)
    - **session_id**: Optional session ID
    - **execute_queries**: Whether to execute all queries
    - **temperature**: Model temperature
    """
    global chat_service
    
    if not chat_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat service not initialized"
        )
    
    try:
        results = await chat_service.process_batch_messages(
            messages=request.messages,
            session_id=request.session_id,
            execute_queries=request.execute_queries,
            temperature=request.temperature
        )
        
        session_id = results[0].session_id if results else chat_service.generate_session_id()
        
        return BatchChatResponse(
            session_id=session_id,
            results=results,
            total_processed=len(results)
        )
        
    except Exception as e:
        logger.error(f"Error in batch chat endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/conversation/history", response_model=ConversationHistoryResponse, tags=["Conversation"])
async def get_conversation_history(request: ConversationHistoryRequest):
    """
    Get conversation history for a session
    
    - **session_id**: Session ID
    - **limit**: Maximum messages to return (default: 50, max: 100)
    """
    global chat_service
    
    if not chat_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat service not initialized"
        )
    
    try:
        messages = chat_service.get_conversation_history(
            session_id=request.session_id,
            limit=request.limit
        )
        
        return ConversationHistoryResponse(
            session_id=request.session_id,
            messages=messages,
            total_messages=len(messages)
        )
        
    except Exception as e:
        logger.error(f"Error getting conversation history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.delete("/conversation/{session_id}", tags=["Conversation"])
async def clear_conversation(session_id: str):
    """
    Clear conversation history for a session
    
    - **session_id**: Session ID to clear
    """
    global chat_service
    
    if not chat_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat service not initialized"
        )
    
    try:
        chat_service.clear_conversation(session_id)
        return {"message": f"Conversation {session_id} cleared successfully"}
        
    except Exception as e:
        logger.error(f"Error clearing conversation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/schema", response_model=SchemaResponse, tags=["Database"])
async def get_schema(include_sample_data: bool = False):
    """
    Get database schema information
    
    - **include_sample_data**: Include sample data from tables
    """
    global converter
    
    if not converter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Converter not initialized"
        )
    
    try:
        schema = converter.schema if converter.schema else converter.load_schema(include_sample_data)
        
        return SchemaResponse(
            database_name=schema.database_name,
            database_type=schema.database_type.value,
            total_tables=schema.total_tables,
            tables=[table.model_dump() for table in schema.tables]
        )
        
    except Exception as e:
        logger.error(f"Error getting schema: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/sessions", tags=["Conversation"])
async def get_active_sessions():
    """Get list of active session IDs"""
    global chat_service
    
    if not chat_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat service not initialized"
        )
    
    return {
        "total_sessions": chat_service.get_session_count(),
        "session_ids": chat_service.get_all_sessions()
    }


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "message": str(exc),
            "details": None
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )
