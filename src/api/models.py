"""Pydantic models for API requests and responses"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class ChatMessage(BaseModel):
    """Single chat message"""
    role: str = Field(..., description="Role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    timestamp: Optional[datetime] = Field(default=None, description="Message timestamp")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")


class ChatRequest(BaseModel):
    """Request model for chat endpoint"""
    message: str = Field(..., description="User's natural language question", min_length=1)
    session_id: Optional[str] = Field(default=None, description="Session ID for conversation tracking")
    execute_query: bool = Field(default=False, description="Whether to execute the generated query")
    temperature: float = Field(default=0.1, ge=0.0, le=1.0, description="Model temperature")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Show me all users registered in the last 30 days",
                "session_id": "session-123",
                "execute_query": True,
                "temperature": 0.1
            }
        }


class SQLGenerationResponse(BaseModel):
    """Response model for SQL generation"""
    query: str = Field(..., description="Generated SQL query")
    explanation: str = Field(..., description="Explanation of the query")
    confidence: float = Field(..., description="Confidence score (0-1)")
    tables_used: List[str] = Field(..., description="Tables referenced in query")
    potential_issues: Optional[List[str]] = Field(default=None, description="Warnings or concerns")


class QueryExecutionResponse(BaseModel):
    """Response model for query execution"""
    success: bool = Field(..., description="Whether execution was successful")
    rows: Optional[List[Dict[str, Any]]] = Field(default=None, description="Query results")
    row_count: int = Field(..., description="Number of rows returned")
    execution_time: float = Field(..., description="Execution time in seconds")
    columns: Optional[List[str]] = Field(default=None, description="Column names")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")


class ChatResponse(BaseModel):
    """Response model for chat endpoint"""
    message_id: str = Field(..., description="Unique message ID")
    session_id: str = Field(..., description="Session ID")
    sql_generation: SQLGenerationResponse = Field(..., description="SQL generation details")
    execution: Optional[QueryExecutionResponse] = Field(default=None, description="Execution results if executed")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message_id": "msg-123",
                "session_id": "session-123",
                "sql_generation": {
                    "query": "SELECT * FROM users WHERE created_at >= NOW() - INTERVAL '30 days'",
                    "explanation": "This query retrieves all users registered in the last 30 days",
                    "confidence": 0.95,
                    "tables_used": ["users"],
                    "potential_issues": None
                },
                "execution": None,
                "timestamp": "2024-11-09T10:30:00Z"
            }
        }


class SchemaResponse(BaseModel):
    """Response model for schema endpoint"""
    database_name: str = Field(..., description="Database name")
    database_type: str = Field(..., description="Database type")
    total_tables: int = Field(..., description="Total number of tables")
    tables: List[Dict[str, Any]] = Field(..., description="Table details")


class HealthResponse(BaseModel):
    """Response model for health check"""
    status: str = Field(..., description="Service status")
    database_connected: bool = Field(..., description="Database connection status")
    openai_configured: bool = Field(..., description="OpenAI API configured")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseModel):
    """Response model for errors"""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional details")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ConversationHistoryRequest(BaseModel):
    """Request model for conversation history"""
    session_id: str = Field(..., description="Session ID to retrieve history")
    limit: int = Field(default=50, ge=1, le=100, description="Max messages to return")


class ConversationHistoryResponse(BaseModel):
    """Response model for conversation history"""
    session_id: str = Field(..., description="Session ID")
    messages: List[ChatMessage] = Field(..., description="Conversation messages")
    total_messages: int = Field(..., description="Total messages in session")


class BatchChatRequest(BaseModel):
    """Request model for batch chat processing"""
    messages: List[str] = Field(..., description="List of user questions", min_items=1, max_items=10)
    session_id: Optional[str] = Field(default=None, description="Session ID")
    execute_queries: bool = Field(default=False, description="Execute all queries")
    temperature: float = Field(default=0.1, ge=0.0, le=1.0)


class BatchChatResponse(BaseModel):
    """Response model for batch chat processing"""
    session_id: str = Field(..., description="Session ID")
    results: List[ChatResponse] = Field(..., description="Results for each message")
    total_processed: int = Field(..., description="Number of messages processed")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
