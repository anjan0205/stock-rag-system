"""LLM module for equity research (Google Gemini Flash)."""

from .client import GeminiClient
from .generator import RAGGenerator

__all__ = ["GeminiClient", "RAGGenerator"]
