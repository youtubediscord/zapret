from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))


class HostsCatalogJsonTests(unittest.TestCase):
    def setUp(self) -> None:
        from hosts import proxy_domains

        proxy_domains.invalidate_hosts_catalog_cache()
        self.proxy_domains = proxy_domains

    def tearDown(self) -> None:
        self.proxy_domains.invalidate_hosts_catalog_cache()

    def _write_catalog(self, root: Path) -> Path:
        catalog_path = root / "private_zapretgui" / "resources" / "json" / "hosts_catalog.json"
        catalog_path.parent.mkdir(parents=True, exist_ok=True)
        catalog_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "profiles": [
                        {"id": "zapret_dns", "name": "Zapret DNS"},
                        {"id": "xbox_dns", "name": "XBOX DNS"},
                        {"id": "xbox_dns_old", "name": "XBOX DNS (old)"},
                        {"id": "direct", "name": "Вкл. (активировать hosts)"},
                    ],
                    "services": [
                        {
                            "name": "ChatGPT",
                            "mode": "dns",
                            "domains": [
                                {
                                    "host": "chat.openai.com",
                                    "ips": {
                                        "zapret_dns": "72.56.93.144",
                                        "xbox_dns": "2.23.88.118",
                                        "xbox_dns_old": "45.155.204.190",
                                    },
                                }
                            ],
                        },
                        {
                            "name": "IP для подмены заблокированных ресурсов",
                            "mode": "direct",
                            "hosts": [
                                {"ip": "157.240.245.174", "host": "instagram.com"},
                                {"ip": "2a03:2880:f330:25:face:b00c:0:4420", "host": "instagram.com"},
                            ],
                        },
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return catalog_path

    def test_source_mode_uses_repo_json_hosts_catalog_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_module = root / "public_zapretgui" / "src" / "hosts" / "proxy_domains.py"
            fake_module.parent.mkdir(parents=True, exist_ok=True)
            fake_module.write_text("", encoding="utf-8")

            with patch.object(self.proxy_domains, "__file__", str(fake_module)):
                self.assertEqual(
                    self.proxy_domains.get_hosts_catalog_path(),
                    root / "private_zapretgui" / "resources" / "json" / "hosts_catalog.json",
                )

    def test_json_catalog_uses_profile_ids_and_display_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_catalog(root)
            fake_module = root / "public_zapretgui" / "src" / "hosts" / "proxy_domains.py"
            fake_module.parent.mkdir(parents=True, exist_ok=True)
            fake_module.write_text("", encoding="utf-8")

            with patch.object(self.proxy_domains, "__file__", str(fake_module)):
                self.proxy_domains.invalidate_hosts_catalog_cache()

                self.assertEqual(
                    self.proxy_domains.get_dns_profiles(),
                    ["zapret_dns", "xbox_dns", "xbox_dns_old", "direct"],
                )
                self.assertEqual(
                    self.proxy_domains.get_dns_profile_display_name("zapret_dns"),
                    "Zapret DNS",
                )
                self.assertEqual(self.proxy_domains.get_all_services(), ["ChatGPT", "IP для подмены заблокированных ресурсов"])
                self.assertEqual(
                    self.proxy_domains.get_service_domain_ip_rows("ChatGPT", "zapret_dns"),
                    [("chat.openai.com", "72.56.93.144")],
                )
                self.assertEqual(
                    self.proxy_domains.get_service_domain_ip_rows(
                        "IP для подмены заблокированных ресурсов",
                        "direct",
                    ),
                    [
                        ("instagram.com", "157.240.245.174"),
                        ("instagram.com", "2a03:2880:f330:25:face:b00c:0:4420"),
                    ],
                )

    def test_multi_value_profile_does_not_hide_single_value_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            catalog_path = self._write_catalog(root)
            data = json.loads(catalog_path.read_text(encoding="utf-8"))
            data["services"][0]["domains"][0]["ips"]["xbox_dns"] = ["2.23.88.118", "2.23.88.119"]
            catalog_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            fake_module = root / "public_zapretgui" / "src" / "hosts" / "proxy_domains.py"
            fake_module.parent.mkdir(parents=True, exist_ok=True)
            fake_module.write_text("", encoding="utf-8")

            with patch.object(self.proxy_domains, "__file__", str(fake_module)):
                self.proxy_domains.invalidate_hosts_catalog_cache()

                self.assertEqual(
                    self.proxy_domains.get_service_available_dns_profiles("ChatGPT"),
                    ["zapret_dns", "xbox_dns", "xbox_dns_old"],
                )
                self.assertEqual(
                    self.proxy_domains.get_service_domain_ip_rows("ChatGPT", "zapret_dns"),
                    [("chat.openai.com", "72.56.93.144")],
                )
                self.assertEqual(
                    self.proxy_domains.get_service_domain_ip_rows("ChatGPT", "xbox_dns"),
                    [
                        ("chat.openai.com", "2.23.88.118"),
                        ("chat.openai.com", "2.23.88.119"),
                    ],
                )

    def test_services_catalog_plan_keeps_saved_selection_when_hosts_is_empty(self) -> None:
        from hosts import page_plans

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_catalog(root)
            fake_module = root / "public_zapretgui" / "src" / "hosts" / "proxy_domains.py"
            fake_module.parent.mkdir(parents=True, exist_ok=True)
            fake_module.write_text("", encoding="utf-8")

            with patch.object(self.proxy_domains, "__file__", str(fake_module)):
                self.proxy_domains.invalidate_hosts_catalog_cache()

                plan = page_plans.build_services_catalog_plan(
                    current_selection={"ChatGPT": "zapret_dns"},
                    active_domains_map={},
                    direct_title="Direct",
                    ai_title="AI",
                    other_title="Other",
                )

        self.assertEqual(plan.new_selection.get("ChatGPT"), "zapret_dns")
        rows = [row for group in plan.groups for row in group.rows if row.service_name == "ChatGPT"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].selected_profile, "zapret_dns")

    def test_apply_domain_rows_skips_ipv6_when_unavailable(self) -> None:
        from hosts import hosts as hosts_module

        written: list[str] = []
        manager = hosts_module.HostsManager()
        manager.is_hosts_file_accessible = lambda: True

        with (
            patch.object(hosts_module, "safe_read_hosts_file", return_value=""),
            patch.object(hosts_module, "safe_write_hosts_file", side_effect=lambda text: written.append(text) or True),
            patch.object(hosts_module, "is_ipv6_available", return_value=False, create=True),
        ):
            self.assertTrue(
                manager.apply_domain_ip_rows(
                    [
                        ("instagram.com", "157.240.245.174"),
                        ("instagram.com", "2a03:2880:f330:25:face:b00c:0:4420"),
                    ]
                )
            )

        self.assertEqual(len(written), 1)
        self.assertIn("157.240.245.174 instagram.com", written[0])
        self.assertNotIn("2a03:2880:f330:25:face:b00c:0:4420 instagram.com", written[0])

    def test_apply_domain_rows_replaces_only_zapretgui_managed_block(self) -> None:
        from hosts import hosts as hosts_module

        original = "\n".join(
            [
                "# user header",
                "10.0.0.1 manual.example",
                "# >>> zapretgui:hosts managed begin >>>",
                "# Generated by ZapretGUI. Do not edit this block manually.",
                "1.1.1.1 old.example",
                "# <<< zapretgui:hosts managed end <<<",
                "10.0.0.2 another.example",
                "",
            ]
        )
        written: list[str] = []
        manager = hosts_module.HostsManager()
        manager.is_hosts_file_accessible = lambda: True

        with (
            patch.object(hosts_module, "safe_read_hosts_file", return_value=original),
            patch.object(hosts_module, "safe_write_hosts_file", side_effect=lambda text: written.append(text) or True),
            patch.object(hosts_module, "is_ipv6_available", return_value=True),
        ):
            self.assertTrue(manager.apply_domain_ip_rows([("new.example", "2.2.2.2")]))

        self.assertEqual(len(written), 1)
        self.assertIn("10.0.0.1 manual.example", written[0])
        self.assertIn("10.0.0.2 another.example", written[0])
        self.assertIn("# >>> zapretgui:hosts managed begin >>>", written[0])
        self.assertIn("2.2.2.2 new.example", written[0])
        self.assertNotIn("1.1.1.1 old.example", written[0])

    def test_apply_domain_rows_places_managed_block_before_manual_hosts_entries(self) -> None:
        from hosts import hosts as hosts_module

        original = "\n".join(
            [
                "# user header",
                "10.0.0.1 manual.example",
                "10.0.0.2 another.example",
                "",
            ]
        )
        written: list[str] = []
        manager = hosts_module.HostsManager()
        manager.is_hosts_file_accessible = lambda: True

        with (
            patch.object(hosts_module, "safe_read_hosts_file", return_value=original),
            patch.object(hosts_module, "safe_write_hosts_file", side_effect=lambda text: written.append(text) or True),
            patch.object(hosts_module, "is_ipv6_available", return_value=True),
        ):
            self.assertTrue(manager.apply_domain_ip_rows([("chatgpt.com", "2.2.2.2")]))

        self.assertEqual(len(written), 1)
        self.assertIn("# user header", written[0])
        self.assertIn("10.0.0.1 manual.example", written[0])
        self.assertIn("10.0.0.2 another.example", written[0])
        self.assertIn("2.2.2.2 chatgpt.com", written[0])
        self.assertLess(written[0].index("# user header"), written[0].index("# >>> zapretgui:hosts managed begin >>>"))
        self.assertLess(written[0].index("2.2.2.2 chatgpt.com"), written[0].index("10.0.0.1 manual.example"))
        self.assertLess(written[0].index("2.2.2.2 chatgpt.com"), written[0].index("10.0.0.2 another.example"))

    def test_apply_domain_rows_updates_top_domain_entry_without_adding_duplicate(self) -> None:
        from hosts import hosts as hosts_module

        original = "\n".join(
            [
                "# user header",
                "10.0.0.1 chatgpt.com",
                "10.0.0.2 another.example",
                "10.0.0.3 chatgpt.com",
                "",
            ]
        )
        written: list[str] = []
        manager = hosts_module.HostsManager()
        manager.is_hosts_file_accessible = lambda: True

        with (
            patch.object(hosts_module, "safe_read_hosts_file", return_value=original),
            patch.object(hosts_module, "safe_write_hosts_file", side_effect=lambda text: written.append(text) or True),
            patch.object(hosts_module, "is_ipv6_available", return_value=True),
        ):
            self.assertTrue(manager.apply_domain_ip_rows([("chatgpt.com", "2.2.2.2")]))

        self.assertEqual(len(written), 1)
        chatgpt_lines = [
            line
            for line in written[0].splitlines()
            if line.strip()
            and not line.lstrip().startswith("#")
            and "chatgpt.com" in line.split()[1:]
        ]
        self.assertEqual(chatgpt_lines, ["2.2.2.2 chatgpt.com", "10.0.0.3 chatgpt.com"])
        self.assertIn("10.0.0.2 another.example", written[0])
        self.assertEqual(manager.last_status, "Файл hosts обновлён: применено 1 запись")

    def test_apply_domain_rows_keeps_other_domains_from_same_hosts_line(self) -> None:
        from hosts import hosts as hosts_module

        original = "\n".join(
            [
                "# user header",
                "10.0.0.1 chatgpt.com manual.example # keep",
                "10.0.0.3 chatgpt.com",
                "",
            ]
        )
        written: list[str] = []
        manager = hosts_module.HostsManager()
        manager.is_hosts_file_accessible = lambda: True

        with (
            patch.object(hosts_module, "safe_read_hosts_file", return_value=original),
            patch.object(hosts_module, "safe_write_hosts_file", side_effect=lambda text: written.append(text) or True),
            patch.object(hosts_module, "is_ipv6_available", return_value=True),
        ):
            self.assertTrue(manager.apply_domain_ip_rows([("chatgpt.com", "2.2.2.2")]))

        self.assertEqual(len(written), 1)
        self.assertIn("2.2.2.2 chatgpt.com", written[0])
        self.assertIn("10.0.0.1 manual.example # keep", written[0])
        self.assertNotIn("10.0.0.1 chatgpt.com manual.example", written[0])

    def test_apply_service_selection_with_unknown_rows_does_not_clear_existing_block(self) -> None:
        from hosts import hosts as hosts_module

        written: list[str] = []
        manager = hosts_module.HostsManager()
        manager.is_hosts_file_accessible = lambda: True

        with (
            patch.object(hosts_module, "get_service_domain_ip_rows", return_value=[]),
            patch.object(hosts_module, "safe_write_hosts_file", side_effect=lambda text: written.append(text) or True),
        ):
            self.assertFalse(manager.apply_service_dns_selections({"Missing": "zapret_dns"}))

        self.assertEqual(written, [])
        self.assertEqual(manager.last_status, "Не найдено записей hosts для выбранных сервисов")

    def test_active_domains_are_read_from_zapretgui_managed_block(self) -> None:
        from hosts import hosts as hosts_module

        content = "\n".join(
            [
                "9.9.9.9 outside.example",
                "# >>> zapretgui:hosts managed begin >>>",
                "# Generated by ZapretGUI. Do not edit this block manually.",
                "2.2.2.2 managed.example",
                "# <<< zapretgui:hosts managed end <<<",
                "",
            ]
        )
        manager = hosts_module.HostsManager()
        with patch.object(hosts_module, "safe_read_hosts_file", return_value=content):
            self.assertEqual(manager.get_active_domains_map(), {"managed.example": "2.2.2.2"})

    def test_active_domains_keep_top_managed_domain_entry(self) -> None:
        from hosts import hosts as hosts_module

        content = "\n".join(
            [
                "# >>> zapretgui:hosts managed begin >>>",
                "# Generated by ZapretGUI. Do not edit this block manually.",
                "2.2.2.2 ChatGPT.com",
                "3.3.3.3 chatgpt.com",
                "# <<< zapretgui:hosts managed end <<<",
                "",
            ]
        )
        manager = hosts_module.HostsManager()
        with patch.object(hosts_module, "safe_read_hosts_file", return_value=content):
            self.assertEqual(manager.get_active_domains_map(), {"chatgpt.com": "2.2.2.2"})

    def test_clear_hosts_file_removes_only_zapretgui_managed_block(self) -> None:
        from hosts import hosts as hosts_module

        original = "\n".join(
            [
                "# user header",
                "10.0.0.1 manual.example",
                "# >>> zapretgui:hosts managed begin >>>",
                "# Generated by ZapretGUI. Do not edit this block manually.",
                "2.2.2.2 managed.example",
                "# <<< zapretgui:hosts managed end <<<",
                "10.0.0.2 another.example",
                "",
            ]
        )
        written: list[str] = []
        manager = hosts_module.HostsManager()
        manager.is_hosts_file_accessible = lambda: True

        with (
            patch.object(hosts_module, "safe_read_hosts_file", return_value=original),
            patch.object(hosts_module, "safe_write_hosts_file", side_effect=lambda text: written.append(text) or True),
        ):
            self.assertTrue(manager.clear_hosts_file())

        self.assertEqual(len(written), 1)
        self.assertIn("10.0.0.1 manual.example", written[0])
        self.assertIn("10.0.0.2 another.example", written[0])
        self.assertNotIn("2.2.2.2 managed.example", written[0])
        self.assertNotIn("zapretgui:hosts managed begin", written[0])

    def test_ipv6_detection_uses_winapi_on_windows(self) -> None:
        from hosts import ipv6_detection

        ipv6_detection.reset_ipv6_detection_cache()
        with (
            patch.object(ipv6_detection.os, "name", "nt"),
            patch.object(ipv6_detection, "_is_ipv6_available_winapi", return_value=True) as winapi_probe,
            patch.object(ipv6_detection, "_is_ipv6_available_socket_probe", return_value=False) as socket_probe,
        ):
            self.assertTrue(ipv6_detection.is_ipv6_available())

        winapi_probe.assert_called_once()
        socket_probe.assert_not_called()


if __name__ == "__main__":
    unittest.main()
