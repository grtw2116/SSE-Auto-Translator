"""
Copyright (c) Cutleast
"""

import textwrap
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.database.translation import Translation
from core.editor.editor import Editor
from core.file_types.plugin.string import PluginString
from core.string.string_status import StringStatus
from core.translation_provider.source import Source


def make_editor(strings: dict[Path, list]) -> Editor:
    translation = Translation(
        name="Test",
        path=Path("/fake/path"),
        source=Source.Local,
        strings_=strings,
    )
    return Editor(
        translation=translation,
        language=MagicMock(),
        database=MagicMock(),
        translator_service=MagicMock(),
    )


def make_plugin_string(
    form_id: str,
    type_: str,
    original: str,
    editor_id: str | None = None,
    translated: str | None = None,
) -> PluginString:
    return PluginString(
        form_id=form_id,
        type=type_,
        original=original,
        editor_id=editor_id,
        string=translated,
        status=StringStatus.TranslationRequired,
    )


XML_TEMPLATE = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <SSTXMLRessources>
      <Params>
        <Addon>TestMod.esp</Addon>
        <Source>english</Source>
        <Dest>japanese</Dest>
        <Version>2</Version>
      </Params>
      <Content>
        {entries}
      </Content>
    </SSTXMLRessources>
""")

XML_ENTRY = """\
    <String List="0">
      <EDID>{edid}</EDID>
      <REC>{rec}</REC>
      <Source>{source}</Source>
      <Dest>{dest}</Dest>
    </String>"""


def get_string(editor: Editor, editor_id: str | None, type_: str) -> PluginString | None:
    """Helper to retrieve a string from the editor's cache by editor_id + type."""
    for s in editor.all_strings:
        if isinstance(s, PluginString) and s.editor_id == editor_id and s.type == type_:
            return s
    return None


def get_string_by_original(editor: Editor, original: str, type_: str) -> PluginString | None:
    """Helper to retrieve a string from the editor's cache by original text + type."""
    for s in editor.all_strings:
        if isinstance(s, PluginString) and s.original == original and s.type == type_:
            return s
    return None


