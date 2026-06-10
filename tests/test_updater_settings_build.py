from __future__ import annotations

import unittest

from updater.ui import settings_build
from updater.ui.settings_build import build_servers_settings_section


class _FakeSignal:
    def connect(self, callback):
        self.callback = callback


class _FakeToggleRow:
    def __init__(self, *args):
        self.args = args
        self.toggled = _FakeSignal()
        self._accessible_name = ""
        self._accessible_description = ""
        self.properties = {}

    def setChecked(self, value, *, block_signals=False):  # noqa: N802
        self.checked = bool(value)
        self.block_signals = bool(block_signals)

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


class _FakeSettingsGroup:
    def __init__(self, title, parent):
        self.title = title
        self.parent = parent
        self.rows = []

    def addSettingCard(self, row):  # noqa: N802
        self.rows.append(row)


class _FakeCard:
    def add_layout(self, layout):
        self.layout = layout


class _FakeButton:
    def __init__(self):
        self.text = ""
        self._accessible_name = ""
        self._accessible_description = ""

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


class _FakePushSettingCard:
    def __init__(self, action_text, icon, title, content):
        self.action_text = action_text
        self.icon = icon
        self.title = title
        self.content = content
        self.button = _FakeButton()
        self.clicked = _FakeSignal()
        self._accessible_name = ""
        self._accessible_description = ""

    def setAccessibleName(self, value):  # noqa: N802
        self._accessible_name = value

    def accessibleName(self):  # noqa: N802
        return self._accessible_name

    def setAccessibleDescription(self, value):  # noqa: N802
        self._accessible_description = value

    def accessibleDescription(self):  # noqa: N802
        return self._accessible_description


class _FakeLabel:
    def __init__(self, text):
        self.text = text
        self._accessible_name = ""
        self.properties = {}

    def setAccessibleName(self, value):  # noqa: N802
        self._accessible_name = value

    def accessibleName(self):  # noqa: N802
        return self._accessible_name

    def setProperty(self, name, value):  # noqa: N802
        self.properties[name] = value

    def property(self, name):
        return self.properties.get(name)


class _FakeLayout:
    def setContentsMargins(self, *args):  # noqa: N802
        self.margins = args

    def setSpacing(self, value):  # noqa: N802
        self.spacing = value

    def addWidget(self, widget):  # noqa: N802
        self.widget = widget

    def addStretch(self):  # noqa: N802
        self.stretch = True


class UpdaterSettingsBuildTests(unittest.TestCase):
    def test_version_label_is_not_added_as_full_settings_card(self) -> None:
        widgets = build_servers_settings_section(
            content_parent=object(),
            tr_fn=lambda _key, default: default,
            accent_hex="#22dddd",
            auto_check_enabled=True,
            app_version="21.0.0.142",
            channel="dev",
            setting_card_group_cls=_FakeSettingsGroup,
            settings_card_cls=_FakeCard,
            win11_toggle_row_cls=_FakeToggleRow,
            caption_label_cls=_FakeLabel,
            qhbox_layout_cls=_FakeLayout,
            on_auto_check_toggled=lambda _value: None,
        )

        self.assertEqual(len(widgets.card.rows), 1)
        self.assertIs(widgets.card.rows[0], widgets.auto_check_card)
        self.assertEqual(widgets.version_info_label.text, "v21.0.0.142 · dev")

    def test_version_label_exposes_screen_reader_state(self) -> None:
        widgets = build_servers_settings_section(
            content_parent=object(),
            tr_fn=lambda _key, default: default,
            accent_hex="#22dddd",
            auto_check_enabled=False,
            app_version="21.0.0.142",
            channel="dev",
            setting_card_group_cls=_FakeSettingsGroup,
            settings_card_cls=_FakeCard,
            win11_toggle_row_cls=_FakeToggleRow,
            caption_label_cls=_FakeLabel,
            qhbox_layout_cls=_FakeLayout,
            on_auto_check_toggled=lambda _value: None,
        )

        self.assertEqual(widgets.version_info_label.accessibleName(), "Версия ZapretGUI: v21.0.0.142 · dev")
        self.assertEqual(
            widgets.version_info_label.property("screenReaderStateText"),
            "Версия ZapretGUI: v21.0.0.142 · dev",
        )

    def test_auto_check_toggle_exposes_screen_reader_state(self) -> None:
        enabled_widgets = build_servers_settings_section(
            content_parent=object(),
            tr_fn=lambda _key, default: default,
            accent_hex="#22dddd",
            auto_check_enabled=True,
            app_version="21.0.0.142",
            channel="dev",
            setting_card_group_cls=_FakeSettingsGroup,
            settings_card_cls=_FakeCard,
            win11_toggle_row_cls=_FakeToggleRow,
            caption_label_cls=_FakeLabel,
            qhbox_layout_cls=_FakeLayout,
            on_auto_check_toggled=lambda _value: None,
        )
        disabled_widgets = build_servers_settings_section(
            content_parent=object(),
            tr_fn=lambda _key, default: default,
            accent_hex="#22dddd",
            auto_check_enabled=False,
            app_version="21.0.0.142",
            channel="dev",
            setting_card_group_cls=_FakeSettingsGroup,
            settings_card_cls=_FakeCard,
            win11_toggle_row_cls=_FakeToggleRow,
            caption_label_cls=_FakeLabel,
            qhbox_layout_cls=_FakeLayout,
            on_auto_check_toggled=lambda _value: None,
        )

        self.assertEqual(
            enabled_widgets.auto_check_card.accessibleName(),
            "Проверять обновления при запуске, включено",
        )
        self.assertEqual(
            enabled_widgets.auto_check_card.property("screenReaderStateText"),
            "Проверять обновления при запуске, включено",
        )
        self.assertIn("Автоматически проверять", enabled_widgets.auto_check_card.accessibleDescription())
        self.assertEqual(
            disabled_widgets.auto_check_card.accessibleName(),
            "Проверять обновления при запуске, выключено",
        )
        self.assertEqual(
            disabled_widgets.auto_check_card.property("screenReaderStateText"),
            "Проверять обновления при запуске, выключено",
        )

    def test_telegram_card_and_button_expose_screen_reader_action(self) -> None:
        old_icon_factory = settings_build.get_themed_qta_icon
        settings_build.get_themed_qta_icon = lambda *_args, **_kwargs: object()
        self.addCleanup(setattr, settings_build, "get_themed_qta_icon", old_icon_factory)

        widgets = settings_build.build_servers_telegram_section(
            tr_fn=lambda _key, default: default,
            accent_hex="#22dddd",
            push_setting_card_cls=_FakePushSettingCard,
            on_open_channel=lambda: None,
        )

        expected_name = "Открыть Telegram канал обновлений"

        self.assertEqual(widgets.card.accessibleName(), expected_name)
        self.assertIn("версии программы", widgets.card.accessibleDescription())
        self.assertEqual(widgets.button.accessibleName(), expected_name)
        self.assertIn("версии программы", widgets.button.accessibleDescription())


if __name__ == "__main__":
    unittest.main()
