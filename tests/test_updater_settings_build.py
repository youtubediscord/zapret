from __future__ import annotations

import unittest

from updater.ui.settings_build import build_servers_settings_section


class _FakeSignal:
    def connect(self, callback):
        self.callback = callback


class _FakeToggleRow:
    def __init__(self, *args):
        self.args = args
        self.toggled = _FakeSignal()

    def setChecked(self, value, *, block_signals=False):  # noqa: N802
        self.checked = bool(value)
        self.block_signals = bool(block_signals)


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


if __name__ == "__main__":
    unittest.main()
