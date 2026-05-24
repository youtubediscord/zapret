from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest

from core.paths import AppPaths
from profile.parser import parse_preset_text
from profile.service import ProfilePresetService


class _PresetStore:
    def __init__(self, text: str) -> None:
        self.text = text

    def read_selected_preset_source(self, _launch_method: str):
        return self.text, SimpleNamespace(file_name="test.txt", name="test")

    def save_selected_preset_source(self, _launch_method: str, text: str) -> None:
        self.text = text


class ProfileFilterKindSwitchTests(unittest.TestCase):
    def _service(
        self,
        text: str,
        *,
        root: Path | None = None,
        launch_method: str = "zapret2_mode",
    ) -> tuple[ProfilePresetService, _PresetStore]:
        store = _PresetStore(text)
        base = root or Path("src").resolve()
        feature = SimpleNamespace(
            _presets_feature=store,
            _app_paths=AppPaths(user_root=base, local_root=base),
        )
        return ProfilePresetService(feature, launch_method), store

    def test_switch_hostlist_profile_to_ipset_rewrites_same_profile_line(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lists_dir = root / "lists"
            (lists_dir / "base").mkdir(parents=True)
            (lists_dir / "base" / "youtube.txt").write_text("youtube.com\n", encoding="utf-8")
            (lists_dir / "base" / "ipset-youtube.txt").write_text("1.1.1.1\n", encoding="utf-8")
            service, store = self._service(
                "\n".join(
                    (
                        "--filter-tcp=80,443",
                        "--hostlist=lists/youtube.txt",
                        "--out-range=-d8",
                        "--lua-desync=fake:blob=tls_max:badsum:repeats=8",
                        "--lua-desync=multidisorder:pos=1:seqovl=681:seqovl_pattern=tls_max",
                        "",
                    )
                ),
                root=root,
            )

            new_key = service.set_profile_filter_kind("profile:0", "ipset")

            self.assertEqual(new_key, "profile:0")
            self.assertIn("--ipset=lists/ipset-youtube.txt", store.text)
            self.assertNotIn("--hostlist=lists/youtube.txt", store.text)
            self.assertIn("--out-range=-d8", store.text)
            self.assertIn("--lua-desync=fake:blob=tls_max:badsum:repeats=8", store.text)
            preset = parse_preset_text(store.text, engine="winws2")
            self.assertEqual(len(preset.profiles), 1)

    def test_switch_ipset_profile_to_hostlist_rewrites_same_profile_line(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lists_dir = root / "lists"
            (lists_dir / "base").mkdir(parents=True)
            (lists_dir / "base" / "youtube.txt").write_text("youtube.com\n", encoding="utf-8")
            (lists_dir / "base" / "ipset-youtube.txt").write_text("1.1.1.1\n", encoding="utf-8")
            service, store = self._service(
                "\n".join(
                    (
                        "--filter-tcp=80,443",
                        "--ipset=lists/ipset-youtube.txt",
                        "--out-range=-d8",
                        "--lua-desync=fake:repeats=6:blob=fake_default_quic",
                        "",
                    )
                ),
                root=root,
            )

            new_key = service.set_profile_filter_kind("profile:0", "hostlist")

            self.assertEqual(new_key, "profile:0")
            self.assertIn("--hostlist=lists/youtube.txt", store.text)
            self.assertNotIn("--ipset=lists/ipset-youtube.txt", store.text)
            self.assertIn("--out-range=-d8", store.text)
            preset = parse_preset_text(store.text, engine="winws2")
            self.assertEqual(len(preset.profiles), 1)

    def test_switch_my_sites_hostlist_to_ipset_uses_ipset_all(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lists_dir = root / "lists"
            (lists_dir / "base").mkdir(parents=True)
            (lists_dir / "base" / "other.txt").write_text("example.com\n", encoding="utf-8")
            (lists_dir / "base" / "ipset-all.txt").write_text("1.1.1.1\n", encoding="utf-8")
            service, store = self._service(
                "\n".join(
                    (
                        "--name=Мои сайты TCP",
                        "--filter-tcp=80,443-65535",
                        "--hostlist=lists/other.txt",
                        "",
                    )
                ),
                root=root,
            )

            new_key = service.set_profile_filter_kind("profile:0", "ipset")

            self.assertEqual(new_key, "profile:0")
            self.assertIn("--ipset=lists/ipset-all.txt", store.text)
            self.assertNotIn("--hostlist=lists/other.txt", store.text)

    def test_switch_my_sites_ipset_to_hostlist_uses_other(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lists_dir = root / "lists"
            (lists_dir / "base").mkdir(parents=True)
            (lists_dir / "base" / "other.txt").write_text("example.com\n", encoding="utf-8")
            (lists_dir / "base" / "ipset-all.txt").write_text("1.1.1.1\n", encoding="utf-8")
            service, store = self._service(
                "\n".join(
                    (
                        "--name=Мои сайты TCP",
                        "--filter-tcp=80,443-65535",
                        "--ipset=lists/ipset-all.txt",
                        "",
                    )
                ),
                root=root,
            )

            new_key = service.set_profile_filter_kind("profile:0", "hostlist")

            self.assertEqual(new_key, "profile:0")
            self.assertIn("--hostlist=lists/other.txt", store.text)
            self.assertNotIn("--ipset=lists/ipset-all.txt", store.text)

    def test_winws1_switch_hostlist_profile_to_ipset_rewrites_same_profile_line(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lists_dir = root / "lists"
            (lists_dir / "base").mkdir(parents=True)
            (lists_dir / "base" / "youtube.txt").write_text("youtube.com\n", encoding="utf-8")
            (lists_dir / "base" / "ipset-youtube.txt").write_text("1.1.1.1\n", encoding="utf-8")
            service, store = self._service(
                "\n".join(
                    (
                        "--filter-tcp=80,443",
                        "--hostlist=lists/youtube.txt",
                        "--dpi-desync=fake,split2",
                        "--dpi-desync-repeats=6",
                        "",
                    )
                ),
                root=root,
                launch_method="zapret1_mode",
            )

            new_key = service.set_profile_filter_kind("profile:0", "ipset")

        self.assertEqual(new_key, "profile:0")
        self.assertIn("--ipset=lists/ipset-youtube.txt", store.text)
        self.assertNotIn("--hostlist=lists/youtube.txt", store.text)
        self.assertIn("--dpi-desync=fake,split2", store.text)
        self.assertIn("--dpi-desync-repeats=6", store.text)
        self.assertNotIn("--out-range", store.text)

    def test_winws1_switch_my_sites_ipset_to_hostlist_uses_other(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lists_dir = root / "lists"
            (lists_dir / "base").mkdir(parents=True)
            (lists_dir / "base" / "other.txt").write_text("example.com\n", encoding="utf-8")
            (lists_dir / "base" / "ipset-all.txt").write_text("1.1.1.1\n", encoding="utf-8")
            service, store = self._service(
                "\n".join(
                    (
                        "--name=Мои сайты",
                        "--filter-tcp=80,443-65535",
                        "--ipset=lists/ipset-all.txt",
                        "--dpi-desync=fake,split2",
                        "",
                    )
                ),
                root=root,
                launch_method="zapret1_mode",
            )

            new_key = service.set_profile_filter_kind("profile:0", "hostlist")

        self.assertEqual(new_key, "profile:0")
        self.assertIn("--hostlist=lists/other.txt", store.text)
        self.assertNotIn("--ipset=lists/ipset-all.txt", store.text)

    def test_switch_exclusion_ipsets_to_hostlist_uses_netrogat(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lists_dir = root / "lists"
            (lists_dir / "base").mkdir(parents=True)
            for name in ("ipset-ru.txt", "ipset-dns.txt", "ipset-exclude.txt", "netrogat.txt"):
                (lists_dir / "base" / name).write_text("1.1.1.1\n", encoding="utf-8")
            service, store = self._service(
                "\n".join(
                    (
                        "--name=Исключения",
                        "--filter-tcp=80,443-65535",
                        "--ipset-exclude=lists/ipset-ru.txt",
                        "--ipset-exclude=lists/ipset-dns.txt",
                        "--ipset-exclude=lists/ipset-exclude.txt",
                        "--out-range=-d8",
                        "--lua-desync=pass",
                        "",
                    )
                ),
                root=root,
            )

            new_key = service.set_profile_filter_kind("profile:0", "hostlist")

        self.assertEqual(new_key, "profile:0")
        self.assertIn("--hostlist-exclude=lists/netrogat.txt", store.text)
        self.assertNotIn("--ipset-exclude=lists/ipset-ru.txt", store.text)
        self.assertNotIn("--ipset-exclude=lists/ipset-dns.txt", store.text)
        self.assertNotIn("--ipset-exclude=lists/ipset-exclude.txt", store.text)
        self.assertIn("--out-range=-d8", store.text)
        self.assertIn("--lua-desync=pass", store.text)

    def test_switch_exclusion_hostlist_to_ipset_uses_service_ipsets(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lists_dir = root / "lists"
            (lists_dir / "base").mkdir(parents=True)
            for name in ("ipset-ru.txt", "ipset-dns.txt", "ipset-exclude.txt", "netrogat.txt"):
                (lists_dir / "base" / name).write_text("1.1.1.1\n", encoding="utf-8")
            service, store = self._service(
                "\n".join(
                    (
                        "--name=Исключения",
                        "--filter-tcp=80,443-65535",
                        "--hostlist-exclude=lists/netrogat.txt",
                        "--out-range=-d8",
                        "--lua-desync=pass",
                        "",
                    )
                ),
                root=root,
            )

            new_key = service.set_profile_filter_kind("profile:0", "ipset")

        self.assertEqual(new_key, "profile:0")
        self.assertNotIn("--hostlist-exclude=lists/netrogat.txt", store.text)
        self.assertIn("--ipset-exclude=lists/ipset-ru.txt", store.text)
        self.assertIn("--ipset-exclude=lists/ipset-dns.txt", store.text)
        self.assertIn("--ipset-exclude=lists/ipset-exclude.txt", store.text)

    def test_missing_generated_ipset_is_not_offered_or_written(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lists_dir = root / "lists"
            (lists_dir / "base").mkdir(parents=True)
            (lists_dir / "base" / "discord-updates.txt").write_text("discord.com\n", encoding="utf-8")
            service, store = self._service(
                "\n".join(
                    (
                        "--filter-tcp=443",
                        "--hostlist=lists/discord-updates.txt",
                        "--lua-desync=pass",
                        "",
                    )
                ),
                root=root,
            )

            setup = service.get_profile_setup("profile:0")
            list_editor = service.get_profile_list_file_editor_state("profile:0")
            payload = service.list_profiles()
            new_key = service.set_profile_filter_kind("profile:0", "ipset")

        self.assertIsNotNone(setup)
        self.assertEqual(setup.editable_filter_kinds, ("hostlist",))
        self.assertEqual(setup.item.list_type, "")
        self.assertIsNotNone(list_editor)
        self.assertEqual(list_editor.kind, "hostlist")
        self.assertTrue(list_editor.editable)
        self.assertNotIn("hostlist", setup.match_summary)
        self.assertEqual(payload.items[0].list_type, "")
        self.assertIsNone(new_key)
        self.assertIn("--hostlist=lists/discord-updates.txt", store.text)
        self.assertNotIn("ipset-discord-updates.txt", store.text)

    def test_existing_generated_ipset_is_offered_and_written(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lists_dir = root / "lists"
            (lists_dir / "base").mkdir(parents=True)
            (lists_dir / "base" / "discord.txt").write_text("discord.com\n", encoding="utf-8")
            (lists_dir / "base" / "ipset-discord.txt").write_text("1.1.1.1\n", encoding="utf-8")
            service, store = self._service(
                "\n".join(
                    (
                        "--filter-tcp=443",
                        "--hostlist=lists/discord.txt",
                        "--lua-desync=pass",
                        "",
                    )
                ),
                root=root,
            )

            setup = service.get_profile_setup("profile:0")
            list_editor = service.get_profile_list_file_editor_state("profile:0")
            payload = service.list_profiles()
            new_key = service.set_profile_filter_kind("profile:0", "ipset")

        self.assertIsNotNone(setup)
        self.assertEqual(setup.editable_filter_kinds, ("hostlist", "ipset"))
        self.assertEqual(setup.item.list_type, "hostlist")
        self.assertIsNotNone(list_editor)
        self.assertTrue(list_editor.editable)
        self.assertIn("hostlist", setup.match_summary)
        self.assertEqual(payload.items[0].list_type, "hostlist")
        self.assertEqual(new_key, "profile:0")
        self.assertIn("--ipset=lists/ipset-discord.txt", store.text)

    def test_hostlist_and_ipset_variants_keep_same_gui_persistent_key(self) -> None:
        hostlist = parse_preset_text(
            "--filter-tcp=80,443\n--hostlist=lists/youtube.txt\n--lua-desync=pass\n",
            engine="winws2",
        ).profiles[0]
        ipset = parse_preset_text(
            "--filter-tcp=80,443\n--ipset=lists/ipset-youtube.txt\n--lua-desync=pass\n",
            engine="winws2",
        ).profiles[0]

        self.assertEqual(hostlist.persistent_key, ipset.persistent_key)

    def test_logical_key_does_not_strip_non_zapret_list_prefixes(self) -> None:
        hostlist = parse_preset_text(
            "--filter-tcp=80,443\n--hostlist=lists/list-youtube.txt\n--lua-desync=pass\n",
            engine="winws2",
        ).profiles[0]
        ipset = parse_preset_text(
            "--filter-tcp=80,443\n--ipset=lists/ipset-youtube.txt\n--lua-desync=pass\n",
            engine="winws2",
        ).profiles[0]

        self.assertNotEqual(hostlist.persistent_key, ipset.persistent_key)


if __name__ == "__main__":
    unittest.main()
