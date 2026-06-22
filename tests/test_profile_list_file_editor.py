from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from core.paths import AppPaths
from profile.list_file_editor import (
    count_profile_list_entries,
    profile_list_file_reference,
    validate_profile_list_file_text,
)
from lists.core.layered_files import rebuild_all_layered_list_files
from profile.parser import parse_preset_text
from profile.service import ProfilePresetService
from settings.mode import ENGINE_WINWS2


class _PresetStore:
    def __init__(self, text: str) -> None:
        self.text = text

    def read_selected_preset_source(self, _launch_method: str):
        return self.text, SimpleNamespace(file_name="selected.txt", name="selected")

    def save_selected_preset_source(self, _launch_method: str, text: str) -> None:
        self.text = text


class ProfileListFileEditorTests(unittest.TestCase):
    def test_validates_hostlist_domains(self) -> None:
        invalid = validate_profile_list_file_text(
            "hostlist",
            "youtube.com\nbad domain\n# comment\nsub.example.org\n",
        )

        self.assertEqual(invalid, ((2, "bad domain"),))

    def test_validates_ipset_entries(self) -> None:
        invalid = validate_profile_list_file_text(
            "ipset",
            "1.1.1.1\n10.0.0.0/8\ndiscord.com\n1.1.1.1-2.2.2.2\n",
        )

        self.assertEqual(invalid, ((3, "discord.com"), (4, "1.1.1.1-2.2.2.2")))

    def test_counts_list_entries_without_comments(self) -> None:
        count = count_profile_list_entries(
            "youtube.com\n# comment\n\nsub.example.org\n",
        )

        self.assertEqual(count, 2)

    def test_profile_reference_uses_current_hostlist_file(self) -> None:
        preset = parse_preset_text(
            "--filter-tcp=80,443\n--hostlist=lists/youtube.txt\n--lua-desync=pass\n",
            engine=ENGINE_WINWS2,
        )

        reference = profile_list_file_reference(preset.profiles[0], Path("/tmp/lists"))

        self.assertTrue(reference.editable)
        self.assertEqual(reference.kind, "hostlist")
        self.assertEqual(reference.file_name, "youtube.txt")

    def test_l7_voice_profile_has_no_editable_list_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "lists").mkdir()
            store = _PresetStore(
                "--filter-l7=stun,discord\n"
                "--payload=stun,discord_ip_discovery\n"
                "--lua-desync=pass\n"
            )
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )
            service = ProfilePresetService(feature, "zapret2_mode")

            setup = service.get_profile_setup("profile:0")
            list_editor = service.get_profile_list_file_editor_state("profile:0")

            self.assertIsNotNone(setup)
            self.assertIsNotNone(list_editor)
            self.assertFalse(setup.editable_filter_enabled)
            self.assertEqual(setup.editable_filter_value, "")
            self.assertFalse(list_editor.editable)
            self.assertIn("нет отдельного hostlist/ipset-файла", list_editor.error_text)

    def test_service_loads_and_saves_current_profile_list_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lists_dir = root / "lists"
            (lists_dir / "base").mkdir(parents=True)
            (lists_dir / "user").mkdir()
            (lists_dir / "base" / "ipset-youtube.txt").write_text("1.1.1.1\n", encoding="utf-8")
            (lists_dir / "user" / "ipset-youtube.txt").write_text("2.2.2.2\n", encoding="utf-8")
            store = _PresetStore(
                "--filter-tcp=80,443\n--ipset=lists/ipset-youtube.txt\n--lua-desync=pass\n"
            )
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )
            service = ProfilePresetService(feature, "zapret2_mode")

            setup = service.get_profile_setup("profile:0")
            list_editor = service.get_profile_list_file_editor_state("profile:0")
            self.assertIsNotNone(setup)
            self.assertIsNotNone(list_editor)
            self.assertEqual(list_editor.kind, "ipset")
            self.assertEqual(list_editor.display_path, "lists/ipset-youtube.txt")
            self.assertEqual(list_editor.base_display_path, "lists/base/ipset-youtube.txt")
            self.assertEqual(list_editor.user_display_path, "lists/user/ipset-youtube.txt")
            self.assertEqual(list_editor.base_text, "1.1.1.1\n")
            self.assertEqual(list_editor.user_text, "2.2.2.2\n")
            self.assertEqual(list_editor.text, "1.1.1.1\n2.2.2.2\n")
            self.assertEqual(list_editor.base_entries_count, 1)
            self.assertEqual(list_editor.user_entries_count, 1)

            saved = service.save_profile_list_file_text("profile:0", "8.8.8.8\n")
            saved_text = (lists_dir / "user" / "ipset-youtube.txt").read_text(encoding="utf-8")
            final_text = (lists_dir / "ipset-youtube.txt").read_text(encoding="utf-8")

            self.assertIsNotNone(saved)
            self.assertEqual(saved_text, "8.8.8.8\n")
            self.assertEqual(final_text, "1.1.1.1\n8.8.8.8\n")

    def test_service_creates_empty_user_layer_for_base_only_list(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lists_dir = root / "lists"
            (lists_dir / "base").mkdir(parents=True)
            (lists_dir / "base" / "youtube.txt").write_text("youtube.com\n", encoding="utf-8")
            store = _PresetStore(
                "--filter-tcp=80,443\n--hostlist=lists/youtube.txt\n--lua-desync=pass\n"
            )
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )
            service = ProfilePresetService(feature, "zapret2_mode")

            list_editor = service.get_profile_list_file_editor_state("profile:0")

            self.assertIsNotNone(list_editor)
            self.assertEqual(list_editor.display_path, "lists/youtube.txt")
            self.assertEqual(list_editor.base_text, "youtube.com\n")
            self.assertEqual(list_editor.user_text, "")
            self.assertEqual(list_editor.text, "youtube.com\n")
            self.assertEqual(list_editor.base_entries_count, 1)
            self.assertEqual(list_editor.user_entries_count, 0)
            self.assertEqual((lists_dir / "user" / "youtube.txt").read_text(encoding="utf-8"), "")
            self.assertEqual((lists_dir / "youtube.txt").read_text(encoding="utf-8"), "youtube.com\n")

    def test_rebuild_all_lists_combines_service_files_like_other_lists(self) -> None:
        with TemporaryDirectory() as temp_dir:
            lists_dir = Path(temp_dir) / "lists"
            (lists_dir / "base").mkdir(parents=True)
            (lists_dir / "user").mkdir()
            for name in ("other.txt", "ipset-all.txt", "ipset-ru.txt", "ipset-dns.txt", "ipset-exclude.txt", "netrogat.txt", "youtube.txt"):
                (lists_dir / "base" / name).write_text(f"base-{name}\n", encoding="utf-8")
                (lists_dir / "user" / name).write_text(f"user-{name}\n", encoding="utf-8")

            rebuilt = rebuild_all_layered_list_files(lists_dir)

            self.assertEqual(rebuilt, 7)
            for name in ("other.txt", "ipset-all.txt", "ipset-ru.txt", "ipset-dns.txt", "ipset-exclude.txt", "netrogat.txt", "youtube.txt"):
                self.assertEqual(
                    (lists_dir / name).read_text(encoding="utf-8"),
                    f"base-{name}\nuser-{name}\n",
                )

    def test_service_exclusion_ipset_ru_file_is_gui_editable(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lists_dir = root / "lists"
            (lists_dir / "base").mkdir(parents=True)
            (lists_dir / "user").mkdir()
            (lists_dir / "base" / "ipset-ru.txt").write_text("1.1.1.1\n", encoding="utf-8")
            (lists_dir / "user" / "ipset-ru.txt").write_text("2.2.2.2\n", encoding="utf-8")
            store = _PresetStore(
                "--name=Исключения\n"
                "--filter-tcp=80,443-65535\n"
                "--ipset-exclude=lists/ipset-ru.txt\n"
                "--ipset-exclude=lists/ipset-dns.txt\n"
                "--ipset-exclude=lists/ipset-exclude.txt\n"
                "--lua-desync=pass\n"
            )
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )
            service = ProfilePresetService(feature, "zapret2_mode")

            list_editor = service.get_profile_list_file_editor_state("profile:0")

            self.assertIsNotNone(list_editor)
            self.assertTrue(list_editor.editable)
            self.assertEqual(list_editor.kind, "ipset")
            self.assertEqual(list_editor.display_path, "lists/ipset-ru.txt")
            self.assertEqual(list_editor.base_text, "1.1.1.1\n")
            self.assertEqual(list_editor.user_text, "2.2.2.2\n")
            self.assertEqual(list_editor.text, "1.1.1.1\n2.2.2.2\n")

    def test_service_exclusion_dns_file_is_not_gui_editable(self) -> None:
        preset = parse_preset_text(
            "--name=Исключения\n"
            "--filter-tcp=80,443-65535\n"
            "--ipset-exclude=lists/ipset-dns.txt\n"
            "--lua-desync=pass\n",
            engine=ENGINE_WINWS2,
        )

        reference = profile_list_file_reference(preset.profiles[0], Path("/tmp/lists"))

        self.assertFalse(reference.editable)
        self.assertEqual(reference.kind, "ipset")
        self.assertEqual(reference.file_name, "ipset-dns.txt")
        self.assertEqual(reference.display_path, "lists/ipset-dns.txt")
        self.assertIn("служебный список", reference.error_text)

    def test_service_exclusion_netrogat_file_is_gui_editable(self) -> None:
        preset = parse_preset_text(
            "--name=Исключения\n"
            "--filter-tcp=80,443-65535\n"
            "--hostlist-exclude=lists/netrogat.txt\n"
            "--lua-desync=pass\n",
            engine=ENGINE_WINWS2,
        )

        reference = profile_list_file_reference(preset.profiles[0], Path("/tmp/lists"))

        self.assertTrue(reference.editable)
        self.assertEqual(reference.kind, "hostlist")
        self.assertEqual(reference.file_name, "netrogat.txt")
        self.assertEqual(reference.display_path, "lists/netrogat.txt")
        self.assertEqual(reference.user_display_path, "lists/user/netrogat.txt")


if __name__ == "__main__":
    unittest.main()
