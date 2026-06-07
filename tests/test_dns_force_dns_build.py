from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import CaptionLabel, PushButton, SettingCardGroup

from dns.ui.force_dns_build import build_force_dns_card_ui
from ui.fluent_widgets import (
    enable_setting_card_group_auto_height,
    insert_widget_into_setting_card_group,
)
from ui.theme import get_theme_tokens
from ui.widgets.win11_controls import Win11ToggleRow


class ForceDnsBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_reset_button_uses_fluent_icon_keyword_for_plain_push_button(self) -> None:
        parent = QWidget()
        added_widgets = []

        _active, widgets = build_force_dns_card_ui(
            parent=parent,
            content_parent=parent,
            add_section_title_fn=lambda **_kwargs: None,
            tr_fn=lambda _key, default: default,
            add_widget_fn=added_widgets.append,
            get_theme_tokens_fn=get_theme_tokens,
            get_force_dns_status_fn=lambda: False,
            setting_card_group_cls=SettingCardGroup,
            caption_label_cls=CaptionLabel,
            action_button_cls=PushButton,
            win11_toggle_row_cls=Win11ToggleRow,
            qwidget_cls=QWidget,
            qvbox_layout_cls=QVBoxLayout,
            qhbox_layout_cls=QHBoxLayout,
            qt_namespace=Qt,
            insert_widget_into_setting_card_group_fn=insert_widget_into_setting_card_group,
            enable_setting_card_group_auto_height_fn=enable_setting_card_group_auto_height,
            on_toggle=lambda _checked: None,
            on_confirm_reset=lambda: None,
        )

        self.assertEqual(1, len(added_widgets))
        self.assertFalse(widgets.reset_button.icon().isNull())

    def test_reset_button_has_screen_reader_text(self) -> None:
        parent = QWidget()

        _active, widgets = build_force_dns_card_ui(
            parent=parent,
            content_parent=parent,
            add_section_title_fn=lambda **_kwargs: None,
            tr_fn=lambda _key, default: default,
            add_widget_fn=lambda _widget: None,
            get_theme_tokens_fn=get_theme_tokens,
            get_force_dns_status_fn=lambda: True,
            setting_card_group_cls=SettingCardGroup,
            caption_label_cls=CaptionLabel,
            action_button_cls=PushButton,
            win11_toggle_row_cls=Win11ToggleRow,
            qwidget_cls=QWidget,
            qvbox_layout_cls=QVBoxLayout,
            qhbox_layout_cls=QHBoxLayout,
            qt_namespace=Qt,
            insert_widget_into_setting_card_group_fn=insert_widget_into_setting_card_group,
            enable_setting_card_group_auto_height_fn=enable_setting_card_group_auto_height,
            on_toggle=lambda _checked: None,
            on_confirm_reset=lambda: None,
        )

        self.assertEqual(widgets.reset_button.accessibleName(), "Сбросить DNS на DHCP")
        self.assertIn("Отключить Force DNS", widgets.reset_button.accessibleDescription())


if __name__ == "__main__":
    unittest.main()
