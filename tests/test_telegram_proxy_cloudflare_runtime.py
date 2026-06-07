from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch


class TelegramProxyCloudflareRuntimeTests(unittest.TestCase):
    def test_cloudflare_settings_are_normalized_in_settings_json_shape(self) -> None:
        from settings.normalize import normalize_telegram_proxy
        from settings.schema import default_telegram_proxy

        defaults = default_telegram_proxy()

        self.assertIn("cloudflare_enabled", defaults)
        self.assertIn("cloudflare_domains", defaults)
        self.assertIn("cloudflare_worker_enabled", defaults)
        self.assertIn("cloudflare_worker_domains", defaults)

        normalized = normalize_telegram_proxy(
            {
                "cloudflare_enabled": "yes",
                "cloudflare_domains": [" Example.COM ", "example.com", "", "bad domain"],
                "cloudflare_worker_enabled": 1,
                "cloudflare_worker_domains": "demo.workers.dev, DEMO.workers.dev; worker.example.dev",
            }
        )

        self.assertTrue(normalized["cloudflare_enabled"])
        self.assertEqual(normalized["cloudflare_domains"], ["example.com"])
        self.assertTrue(normalized["cloudflare_worker_enabled"])
        self.assertEqual(
            normalized["cloudflare_worker_domains"],
            ["demo.workers.dev", "worker.example.dev"],
        )

    def test_cloudflare_config_is_built_from_settings_store(self) -> None:
        import telegram_proxy.config.settings as telegram_proxy_settings

        with (
            patch("settings.store.get_tg_proxy_cloudflare_enabled", return_value=True),
            patch("settings.store.get_tg_proxy_cloudflare_domains", return_value=[" Example.COM ", "example.com"]),
            patch("settings.store.get_tg_proxy_cloudflare_worker_enabled", return_value=True),
            patch("settings.store.get_tg_proxy_cloudflare_worker_domains", return_value=["demo.workers.dev"]),
        ):
            config = telegram_proxy_settings.build_cloudflare_config()

        self.assertTrue(config.enabled)
        self.assertEqual(config.domains, ("example.com",))
        self.assertTrue(config.worker_enabled)
        self.assertEqual(config.worker_domains, ("demo.workers.dev",))

    def test_cloudflare_enabled_without_custom_domains_uses_builtin_auto_pool(self) -> None:
        import telegram_proxy.config.settings as telegram_proxy_settings
        from telegram_proxy.proxy.cloudflare import AUTO_CLOUDFLARE_DOMAINS

        with (
            patch("settings.store.get_tg_proxy_cloudflare_enabled", return_value=True),
            patch("settings.store.get_tg_proxy_cloudflare_domains", return_value=[]),
            patch("settings.store.get_tg_proxy_cloudflare_worker_enabled", return_value=False),
            patch("settings.store.get_tg_proxy_cloudflare_worker_domains", return_value=[]),
        ):
            config = telegram_proxy_settings.build_cloudflare_config()

        self.assertTrue(config.enabled)
        self.assertEqual(config.domains, AUTO_CLOUDFLARE_DOMAINS)

    def test_cloudflare_settings_are_saved_through_runtime_command(self) -> None:
        import telegram_proxy.runtime.commands as commands

        with (
            patch("telegram_proxy.config.settings.set_cloudflare_enabled") as set_enabled,
            patch("telegram_proxy.config.settings.set_cloudflare_domains") as set_domains,
            patch("telegram_proxy.config.settings.set_cloudflare_worker_enabled") as set_worker_enabled,
            patch("telegram_proxy.config.settings.set_cloudflare_worker_domains") as set_worker_domains,
        ):
            commands.save_settings_action("cloudflare_enabled", enabled=True)
            commands.save_settings_action("cloudflare_domains", value="example.com, demo.example.com")
            commands.save_settings_action("cloudflare_worker_enabled", enabled=True)
            commands.save_settings_action("cloudflare_worker_domains", value="worker.example.dev")

        set_enabled.assert_called_once_with(True)
        set_domains.assert_called_once_with("example.com, demo.example.com")
        set_worker_enabled.assert_called_once_with(True)
        set_worker_domains.assert_called_once_with("worker.example.dev")

    def test_cloudflare_helpers_build_domain_and_worker_targets(self) -> None:
        from telegram_proxy.proxy.cloudflare import (
            CloudflareFallbackConfig,
            build_cloudflare_domains,
            build_worker_path,
            should_try_cloudflare,
        )

        config = CloudflareFallbackConfig(
            enabled=True,
            domains=("example.com",),
            worker_enabled=True,
            worker_domains=("demo.workers.dev",),
        )

        self.assertTrue(should_try_cloudflare(config))
        self.assertEqual(build_cloudflare_domains(4, config), ["kws4.example.com"])
        self.assertEqual(build_worker_path("149.154.167.91", 4), "/apiws?dst=149.154.167.91&dc=4")

    def test_cloudflare_guides_include_dns_records_and_worker_code(self) -> None:
        from telegram_proxy.proxy.cloudflare import build_cfproxy_dns_records_text, build_cfworker_code

        dns_text = build_cfproxy_dns_records_text()
        worker_code = build_cfworker_code()

        self.assertIn("kws1", dns_text)
        self.assertIn("149.154.175.50", dns_text)
        self.assertIn("kws203", dns_text)
        self.assertIn("91.105.192.100", dns_text)
        self.assertIn('url.pathname !== "/apiws"', worker_code)
        self.assertIn("connect({ hostname: dst, port: 443 })", worker_code)

    def test_cloudflare_connectivity_check_builds_domain_and_worker_probes(self) -> None:
        from telegram_proxy.proxy.cloudflare import check_cloudflare_connectivity

        class _Ws:
            async def close(self):
                return None

        calls = []

        async def fake_connect(host, domain, path="/apiws", timeout=10.0):
            calls.append((host, domain, path, timeout))
            return _Ws()

        domain_result = asyncio.run(
            check_cloudflare_connectivity(
                "domain",
                ["Example.COM"],
                dcs=(4,),
                timeout=1.5,
                connect=fake_connect,
            )
        )
        worker_result = asyncio.run(
            check_cloudflare_connectivity(
                "worker",
                ["worker.example.dev"],
                dcs=(4,),
                timeout=1.5,
                connect=fake_connect,
            )
        )

        self.assertTrue(domain_result.ok)
        self.assertTrue(worker_result.ok)
        self.assertEqual(
            calls,
            [
                ("kws4.example.com", "kws4.example.com", "/apiws", 1.5),
                ("worker.example.dev", "worker.example.dev", "/apiws?dst=149.154.167.91&dc=4", 1.5),
            ],
        )

    def test_wss_proxy_uses_cloudflare_before_plain_tcp_fallback(self) -> None:
        import inspect
        import telegram_proxy.wss_proxy as wss_proxy

        source = inspect.getsource(wss_proxy.TelegramWSProxy._tunnel_via_wss)

        self.assertIn("_cloudflare_fallback", source)
        self.assertLess(source.index("_cloudflare_fallback"), source.index("_tcp_fallback"))


if __name__ == "__main__":
    unittest.main()
