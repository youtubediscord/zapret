from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from core.paths import AppPaths
from profile.ui.profiles_list import _ordered_group_keys
from profile.strategy_state import ProfileStrategyState
from profile.service import ProfilePresetService


class _PresetStore:
    def __init__(self, text: str) -> None:
        self.text = text

    def read_selected_preset_source(self, _launch_method: str):
        return self.text, SimpleNamespace(file_name="selected.txt", name="selected")

    def save_selected_preset_source(self, _launch_method: str, text: str) -> None:
        self.text = text


class ProfileListPayloadTests(unittest.TestCase):
    def test_profile_folder_order_keeps_zero_order_first(self) -> None:
        grouped = {
            "discord": [object()],
            "youtube": [object()],
            "messengers": [object()],
        }

        self.assertEqual(_ordered_group_keys(grouped), ["youtube", "discord", "messengers"])

    def test_list_profiles_keeps_catalog_rows_but_collapses_hostlist_ipset_variants(self) -> None:
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

    def test_list_profiles_shows_current_ipset_variant_when_preset_uses_ipset(self) -> None:
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
