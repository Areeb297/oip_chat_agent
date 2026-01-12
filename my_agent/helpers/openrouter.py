"""OpenRouter API helper functions for embeddings and LLM calls"""
import requests
from typing import List, Optional, Dict, Any
from ..config import (
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENROUTER_HEADERS,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_LLM_MODEL,
)
from ..models import EmbeddingResponse, LLMResponse


class OpenRouterClient:
    """Reusable client for OpenRouter API calls"""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the OpenRouter client.

        Args:
            api_key: OpenRouter API key. Uses env var if not provided.
        """
        self.api_key = api_key or OPENROUTER_API_KEY
        if not self.api_key:
            raise ValueError(
                "OpenRouter API key not found. Set OPENROUTER_API_KEY env var."
            )

        self.base_url = OPENROUTER_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            **OPENROUTER_HEADERS,
        }

    # =========================================================================
    # EMBEDDINGS
    # =========================================================================

    def get_embeddings(
        self,
        texts: List[str],
        model: str = DEFAULT_EMBEDDING_MODEL,
    ) -> List[List[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed
            model: Embedding model to use

        Returns:
            List of embedding vectors
        """
        response = requests.post(
            f"{self.base_url}/embeddings",
            headers=self.headers,
            json={
                "model": model,
                "input": texts,
                "encoding_format": "float",
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()

        return [item["embedding"] for item in data["data"]]

    def get_embedding(
        self,
        text: str,
        model: str = DEFAULT_EMBEDDING_MODEL,
    ) -> List[float]:
        """Generate embedding for a single text.

        Args:
            text: Text to embed
            model: Embedding model to use

        Returns:
            Embedding vector
        """
        return self.get_embeddings([text], model)[0]

    # =========================================================================
    # CHAT COMPLETIONS
    # =========================================================================

    def chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str = DEFAULT_LLM_MODEL,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> str:
        """Get chat completion from OpenRouter.

        Args:
            system_prompt: System message defining assistant behavior
            user_prompt: User's message/question
            model: LLM model to use
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens in response

        Returns:
            Generated text response
        """
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=self.headers,
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    def chat_completion_with_history(
        self,
        messages: List[Dict[str, str]],
        model: str = DEFAULT_LLM_MODEL,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> str:
        """Get chat completion with conversation history.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: LLM model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response

        Returns:
            Generated text response
        """
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=self.headers,
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available models from OpenRouter."""
        response = requests.get(
            f"{self.base_url}/models",
            headers=self.headers,
            timeout=30,
        )
        response.raise_for_status()
        return response.json().get("data", [])


# =============================================================================
# CONVENIENCE FUNCTIONS (Module-level)
# =============================================================================

# Singleton instance
_client: Optional[OpenRouterClient] = None


def get_client() -> OpenRouterClient:
    """Get or create singleton OpenRouter client."""
    global _client
    if _client is None:
        _client = OpenRouterClient()
    return _client


def embed_text(text: str, model: str = DEFAULT_EMBEDDING_MODEL) -> List[float]:
    """Convenience function to embed single text."""
    return get_client().get_embedding(text, model)


def embed_texts(texts: List[str], model: str = DEFAULT_EMBEDDING_MODEL) -> List[List[float]]:
    """Convenience function to embed multiple texts."""
    return get_client().get_embeddings(texts, model)


def llm_call(
    system_prompt: str,
    user_prompt: str,
    model: str = DEFAULT_LLM_MODEL,
    temperature: float = 0.7,
) -> str:
    """Convenience function for LLM completion."""
    return get_client().chat_completion(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=model,
        temperature=temperature,
    )
