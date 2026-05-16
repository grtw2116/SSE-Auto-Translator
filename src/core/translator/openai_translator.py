"""
Copyright (c) Cutleast
"""

from typing import final, override

import openai

from core.config.translator_config import TranslatorConfig
from core.utilities.game_language import GameLanguage

from .translator import Translator


@final
class OpenAITranslator(Translator):
    """
    API class for translating texts with OpenAI-compatible LLM APIs.
    """

    LANG_NAMES: dict[GameLanguage, str] = {
        GameLanguage.Chinese: "Simplified Chinese",
        GameLanguage.French: "French",
        GameLanguage.German: "German",
        GameLanguage.Italian: "Italian",
        GameLanguage.Japanese: "Japanese",
        GameLanguage.Korean: "Korean",
        GameLanguage.Polish: "Polish",
        GameLanguage.Portuguese: "Brazilian Portuguese",
        GameLanguage.Russian: "Russian",
        GameLanguage.Spanish: "Spanish",
        GameLanguage.Turkish: "Turkish",
    }

    __client: openai.OpenAI

    @override
    def __init__(self, config: TranslatorConfig) -> None:
        super().__init__(config)

        if config.api_key is None:
            raise RuntimeError("OpenAI API key is required!")

        self.__client = openai.OpenAI(
            api_key=config.api_key,
            base_url=config.openai_base_url or None,
        )

    @override
    def translate_uncached(self, text: str, dst: GameLanguage) -> str:
        lang_name = self.get_lang_name(dst)

        response = self.__client.chat.completions.create(
            model=self._config.openai_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You are a professional translator specializing in video game localization. "
                        f"Translate the following text from English to {lang_name}. "
                        "Preserve any special formatting, placeholders (like <Alias.Something> or %s), "
                        "and line breaks exactly as they appear. "
                        "Return only the translated text without any explanation or additional content."
                    ),
                },
                {"role": "user", "content": text},
            ],
            temperature=0,
        )

        result = response.choices[0].message.content
        if result is None:
            raise RuntimeError("OpenAI API returned an empty response!")

        return result.strip()

    @staticmethod
    def get_lang_name(language: GameLanguage) -> str:
        """
        Returns the natural language name for use in translation prompts.

        Args:
            language (GameLanguage): The target language.

        Returns:
            str: The language name.
        """

        return OpenAITranslator.LANG_NAMES[language]
