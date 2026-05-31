from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from folders.defaults import COMMON_FOLDER_KEY
from profile.folders import (
    create_profile_folder,
    delete_profile_folder,
    load_profile_folder_state,
    move_profile_before_in_folder_state,
    move_profile_after_in_folder_state,
    move_profile_folder_by_step,
    move_profile_to_end_in_folder_state,
    move_profile_to_folder_in_folder_state,
    rename_profile_folder,
    reset_profile_folders,
    set_profile_folder,
    set_profile_folder_collapsed,
    set_profile_folder_order,
    save_profile_folder_state,
)


class ProfileFolderActionTests(unittest.TestCase):
    def test_create_profile_folder_places_it_after_common(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch("settings.store.MAIN_DIRECTORY", str(Path(temp_dir))):
                folder_key = create_profile_folder("Моя папка")
                state = load_profile_folder_state()

        ordered_names = [
            folder["name"]
            for _key, folder in sorted(state["folders"].items(), key=lambda pair: pair[1]["order"])
        ]
        self.assertEqual(folder_key, "моя-папка")
        self.assertEqual(ordered_names[-3:], ["Общие", "Моя папка", "Все сайты"])

    def test_delete_profile_folder_moves_profiles_to_common(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch("settings.store.MAIN_DIRECTORY", str(Path(temp_dir))):
                folder_key = create_profile_folder("Моя папка")
                state = load_profile_folder_state()
                state["items"]["youtube.com (интерфейс)"] = {"folder_key": folder_key, "order": 0, "rating": 0}
                save_profile_folder_state(state)

                self.assertTrue(delete_profile_folder(folder_key))
                state = load_profile_folder_state()

        self.assertNotIn(folder_key, state["folders"])
        self.assertEqual(state["items"]["youtube.com (интерфейс)"]["folder_key"], COMMON_FOLDER_KEY)

    def test_common_profile_folder_cannot_be_renamed_but_can_move(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch("settings.store.MAIN_DIRECTORY", str(Path(temp_dir))):
                self.assertFalse(rename_profile_folder(COMMON_FOLDER_KEY, "Другая"))
                self.assertTrue(move_profile_folder_by_step(COMMON_FOLDER_KEY, -1))
                state = load_profile_folder_state()

        ordered_names = [
            folder["name"]
            for _key, folder in sorted(state["folders"].items(), key=lambda pair: pair[1]["order"])
        ]
        self.assertIn("Общие", ordered_names)
        self.assertLess(ordered_names.index("Общие"), ordered_names.index("ZapretKVN"))

    def test_duplicate_profile_folder_rename_skips_folder_state_save(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch("settings.store.MAIN_DIRECTORY", str(Path(temp_dir))):
                folder_key = create_profile_folder("Моя папка")
                with patch(
                    "profile.folders.save_profile_folder_state",
                    side_effect=AssertionError("unchanged profile folder name must not be saved"),
                ):
                    self.assertFalse(rename_profile_folder(folder_key, "Моя   папка"))

    def test_profile_folder_collapsed_and_reset_are_saved_in_settings(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch("settings.store.MAIN_DIRECTORY", str(Path(temp_dir))):
                self.assertTrue(set_profile_folder_collapsed("youtube", True))
                state = load_profile_folder_state()
                self.assertTrue(state["folders"]["youtube"]["collapsed"])

                reset_profile_folders()
                state = load_profile_folder_state()

        self.assertFalse(state["folders"]["youtube"]["collapsed"])

    def test_duplicate_profile_folder_reset_skips_folder_state_save(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch("settings.store.MAIN_DIRECTORY", str(Path(temp_dir))):
                load_profile_folder_state()
                with patch(
                    "profile.folders.save_profile_folder_state",
                    side_effect=AssertionError("unchanged profile folder reset must not be saved"),
                ):
                    self.assertFalse(reset_profile_folders())

    def test_save_profile_folder_state_skips_settings_write_when_state_is_unchanged(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch("settings.store.MAIN_DIRECTORY", str(Path(temp_dir))):
                state = load_profile_folder_state()
                with patch(
                    "profile.folders.settings_store.set_folders_settings",
                    side_effect=AssertionError("unchanged profile folder state must not write settings"),
                ):
                    self.assertEqual(save_profile_folder_state(state), state)

    def test_profile_folder_collapsed_skips_save_when_state_is_unchanged(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch("settings.store.MAIN_DIRECTORY", str(Path(temp_dir))):
                self.assertTrue(set_profile_folder_collapsed("youtube", True))
                with patch(
                    "profile.folders.save_profile_folder_state",
                    side_effect=AssertionError("unchanged folder collapsed state must not be saved"),
                ):
                    self.assertFalse(set_profile_folder_collapsed("youtube", True))

    def test_duplicate_profile_folder_item_metadata_skips_save(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch("settings.store.MAIN_DIRECTORY", str(Path(temp_dir))):
                self.assertTrue(set_profile_folder("profile-a", "youtube"))
                set_profile_folder_order("profile-a", 3)
                with patch(
                    "profile.folders.save_profile_folder_state",
                    side_effect=AssertionError("unchanged profile item metadata must not be saved"),
                ):
                    self.assertFalse(set_profile_folder("profile-a", "youtube"))
                    self.assertFalse(set_profile_folder_order("profile-a", 3))

    def test_profile_reorder_saves_folder_state_once(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch("settings.store.MAIN_DIRECTORY", str(Path(temp_dir))):
                state = load_profile_folder_state()
                for index, key in enumerate(("a", "b", "c", "d")):
                    state["items"][key] = {"folder_key": COMMON_FOLDER_KEY, "order": index, "rating": 0}
                save_profile_folder_state(state)

                save_calls = 0
                original_save = save_profile_folder_state

                def _counting_save(next_state):
                    nonlocal save_calls
                    save_calls += 1
                    return original_save(next_state)

                with patch("profile.folders.save_profile_folder_state", side_effect=_counting_save):
                    move_profile_before_in_folder_state("d", "a", ["a", "b", "c", "d"])

        self.assertEqual(save_calls, 1)

    def test_profile_move_after_matches_lower_drop_marker(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch("settings.store.MAIN_DIRECTORY", str(Path(temp_dir))):
                state = load_profile_folder_state()
                for index, key in enumerate(("a", "b", "c")):
                    state["items"][key] = {"folder_key": COMMON_FOLDER_KEY, "order": index, "rating": 0}
                save_profile_folder_state(state)

                move_profile_after_in_folder_state("a", "b", ["a", "b", "c"])
                state = load_profile_folder_state()

        self.assertEqual(state["items"]["b"]["order"], 0)
        self.assertEqual(state["items"]["a"]["order"], 1)
        self.assertEqual(state["items"]["c"]["order"], 2)

    def test_duplicate_profile_move_after_skips_folder_state_save(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch("settings.store.MAIN_DIRECTORY", str(Path(temp_dir))):
                state = load_profile_folder_state()
                for index, key in enumerate(("a", "b", "c")):
                    state["items"][key] = {"folder_key": COMMON_FOLDER_KEY, "order": index, "rating": 0}
                save_profile_folder_state(state)

                move_profile_after_in_folder_state("a", "b", ["a", "b", "c"])
                with patch(
                    "profile.folders.save_profile_folder_state",
                    side_effect=AssertionError("unchanged profile folder order must not be saved"),
                ):
                    self.assertFalse(move_profile_after_in_folder_state("a", "b", ["b", "a", "c"]))

    def test_duplicate_profile_move_to_end_skips_folder_state_save(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch("settings.store.MAIN_DIRECTORY", str(Path(temp_dir))):
                state = load_profile_folder_state()
                for index, key in enumerate(("a", "b", "c")):
                    state["items"][key] = {"folder_key": COMMON_FOLDER_KEY, "order": index, "rating": 0}
                save_profile_folder_state(state)

                move_profile_to_end_in_folder_state("a", ["a", "b", "c"])
                with patch(
                    "profile.folders.save_profile_folder_state",
                    side_effect=AssertionError("unchanged profile move-to-end must not be saved"),
                ):
                    self.assertFalse(move_profile_to_end_in_folder_state("a", ["b", "c", "a"]))

    def test_duplicate_profile_move_to_folder_skips_folder_state_save(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch("settings.store.MAIN_DIRECTORY", str(Path(temp_dir))):
                state = load_profile_folder_state()
                state["items"]["a"] = {"folder_key": "youtube", "order": 0, "rating": 0}
                state["items"]["b"] = {"folder_key": "youtube", "order": 1, "rating": 0}
                save_profile_folder_state(state)

                with patch(
                    "profile.folders.save_profile_folder_state",
                    side_effect=AssertionError("unchanged profile move-to-folder must not be saved"),
                ):
                    self.assertFalse(move_profile_to_folder_in_folder_state("b", "youtube", ["a", "b"]))


if __name__ == "__main__":
    unittest.main()
