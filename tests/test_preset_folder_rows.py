from __future__ import annotations

import unittest
import inspect

from folders.defaults import COMMON_FOLDER_KEY, build_default_preset_folders
from presets.user_presets_page_plans import build_preset_rows_plan
from presets import folders as preset_folders


class PresetFolderRowsTests(unittest.TestCase):
    def test_preset_rows_do_not_accept_old_hierarchy_source(self) -> None:
        signature = inspect.signature(build_preset_rows_plan)
        source = inspect.getsource(preset_folders.build_preset_folder_rows)

        self.assertNotIn("hierarchy", signature.parameters)
        self.assertNotIn("get_preset_meta", source)

    def test_rows_are_grouped_by_folders_with_pinned_folder_above_all(self) -> None:
        folder_state = build_default_preset_folders()
        folder_state["items"] = {
            "Default.txt": {"folder_key": COMMON_FOLDER_KEY, "order": None, "rating": 9},
            "Manual.txt": {"folder_key": COMMON_FOLDER_KEY, "order": 0, "rating": 0},
            "Game.txt": {"folder_key": "game-filter", "order": None, "rating": 0},
            "Pinned.txt": {"folder_key": COMMON_FOLDER_KEY, "order": None, "rating": 0, "pinned": True},
        }

        plan = build_preset_rows_plan(
            all_presets={
                "Default.txt": {"display_name": "Default", "is_builtin": True},
                "Manual.txt": {"display_name": "Manual", "is_builtin": False},
                "Game.txt": {"display_name": "Game", "is_builtin": True},
                "Pinned.txt": {"display_name": "Pinned", "is_builtin": False},
            },
            query="",
            active_file_name="Default.txt",
            language="ru",
            folder_state=folder_state,
            empty_not_found_key="missing",
            empty_none_key="empty",
        )

        rows = plan.rows
        self.assertEqual(rows[0]["kind"], "folder")
        self.assertEqual(rows[0]["name"], "Закрепленные")
        self.assertEqual(rows[1]["kind"], "preset")
        self.assertEqual(rows[1]["file_name"], "Pinned.txt")

        common_index = next(index for index, row in enumerate(rows) if row.get("kind") == "folder" and row.get("folder_key") == COMMON_FOLDER_KEY)
        common_items = [
            row["file_name"]
            for row in rows[common_index + 1:]
            if row.get("kind") == "preset"
        ][:2]
        self.assertEqual(common_items, ["Manual.txt", "Default.txt"])
        default_row = next(row for row in rows if row.get("file_name") == "Default.txt")
        self.assertEqual(default_row["folder_name"], "Общие")

    def test_search_shows_only_matching_folder_rows(self) -> None:
        folder_state = build_default_preset_folders()
        folder_state["items"] = {
            "Default.txt": {"folder_key": COMMON_FOLDER_KEY, "order": None},
            "Game.txt": {"folder_key": "game-filter", "order": None},
        }

        plan = build_preset_rows_plan(
            all_presets={
                "Default.txt": {"display_name": "Default", "is_builtin": True},
                "Game.txt": {"display_name": "Game", "is_builtin": True},
            },
            query="game",
            active_file_name="",
            language="ru",
            folder_state=folder_state,
            empty_not_found_key="missing",
            empty_none_key="empty",
        )

        folder_names = [row["name"] for row in plan.rows if row["kind"] == "folder"]
        item_names = [row["name"] for row in plan.rows if row["kind"] == "preset"]
        self.assertEqual(folder_names, ["Game filter"])
        self.assertEqual(item_names, ["Game"])


if __name__ == "__main__":
    unittest.main()
