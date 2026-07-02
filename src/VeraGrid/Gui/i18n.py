from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator
from PySide6.QtWidgets import QApplication

from VeraGridEngine.IO.file_system import get_create_veragrid_folder


class ApplicationLanguage(Enum):
    """
    Supported application language selection modes.
    """

    SYSTEM = "system"
    ENGLISH = "en"
    JAPANESE = "ja_JP"
    BASQUE = "eu_ES"
    GALICIAN = "gl_ES"
    TONGAN = "to_TO"
    TUVALUAN = "tvl_TV"
    ARABIC = "ar"
    ITALIAN = "it_IT"
    GREEK = "el_GR"
    DUTCH = "nl_NL"
    CATALAN = "ca_ES"
    CHINESE = "zh_CN"
    GERMAN = "de_DE"
    FRENCH = "fr_FR"
    PORTUGUESE = "pt_PT"
    SPANISH = "es_ES"

    def __str__(self) -> str:
        """
        Return the stable serialized identifier for one language option.

        :returns: Stable language identifier.
        """
        return self.value


class InstalledTranslations:
    """
    Container keeping the installed Qt translators alive for the application lifetime.
    """

    __slots__ = ("app_translator", "qtbase_translator")

    def __init__(self) -> None:
        """
        Build one empty translation container.

        :returns: None.
        """
        self.app_translator: QTranslator | None = None
        self.qtbase_translator: QTranslator | None = None


class ApplicationTranslator:
    """
    Application-wide translator installer and lifetime owner.
    """

    __slots__ = ("_app", "_current_language", "_installed_translations")

    def __init__(self, app: QApplication) -> None:
        """
        Build one translator controller for the running Qt application.

        :param app: Qt application receiving translator installations.
        :returns: None.
        """
        self._app: QApplication = app
        self._current_language: ApplicationLanguage = ApplicationLanguage.SYSTEM
        self._installed_translations: InstalledTranslations = InstalledTranslations()

    def get_current_language(self) -> ApplicationLanguage:
        """
        Return the currently selected application language.

        :returns: Current application language.
        """
        return self._current_language

    def set_language(self, language: ApplicationLanguage) -> None:
        """
        Apply one language selection to the whole application.

        The method removes any previous translators first because Qt only keeps
        the last installed translation chain consistent when the old instances
        are removed explicitly before the new ones are installed.

        :param language: Requested application language.
        :returns: None.
        """
        requested_language_code: str = get_requested_language_code(language=language)
        candidate_languages: list[str] = build_language_candidates(requested_language_code)

        # Remove the previous translators before installing the new language,
        # otherwise strings from multiple languages can remain active.
        self._clear_translators()

        # Update Qt's default locale so built-in widgets use the same locale
        # rules as the translation catalogs we are about to install.
        if len(requested_language_code) > 0:
            QLocale.setDefault(QLocale(requested_language_code))
        else:
            QLocale.setDefault(QLocale.system())

        # Install the application catalog first so VeraGrid strings resolve
        # before the built-in Qt dialog strings are queried.
        self._installed_translations.app_translator = load_translator(
            prefix="veragrid",
            directory=str(get_translations_directory()),
            candidates=candidate_languages,
        )
        if self._installed_translations.app_translator is not None:
            self._app.installTranslator(self._installed_translations.app_translator)
        else:
            pass

        # Install Qt's own catalog afterwards so stock widgets like file dialogs
        # and message buttons switch to the same language when available.
        self._installed_translations.qtbase_translator = load_translator(
            prefix="qtbase",
            directory=get_qt_translations_directory(),
            candidates=candidate_languages,
        )
        if self._installed_translations.qtbase_translator is not None:
            self._app.installTranslator(self._installed_translations.qtbase_translator)
        else:
            pass

        self._current_language = language

    def _clear_translators(self) -> None:
        """
        Remove any translators currently installed by this controller.

        :returns: None.
        """
        if self._installed_translations.app_translator is not None:
            self._app.removeTranslator(self._installed_translations.app_translator)
            self._installed_translations.app_translator = None
        else:
            pass

        if self._installed_translations.qtbase_translator is not None:
            self._app.removeTranslator(self._installed_translations.qtbase_translator)
            self._installed_translations.qtbase_translator = None
        else:
            pass


def get_translations_directory() -> Path:
    """
    Return the VeraGrid translations directory.

    :returns: Application translations directory.
    """
    return Path(__file__).resolve().parent / "translations"


def get_qt_translations_directory() -> str:
    """
    Return the Qt built-in translations directory.

    :returns: Qt translations directory.
    """
    return QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)


def normalize_language_code(language_code: str | None) -> str:
    """
    Normalize one locale string to the ``ll`` or ``ll_CC`` form used by Qt catalogs.

    :param language_code: Raw locale code.
    :returns: Normalized locale code or an empty string.
    """
    raw_text: str = "" if language_code is None else str(language_code).strip()

    if len(raw_text) == 0:
        return ""
    else:
        pass

    locale_text: str = raw_text.split(".", 1)[0].replace("-", "_")
    parts: list[str] = [part for part in locale_text.split("_") if len(part) > 0]

    if len(parts) == 0:
        return ""
    else:
        if len(parts) == 1:
            return parts[0].lower()
        else:
            return parts[0].lower() + "_" + parts[1].upper()


def build_language_candidates(language_code: str | None) -> list[str]:
    """
    Build the locale fallback order used when loading ``.qm`` files.

    :param language_code: Preferred locale code.
    :returns: Locale candidates ordered from most specific to least specific.
    """
    normalized_code: str = normalize_language_code(language_code)

    if len(normalized_code) == 0:
        return list()
    else:
        if "_" in normalized_code:
            base_language: str = normalized_code.split("_", 1)[0]
            return [normalized_code, base_language]
        else:
            return [normalized_code]


