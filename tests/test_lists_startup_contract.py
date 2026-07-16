from __future__ import annotations

import ipaddress
import inspect
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class ListsStartupContractTests(unittest.TestCase):
    def test_embedded_ipset_ru_contains_storm_networks_as43298(self) -> None:
        from lists.core.embedded_defaults import get_ipset_ru_base_text

        expected = {
            "185.13.160.0/24",
            "185.71.64.0/24",
            "185.71.65.0/24",
            "185.71.66.0/24",
            "185.71.67.0/24",
            "185.121.243.0/24",
            "193.84.78.0/24",
            "193.84.90.0/24",
            "2a06:a180:20::/48",
            "2a06:a180:21::/48",
            "2a06:a180:22::/48",
        }
        lines = get_ipset_ru_base_text().splitlines()
        entries = {
            line.strip()
            for line in lines
            if line.strip() and not line.lstrip().startswith("#")
        }

        self.assertIn("# https://ipinfo.io/AS43298", lines)
        self.assertLess(
            lines.index("# https://ipinfo.io/AS43298"),
            lines.index("# DNS"),
        )
        self.assertLessEqual(expected, entries)
        for entry in expected:
            self.assertEqual(str(ipaddress.ip_network(entry, strict=True)), entry)

    def test_fast_required_files_check_does_not_import_layered_rebuild_at_module_load(self) -> None:
        from lists import file_manager

        module_prefix = inspect.getsource(file_manager).split("def _runtime_required_file_ready", 1)[0]

        self.assertNotIn("lists.core.layered_files", module_prefix)
        self.assertNotIn("rebuild_all_layered_list_files", module_prefix)
        self.assertNotIn("\nfrom log.log import log", module_prefix)

    def test_core_startup_uses_fast_required_files_check(self) -> None:
        from winws_runtime.runtime import startup

        with (
            patch("lists.file_manager.ensure_required_files", side_effect=AssertionError("full rebuild is deferred")),
            patch("lists.file_manager.ensure_required_files_fast", return_value=True) as ensure_fast,
        ):
            startup.init_core_startup()

        ensure_fast.assert_called_once_with()

    def test_fast_required_files_check_skips_full_rebuild_when_final_files_exist(self) -> None:
        from lists import file_manager

        with tempfile.TemporaryDirectory() as tmp:
            lists_root = Path(tmp)
            for name in ("other.txt", "ipset-all.txt", "ipset-ru.txt"):
                (lists_root / name).write_text("ready\n", encoding="utf-8")

            with (
                patch.object(file_manager, "LISTS_FOLDER", str(lists_root)),
                patch.object(file_manager, "ensure_required_files", side_effect=AssertionError("unexpected rebuild")),
            ):
                self.assertTrue(file_manager.ensure_required_files_fast())

    def test_fast_required_files_check_rebuilds_layered_profile_lists(self) -> None:
        from lists import file_manager

        with tempfile.TemporaryDirectory() as tmp:
            lists_root = Path(tmp)
            base_dir = lists_root / "base"
            base_dir.mkdir()
            for name in ("other.txt", "ipset-all.txt", "ipset-ru.txt"):
                (lists_root / name).write_text("ready\n", encoding="utf-8")
            (base_dir / "tiktok.txt").write_text("tiktok.com\n", encoding="utf-8")

            with (
                patch.object(file_manager, "LISTS_FOLDER", str(lists_root)),
                patch.object(file_manager, "ensure_required_files", side_effect=AssertionError("unexpected full rebuild")),
            ):
                self.assertTrue(file_manager.ensure_required_files_fast())

            self.assertEqual((lists_root / "tiktok.txt").read_text(encoding="utf-8"), "tiktok.com\n")

    def test_fast_required_files_check_skips_unreferenced_user_only_lists(self) -> None:
        from lists import file_manager

        with tempfile.TemporaryDirectory() as tmp:
            lists_root = Path(tmp)
            user_dir = lists_root / "user"
            user_dir.mkdir(parents=True)
            for name in ("other.txt", "ipset-all.txt", "ipset-ru.txt"):
                (lists_root / name).write_text("ready\n", encoding="utf-8")
            (user_dir / "i.ytimg.txt").write_text("qwen.ai\n", encoding="utf-8")

            with (
                patch.object(file_manager, "LISTS_FOLDER", str(lists_root)),
                patch.object(file_manager, "ensure_required_files", side_effect=AssertionError("unexpected full rebuild")),
                patch("settings.store.get_user_profiles_settings", return_value={"version": 1, "profiles": {}}),
            ):
                self.assertTrue(file_manager.ensure_required_files_fast())

            self.assertFalse((lists_root / "i.ytimg.txt").exists())

    def test_fast_required_files_check_rebuilds_active_preset_user_only_lists(self) -> None:
        from lists import file_manager

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lists_root = root / "lists"
            user_dir = lists_root / "user"
            user_dir.mkdir(parents=True)
            for name in ("other.txt", "ipset-all.txt", "ipset-ru.txt"):
                (lists_root / name).write_text("ready\n", encoding="utf-8")
            (user_dir / "custom.txt").write_text("qwen.ai\n", encoding="utf-8")
            preset_path = root / "selected.txt"
            preset_path.write_text(
                "--filter-tcp=443\n--hostlist=lists/custom.txt\n--lua-desync=pass\n",
                encoding="utf-8",
            )

            with (
                patch.object(file_manager, "LISTS_FOLDER", str(lists_root)),
                patch.object(file_manager, "ensure_required_files", side_effect=AssertionError("unexpected full rebuild")),
                patch("settings.store.get_user_profiles_settings", return_value={"version": 1, "profiles": {}}),
            ):
                self.assertTrue(file_manager.ensure_required_files_fast(active_preset_path=str(preset_path)))

            self.assertEqual((lists_root / "custom.txt").read_text(encoding="utf-8"), "qwen.ai\n")

    def test_fast_required_files_check_reads_file_from_mixed_hostlist_line(self) -> None:
        from lists import file_manager

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lists_root = root / "lists"
            user_dir = lists_root / "user"
            user_dir.mkdir(parents=True)
            for name in ("other.txt", "ipset-all.txt", "ipset-ru.txt"):
                (lists_root / name).write_text("ready\n", encoding="utf-8")
            (user_dir / "discord-updates.txt").write_text("discord.com\n", encoding="utf-8")
            (user_dir / "animego.online.txt").write_text("old.example\n", encoding="utf-8")
            preset_path = root / "selected.txt"
            preset_path.write_text(
                "--filter-tcp=443\n"
                "--hostlist=lists/discord-updates.txt,stable.dl2.discordapp.net,animego.online\n"
                "--lua-desync=pass\n",
                encoding="utf-8",
            )

            with (
                patch.object(file_manager, "LISTS_FOLDER", str(lists_root)),
                patch.object(file_manager, "ensure_required_files", side_effect=AssertionError("unexpected full rebuild")),
                patch("settings.store.get_user_profiles_settings", return_value={"version": 1, "profiles": {}}),
            ):
                self.assertTrue(file_manager.ensure_required_files_fast(active_preset_path=str(preset_path)))

            self.assertEqual((lists_root / "discord-updates.txt").read_text(encoding="utf-8"), "discord.com\n")
            self.assertFalse((lists_root / "animego.online.txt").exists())

    def test_fast_required_files_check_rebuilds_user_profile_list_files(self) -> None:
        from lists import file_manager

        with tempfile.TemporaryDirectory() as tmp:
            lists_root = Path(tmp)
            user_dir = lists_root / "user"
            user_dir.mkdir(parents=True)
            for name in ("other.txt", "ipset-all.txt", "ipset-ru.txt"):
                (lists_root / name).write_text("ready\n", encoding="utf-8")
            (user_dir / "my-site.txt").write_text("qwen.ai\n", encoding="utf-8")
            (user_dir / "ipset-my-site.txt").write_text("1.1.1.1\n", encoding="utf-8")
            settings = {
                "version": 1,
                "profiles": {
                    "my-site": {
                        "hostlist": "lists/my-site.txt",
                        "ipset": "lists/ipset-my-site.txt",
                    }
                },
            }

            with (
                patch.object(file_manager, "LISTS_FOLDER", str(lists_root)),
                patch.object(file_manager, "ensure_required_files", side_effect=AssertionError("unexpected full rebuild")),
                patch("settings.store.get_user_profiles_settings", return_value=settings),
            ):
                self.assertTrue(file_manager.ensure_required_files_fast())

            self.assertEqual((lists_root / "my-site.txt").read_text(encoding="utf-8"), "qwen.ai\n")
            self.assertEqual((lists_root / "ipset-my-site.txt").read_text(encoding="utf-8"), "1.1.1.1\n")

    def test_post_startup_lists_check_rebuilds_user_profile_files_but_skips_old_user_only_files(self) -> None:
        from lists import commands

        with tempfile.TemporaryDirectory() as tmp:
            lists_root = Path(tmp)
            user_dir = lists_root / "user"
            user_dir.mkdir(parents=True)
            (user_dir / "my-site.txt").write_text("qwen.ai\n", encoding="utf-8")
            (user_dir / "i.ytimg.txt").write_text("old.example\n", encoding="utf-8")
            settings = {
                "version": 1,
                "profiles": {
                    "my-site": {
                        "hostlist": "lists/my-site.txt",
                        "ipset": "lists/ipset-my-site.txt",
                    }
                },
            }

            with (
                patch.object(commands, "LISTS_FOLDER", str(lists_root)),
                patch("lists.hostlists_manager.startup_hostlists_check", return_value=True),
                patch("lists.ipsets_manager.startup_ipsets_check", return_value=True),
                patch("settings.store.get_user_profiles_settings", return_value=settings),
            ):
                self.assertEqual(commands.startup_lists_check(), (True, True))

            self.assertEqual((lists_root / "my-site.txt").read_text(encoding="utf-8"), "qwen.ai\n")
            self.assertFalse((lists_root / "i.ytimg.txt").exists())

    def test_fast_required_files_check_falls_back_when_final_file_missing(self) -> None:
        from lists import file_manager

        with tempfile.TemporaryDirectory() as tmp:
            lists_root = Path(tmp)
            (lists_root / "other.txt").write_text("ready\n", encoding="utf-8")
            (lists_root / "ipset-all.txt").write_text("ready\n", encoding="utf-8")

            with (
                patch.object(file_manager, "LISTS_FOLDER", str(lists_root)),
                patch.object(file_manager, "ensure_required_files", return_value=True) as ensure_full,
            ):
                self.assertTrue(file_manager.ensure_required_files_fast())

            ensure_full.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
