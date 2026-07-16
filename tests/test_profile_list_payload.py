from __future__ import annotations

import os
import threading
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from core.paths import AppPaths
from profile.display_items import build_profile_display_items
from profile.list_view_state import ordered_group_keys
from profile.strategy_state import ProfileStrategyState
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
    def test_strategy_only_apply_updates_cached_profile_list_item_without_dropping_snapshot(self) -> None:
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
                first_payload = service.list_profiles()
                result = service.apply_strategy("profile:0", "tcp_md5")
                cache_entry = service.get_cached_profile_list_entry()

        self.assertEqual(result.status, "applied")
        self.assertIsNotNone(cache_entry)
        _revision, cached_payload = cache_entry
        self.assertIsNot(cached_payload, first_payload)
        self.assertEqual(tuple(item.strategy_id for item in cached_payload.items), ("tcp_md5",))
        self.assertEqual(store.save_count, 1)

    def test_profile_folder_order_keeps_zero_order_first(self) -> None:
        # Ранг папки приходит из единого резолвера (сохранённое состояние),
        # а не из зашитых дефолтов.
        grouped = {
            "discord": [SimpleNamespace(group_rank=1)],
            "youtube": [SimpleNamespace(group_rank=0)],
            "messengers": [SimpleNamespace(group_rank=3)],
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

    def test_list_profiles_normalizes_multi_list_profile_without_saving_preset(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lists_dir = root / "lists"
            lists_dir.mkdir()
            (lists_dir / "youtube.txt").write_text("youtube.com\n", encoding="utf-8")
            (lists_dir / "ipset-youtube.txt").write_text("1.1.1.1\n", encoding="utf-8")
            templates_dir = root / "profile" / "templates"
            templates_dir.mkdir(parents=True)
            (templates_dir / "all_profiles.txt").write_text("", encoding="utf-8")
            original_text = "\n".join(
                (
                    "--filter-tcp=80,443",
                    "--hostlist=lists/discord.txt",
                    "--hostlist=lists/other.txt",
                    "--hostlist-exclude=lists/list-exclude.txt",
                    "--lua-desync=pass",
                    "",
                )
            )
            store = _PresetStore(original_text)
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )

            with patch("settings.store.MAIN_DIRECTORY", str(root)):
                payload = ProfilePresetService(feature, "zapret2_mode").list_profiles()

        self.assertEqual(payload.normalized_split_profiles, 1)
        self.assertEqual(payload.normalized_created_profiles, 1)
        self.assertEqual(len(payload.items), 2)
        self.assertEqual(store.save_count, 0)
        self.assertEqual(store.text, original_text)
        self.assertTrue(any("--hostlist=lists/discord.txt" in item.match_lines for item in payload.items))
        self.assertTrue(any("--hostlist=lists/other.txt" in item.match_lines for item in payload.items))

    def test_catalog_profile_with_multiple_ipsets_is_visible_and_not_split(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lists_dir = root / "lists"
            lists_dir.mkdir()
            for name in ("ipset-one.txt", "ipset-two.txt", "ipset-three.txt", "ipset-four.txt", "youtube.txt"):
                (lists_dir / name).write_text("127.0.0.1\n", encoding="utf-8")
            templates_dir = root / "profile" / "templates"
            templates_dir.mkdir(parents=True)
            (templates_dir / "all_profiles.txt").write_text(
                "\n".join(
                    (
                        "--name=Каталожный набор IP",
                        "--filter-tcp=80,443-65535",
                        "--ipset=lists/ipset-one.txt",
                        "--ipset=lists/ipset-two.txt",
                        "--ipset=lists/ipset-three.txt",
                        "--ipset=lists/ipset-four.txt",
                        "",
                        "--new",
                        "--name=YouTube",
                        "--filter-tcp=80,443",
                        "--hostlist=lists/youtube.txt",
                        "",
                    )
                ),
                encoding="utf-8",
            )
            store = _PresetStore(
                "\n".join(
                    (
                        "--name=Каталожный набор IP",
                        "--filter-tcp=80,443-65535",
                        "--ipset=lists/ipset-one.txt",
                        "--ipset=lists/ipset-two.txt",
                        "--ipset=lists/ipset-three.txt",
                        "--ipset=lists/ipset-four.txt",
                        "--payload=tls_client_hello",
                        "--out-range=-d8",
                        "--lua-desync=pass",
                        "",
                        "--new",
                        "--name=YouTube",
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
                service = ProfilePresetService(feature, "zapret2_mode")
                payload = service.list_profiles()
                order_payload = service.list_preset_order_profiles()

        self.assertEqual(payload.normalized_split_profiles, 0)
        self.assertEqual([item.profile_name for item in payload.items], ["Каталожный набор IP", "YouTube"])
        self.assertEqual([item.profile_name for item in order_payload.items], ["Каталожный набор IP", "YouTube"])
        catalog_item = payload.items[0]
        self.assertEqual(
            [
                line
                for line in catalog_item.match_lines
                if line.startswith("--ipset=")
            ],
            [
                "--ipset=lists/ipset-one.txt",
                "--ipset=lists/ipset-two.txt",
                "--ipset=lists/ipset-three.txt",
                "--ipset=lists/ipset-four.txt",
            ],
        )
        self.assertIn(
            "\n".join(
                (
                    "--ipset=lists/ipset-one.txt",
                    "--ipset=lists/ipset-two.txt",
                    "--ipset=lists/ipset-three.txt",
                    "--ipset=lists/ipset-four.txt",
                )
            ),
            store.text,
        )
        self.assertIn("--payload=tls_client_hello\n--out-range=-d8\n--lua-desync=pass", store.text)

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
                patch(
                    "profile.service.load_strategy_catalogs_with_signature",
                    return_value=(("catalogs", "signature"), {}),
                ) as catalogs_loader,
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
            lists_dir = root / "lists"
            lists_dir.mkdir()
            (lists_dir / "facebook.txt").write_text("", encoding="utf-8")
            (lists_dir / "ipset-facebook.txt").write_text("", encoding="utf-8")
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
                patch(
                    "profile.service.load_strategy_catalogs_with_signature",
                    return_value=(("catalogs", "signature"), {}),
                ) as catalogs_loader,
            ):
                service = ProfilePresetService(feature, "zapret2_mode")
                first_payload = service.list_profiles()
                store.selected = "second.txt"
                second_payload = service.list_profiles()
                # Первая загрузка second.txt материализовала мету его нового
                # профиля и сдвинула ревизию папок — first перечитывается один раз.
                store.selected = "first.txt"
                first_warm_payload = service.list_profiles()
                store.selected = "second.txt"
                cached_second_payload = service.get_cached_profile_list()
                store.selected = "first.txt"
                cached_first_payload = service.get_cached_profile_list()

        self.assertIs(cached_first_payload, first_warm_payload)
        self.assertIs(cached_second_payload, second_payload)
        self.assertIsNot(second_payload, first_payload)
        self.assertEqual(store.read_count_by_file, {"first.txt": 2, "second.txt": 1})
        self.assertEqual(catalogs_loader.call_count, 3)

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
            lists_dir = root / "lists"
            lists_dir.mkdir()
            (lists_dir / "facebook.txt").write_text("", encoding="utf-8")
            (lists_dir / "ipset-facebook.txt").write_text("", encoding="utf-8")
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
                patch(
                    "profile.service.load_strategy_catalogs_with_signature",
                    return_value=(("catalogs", "signature"), {}),
                ),
            ):
                service = ProfilePresetService(feature, "zapret2_mode")
                # Прогрев: первый resolve каждого пресета материализует мету
                # папок и сдвигает ревизию; LRU проверяем на стабильном состоянии.
                for warm_name in ("first.txt", "second.txt", "third.txt"):
                    store.selected = warm_name
                    service.list_profiles()
                store.selected = "first.txt"
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
        self.assertEqual(payload.items[0].display_name, "TCP 80,443 • hostlist youtube.txt")

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

    def test_unnamed_preset_profile_uses_matching_template_display_name(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            templates_dir = root / "profile" / "templates"
            templates_dir.mkdir(parents=True)
            (templates_dir / "all_profiles.txt").write_text(
                "\n".join(
                    (
                        "--name=Facebook",
                        "--filter-tcp=80,443",
                        "--hostlist=lists/facebook.txt",
                        "",
                    )
                ),
                encoding="utf-8",
            )

            store = _PresetStore(
                "\n".join(
                    (
                        "--filter-tcp=80,443",
                        "--hostlist=lists/facebook.txt",
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
        self.assertEqual(payload.items[0].profile_name, "")
        self.assertEqual(payload.items[0].display_name, "Facebook")

    def test_not_added_template_profile_keeps_all_profiles_display_name(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lists_dir = root / "lists"
            lists_dir.mkdir()
            (lists_dir / "facebook.txt").write_text("facebook.com\n", encoding="utf-8")
            templates_dir = root / "profile" / "templates"
            templates_dir.mkdir(parents=True)
            (templates_dir / "all_profiles.txt").write_text(
                "\n".join(
                    (
                        "--name=Facebook",
                        "--filter-tcp=80,443",
                        "--hostlist=lists/facebook.txt",
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
        self.assertFalse(payload.items[0].in_preset)
        self.assertEqual(payload.items[0].strategy_name, "Не добавлен")
        self.assertEqual(payload.items[0].profile_name, "Facebook")
        self.assertEqual(payload.items[0].display_name, "Facebook")
        display_items = build_profile_display_items(payload.items)
        self.assertEqual(display_items[0].display_name, "Facebook")

    def test_template_profile_without_any_name_uses_inferred_display_name(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lists_dir = root / "lists"
            lists_dir.mkdir()
            (lists_dir / "facebook.txt").write_text("facebook.com\n", encoding="utf-8")
            templates_dir = root / "profile" / "templates"
            templates_dir.mkdir(parents=True)
            (templates_dir / "all_profiles.txt").write_text(
                "\n".join(
                    (
                        "--filter-tcp=80,443",
                        "--hostlist=lists/facebook.txt",
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
        self.assertFalse(payload.items[0].in_preset)
        self.assertEqual(payload.items[0].profile_name, "")
        self.assertEqual(payload.items[0].display_name, "TCP 80,443 • hostlist facebook.txt")

    def test_lowercase_preset_profile_name_wins_over_template_case(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            templates_dir = root / "profile" / "templates"
            templates_dir.mkdir(parents=True)
            (templates_dir / "all_profiles.txt").write_text(
                "\n".join(
                    (
                        "--name=Facebook",
                        "--filter-tcp=80,443",
                        "--hostlist=lists/facebook.txt",
                        "",
                    )
                ),
                encoding="utf-8",
            )

            store = _PresetStore(
                "\n".join(
                    (
                        "--name=facebook",
                        "--filter-tcp=80,443",
                        "--hostlist=lists/facebook.txt",
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
        self.assertEqual(payload.items[0].display_name, "facebook")
        self.assertEqual(payload.items[0].profile_name, "facebook")
        display_items = build_profile_display_items(payload.items)
        self.assertEqual(display_items[0].display_name, "facebook")

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
        moved_youtube = next(item for item in moved_payload.items if "youtube" in " ".join(item.match_lines).lower())
        self.assertEqual(moved_discord.group, "youtube")
        self.assertEqual(moved_discord.order, 0)
        self.assertEqual(moved_youtube.order, 1)

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

    def test_preset_order_move_preserves_new_line_name_when_profile_becomes_first(self) -> None:
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
                        "--new=Discord",
                        "--filter-tcp=443",
                        "--hostlist=lists/discord.txt",
                        "--lua-desync=fake",
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
                youtube, discord = service.list_preset_order_profiles().items
                service.move_preset_profile_before(discord.key, youtube.key)
                moved_payload = service.list_preset_order_profiles()

        self.assertEqual([item.profile_name for item in moved_payload.items], ["Discord", "YouTube"])
        self.assertIn("--name=Discord", store.text)
        self.assertLess(store.text.index("--name=Discord"), store.text.index("--hostlist=lists/discord.txt"))

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

    def test_profile_raw_text_update_targets_first_duplicate_deterministically(self) -> None:
        """Дубликаты имён больше не дают неоднозначности: базовый ключ
        детерминированно принадлежит первому профилю, у остальных — уникальные
        суффиксы (см. _assign_profile_keys)."""
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
                first_key_before = service.load_selected_preset()[0].profiles[0].persistent_key
                second_key_before = service.load_selected_preset()[0].profiles[1].persistent_key
                updated = service.update_profile_raw_text(
                    first_key_before,
                    "\n".join(
                        (
                            "--name=Same",
                            "--filter-tcp=443",
                            "--hostlist=lists/same.txt",
                            "--lua-desync=split",
                        )
                    ),
                )
                preset_after, _manifest = service.load_selected_preset()

        # Успех: пара (old, new) persistent_key первого дубликата; uid стабилен.
        self.assertEqual(updated, (first_key_before, first_key_before))
        self.assertIn("--lua-desync=split", [segment.text for segment in preset_after.profiles[0].segments])
        # Второй дубликат не тронут и сохранил свой уникальный ключ.
        self.assertIn("--lua-desync=fake", [segment.text for segment in preset_after.profiles[1].segments])
        self.assertEqual(preset_after.profiles[1].persistent_key, second_key_before)
        self.assertNotEqual(preset_after.profiles[1].persistent_key, first_key_before)

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


class ProfileDerivedCacheTests(unittest.TestCase):
    """Контентный кэш производных данных профиля: пересчёт только изменённого."""

    @staticmethod
    def _make_environment(root: Path, files: dict[str, str], selected: str):
        templates_dir = root / "profile" / "templates"
        templates_dir.mkdir(parents=True)
        (templates_dir / "all_profiles.txt").write_text("", encoding="utf-8")
        store = _SwitchableFileBackedPresetStore(root, files, selected=selected)
        feature = SimpleNamespace(
            _presets_feature=store,
            _app_paths=AppPaths(user_root=root, local_root=root),
        )
        return store, feature

    @staticmethod
    def _profile_text(name: str, match_line: str) -> tuple[str, ...]:
        return (
            f"--name={name}",
            match_line,
            "--lua-desync=pass",
            "",
        )

    def test_preset_switch_reuses_derived_cores_of_unchanged_profiles(self) -> None:
        import profile.derived_cache as profile_derived_cache_module

        real_entries = profile_derived_cache_module.basic_strategy_entries
        computed_names: list[str] = []

        def counting_entries(profile, catalogs):
            computed_names.append(str(getattr(profile, "name", "") or ""))
            return real_entries(profile, catalogs)

        alpha = self._profile_text("Alpha", "--filter-tcp=80,443")
        beta = self._profile_text("Beta", "--filter-udp=443")
        gamma = self._profile_text("Gamma", "--filter-tcp=8443")
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store, feature = self._make_environment(
                root,
                {
                    "first.txt": "\n".join((*alpha, "--new", *beta)),
                    "second.txt": "\n".join((*alpha, "--new", *gamma)),
                },
                selected="first.txt",
            )

            with (
                patch("settings.store.MAIN_DIRECTORY", str(root)),
                patch("profile.derived_cache.basic_strategy_entries", new=counting_entries),
            ):
                service = ProfilePresetService(feature, "zapret2_mode")
                service.list_profiles()
                first_computed = list(computed_names)

                computed_names.clear()
                store.selected = "second.txt"
                service.list_profiles()
                second_computed = list(computed_names)

                computed_names.clear()
                store.selected = "first.txt"
                service.list_profiles()
                back_computed = list(computed_names)

        self.assertIn("Alpha", first_computed)
        self.assertIn("Beta", first_computed)
        self.assertIn("Gamma", second_computed)
        self.assertNotIn("Alpha", second_computed, "неизменённый профиль не должен пересчитываться при смене пресета")
        self.assertEqual(back_computed, [], "возврат на прогретый пресет не должен пересчитывать профили")

    def test_profile_content_change_recomputes_only_changed_profile(self) -> None:
        import profile.derived_cache as profile_derived_cache_module

        real_entries = profile_derived_cache_module.basic_strategy_entries
        computed_names: list[str] = []

        def counting_entries(profile, catalogs):
            computed_names.append(str(getattr(profile, "name", "") or ""))
            return real_entries(profile, catalogs)

        alpha = self._profile_text("Alpha", "--filter-tcp=80,443")
        beta = self._profile_text("Beta", "--filter-udp=443")
        beta_changed = self._profile_text("Beta", "--filter-udp=443,50000-50100")
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store, feature = self._make_environment(
                root,
                {"selected.txt": "\n".join((*alpha, "--new", *beta))},
                selected="selected.txt",
            )

            with (
                patch("settings.store.MAIN_DIRECTORY", str(root)),
                patch("profile.derived_cache.basic_strategy_entries", new=counting_entries),
            ):
                service = ProfilePresetService(feature, "zapret2_mode")
                service.list_profiles()

                computed_names.clear()
                (root / "selected.txt").write_text("\n".join((*alpha, "--new", *beta_changed)), encoding="utf-8")
                service.list_profiles()
                recomputed = list(computed_names)

        self.assertIn("Beta", recomputed)
        self.assertNotIn("Alpha", recomputed, "изменение одного профиля не должно пересчитывать остальные")

    def test_profile_setup_reuses_prepared_sources_and_cores(self) -> None:
        import profile.derived_cache as profile_derived_cache_module

        real_entries = profile_derived_cache_module.basic_strategy_entries
        real_sources = profile_derived_cache_module.build_profile_list_sources
        entries_calls: list[str] = []
        sources_calls: list[int] = []

        def counting_entries(profile, catalogs):
            entries_calls.append(str(getattr(profile, "name", "") or ""))
            return real_entries(profile, catalogs)

        def counting_sources(profiles, templates):
            sources_calls.append(len(tuple(profiles)))
            return real_sources(profiles, templates)

        alpha = self._profile_text("Alpha", "--filter-tcp=80,443")
        beta = self._profile_text("Beta", "--filter-udp=443")
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _store, feature = self._make_environment(
                root,
                {"selected.txt": "\n".join((*alpha, "--new", *beta))},
                selected="selected.txt",
            )

            with (
                patch("settings.store.MAIN_DIRECTORY", str(root)),
                patch("profile.derived_cache.basic_strategy_entries", new=counting_entries),
                patch("profile.derived_cache.build_profile_list_sources", new=counting_sources),
            ):
                service = ProfilePresetService(feature, "zapret2_mode")
                payload = service.list_profiles()
                profile_keys = tuple(item.key for item in payload.items)
                sources_after_list = len(sources_calls)
                entries_after_list = len(entries_calls)

                for profile_key in profile_keys:
                    self.assertIsNotNone(service.get_profile_setup(profile_key))

        self.assertGreaterEqual(sources_after_list, 1)
        self.assertEqual(
            len(sources_calls),
            sources_after_list,
            "get_profile_setup не должен пересобирать sources после построения списка",
        )
        self.assertEqual(
            len(entries_calls),
            entries_after_list,
            "get_profile_setup не должен пересчитывать контентное ядро после построения списка",
        )


class FolderStateHotPathTests(unittest.TestCase):
    """Горячий цикл сборки списка не пере-нормализует состояние папок."""

    def test_folder_helpers_trust_normalized_state(self) -> None:
        import inspect

        from profile.folders import profile_folder_collapsed, profile_folder_for_profile

        for helper in (profile_folder_for_profile, profile_folder_collapsed):
            source = inspect.getsource(helper)
            self.assertNotIn(
                "normalize_folder_state(",
                source,
                f"{helper.__name__} не должен нормализовать состояние на каждый вызов",
            )

    def test_folder_helper_loads_state_when_none(self) -> None:
        from unittest.mock import patch as mock_patch

        from profile import folders as folders_module

        normalized = {"folders": {"youtube": {"name": "YouTube", "collapsed": True}}, "items": {}}
        with mock_patch.object(folders_module, "load_profile_folder_state", return_value=normalized) as loader:
            self.assertTrue(folders_module.profile_folder_collapsed("youtube", None))
            loader.assert_called_once_with()
        # переданный dict используется как есть, без загрузки
        with mock_patch.object(folders_module, "load_profile_folder_state") as loader:
            self.assertTrue(folders_module.profile_folder_collapsed("youtube", normalized))
            loader.assert_not_called()


class CatalogIdentityCacheTests(unittest.TestCase):
    """Identity записей каталога считается один раз на запись, не профили×каталог."""

    def test_catalog_identity_lines_computed_once_per_entry(self) -> None:
        from types import SimpleNamespace

        from profile.derived_cache import _entry_identity_lines, resolve_strategy
        from profile.strategy_catalog import StrategyEntry
        from settings.mode import ENGINE_WINWS2

        entries = {
            f"strategy_{i}": StrategyEntry(
                strategy_id=f"strategy_{i}",
                catalog_name="tcp",
                name=f"Strategy {i}",
                args=f"--lua-desync=multidisorder:pos={i}:repeats=10",
                visual=None,
            )
            for i in range(5)
        }
        profiles = [
            SimpleNamespace(
                engine=ENGINE_WINWS2,
                strategy=SimpleNamespace(strategy_lines=(f"--lua-desync=multidisorder:pos={i}:repeats=10",)),
            )
            for i in range(3)
        ]

        _entry_identity_lines.cache_clear()
        for profile in profiles:
            strategy_id, _name = resolve_strategy(profile, entries)
            self.assertTrue(strategy_id.startswith("strategy_"))

        info = _entry_identity_lines.cache_info()
        self.assertEqual(info.misses, len(entries), "identity должен считаться один раз на запись каталога")
        self.assertEqual(info.hits, len(entries) * (len(profiles) - 1))


if __name__ == "__main__":
    unittest.main()