def get_system_language_code(ui_languages: Iterable[str] | None = None) -> str:
    """
    Return the first usable language reported by the system locale.

    :param ui_languages: Optional override used by tests.
    :returns: Normalized preferred system language code or an empty string.
    """
    language_items: Iterable[str]

    if ui_languages is None:
        language_items = QLocale.system().uiLanguages()
    else:
        language_items = ui_languages

    language_item: str

    for language_item in language_items:
        normalized_code: str = normalize_language_code(language_item)
        if len(normalized_code) > 0:
            return normalized_code
        else:
            pass

    return ""


def get_requested_language_code(
    language: ApplicationLanguage,
    ui_languages: Iterable[str] | None = None,
) -> str:
    """
    Resolve one application language selection to a concrete locale code.

    :param language: Selected application language.
    :param ui_languages: Optional system-language override used by tests.
    :returns: Concrete locale code or an empty string.
    """
    if language == ApplicationLanguage.SYSTEM:
        return get_system_language_code(ui_languages=ui_languages)
    else:
        return normalize_language_code(str(language.value))


def load_translator(prefix: str, directory: str, candidates: list[str]) -> QTranslator | None:
    """
    Load one Qt translator by trying each locale candidate in order.

    :param prefix: Translation file prefix.
    :param directory: Directory containing the translation files.
    :param candidates: Ordered locale candidate list.
    :returns: Loaded translator or ``None``.
    """
    locale_candidate: str

    for locale_candidate in candidates:
        translator: QTranslator = QTranslator()
        if translator.load(f"{prefix}_{locale_candidate}", directory):
            return translator
        else:
            pass

    return None


def get_gui_config_file_path() -> Path:
    """
    Return the GUI configuration file path used to persist the language selection.

    :returns: GUI configuration file path.
    """
    return Path(get_create_veragrid_folder()) / "gui_config.json"


def language_from_name(name_text: str | None) -> ApplicationLanguage:
    """
    Parse one persisted language name into the corresponding enum value.

    :param name_text: Persisted enum name.
    :returns: Matching application language.
    """
    if name_text is None:
        return ApplicationLanguage.SYSTEM
    else:
        pass

    normalized_name: str = str(name_text).strip()

    if normalized_name == ApplicationLanguage.ENGLISH.name:
        return ApplicationLanguage.ENGLISH
    else:
        if normalized_name == ApplicationLanguage.JAPANESE.name:
            return ApplicationLanguage.JAPANESE
        else:
            if normalized_name == ApplicationLanguage.BASQUE.name:
                return ApplicationLanguage.BASQUE
            else:
                if normalized_name == ApplicationLanguage.GALICIAN.name:
                    return ApplicationLanguage.GALICIAN
                else:
                    if normalized_name == ApplicationLanguage.TONGAN.name:
                        return ApplicationLanguage.TONGAN
                    else:
                        if normalized_name == ApplicationLanguage.TUVALUAN.name:
                            return ApplicationLanguage.TUVALUAN
                        else:
                            if normalized_name == ApplicationLanguage.ARABIC.name:
                                return ApplicationLanguage.ARABIC
                            else:
                                if normalized_name == ApplicationLanguage.ITALIAN.name:
                                    return ApplicationLanguage.ITALIAN
                                else:
                                    if normalized_name == ApplicationLanguage.GREEK.name:
                                        return ApplicationLanguage.GREEK
                                    else:
                                        if normalized_name == ApplicationLanguage.DUTCH.name:
                                            return ApplicationLanguage.DUTCH
                                        else:
                                            if normalized_name == ApplicationLanguage.CATALAN.name:
                                                return ApplicationLanguage.CATALAN
                                            else:
                                                if normalized_name == ApplicationLanguage.CHINESE.name:
                                                    return ApplicationLanguage.CHINESE
                                                else:
                                                    if normalized_name == ApplicationLanguage.GERMAN.name:
                                                        return ApplicationLanguage.GERMAN
                                                    else:
                                                        if normalized_name == ApplicationLanguage.FRENCH.name:
                                                            return ApplicationLanguage.FRENCH
                                                        else:
                                                            if normalized_name == ApplicationLanguage.PORTUGUESE.name:
                                                                return ApplicationLanguage.PORTUGUESE
                                                            else:
                                                                if normalized_name == ApplicationLanguage.SPANISH.name:
                                                                    return ApplicationLanguage.SPANISH
                                                                else:
                                                                    return ApplicationLanguage.SYSTEM


def read_saved_language() -> ApplicationLanguage:
    """
    Read the last saved language from the GUI configuration file.

    The read path only inspects the small part of the JSON tree that stores the
    language selection so the startup translation choice can happen before the
    main window is created.

    :returns: Saved application language or ``SYSTEM`` when missing.
    """
    config_path: Path = get_gui_config_file_path()

    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as file_pointer:
            try:
                json_data: object = json.load(file_pointer)
            except json.decoder.JSONDecodeError:
                return ApplicationLanguage.SYSTEM

        if isinstance(json_data, dict):
            graphics_data: object = json_data.get("graphics", None)
            if isinstance(graphics_data, dict):
                saved_language_name: object = graphics_data.get("language", None)
                if isinstance(saved_language_name, str):
                    return language_from_name(saved_language_name)
                else:
                    return ApplicationLanguage.SYSTEM
            else:
                return ApplicationLanguage.SYSTEM
        else:
            return ApplicationLanguage.SYSTEM
    else:
        return ApplicationLanguage.SYSTEM
