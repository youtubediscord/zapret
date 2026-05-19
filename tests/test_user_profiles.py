from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from core.paths import AppPaths
from profile.parser import parse_preset_text
from profile.service import ProfilePresetService
from profile.template_library import load_profile_template_library
from profile.user_profiles import create_user_profile, load_user_profile_templates
from settings.mode import ZAPRET1_MODE, ZAPRET2_MODE
from settings.store import read_settings


class _PresetStore:
    def __init__(self, text: str = "") -> None:
        self.text = text

    def read_selected_preset_source(self, _launch_method: str):
        return self.text, SimpleNamespace(file_name="selected.txt", name="selected")

    def save_selected_preset_source(self, _launch_method: str, text: str) -> None:
        self.text = text


class _PresetLibrary:
    def __init__(self, files_by_method: dict[str, dict[str, str]]) -> None:
        self.files_by_method = files_by_method

    def read_selected_preset_source(self, launch_method: str):
        files = self.files_by_method.get(launch_method) or {}
        file_name = next(iter(files), "selected.txt")
        return files.get(file_name, ""), SimpleNamespace(file_name=file_name, name=Path(file_name).stem)

    def save_selected_preset_source(self, launch_method: str, text: str) -> None:
        files = self.files_by_method.setdefault(launch_method, {})
        file_name = next(iter(files), "selected.txt")
        files[file_name] = text

    def list_preset_manifests(self, launch_method: str):
        return [
            SimpleNamespace(file_name=file_name, name=Path(file_name).stem)
            for file_name in self.files_by_method.get(launch_method, {})
        ]

    def read_preset_source_by_file_name(self, launch_method: str, file_name: str) -> str:
        return self.files_by_method[launch_method][file_name]

    def save_preset_source_by_file_name(self, launch_method: str, file_name: str, source_text: str):
        self.files_by_method[launch_method][file_name] = source_text
        return SimpleNamespace(file_name=file_name, name=Path(file_name).stem)


