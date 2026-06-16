"""
Copyright (c) Cutleast
"""

from copy import deepcopy
from pathlib import Path

from core.database.database import TranslationDatabase
from core.database.database_service import DatabaseService
from core.database.translation import Translation
from core.file_types.plugin.string import PluginString
from core.mod_file.mod_file import ModFile
from core.mod_file.translation_status import TranslationStatus
from core.mod_instance.mod import Mod
from core.string.string_extractor import StringExtractor
from core.string.string_status import StringStatus
from core.string.types import StringList
from core.user_data.user_data import UserData
from core.utilities.game_language import GameLanguage

from ..core_test import CoreTest


class TestDatabaseService(CoreTest):
    """
    Tests `core.database.database_service.DatabaseService`.
    """

    def test_load_database(self, res_path: Path, user_data_path: Path) -> None:
        """
        Tests `DatabaseService.load_database()`.
        """

        # given
        appdb_path: Path = res_path / "app" / "database"
        userdb_path: Path = user_data_path / "user" / "database"
        language: GameLanguage = GameLanguage.German

        # when
        database: TranslationDatabase = DatabaseService.load_database(
            appdb_path, userdb_path, language
        )

        # then
        assert len(database.user_translations) == 2
        assert sorted(map(lambda t: t.name, database.user_translations)) == [
            "Obsidian Weathers and Seasons - German",
            "Wet and Cold SE - German",
        ]

    def test_create_translation_for_mod(self, user_data: UserData) -> None:
        """
        Tests `DatabaseService.create_translation_for_mod()`.
        """

        # given
        mod: Mod = self.get_mod_by_name("RS Children Overhaul", user_data.modinstance)
        main_esp: ModFile = self.get_modfile_from_mod(mod, "RSChildren.esp")
        main_esp.status = TranslationStatus.TranslationAvailableInDatabase
        database: TranslationDatabase = user_data.database

        # when
        created_translation: Translation = DatabaseService.create_translation_for_mod(
            mod, database, add_and_save=False
        )

        # then
        assert len(created_translation.strings) == 3
        assert sorted(created_translation.strings.keys()) == [
            Path("RSChildren Patch - BS Bruma.esp"),
            Path("RSChildren.esp"),
            Path("RSkyrimChildren.esm"),
        ]

        # when
        created_translation = DatabaseService.create_translation_for_mod(
            mod, database, only_complete_coverage=True, add_and_save=False
        )

        # then
        assert len(created_translation.strings) == 1
        assert sorted(created_translation.strings.keys()) == [Path("RSChildren.esp")]

    def test_create_translation_for_mod_file(self, user_data: UserData) -> None:
        """
        Tests `DatabaseService.create_translation_for_mod()`.
        """

        # given
        modfile: ModFile = self.get_modfile_from_mod_name(
            "RS Children Overhaul", "RSChildren.esp", user_data.modinstance
        )
        database: TranslationDatabase = user_data.database

        # when
        created_translation: Translation = (
            DatabaseService.create_translation_for_modfile(
                modfile, database, add_and_save=False
            )
        )

        # then
        assert created_translation.name == "RSChildren.esp - German"
        assert list(created_translation.strings.keys()) == [Path("RSChildren.esp")]

    def test_create_unfinished_translation_view(self, user_data: UserData) -> None:
        """
        Tests `DatabaseService.create_unfinished_translation_view()`.
        """

        # given
        database: TranslationDatabase = user_data.database
        first_translation: Translation = database.user_translations[0]
        second_translation: Translation = database.user_translations[1]
        first_modfile: Path = next(iter(first_translation.strings))
        second_modfile: Path = next(iter(second_translation.strings))

        first_string = first_translation.strings[first_modfile][0]
        second_string = second_translation.strings[second_modfile][0]
        complete_string = first_translation.strings[first_modfile][1]

        first_string.status = StringStatus.TranslationRequired
        first_string.string = None
        second_string.status = StringStatus.TranslationIncomplete
        second_string.string = "Draft translation"
        complete_string.status = StringStatus.TranslationComplete

        # when
        view: Translation = DatabaseService.create_unfinished_translation_view(database)

        # then
        view_strings = [
            string for strings in view.strings.values() for string in strings
        ]
        assert first_string in view_strings
        assert second_string in view_strings
        assert complete_string not in view_strings

        # when
        view_string_location = next(
            (modfile, index)
            for modfile, strings in view.strings.items()
            for index, string in enumerate(strings)
            if string is first_string
        )
        view.strings = deepcopy(view.strings)
        view_modfile, view_index = view_string_location
        view_first_string = view.strings[view_modfile][view_index]
        view_first_string.string = "Finished translation"
        view_first_string.status = StringStatus.TranslationComplete
        view.save()

        # then
        assert first_translation.strings[first_modfile][0].string == (
            "Finished translation"
        )
        assert first_translation.strings[first_modfile][0].status == (
            StringStatus.TranslationComplete
        )

    def test_create_unfinished_translation_view_with_missing_translation(
        self, user_data: UserData
    ) -> None:
        """
        Tests `DatabaseService.create_unfinished_translation_view()` with a mod file
        that has no database translation yet.
        """

        # given
        database: TranslationDatabase = user_data.database
        mod: Mod = self.get_mod_by_name("RS Children Overhaul", user_data.modinstance)
        modfile: ModFile = self.get_modfile_from_mod(
            mod, "RSChildren Patch - BS Bruma.esp"
        )
        modfile.status = TranslationStatus.RequiresTranslation

        assert database.get_translation_by_modfile_path(modfile.path) is None

        # when
        view: Translation = DatabaseService.create_unfinished_translation_view(
            database,
            user_data.modinstance,
        )

        # then
        created_translation = database.get_translation_by_modfile_path(modfile.path)
        assert created_translation is not None
        assert modfile.path in view.strings
        assert modfile.path in created_translation.strings
        assert all(
            string.status == StringStatus.TranslationRequired
            for string in created_translation.strings[modfile.path]
        )

    def test_create_translation_from_mod(self, user_data: UserData) -> None:
        """
        Tests `DatabaseService.create_translation_from_mod()`.
        """

        # given
        original_mod: Mod = self.get_mod_by_name(
            "Wet and Cold SE", user_data.modinstance
        )
        translated_mod: Mod = self.get_mod_by_name(
            "Wet and Cold SE - German", user_data.modinstance
        )
        database: TranslationDatabase = user_data.database

        # when
        translation_strings: dict[Path, StringList] = (
            StringExtractor.map_strings_from_mods(translated_mod, original_mod)
        )
        created_translation: Translation = DatabaseService.create_translation_from_mod(
            translated_mod,
            original_mod,
            translation_strings,
            database,
            add_and_save=False,
        )

        # then
        assert len(created_translation.strings) == 2
        assert sorted(created_translation.strings.keys()) == [
            Path("interface/translations/wetandcold_german.txt"),
            Path("WetandCold.esp"),
        ]

        strings: StringList = created_translation.strings[Path("WetandCold.esp")]
        string_hashes: list[int] = list(map(CoreTest.calc_unique_string_hash, strings))

        expected_strings: StringList = [
            PluginString(
                form_id="05062F4E|WetandCold.esp",
                type="ENCH FULL",
                original="Fortify Carry Weight",
                string="Tragfähigkeit verstärken",
                editor_id="_WetEnchArmorFortifyCarry03",
                status=StringStatus.TranslationComplete,
            )
        ]

        assert len(strings) == 204
        for string in expected_strings:
            assert CoreTest.calc_unique_string_hash(string) in string_hashes, (
                f"<{string}> not in actual strings!"
            )
