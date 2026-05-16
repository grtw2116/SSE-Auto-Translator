"""
Copyright (c) Cutleast
"""

import logging
import re
import xml.etree.ElementTree as ET
from copy import copy, deepcopy
from pathlib import Path
from typing import Optional

import jstyleson as json
from cutleast_core_lib.ui.widgets.loading_dialog import LoadingDialog
from PySide6.QtCore import QObject, Signal

from core.database.database import TranslationDatabase
from core.database.translation import Translation
from core.file_types.plugin.string import PluginString
from core.string.string_status import StringStatus
from core.string.types import String, StringList
from core.translator.service import TranslatorService
from core.translator.translator import Translator
from core.utilities.game_language import GameLanguage


class Editor(QObject):
    """
    Class for editing a translation.
    """

    log: logging.Logger = logging.getLogger("Editor")

    language: GameLanguage
    database: TranslationDatabase
    translator_service: TranslatorService

    __translation: Translation
    __strings_cache: dict[Path, StringList]
    """
    Stores a deep copy of the strings in the translation.
    """

    update_signal = Signal()
    """
    This signal gets emitted when any of the strings in the translation change.
    """

    __changes_pending: bool = False

    def __init__(
        self,
        translation: Translation,
        language: GameLanguage,
        database: TranslationDatabase,
        translator_service: TranslatorService,
    ) -> None:
        super().__init__()

        self.__translation = translation

        self.language = language
        self.database = database
        self.translator_service = translator_service

        # Make a deep copy to prevent immediately modifying the translation
        self.__strings_cache = deepcopy(self.__translation.strings)

        self.update_signal.connect(self.__on_change)

    def save(self) -> None:
        """
        Saves changes to the translation.
        """

        self.__translation.strings = self.__strings_cache
        self.__translation.save()

        self.log.info(f"Saved translation {self.__translation.name!r}.")
        self.__changes_pending = False

    def __on_change(self, changes_pending: bool = True) -> None:
        self.__changes_pending = changes_pending

    @property
    def changes_pending(self) -> bool:
        """
        Whether there are unsaved changes.
        """

        return self.__changes_pending

    @property
    def strings(self) -> dict[Path, StringList]:
        """
        Map of plugin names to their list of strings.
        Returns their current editing state.
        """

        return copy(self.__strings_cache)

    @property
    def all_strings(self) -> StringList:
        """
        List of all strings.
        """

        return [
            string for strings in self.__strings_cache.values() for string in strings
        ]

    def set_status(self, strings: StringList, status: StringStatus) -> None:
        """
        Sets the status of a list of strings.

        Args:
            strings (StringList): List of strings
            status (Status): The status to set
        """

        for string in strings:
            string.status = status

        self.update_signal.emit()
        self.log.info(f"Updated status for {len(strings)} string(s).")

    def update_string(
        self,
        string: String,
        translation: Optional[str] = None,
        status: Optional[StringStatus] = None,
    ) -> None:
        """
        Updates a string.

        Args:
            string (String): The string
            translation (Optional[str], optional): Translation string to set. Defaults to None.
            status (Optional[Status], optional): Status to set. Defaults to None.
        """

        if translation is not None:
            string.string = translation

        if status is not None:
            string.status = status

            if status == StringStatus.NoTranslationRequired:
                string.string = string.original

        self.update_signal.emit()

    def translate_with_api(
        self, strings: StringList, ldialog: Optional[LoadingDialog]
    ) -> None:
        """
        Translates a list of strings with a translator API.

        Args:
            strings (StringList): List of strings
            ldialog (Optional[LoadingDialog]): Optional loading dialog, defaults to None
        """

        if ldialog is not None:
            ldialog.updateProgress(text1=self.tr("Translating with API..."))

        self.log.info(f"Translating {len(strings)} string(s) with API...")

        translator: Translator = self.translator_service.get_translator()

        self.log.info(f"Used translator API: {translator.__class__.__name__}")

        texts: list[str] = list(
            dict.fromkeys(s.original for s in strings)
        )
        result: dict[str, str] = translator.mass_translate(texts, self.language)

        for string in strings:
            string.string = result[string.original]
            string.status = StringStatus.TranslationIncomplete

        self.update_signal.emit()
        self.log.info("API translation complete.")

    def apply_regex(
        self, strings: StringList, replace_text: str, pattern: re.Pattern
    ) -> int:
        """
        Applies a regex to a list of strings.

        Args:
            strings (StringList): List of strings
            replace_text (str): Replacer text
            pattern (re.Pattern): Regex pattern

        Returns:
            int: Number of strings modified
        """

        self.log.info(f"Applying regex to {len(strings)} string(s)...")

        modified_strings: int = 0
        for string in strings:
            src: str = string.string if string.string is not None else string.original
            res: str = pattern.sub(replace_text, src)
            string.string = res

            if src != string.string:
                string.status = StringStatus.TranslationIncomplete
                modified_strings += 1

        self.update_signal.emit()
        self.log.info("Regex applied.")

        return modified_strings

    def apply_database(self, strings: StringList) -> int:
        """
        Applies database to a list of strings.

        Args:
            strings (StringList): List of strings

        Returns:
            int: Number of strings modified
        """

        self.log.info(f"Applying database to {len(strings)} string(s)...")

        database_originals: dict[str, String] = {
            string.original: string for string in self.database.strings
        }
        database_strings: dict[str, String] = {
            string.id: string for string in self.database.strings
        }

        modified_strings: int = 0
        for string in strings:
            if string.id in database_strings:
                string.string = database_strings[string.id].string
                string.status = StringStatus.TranslationComplete
                modified_strings += 1

            elif string.original in database_originals:
                string.string = database_originals[string.original].string
                string.status = StringStatus.TranslationIncomplete
                modified_strings += 1

        self.update_signal.emit()
        self.log.info("Database applied.")

        return modified_strings

    def apply_to_matching_strings(self, original: str, translation: str) -> int:
        """
        Applies translation to strings that are matching.

        Args:
            original (str): The original string
            translation (str): The translation

        Returns:
            int: Number of strings modified
        """

        modified_strings: int = 0
        for string in self.all_strings:
            if (
                string.original == original
                and string.status != StringStatus.TranslationComplete
            ):
                string.string = translation
                string.status = StringStatus.TranslationIncomplete
                modified_strings += 1

        self.update_signal.emit()
        self.log.info(f"Applied translation to {modified_strings} string(s).")

        return modified_strings

    def reset_strings(self, strings: StringList) -> None:
        """
        Resets the translation and the status of a list of strings.

        Args:
            strings (StringList): List of strings
        """

        self.log.info(f"Resetting {len(strings)} string(s)...")

        for string in strings:
            string.string = None
            string.status = StringStatus.TranslationRequired

        self.update_signal.emit()
        self.log.info("Strings reset.")

    def import_legacy_dsd_translation(self, dsd_file: Path) -> int:
        """
        Imports a legacy (pre-v1.1) DSD translation by overwriting the current translation.

        Args:
            dsd_file (Path): Path to DSD file

        Returns:
            int: Number of strings modified
        """

        self.log.info(f"Importing legacy translation from '{dsd_file}'...")

        with dsd_file.open(encoding="utf8") as file:
            legacy_strings: list[dict] = json.load(file)

        self.log.debug(f"Found {len(legacy_strings)} string(s) in legacy translation.")

        translation_strings: dict[str, StringList] = {}
        for string in self.all_strings:
            translation_strings.setdefault(string.original, []).append(string)

        strings_modified: int = 0
        for legacy_string in legacy_strings:
            original = legacy_string.get("original")
            translated = legacy_string.get("string")

            if original is None or translated is None:
                continue

            matching_strings: Optional[StringList] = translation_strings.get(original)

            if matching_strings is None:
                continue

            for matching_string in matching_strings:
                matching_string.string = translated

                if (
                    isinstance(matching_string, PluginString)
                    and legacy_string.get("type") == matching_string.type
                    and legacy_string.get("editor_id") == matching_string.editor_id
                    and legacy_string.get("index") == matching_string.index
                ):
                    legacy_status = StringStatus.get(legacy_string.get("status") or "")

                    if legacy_status is not None:
                        matching_string.status = legacy_status
                    else:
                        matching_string.status = StringStatus.TranslationComplete

            strings_modified += 1

        self.update_signal.emit()
        self.log.info("Legacy translation imported.")

        return strings_modified

    def import_xtranslator_xml(self, xml_file: Path) -> int:
        """
        Imports an xTranslator XML translation (SSTXMLRessources format).

        Args:
            xml_file (Path): Path to the xTranslator XML file

        Returns:
            int: Number of XML entries matched and applied
        """

        self.log.info(f"Importing xTranslator XML from '{xml_file}'...")

        tree = ET.parse(xml_file)
        root = tree.getroot()

        content = root.find("Content")
        if content is None:
            self.log.warning("No <Content> element found in XML file.")
            return 0

        # Build lookup tables from current strings
        by_edid_type: dict[tuple[str, str], StringList] = {}
        by_original_type: dict[tuple[str, str], StringList] = {}
        for string in self.all_strings:
            if isinstance(string, PluginString) and string.editor_id:
                key = (string.editor_id.lower(), string.type)
                by_edid_type.setdefault(key, []).append(string)
            rec_type = string.type if isinstance(string, PluginString) else ""
            by_original_type.setdefault((string.original, rec_type), []).append(string)

        entries_matched: int = 0
        for str_elem in content.findall("String"):
            edid_elem = str_elem.find("EDID")
            rec_elem = str_elem.find("REC")
            source_elem = str_elem.find("Source")
            dest_elem = str_elem.find("Dest")

            if source_elem is None or dest_elem is None:
                continue

            original: str = source_elem.text or ""
            translated: str = dest_elem.text or ""

            if not translated:
                continue

            # Convert "RECORD:SUBRECORD" -> "RECORD SUBRECORD"
            rec_type: str = ""
            if rec_elem is not None and rec_elem.text:
                rec_type = rec_elem.text.replace(":", " ", 1)

            edid: str = (edid_elem.text or "").strip() if edid_elem is not None else ""
            is_form_id_placeholder = edid.startswith("[") and edid.endswith("]")

            matched: Optional[StringList] = None

            if not is_form_id_placeholder and edid:
                matched = by_edid_type.get((edid.lower(), rec_type))

            if matched is None:
                matched = by_original_type.get((original, rec_type))

            if matched is None:
                continue

            for string in matched:
                string.string = translated
                string.status = StringStatus.TranslationComplete

            entries_matched += 1

        self.update_signal.emit()
        self.log.info(f"xTranslator XML imported: {entries_matched} entries matched.")

        return entries_matched
