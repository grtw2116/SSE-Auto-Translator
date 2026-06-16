"""
Copyright (c) Cutleast
"""

from dataclasses import dataclass
from pathlib import Path

from pydantic import PrivateAttr

from core.string.types import String

from .translation import Translation


@dataclass(frozen=True)
class _SourceString:
    translation: Translation
    modfile: Path
    index: int


class TranslationView(Translation):
    """
    Transient translation that exposes strings from multiple translations in one editor
    tab and saves changes back to their source translations.
    """

    _sources: dict[Path, list[_SourceString]] = PrivateAttr(default_factory=dict)

    def add_string(
        self,
        translation: Translation,
        modfile: Path,
        index: int,
        string: String,
    ) -> None:
        """
        Adds a string from a source translation to this view.
        """

        self.strings.setdefault(modfile, []).append(string)
        self._sources.setdefault(modfile, []).append(
            _SourceString(translation, modfile, index)
        )

    def save(self) -> None:
        """
        Saves changed strings back to their source translations.
        """

        changed_translations: set[Translation] = set()

        for modfile, strings in self.strings.items():
            sources: list[_SourceString] = self._sources[modfile]

            for string, source in zip(strings, sources):
                source.translation.strings[source.modfile][source.index] = string
                changed_translations.add(source.translation)

        for translation in changed_translations:
            translation.save()