class TestImportXtranslatorXml:
    def test_match_by_editor_id_and_type(self, tmp_path: Path) -> None:
        """Strings are matched and translated when editor_id + type match."""
        editor = make_editor({
            Path("TestMod.esp"): [
                make_plugin_string("0x00012345", "ACTI FULL", "Burned Corpse", "ARTHLALBurnedCorpse")
            ]
        })

        xml_file = tmp_path / "test.xml"
        xml_file.write_text(
            XML_TEMPLATE.format(
                entries=XML_ENTRY.format(
                    edid="ARTHLALBurnedCorpse",
                    rec="ACTI:FULL",
                    source="Burned Corpse",
                    dest="焼けた死体",
                )
            ),
            encoding="utf-8",
        )

        matched = editor.import_xtranslator_xml(xml_file)

        s = get_string(editor, "ARTHLALBurnedCorpse", "ACTI FULL")
        assert matched == 1
        assert s is not None
        assert s.string == "焼けた死体"
        assert s.status == StringStatus.TranslationComplete

    def test_fallback_to_original_text_match(self, tmp_path: Path) -> None:
        """Falls back to original-text match when editor_id is a FormID placeholder."""
        editor = make_editor({
            Path("TestMod.esp"): [
                make_plugin_string("0x00000000", "TES4 CNAM", "Arthmoor", editor_id=None)
            ]
        })

        xml_file = tmp_path / "test.xml"
        xml_file.write_text(
            XML_TEMPLATE.format(
                entries=XML_ENTRY.format(
                    edid="[00000000]",
                    rec="TES4:CNAM",
                    source="Arthmoor",
                    dest="アースムア",
                )
            ),
            encoding="utf-8",
        )

        matched = editor.import_xtranslator_xml(xml_file)

        s = get_string_by_original(editor, "Arthmoor", "TES4 CNAM")
        assert matched == 1
        assert s is not None
        assert s.string == "アースムア"
        assert s.status == StringStatus.TranslationComplete

    def test_no_match_returns_zero(self, tmp_path: Path) -> None:
        """Returns 0 when no strings match the XML entries."""
        editor = make_editor({
            Path("TestMod.esp"): [
                make_plugin_string("0x00099999", "WEAP FULL", "Iron Sword", "WeapIronSword")
            ]
        })

        xml_file = tmp_path / "test.xml"
        xml_file.write_text(
            XML_TEMPLATE.format(
                entries=XML_ENTRY.format(
                    edid="SomeOtherEditorID",
                    rec="ARMO:FULL",
                    source="Iron Armor",
                    dest="鉄の鎧",
                )
            ),
            encoding="utf-8",
        )

        matched = editor.import_xtranslator_xml(xml_file)

        s = get_string(editor, "WeapIronSword", "WEAP FULL")
        assert matched == 0
        assert s is not None
        assert s.string is None
        assert s.status == StringStatus.TranslationRequired

    def test_empty_dest_is_skipped(self, tmp_path: Path) -> None:
        """Entries with empty <Dest> are skipped."""
        editor = make_editor({
            Path("TestMod.esp"): [
                make_plugin_string("0x00012345", "ACTI FULL", "Door", "ARTHLALJailDoor")
            ]
        })

        xml_file = tmp_path / "test.xml"
        xml_file.write_text(
            XML_TEMPLATE.format(
                entries=XML_ENTRY.format(
                    edid="ARTHLALJailDoor",
                    rec="ACTI:FULL",
                    source="Door",
                    dest="",
                )
            ),
            encoding="utf-8",
        )

        matched = editor.import_xtranslator_xml(xml_file)

        s = get_string(editor, "ARTHLALJailDoor", "ACTI FULL")
        assert matched == 0
        assert s is not None
        assert s.string is None

    def test_multiple_entries_applied(self, tmp_path: Path) -> None:
        """Multiple XML entries are all applied."""
        editor = make_editor({
            Path("TestMod.esp"): [
                make_plugin_string("0x00000001", "ACTI FULL", "Door", "EdDoor"),
                make_plugin_string("0x00000002", "BOOK FULL", "Journal", "EdJournal"),
            ]
        })

        entries = "\n".join([
            XML_ENTRY.format(edid="EdDoor", rec="ACTI:FULL", source="Door", dest="扉"),
            XML_ENTRY.format(edid="EdJournal", rec="BOOK:FULL", source="Journal", dest="日記"),
        ])
        xml_file = tmp_path / "test.xml"
        xml_file.write_text(XML_TEMPLATE.format(entries=entries), encoding="utf-8")

        matched = editor.import_xtranslator_xml(xml_file)

        s1 = get_string(editor, "EdDoor", "ACTI FULL")
        s2 = get_string(editor, "EdJournal", "BOOK FULL")
        assert matched == 2
        assert s1 is not None and s1.string == "扉"
        assert s2 is not None and s2.string == "日記"

    def test_real_xtranslator_xml_file(self) -> None:
        """Smoke-test with the actual xTranslator sample file."""
        sample = Path(
            r"C:\Users\ryg-wtnb\Downloads\13631\ASLAL"
            r"\alternate start - live another life_english_japanese.xml"
        )
        if not sample.exists():
            pytest.skip("Sample XML file not available")

        editor = make_editor({
            Path("alternate start - live another life.esp"): [
                make_plugin_string("0x00000001", "ACTI FULL", "Burned Corpse", "ARTHLALBurnedCorpse"),
                make_plugin_string("0x00000002", "ACTI FULL", "Door", "ARTHLALJailDoorTriggerActivator"),
                make_plugin_string("0x00000003", "ACTI FULL", "Bed", "ARTHLALFakeBed"),
            ]
        })

        matched = editor.import_xtranslator_xml(sample)

        assert matched >= 3
        assert get_string(editor, "ARTHLALBurnedCorpse", "ACTI FULL") is not None
        assert get_string(editor, "ARTHLALBurnedCorpse", "ACTI FULL").string == "焼けた死体"  # type: ignore[union-attr]
        assert get_string(editor, "ARTHLALJailDoorTriggerActivator", "ACTI FULL").string == "扉"  # type: ignore[union-attr]
        assert get_string(editor, "ARTHLALFakeBed", "ACTI FULL").string == "ベッド"  # type: ignore[union-attr]
