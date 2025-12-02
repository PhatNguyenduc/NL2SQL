"""
Embedding Provider Module

Provides embeddings for semantic similarity using multiple providers:
- OpenAI (text-embedding-3-small, text-embedding-3-large)
- Sentence Transformers (all-MiniLM-L6-v2, etc.)
- Gemini (text-embedding-004)

Embeddings are used for semantic cache to find similar questions.
"""

import os
import logging
import hashlib
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingProvider(str, Enum):
    """Supported embedding providers"""
    OPENAI = "openai"
    SENTENCE_TRANSFORMERS = "sentence_transformers"
    GEMINI = "gemini"
    NONE = "none"  # Fallback to keyword-based


@dataclass
class EmbeddingConfig:
    """Configuration for embedding provider"""
    provider: EmbeddingProvider
    model: str
    api_key: Optional[str] = None
    batch_size: int = 32
    normalize: bool = True
    cache_embeddings: bool = True
    dimensions: Optional[int] = None  # For dimensionality reduction


class BaseEmbedder(ABC):
    """Abstract base class for embedding providers"""
    
    def __init__(self, config: EmbeddingConfig):
        self.config = config
        self._cache: Dict[str, np.ndarray] = {}
    
    @abstractmethod
    def embed(self, texts: List[str]) -> np.ndarray:
        """
        Generate embeddings for texts
        
        Args:
            texts: List of texts to embed
            
        Returns:
            numpy array of shape (len(texts), embedding_dim)
        """
        pass
    
    @abstractmethod
    def embed_single(self, text: str) -> np.ndarray:
        """
        Generate embedding for a single text
        
        Args:
            text: Text to embed
            
        Returns:
            numpy array of shape (embedding_dim,)
        """
        pass
    
    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return embedding dimension"""
        pass
    
    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text"""
        return hashlib.sha256(text.encode()).hexdigest()[:16]
    
    def _get_from_cache(self, text: str) -> Optional[np.ndarray]:
        """Get embedding from cache"""
        if not self.config.cache_embeddings:
            return None
        key = self._get_cache_key(text)
        return self._cache.get(key)
    
    def _set_cache(self, text: str, embedding: np.ndarray):
        """Store embedding in cache"""
        if self.config.cache_embeddings:
            key = self._get_cache_key(text)
            self._cache[key] = embedding
    
    def clear_cache(self):
        """Clear embedding cache"""
        self._cache.clear()


