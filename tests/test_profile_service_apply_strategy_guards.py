from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from core.paths import AppPaths
from profile.service import ProfilePresetService


class _PresetStore:
    def __init__(self, text: str) -> None:
        self.text = text
        self.save_count = 0

    def read_selected_preset_source(self, _launch_method: str):
        return self.text, SimpleNamespace(file_name="selected.txt", name="selected")

    def save_selected_preset_source(self, _launch_method: str, text: str) -> None:
        self.save_count += 1
        self.text = text


class ProfileServiceApplyStrategyGuardTests(unittest.TestCase):
    def test_set_profile_enabled_skips_save_when_state_is_unchanged(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = _PresetStore(
                "\n".join(
                    (
                        "--name=Speedtest",
                        "--filter-tcp=443,8080",
                        "--hostlist=lists/speedtest.txt",
                        "--lua-desync=pass",
                        "",
                    )
                )
            )
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )

            service = ProfilePresetService(feature, "zapret2_mode")
            result = service.set_profile_enabled("profile:0", True)

        self.assertEqual(result, "profile:0")
        self.assertEqual(store.save_count, 0)

    def test_update_editable_settings_skips_save_when_settings_are_unchanged(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = _PresetStore(
                "\n".join(
                    (
                        "--name=Speedtest",
                        "--filter-tcp=443,8080",
                        "--hostlist=lists/speedtest.txt",
                        "--in-range=x",
                        "--out-range=a",
                        "--lua-desync=pass",
                        "",
                    )
                )
            )
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )

            service = ProfilePresetService(feature, "zapret2_mode")
            result = service.update_winws2_editable_settings(
                "profile:0",
                filter_kind="hostlist",
                filter_value="lists/speedtest.txt",
                in_range="x",
                out_range="a",
            )

        self.assertEqual(result, "profile:0")
        self.assertEqual(store.save_count, 0)

    def test_update_raw_profile_text_skips_save_when_text_is_unchanged(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            raw_text = "\n".join(
                (
                    "--name=Speedtest",
                    "--filter-tcp=443,8080",
                    "--hostlist=lists/speedtest.txt",
                    "--lua-desync=pass",
                    "",
                )
            )
            store = _PresetStore(raw_text)
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )

            service = ProfilePresetService(feature, "zapret2_mode")
            result = service.update_profile_raw_text("profile:0", raw_text)

        self.assertEqual(result, "profile:0")
        self.assertEqual(store.save_count, 0)

    def test_save_profile_list_file_text_skips_write_when_user_text_is_unchanged(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lists_dir = root / "lists" / "user"
            lists_dir.mkdir(parents=True)
            (lists_dir / "speedtest.txt").write_text("speedtest.net\n", encoding="utf-8")
            store = _PresetStore(
                "\n".join(
                    (
                        "--name=Speedtest",
                        "--filter-tcp=443,8080",
                        "--hostlist=lists/speedtest.txt",
                        "--lua-desync=pass",
                        "",
                    )
                )
            )
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )

            service = ProfilePresetService(feature, "zapret2_mode")
            with patch(
                "profile.service.write_profile_list_file_text",
                side_effect=AssertionError("unchanged list text must not be written"),
            ):
                state = service.save_profile_list_file_text("profile:0", "speedtest.net\n")

        self.assertIsNotNone(state)
        self.assertEqual(state.user_text, "speedtest.net\n")

    def test_move_profile_to_end_skips_folder_write_when_profile_is_already_last(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            templates_dir = root / "profile" / "templates"
            templates_dir.mkdir(parents=True)
            (templates_dir / "all_profiles.txt").write_text("", encoding="utf-8")
            store = _PresetStore(
                "\n".join(
                    (
                        "--name=YouTube",
                        "--filter-tcp=80,443",
                        "--hostlist=lists/youtube.txt",
                        "",
                        "--new",
                        "",
                        "--name=Googlevideo",
                        "--filter-tcp=80,443",
                        "--hostlist=lists/googlevideo.txt",
                        "",
                    )
                )
            )
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )

            with patch("settings.store.MAIN_DIRECTORY", str(root)):
                service = ProfilePresetService(feature, "zapret2_mode")
                payload = service.list_profiles()
                googlevideo = next(item for item in payload.items if "googlevideo" in " ".join(item.match_lines).lower())
                with (
                    patch(
                        "profile.service.move_profile_to_end_in_folder_state",
                        side_effect=AssertionError("already-last profile must not rewrite folder state"),
                    ),
                    patch.object(
                        service,
                        "_invalidate_profile_list_snapshot",
                        side_effect=AssertionError("already-last profile must not invalidate list cache"),
                    ),
                ):
                    moved = service.move_profile_to_end(googlevideo.key)

        self.assertEqual(moved, googlevideo.key)

    def test_apply_strategy_skips_save_when_profile_already_uses_strategy(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            catalogs_dir = root / "profile" / "strategy_catalogs" / "winws2"
            catalogs_dir.mkdir(parents=True)
            (catalogs_dir / "tcp.txt").write_text(
                "\n".join(
                    (
                        "[tcp_md5]",
                        "name = TCP MD5",
                        "--lua-desync=multidisorder:pos=4:repeats=10:tcp_md5",
                        "",
                    )
                ),
                encoding="utf-8",
            )
            store = _PresetStore(
                "\n".join(
                    (
                        "--name=Speedtest",
                        "--filter-tcp=443,8080",
                        "--hostlist=lists/speedtest.txt",
                        "--lua-desync=multidisorder:pos=4:repeats=10:tcp_md5",
                        "",
                    )
                )
            )
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )

            with patch("settings.store.MAIN_DIRECTORY", str(root)):
                service = ProfilePresetService(feature, "zapret2_mode")
                result = service.apply_strategy("profile:0", "tcp_md5")

        self.assertEqual(result, "profile:0")
        self.assertEqual(store.save_count, 0)


if __name__ == "__main__":
    unittest.main()
