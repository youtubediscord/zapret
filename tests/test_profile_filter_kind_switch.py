from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest

from core.paths import AppPaths
from profile.editable_settings import EditableProfileSettings
from profile.filter_switch import build_filter_kind_candidate, resolve_filter_kind_switch
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

    def _assert_saved_pair(self, result, store, *, engine: str = "winws2") -> None:
        """Edit-операции service возвращают пару (old, new) persistent_key;
        new обязан соответствовать profile:0 сохранённого текста preset."""
        self.assertIsNotNone(result)
        _old_key, new_key = result
        preset = parse_preset_text(store.text, engine=engine)
        self.assertEqual(new_key, preset.profiles[0].persistent_key)

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

            self._assert_saved_pair(new_key, store)
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

            self._assert_saved_pair(new_key, store)
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

            self._assert_saved_pair(new_key, store)
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

            self._assert_saved_pair(new_key, store)
            self.assertIn("--hostlist=lists/other.txt", store.text)
            self.assertNotIn("--ipset=lists/ipset-all.txt", store.text)

    def test_save_list_file_text_with_filter_override_writes_selected_pair_file(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lists_dir = root / "lists"
            (lists_dir / "base").mkdir(parents=True)
            (lists_dir / "user").mkdir(parents=True)
            (lists_dir / "base" / "other.txt").write_text("example.com\n", encoding="utf-8")
            (lists_dir / "base" / "ipset-all.txt").write_text("1.1.1.1\n", encoding="utf-8")
            (lists_dir / "user" / "other.txt").write_text("from-lordserials.ru\n", encoding="utf-8")
            service, _store = self._service(
                "\n".join(
                    (
                        "--name=Мои сайты",
                        "--filter-tcp=80,443-65535",
                        "--hostlist=lists/other.txt",
                        "",
                    )
                ),
                root=root,
            )

            state = service.save_profile_list_file_text(
                "profile:0",
                "2.2.2.0/24\n",
                filter_kind="ipset",
                filter_value="lists/other.txt",
            )

            self.assertIsNotNone(state)
            self.assertEqual(state.kind, "ipset")
            self.assertEqual(state.user_display_path, "lists/user/ipset-all.txt")
            self.assertEqual((lists_dir / "user" / "other.txt").read_text(encoding="utf-8"), "from-lordserials.ru\n")
            self.assertEqual((lists_dir / "user" / "ipset-all.txt").read_text(encoding="utf-8"), "2.2.2.0/24\n")

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

        self._assert_saved_pair(new_key, store, engine="winws1")
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

        self._assert_saved_pair(new_key, store, engine="winws1")
        self.assertIn("--hostlist=lists/other.txt", store.text)
        self.assertNotIn("--ipset=lists/ipset-all.txt", store.text)

    def test_exclusion_ipsets_do_not_offer_or_switch_to_hostlist(self) -> None:
        # AC10: exclude-фильтры не переключаются между типами — связка
        # netrogat ↔ ipset-ru/dns/exclude убрана, комбо типа скрыто.
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
            text_before = store.text

            setup = service.get_profile_setup("profile:0")
            new_key = service.set_profile_filter_kind("profile:0", "hostlist")

        self.assertIsNotNone(setup)
        self.assertEqual(setup.editable_filter_kinds, ("ipset",))
        self.assertIsNone(new_key)
        self.assertEqual(store.text, text_before)
        self.assertNotIn("--hostlist-exclude=lists/netrogat.txt", store.text)
        self.assertIn("--ipset-exclude=lists/ipset-ru.txt", store.text)

    def test_udp_exclusion_ipsets_do_not_offer_hostlist_pair(self) -> None:
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
                        "--name=Все сайты UDP (айпи)",
                        "--filter-udp=443-65535",
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

            setup = service.get_profile_setup("profile:0")
            new_key = service.set_profile_filter_kind("profile:0", "hostlist")

        self.assertIsNotNone(setup)
        self.assertEqual(setup.editable_filter_kind, "ipset")
        self.assertEqual(setup.editable_filter_kinds, ("ipset",))
        self.assertIsNone(new_key)
        self.assertNotIn("--hostlist-exclude=lists/netrogat.txt", store.text)
        self.assertIn("--ipset-exclude=lists/ipset-ru.txt", store.text)
        self.assertIn("--ipset-exclude=lists/ipset-dns.txt", store.text)
        self.assertIn("--ipset-exclude=lists/ipset-exclude.txt", store.text)

    def test_exclusion_hostlist_does_not_offer_or_switch_to_ipset(self) -> None:
        # AC10: обратное направление симметрично недоступно.
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
            text_before = store.text

            setup = service.get_profile_setup("profile:0")
            new_key = service.set_profile_filter_kind("profile:0", "ipset")

        self.assertIsNotNone(setup)
        self.assertEqual(setup.editable_filter_kinds, ("hostlist",))
        self.assertIsNone(new_key)
        self.assertEqual(store.text, text_before)
        self.assertIn("--hostlist-exclude=lists/netrogat.txt", store.text)
        self.assertNotIn("--ipset-exclude=lists/ipset-ru.txt", store.text)

    def test_update_settings_keeps_exclusion_hostlist_kind(self) -> None:
        # AC10: автосейв настроек с чужим типом не переключает exclude-фильтр.
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
            text_before = store.text

            new_key = service.update_winws2_editable_settings(
                "profile:0",
                filter_kind="ipset",
                filter_value="lists/netrogat.txt",
                in_range="x",
                out_range="-d8",
            )

        self._assert_saved_pair(new_key, store)
        self.assertEqual(new_key[0], new_key[1])
        self.assertEqual(store.text, text_before)
        self.assertIn("--hostlist-exclude=lists/netrogat.txt", store.text)
        self.assertNotIn("--ipset-exclude=lists/ipset-ru.txt", store.text)

    def test_switch_blocked_when_counterpart_profile_exists_in_preset(self) -> None:
        # Пара catch-all профилей: hostlist-вариант ловит соединения с известным
        # hostname, ipset-вариант — остальные по IP. Переключение типа на одном
        # из них создало бы дубликат match-сигнатуры соседа — запрещено.
        from tempfile import TemporaryDirectory

        preset_text = "\n".join(
            (
                "--new",
                "--name=Все сайты (хостлисты)",
                "--filter-tcp=80,443-65535",
                "--hostlist-exclude=lists/netrogat.txt",
                "--out-range=-d8",
                "--lua-desync=pass",
                "",
                "--new",
                "--name=Все сайты (айпи)",
                "--filter-tcp=80,443-65535",
                "--ipset-exclude=lists/ipset-ru.txt",
                "--ipset-exclude=lists/ipset-dns.txt",
                "--ipset-exclude=lists/ipset-exclude.txt",
                "--out-range=-d8",
                "--lua-desync=pass",
                "",
            )
        )
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lists_dir = root / "lists"
            (lists_dir / "base").mkdir(parents=True)
            for name in ("ipset-ru.txt", "ipset-dns.txt", "ipset-exclude.txt", "netrogat.txt"):
                (lists_dir / "base" / name).write_text("1.1.1.1\n", encoding="utf-8")
            service, store = self._service(preset_text, root=root)
            text_before = store.text

            hostlist_setup = service.get_profile_setup("profile:0")
            ipset_setup = service.get_profile_setup("profile:1")
            hostlist_switch = service.set_profile_filter_kind("profile:0", "ipset")
            ipset_switch = service.set_profile_filter_kind("profile:1", "hostlist")
            settings_switch = service.update_winws2_editable_settings(
                "profile:0",
                filter_kind="ipset",
                filter_value="lists/netrogat.txt",
                in_range="x",
                out_range="-d8",
            )

        self.assertIsNotNone(hostlist_setup)
        self.assertEqual(hostlist_setup.editable_filter_kinds, ("hostlist",))
        self.assertIsNotNone(ipset_setup)
        self.assertEqual(ipset_setup.editable_filter_kinds, ("ipset",))
        self.assertIsNone(hostlist_switch)
        self.assertIsNone(ipset_switch)
        # Автосейв настроек не молча меняет тип: профиль остаётся hostlist.
        self._assert_saved_pair(settings_switch, store)
        self.assertEqual(settings_switch[0], settings_switch[1])
        self.assertEqual(store.text, text_before)

    def test_switch_blocked_even_when_counterpart_is_disabled(self) -> None:
        # Выключенный двойник — всё равно двойник: переключение создало бы
        # дубликат ключей и путаницу с метой. Правильный путь — включить пару.
        from tempfile import TemporaryDirectory

        preset_text = "\n".join(
            (
                "--new",
                "--name=Все сайты (хостлисты)",
                "--filter-tcp=80,443-65535",
                "--hostlist-exclude=lists/netrogat.txt",
                "--out-range=-d8",
                "--lua-desync=pass",
                "",
                "--new",
                "--name=Все сайты (айпи)",
                "--skip",
                "--filter-tcp=80,443-65535",
                "--ipset-exclude=lists/ipset-ru.txt",
                "--ipset-exclude=lists/ipset-dns.txt",
                "--ipset-exclude=lists/ipset-exclude.txt",
                "--out-range=-d8",
                "--lua-desync=pass",
                "",
            )
        )
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lists_dir = root / "lists"
            (lists_dir / "base").mkdir(parents=True)
            for name in ("ipset-ru.txt", "ipset-dns.txt", "ipset-exclude.txt", "netrogat.txt"):
                (lists_dir / "base" / name).write_text("1.1.1.1\n", encoding="utf-8")
            service, _store = self._service(preset_text, root=root)

            setup = service.get_profile_setup("profile:0")
            switch = service.set_profile_filter_kind("profile:0", "ipset")

        self.assertIsNotNone(setup)
        self.assertEqual(setup.editable_filter_kinds, ("hostlist",))
        self.assertIsNone(switch)

    def test_custom_exclusion_file_is_not_rewritten_to_service_pair(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lists_dir = root / "lists"
            (lists_dir / "base").mkdir(parents=True)
            (lists_dir / "base" / "custom-exclude.txt").write_text("example.com\n", encoding="utf-8")
            service, store = self._service(
                "\n".join(
                    (
                        "--name=Исключения custom",
                        "--filter-tcp=80,443-65535",
                        "--hostlist-exclude=lists/custom-exclude.txt",
                        "--out-range=-d8",
                        "--lua-desync=pass",
                        "",
                    )
                ),
                root=root,
            )

            setup = service.get_profile_setup("profile:0")
            new_key = service.set_profile_filter_kind("profile:0", "ipset")

        self.assertIsNotNone(setup)
        self.assertEqual(setup.editable_filter_kinds, ("hostlist",))
        self.assertIsNone(new_key)
        self.assertIn("--hostlist-exclude=lists/custom-exclude.txt", store.text)
        self.assertNotIn("--ipset-exclude=lists/ipset-ru.txt", store.text)
        self.assertNotIn("--ipset-exclude=lists/custom-exclude.txt", store.text)

    def test_legacy_cloudflare_ipset_without_hostlist_pair_is_not_switchable(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lists_dir = root / "lists"
            (lists_dir / "base").mkdir(parents=True)
            (lists_dir / "base" / "cloudflare-ipset.txt").write_text("1.1.1.1\n", encoding="utf-8")
            service, store = self._service(
                "\n".join(
                    (
                        "--name=Cloudflare legacy TCP",
                        "--filter-tcp=80,443-65535",
                        "--ipset=lists/cloudflare-ipset.txt",
                        "--lua-desync=pass",
                        "",
                    )
                ),
                root=root,
            )

            setup = service.get_profile_setup("profile:0")
            new_key = service.set_profile_filter_kind("profile:0", "hostlist")

        self.assertIsNotNone(setup)
        self.assertEqual(setup.editable_filter_kinds, ("ipset",))
        self.assertIsNone(new_key)
        self.assertIn("--ipset=lists/cloudflare-ipset.txt", store.text)
        self.assertNotIn("--hostlist=lists/cloudflare-ipset.txt", store.text)
        self.assertNotIn("ipset-cloudflare-ipset.txt", store.text)

    def test_update_settings_does_not_create_missing_cloudflare_hostlist_pair(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lists_dir = root / "lists"
            (lists_dir / "base").mkdir(parents=True)
            (lists_dir / "base" / "cloudflare-ipset.txt").write_text("1.1.1.1\n", encoding="utf-8")
            service, store = self._service(
                "\n".join(
                    (
                        "--name=Cloudflare legacy TCP",
                        "--filter-tcp=80,443-65535",
                        "--ipset=lists/cloudflare-ipset.txt",
                        "--lua-desync=pass",
                        "",
                    )
                ),
                root=root,
            )

            new_key = service.update_winws2_editable_settings(
                "profile:0",
                filter_kind="hostlist",
                filter_value="lists/cloudflare-ipset.txt",
                in_range="x",
                out_range="a",
            )

        self._assert_saved_pair(new_key, store)
        self.assertEqual(new_key[0], new_key[1])
        self.assertIn("--ipset=lists/cloudflare-ipset.txt", store.text)
        self.assertNotIn("--hostlist=lists/cloudflare-ipset.txt", store.text)
        self.assertNotIn("ipset-cloudflare-ipset.txt", store.text)

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
        self._assert_saved_pair(new_key, store)
        self.assertIn("--ipset=lists/ipset-discord.txt", store.text)

    def test_update_settings_rejects_domain_as_ipset_file_value(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lists_dir = root / "lists"
            (lists_dir / "base").mkdir(parents=True)
            (lists_dir / "base" / "ipset-discord.txt").write_text("1.1.1.1\n", encoding="utf-8")
            service, store = self._service(
                "\n".join(
                    (
                        "--filter-tcp=443",
                        "--ipset=lists/ipset-discord.txt",
                        "--lua-desync=pass",
                        "",
                    )
                ),
                root=root,
            )

            new_key = service.update_winws2_editable_settings(
                "profile:0",
                filter_kind="ipset",
                filter_value="discord.com",
                in_range="x",
                out_range="a",
            )

        self._assert_saved_pair(new_key, store)
        self.assertEqual(new_key[0], new_key[1])
        self.assertIn("--ipset=lists/ipset-discord.txt", store.text)
        self.assertNotIn("--ipset=discord.com", store.text)

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


class FilterKindSwitchResolverTests(unittest.TestCase):
    def test_candidate_builds_pair_before_file_availability_check(self) -> None:
        settings = EditableProfileSettings(filter_kind="hostlist", filter_value="lists/youtube.txt")

        candidate = build_filter_kind_candidate(settings, "ipset")

        self.assertEqual(candidate.reason, "")
        self.assertEqual(candidate.filter_kind, "ipset")
        self.assertEqual(candidate.filter_value, "lists/ipset-youtube.txt")

    def test_resolver_requires_existing_pair_file(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lists_dir = root / "lists"
            (lists_dir / "base").mkdir(parents=True)
            (lists_dir / "base" / "youtube.txt").write_text("youtube.com\n", encoding="utf-8")
            app_paths = AppPaths(user_root=root, local_root=root)
            settings = EditableProfileSettings(filter_kind="hostlist", filter_value="lists/youtube.txt")

            missing = resolve_filter_kind_switch(settings, "ipset", app_paths)

            (lists_dir / "base" / "ipset-youtube.txt").write_text("1.1.1.1\n", encoding="utf-8")
            resolved = resolve_filter_kind_switch(settings, "ipset", app_paths)

        self.assertFalse(missing.allowed)
        self.assertEqual(missing.reason, "missing_file")
        self.assertTrue(resolved.allowed)
        self.assertEqual(resolved.filter_kind, "ipset")
        self.assertEqual(resolved.filter_value, "lists/ipset-youtube.txt")

    def test_resolver_rejects_cloudflare_legacy_ipset_without_hostlist_pair(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lists_dir = root / "lists"
            (lists_dir / "base").mkdir(parents=True)
            (lists_dir / "base" / "cloudflare-ipset.txt").write_text("1.1.1.1\n", encoding="utf-8")
            app_paths = AppPaths(user_root=root, local_root=root)
            settings = EditableProfileSettings(filter_kind="ipset", filter_value="lists/cloudflare-ipset.txt")

            resolved = resolve_filter_kind_switch(settings, "hostlist", app_paths)

        self.assertFalse(resolved.allowed)
        self.assertEqual(resolved.reason, "missing_pair")
        self.assertEqual(resolved.filter_kind, "hostlist")
        self.assertEqual(resolved.filter_value, "")

    def test_resolver_rejects_exclude_role_switch(self) -> None:
        # AC10: exclude-роль не имеет парного типа — даже при существующих
        # служебных файлах resolver не предлагает netrogat ↔ ipset-триплет.
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lists_dir = root / "lists"
            (lists_dir / "base").mkdir(parents=True)
            for name in ("ipset-ru.txt", "ipset-dns.txt", "ipset-exclude.txt", "netrogat.txt"):
                (lists_dir / "base" / name).write_text("1.1.1.1\n", encoding="utf-8")
            app_paths = AppPaths(user_root=root, local_root=root)

            for current_kind, current_value, target_kind in (
                ("hostlist", "lists/netrogat.txt", "ipset"),
                (
                    "ipset",
                    "lists/ipset-ru.txt,lists/ipset-dns.txt,lists/ipset-exclude.txt",
                    "hostlist",
                ),
            ):
                with self.subTest(current=current_kind, target=target_kind):
                    settings = EditableProfileSettings(
                        filter_kind=current_kind,
                        filter_value=current_value,
                        filter_role="exclude",
                    )

                    resolved = resolve_filter_kind_switch(settings, target_kind, app_paths)

                    self.assertFalse(resolved.allowed)
                    self.assertEqual(resolved.reason, "missing_pair")
                    self.assertEqual(resolved.filter_value, "")

    def test_resolver_reports_not_editable_reason(self) -> None:
        app_paths = AppPaths(user_root=Path("src").resolve(), local_root=Path("src").resolve())
        settings = EditableProfileSettings(
            filter_kind="hostlist",
            filter_value="lists/youtube.txt",
            filter_editable=False,
        )

        resolved = resolve_filter_kind_switch(settings, "ipset", app_paths)

        self.assertFalse(resolved.allowed)
        self.assertEqual(resolved.reason, "not_editable")


if __name__ == "__main__":
    unittest.main()