class OpenAIEmbedder(BaseEmbedder):
    """OpenAI embedding provider"""
    
    # Embedding dimensions for OpenAI models
    MODEL_DIMENSIONS = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
    }
    
    def __init__(self, config: EmbeddingConfig):
        super().__init__(config)
        from openai import OpenAI
        
        self.client = OpenAI(api_key=config.api_key)
        self.model = config.model or "text-embedding-3-small"
        self._dimension = config.dimensions or self.MODEL_DIMENSIONS.get(self.model, 1536)
        logger.info(f"OpenAI Embedder initialized with model: {self.model}")
    
    @property
    def dimension(self) -> int:
        return self._dimension
    
    def embed(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for multiple texts"""
        # Check cache first
        results = []
        uncached_texts = []
        uncached_indices = []
        
        for i, text in enumerate(texts):
            cached = self._get_from_cache(text)
            if cached is not None:
                results.append((i, cached))
            else:
                uncached_texts.append(text)
                uncached_indices.append(i)
        
        # Fetch uncached embeddings
        if uncached_texts:
            try:
                kwargs = {"model": self.model, "input": uncached_texts}
                if self.config.dimensions and self.model.startswith("text-embedding-3"):
                    kwargs["dimensions"] = self.config.dimensions
                
                response = self.client.embeddings.create(**kwargs)
                
                for i, emb_data in enumerate(response.data):
                    embedding = np.array(emb_data.embedding, dtype=np.float32)
                    if self.config.normalize:
                        embedding = embedding / np.linalg.norm(embedding)
                    
                    original_idx = uncached_indices[i]
                    results.append((original_idx, embedding))
                    self._set_cache(uncached_texts[i], embedding)
                    
            except Exception as e:
                logger.error(f"OpenAI embedding error: {e}")
                raise
        
        # Sort by original index and return
        results.sort(key=lambda x: x[0])
        return np.array([emb for _, emb in results])
    
    def embed_single(self, text: str) -> np.ndarray:
        """Generate embedding for single text"""
        cached = self._get_from_cache(text)
        if cached is not None:
            return cached
        
        result = self.embed([text])
        return result[0]


class SentenceTransformersEmbedder(BaseEmbedder):
    """Sentence Transformers embedding provider (local, no API needed)"""
    
    def __init__(self, config: EmbeddingConfig):
        super().__init__(config)
        try:
            from sentence_transformers import SentenceTransformer
            
            self.model_name = config.model or "all-MiniLM-L6-v2"
            self.model = SentenceTransformer(self.model_name)
            self._dimension = self.model.get_sentence_embedding_dimension()
            logger.info(f"SentenceTransformers initialized with model: {self.model_name}")
        except ImportError:
            raise ImportError(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )
    
    @property
    def dimension(self) -> int:
        return self._dimension
    
    def embed(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for multiple texts"""
        # Check cache
        results = []
        uncached_texts = []
        uncached_indices = []
        
        for i, text in enumerate(texts):
            cached = self._get_from_cache(text)
            if cached is not None:
                results.append((i, cached))
            else:
                uncached_texts.append(text)
                uncached_indices.append(i)
        
        # Encode uncached
        if uncached_texts:
            embeddings = self.model.encode(
                uncached_texts,
                batch_size=self.config.batch_size,
                normalize_embeddings=self.config.normalize,
                show_progress_bar=False
            )
            
            for i, embedding in enumerate(embeddings):
                original_idx = uncached_indices[i]
                emb_array = np.array(embedding, dtype=np.float32)
                results.append((original_idx, emb_array))
                self._set_cache(uncached_texts[i], emb_array)
        
        results.sort(key=lambda x: x[0])
        return np.array([emb for _, emb in results])
    
    def embed_single(self, text: str) -> np.ndarray:
        """Generate embedding for single text"""
        cached = self._get_from_cache(text)
        if cached is not None:
            return cached
        
        embedding = self.model.encode(
            text,
            normalize_embeddings=self.config.normalize,
            show_progress_bar=False
        )
        emb_array = np.array(embedding, dtype=np.float32)
        self._set_cache(text, emb_array)
        return emb_array


class GeminiEmbedder(BaseEmbedder):
    """Google Gemini embedding provider"""
    
    def __init__(self, config: EmbeddingConfig):
        super().__init__(config)
        from openai import OpenAI
        
        # Use OpenAI-compatible endpoint for Gemini
        self.client = OpenAI(
            api_key=config.api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
        )
        self.model = config.model or "text-embedding-004"
        self._dimension = 768  # Gemini embedding dimension
        logger.info(f"Gemini Embedder initialized with model: {self.model}")
    
    @property
    def dimension(self) -> int:
        return self._dimension
    
    def embed(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for multiple texts"""
        results = []
        uncached_texts = []
        uncached_indices = []
        
        for i, text in enumerate(texts):
            cached = self._get_from_cache(text)
            if cached is not None:
                results.append((i, cached))
            else:
                uncached_texts.append(text)
                uncached_indices.append(i)
        
        if uncached_texts:
            try:
                response = self.client.embeddings.create(
                    model=self.model,
                    input=uncached_texts
                )
                
                for i, emb_data in enumerate(response.data):
                    embedding = np.array(emb_data.embedding, dtype=np.float32)
                    if self.config.normalize:
                        embedding = embedding / np.linalg.norm(embedding)
                    
                    original_idx = uncached_indices[i]
                    results.append((original_idx, embedding))
                    self._set_cache(uncached_texts[i], embedding)
                    
            except Exception as e:
                logger.error(f"Gemini embedding error: {e}")
                raise
        
        results.sort(key=lambda x: x[0])
        return np.array([emb for _, emb in results])
    
    def embed_single(self, text: str) -> np.ndarray:
        """Generate embedding for single text"""
        cached = self._get_from_cache(text)
        if cached is not None:
            return cached
        
        result = self.embed([text])
        return result[0]


class KeywordEmbedder(BaseEmbedder):
    """
    Fallback embedder using TF-IDF style keyword vectors
    No external API needed - works offline
    """
    
    def __init__(self, config: EmbeddingConfig):
        super().__init__(config)
        self._dimension = config.dimensions or 256
        self._vocab: Dict[str, int] = {}
        self._idf: Dict[str, float] = {}
        logger.info(f"Keyword Embedder initialized (dimension={self._dimension})")
    
    @property
    def dimension(self) -> int:
        return self._dimension
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization"""
        import re
        text = text.lower()
        words = re.findall(r'\b\w+\b', text)
        return words
    
    def _hash_word(self, word: str) -> int:
        """Hash word to dimension index"""
        return hash(word) % self._dimension
    
    def embed_single(self, text: str) -> np.ndarray:
        """Generate keyword-based embedding"""
        cached = self._get_from_cache(text)
        if cached is not None:
            return cached
        
        words = self._tokenize(text)
        embedding = np.zeros(self._dimension, dtype=np.float32)
        
        # Count word frequencies
        word_counts: Dict[str, int] = {}
        for word in words:
            word_counts[word] = word_counts.get(word, 0) + 1
        
        # Build embedding using hash trick
        for word, count in word_counts.items():
            idx = self._hash_word(word)
            embedding[idx] += count
        
        # Normalize
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        
        self._set_cache(text, embedding)
        return embedding
    
    def embed(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for multiple texts"""
        return np.array([self.embed_single(t) for t in texts])


def get_embedder(config: Optional[EmbeddingConfig] = None) -> BaseEmbedder:
    """
    Get embedder instance based on configuration
    
    Args:
        config: Embedding configuration. If None, creates from env vars.
        
    Returns:
        Embedder instance
    """
    if config is None:
        config = create_embedding_config_from_env()
    
    provider = config.provider
    
    if provider == EmbeddingProvider.OPENAI:
        return OpenAIEmbedder(config)
    elif provider == EmbeddingProvider.SENTENCE_TRANSFORMERS:
        return SentenceTransformersEmbedder(config)
    elif provider == EmbeddingProvider.GEMINI:
        return GeminiEmbedder(config)
    else:
        logger.warning("No embedding provider configured, using keyword fallback")
        return KeywordEmbedder(config)


def create_embedding_config_from_env() -> EmbeddingConfig:
    """
    Create embedding config from environment variables
    
    Environment variables:
        EMBEDDING_PROVIDER: openai, sentence_transformers, gemini, none (default: auto-detect)
        EMBEDDING_MODEL: Model name (provider-specific default)
        EMBEDDING_DIMENSIONS: Dimensionality (optional, for reduction)
        EMBEDDING_BATCH_SIZE: Batch size for encoding (default: 32)
        OPENAI_API_KEY / GEMINI_API_KEY: API keys (if using API-based provider)
    """
    provider_str = os.getenv("EMBEDDING_PROVIDER", "").lower()
    
    # Auto-detect provider based on available API keys
    if not provider_str:
        if os.getenv("OPENAI_API_KEY"):
            provider_str = "openai"
        elif os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
            provider_str = "gemini"
        else:
            # Default to keyword fallback if no API key available
            provider_str = "none"
            logger.warning("No embedding API key found, using keyword fallback")
    
    try:
        provider = EmbeddingProvider(provider_str)
    except ValueError:
        logger.warning(f"Unknown embedding provider: {provider_str}, using keyword fallback")
        provider = EmbeddingProvider.NONE
    
    # Get API key based on provider
    api_key = None
    if provider == EmbeddingProvider.OPENAI:
        api_key = os.getenv("OPENAI_API_KEY")
    elif provider == EmbeddingProvider.GEMINI:
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    
    # Get model (provider-specific defaults)
    model_defaults = {
        EmbeddingProvider.OPENAI: "text-embedding-3-small",
        EmbeddingProvider.SENTENCE_TRANSFORMERS: "all-MiniLM-L6-v2",
        EmbeddingProvider.GEMINI: "text-embedding-004",
        EmbeddingProvider.NONE: "keyword"
    }
    model = os.getenv("EMBEDDING_MODEL") or model_defaults.get(provider, "")
    
    # Optional settings
    dimensions = os.getenv("EMBEDDING_DIMENSIONS")
    batch_size = int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))
    
    config = EmbeddingConfig(
        provider=provider,
        model=model,
        api_key=api_key,
        batch_size=batch_size,
        dimensions=int(dimensions) if dimensions else None,
        normalize=True,
        cache_embeddings=True
    )
    
    logger.info(f"Embedding Config: provider={provider}, model={model}")
    return config


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """
    Compute cosine similarity between two vectors
    
    Args:
        a: First vector
        b: Second vector
        
    Returns:
        Similarity score between -1 and 1
    """
    # If vectors are already normalized, dot product = cosine similarity
    return float(np.dot(a, b))


def batch_cosine_similarity(query: np.ndarray, vectors: np.ndarray) -> np.ndarray:
    """
    Compute cosine similarity between query and multiple vectors
    
    Args:
        query: Query vector of shape (dim,)
        vectors: Matrix of vectors of shape (n, dim)
        
    Returns:
        Array of similarities of shape (n,)
    """
    # Efficient batch similarity using matrix multiplication
    return np.dot(vectors, query)


# Singleton embedder instance
_embedder: Optional[BaseEmbedder] = None


def get_default_embedder() -> BaseEmbedder:
    """Get or create default embedder singleton"""
    global _embedder
    if _embedder is None:
        _embedder = get_embedder()
    return _embedder


def reset_embedder():
    """Reset embedder singleton"""
    global _embedder
    if _embedder:
        _embedder.clear_cache()
    _embedder = None
