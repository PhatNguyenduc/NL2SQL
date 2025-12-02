"""Async Chat Service - High-performance async version"""

import uuid
import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
from src.api.models import ChatMessage, ChatResponse, SQLGenerationResponse, QueryExecutionResponse
from src.core.async_converter import AsyncNL2SQLConverter
from src.models.sql_query import SQLQuery, QueryResult
import logging

logger = logging.getLogger(__name__)

# Session configuration
MAX_SESSIONS = 1000
SESSION_EXPIRY_HOURS = 24


class SessionData:
    """Container for session data with metadata"""
    def __init__(self):
        self.messages: List[ChatMessage] = []
        self.created_at: datetime = datetime.now(timezone.utc)
        self.last_accessed: datetime = datetime.now(timezone.utc)
        self._lock = asyncio.Lock()
    
    def touch(self):
        """Update last accessed time"""
        self.last_accessed = datetime.now(timezone.utc)
    
    def is_expired(self, expiry_hours: int = SESSION_EXPIRY_HOURS) -> bool:
        """Check if session has expired"""
        expiry_time = datetime.now(timezone.utc) - timedelta(hours=expiry_hours)
        return self.last_accessed < expiry_time


class AsyncChatService:
    """
    High-performance async chat service
    
    Features:
    - True async SQL generation with non-blocking LLM calls
    - Parallel batch processing
    - Concurrent session management
    - Background cache operations
    """
    
    def __init__(self, converter: AsyncNL2SQLConverter):
        """
        Initialize async chat service
        
        Args:
            converter: AsyncNL2SQLConverter instance
        """
        self.converter = converter
        self.conversations: Dict[str, SessionData] = {}
        self._cleanup_counter = 0
        self._cleanup_lock = asyncio.Lock()
        
    def generate_session_id(self) -> str:
        """Generate a unique session ID"""
        return f"session-{uuid.uuid4().hex[:12]}"
    
    def generate_message_id(self) -> str:
        """Generate a unique message ID"""
        return f"msg-{uuid.uuid4().hex[:12]}"
    
    async def add_message_to_history(
        self, 
        session_id: str, 
        role: str, 
        content: str,
        metadata: Optional[Dict] = None
    ) -> ChatMessage:
        """
        Add a message to conversation history (async-safe)
        
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
            asyncio.create_task(self._cleanup_expired_sessions())
            self._cleanup_counter = 0
        
        if session_id not in self.conversations:
            async with self._cleanup_lock:
                if len(self.conversations) >= MAX_SESSIONS:
                    await self._evict_oldest_session()
                self.conversations[session_id] = SessionData()
        
        session = self.conversations[session_id]
        session.touch()
        
        message = ChatMessage(
            role=role,
            content=content,
            timestamp=datetime.now(timezone.utc),
            metadata=metadata
        )
        
        async with session._lock:
            session.messages.append(message)
        
        return message
    
    async def _cleanup_expired_sessions(self):
        """Remove expired sessions to free memory"""
        async with self._cleanup_lock:
            expired = [sid for sid, s in self.conversations.items() if s.is_expired()]
            for sid in expired:
                del self.conversations[sid]
            if expired:
                logger.info(f"Cleaned up {len(expired)} expired sessions")
    
    async def _evict_oldest_session(self):
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
        
        recent_messages = session.messages[-(max_turns * 2 + 1):-1]
        
        history = []
        for msg in recent_messages:
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
        """Clear conversation history for a session"""
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
        Process a user message and generate SQL response (async)
        
        Args:
            message: User's natural language question
            session_id: Session ID (generated if None)
            execute_query: Whether to execute the query
            temperature: Model temperature
            
        Returns:
            ChatResponse object
        """
        if not session_id:
            session_id = self.generate_session_id()
        message_id = self.generate_message_id()
        
        # Add user message to history
        await self.add_message_to_history(
            session_id=session_id,
            role="user",
            content=message
        )
        
        logger.info(f"Async processing message in session {session_id}: {message}")
        
        try:
            # Build conversation history for context
            conversation_history = self._build_conversation_history(session_id)
            
            # Async SQL generation
            sql_query = await self.converter.generate_sql(
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
                # Run sync database operation in thread pool
                result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.converter.query_executor.execute(sql_query.query)
                )
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
            
            await self.add_message_to_history(
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
            
            logger.info(f"Successfully processed async message {message_id}")
            return response
            
        except Exception as e:
            logger.error(f"Error processing async message: {e}")
            raise
    
    async def process_batch_messages(
        self,
        messages: List[str],
        session_id: Optional[str] = None,
        execute_queries: bool = False,
        temperature: float = 0.1,
        max_concurrent: int = 5
    ) -> List[ChatResponse]:
        """
        Process multiple messages in parallel (true async batch)
        
        Args:
            messages: List of user questions
            session_id: Session ID (generated if None)
            execute_queries: Whether to execute queries
            temperature: Model temperature
            max_concurrent: Maximum concurrent requests
            
        Returns:
            List of ChatResponse objects
        """
        if not session_id:
            session_id = self.generate_session_id()
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_with_limit(message: str) -> Optional[ChatResponse]:
            async with semaphore:
                try:
                    return await self.process_message(
                        message=message,
                        session_id=session_id,
                        execute_query=execute_queries,
                        temperature=temperature
                    )
                except Exception as e:
                    logger.error(f"Error processing message '{message}': {e}")
                    return None
        
        # Process all messages in parallel
        tasks = [process_with_limit(msg) for msg in messages]
        results = await asyncio.gather(*tasks)
        
        # Filter out failed results
        return [r for r in results if r is not None]
    
    async def generate_sql_batch(
        self,
        questions: List[str],
        max_concurrent: int = 5,
        **kwargs
    ) -> List[SQLQuery]:
        """
        Generate SQL for multiple questions in parallel (no chat history)
        
        Args:
            questions: List of natural language questions
            max_concurrent: Maximum concurrent LLM calls
            **kwargs: Additional args passed to generate_sql
            
        Returns:
            List of SQLQuery objects
        """
        return await self.converter.generate_sql_batch(
            questions=questions,
            max_concurrent=max_concurrent,
            **kwargs
        )
    
    def get_session_count(self) -> int:
        """Get number of active sessions"""
        return len(self.conversations)
    
    def get_all_sessions(self) -> List[str]:
        """Get list of all session IDs"""
        return list(self.conversations.keys())
    
    async def close(self):
        """Close async resources"""
        await self.converter.close()
