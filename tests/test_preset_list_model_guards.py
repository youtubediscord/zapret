from __future__ import annotations

import unittest

from ui.presets_menu.model import PresetListModel


class PresetListModelGuardTests(unittest.TestCase):
    def test_rename_preset_skips_same_file_and_name(self) -> None:
        model = PresetListModel()
        model.set_rows([
            {
                "kind": "preset",
                "file_name": "Default.txt",
                "name": "Default",
                "folder_key": "common",
            },
        ])
        self.assertFalse(model.rename_preset("Default.txt", "Default.txt", name="Default"))

    def test_set_folder_collapsed_removes_only_visible_folder_rows(self) -> None:
        model = PresetListModel()
        model.set_rows(
            [
                {"kind": "folder", "folder_key": "common", "name": "Common", "is_collapsed": False, "count": 2},
                {"kind": "preset", "file_name": "A.txt", "name": "A", "folder_key": "common"},
                {"kind": "preset", "file_name": "B.txt", "name": "B", "folder_key": "common"},
                {"kind": "folder", "folder_key": "games", "name": "Games", "is_collapsed": False, "count": 1},
                {"kind": "preset", "file_name": "C.txt", "name": "C", "folder_key": "games"},
            ]
        )

        self.assertTrue(model.set_folder_collapsed("common", True))

        self.assertEqual(model.rowCount(), 3)
        self.assertTrue(model.index(0, 0).data(PresetListModel.CollapsedRole))
        self.assertEqual(model.index(1, 0).data(PresetListModel.FolderKeyRole), "games")
        self.assertEqual(model.index(2, 0).data(PresetListModel.FileNameRole), "C.txt")

    def test_set_folder_collapsed_does_not_expand_without_rows_plan(self) -> None:
        model = PresetListModel()
        model.set_rows(
            [
                {"kind": "folder", "folder_key": "common", "name": "Common", "is_collapsed": True, "count": 2},
            ]
        )

        self.assertFalse(model.set_folder_collapsed("common", False))

    def test_preset_display_name_cache_updates_with_row_metadata(self) -> None:
        model = PresetListModel()
        model.set_rows(
            [
                {"kind": "preset", "file_name": "A.txt", "name": "Old"},
            ]
        )

        self.assertEqual(model.preset_display_name("A.txt"), "Old")
        self.assertTrue(model.update_preset_row("A.txt", name="New"))

        self.assertEqual(model.preset_display_name("A.txt"), "New")

    def test_preset_builtin_cache_updates_with_row_metadata(self) -> None:
        model = PresetListModel()
        model.set_rows(
            [
                {"kind": "preset", "file_name": "A.txt", "name": "A", "is_builtin": False},
            ]
        )

        self.assertFalse(model.preset_is_builtin("A.txt"))
        self.assertTrue(model.update_preset_row("A.txt", is_builtin=True))

        self.assertTrue(model.preset_is_builtin("A.txt"))

    def test_preset_rating_cache_updates_with_row_metadata(self) -> None:
        model = PresetListModel()
        model.set_rows(
            [
                {"kind": "preset", "file_name": "A.txt", "name": "A", "rating": 2},
            ]
        )

        self.assertEqual(model.preset_rating("A.txt"), 2)
        self.assertTrue(model.update_preset_row("A.txt", rating=7))

        self.assertEqual(model.preset_rating("A.txt"), 7)


if __name__ == "__main__":
    unittest.main()
