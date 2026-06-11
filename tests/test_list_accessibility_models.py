from __future__ import annotations

import unittest
from types import SimpleNamespace

from PyQt6.QtCore import Qt


class ListAccessibilityModelTests(unittest.TestCase):
    def test_profile_rows_expose_screen_reader_text(self) -> None:
        from profile.ui.profile_list_model import ProfileListModel

        model = ProfileListModel()
        model._rows = [
            {
                "kind": "profile",
                "display_name": "YouTube",
                "enabled": True,
                "in_preset": True,
                "strategy_name": "TLS fake",
                "favorite": True,
                "rating": "work",
            }
        ]

        text = model.index(0, 0).data(Qt.ItemDataRole.AccessibleTextRole)

        self.assertEqual(
            text,
            "YouTube, включён, есть в preset, стратегия: TLS fake, в избранном, работает. "
            "Нажмите Enter, чтобы открыть profile.",
        )

    def test_profile_folder_rows_expose_screen_reader_text(self) -> None:
        from profile.ui.profile_list_model import ProfileListModel

        model = ProfileListModel()
        model._rows = [
            {
                "kind": "group",
                "group_name": "Видео",
                "count": 3,
                "collapsed": True,
            }
        ]

        text = model.index(0, 0).data(Qt.ItemDataRole.AccessibleTextRole)

        self.assertEqual(
            text,
            "Группа Видео, 3 профиля, свернута. Нажмите Enter, чтобы свернуть или развернуть группу.",
        )

    def test_profile_order_rows_expose_screen_reader_text(self) -> None:
        from profile.ui.profile_order_list import ProfileOrderListModel

        model = ProfileOrderListModel()
        model.set_profiles(
            (
                SimpleNamespace(
                    display_name="YouTube",
                    enabled=True,
                    in_preset=True,
                    profile_index=2,
                    strategy_name="TLS fake",
                    match_lines=("--filter-tcp=443",),
                ),
            )
        )

        text = model.index(0, 0).data(Qt.ItemDataRole.AccessibleTextRole)

        self.assertEqual(
            text,
            "Позиция 1, YouTube, включён, стратегия: TLS fake, TCP | TCP 443. "
            "PageUp и PageDown меняют порядок profile.",
        )

    def test_preset_rows_expose_screen_reader_text(self) -> None:
        from ui.presets_menu.model import PresetListModel

        model = PresetListModel()
        model.set_rows(
            [
                {
                    "kind": "preset",
                    "name": "Default",
                    "file_name": "Default.txt",
                    "is_active": True,
                    "is_builtin": True,
                    "is_pinned": True,
                    "folder_name": "Общие",
                    "rating": 9,
                }
            ]
        )

        text = model.index(0, 0).data(Qt.ItemDataRole.AccessibleTextRole)

        self.assertEqual(
            text,
            "Default, активный пресет, встроенный, папка: Общие, закреплённый, оценка 9. Нажмите Enter, чтобы открыть preset.",
        )

    def test_preset_folder_rows_expose_screen_reader_text(self) -> None:
        from ui.presets_menu.model import PresetListModel

        model = PresetListModel()
        model.set_rows(
            [
                {
                    "kind": "folder",
                    "name": "Общие",
                    "count": 5,
                    "is_collapsed": False,
                }
            ]
        )

        text = model.index(0, 0).data(Qt.ItemDataRole.AccessibleTextRole)

        self.assertEqual(
            text,
            "Папка Общие, 5 пресетов, развернута. Нажмите Enter, чтобы свернуть или развернуть папку.",
        )


if __name__ == "__main__":
    unittest.main()
