from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QVBoxLayout, QWidget

from profile.ui.shell import build_profile_shell


class ProfileShellAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_toolbar_controls_have_screen_reader_text(self) -> None:
        parent = QWidget()
        parent.resize(900, 400)
        layout = QVBoxLayout(parent)

        widgets = build_profile_shell(
            content_parent=parent,
            content_layout=layout,
            add_section_title=lambda *_args, **_kwargs: None,
            tr_fn=lambda _key, default: default,
            engine_label="Zapret 2",
            toolbar_title_key="page.winws2_pages.toolbar.title",
            request_button_key="page.winws2_pages.request.button",
            request_hint_key="page.winws2_pages.request.hint",
            loading_key="page.winws2_pages.loading",
            on_open_profile_request_form=lambda: None,
            on_add_user_profile=lambda: None,
            on_expand_all=lambda: None,
            on_collapse_all=lambda: None,
            on_open_profile_order=lambda: None,
            on_show_info_popup=lambda: None,
            on_profile_search_text_changed=lambda _text: None,
        )

        expected = {
            widgets.add_profile_btn: ("Добавить пользовательский profile", "Добавить новый пользовательский profile"),
            widgets.request_btn: ("Открыть форму добавления profile на GitHub", "Откройте готовую форму на GitHub"),
            widgets.expand_btn: ("Развернуть все группы профилей", "Развернуть все группы профилей"),
            widgets.collapse_btn: ("Свернуть все группы профилей", "Свернуть все группы профилей"),
            widgets.order_btn: ("Открыть порядок профилей в пресете", "изменения реального порядка профилей"),
            widgets.info_btn: ("Показать справку по профилям", "Показать краткое объяснение"),
            widgets.profile_search_input: ("Поиск профиля", "Поиск профиля по имени, портам и т.д."),
        }
        for widget, (name, description) in expected.items():
            with self.subTest(name=name):
                self.assertEqual(widget.accessibleName(), name)
                self.assertIn(description, widget.accessibleDescription())
                self.assertEqual(widget.property("screenReaderStateText"), name)

        search_description = widgets.profile_search_input.accessibleDescription()
        self.assertIn("После ввода перейдите в список клавишей Tab", search_description)
        self.assertIn("выберите profile стрелками вверх и вниз", search_description)


if __name__ == "__main__":
    unittest.main()
