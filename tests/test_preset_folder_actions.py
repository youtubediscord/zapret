from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from folders.defaults import COMMON_FOLDER_KEY, PINNED_FOLDER_KEY
from presets.folders import (
    copy_preset_item_meta,
    create_preset_folder,
    delete_preset_folder,
    delete_preset_item_meta,
    get_preset_item_meta,
    load_preset_folder_state,
    move_preset_folder_by_step,
    move_preset_by_step,
    move_preset_after,
    move_preset_before,
    rename_preset_folder,
    rename_preset_item_meta,
    set_preset_folder_collapsed,
    set_preset_rating,
    toggle_preset_pin,
)
from settings.mode import PRESETS_SCOPE_WINWS2


class PresetFolderActionTests(unittest.TestCase):
    def test_create_folder_places_it_after_common(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch("settings.store.MAIN_DIRECTORY", str(Path(temp_dir))):
                folder_key = create_preset_folder(PRESETS_SCOPE_WINWS2, "Моя папка")
                state = load_preset_folder_state(PRESETS_SCOPE_WINWS2)

        ordered_names = [
            folder["name"]
            for _key, folder in sorted(state["folders"].items(), key=lambda pair: pair[1]["order"])
        ]
        self.assertEqual(folder_key, "моя-папка")
        self.assertEqual(ordered_names, ["ALL TCP & UDP", "Общие", "Моя папка", "1.9.9", "Game filter", "Circular"])

    def test_delete_folder_moves_presets_to_common(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch("settings.store.MAIN_DIRECTORY", str(Path(temp_dir))):
                folder_key = create_preset_folder(PRESETS_SCOPE_WINWS2, "Моя папка")
                from presets.folders import move_preset_to_folder

                self.assertTrue(move_preset_to_folder(PRESETS_SCOPE_WINWS2, "Custom.txt", folder_key))
                self.assertTrue(delete_preset_folder(PRESETS_SCOPE_WINWS2, folder_key))
                state = load_preset_folder_state(PRESETS_SCOPE_WINWS2)

        self.assertNotIn(folder_key, state["folders"])
        self.assertEqual(state["items"]["Custom.txt"]["folder_key"], COMMON_FOLDER_KEY)

    def test_system_folder_cannot_be_renamed_but_can_move(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch("settings.store.MAIN_DIRECTORY", str(Path(temp_dir))):
                self.assertFalse(rename_preset_folder(PRESETS_SCOPE_WINWS2, COMMON_FOLDER_KEY, "Другая"))
                self.assertTrue(move_preset_folder_by_step(PRESETS_SCOPE_WINWS2, COMMON_FOLDER_KEY, 1))
                state = load_preset_folder_state(PRESETS_SCOPE_WINWS2)

        ordered_names = [
            folder["name"]
            for _key, folder in sorted(state["folders"].items(), key=lambda pair: pair[1]["order"])
        ]
        self.assertEqual(ordered_names[:2], ["ALL TCP & UDP", "1.9.9"])
        self.assertIn("Общие", ordered_names)

    def test_duplicate_preset_folder_rename_skips_folder_state_save(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch("settings.store.MAIN_DIRECTORY", str(Path(temp_dir))):
                folder_key = create_preset_folder(PRESETS_SCOPE_WINWS2, "Моя папка")
                with patch(
                    "presets.folders.save_preset_folder_state",
                    side_effect=AssertionError("unchanged preset folder name must not be saved"),
                ):
                    self.assertFalse(rename_preset_folder(PRESETS_SCOPE_WINWS2, folder_key, "Моя   папка"))

    def test_rating_and_pin_are_stored_in_folders_items(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch("settings.store.MAIN_DIRECTORY", str(Path(temp_dir))):
                self.assertTrue(set_preset_rating(PRESETS_SCOPE_WINWS2, "ALL TCP & UDP v3.txt", 8))
                self.assertTrue(toggle_preset_pin(PRESETS_SCOPE_WINWS2, "ALL TCP & UDP v3.txt"))
                meta = get_preset_item_meta(PRESETS_SCOPE_WINWS2, "ALL TCP & UDP v3.txt")

        self.assertEqual(meta["folder_key"], "all-tcp-udp")
        self.assertEqual(meta["rating"], 8)
        self.assertTrue(meta["pinned"])

    def test_duplicate_rating_and_pin_skip_folder_state_save(self) -> None:
        from presets.folders import set_preset_pin

        with TemporaryDirectory() as temp_dir:
            with patch("settings.store.MAIN_DIRECTORY", str(Path(temp_dir))):
                self.assertTrue(set_preset_rating(PRESETS_SCOPE_WINWS2, "ALL TCP & UDP v3.txt", 8))
                self.assertTrue(set_preset_pin(PRESETS_SCOPE_WINWS2, "ALL TCP & UDP v3.txt", True))
                with patch(
                    "presets.folders.save_preset_folder_state",
                    side_effect=AssertionError("unchanged preset item metadata must not be saved"),
                ):
                    self.assertFalse(set_preset_rating(PRESETS_SCOPE_WINWS2, "ALL TCP & UDP v3.txt", 8))
                    self.assertFalse(set_preset_pin(PRESETS_SCOPE_WINWS2, "ALL TCP & UDP v3.txt", True))

    def test_duplicate_pinned_folder_collapsed_skips_folder_state_save(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch("settings.store.MAIN_DIRECTORY", str(Path(temp_dir))):
                self.assertTrue(set_preset_folder_collapsed(PRESETS_SCOPE_WINWS2, PINNED_FOLDER_KEY, True))
                with patch(
                    "presets.folders.save_preset_folder_state",
                    side_effect=AssertionError("unchanged pinned folder collapsed state must not be saved"),
                ):
                    self.assertFalse(set_preset_folder_collapsed(PRESETS_SCOPE_WINWS2, PINNED_FOLDER_KEY, True))

    def test_rating_action_preserves_display_default_folder(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch("settings.store.MAIN_DIRECTORY", str(Path(temp_dir))):
                self.assertTrue(
                    set_preset_rating(
                        PRESETS_SCOPE_WINWS2,
                        "custom-name.txt",
                        6,
                        display_name="Preset X Game filter",
                    )
                )
                self.assertTrue(
                    toggle_preset_pin(
                        PRESETS_SCOPE_WINWS2,
                        "another-custom-name.txt",
                        display_name="ALL TCP & UDP v3",
                    )
                )
                rated_meta = get_preset_item_meta(PRESETS_SCOPE_WINWS2, "custom-name.txt")
                pinned_meta = get_preset_item_meta(PRESETS_SCOPE_WINWS2, "another-custom-name.txt")

        self.assertEqual(rated_meta["folder_key"], "game-filter")
        self.assertEqual(pinned_meta["folder_key"], "all-tcp-udp")

    def test_rename_copy_and_delete_update_folder_item_meta(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch("settings.store.MAIN_DIRECTORY", str(Path(temp_dir))):
                folder_key = create_preset_folder(PRESETS_SCOPE_WINWS2, "Моя папка")
                from presets.folders import move_preset_to_folder

                self.assertTrue(move_preset_to_folder(PRESETS_SCOPE_WINWS2, "Source.txt", folder_key))
                self.assertTrue(set_preset_rating(PRESETS_SCOPE_WINWS2, "Source.txt", 7))
                self.assertTrue(toggle_preset_pin(PRESETS_SCOPE_WINWS2, "Source.txt"))

                self.assertTrue(rename_preset_item_meta(PRESETS_SCOPE_WINWS2, "Source.txt", "Renamed.txt"))
                self.assertEqual(get_preset_item_meta(PRESETS_SCOPE_WINWS2, "Renamed.txt")["folder_key"], folder_key)
                self.assertEqual(get_preset_item_meta(PRESETS_SCOPE_WINWS2, "Source.txt")["rating"], 0)

                self.assertTrue(copy_preset_item_meta(PRESETS_SCOPE_WINWS2, "Renamed.txt", "Copy.txt"))
                copy_meta = get_preset_item_meta(PRESETS_SCOPE_WINWS2, "Copy.txt")
                self.assertEqual(copy_meta["folder_key"], folder_key)
                self.assertEqual(copy_meta["rating"], 0)
                self.assertFalse(copy_meta.get("pinned", False))

                self.assertTrue(delete_preset_item_meta(PRESETS_SCOPE_WINWS2, "Renamed.txt"))
                self.assertEqual(get_preset_item_meta(PRESETS_SCOPE_WINWS2, "Renamed.txt")["rating"], 0)

    def test_move_preset_by_step_uses_folder_rows(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch("settings.store.MAIN_DIRECTORY", str(Path(temp_dir))):
                folder_key = create_preset_folder(PRESETS_SCOPE_WINWS2, "Моя папка")
                from presets.folders import move_preset_to_folder

                self.assertTrue(move_preset_to_folder(PRESETS_SCOPE_WINWS2, "A.txt", COMMON_FOLDER_KEY))
                self.assertTrue(move_preset_to_folder(PRESETS_SCOPE_WINWS2, "B.txt", folder_key))
                self.assertTrue(move_preset_to_folder(PRESETS_SCOPE_WINWS2, "C.txt", folder_key))

                moved = move_preset_by_step(
                    PRESETS_SCOPE_WINWS2,
                    "A.txt",
                    1,
                    live_items=[
                        {"key": "A.txt", "name": "A"},
                        {"key": "B.txt", "name": "B"},
                        {"key": "C.txt", "name": "C"},
                    ],
                )
                state = load_preset_folder_state(PRESETS_SCOPE_WINWS2)

        self.assertTrue(moved)
        self.assertEqual(state["items"]["A.txt"]["folder_key"], folder_key)
        self.assertEqual(state["items"]["A.txt"]["order"], 1)

    def test_move_preset_after_matches_lower_drop_marker(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch("settings.store.MAIN_DIRECTORY", str(Path(temp_dir))):
                from presets.folders import move_preset_to_folder

                self.assertTrue(move_preset_to_folder(PRESETS_SCOPE_WINWS2, "A.txt", COMMON_FOLDER_KEY))
                self.assertTrue(move_preset_to_folder(PRESETS_SCOPE_WINWS2, "B.txt", COMMON_FOLDER_KEY))
                self.assertTrue(move_preset_to_folder(PRESETS_SCOPE_WINWS2, "C.txt", COMMON_FOLDER_KEY))
                self.assertTrue(move_preset_after(PRESETS_SCOPE_WINWS2, "A.txt", "B.txt"))
                state = load_preset_folder_state(PRESETS_SCOPE_WINWS2)

        self.assertEqual(state["items"]["B.txt"]["order"], 0)
        self.assertEqual(state["items"]["A.txt"]["order"], 1)
        self.assertEqual(state["items"]["C.txt"]["order"], 2)

    def test_duplicate_move_preset_after_skips_folder_state_save(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch("settings.store.MAIN_DIRECTORY", str(Path(temp_dir))):
                from presets.folders import move_preset_to_folder

                self.assertTrue(move_preset_to_folder(PRESETS_SCOPE_WINWS2, "A.txt", COMMON_FOLDER_KEY))
                self.assertTrue(move_preset_to_folder(PRESETS_SCOPE_WINWS2, "B.txt", COMMON_FOLDER_KEY))
                self.assertTrue(move_preset_to_folder(PRESETS_SCOPE_WINWS2, "C.txt", COMMON_FOLDER_KEY))
                self.assertTrue(move_preset_after(PRESETS_SCOPE_WINWS2, "A.txt", "B.txt"))
                with patch(
                    "presets.folders.save_preset_folder_state",
                    side_effect=AssertionError("unchanged preset folder order must not be saved"),
                ):
                    self.assertFalse(move_preset_after(PRESETS_SCOPE_WINWS2, "A.txt", "B.txt"))

    def test_move_preset_after_uses_visible_destination_folder(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch("settings.store.MAIN_DIRECTORY", str(Path(temp_dir))):
                from presets.folders import move_preset_to_folder

                self.assertTrue(move_preset_to_folder(PRESETS_SCOPE_WINWS2, "A.txt", COMMON_FOLDER_KEY))
                self.assertTrue(move_preset_to_folder(PRESETS_SCOPE_WINWS2, "C.txt", COMMON_FOLDER_KEY))
                self.assertTrue(
                    move_preset_after(
                        PRESETS_SCOPE_WINWS2,
                        "A.txt",
                        "B.txt",
                        destination_folder_key="game-filter",
                    )
                )
                state = load_preset_folder_state(PRESETS_SCOPE_WINWS2)

        self.assertEqual(state["items"]["B.txt"]["folder_key"], "game-filter")
        self.assertEqual(state["items"]["A.txt"]["folder_key"], "game-filter")
        self.assertEqual(state["items"]["B.txt"]["order"], 0)
        self.assertEqual(state["items"]["A.txt"]["order"], 1)
        self.assertEqual(state["items"]["C.txt"]["folder_key"], COMMON_FOLDER_KEY)

    def test_move_preset_before_uses_visible_destination_folder(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch("settings.store.MAIN_DIRECTORY", str(Path(temp_dir))):
                from presets.folders import move_preset_to_folder

                self.assertTrue(move_preset_to_folder(PRESETS_SCOPE_WINWS2, "A.txt", COMMON_FOLDER_KEY))
                self.assertTrue(move_preset_to_folder(PRESETS_SCOPE_WINWS2, "C.txt", COMMON_FOLDER_KEY))
                self.assertTrue(
                    move_preset_before(
                        PRESETS_SCOPE_WINWS2,
                        "A.txt",
                        "B.txt",
                        destination_folder_key="game-filter",
                    )
                )
                state = load_preset_folder_state(PRESETS_SCOPE_WINWS2)

        self.assertEqual(state["items"]["A.txt"]["folder_key"], "game-filter")
        self.assertEqual(state["items"]["B.txt"]["folder_key"], "game-filter")
        self.assertEqual(state["items"]["A.txt"]["order"], 0)
        self.assertEqual(state["items"]["B.txt"]["order"], 1)
        self.assertEqual(state["items"]["C.txt"]["folder_key"], COMMON_FOLDER_KEY)


if __name__ == "__main__":
    unittest.main()
