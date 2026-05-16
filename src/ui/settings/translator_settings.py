"""
Copyright (c) Cutleast
"""

from typing import override

from cutleast_core_lib.ui.settings.settings_page import SettingsPage
from cutleast_core_lib.ui.widgets.enum_radiobutton_widget import EnumRadiobuttonsWidget
from cutleast_core_lib.ui.widgets.key_edit import KeyLineEdit
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QFormLayout, QLabel, QLineEdit, QWidget

from core.config.translator_config import TranslatorConfig
from core.translator.apis import TranslatorApi

APIS_REQUIRING_KEY = {TranslatorApi.DeepL, TranslatorApi.OpenAI}
"""Translator APIs that require an API key."""


class TranslatorSettings(SettingsPage[TranslatorConfig]):
    """
    Widget for translator API settings.
    """

    __flayout: QFormLayout

    __api_selector: EnumRadiobuttonsWidget[TranslatorApi]
    __api_key_entry: KeyLineEdit
    __api_key_label: QLabel

    __openai_base_url_label: QLabel
    __openai_base_url_entry: QLineEdit
    __openai_model_label: QLabel
    __openai_model_entry: QLineEdit

    __show_confirmations_box: QCheckBox

    @override
    def _init_ui(self) -> None:
        scroll_widget = QWidget()
        scroll_widget.setObjectName("transparent")
        self.setWidget(scroll_widget)

        self.__flayout = QFormLayout()
        scroll_widget.setLayout(self.__flayout)

        self.__init_api_settings()
        self.__init_confirmation_box()

    def __init_api_settings(self) -> None:
        self.__api_selector = EnumRadiobuttonsWidget(
            TranslatorApi,
            self._initial_config.translator,
            orientation=Qt.Orientation.Horizontal,
        )
        self.__api_selector.currentValueChanged.connect(
            lambda _: self.changed_signal.emit()
        )
        self.__flayout.addRow(self.tr("Translator API"), self.__api_selector)

        requires_key = self._initial_config.translator in APIS_REQUIRING_KEY

        self.__api_key_label = QLabel(self.tr("Translator API key"))
        self.__api_key_entry = KeyLineEdit()
        if self._initial_config.api_key:
            self.__api_key_entry.setText(self._initial_config.api_key)
        self.__api_key_label.setEnabled(requires_key)
        self.__api_key_entry.setEnabled(requires_key)
        self.__api_key_entry.textChanged.connect(lambda _: self.changed_signal.emit())
        self.__flayout.addRow(self.__api_key_label, self.__api_key_entry)

        is_openai = self._initial_config.translator == TranslatorApi.OpenAI

        self.__openai_base_url_label = QLabel(self.tr("API base URL"))
        self.__openai_base_url_entry = QLineEdit()
        self.__openai_base_url_entry.setPlaceholderText("https://api.openai.com/v1")
        if self._initial_config.openai_base_url:
            self.__openai_base_url_entry.setText(self._initial_config.openai_base_url)
        self.__openai_base_url_label.setEnabled(is_openai)
        self.__openai_base_url_entry.setEnabled(is_openai)
        self.__openai_base_url_entry.textChanged.connect(
            lambda _: self.changed_signal.emit()
        )
        self.__flayout.addRow(self.__openai_base_url_label, self.__openai_base_url_entry)

        self.__openai_model_label = QLabel(self.tr("Model"))
        self.__openai_model_entry = QLineEdit()
        self.__openai_model_entry.setText(self._initial_config.openai_model)
        self.__openai_model_label.setEnabled(is_openai)
        self.__openai_model_entry.setEnabled(is_openai)
        self.__openai_model_entry.textChanged.connect(
            lambda _: self.changed_signal.emit()
        )
        self.__flayout.addRow(self.__openai_model_label, self.__openai_model_entry)

        self.__api_selector.currentValueChanged.connect(self.__on_api_changed)

    def __on_api_changed(self, translator_api: TranslatorApi) -> None:
        requires_key = translator_api in APIS_REQUIRING_KEY
        self.__api_key_entry.setEnabled(requires_key)
        self.__api_key_label.setEnabled(requires_key)

        is_openai = translator_api == TranslatorApi.OpenAI
        self.__openai_base_url_label.setEnabled(is_openai)
        self.__openai_base_url_entry.setEnabled(is_openai)
        self.__openai_model_label.setEnabled(is_openai)
        self.__openai_model_entry.setEnabled(is_openai)

    def __init_confirmation_box(self) -> None:
        self.__show_confirmations_box = QCheckBox(
            self.tr("Ask for confirmation before starting a batch machine translation")
        )
        self.__show_confirmations_box.setChecked(
            self._initial_config.show_confirmation_dialogs
        )
        self.__show_confirmations_box.stateChanged.connect(
            lambda _: self.changed_signal.emit()
        )
        self.__flayout.addRow(self.__show_confirmations_box)

    @override
    def apply(self, config: TranslatorConfig) -> None:
        config.translator = self.__api_selector.getCurrentValue()
        config.api_key = self.__api_key_entry.text().strip() or None
        config.openai_base_url = self.__openai_base_url_entry.text().strip()
        config.openai_model = self.__openai_model_entry.text().strip() or "gpt-4o-mini"
        config.show_confirmation_dialogs = self.__show_confirmations_box.isChecked()