class UserProfilesTests(unittest.TestCase):
    def test_create_user_profile_saves_settings_and_creates_list_files(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = AppPaths(user_root=root, local_root=root)
            with patch("settings.store.MAIN_DIRECTORY", str(root)):
                profile_id = create_user_profile(paths, name="Мой сайт", protocol="tcp", ports="80,443")
                settings = read_settings()

            profiles = settings["user_profiles"]["profiles"]
            self.assertIn(profile_id, profiles)
            self.assertEqual(profiles[profile_id]["name"], "Мой сайт")
            self.assertEqual(profiles[profile_id]["protocol"], "tcp")
            self.assertEqual(profiles[profile_id]["ports"], "80,443")
            self.assertTrue((root / "lists" / "moi-sait.txt").is_file())
            self.assertTrue((root / "lists" / "ipset-moi-sait.txt").is_file())

    def test_user_profile_name_must_be_unique_between_user_profiles(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = AppPaths(user_root=root, local_root=root)
            with patch("settings.store.MAIN_DIRECTORY", str(root)):
                create_user_profile(paths, name="My Site", protocol="tcp", ports="80,443")
                with self.assertRaisesRegex(ValueError, "уже есть"):
                    create_user_profile(paths, name="my site", protocol="udp", ports="443")

    def test_user_profile_name_must_not_intersect_with_system_profile_names(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            templates_dir = root / "profile" / "templates"
            templates_dir.mkdir(parents=True)
            (templates_dir / "all_profiles.txt").write_text(
                "\n".join(
                    (
                        "--name=YouTube",
                        "--filter-tcp=80,443",
                        "--hostlist=lists/youtube.txt",
                        "",
                        "--new",
                        "--name=YouTube",
                        "--filter-tcp=80,443",
                        "--ipset=lists/ipset-youtube.txt",
                        "",
                    )
                ),
                encoding="utf-8",
            )
            paths = AppPaths(user_root=root, local_root=root)
            with patch("settings.store.MAIN_DIRECTORY", str(root)):
                with self.assertRaisesRegex(ValueError, "системн"):
                    create_user_profile(paths, name="youtube", protocol="tcp", ports="80,443")

    def test_user_profile_is_loaded_as_disabled_template(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = AppPaths(user_root=root, local_root=root)
            with patch("settings.store.MAIN_DIRECTORY", str(root)):
                profile_id = create_user_profile(paths, name="My Site", protocol="udp", ports="443")
                templates = load_user_profile_templates(paths, "winws2")

        profile = templates[f"user:{profile_id}"]
        self.assertEqual(profile.name, "My Site")
        self.assertIn("--filter-udp=443", profile.match.filter_lines)
        self.assertIn("--hostlist=lists/my-site.txt", profile.match.hostlist_lines)
        self.assertIn("--lua-desync=pass", [segment.text for segment in profile.segments])

    def test_l7_user_profile_uses_filter_l7(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = AppPaths(user_root=root, local_root=root)
            with patch("settings.store.MAIN_DIRECTORY", str(root)):
                profile_id = create_user_profile(paths, name="Voice L7", protocol="l7", ports="stun,discord")
                templates = load_user_profile_templates(paths, "winws2")

        profile = templates[f"user:{profile_id}"]
        self.assertIn("--filter-l7=stun,discord", profile.match.filter_lines)
        self.assertNotIn("--filter-tcp=stun,discord", profile.match.filter_lines)

    def test_winws1_user_profile_uses_first_strategy_from_protocol_catalog(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            catalog_dir = root / "profile" / "strategy_catalogs" / "winws1"
            catalog_dir.mkdir(parents=True)
            (catalog_dir / "tcp.txt").write_text(
                "\n".join(
                    (
                        "[first_tcp]",
                        "name = first tcp",
                        "--dpi-desync=fake",
                        "--dup=2",
                        "",
                        "[second_tcp]",
                        "name = second tcp",
                        "--dpi-desync=split2",
                        "",
                    )
                ),
                encoding="utf-8",
            )
            paths = AppPaths(user_root=root, local_root=root)
            with patch("settings.store.MAIN_DIRECTORY", str(root)):
                profile_id = create_user_profile(paths, name="My TCP", protocol="tcp", ports="80,443")
                templates = load_user_profile_templates(paths, "winws1")

        profile = templates[f"user:{profile_id}"]
        texts = [segment.text for segment in profile.segments]
        self.assertIn("--filter-tcp=80,443", profile.match.filter_lines)
        self.assertIn("--hostlist=lists/my-tcp.txt", profile.match.hostlist_lines)
        self.assertIn("--dpi-desync=fake", texts)
        self.assertIn("--dup=2", texts)
        self.assertNotIn("--dpi-desync=split2", texts)

    def test_list_profiles_includes_user_profile_and_enabling_adds_it_to_preset(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "profile" / "templates").mkdir(parents=True)
            (root / "profile" / "templates" / "all_profiles.txt").write_text("", encoding="utf-8")
            store = _PresetStore("")
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )

            with patch("settings.store.MAIN_DIRECTORY", str(root)):
                profile_id = create_user_profile(feature._app_paths, name="My Site", protocol="tcp", ports="80,443")
                service = ProfilePresetService(feature, "zapret2_mode")
                payload = service.list_profiles()
                new_key = service.set_profile_enabled(f"template:user:{profile_id}", True)

        self.assertEqual(len(payload.items), 1)
        self.assertFalse(payload.items[0].in_preset)
        self.assertTrue(payload.items[0].key.startswith("template:user:"))
        self.assertEqual(new_key, "profile:0")
        preset = parse_preset_text(store.text, engine="winws2")
        self.assertEqual(len(preset.profiles), 1)
        self.assertIn("--filter-tcp=80,443", preset.profiles[0].match.filter_lines)
        self.assertIn("--hostlist=lists/my-site.txt", preset.profiles[0].match.hostlist_lines)
        self.assertIn("--lua-desync=pass", [segment.text for segment in preset.profiles[0].segments])

    def test_update_user_profile_renames_files_and_updates_named_profiles_in_all_presets(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "profile" / "templates").mkdir(parents=True)
            (root / "profile" / "templates" / "all_profiles.txt").write_text("", encoding="utf-8")
            store = _PresetLibrary({
                ZAPRET2_MODE: {
                    "one.txt": "\n".join((
                        "--name=My Site",
                        "--filter-tcp=80,443",
                        "--hostlist=lists/my-site.txt",
                        "--lua-desync=pass",
                        "",
                    )),
                    "two.txt": "\n".join((
                        "--name=Other",
                        "--filter-tcp=443",
                        "--hostlist=lists/other.txt",
                        "--lua-desync=pass",
                        "",
                    )),
                },
                ZAPRET1_MODE: {
                    "three.txt": "\n".join((
                        "--name=My Site",
                        "--filter-tcp=80,443",
                        "--ipset=lists/ipset-my-site.txt",
                        "--dpi-desync=fake",
                        "",
                    )),
                },
            })
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )

            with patch("settings.store.MAIN_DIRECTORY", str(root)):
                profile_id = create_user_profile(feature._app_paths, name="My Site", protocol="tcp", ports="80,443")
                service = ProfilePresetService(feature, "zapret2_mode")
                changed = service.update_user_profile(profile_id, name="New Site", protocol="udp", ports="443")
                settings = read_settings()
            self.assertEqual(changed, 2)
            self.assertFalse((root / "lists" / "my-site.txt").exists())
            self.assertFalse((root / "lists" / "ipset-my-site.txt").exists())
            self.assertTrue((root / "lists" / "new-site.txt").is_file())
            self.assertTrue((root / "lists" / "ipset-new-site.txt").is_file())
            self.assertEqual(settings["user_profiles"]["profiles"][profile_id]["name"], "New Site")
            self.assertEqual(settings["user_profiles"]["profiles"][profile_id]["protocol"], "udp")
            self.assertEqual(settings["user_profiles"]["profiles"][profile_id]["ports"], "443")
            self.assertIn("--name=New Site", store.files_by_method[ZAPRET2_MODE]["one.txt"])
            self.assertIn("--filter-udp=443", store.files_by_method[ZAPRET2_MODE]["one.txt"])
            self.assertIn("--hostlist=lists/new-site.txt", store.files_by_method[ZAPRET2_MODE]["one.txt"])
            self.assertIn("--name=Other", store.files_by_method[ZAPRET2_MODE]["two.txt"])
            self.assertIn("--name=New Site", store.files_by_method[ZAPRET1_MODE]["three.txt"])
            self.assertIn("--filter-udp=443", store.files_by_method[ZAPRET1_MODE]["three.txt"])
            self.assertIn("--ipset=lists/ipset-new-site.txt", store.files_by_method[ZAPRET1_MODE]["three.txt"])

    def test_delete_user_profile_removes_files_and_named_profiles_from_all_presets(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "profile" / "templates").mkdir(parents=True)
            (root / "profile" / "templates" / "all_profiles.txt").write_text("", encoding="utf-8")
            store = _PresetLibrary({
                ZAPRET2_MODE: {
                    "one.txt": "\n".join((
                        "--name=My Site",
                        "--filter-tcp=80,443",
                        "--hostlist=lists/my-site.txt",
                        "--lua-desync=pass",
                        "",
                        "--new",
                        "--name=Other",
                        "--filter-tcp=443",
                        "--hostlist=lists/other.txt",
                        "--lua-desync=pass",
                        "",
                    )),
                },
                ZAPRET1_MODE: {
                    "two.txt": "\n".join((
                        "--name=My Site",
                        "--filter-tcp=80,443",
                        "--ipset=lists/ipset-my-site.txt",
                        "--dpi-desync=fake",
                        "",
                    )),
                },
            })
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )

            with patch("settings.store.MAIN_DIRECTORY", str(root)):
                profile_id = create_user_profile(feature._app_paths, name="My Site", protocol="tcp", ports="80,443")
                service = ProfilePresetService(feature, "zapret2_mode")
                changed = service.delete_user_profile(profile_id)
                settings = read_settings()
                self.assertEqual(changed, 2)
                self.assertNotIn(profile_id, settings["user_profiles"]["profiles"])
                self.assertFalse((root / "lists" / "my-site.txt").exists())
                self.assertFalse((root / "lists" / "ipset-my-site.txt").exists())
                self.assertNotIn("--name=My Site", store.files_by_method[ZAPRET2_MODE]["one.txt"])
                self.assertIn("--name=Other", store.files_by_method[ZAPRET2_MODE]["one.txt"])
                self.assertNotIn("--name=My Site", store.files_by_method[ZAPRET1_MODE]["two.txt"])

    def test_template_library_is_single_entry_for_stock_and_user_profiles(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            templates_dir = root / "profile" / "templates"
            templates_dir.mkdir(parents=True)
            (templates_dir / "all_profiles.txt").write_text(
                "\n".join(
                    (
                        "--name=Stock Site",
                        "--filter-tcp=443",
                        "--hostlist=lists/stock.txt",
                        "",
                    )
                ),
                encoding="utf-8",
            )
            paths = AppPaths(user_root=root, local_root=root)

            with patch("settings.store.MAIN_DIRECTORY", str(root)):
                profile_id = create_user_profile(paths, name="My Site", protocol="udp", ports="443")
                templates = load_profile_template_library(paths, "winws2")

        self.assertIn("all_profiles:0", templates)
        self.assertIn(f"user:{profile_id}", templates)
        self.assertEqual(templates["all_profiles:0"].name, "Stock Site")
        self.assertEqual(templates[f"user:{profile_id}"].name, "My Site")

    def test_profile_service_uses_template_library_as_single_entry(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            feature = SimpleNamespace(
                _presets_feature=_PresetStore(""),
                _app_paths=AppPaths(user_root=root, local_root=root),
            )
            service = ProfilePresetService(feature, "zapret2_mode")

            with patch("profile.service.load_profile_template_library", return_value={}) as loader:
                self.assertEqual(service._load_profile_templates(), {})

        loader.assert_called_once_with(feature._app_paths, "winws2")


if __name__ == "__main__":
    unittest.main()
