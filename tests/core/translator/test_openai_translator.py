"""
Copyright (c) Cutleast
"""

import json
from typing import Optional
from unittest.mock import MagicMock, call, patch

import pytest

from core.config.translator_config import TranslatorConfig
from core.translator.openai_translator import OpenAITranslator
from core.utilities.game_language import GameLanguage

DST = GameLanguage.German


def make_config(
    use_batch: bool = True,
    batch_size: int = 50,
) -> TranslatorConfig:
    config = TranslatorConfig()
    config.api_key = "test-key"
    config.openai_use_batch = use_batch
    config.openai_batch_size = batch_size
    return config


def make_translator(
    config: Optional[TranslatorConfig] = None,
) -> OpenAITranslator:
    if config is None:
        config = make_config()
    with patch("openai.OpenAI"):
        t = OpenAITranslator(config)
    t._OpenAITranslator__client = MagicMock()  # type: ignore[attr-defined]
    # Disable persistent cache for all tests
    t._get_from_cache = MagicMock(return_value=None)  # type: ignore[method-assign]
    t._add_to_cache = MagicMock()  # type: ignore[method-assign]
    return t


def api_response(translations: dict[str, str]) -> MagicMock:
    """Builds a mock chat completion response returning the given index->translation map."""
    resp = MagicMock()
    resp.choices[0].message.content = json.dumps(translations)
    return resp


class TestMassTranslate:
    def test_empty_input_returns_empty_dict(self) -> None:
        t = make_translator()
        assert t.mass_translate([], DST) == {}

    def test_batch_disabled_falls_back_to_sequential(self) -> None:
        t = make_translator(make_config(use_batch=False))
        t._OpenAITranslator__client.chat.completions.create.return_value = MagicMock(  # type: ignore[attr-defined]
            choices=[MagicMock(message=MagicMock(content="Hallo"))]
        )
        result = t.mass_translate(["Hello"], DST)
        assert result == {"Hello": "Hallo"}
        # base-class path calls translate() which calls translate_uncached(), not batch
        create = t._OpenAITranslator__client.chat.completions.create  # type: ignore[attr-defined]
        msg = create.call_args[1]["messages"][1]["content"]
        assert msg == "Hello"  # single-string prompt, not a JSON object

    def test_basic_batch_single_api_call(self) -> None:
        t = make_translator()
        texts = ["Hello", "World", "Goodbye"]
        t._OpenAITranslator__client.chat.completions.create.return_value = api_response(  # type: ignore[attr-defined]
            {"0": "Hallo", "1": "Welt", "2": "Auf Wiedersehen"}
        )
        result = t.mass_translate(texts, DST)
        assert result == {"Hello": "Hallo", "World": "Welt", "Goodbye": "Auf Wiedersehen"}
        t._OpenAITranslator__client.chat.completions.create.assert_called_once()  # type: ignore[attr-defined]

    def test_batch_splitting_calls_api_once_per_chunk(self) -> None:
        t = make_translator(make_config(batch_size=2))
        texts = ["A", "B", "C"]
        t._OpenAITranslator__client.chat.completions.create.side_effect = [  # type: ignore[attr-defined]
            api_response({"0": "a", "1": "b"}),
            api_response({"0": "c"}),
        ]
        result = t.mass_translate(texts, DST)
        assert result == {"A": "a", "B": "b", "C": "c"}
        assert t._OpenAITranslator__client.chat.completions.create.call_count == 2  # type: ignore[attr-defined]

    def test_all_cached_skips_api(self) -> None:
        t = make_translator()
        t._get_from_cache = MagicMock(side_effect=lambda text, dst: f"[{text}]")  # type: ignore[method-assign]
        result = t.mass_translate(["Hello", "World"], DST)
        assert result == {"Hello": "[Hello]", "World": "[World]"}
        t._OpenAITranslator__client.chat.completions.create.assert_not_called()  # type: ignore[attr-defined]

    def test_partial_cache_sends_only_uncached(self) -> None:
        t = make_translator()
        t._get_from_cache = MagicMock(  # type: ignore[method-assign]
            side_effect=lambda text, dst: "Hallo" if text == "Hello" else None
        )
        t._OpenAITranslator__client.chat.completions.create.return_value = api_response(  # type: ignore[attr-defined]
            {"0": "Auf Wiedersehen"}
        )
        result = t.mass_translate(["Hello", "Goodbye"], DST)
        assert result == {"Hello": "Hallo", "Goodbye": "Auf Wiedersehen"}
        # API received only the uncached text
        user_msg = t._OpenAITranslator__client.chat.completions.create.call_args[1][  # type: ignore[attr-defined]
            "messages"
        ][1]["content"]
        assert json.loads(user_msg) == {"0": "Goodbye"}

    def test_result_is_cached_after_api_call(self) -> None:
        t = make_translator()
        t._OpenAITranslator__client.chat.completions.create.return_value = api_response(  # type: ignore[attr-defined]
            {"0": "Hallo"}
        )
        t.mass_translate(["Hello"], DST)
        t._add_to_cache.assert_called_once_with("Hello", "Hallo", DST)  # type: ignore[attr-defined]


class TestFallback:
    def test_invalid_json_falls_back_to_single_translate(self) -> None:
        t = make_translator()
        t._OpenAITranslator__client.chat.completions.create.side_effect = [  # type: ignore[attr-defined]
            MagicMock(choices=[MagicMock(message=MagicMock(content="not valid json"))]),
            MagicMock(choices=[MagicMock(message=MagicMock(content="Hallo"))]),
        ]
        result = t.mass_translate(["Hello"], DST)
        assert result == {"Hello": "Hallo"}
        assert t._OpenAITranslator__client.chat.completions.create.call_count == 2  # type: ignore[attr-defined]

    def test_missing_index_in_response_falls_back_to_single(self) -> None:
        t = make_translator()
        t._OpenAITranslator__client.chat.completions.create.side_effect = [
            api_response({"0": "Hallo"}),           # batch: index 1 is missing
            MagicMock(choices=[MagicMock(message=MagicMock(content="Welt"))]),  # fallback
        ]
        result = t.mass_translate(["Hello", "World"], DST)
        assert result == {"Hello": "Hallo", "World": "Welt"}

    def test_markdown_fence_stripped(self) -> None:
        t = make_translator()
        fenced = '```json\n{"0": "Hallo"}\n```'
        t._OpenAITranslator__client.chat.completions.create.return_value = MagicMock(  # type: ignore[attr-defined]
            choices=[MagicMock(message=MagicMock(content=fenced))]
        )
        result = t.mass_translate(["Hello"], DST)
        assert result == {"Hello": "Hallo"}

    def test_whitespace_stripped_from_translations(self) -> None:
        t = make_translator()
        t._OpenAITranslator__client.chat.completions.create.return_value = api_response(  # type: ignore[attr-defined]
            {"0": "  Hallo  "}
        )
        result = t.mass_translate(["Hello"], DST)
        assert result == {"Hello": "Hallo"}
