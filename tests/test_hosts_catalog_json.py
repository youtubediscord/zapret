from __future__ import annotations

import json
import os
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
                            "name": "Instagram",
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

    def _write_split_catalog(self, root: Path) -> Path:
        catalog_dir = root / "private_zapretgui" / "resources" / "json" / "hosts_catalog"
        (catalog_dir / "dns").mkdir(parents=True, exist_ok=True)
        (catalog_dir / "hosts").mkdir(parents=True, exist_ok=True)
        (catalog_dir / "dns_sources.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "dns_sources": [
                        {"id": "zapret_dns", "name": "Zapret DNS"},
                        {"id": "xbox_dns", "name": "XBOX DNS"},
                        {"id": "xbox_dns_old", "name": "XBOX DNS (old)"},
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (catalog_dir / "dns" / "chatgpt.json").write_text(
            json.dumps(
                {
                    "name": "ChatGPT",
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
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (catalog_dir / "hosts" / "instagram.json").write_text(
            json.dumps(
                {
                    "name": "Instagram",
                    "hosts": [
                        {"ip": "157.240.245.174", "host": "instagram.com"},
                        {"ip": "2a03:2880:f330:25:face:b00c:0:4420", "host": "instagram.com"},
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return catalog_dir

    def test_source_mode_uses_repo_json_hosts_catalog_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_module = root / "public_zapretgui" / "src" / "hosts" / "proxy_domains.py"
            fake_module.parent.mkdir(parents=True, exist_ok=True)
            fake_module.write_text("", encoding="utf-8")

            with patch.object(self.proxy_domains, "__file__", str(fake_module)):
                self.assertEqual(
                    self.proxy_domains.get_hosts_catalog_path(),
                    root / "private_zapretgui" / "resources" / "json" / "hosts_catalog",
                )

    def test_source_mode_uses_split_hosts_catalog_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_module = root / "public_zapretgui" / "src" / "hosts" / "proxy_domains.py"
            fake_module.parent.mkdir(parents=True, exist_ok=True)
            fake_module.write_text("", encoding="utf-8")

            with patch.object(self.proxy_domains, "__file__", str(fake_module)):
                self.assertEqual(
                    self.proxy_domains.get_hosts_catalog_path(),
                    root / "private_zapretgui" / "resources" / "json" / "hosts_catalog",
                )

    def test_split_catalog_reads_dns_sources_and_hosts_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_split_catalog(root)
            fake_module = root / "public_zapretgui" / "src" / "hosts" / "proxy_domains.py"
            fake_module.parent.mkdir(parents=True, exist_ok=True)
            fake_module.write_text("", encoding="utf-8")

            with patch.object(self.proxy_domains, "__file__", str(fake_module)):
                self.proxy_domains.invalidate_hosts_catalog_cache()

                self.assertEqual(
                    self.proxy_domains.get_dns_profiles(),
                    ["zapret_dns", "xbox_dns", "xbox_dns_old", "hosts"],
                )
                self.assertEqual(
                    self.proxy_domains.get_dns_profile_display_name("hosts"),
                    "Вкл. (активировать hosts)",
                )
                self.assertEqual(self.proxy_domains.get_all_services(), ["ChatGPT", "Instagram"])
                self.assertEqual(
                    self.proxy_domains.get_service_domain_ip_rows("ChatGPT", "zapret_dns"),
                    [("chat.openai.com", "72.56.93.144")],
                )
                self.assertEqual(
                    self.proxy_domains.get_service_domain_ip_rows("Instagram", "hosts"),
                    [
                        ("instagram.com", "157.240.245.174"),
                        ("instagram.com", "2a03:2880:f330:25:face:b00c:0:4420"),
                    ],
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
                self.assertEqual(self.proxy_domains.get_all_services(), ["ChatGPT", "Instagram"])
                self.assertEqual(
                    self.proxy_domains.get_service_domain_ip_rows("ChatGPT", "zapret_dns"),
                    [("chat.openai.com", "72.56.93.144")],
                )
                self.assertEqual(
                    self.proxy_domains.get_service_domain_ip_rows(
                        "Instagram",
                        "direct",
                    ),
                    [
                        ("instagram.com", "157.240.245.174"),
                        ("instagram.com", "2a03:2880:f330:25:face:b00c:0:4420"),
                    ],
                )

    def test_service_domains_uses_top_available_hosts_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_catalog(root)
            fake_module = root / "public_zapretgui" / "src" / "hosts" / "proxy_domains.py"
            fake_module.parent.mkdir(parents=True, exist_ok=True)
            fake_module.write_text("", encoding="utf-8")

            with patch.object(self.proxy_domains, "__file__", str(fake_module)):
                self.proxy_domains.invalidate_hosts_catalog_cache()

                self.assertEqual(
                    self.proxy_domains.get_service_domains("Instagram"),
                    {"instagram.com": "157.240.245.174"},
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

    def test_multi_value_profile_ip_map_uses_top_hosts_entry(self) -> None:
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
                    self.proxy_domains.get_service_domain_ip_map("ChatGPT", "xbox_dns"),
                    {"chat.openai.com": "2.23.88.118"},
                )

    def test_services_catalog_plan_matches_dns_domains_case_insensitively(self) -> None:
        from hosts import page_plans

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            catalog_path = self._write_catalog(root)
            data = json.loads(catalog_path.read_text(encoding="utf-8"))
            data["services"][0]["domains"][0]["host"] = "Chat.OpenAI.com"
            catalog_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            fake_module = root / "public_zapretgui" / "src" / "hosts" / "proxy_domains.py"
            fake_module.parent.mkdir(parents=True, exist_ok=True)
            fake_module.write_text("", encoding="utf-8")

            with patch.object(self.proxy_domains, "__file__", str(fake_module)):
                self.proxy_domains.invalidate_hosts_catalog_cache()

                plan = page_plans.build_services_catalog_plan(
                    current_selection={},
                    active_domains_map={"chat.openai.com": "72.56.93.144"},
                    direct_title="Direct",
                    ai_title="AI",
                    other_title="Other",
                )

        self.assertEqual(plan.new_selection.get("ChatGPT"), "zapret_dns")

    def test_services_catalog_plan_does_not_select_dns_profile_from_partial_hosts_match(self) -> None:
        from hosts import page_plans

        catalog = {
            "version": 1,
            "profiles": [
                {"id": "zapret_dns", "name": "Zapret DNS"},
                {"id": "direct", "name": "Вкл. (активировать hosts)"},
            ],
            "services": [
                {
                    "name": "Two Domain Service",
                    "mode": "dns",
                    "domains": [
                        {"host": "one.example", "ips": {"zapret_dns": "1.1.1.1"}},
                        {"host": "two.example", "ips": {"zapret_dns": "2.2.2.2"}},
                    ],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            catalog_path = root / "private_zapretgui" / "resources" / "json" / "hosts_catalog.json"
            catalog_path.parent.mkdir(parents=True, exist_ok=True)
            catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
            fake_module = root / "public_zapretgui" / "src" / "hosts" / "proxy_domains.py"
            fake_module.parent.mkdir(parents=True, exist_ok=True)
            fake_module.write_text("", encoding="utf-8")

            with patch.object(self.proxy_domains, "__file__", str(fake_module)):
                self.proxy_domains.invalidate_hosts_catalog_cache()

                plan = page_plans.build_services_catalog_plan(
                    current_selection={},
                    active_domains_map={"one.example": "1.1.1.1"},
                    direct_title="Direct",
                    ai_title="AI",
                    other_title="Other",
                )

        rows = [row for group in plan.groups for row in group.rows if row.service_name == "Two Domain Service"]
        self.assertEqual(rows[0].selected_profile, None)
        self.assertNotIn("Two Domain Service", plan.new_selection)

    def test_services_catalog_plan_does_not_keep_saved_dns_profile_when_hosts_is_partial(self) -> None:
        from hosts import page_plans

        catalog = {
            "version": 1,
            "profiles": [
                {"id": "zapret_dns", "name": "Zapret DNS"},
                {"id": "direct", "name": "Вкл. (активировать hosts)"},
            ],
            "services": [
                {
                    "name": "Two Domain Service",
                    "mode": "dns",
                    "domains": [
                        {"host": "one.example", "ips": {"zapret_dns": "1.1.1.1"}},
                        {"host": "two.example", "ips": {"zapret_dns": "2.2.2.2"}},
                    ],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            catalog_path = root / "private_zapretgui" / "resources" / "json" / "hosts_catalog.json"
            catalog_path.parent.mkdir(parents=True, exist_ok=True)
            catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
            fake_module = root / "public_zapretgui" / "src" / "hosts" / "proxy_domains.py"
            fake_module.parent.mkdir(parents=True, exist_ok=True)
            fake_module.write_text("", encoding="utf-8")

            with patch.object(self.proxy_domains, "__file__", str(fake_module)):
                self.proxy_domains.invalidate_hosts_catalog_cache()

                plan = page_plans.build_services_catalog_plan(
                    current_selection={"Two Domain Service": "zapret_dns"},
                    active_domains_map={"one.example": "1.1.1.1"},
                    direct_title="Direct",
                    ai_title="AI",
                    other_title="Other",
                )

        rows = [row for group in plan.groups for row in group.rows if row.service_name == "Two Domain Service"]
        self.assertEqual(rows[0].selected_profile, None)
        self.assertNotIn("Two Domain Service", plan.new_selection)

    def test_services_catalog_plan_matches_direct_domains_case_insensitively(self) -> None:
        from hosts import page_plans

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            catalog_path = self._write_catalog(root)
            data = json.loads(catalog_path.read_text(encoding="utf-8"))
            data["services"][1]["hosts"][0]["host"] = "Instagram.com"
            catalog_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            fake_module = root / "public_zapretgui" / "src" / "hosts" / "proxy_domains.py"
            fake_module.parent.mkdir(parents=True, exist_ok=True)
            fake_module.write_text("", encoding="utf-8")

            with patch.object(self.proxy_domains, "__file__", str(fake_module)):
                self.proxy_domains.invalidate_hosts_catalog_cache()

                plan = page_plans.build_services_catalog_plan(
                    current_selection={},
                    active_domains_map={"instagram.com": "157.240.245.174"},
                    direct_title="Direct",
                    ai_title="AI",
                    other_title="Other",
                )

        service_name = "Instagram"
        self.assertEqual(plan.new_selection.get(service_name), "direct")

    def test_services_catalog_plan_matches_direct_ipv4_when_catalog_has_ipv6_first(self) -> None:
        from hosts import page_plans

        catalog = {
            "version": 1,
            "profiles": [
                {"id": "zapret_dns", "name": "Zapret DNS"},
                {"id": "direct", "name": "Вкл. (активировать hosts)"},
            ],
            "services": [
                {
                    "name": "IPv6 First Direct Service",
                    "mode": "direct",
                    "hosts": [
                        {"ip": "2a03:2880:f330:25:face:b00c:0:4420", "host": "instagram.com"},
                        {"ip": "163.70.151.174", "host": "instagram.com"},
                    ],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            catalog_path = root / "private_zapretgui" / "resources" / "json" / "hosts_catalog.json"
            catalog_path.parent.mkdir(parents=True, exist_ok=True)
            catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
            fake_module = root / "public_zapretgui" / "src" / "hosts" / "proxy_domains.py"
            fake_module.parent.mkdir(parents=True, exist_ok=True)
            fake_module.write_text("", encoding="utf-8")

            with patch.object(self.proxy_domains, "__file__", str(fake_module)):
                self.proxy_domains.invalidate_hosts_catalog_cache()

                plan = page_plans.build_services_catalog_plan(
                    current_selection={},
                    active_domains_map={"instagram.com": "163.70.151.174"},
                    direct_title="Direct",
                    ai_title="AI",
                    other_title="Other",
                )

        rows = [row for group in plan.groups for row in group.rows if row.service_name == "IPv6 First Direct Service"]
        self.assertEqual(rows[0].selected_profile, "direct")
        self.assertTrue(rows[0].toggle_checked)
        self.assertEqual(plan.new_selection.get("IPv6 First Direct Service"), "direct")

    def test_services_catalog_plan_does_not_enable_direct_service_from_partial_hosts_match(self) -> None:
        from hosts import page_plans

        catalog = {
            "version": 1,
            "profiles": [
                {"id": "zapret_dns", "name": "Zapret DNS"},
                {"id": "direct", "name": "Вкл. (активировать hosts)"},
            ],
            "services": [
                {
                    "name": "Direct Two Domain Service",
                    "mode": "direct",
                    "hosts": [
                        {"ip": "1.1.1.1", "host": "one.example"},
                        {"ip": "2.2.2.2", "host": "two.example"},
                    ],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            catalog_path = root / "private_zapretgui" / "resources" / "json" / "hosts_catalog.json"
            catalog_path.parent.mkdir(parents=True, exist_ok=True)
            catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
            fake_module = root / "public_zapretgui" / "src" / "hosts" / "proxy_domains.py"
            fake_module.parent.mkdir(parents=True, exist_ok=True)
            fake_module.write_text("", encoding="utf-8")

            with patch.object(self.proxy_domains, "__file__", str(fake_module)):
                self.proxy_domains.invalidate_hosts_catalog_cache()

                plan = page_plans.build_services_catalog_plan(
                    current_selection={},
                    active_domains_map={"one.example": "1.1.1.1"},
                    direct_title="Direct",
                    ai_title="AI",
                    other_title="Other",
                )

        rows = [row for group in plan.groups for row in group.rows if row.service_name == "Direct Two Domain Service"]
        self.assertEqual(rows[0].selected_profile, None)
        self.assertFalse(rows[0].toggle_checked)
        self.assertNotIn("Direct Two Domain Service", plan.new_selection)

    def test_services_catalog_plan_does_not_keep_saved_direct_service_when_hosts_is_partial(self) -> None:
        from hosts import page_plans

        catalog = {
            "version": 1,
            "profiles": [
                {"id": "zapret_dns", "name": "Zapret DNS"},
                {"id": "direct", "name": "Вкл. (активировать hosts)"},
            ],
            "services": [
                {
                    "name": "Direct Two Domain Service",
                    "mode": "direct",
                    "hosts": [
                        {"ip": "1.1.1.1", "host": "one.example"},
                        {"ip": "2.2.2.2", "host": "two.example"},
                    ],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            catalog_path = root / "private_zapretgui" / "resources" / "json" / "hosts_catalog.json"
            catalog_path.parent.mkdir(parents=True, exist_ok=True)
            catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
            fake_module = root / "public_zapretgui" / "src" / "hosts" / "proxy_domains.py"
            fake_module.parent.mkdir(parents=True, exist_ok=True)
            fake_module.write_text("", encoding="utf-8")

            with patch.object(self.proxy_domains, "__file__", str(fake_module)):
                self.proxy_domains.invalidate_hosts_catalog_cache()

                plan = page_plans.build_services_catalog_plan(
                    current_selection={"Direct Two Domain Service": "direct"},
                    active_domains_map={"one.example": "1.1.1.1"},
                    direct_title="Direct",
                    ai_title="AI",
                    other_title="Other",
                )

        rows = [row for group in plan.groups for row in group.rows if row.service_name == "Direct Two Domain Service"]
        self.assertEqual(rows[0].selected_profile, None)
        self.assertFalse(rows[0].toggle_checked)
        self.assertNotIn("Direct Two Domain Service", plan.new_selection)

    def test_services_catalog_plan_uses_icons_for_current_catalog_service_names(self) -> None:
        from hosts import page_plans

        youtube_name = "YouTube (иногда может не работать с ним! Отключите тумблер если YouTube не работает с пресетами)"
        catalog = {
            "version": 1,
            "profiles": [
                {"id": "zapret_dns", "name": "Zapret DNS"},
                {"id": "direct", "name": "Вкл. (активировать hosts)"},
            ],
            "services": [
                {
                    "name": "ChatGPT & Sora (OpenAI)",
                    "mode": "dns",
                    "domains": [{"host": "chat.openai.com", "ips": {"zapret_dns": "72.56.93.144"}}],
                },
                {
                    "name": "Microsoft (Copilot, Designer, Xbox)",
                    "mode": "dns",
                    "domains": [{"host": "copilot.microsoft.com", "ips": {"zapret_dns": "72.56.93.144"}}],
                },
                {
                    "name": "Discord",
                    "mode": "direct",
                    "hosts": [{"ip": "1.1.1.1", "host": "discord.com"}],
                },
                {
                    "name": youtube_name,
                    "mode": "direct",
                    "hosts": [{"ip": "1.1.1.1", "host": "youtube.com"}],
                },
                {
                    "name": "GitHub",
                    "mode": "direct",
                    "hosts": [{"ip": "1.1.1.1", "host": "github.com"}],
                },
                {
                    "name": "Instagram",
                    "mode": "direct",
                    "hosts": [{"ip": "1.1.1.1", "host": "instagram.com"}],
                },
                {
                    "name": "Rutor",
                    "mode": "direct",
                    "hosts": [{"ip": "1.1.1.1", "host": "rutor.info"}],
                },
                {
                    "name": "Остальное",
                    "mode": "dns",
                    "domains": [{"host": "example.com", "ips": {"zapret_dns": "72.56.93.144"}}],
                },
            ],
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            catalog_path = root / "private_zapretgui" / "resources" / "json" / "hosts_catalog.json"
            catalog_path.parent.mkdir(parents=True, exist_ok=True)
            catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
            fake_module = root / "public_zapretgui" / "src" / "hosts" / "proxy_domains.py"
            fake_module.parent.mkdir(parents=True, exist_ok=True)
            fake_module.write_text("", encoding="utf-8")

            with patch.object(self.proxy_domains, "__file__", str(fake_module)):
                self.proxy_domains.invalidate_hosts_catalog_cache()
                plan = page_plans.build_services_catalog_plan(
                    current_selection={},
                    active_domains_map={},
                    direct_title="Direct",
                    ai_title="AI",
                    other_title="Other",
                )

        rows = {row.service_name: row for group in plan.groups for row in group.rows}
        self.assertEqual(rows["ChatGPT & Sora (OpenAI)"].icon_name, "mdi.robot")
        self.assertEqual(rows["Microsoft (Copilot, Designer, Xbox)"].icon_name, "fa5b.microsoft")
        self.assertEqual(rows["Discord"].icon_name, "fa5b.discord")
        self.assertEqual(rows[youtube_name].icon_name, "fa5b.youtube")
        self.assertEqual(rows["GitHub"].icon_name, "fa5b.github")
        self.assertEqual(rows["Instagram"].icon_name, "fa5b.instagram")
        self.assertEqual(rows["Rutor"].icon_name, "fa5s.magnet")
        self.assertEqual(rows["Остальное"].icon_name, "fa5s.box-open")

    def test_services_catalog_plan_groups_current_ai_service_names(self) -> None:
        from hosts import page_plans

        catalog = {
            "version": 1,
            "profiles": [{"id": "zapret_dns", "name": "Zapret DNS"}],
            "services": [
                {
                    "name": "Meta AI",
                    "mode": "dns",
                    "domains": [{"host": "meta.ai", "ips": {"zapret_dns": "72.56.93.144"}}],
                },
                {
                    "name": "Trae.ai",
                    "mode": "dns",
                    "domains": [{"host": "trae.ai", "ips": {"zapret_dns": "72.56.93.144"}}],
                },
                {
                    "name": "Windsurf",
                    "mode": "dns",
                    "domains": [{"host": "windsurf.com", "ips": {"zapret_dns": "72.56.93.144"}}],
                },
                {
                    "name": "Tailscale",
                    "mode": "dns",
                    "domains": [{"host": "tailscale.com", "ips": {"zapret_dns": "72.56.93.144"}}],
                },
                {
                    "name": "JetBrains",
                    "mode": "dns",
                    "domains": [{"host": "jetbrains.com", "ips": {"zapret_dns": "72.56.93.144"}}],
                },
            ],
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            catalog_path = root / "private_zapretgui" / "resources" / "json" / "hosts_catalog.json"
            catalog_path.parent.mkdir(parents=True, exist_ok=True)
            catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
            fake_module = root / "public_zapretgui" / "src" / "hosts" / "proxy_domains.py"
            fake_module.parent.mkdir(parents=True, exist_ok=True)
            fake_module.write_text("", encoding="utf-8")

            with patch.object(self.proxy_domains, "__file__", str(fake_module)):
                self.proxy_domains.invalidate_hosts_catalog_cache()
                plan = page_plans.build_services_catalog_plan(
                    current_selection={},
                    active_domains_map={},
                    direct_title="Direct",
                    ai_title="AI",
                    other_title="Other",
                )

        groups = {group.title: {row.service_name: row for row in group.rows} for group in plan.groups}
        self.assertIn("Meta AI", groups["AI"])
        self.assertIn("Trae.ai", groups["AI"])
        self.assertIn("Windsurf", groups["AI"])
        self.assertIn("Tailscale", groups["Other"])
        self.assertIn("JetBrains", groups["Other"])
        self.assertEqual(groups["AI"]["Meta AI"].icon_name, "fa5b.facebook-f")
        self.assertEqual(groups["AI"]["Trae.ai"].icon_name, "fa5s.code")
        self.assertEqual(groups["AI"]["Windsurf"].icon_name, "fa5s.wind")

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

    def test_services_catalog_plan_prefers_active_hosts_profile_over_saved_selection(self) -> None:
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
                    active_domains_map={"chat.openai.com": "2.23.88.118"},
                    direct_title="Direct",
                    ai_title="AI",
                    other_title="Other",
                )

        self.assertEqual(plan.new_selection.get("ChatGPT"), "xbox_dns")
        rows = [row for group in plan.groups for row in group.rows if row.service_name == "ChatGPT"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].selected_profile, "xbox_dns")
        self.assertTrue(plan.selection_changed)

    def test_services_catalog_plan_uses_single_profile_index_without_catalog_roundtrips(self) -> None:
        from hosts import page_plans

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_catalog(root)
            fake_module = root / "public_zapretgui" / "src" / "hosts" / "proxy_domains.py"
            fake_module.parent.mkdir(parents=True, exist_ok=True)
            fake_module.write_text("", encoding="utf-8")

            with patch.object(self.proxy_domains, "__file__", str(fake_module)):
                self.proxy_domains.invalidate_hosts_catalog_cache()
                profile_index = self.proxy_domains.get_services_profile_index()

        def _old_catalog_path_used(*_args, **_kwargs):
            raise AssertionError("build_services_catalog_plan должен использовать общий индекс каталога")

        with (
            patch("hosts.proxy_domains.get_services_profile_index", return_value=profile_index),
            patch.object(page_plans, "get_direct_profile_name", side_effect=_old_catalog_path_used),
            patch.object(page_plans, "service_has_active_domains", side_effect=_old_catalog_path_used),
            patch.object(page_plans, "infer_profile_from_hosts", side_effect=_old_catalog_path_used),
            patch.object(page_plans, "infer_direct_toggle_from_hosts", side_effect=_old_catalog_path_used),
        ):
            plan = page_plans.build_services_catalog_plan(
                current_selection={},
                active_domains_map={
                    "chat.openai.com": "2.23.88.118",
                    "instagram.com": "157.240.245.174",
                },
                direct_title="Direct",
                ai_title="AI",
                other_title="Other",
            )

        self.assertEqual(plan.new_selection.get("ChatGPT"), "xbox_dns")
        self.assertEqual(plan.new_selection.get("Instagram"), "direct")

    def test_services_profile_index_is_cached_until_catalog_is_invalidated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_catalog(root)
            fake_module = root / "public_zapretgui" / "src" / "hosts" / "proxy_domains.py"
            fake_module.parent.mkdir(parents=True, exist_ok=True)
            fake_module.write_text("", encoding="utf-8")

            with patch.object(self.proxy_domains, "__file__", str(fake_module)):
                self.proxy_domains.invalidate_hosts_catalog_cache()
                with patch.object(
                    self.proxy_domains,
                    "_get_path_sig",
                    wraps=self.proxy_domains._get_path_sig,
                ) as get_path_sig:
                    first = self.proxy_domains.get_services_profile_index()
                    second = self.proxy_domains.get_services_profile_index()

        self.assertIs(first, second)
        self.assertEqual(get_path_sig.call_count, 1)

    def test_split_catalog_signature_tracks_same_size_content_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "hosts_catalog"
            root.mkdir()
            item = root / "001.json"
            item.write_text('{"a":1}\n', encoding="utf-8")
            first_stat = item.stat()
            first_sig = self.proxy_domains._get_path_sig(root)

            item.write_text('{"a":2}\n', encoding="utf-8")
            os.utime(item, ns=(int(first_stat.st_atime_ns), int(first_stat.st_mtime_ns)))

            second_sig = self.proxy_domains._get_path_sig(root)

        self.assertNotEqual(first_sig, second_sig)

    def test_loaded_split_catalog_signature_is_reused_for_immediate_consumer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_split_catalog(root)
            fake_module = root / "public_zapretgui" / "src" / "hosts" / "proxy_domains.py"
            fake_module.parent.mkdir(parents=True, exist_ok=True)
            fake_module.write_text("", encoding="utf-8")

            with patch.object(self.proxy_domains, "__file__", str(fake_module)):
                self.proxy_domains.invalidate_hosts_catalog_cache()
                self.proxy_domains.get_services_profile_index()
                with patch.object(
                    self.proxy_domains,
                    "_get_path_sig",
                    side_effect=AssertionError("recent loaded signature should be reused"),
                ):
                    signature = self.proxy_domains.get_hosts_catalog_signature()

        self.assertIsNotNone(signature)

    def test_cold_split_catalog_load_computes_signature_while_reading_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_split_catalog(root)
            fake_module = root / "public_zapretgui" / "src" / "hosts" / "proxy_domains.py"
            fake_module.parent.mkdir(parents=True, exist_ok=True)
            fake_module.write_text("", encoding="utf-8")

            with patch.object(self.proxy_domains, "__file__", str(fake_module)):
                self.proxy_domains.invalidate_hosts_catalog_cache()
                with patch.object(
                    self.proxy_domains,
                    "_get_path_sig",
                    side_effect=AssertionError("cold split load should not rescan signature before reading"),
                ):
                    index = self.proxy_domains.get_services_profile_index()

        self.assertEqual(index.get("services"), ["ChatGPT", "Instagram"])

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

    def test_apply_domain_rows_does_not_clear_hosts_when_all_rows_are_filtered_ipv6(self) -> None:
        from hosts import hosts as hosts_module

        original = "\n".join(
            [
                "# >>> zapretgui:hosts managed begin >>>",
                "# Generated by ZapretGUI. Do not edit this block manually.",
                "2.2.2.2 old.example",
                "# <<< zapretgui:hosts managed end <<<",
                "",
            ]
        )
        written: list[str] = []
        manager = hosts_module.HostsManager()
        manager.is_hosts_file_accessible = lambda: True

        with (
            patch.object(hosts_module, "safe_read_hosts_file", return_value=original),
            patch.object(hosts_module, "safe_write_hosts_file", side_effect=lambda text: written.append(text) or True),
            patch.object(hosts_module, "is_ipv6_available", return_value=False, create=True),
        ):
            self.assertFalse(
                manager.apply_domain_ip_rows(
                    [("ipv6-only.example", "2a03:2880:f330:25:face:b00c:0:4420")]
                )
            )

        self.assertEqual(written, [])
        self.assertEqual(manager.last_status, "Нет подходящих hosts-записей для применения")

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

    def test_apply_domain_rows_does_not_shift_block_down_on_repeated_updates(self) -> None:
        from hosts import hosts as hosts_module

        original = "\n".join(
            [
                "# user header",
                "10.0.0.1 chatgpt.com",
                "10.0.0.2 another.example",
                "",
            ]
        )
        written: list[str] = []
        current_content = {"text": original}
        manager = hosts_module.HostsManager()
        manager.is_hosts_file_accessible = lambda: True

        def write_hosts(text: str) -> bool:
            written.append(text)
            current_content["text"] = text
            return True

        with (
            patch.object(hosts_module, "safe_read_hosts_file", side_effect=lambda: current_content["text"]),
            patch.object(hosts_module, "safe_write_hosts_file", side_effect=write_hosts),
            patch.object(hosts_module, "is_ipv6_available", return_value=True),
        ):
            self.assertTrue(manager.apply_domain_ip_rows([("chatgpt.com", "2.2.2.2")]))
            self.assertTrue(manager.apply_domain_ip_rows([("chatgpt.com", "3.3.3.3")]))

        self.assertEqual(len(written), 2)
        first_lines = written[0].splitlines()
        second_lines = written[1].splitlines()
        first_begin = first_lines.index("# >>> zapretgui:hosts managed begin >>>")
        second_begin = second_lines.index("# >>> zapretgui:hosts managed begin >>>")
        self.assertEqual(second_begin, first_begin)
        self.assertNotIn("\n\n\n# >>> zapretgui:hosts managed begin >>>", written[1])

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
