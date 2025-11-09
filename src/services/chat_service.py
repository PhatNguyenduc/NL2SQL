"""Chat service for handling conversation logic"""

import uuid
from typing import Dict, List, Optional
from datetime import datetime
from src.api.models import ChatMessage, ChatResponse, SQLGenerationResponse, QueryExecutionResponse
from src.core.converter import NL2SQLConverter
from src.models.sql_query import DatabaseType
import logging

logger = logging.getLogger(__name__)


class ChatService:
    """Service for handling chat interactions and conversation history"""
    
    def __init__(self, converter: NL2SQLConverter):
        """
        Initialize chat service
        
        Args:
            converter: NL2SQLConverter instance
        """
        self.converter = converter
        self.conversations: Dict[str, List[ChatMessage]] = {}
        
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
        if session_id not in self.conversations:
            self.conversations[session_id] = []
        
        message = ChatMessage(
            role=role,
            content=content,
            timestamp=datetime.utcnow(),
            metadata=metadata
        )
        
        self.conversations[session_id].append(message)
        return message
    
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
        messages = self.conversations.get(session_id, [])
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
            # Generate SQL
            sql_query = self.converter.generate_sql(message, temperature=temperature)
            
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
                timestamp=datetime.utcnow()
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
