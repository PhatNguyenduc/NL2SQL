"""Async LLM Provider Adapters - Support async calls for better performance"""

import os
import logging
import asyncio
from typing import Optional, Dict, Any, List, TypeVar, Type
from enum import Enum
import instructor
from pydantic import BaseModel

from src.core.llm_provider import LLMConfig, LLMProvider, get_default_model

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)


class AsyncLLMClient:
    """Async wrapper for LLM clients with instructor support"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.provider = config.provider
        self.model = config.model
        self._client = None
        self._async_client = None
        
    async def _get_async_client(self):
        """Lazy initialization of async client"""
        if self._async_client is None:
            self._async_client = await self._create_async_client()
        return self._async_client
    
    async def _create_async_client(self):
        """Create async client based on provider"""
        if self.provider == LLMProvider.OPENAI:
            return await self._create_openai_async_client()
        elif self.provider == LLMProvider.GEMINI:
            return await self._create_gemini_async_client()
        elif self.provider == LLMProvider.OPENROUTER:
            return await self._create_openrouter_async_client()
        elif self.provider == LLMProvider.ANTHROPIC:
            return await self._create_anthropic_async_client()
        elif self.provider == LLMProvider.AZURE_OPENAI:
            return await self._create_azure_openai_async_client()
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
    
    async def _create_openai_async_client(self):
        """Create async OpenAI client"""
        from openai import AsyncOpenAI
        
        client = AsyncOpenAI(
            api_key=self.config.api_key,
            timeout=self.config.timeout
        )
        return instructor.from_openai(client)
    
    async def _create_gemini_async_client(self):
        """Create async Gemini client via OpenAI-compatible API"""
        from openai import AsyncOpenAI
        
        client = AsyncOpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url or "https://generativelanguage.googleapis.com/v1beta/openai/",
            timeout=self.config.timeout
        )
        return instructor.from_openai(client)
    
    async def _create_openrouter_async_client(self):
        """Create async OpenRouter client"""
        from openai import AsyncOpenAI
        
        client = AsyncOpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url or "https://openrouter.ai/api/v1",
            timeout=self.config.timeout,
            default_headers={
                "HTTP-Referer": "https://github.com/nl2sql",
                "X-Title": "NL2SQL"
            }
        )
        return instructor.from_openai(client)
    
    async def _create_anthropic_async_client(self):
        """Create async Anthropic client"""
        from anthropic import AsyncAnthropic
        
        client = AsyncAnthropic(
            api_key=self.config.api_key,
            timeout=float(self.config.timeout)
        )
        return instructor.from_anthropic(client)
    
    async def _create_azure_openai_async_client(self):
        """Create async Azure OpenAI client"""
        from openai import AsyncAzureOpenAI
        
        client = AsyncAzureOpenAI(
            api_key=self.config.api_key,
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
            timeout=self.config.timeout
        )
        return instructor.from_openai(client)
    
    async def create_completion(
        self,
        response_model: Type[T],
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_retries: int = 2
    ) -> T:
        """
        Create async completion with structured output
        
        Args:
            response_model: Pydantic model for response
            messages: Chat messages
            temperature: Model temperature
            max_retries: Maximum retry attempts
            
        Returns:
            Structured response matching response_model
        """
        client = await self._get_async_client()
        
        response = await client.chat.completions.create(
            model=self.model,
            response_model=response_model,
            messages=messages,
            temperature=temperature,
            max_retries=max_retries
        )
        
        return response
    
    async def create_batch_completions(
        self,
        requests: List[Dict[str, Any]],
        response_model: Type[T],
        max_concurrent: int = 5
    ) -> List[T]:
        """
        Create multiple completions in parallel
        
        Args:
            requests: List of request dicts with 'messages', 'temperature'
            response_model: Pydantic model for response
            max_concurrent: Maximum concurrent requests
            
        Returns:
            List of structured responses
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def limited_completion(req: Dict[str, Any]) -> T:
            async with semaphore:
                return await self.create_completion(
                    response_model=response_model,
                    messages=req.get('messages', []),
                    temperature=req.get('temperature', 0.1),
                    max_retries=req.get('max_retries', 2)
                )
        
        tasks = [limited_completion(req) for req in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions and log them
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Batch request {i} failed: {result}")
            else:
                valid_results.append(result)
        
        return valid_results
    
    async def close(self):
        """Close async client connections"""
        if self._async_client:
            # Most clients don't need explicit closing, but good practice
            self._async_client = None


class AsyncLLMPool:
    """Pool of async LLM clients for high-throughput scenarios"""
    
    def __init__(self, config: LLMConfig, pool_size: int = 3):
        self.config = config
        self.pool_size = pool_size
        self._clients: List[AsyncLLMClient] = []
        self._current_index = 0
        self._lock = asyncio.Lock()
    
    async def initialize(self):
        """Initialize the client pool"""
        self._clients = [AsyncLLMClient(self.config) for _ in range(self.pool_size)]
        # Pre-warm all clients
        await asyncio.gather(*[c._get_async_client() for c in self._clients])
        logger.info(f"Initialized async LLM pool with {self.pool_size} clients")
    
    async def get_client(self) -> AsyncLLMClient:
        """Get next client from pool (round-robin)"""
        async with self._lock:
            client = self._clients[self._current_index]
            self._current_index = (self._current_index + 1) % self.pool_size
            return client
    
    async def create_completion(
        self,
        response_model: Type[T],
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_retries: int = 2
    ) -> T:
        """Create completion using next available client"""
        client = await self.get_client()
        return await client.create_completion(
            response_model=response_model,
            messages=messages,
            temperature=temperature,
            max_retries=max_retries
        )
    
    async def close(self):
        """Close all clients in pool"""
        for client in self._clients:
            await client.close()
        self._clients = []


# Singleton instance for async client
_async_client: Optional[AsyncLLMClient] = None


async def get_async_llm_client(config: Optional[LLMConfig] = None) -> AsyncLLMClient:
    """
    Get or create async LLM client
    
    Args:
        config: LLM configuration (uses env vars if not provided)
        
    Returns:
        AsyncLLMClient instance
    """
    global _async_client
    
    if _async_client is None:
        if config is None:
            from src.core.llm_provider import create_llm_config_from_env
            config = create_llm_config_from_env()
        _async_client = AsyncLLMClient(config)
    
    return _async_client


def reset_async_client():
    """Reset the singleton async client (useful for testing)"""
    global _async_client
    _async_client = None


# Utility functions for common async patterns

async def run_with_timeout(
    coro,
    timeout: float = 30.0,
    error_msg: str = "Operation timed out"
):
    """
    Run coroutine with timeout
    
    Args:
        coro: Coroutine to run
        timeout: Timeout in seconds
        error_msg: Error message if timeout
        
    Returns:
        Coroutine result
        
    Raises:
        TimeoutError: If operation times out
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        logger.error(f"Timeout after {timeout}s: {error_msg}")
        raise TimeoutError(error_msg)


async def retry_async(
    coro_func,
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Retry async function with exponential backoff
    
    Args:
        coro_func: Async function to retry (callable that returns coroutine)
        max_retries: Maximum retry attempts
        delay: Initial delay between retries
        backoff: Backoff multiplier
        exceptions: Exceptions to catch and retry
        
    Returns:
        Function result
    """
    last_exception = None
    current_delay = delay
    
    for attempt in range(max_retries + 1):
        try:
            return await coro_func()
        except exceptions as e:
            last_exception = e
            if attempt < max_retries:
                logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {current_delay}s...")
                await asyncio.sleep(current_delay)
                current_delay *= backoff
            else:
                logger.error(f"All {max_retries + 1} attempts failed")
    
    raise last_exception
