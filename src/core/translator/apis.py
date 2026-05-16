"""
Copyright (c) Cutleast
"""

from enum import Enum


class TranslatorApi(Enum):
    """Enum for available translator APIs."""

    Google = "Google Translator"
    """Google translator API (free)."""

    DeepL = "DeepL"
    """DeepL translator API (requires API key)."""

    OpenAI = "OpenAI-compatible"
    """OpenAI-compatible LLM API (requires API key and model configuration)."""
