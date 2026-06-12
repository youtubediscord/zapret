from __future__ import annotations

import os
import threading
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from core.paths import AppPaths
from profile.list_view_state import ordered_group_keys
from profile.strategy_state import ProfileStrategyState
from profile.service import ProfilePresetService


class _PresetStore:
    def __init__(self, text: str) -> None:
        self.text = text

    def read_selected_preset_source(self, _launch_method: str):
        return self.text, SimpleNamespace(file_name="selected.txt", name="selected")

    def save_selected_preset_source(self, _launch_method: str, text: str) -> None:
        self.text = text


class _FileBackedPresetStore:
    def __init__(self, preset_path: Path, text: str) -> None:
        self.preset_path = preset_path
        self.preset_path.write_text(text, encoding="utf-8")
        self.read_count = 0

    def get_selected_source_preset_manifest(self, _launch_method: str):
        return SimpleNamespace(file_name=self.preset_path.name, name=self.preset_path.stem)

    def get_selected_source_path(self, _launch_method: str) -> Path:
        return self.preset_path

    def read_selected_preset_source(self, _launch_method: str):
        self.read_count += 1
        return self.preset_path.read_text(encoding="utf-8"), self.get_selected_source_preset_manifest(_launch_method)

    def save_selected_preset_source(self, _launch_method: str, text: str) -> None:
        self.preset_path.write_text(text, encoding="utf-8")


class _SwitchableFileBackedPresetStore:
    def __init__(self, root: Path, files: dict[str, str], selected: str) -> None:
        self.root = root
        self.files = dict(files)
        self.selected = selected
        self.read_count_by_file: dict[str, int] = {}
        for file_name, text in self.files.items():
            (self.root / file_name).write_text(text, encoding="utf-8")

    def get_selected_source_preset_manifest(self, _launch_method: str):
        return SimpleNamespace(file_name=self.selected, name=Path(self.selected).stem)

    def get_selected_source_path(self, _launch_method: str) -> Path:
        return self.root / self.selected

    def read_selected_preset_source(self, launch_method: str):
        manifest = self.get_selected_source_preset_manifest(launch_method)
        file_name = str(getattr(manifest, "file_name", "") or "")
        self.read_count_by_file[file_name] = self.read_count_by_file.get(file_name, 0) + 1
        return (self.root / file_name).read_text(encoding="utf-8"), manifest

    def save_selected_preset_source(self, _launch_method: str, text: str) -> None:
        (self.root / self.selected).write_text(text, encoding="utf-8")


class _BlockingFileBackedPresetStore(_FileBackedPresetStore):
    def __init__(self, preset_path: Path, text: str) -> None:
        super().__init__(preset_path, text)
        self.first_read_started = threading.Event()
        self.release_first_read = threading.Event()

    def read_selected_preset_source(self, launch_method: str):
        self.read_count += 1
        if self.read_count == 1:
            self.first_read_started.set()
            self.release_first_read.wait(timeout=2)
        return self.preset_path.read_text(encoding="utf-8"), self.get_selected_source_preset_manifest(launch_method)


