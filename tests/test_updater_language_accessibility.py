from __future__ import annotations

import unittest

from config.build_info import APP_VERSION, CHANNEL
from updater.ui.language import apply_servers_page_language


class _TextTarget:
    def __init__(self, text: str = ""):
        self.text = text
        self._accessible_name = ""
        self._accessible_description = ""
        self.properties = {}

    def setText(self, text):  # noqa: N802
        self.text = text

    def setAccessibleName(self, value):  # noqa: N802
        self._accessible_name = value

    def accessibleName(self):  # noqa: N802
        return self._accessible_name

    def setAccessibleDescription(self, value):  # noqa: N802
        self._accessible_description = value

    def accessibleDescription(self):  # noqa: N802
        return self._accessible_description

    def setProperty(self, name, value):  # noqa: N802
        self.properties[name] = value

    def property(self, name):
        return self.properties.get(name)


class _Card:
    titleLabel = None

    def __init__(self):
        self.title = ""
        self.content = ""
        self._accessible_name = ""
        self._accessible_description = ""

    def set_title(self, text):
        self.title = text

    def setContent(self, text):  # noqa: N802
        self.content = text

    def setAccessibleName(self, value):  # noqa: N802
        self._accessible_name = value

    def accessibleName(self):  # noqa: N802
        return self._accessible_name

    def setAccessibleDescription(self, value):  # noqa: N802
        self._accessible_description = value

    def accessibleDescription(self):  # noqa: N802
        return self._accessible_description


class _Stateful:
    def __init__(self):
        self.language = ""
        self.texts = ()
        self._accessible_name = ""
        self._accessible_description = ""
        self.properties = {}

    def set_ui_language(self, language):
        self.language = language

    def set_texts(self, *texts):
        self.texts = texts

    def accessibleName(self):  # noqa: N802
        return self._accessible_name

    def setAccessibleName(self, value):  # noqa: N802
        self._accessible_name = value

    def accessibleDescription(self):  # noqa: N802
        return self._accessible_description

    def setAccessibleDescription(self, value):  # noqa: N802
        self._accessible_description = value

    def property(self, name):
        return self.properties.get(name)

    def setProperty(self, name, value):  # noqa: N802
        self.properties[name] = value


class _Breadcrumb:
    def __init__(self):
        self.items = []

    def blockSignals(self, _blocked):  # noqa: N802
        pass

    def clear(self):
        self.items.clear()

    def addItem(self, key, text):  # noqa: N802
        self.items.append((key, text))


class _Table:
    def setHorizontalHeaderLabels(self, labels):  # noqa: N802
        self.labels = labels


class UpdaterLanguageAccessibilityTests(unittest.TestCase):
    def test_language_refresh_updates_version_screen_reader_state(self) -> None:
        version_info_label = _TextTarget("old")

        apply_servers_page_language(
            tr_fn=lambda _key, default, **_kwargs: default,
            ui_language="ru",
            update_card=_Stateful(),
            changelog_card=_Stateful(),
            breadcrumb=_Breadcrumb(),
            page_title_label=_TextTarget(),
            servers_title_label=_TextTarget(),
            legend_active_label=_TextTarget(),
            servers_table=_Table(),
            settings_card=_Card(),
            toggle_label=None,
            auto_check_card=_Stateful(),
            version_info_label=version_info_label,
            telegram_card=_Card(),
            telegram_info_label=None,
            telegram_button=_TextTarget(),
            refresh_server_rows=lambda: None,
        )

        expected = f"Версия ZapretGUI: v{APP_VERSION} · {CHANNEL}"

        self.assertEqual(version_info_label.accessibleName(), expected)
        self.assertEqual(
            version_info_label.property("screenReaderStateText"),
            expected,
        )

    def test_language_refresh_updates_active_legend_screen_reader_state(self) -> None:
        legend_active_label = _TextTarget("old")

        apply_servers_page_language(
            tr_fn=lambda _key, default, **_kwargs: default,
            ui_language="ru",
            update_card=_Stateful(),
            changelog_card=_Stateful(),
            breadcrumb=_Breadcrumb(),
            page_title_label=_TextTarget(),
            servers_title_label=_TextTarget(),
            legend_active_label=legend_active_label,
            servers_table=_Table(),
            settings_card=_Card(),
            toggle_label=None,
            auto_check_card=_Stateful(),
            version_info_label=_TextTarget(),
            telegram_card=_Card(),
            telegram_info_label=None,
            telegram_button=_TextTarget(),
            refresh_server_rows=lambda: None,
        )

        expected = "Легенда серверов обновлений: активный сервер"
        self.assertEqual(legend_active_label.accessibleName(), expected)
        self.assertEqual(
            legend_active_label.property("screenReaderStateText"),
            expected,
        )

    def test_language_refresh_updates_auto_check_screen_reader_state(self) -> None:
        auto_check_card = _Stateful()

        apply_servers_page_language(
            tr_fn=lambda _key, default, **_kwargs: default,
            ui_language="ru",
            update_card=_Stateful(),
            changelog_card=_Stateful(),
            breadcrumb=_Breadcrumb(),
            page_title_label=_TextTarget(),
            servers_title_label=_TextTarget(),
            legend_active_label=_TextTarget(),
            servers_table=_Table(),
            settings_card=_Card(),
            toggle_label=None,
            auto_check_card=auto_check_card,
            version_info_label=_TextTarget(),
            telegram_card=_Card(),
            telegram_info_label=None,
            telegram_button=_TextTarget(),
            refresh_server_rows=lambda: None,
        )

        expected = "Проверять обновления при запуске"
        self.assertEqual(auto_check_card.accessibleName(), expected)
        self.assertEqual(auto_check_card.property("screenReaderStateText"), expected)
        self.assertIn("Автоматически проверять", auto_check_card.accessibleDescription())

    def test_language_refresh_updates_telegram_screen_reader_action(self) -> None:
        telegram_card = _Card()
        telegram_button = _TextTarget()

        apply_servers_page_language(
            tr_fn=lambda key, default, **_kwargs: {
                "page.servers.telegram.accessible_name": "Открыть канал обновлений",
                "page.servers.telegram.accessible_description": "Открывает канал с версиями программы.",
            }.get(key, default),
            ui_language="ru",
            update_card=_Stateful(),
            changelog_card=_Stateful(),
            breadcrumb=_Breadcrumb(),
            page_title_label=_TextTarget(),
            servers_title_label=_TextTarget(),
            legend_active_label=_TextTarget(),
            servers_table=_Table(),
            settings_card=_Card(),
            toggle_label=None,
            auto_check_card=_Stateful(),
            version_info_label=_TextTarget(),
            telegram_card=telegram_card,
            telegram_info_label=None,
            telegram_button=telegram_button,
            refresh_server_rows=lambda: None,
        )

        self.assertEqual(telegram_card.accessibleName(), "Открыть канал обновлений")
        self.assertEqual(telegram_card.accessibleDescription(), "Открывает канал с версиями программы.")
        self.assertEqual(telegram_button.accessibleName(), "Открыть канал обновлений")
        self.assertEqual(telegram_button.accessibleDescription(), "Открывает канал с версиями программы.")


if __name__ == "__main__":
    unittest.main()
