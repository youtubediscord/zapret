from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from core.paths import AppPaths
from profile.service import ProfilePresetService
from profile.strategy_state import ProfileStrategyState


class _PresetStore:
    def __init__(self, text: str) -> None:
        self.text = text
        self.save_count = 0
        self.content_change_kinds: list[str] = []

    def read_selected_preset_source(self, _launch_method: str):
        return self.text, SimpleNamespace(file_name="selected.txt", name="selected")

    def save_selected_preset_source(self, _launch_method: str, text: str, *, content_change_kind: str = "") -> None:
        self.save_count += 1
        self.content_change_kinds.append(str(content_change_kind or ""))
        self.text = text


class ProfileServiceApplyStrategyGuardTests(unittest.TestCase):
    def test_save_selected_preset_skips_save_when_loaded_preset_is_unchanged(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = _PresetStore(
                "\n".join(
                    (
                        "--name=SpeedTest",
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
            preset, _manifest = service.load_selected_preset()
            service.save_selected_preset(preset)

        self.assertEqual(store.save_count, 0)

    def test_set_profile_enabled_skips_save_when_state_is_unchanged(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = _PresetStore(
                "\n".join(
                    (
                        "--name=SpeedTest",
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
                        "--name=SpeedTest",
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

        # No-op-успех: пара (old, new) persistent_key с old == new;
        # идентичность стабильна — это uid из sidecar-реестра.
        self.assertIsNotNone(result)
        old_key, new_key = result
        self.assertEqual(old_key, new_key)
        self.assertTrue(new_key.startswith("uid:"))
        self.assertEqual(store.save_count, 0)

    def test_update_raw_profile_text_skips_save_when_text_is_unchanged(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            raw_text = "\n".join(
                (
                    "--name=SpeedTest",
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

        # No-op-успех: пара (old, new) persistent_key с old == new;
        # идентичность стабильна — это uid из sidecar-реестра.
        self.assertIsNotNone(result)
        old_key, new_key = result
        self.assertEqual(old_key, new_key)
        self.assertTrue(new_key.startswith("uid:"))
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
                        "--name=SpeedTest",
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
                        "profile.service.save_profile_folder_state",
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

    def test_move_profile_before_skips_folder_write_when_profile_is_already_before_target(self) -> None:
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
                youtube_items = [item for item in payload.items if item.group == "youtube"]
                source, destination = youtube_items[0], youtube_items[1]
                with (
                    patch(
                        "profile.service.save_profile_folder_state",
                        side_effect=AssertionError("already-ordered profile must not rewrite folder state"),
                    ),
                    patch.object(
                        service,
                        "_invalidate_profile_list_snapshot",
                        side_effect=AssertionError("already-ordered profile must not invalidate list cache"),
                    ),
                ):
                    moved = service.move_profile_before(source.key, destination.key)

        self.assertEqual(moved, source.key)

    def test_move_profile_after_skips_folder_write_when_profile_is_already_after_target(self) -> None:
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
                youtube_items = [item for item in payload.items if item.group == "youtube"]
                destination, source = youtube_items[0], youtube_items[1]
                with (
                    patch(
                        "profile.service.save_profile_folder_state",
                        side_effect=AssertionError("already-ordered profile must not rewrite folder state"),
                    ),
                    patch.object(
                        service,
                        "_invalidate_profile_list_snapshot",
                        side_effect=AssertionError("already-ordered profile must not invalidate list cache"),
                    ),
                ):
                    moved = service.move_profile_after(source.key, destination.key)

        self.assertEqual(moved, source.key)

    def test_set_strategy_state_skips_cache_invalidation_when_state_is_unchanged(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = _PresetStore(
                "\n".join(
                    (
                        "--name=SpeedTest",
                        "--filter-tcp=443,8080",
                        "--hostlist=lists/speedtest.txt",
                        "--lua-desync=fake",
                        "",
                    )
                )
            )
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )
            service = ProfilePresetService(feature, "zapret2_mode")
            service._state_store = SimpleNamespace(
                get_strategy_state=lambda _profile_key, _strategy_id: ProfileStrategyState(rating="work", favorite=True),
                set_strategy_state=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                    AssertionError("unchanged strategy state must not be written")
                ),
            )

            with patch.object(
                service,
                "_invalidate_profile_list_snapshot",
                side_effect=AssertionError("unchanged strategy state must not invalidate list cache"),
            ):
                state = service.set_strategy_state("profile:0", "tls_fake", rating="work", favorite=True)

        self.assertEqual(state, ProfileStrategyState(rating="work", favorite=True))

    def test_clear_strategy_state_skips_cache_invalidation_when_state_is_already_empty(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = _PresetStore(
                "\n".join(
                    (
                        "--name=SpeedTest",
                        "--filter-tcp=443,8080",
                        "--hostlist=lists/speedtest.txt",
                        "--lua-desync=fake",
                        "",
                    )
                )
            )
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )
            service = ProfilePresetService(feature, "zapret2_mode")
            service._state_store = SimpleNamespace(
                get_strategy_state=lambda _profile_key, _strategy_id: ProfileStrategyState(),
                clear_strategy_state=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                    AssertionError("empty strategy state must not be cleared again")
                ),
            )

            with patch.object(
                service,
                "_invalidate_profile_list_snapshot",
                side_effect=AssertionError("empty strategy state must not invalidate list cache"),
            ):
                state = service.set_strategy_state("profile:0", "tls_fake", clear=True)

        self.assertEqual(state, ProfileStrategyState())

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
                        "--name=SpeedTest",
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

        self.assertEqual(result.status, "already_applied")
        self.assertEqual(result.profile_key, "profile:0")
        self.assertEqual(store.save_count, 0)

    def test_apply_strategy_reports_strategy_only_change_contract(self) -> None:
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
                        "--name=SpeedTest",
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

            with patch("settings.store.MAIN_DIRECTORY", str(root)):
                service = ProfilePresetService(feature, "zapret2_mode")
                result = service.apply_strategy("profile:0", "tcp_md5")

        self.assertEqual(result.status, "applied")
        self.assertEqual(result.profile_key, "profile:0")
        self.assertEqual(result.strategy_id, "tcp_md5")
        self.assertEqual(result.change_kind, "strategy_only")
        self.assertFalse(result.list_structure_changed)
        self.assertTrue(result.profile_payload_changed)
        self.assertTrue(result.profile_list_item_changed)
        self.assertTrue(result.summary_changed)
        self.assertTrue(result.runtime_apply_needed)
        self.assertFalse(result.should_reload)
        self.assertEqual(store.save_count, 1)
        self.assertEqual(store.content_change_kinds, ["strategy_only"])

    def test_apply_strategy_already_selected_reports_no_precise_rebuild_needed(self) -> None:
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
                        "--name=SpeedTest",
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

        self.assertEqual(result.status, "already_applied")
        self.assertEqual(result.change_kind, "unchanged")
        self.assertFalse(result.list_structure_changed)
        self.assertFalse(result.profile_payload_changed)
        self.assertFalse(result.profile_list_item_changed)
        self.assertFalse(result.summary_changed)
        self.assertFalse(result.runtime_apply_needed)
        self.assertFalse(result.should_reload)
        self.assertEqual(store.save_count, 0)

    def test_apply_strategy_reports_profile_missing_without_error_result(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = _PresetStore("")
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )

            service = ProfilePresetService(feature, "zapret2_mode")
            result = service.apply_strategy("profile:0", "tcp_md5")

        self.assertEqual(result.status, "profile_missing")
        self.assertEqual(result.profile_key, "")
        self.assertTrue(result.should_reload)
        self.assertEqual(store.save_count, 0)

    def test_apply_strategy_reports_stale_reload_when_requested_branch_disappeared(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            catalogs_dir = root / "profile" / "strategy_catalogs" / "winws2"
            catalogs_dir.mkdir(parents=True)
            (catalogs_dir / "tcp.txt").write_text(
                "\n".join(
                    (
                        "[tls_fake]",
                        "name = TLS fake",
                        "--lua-desync=fake",
                        "",
                    )
                ),
                encoding="utf-8",
            )
            store = _PresetStore(
                "\n".join(
                    (
                        "--name=SpeedTest",
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

            with patch("settings.store.MAIN_DIRECTORY", str(root)):
                service = ProfilePresetService(feature, "zapret2_mode")
                result = service.apply_strategy("profile:0", "tls_fake", strategy_branch_id="branch:9")

        self.assertEqual(result.status, "stale_reloaded")
        self.assertEqual(result.profile_key, "profile:0")
        self.assertTrue(result.should_reload)
        self.assertEqual(store.save_count, 0)


if __name__ == "__main__":
    unittest.main()