class ProfileListPayloadTests(unittest.TestCase):
    def test_profile_folder_order_keeps_zero_order_first(self) -> None:
        grouped = {
            "discord": [object()],
            "youtube": [object()],
            "messengers": [object()],
        }

        self.assertEqual(ordered_group_keys(grouped), ["youtube", "discord", "messengers"])

    def test_list_profiles_keeps_catalog_rows_but_collapses_hostlist_ipset_variants(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lists_dir = root / "lists"
            lists_dir.mkdir()
            (lists_dir / "youtube.txt").write_text("youtube.com\n", encoding="utf-8")
            (lists_dir / "ipset-youtube.txt").write_text("1.1.1.1\n", encoding="utf-8")
            templates_dir = root / "profile" / "templates"
            templates_dir.mkdir(parents=True)
            (templates_dir / "all_profiles.txt").write_text(
                "\n".join(
                    (
                        "--filter-tcp=80,443",
                        "--hostlist=lists/youtube.txt",
                        "",
                        "--new",
                        "--filter-tcp=80,443",
                        "--ipset=lists/ipset-youtube.txt",
                        "",
                        "--new",
                        "--filter-udp=443",
                        "--ipset=lists/ipset-discord.txt",
                        "",
                    )
                ),
                encoding="utf-8",
            )

            store = _PresetStore(
                "\n".join(
                    (
                        "--filter-tcp=80,443",
                        "--hostlist=lists/youtube.txt",
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
                payload = ProfilePresetService(feature, "zapret2_mode").list_profiles()

        self.assertEqual(len(payload.items), 2)
        youtube = next(item for item in payload.items if "youtube" in " ".join(item.match_lines).lower())
        discord = next(item for item in payload.items if "discord" in " ".join(item.match_lines).lower())
        self.assertTrue(youtube.in_preset)
        self.assertEqual(youtube.list_type, "hostlist")
        self.assertIn("--hostlist=lists/youtube.txt", youtube.match_lines)
        self.assertFalse(discord.in_preset)
        self.assertTrue(discord.key.startswith("template:"))

    def test_list_profiles_normalizes_multi_list_profile_and_saves_preset(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lists_dir = root / "lists"
            lists_dir.mkdir()
            (lists_dir / "youtube.txt").write_text("youtube.com\n", encoding="utf-8")
            (lists_dir / "ipset-youtube.txt").write_text("1.1.1.1\n", encoding="utf-8")
            templates_dir = root / "profile" / "templates"
            templates_dir.mkdir(parents=True)
            (templates_dir / "all_profiles.txt").write_text("", encoding="utf-8")
            store = _PresetStore(
                "\n".join(
                    (
                        "--filter-tcp=80,443",
                        "--hostlist=lists/discord.txt",
                        "--hostlist=lists/other.txt",
                        "--hostlist-exclude=lists/list-exclude.txt",
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
                payload = ProfilePresetService(feature, "zapret2_mode").list_profiles()

        self.assertEqual(payload.normalized_split_profiles, 1)
        self.assertEqual(payload.normalized_created_profiles, 1)
        self.assertEqual(len(payload.items), 2)
        self.assertIn("--new", store.text)
        self.assertIn("--hostlist=lists/discord.txt", store.text)
        self.assertIn("--hostlist=lists/other.txt", store.text)
        self.assertNotIn("--hostlist-exclude=lists/list-exclude.txt", store.text)

    def test_selected_preset_snapshot_reuses_parsed_preset_for_summary_calls(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lists_dir = root / "lists"
            lists_dir.mkdir()
            (lists_dir / "youtube.txt").write_text("youtube.com\n", encoding="utf-8")
            templates_dir = root / "profile" / "templates"
            templates_dir.mkdir(parents=True)
            (templates_dir / "all_profiles.txt").write_text("", encoding="utf-8")
            store = _FileBackedPresetStore(
                root / "selected.txt",
                "\n".join(
                    (
                        "--filter-tcp=80,443",
                        "--hostlist=lists/youtube.txt",
                        "--lua-desync=pass",
                        "",
                    )
                ),
            )
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )

            with patch("settings.store.MAIN_DIRECTORY", str(root)):
                service = ProfilePresetService(feature, "zapret2_mode")
                service.list_profiles()
                enabled_count = service.count_enabled_profiles()
                display_state = service.get_profile_strategy_display_state()

        self.assertEqual(enabled_count, 1)
        self.assertEqual(display_state.active_count, 1)
        self.assertEqual(store.read_count, 1)

    def test_list_profiles_serializes_concurrent_snapshot_builds(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lists_dir = root / "lists"
            lists_dir.mkdir()
            (lists_dir / "youtube.txt").write_text("youtube.com\n", encoding="utf-8")
            templates_dir = root / "profile" / "templates"
            templates_dir.mkdir(parents=True)
            (templates_dir / "all_profiles.txt").write_text("", encoding="utf-8")
            store = _BlockingFileBackedPresetStore(
                root / "selected.txt",
                "\n".join(
                    (
                        "--filter-tcp=80,443",
                        "--hostlist=lists/youtube.txt",
                        "--lua-desync=pass",
                        "",
                    )
                ),
            )
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )

            with patch("settings.store.MAIN_DIRECTORY", str(root)):
                service = ProfilePresetService(feature, "zapret2_mode")
                results: list[object] = []
                errors: list[BaseException] = []

                def load_profiles() -> None:
                    try:
                        results.append(service.list_profiles())
                    except BaseException as exc:
                        errors.append(exc)

                first = threading.Thread(target=load_profiles)
                second = threading.Thread(target=load_profiles)
                first.start()
                self.assertTrue(store.first_read_started.wait(timeout=2))
                second.start()
                store.release_first_read.set()
                first.join(timeout=2)
                second.join(timeout=2)

        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(len(results), 2)
        self.assertIs(results[0], results[1])
        self.assertEqual(store.read_count, 1)

    def test_list_profiles_returns_cached_payload_when_selected_preset_is_unchanged(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lists_dir = root / "lists"
            lists_dir.mkdir()
            (lists_dir / "youtube.txt").write_text("youtube.com\n", encoding="utf-8")
            templates_dir = root / "profile" / "templates"
            templates_dir.mkdir(parents=True)
            (templates_dir / "all_profiles.txt").write_text("", encoding="utf-8")
            store = _FileBackedPresetStore(
                root / "selected.txt",
                "\n".join(
                    (
                        "--filter-tcp=80,443",
                        "--hostlist=lists/youtube.txt",
                        "--lua-desync=pass",
                        "",
                    )
                ),
            )
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )

            with (
                patch("settings.store.MAIN_DIRECTORY", str(root)),
                patch("profile.service.load_strategy_catalogs", return_value={}) as catalogs_loader,
            ):
                service = ProfilePresetService(feature, "zapret2_mode")
                first_payload = service.list_profiles()
                second_payload = service.list_profiles()

        self.assertIs(second_payload, first_payload)
        self.assertEqual(store.read_count, 1)
        catalogs_loader.assert_called_once()

    def test_cached_profile_payload_is_kept_per_selected_preset_revision(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            templates_dir = root / "profile" / "templates"
            templates_dir.mkdir(parents=True)
            (templates_dir / "all_profiles.txt").write_text("", encoding="utf-8")
            store = _SwitchableFileBackedPresetStore(
                root,
                {
                    "first.txt": "\n".join(("--filter-tcp=80", "--lua-desync=pass", "")),
                    "second.txt": "\n".join(("--filter-tcp=443", "--lua-desync=pass", "")),
                },
                selected="first.txt",
            )
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )

            with (
                patch("settings.store.MAIN_DIRECTORY", str(root)),
                patch("profile.service.load_strategy_catalogs", return_value={}) as catalogs_loader,
            ):
                service = ProfilePresetService(feature, "zapret2_mode")
                first_payload = service.list_profiles()
                store.selected = "second.txt"
                second_payload = service.list_profiles()
                store.selected = "first.txt"
                cached_first_payload = service.get_cached_profile_list()

        self.assertIs(cached_first_payload, first_payload)
        self.assertIsNot(second_payload, first_payload)
        self.assertEqual(store.read_count_by_file, {"first.txt": 1, "second.txt": 1})
        self.assertEqual(catalogs_loader.call_count, 2)

    def test_empty_profile_payload_cache_returns_without_touching_preset_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = _FileBackedPresetStore(
                root / "selected.txt",
                "\n".join(("--filter-tcp=443", "--lua-desync=pass", "")),
            )
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )

            with (
                patch("settings.store.MAIN_DIRECTORY", str(root)),
                patch("profile.service.path_cache_signature", return_value=(1, 2, "digest")) as signature_reader,
                patch("profile.service.load_profile_folder_state", return_value={}) as folder_reader,
            ):
                service = ProfilePresetService(feature, "zapret2_mode")
                cached_payload = service.get_cached_profile_list()

        self.assertIsNone(cached_payload)
        self.assertEqual(store.read_count, 0)
        signature_reader.assert_not_called()
        folder_reader.assert_not_called()

    def test_profile_payload_cache_drops_oldest_revision_after_limit(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            templates_dir = root / "profile" / "templates"
            templates_dir.mkdir(parents=True)
            (templates_dir / "all_profiles.txt").write_text("", encoding="utf-8")
            store = _SwitchableFileBackedPresetStore(
                root,
                {
                    "first.txt": "\n".join(("--filter-tcp=80", "--lua-desync=pass", "")),
                    "second.txt": "\n".join(("--filter-tcp=443", "--lua-desync=pass", "")),
                    "third.txt": "\n".join(("--filter-udp=50000-50100", "--lua-desync=pass", "")),
                },
                selected="first.txt",
            )
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )

            with (
                patch("settings.store.MAIN_DIRECTORY", str(root)),
                patch("profile.service.PROFILE_LIST_PAYLOAD_CACHE_LIMIT", 2, create=True),
                patch("profile.service.load_strategy_catalogs", return_value={}),
            ):
                service = ProfilePresetService(feature, "zapret2_mode")
                service.list_profiles()
                store.selected = "second.txt"
                second_payload = service.list_profiles()
                store.selected = "third.txt"
                service.list_profiles()
                store.selected = "first.txt"
                evicted_first_payload = service.get_cached_profile_list()
                store.selected = "second.txt"
                cached_second_payload = service.get_cached_profile_list()

        self.assertIsNone(evicted_first_payload)
        self.assertIs(cached_second_payload, second_payload)

    def test_selected_preset_snapshot_changes_when_same_size_file_content_changes(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            preset_path = root / "selected.txt"
            fixed_ns = 1_779_890_000_000_000_000
            store = _FileBackedPresetStore(
                preset_path,
                "\n".join(
                    (
                        "--filter-tcp=443",
                        "--lua-desync=pass",
                        "",
                    )
                ),
            )
            os.utime(preset_path, ns=(fixed_ns, fixed_ns))
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )

            with patch("settings.store.MAIN_DIRECTORY", str(root)):
                service = ProfilePresetService(feature, "zapret2_mode")
                first_preset, _manifest = service.load_selected_preset()

                preset_path.write_text(
                    "\n".join(
                        (
                            "--filter-tcp=443",
                            "--lua-desync=fake",
                            "",
                        )
                    ),
                    encoding="utf-8",
                )
                os.utime(preset_path, ns=(fixed_ns, fixed_ns))

                second_preset, _manifest = service.load_selected_preset()

        self.assertIn("--lua-desync=pass", first_preset.profiles[0].strategy.strategy_lines)
        self.assertIn("--lua-desync=fake", second_preset.profiles[0].strategy.strategy_lines)

    def test_list_profiles_shows_current_ipset_variant_when_preset_uses_ipset(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lists_dir = root / "lists"
            lists_dir.mkdir()
            (lists_dir / "youtube.txt").write_text("youtube.com\n", encoding="utf-8")
            (lists_dir / "ipset-youtube.txt").write_text("1.1.1.1\n", encoding="utf-8")
            templates_dir = root / "profile" / "templates"
            templates_dir.mkdir(parents=True)
            (templates_dir / "all_profiles.txt").write_text(
                "\n".join(
                    (
                        "--filter-tcp=80,443",
                        "--hostlist=lists/youtube.txt",
                        "",
                        "--new",
                        "--filter-tcp=80,443",
                        "--ipset=lists/ipset-youtube.txt",
                        "",
                    )
                ),
                encoding="utf-8",
            )

            store = _PresetStore(
                "\n".join(
                    (
                        "--filter-tcp=80,443",
                        "--ipset=lists/ipset-youtube.txt",
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
                payload = ProfilePresetService(feature, "zapret2_mode").list_profiles()

        self.assertEqual(len(payload.items), 1)
        self.assertEqual(payload.items[0].list_type, "ipset")
        self.assertIn("--ipset=lists/ipset-youtube.txt", payload.items[0].match_lines)

    def test_template_profile_is_shown_as_not_added(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lists_dir = root / "lists"
            lists_dir.mkdir()
            (lists_dir / "youtube.txt").write_text("youtube.com\n", encoding="utf-8")
            (lists_dir / "ipset-youtube.txt").write_text("1.1.1.1\n", encoding="utf-8")
            templates_dir = root / "profile" / "templates"
            templates_dir.mkdir(parents=True)
            (templates_dir / "all_profiles.txt").write_text(
                "\n".join(
                    (
                        "--filter-tcp=80,443",
                        "--hostlist=lists/youtube.txt",
                        "",
                    )
                ),
                encoding="utf-8",
            )
            store = _PresetStore("")
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )

            with patch("settings.store.MAIN_DIRECTORY", str(root)):
                payload = ProfilePresetService(feature, "zapret2_mode").list_profiles()
                setup = ProfilePresetService(feature, "zapret2_mode").get_profile_setup(payload.items[0].key)

        self.assertEqual(len(payload.items), 1)
        self.assertFalse(payload.items[0].in_preset)
        self.assertFalse(payload.items[0].enabled)
        self.assertEqual(payload.items[0].strategy_id, "none")
        self.assertEqual(payload.items[0].strategy_name, "Не добавлен")
        self.assertIsNotNone(setup)
        self.assertEqual(setup.item.strategy_name, "Не добавлен")
        self.assertEqual(store.text, "")

    def test_skipped_preset_profile_is_shown_as_disabled(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lists_dir = root / "lists"
            lists_dir.mkdir()
            (lists_dir / "youtube.txt").write_text("youtube.com\n", encoding="utf-8")
            (lists_dir / "ipset-youtube.txt").write_text("1.1.1.1\n", encoding="utf-8")
            templates_dir = root / "profile" / "templates"
            templates_dir.mkdir(parents=True)
            (templates_dir / "all_profiles.txt").write_text("", encoding="utf-8")
            store = _PresetStore(
                "\n".join(
                    (
                        "--skip",
                        "--filter-tcp=80,443",
                        "--hostlist=lists/youtube.txt",
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
                payload = ProfilePresetService(feature, "zapret2_mode").list_profiles()

        self.assertEqual(len(payload.items), 1)
        self.assertTrue(payload.items[0].in_preset)
        self.assertFalse(payload.items[0].enabled)
        self.assertEqual(payload.items[0].strategy_id, "none")
        self.assertEqual(payload.items[0].strategy_name, "Выключен")

    def test_enabled_profile_without_strategy_is_shown_as_no_strategy_selected(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            templates_dir = root / "profile" / "templates"
            templates_dir.mkdir(parents=True)
            (templates_dir / "all_profiles.txt").write_text("", encoding="utf-8")
            store = _PresetStore(
                "\n".join(
                    (
                        "--filter-tcp=80,443",
                        "--hostlist=lists/youtube.txt",
                        "",
                    )
                )
            )
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )

            with patch("settings.store.MAIN_DIRECTORY", str(root)):
                payload = ProfilePresetService(feature, "zapret2_mode").list_profiles()

        self.assertEqual(len(payload.items), 1)
        self.assertTrue(payload.items[0].in_preset)
        self.assertTrue(payload.items[0].enabled)
        self.assertEqual(payload.items[0].strategy_id, "none")
        self.assertEqual(payload.items[0].strategy_name, "Стратегия не выбрана")

    def test_same_profile_name_collapses_different_hostlist_files(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lists_dir = root / "lists"
            lists_dir.mkdir()
            (lists_dir / "youtube.txt").write_text("", encoding="utf-8")
            (lists_dir / "ipset-youtube.txt").write_text("", encoding="utf-8")
            templates_dir = root / "profile" / "templates"
            templates_dir.mkdir(parents=True)
            (templates_dir / "all_profiles.txt").write_text(
                "\n".join(
                    (
                        "--name=youtube.com (интерфейс)",
                        "--filter-tcp=80,443",
                        "--hostlist=lists/youtube.txt",
                        "",
                        "--new",
                        "--name=youtube.com (интерфейс)",
                        "--filter-tcp=80,443",
                        "--hostlist=lists/russia-youtube.txt",
                        "",
                        "--new",
                        "--name=youtube.com (интерфейс)",
                        "--filter-tcp=80,443",
                        "--ipset=lists/ipset-youtube.txt",
                        "",
                    )
                ),
                encoding="utf-8",
            )

            store = _PresetStore("")
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )

            with patch("settings.store.MAIN_DIRECTORY", str(root)):
                payload = ProfilePresetService(feature, "zapret2_mode").list_profiles()

        self.assertEqual(len(payload.items), 1)
        self.assertEqual(payload.items[0].display_name, "youtube.com (интерфейс)")
        self.assertEqual(payload.items[0].list_type, "hostlist")
        self.assertIn("--hostlist=lists/youtube.txt", payload.items[0].match_lines)

    def test_named_template_collapses_with_unnamed_preset_profile_by_same_list(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            templates_dir = root / "profile" / "templates"
            templates_dir.mkdir(parents=True)
            (templates_dir / "all_profiles.txt").write_text(
                "\n".join(
                    (
                        "--name=googlevideo.com (CDN сервера)",
                        "--filter-tcp=80,443",
                        "--hostlist=lists/googlevideo.txt",
                        "",
                    )
                ),
                encoding="utf-8",
            )

            store = _PresetStore(
                "\n".join(
                    (
                        "--filter-tcp=80,443",
                        "--hostlist=lists/googlevideo.txt",
                        "--lua-desync=multisplit:pos=sniext+1",
                        "",
                    )
                )
            )
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )

            with patch("settings.store.MAIN_DIRECTORY", str(root)):
                payload = ProfilePresetService(feature, "zapret2_mode").list_profiles()

        self.assertEqual(len(payload.items), 1)
        self.assertTrue(payload.items[0].in_preset)
        self.assertIn("--hostlist=lists/googlevideo.txt", payload.items[0].match_lines)

    def test_profile_folder_does_not_depend_on_preset_membership(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            templates_dir = root / "profile" / "templates"
            templates_dir.mkdir(parents=True)
            (templates_dir / "all_profiles.txt").write_text(
                "\n".join(
                    (
                        "--filter-tcp=80,443",
                        "--hostlist=lists/youtube.txt",
                        "",
                        "--new",
                        "--filter-tcp=443",
                        "--hostlist=lists/discord.txt",
                        "",
                    )
                ),
                encoding="utf-8",
            )
            store = _PresetStore(
                "\n".join(
                    (
                        "--filter-tcp=80,443",
                        "--hostlist=lists/youtube.txt",
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
                payload = ProfilePresetService(feature, "zapret2_mode").list_profiles()

        by_text = {" ".join(item.match_lines).lower(): item for item in payload.items}
        youtube = next(item for text, item in by_text.items() if "youtube" in text)
        discord = next(item for text, item in by_text.items() if "discord" in text)
        self.assertTrue(youtube.in_preset)
        self.assertEqual(youtube.group, "youtube")
        self.assertEqual(youtube.group_name, "YouTube")
        self.assertFalse(discord.in_preset)
        self.assertEqual(discord.group, "discord")
        self.assertEqual(discord.group_name, "Discord")

    def test_profile_setup_loads_selected_profile_without_rebuilding_whole_list(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "profile" / "templates").mkdir(parents=True)
            (root / "profile" / "templates" / "all_profiles.txt").write_text("", encoding="utf-8")
            catalogs_dir = root / "profile" / "strategy_catalogs" / "winws2"
            catalogs_dir.mkdir(parents=True)
            (catalogs_dir / "tcp.txt").write_text(
                "\n".join(
                    (
                        "[tls_fake]",
                        "name = TLS Fake",
                        "--lua-desync=fake",
                        "",
                        "[tls_split]",
                        "name = TLS Split",
                        "--lua-desync=multisplit:pos=sniext+1",
                        "",
                    )
                ),
                encoding="utf-8",
            )
            store = _PresetStore(
                "\n".join(
                    (
                        "--filter-tcp=80,443",
                        "--hostlist=lists/youtube.txt",
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

            with patch.object(service, "list_profiles", side_effect=AssertionError("list_profiles не должен вызываться")):
                payload = service.get_profile_setup("profile:0")

        self.assertIsNotNone(payload)
        self.assertEqual(payload.item.strategy_id, "tls_fake")
        self.assertEqual(set(payload.strategy_entries), {"tls_fake", "tls_split"})

    def test_profile_move_updates_interface_order_without_rewriting_preset_text(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            templates_dir = root / "profile" / "templates"
            templates_dir.mkdir(parents=True)
            (templates_dir / "all_profiles.txt").write_text("", encoding="utf-8")
            source_text = "\n".join(
                (
                    "--filter-tcp=80,443",
                    "--hostlist=lists/youtube.txt",
                    "",
                    "--new",
                    "--filter-tcp=443",
                    "--hostlist=lists/discord.txt",
                    "",
                )
            )
            store = _PresetStore(source_text)
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )
            service = ProfilePresetService(feature, "zapret2_mode")

            with patch("settings.store.MAIN_DIRECTORY", str(root)):
                payload = service.list_profiles()
                youtube = next(item for item in payload.items if "youtube" in " ".join(item.match_lines).lower())
                discord = next(item for item in payload.items if "discord" in " ".join(item.match_lines).lower())
                moved = service.move_profile_before(discord.key, youtube.key)
                moved_payload = service.list_profiles()

        self.assertEqual(moved, discord.key)
        self.assertEqual(store.text, source_text)
        moved_discord = next(item for item in moved_payload.items if "discord" in " ".join(item.match_lines).lower())
        self.assertTrue(moved_discord.order_is_manual)
        self.assertEqual(moved_discord.group, "youtube")

    def test_profile_move_inside_folder_does_not_pull_other_default_groups(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            templates_dir = root / "profile" / "templates"
            templates_dir.mkdir(parents=True)
            (templates_dir / "all_profiles.txt").write_text("", encoding="utf-8")
            source_text = "\n".join(
                (
                    "--filter-tcp=80,443",
                    "--hostlist=lists/youtube.txt",
                    "",
                    "--new",
                    "--filter-tcp=80,443",
                    "--hostlist=lists/googlevideo.txt",
                    "",
                    "--new",
                    "--filter-tcp=443",
                    "--hostlist=lists/discord.txt",
                    "",
                )
            )
            store = _PresetStore(source_text)
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )
            service = ProfilePresetService(feature, "zapret2_mode")

            with patch("settings.store.MAIN_DIRECTORY", str(root)):
                payload = service.list_profiles()
                youtube = next(item for item in payload.items if "youtube.txt" in " ".join(item.match_lines).lower())
                googlevideo = next(item for item in payload.items if "googlevideo" in " ".join(item.match_lines).lower())
                service.move_profile_after(googlevideo.key, youtube.key)
                moved_payload = service.list_profiles()

        moved_groups = {
            " ".join(item.match_lines).lower(): item.group
            for item in moved_payload.items
        }
        self.assertEqual(next(group for text, group in moved_groups.items() if "youtube.txt" in text), "youtube")
        self.assertEqual(next(group for text, group in moved_groups.items() if "googlevideo" in text), "youtube")
        self.assertEqual(next(group for text, group in moved_groups.items() if "discord" in text), "discord")

    def test_profile_folder_reset_rebuilds_cached_list_with_default_groups(self) -> None:
        from profile.folders import load_profile_folder_state, reset_profile_folders, save_profile_folder_state

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            templates_dir = root / "profile" / "templates"
            templates_dir.mkdir(parents=True)
            (templates_dir / "all_profiles.txt").write_text("", encoding="utf-8")
            source_text = "\n".join(
                (
                    "--filter-tcp=80,443",
                    "--hostlist=lists/youtube.txt",
                    "",
                    "--new",
                    "--filter-tcp=443",
                    "--hostlist=lists/discord.txt",
                    "",
                )
            )
            store = _PresetStore(source_text)
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )
            service = ProfilePresetService(feature, "zapret2_mode")

            with patch("settings.store.MAIN_DIRECTORY", str(root)):
                payload = service.list_profiles()
                state = load_profile_folder_state()
                for item in payload.items:
                    state["items"][item.persistent_key] = {"folder_key": "common", "order": 0, "rating": 0}
                save_profile_folder_state(state)
                service._invalidate_profile_list_snapshot()
                common_payload = service.list_profiles()

                reset_profile_folders()
                reset_payload = service.list_profiles()

        self.assertEqual({item.group for item in common_payload.items}, {"common"})
        reset_groups = {item.group for item in reset_payload.items}
        self.assertIn("youtube", reset_groups)
        self.assertIn("discord", reset_groups)

    def test_profile_can_move_to_folder_without_rewriting_preset_text(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            templates_dir = root / "profile" / "templates"
            templates_dir.mkdir(parents=True)
            (templates_dir / "all_profiles.txt").write_text("", encoding="utf-8")
            source_text = "\n".join(
                (
                    "--filter-tcp=80,443",
                    "--hostlist=lists/youtube.txt",
                    "",
                )
            )
            store = _PresetStore(source_text)
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )
            service = ProfilePresetService(feature, "zapret2_mode")

            with patch("settings.store.MAIN_DIRECTORY", str(root)):
                payload = service.list_profiles()
                youtube = next(item for item in payload.items if "youtube" in " ".join(item.match_lines).lower())
                moved = service.move_profile_to_folder(youtube.key, "common")
                moved_payload = service.list_profiles()

        self.assertEqual(moved, youtube.key)
        self.assertEqual(store.text, source_text)
        moved_youtube = next(item for item in moved_payload.items if "youtube" in " ".join(item.match_lines).lower())
        self.assertEqual(moved_youtube.group, "common")

    def test_preset_order_profiles_use_raw_preset_order_without_templates_or_deduplication(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            templates_dir = root / "profile" / "templates"
            templates_dir.mkdir(parents=True)
            (templates_dir / "all_profiles.txt").write_text(
                "\n".join(
                    (
                        "--name=Не добавлен",
                        "--filter-tcp=443",
                        "--hostlist=lists/not-added.txt",
                        "--lua-desync=pass",
                        "",
                    )
                ),
                encoding="utf-8",
            )
            store = _PresetStore(
                "\n".join(
                    (
                        "--name=YouTube pass",
                        "--filter-tcp=80,443",
                        "--hostlist=lists/youtube.txt",
                        "--lua-desync=pass",
                        "",
                        "--new",
                        "--name=YouTube fake",
                        "--filter-tcp=80,443",
                        "--hostlist=lists/youtube.txt",
                        "--lua-desync=fake",
                        "",
                        "--new",
                        "--name=Telegram",
                        "--filter-tcp=443",
                        "--hostlist=lists/telegram.txt",
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
                payload = ProfilePresetService(feature, "zapret2_mode").list_preset_order_profiles()

        self.assertEqual([item.profile_name for item in payload.items], ["YouTube pass", "YouTube fake", "Telegram"])
        self.assertTrue(all(item.in_preset for item in payload.items))
        self.assertEqual(sum("youtube.txt" in " ".join(item.match_lines).lower() for item in payload.items), 2)
        self.assertNotIn("Не добавлен", [item.profile_name for item in payload.items])

    def test_preset_order_move_rewrites_preset_file_order(self) -> None:
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
                        "--lua-desync=pass",
                        "",
                        "--new",
                        "--name=Discord",
                        "--filter-tcp=443",
                        "--hostlist=lists/discord.txt",
                        "--lua-desync=fake",
                        "",
                        "--new",
                        "--name=Telegram",
                        "--filter-tcp=443",
                        "--hostlist=lists/telegram.txt",
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
                payload = service.list_preset_order_profiles()
                youtube, _discord, telegram = payload.items
                moved = service.move_preset_profile_before(telegram.key, youtube.key)
                moved_payload = service.list_preset_order_profiles()

        self.assertEqual(str(moved), moved_payload.items[0].key)
        self.assertEqual(moved.key_map[telegram.key], moved_payload.items[0].key)
        self.assertEqual([item.profile_name for item in moved_payload.items], ["Telegram", "YouTube", "Discord"])
        self.assertLess(store.text.index("--name=Telegram"), store.text.index("--name=YouTube"))
        self.assertLess(store.text.index("--name=YouTube"), store.text.index("--name=Discord"))

    def test_preset_order_move_uses_exact_row_key_for_duplicate_profiles(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            templates_dir = root / "profile" / "templates"
            templates_dir.mkdir(parents=True)
            (templates_dir / "all_profiles.txt").write_text("", encoding="utf-8")
            store = _PresetStore(
                "\n".join(
                    (
                        "--name=Same",
                        "--filter-tcp=443",
                        "--hostlist=lists/same.txt",
                        "--lua-desync=pass",
                        "",
                        "--new",
                        "--name=Same",
                        "--filter-tcp=443",
                        "--hostlist=lists/same.txt",
                        "--lua-desync=fake",
                        "",
                        "--new",
                        "--name=Other",
                        "--filter-tcp=443",
                        "--hostlist=lists/other.txt",
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
                first, second, other = service.list_preset_order_profiles().items
                moved = service.move_preset_profile_after(second.key, other.key)
                moved_payload = service.list_preset_order_profiles()

        self.assertEqual(str(moved), moved_payload.items[2].key)
        self.assertEqual([item.profile_name for item in moved_payload.items], ["Same", "Other", "Same"])
        self.assertIn(second.key, moved.key_map)
        self.assertEqual(moved.key_map[second.key], moved_payload.items[2].key)
        self.assertLess(store.text.index("--lua-desync=pass"), store.text.index("--name=Other"))
        self.assertLess(store.text.index("--name=Other"), store.text.index("--lua-desync=fake"))

    def test_preset_order_move_rejects_ambiguous_logical_key(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            templates_dir = root / "profile" / "templates"
            templates_dir.mkdir(parents=True)
            (templates_dir / "all_profiles.txt").write_text("", encoding="utf-8")
            source_text = "\n".join(
                (
                    "--name=Same",
                    "--filter-tcp=443",
                    "--hostlist=lists/same.txt",
                    "--lua-desync=pass",
                    "",
                    "--new",
                    "--name=Same",
                    "--filter-tcp=443",
                    "--hostlist=lists/same.txt",
                    "--lua-desync=fake",
                    "",
                    "--new",
                    "--name=Other",
                    "--filter-tcp=443",
                    "--hostlist=lists/other.txt",
                    "--lua-desync=pass",
                    "",
                )
            )
            store = _PresetStore(source_text)
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )

            with patch("settings.store.MAIN_DIRECTORY", str(root)):
                service = ProfilePresetService(feature, "zapret2_mode")
                _first, _second, other = service.list_preset_order_profiles().items
                moved = service.move_preset_profile_after("name:Same", other.key)

        self.assertIsNone(moved)
        self.assertEqual(store.text, source_text)

    def test_profile_raw_text_update_rejects_ambiguous_logical_key(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            templates_dir = root / "profile" / "templates"
            templates_dir.mkdir(parents=True)
            (templates_dir / "all_profiles.txt").write_text("", encoding="utf-8")
            source_text = "\n".join(
                (
                    "--name=Same",
                    "--filter-tcp=443",
                    "--hostlist=lists/same.txt",
                    "--lua-desync=pass",
                    "",
                    "--new",
                    "--name=Same",
                    "--filter-tcp=443",
                    "--hostlist=lists/same.txt",
                    "--lua-desync=fake",
                    "",
                )
            )
            store = _PresetStore(source_text)
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )

            with patch("settings.store.MAIN_DIRECTORY", str(root)):
                service = ProfilePresetService(feature, "zapret2_mode")
                updated = service.update_profile_raw_text(
                    "name:Same",
                    "\n".join(
                        (
                            "--name=Same",
                            "--filter-tcp=443",
                            "--hostlist=lists/same.txt",
                            "--lua-desync=split",
                        )
                    ),
                )

        self.assertIsNone(updated)
        self.assertEqual(store.text, source_text)

    def test_profile_setup_reads_strategy_feedback_in_one_batch(self) -> None:
        class _StateStore:
            def __init__(self) -> None:
                self.single_calls = 0
                self.batch_calls = 0

            def get_strategy_state(self, _profile_key: str, _strategy_id: str) -> ProfileStrategyState:
                self.single_calls += 1
                return ProfileStrategyState()

            def get_strategy_states(self, _profile_key: str, strategy_ids) -> dict[str, ProfileStrategyState]:
                self.batch_calls += 1
                return {
                    str(strategy_id): ProfileStrategyState()
                    for strategy_id in tuple(strategy_ids or ())
                }

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "profile" / "templates").mkdir(parents=True)
            (root / "profile" / "templates" / "all_profiles.txt").write_text("", encoding="utf-8")
            catalogs_dir = root / "profile" / "strategy_catalogs" / "winws2"
            catalogs_dir.mkdir(parents=True)
            catalog_lines: list[str] = []
            for index in range(80):
                catalog_lines.extend(
                    (
                        f"[strategy_{index}]",
                        f"name = Strategy {index}",
                        f"--lua-desync=fake:repeats={index + 1}",
                        "",
                    )
                )
            (catalogs_dir / "tcp.txt").write_text("\n".join(catalog_lines), encoding="utf-8")
            store = _PresetStore(
                "\n".join(
                    (
                        "--filter-tcp=80,443",
                        "--hostlist=lists/youtube.txt",
                        "--lua-desync=fake:repeats=1",
                        "",
                    )
                )
            )
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )
            service = ProfilePresetService(feature, "zapret2_mode")
            state_store = _StateStore()
            service._state_store = state_store

            payload = service.get_profile_setup("profile:0")

        self.assertIsNotNone(payload)
        self.assertEqual(len(payload.strategy_entries), 80)
        self.assertEqual(state_store.batch_calls, 1)
        self.assertLessEqual(state_store.single_calls, 1)


if __name__ == "__main__":
    unittest.main()
