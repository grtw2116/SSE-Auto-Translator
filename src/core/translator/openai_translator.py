"""
Copyright (c) Cutleast
"""

import json
from typing import Optional, final, override

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

    @override
    def mass_translate(self, texts: list[str], dst: GameLanguage) -> dict[str, str]:
        if not texts:
            return {}

        if not self._config.openai_use_batch:
            return super().mass_translate(texts, dst)

        batch_size = max(1, self._config.openai_batch_size)
        result: dict[str, str] = {}

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            result.update(self.__translate_batch(batch, dst))

        return result

    def __translate_batch(self, texts: list[str], dst: GameLanguage) -> dict[str, str]:
        """
        Translates a batch of texts in a single API call.
        Checks and populates the cache for each entry.
        Falls back to per-string translation on parse errors.
        """

        batch_result: dict[str, str] = {}
        uncached: list[str] = []

        for text in texts:
            cached = self._get_from_cache(text, dst)
            if cached is not None:
                batch_result[text] = cached
            else:
                uncached.append(text)

        if not uncached:
            return batch_result

        lang_name = self.get_lang_name(dst)
        indexed = {str(i): text for i, text in enumerate(uncached)}
        input_json = json.dumps(indexed, ensure_ascii=False)

        response = self.__client.chat.completions.create(
            model=self._config.openai_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You are a professional translator specializing in video game localization. "
                        f"Translate the following texts from English to {lang_name}. "
                        "Preserve any special formatting, placeholders (like <Alias.Something> or %s), "
                        "and line breaks exactly as they appear. "
                        "The input is a JSON object where each key is an integer index and each value is a text to translate. "
                        "Return ONLY a valid JSON object with the same integer keys and the translated texts as values. "
                        "Do not include any explanation or additional content outside the JSON."
                    ),
                },
                {"role": "user", "content": input_json},
            ],
            temperature=0,
        )

        content = response.choices[0].message.content
        if content is None:
            raise RuntimeError("OpenAI API returned an empty response!")

        translations: Optional[dict[str, str]] = self.__parse_json_response(
            content.strip()
        )

        for i, text in enumerate(uncached):
            translation: Optional[str] = (
                translations.get(str(i)) if translations is not None else None
            )
            if translation is None:
                self.log.warning(
                    f"Batch translation missing index {i}, falling back to single call."
                )
                batch_result[text] = self.translate(text, dst)
            else:
                translation = translation.strip()
                self._add_to_cache(text, translation, dst)
                batch_result[text] = translation

        return batch_result

    @staticmethod
    def __parse_json_response(content: str) -> Optional[dict[str, str]]:
        """Parses JSON from the model response, stripping markdown fences if present."""

        if content.startswith("```"):
            lines = content.splitlines()
            content = "\n".join(lines[1:-1])

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return None

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
