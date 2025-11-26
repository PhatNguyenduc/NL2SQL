"""Chat service for handling conversation logic"""

import uuid
from typing import Dict, List, Optional
from datetime import datetime, timezone, timedelta
from src.api.models import ChatMessage, ChatResponse, SQLGenerationResponse, QueryExecutionResponse
from src.core.converter import NL2SQLConverter
import logging

logger = logging.getLogger(__name__)

# Session configuration
MAX_SESSIONS = 1000  # Maximum number of sessions to keep
SESSION_EXPIRY_HOURS = 24  # Sessions older than this will be cleaned up


class SessionData:
    """Container for session data with metadata"""
    def __init__(self):
        self.messages: List[ChatMessage] = []
        self.created_at: datetime = datetime.now(timezone.utc)
        self.last_accessed: datetime = datetime.now(timezone.utc)
    
    def touch(self):
        """Update last accessed time"""
        self.last_accessed = datetime.now(timezone.utc)
    
    def is_expired(self, expiry_hours: int = SESSION_EXPIRY_HOURS) -> bool:
        """Check if session has expired"""
        expiry_time = datetime.now(timezone.utc) - timedelta(hours=expiry_hours)
        return self.last_accessed < expiry_time


class ChatService:
    """Service for handling chat interactions and conversation history"""
    
    def __init__(self, converter: NL2SQLConverter):
        """
        Initialize chat service
        
        Args:
            converter: NL2SQLConverter instance
        """
        self.converter = converter
        self.conversations: Dict[str, SessionData] = {}
        self._cleanup_counter = 0
        
    def generate_session_id(self) -> str:
        """Generate a unique session ID"""
        return f"session-{uuid.uuid4().hex[:12]}"
    
    def generate_message_id(self) -> str:
        """Generate a unique message ID"""
        return f"msg-{uuid.uuid4().hex[:12]}"
    
    def add_message_to_history(
        self, 
        session_id: str, 
        role: str, 
        content: str,
        metadata: Optional[Dict] = None
    ) -> ChatMessage:
        """
        Add a message to conversation history
        
        Args:
            session_id: Session ID
            role: Message role (user/assistant)
            content: Message content
            metadata: Additional metadata
            
        Returns:
            ChatMessage object
        """
        # Run cleanup periodically
        self._cleanup_counter += 1
        if self._cleanup_counter >= 100:
            self._cleanup_expired_sessions()
            self._cleanup_counter = 0
        
        if session_id not in self.conversations:
            if len(self.conversations) >= MAX_SESSIONS:
                self._evict_oldest_session()
            self.conversations[session_id] = SessionData()
        
        session = self.conversations[session_id]
        session.touch()
        
        message = ChatMessage(
            role=role,
            content=content,
            timestamp=datetime.now(timezone.utc),
            metadata=metadata
        )
        
        session.messages.append(message)
        return message
    
    def _cleanup_expired_sessions(self):
        """Remove expired sessions to free memory"""
        expired = [sid for sid, s in self.conversations.items() if s.is_expired()]
        for sid in expired:
            del self.conversations[sid]
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")
    
    def _evict_oldest_session(self):
        """Evict the oldest session when max sessions reached"""
        if not self.conversations:
            return
        oldest = min(self.conversations.keys(), 
                     key=lambda sid: self.conversations[sid].last_accessed)
        del self.conversations[oldest]
        logger.info(f"Evicted oldest session: {oldest}")
    
    def _build_conversation_history(
        self, 
        session_id: str, 
        max_turns: int = 5
    ) -> List[Dict[str, str]]:
        """
        Build conversation history for LLM context
        
        Args:
            session_id: Session ID
            max_turns: Maximum conversation turns to include
            
        Returns:
            List of message dicts with role and content
        """
        session = self.conversations.get(session_id)
        if not session or not session.messages:
            return []
        
        # Get recent messages (excluding the current user message which was just added)
        recent_messages = session.messages[-(max_turns * 2 + 1):-1]  # *2 for user+assistant pairs
        
        history = []
        for msg in recent_messages:
            # For assistant messages, extract just the SQL if available
            content = msg.content
            if msg.role == "assistant" and msg.metadata:
                sql = msg.metadata.get("sql_query")
                if sql:
                    content = f"SQL: {sql}"
            
            history.append({
                "role": msg.role,
                "content": content
            })
        
        return history
    
    def get_conversation_history(
        self, 
        session_id: str, 
        limit: Optional[int] = None
    ) -> List[ChatMessage]:
        """
        Get conversation history for a session
        
        Args:
            session_id: Session ID
            limit: Maximum messages to return
            
        Returns:
            List of ChatMessage objects
        """
        session = self.conversations.get(session_id)
        if not session:
            return []
        session.touch()
        messages = session.messages
        if limit:
            return messages[-limit:]
        return messages
    
    def clear_conversation(self, session_id: str):
        """
        Clear conversation history for a session
        
        Args:
            session_id: Session ID
        """
        if session_id in self.conversations:
            del self.conversations[session_id]
    
    async def process_message(
        self,
        message: str,
        session_id: Optional[str] = None,
        execute_query: bool = False,
        temperature: float = 0.1
    ) -> ChatResponse:
        """
        Process a user message and generate SQL response
        
        Args:
            message: User's natural language question
            session_id: Session ID (generated if None)
            execute_query: Whether to execute the query
            temperature: Model temperature
            
        Returns:
            ChatResponse object
        """
        # Generate IDs if needed
        if not session_id:
            session_id = self.generate_session_id()
        message_id = self.generate_message_id()
        
        # Add user message to history
        self.add_message_to_history(
            session_id=session_id,
            role="user",
            content=message
        )
        
        logger.info(f"Processing message in session {session_id}: {message}")
        
        try:
            # Build conversation history for context
            conversation_history = self._build_conversation_history(session_id)
            
            # Generate SQL with conversation context
            sql_query = self.converter.generate_sql(
                message, 
                temperature=temperature,
                conversation_history=conversation_history
            )
            
            # Create SQL generation response
            sql_response = SQLGenerationResponse(
                query=sql_query.query,
                explanation=sql_query.explanation,
                confidence=sql_query.confidence,
                tables_used=sql_query.tables_used,
                potential_issues=sql_query.potential_issues
            )
            
            # Execute query if requested
            execution_response = None
            if execute_query:
                result = self.converter.query_executor.execute(sql_query.query)
                execution_response = QueryExecutionResponse(
                    success=result.success,
                    rows=result.rows,
                    row_count=result.row_count,
                    execution_time=result.execution_time,
                    columns=result.columns,
                    error_message=result.error_message
                )
            
            # Create assistant message
            assistant_content = f"Generated SQL:\n{sql_query.query}\n\nExplanation: {sql_query.explanation}"
            if execution_response and execution_response.success:
                assistant_content += f"\n\nReturned {execution_response.row_count} rows"
            
            self.add_message_to_history(
                session_id=session_id,
                role="assistant",
                content=assistant_content,
                metadata={
                    "sql_query": sql_query.query,
                    "confidence": sql_query.confidence,
                    "executed": execute_query
                }
            )
            
            # Create response
            response = ChatResponse(
                message_id=message_id,
                session_id=session_id,
                sql_generation=sql_response,
                execution=execution_response,
                timestamp=datetime.now(timezone.utc)
            )
            
            logger.info(f"Successfully processed message {message_id}")
            return response
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            raise
    
    async def process_batch_messages(
        self,
        messages: List[str],
        session_id: Optional[str] = None,
        execute_queries: bool = False,
        temperature: float = 0.1
    ) -> List[ChatResponse]:
        """
        Process multiple messages in batch
        
        Args:
            messages: List of user questions
            session_id: Session ID (generated if None)
            execute_queries: Whether to execute queries
            temperature: Model temperature
            
        Returns:
            List of ChatResponse objects
        """
        if not session_id:
            session_id = self.generate_session_id()
        
        responses = []
        for message in messages:
            try:
                response = await self.process_message(
                    message=message,
                    session_id=session_id,
                    execute_query=execute_queries,
                    temperature=temperature
                )
                responses.append(response)
            except Exception as e:
                logger.error(f"Error processing message '{message}': {e}")
                # Continue with other messages
                continue
        
        return responses
    
    def get_session_count(self) -> int:
        """Get number of active sessions"""
        return len(self.conversations)
    
    def get_all_sessions(self) -> List[str]:
        """Get list of all session IDs"""
        return list(self.conversations.keys())
