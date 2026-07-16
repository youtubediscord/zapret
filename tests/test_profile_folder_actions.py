from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from folders.defaults import COMMON_FOLDER_KEY
from folders.ordering import plan_item_move
from profile.folders import (
    create_profile_folder,
    delete_profile_folder,
    load_profile_folder_state,
    move_profile_folder_by_step,
    rename_profile_folder,
    reset_profile_folders,
    set_profile_folder,
    set_profile_folder_collapsed,
    set_profile_folders_collapsed,
    set_profile_folder_order,
    save_profile_folder_state,
)


def _live_items(*keys: str) -> list[dict]:
    return [{"key": key, "name": key} for key in keys]


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

    def test_profile_folder_reset_always_returns_fresh_state_without_redundant_write(self) -> None:
        # Reset всегда возвращает свежее состояние (UI обязан перерисоваться),
        # но фактическая запись settings при неизменном состоянии не происходит.
        with TemporaryDirectory() as temp_dir:
            with patch("settings.store.MAIN_DIRECTORY", str(Path(temp_dir))):
                load_profile_folder_state()
                with patch(
                    "profile.folders.settings_store.set_folders_settings",
                    side_effect=AssertionError("unchanged profile folder state must not write settings"),
                ):
                    state = reset_profile_folders()
        self.assertIsInstance(state, dict)
        self.assertIn("youtube", state["folders"])

    def test_profile_folder_reset_materializes_assignments(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch("settings.store.MAIN_DIRECTORY", str(Path(temp_dir))):
                folder_key = create_profile_folder("Моя папка")
                state = load_profile_folder_state()
                state["items"]["uid:manual"] = {"folder_key": folder_key, "order": 3, "rating": 0}
                save_profile_folder_state(state)

                state = reset_profile_folders({"uid:manual": "discord", "uid:unknown-folder": "no-such"})

        self.assertNotIn(folder_key, state["folders"])
        self.assertEqual(state["items"]["uid:manual"]["folder_key"], "discord")
        self.assertIsNone(state["items"]["uid:manual"]["order"])
        self.assertEqual(state["items"]["uid:unknown-folder"]["folder_key"], COMMON_FOLDER_KEY)

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

    def test_profile_folders_collapsed_batch_saves_settings_once(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch("settings.store.MAIN_DIRECTORY", str(Path(temp_dir))):
                calls = []
                original_save = save_profile_folder_state

                def wrapped_save(state):
                    calls.append(state)
                    return original_save(state)

                with patch("profile.folders.save_profile_folder_state", side_effect=wrapped_save):
                    self.assertTrue(set_profile_folders_collapsed({"youtube": True, "discord": True}))

                state = load_profile_folder_state()

        self.assertEqual(len(calls), 1)
        self.assertTrue(state["folders"]["youtube"]["collapsed"])
        self.assertTrue(state["folders"]["discord"]["collapsed"])

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

    def test_profile_reorder_renumbers_folder_from_display_order(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch("settings.store.MAIN_DIRECTORY", str(Path(temp_dir))):
                state = load_profile_folder_state()
                for index, key in enumerate(("a", "b", "c", "d")):
                    state["items"][key] = {"folder_key": COMMON_FOLDER_KEY, "order": index, "rating": 0}
                save_profile_folder_state(state)

                planned = plan_item_move(
                    load_profile_folder_state(),
                    _live_items("a", "b", "c", "d"),
                    action="before",
                    source_key="d",
                    destination_key="a",
                )
                self.assertIsNotNone(planned)
                save_profile_folder_state(planned)
                state = load_profile_folder_state()

        self.assertEqual(state["items"]["d"]["order"], 0)
        self.assertEqual(state["items"]["a"]["order"], 1)
        self.assertEqual(state["items"]["b"]["order"], 2)
        self.assertEqual(state["items"]["c"]["order"], 3)

    def test_profile_move_after_matches_lower_drop_marker(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch("settings.store.MAIN_DIRECTORY", str(Path(temp_dir))):
                state = load_profile_folder_state()
                for index, key in enumerate(("a", "b", "c")):
                    state["items"][key] = {"folder_key": COMMON_FOLDER_KEY, "order": index, "rating": 0}
                save_profile_folder_state(state)

                planned = plan_item_move(
                    load_profile_folder_state(),
                    _live_items("a", "b", "c"),
                    action="after",
                    source_key="a",
                    destination_key="b",
                )
                self.assertIsNotNone(planned)
                save_profile_folder_state(planned)
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

                first = plan_item_move(
                    load_profile_folder_state(),
                    _live_items("a", "b", "c"),
                    action="after",
                    source_key="a",
                    destination_key="b",
                )
                self.assertIsNotNone(first)
                save_profile_folder_state(first)
                # Повторное «a после b» уже не меняет отображаемый порядок — no-op.
                self.assertIsNone(
                    plan_item_move(
                        load_profile_folder_state(),
                        _live_items("a", "b", "c"),
                        action="after",
                        source_key="a",
                        destination_key="b",
                    )
                )

    def test_duplicate_profile_move_to_end_skips_folder_state_save(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch("settings.store.MAIN_DIRECTORY", str(Path(temp_dir))):
                state = load_profile_folder_state()
                for index, key in enumerate(("a", "b", "c")):
                    state["items"][key] = {"folder_key": COMMON_FOLDER_KEY, "order": index, "rating": 0}
                save_profile_folder_state(state)

                first = plan_item_move(
                    load_profile_folder_state(),
                    _live_items("a", "b", "c"),
                    action="end",
                    source_key="a",
                )
                self.assertIsNotNone(first)
                save_profile_folder_state(first)
                # Профиль уже в конце папки — повторный move-to-end это no-op.
                self.assertIsNone(
                    plan_item_move(
                        load_profile_folder_state(),
                        _live_items("a", "b", "c"),
                        action="end",
                        source_key="a",
                    )
                )

    def test_duplicate_profile_move_to_folder_skips_folder_state_save(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch("settings.store.MAIN_DIRECTORY", str(Path(temp_dir))):
                state = load_profile_folder_state()
                state["items"]["a"] = {"folder_key": "youtube", "order": 0, "rating": 0}
                state["items"]["b"] = {"folder_key": "youtube", "order": 1, "rating": 0}
                save_profile_folder_state(state)

                # «b» уже последний в youtube — перенос в ту же папку это no-op.
                self.assertIsNone(
                    plan_item_move(
                        load_profile_folder_state(),
                        _live_items("a", "b"),
                        action="folder",
                        source_key="b",
                        destination_folder_key="youtube",
                    )
                )


if __name__ == "__main__":
    unittest.main()
