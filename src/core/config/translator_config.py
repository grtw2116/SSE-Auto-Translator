"""
Copyright (c) Cutleast
"""

from typing import Annotated, Optional, override

from cutleast_core_lib.core.config.base_config import BaseConfig

from core.translator.apis import TranslatorApi


class TranslatorConfig(BaseConfig):
    """
    Class for translator settings.
    """

    translator: TranslatorApi = TranslatorApi.Google
    """The translator API to use for machine translations."""

    api_key: Annotated[Optional[str], BaseConfig.PropertyMarker.ExcludeFromLogging] = (
        None
    )
    """The API key for the translator API."""

    openai_base_url: str = ""
    """The base URL for the OpenAI-compatible API (empty = use OpenAI default)."""

    openai_model: str = "gpt-4o-mini"
    """The model name to use for the OpenAI-compatible API."""

    openai_use_batch: bool = True
    """Whether to send multiple strings in a single API call when translating with OpenAI."""

    openai_batch_size: int = 50
    """Number of strings to include per batch API call when using OpenAI."""

    show_confirmation_dialogs: bool = True
    """Whether to ask for confirmation before starting a machine translation."""

    @override
    @staticmethod
    def get_config_name() -> str:
        return "translator/config.json"
