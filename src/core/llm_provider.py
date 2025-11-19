"""LLM Provider Adapters - Support multiple LLM providers"""

import os
import logging
from typing import Optional, Dict, Any
from enum import Enum
import instructor
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    """Supported LLM providers"""
    OPENAI = "openai"
    GEMINI = "gemini"
    OPENROUTER = "openrouter"
    ANTHROPIC = "anthropic"
    AZURE_OPENAI = "azure_openai"


class LLMConfig(BaseModel):
    """Configuration for LLM provider"""
    provider: LLMProvider
    api_key: str
    model: str
    base_url: Optional[str] = None
    temperature: float = 0.1
    max_tokens: Optional[int] = None
    timeout: int = 30


def get_llm_client(config: LLMConfig):
    """
    Get instructor-wrapped LLM client based on provider
    
    Args:
        config: LLM configuration
        
    Returns:
        Instructor-wrapped client
    """
    provider = config.provider
    
    if provider == LLMProvider.OPENAI:
        return _get_openai_client(config)
    elif provider == LLMProvider.GEMINI:
        return _get_gemini_client(config)
    elif provider == LLMProvider.OPENROUTER:
        return _get_openrouter_client(config)
    elif provider == LLMProvider.ANTHROPIC:
        return _get_anthropic_client(config)
    elif provider == LLMProvider.AZURE_OPENAI:
        return _get_azure_openai_client(config)
    else:
        raise ValueError(f"Unsupported provider: {provider}")


def _get_openai_client(config: LLMConfig):
    """Get OpenAI client"""
    from openai import OpenAI
    
    client = OpenAI(
        api_key=config.api_key,
        timeout=config.timeout
    )
    return instructor.from_openai(client)


def _get_gemini_client(config: LLMConfig):
    """Get Google Gemini client using OpenAI-compatible API"""
    from openai import OpenAI
    
    # Gemini through OpenAI-compatible endpoint
    client = OpenAI(
        api_key=config.api_key,
        base_url=config.base_url or "https://generativelanguage.googleapis.com/v1beta/openai/",
        timeout=config.timeout
    )
    return instructor.from_openai(client)


def _get_openrouter_client(config: LLMConfig):
    """Get OpenRouter client (OpenAI-compatible)"""
    from openai import OpenAI
    
    client = OpenAI(
        api_key=config.api_key,
        base_url=config.base_url or "https://openrouter.ai/api/v1",
        timeout=config.timeout,
        default_headers={
            "HTTP-Referer": "https://github.com/nl2sql",
            "X-Title": "NL2SQL"
        }
    )
    return instructor.from_openai(client)


def _get_anthropic_client(config: LLMConfig):
    """Get Anthropic Claude client"""
    from anthropic import Anthropic
    
    client = Anthropic(api_key=config.api_key)
    return instructor.from_anthropic(client)


def _get_azure_openai_client(config: LLMConfig):
    """Get Azure OpenAI client"""
    from openai import AzureOpenAI
    
    # Azure requires additional env vars: AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_VERSION
    client = AzureOpenAI(
        api_key=config.api_key,
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
        timeout=config.timeout
    )
    return instructor.from_openai(client)


def get_default_model(provider: LLMProvider) -> str:
    """Get default model for each provider"""
    defaults = {
        LLMProvider.OPENAI: "gpt-4o-mini",
        LLMProvider.GEMINI: "gemini-1.5-flash",
        LLMProvider.OPENROUTER: "openai/gpt-4o-mini",  # Can use any model on OpenRouter
        LLMProvider.ANTHROPIC: "claude-3-haiku-20240307",
        LLMProvider.AZURE_OPENAI: "gpt-4o-mini"
    }
    return defaults.get(provider, "gpt-4o-mini")


def create_llm_config_from_env() -> LLMConfig:
    """
    Create LLM config from environment variables
    
    Environment variables:
        LLM_PROVIDER: openai, gemini, openrouter, anthropic, azure_openai (default: openai)
        OPENAI_API_KEY: For OpenAI
        GEMINI_API_KEY or GOOGLE_API_KEY: For Gemini
        OPENROUTER_API_KEY: For OpenRouter
        ANTHROPIC_API_KEY: For Anthropic
        AZURE_OPENAI_API_KEY: For Azure OpenAI
        LLM_MODEL: Model name (optional, uses default if not set)
        LLM_BASE_URL: Custom base URL (optional)
        LLM_TEMPERATURE: Temperature (default: 0.1)
        LLM_TIMEOUT: Timeout in seconds (default: 30)
    """
    provider_str = os.getenv("LLM_PROVIDER", "openai").lower()
    provider = LLMProvider(provider_str)
    
    # Get API key based on provider
    api_key_map = {
        LLMProvider.OPENAI: "OPENAI_API_KEY",
        LLMProvider.GEMINI: ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
        LLMProvider.OPENROUTER: "OPENROUTER_API_KEY",
        LLMProvider.ANTHROPIC: "ANTHROPIC_API_KEY",
        LLMProvider.AZURE_OPENAI: ["AZURE_OPENAI_API_KEY", "AZURE_OPENAI_KEY"]
    }
    
    env_keys = api_key_map[provider]
    if isinstance(env_keys, str):
        env_keys = [env_keys]
    
    api_key = None
    for key in env_keys:
        api_key = os.getenv(key)
        if api_key:
            break
    
    if not api_key:
        raise ValueError(f"API key not found. Set one of: {', '.join(env_keys)}")
    
    # Get model (use env var or default)
    model = os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL") or get_default_model(provider)
    
    # Get optional settings
    base_url = os.getenv("LLM_BASE_URL")
    temperature = float(os.getenv("LLM_TEMPERATURE", "0.1"))
    timeout = int(os.getenv("LLM_TIMEOUT", "30"))
    
    config = LLMConfig(
        provider=provider,
        api_key=api_key,
        model=model,
        base_url=base_url,
        temperature=temperature,
        timeout=timeout
    )
    
    logger.info(f"LLM Config: provider={provider}, model={model}")
    return config


# Model recommendations for different providers
RECOMMENDED_MODELS = {
    LLMProvider.OPENAI: [
        "gpt-4o-mini",  # Fast, cheap, good for SQL
        "gpt-4o",       # Most capable
        "gpt-4-turbo",  # Good balance
    ],
    LLMProvider.GEMINI: [
        "gemini-1.5-flash",    # Fast and efficient
        "gemini-1.5-pro",      # Most capable
        "gemini-2.0-flash-exp" # Latest experimental
    ],
    LLMProvider.OPENROUTER: [
        "openai/gpt-4o-mini",           # Cheap OpenAI
        "anthropic/claude-3-haiku",     # Fast Anthropic
        "google/gemini-flash-1.5",      # Fast Google
        "meta-llama/llama-3.1-8b-instruct",  # Open source
    ],
    LLMProvider.ANTHROPIC: [
        "claude-3-haiku-20240307",   # Fast and cheap
        "claude-3-5-sonnet-20241022", # Most capable
        "claude-3-opus-20240229",    # Best quality
    ],
    LLMProvider.AZURE_OPENAI: [
        "gpt-4o-mini",
        "gpt-4o",
        "gpt-4-turbo"
    ]
}
