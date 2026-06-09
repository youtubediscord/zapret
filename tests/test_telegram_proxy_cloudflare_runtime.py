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

    def test_cloudflare_domain_balancer_keeps_successful_domain_first(self) -> None:
        from telegram_proxy.proxy.cloudflare import (
            CloudflareDomainBalancer,
            CloudflareFallbackConfig,
            build_cloudflare_domains,
        )

        config = CloudflareFallbackConfig(
            enabled=True,
            domains=("first.example.com", "fast.example.com", "last.example.com"),
        )
        balancer = CloudflareDomainBalancer()

        self.assertEqual(
            build_cloudflare_domains(4, config, balancer=balancer),
            [
                "kws4.first.example.com",
                "kws4.fast.example.com",
                "kws4.last.example.com",
            ],
        )

        balancer.record_success(4, "kws4.fast.example.com")

        self.assertEqual(
            build_cloudflare_domains(4, config, balancer=balancer),
            [
                "kws4.fast.example.com",
                "kws4.first.example.com",
                "kws4.last.example.com",
            ],
        )
        self.assertEqual(
            build_cloudflare_domains(2, config, balancer=balancer),
            [
                "kws2.first.example.com",
                "kws2.fast.example.com",
                "kws2.last.example.com",
            ],
        )

    def test_cloudflare_guides_include_dns_records_and_worker_code(self) -> None:
        from telegram_proxy.proxy.cloudflare import build_cfproxy_dns_records_text, build_cfworker_code

        dns_text = build_cfproxy_dns_records_text()
        worker_code = build_cfworker_code()

        self.assertIn("kws1", dns_text)
        self.assertIn("149.154.175.50", dns_text)
        self.assertIn("kws203", dns_text)
        self.assertIn("91.105.192.100", dns_text)
        self.assertIn('url.pathname !== "/apiws"', worker_code)
        self.assertIn('request.headers.get("Upgrade")', worker_code)
        self.assertIn("function toBytes(data)", worker_code)
        self.assertIn("connect({ hostname: dst, port: 443 })", worker_code)
        self.assertIn("await tcpWriter.write(await toBytes(event.data))", worker_code)
        self.assertIn("tcpReader.releaseLock()", worker_code)
        self.assertIn("socket.close()", worker_code)

    def test_cloudflare_connectivity_check_builds_domain_and_worker_probes(self) -> None:
        from telegram_proxy.proxy.cloudflare import check_cloudflare_connectivity

        class _Ws:
            async def close(self):
                return None

        calls = []

        async def fake_connect(host, domain, path="/apiws", timeout=10.0, **_kwargs):
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

    def test_wss_proxy_remembers_successful_cloudflare_domain(self) -> None:
        from telegram_proxy.proxy.cloudflare import CloudflareFallbackConfig
        from telegram_proxy.wss_proxy import TelegramWSProxy

        class _Ws:
            async def send(self, data):
                return None

        calls: list[str] = []

        async def fake_connect(host, domain, path="/apiws", timeout=10.0, **_kwargs):
            calls.append(domain)
            if domain == "kws4.first.example.com":
                raise OSError("dead domain")
            return _Ws()

        async def fake_relay(*args, **kwargs):
            return None

        proxy = TelegramWSProxy(
            cloudflare_config=CloudflareFallbackConfig(
                enabled=True,
                domains=("first.example.com", "fast.example.com"),
            )
        )
        proxy._relay_wss = fake_relay

        with (
            patch("telegram_proxy.wss_proxy.RawWebSocket.connect", side_effect=fake_connect),
            patch("telegram_proxy.wss_proxy.log.warning"),
        ):
            first_ok = asyncio.run(
                proxy._cloudflare_fallback(
                    None,
                    None,
                    "149.154.167.91",
                    443,
                    b"x" * 64,
                    False,
                    "test",
                    4,
                    False,
                )
            )
            second_ok = asyncio.run(
                proxy._cloudflare_fallback(
                    None,
                    None,
                    "149.154.167.91",
                    443,
                    b"x" * 64,
                    False,
                    "test",
                    4,
                    False,
                )
            )

        self.assertTrue(first_ok)
        self.assertTrue(second_ok)
        self.assertEqual(
            calls,
            [
                "kws4.first.example.com",
                "kws4.fast.example.com",
                "kws4.fast.example.com",
            ],
        )

    def test_wss_proxy_uses_cloudflare_worker_pool_before_fresh_connect(self) -> None:
        from telegram_proxy.proxy.cloudflare import CloudflareFallbackConfig
        from telegram_proxy.wss_proxy import TelegramWSProxy

        class _Ws:
            async def send(self, data):
                return None

        class _WorkerPool:
            def __init__(self):
                self.calls: list[tuple[int, str, str]] = []

            async def get(self, dc, worker_domain, fallback_dst):
                self.calls.append((dc, worker_domain, fallback_dst))
                return _Ws()

        async def fake_relay(*args, **kwargs):
            return None

        worker_pool = _WorkerPool()
        proxy = TelegramWSProxy(
            cloudflare_config=CloudflareFallbackConfig(
                worker_enabled=True,
                worker_domains=("worker.example.dev",),
            )
        )
        proxy._cloudflare_worker_pool = worker_pool
        proxy._relay_wss = fake_relay

        with patch("telegram_proxy.wss_proxy.RawWebSocket.connect") as connect:
            ok = asyncio.run(
                proxy._cloudflare_fallback(
                    None,
                    None,
                    "149.154.167.91",
                    443,
                    b"x" * 64,
                    False,
                    "test",
                    4,
                    False,
                )
            )

        self.assertTrue(ok)
        self.assertEqual(worker_pool.calls, [(4, "worker.example.dev", "149.154.167.91")])
        self.assertEqual(connect.call_count, 0)
        self.assertEqual(proxy.stats.cloudflare_worker_connections, 1)

    def test_proxy_start_prewarms_worker_pool_for_fallback_media_targets(self) -> None:
        from telegram_proxy.proxy.cloudflare import CloudflareFallbackConfig
        from telegram_proxy.wss_proxy import TelegramWSProxy

        warmup_calls: list[tuple[tuple[str, ...], tuple[tuple[int, str], ...]]] = []

        class _WsPool:
            def __init__(self, *args, **kwargs):
                pass

            async def warmup(self):
                return None

            async def close_all(self):
                return None

        class _WorkerPool:
            def __init__(self, *args, **kwargs):
                pass

            async def warmup(self, worker_domains, fallback_targets):
                warmup_calls.append((tuple(worker_domains), tuple(fallback_targets)))

            async def close_all(self):
                return None

        async def run_proxy_once():
            proxy = TelegramWSProxy(
                port=0,
                cloudflare_config=CloudflareFallbackConfig(
                    worker_enabled=True,
                    worker_domains=("worker.example.dev",),
                ),
            )
            await proxy.start()
            await asyncio.sleep(0)
            await proxy.stop()

        with (
            patch("telegram_proxy.wss_proxy._WsPool", _WsPool),
            patch("telegram_proxy.wss_proxy.CloudflareWorkerPool", _WorkerPool),
        ):
            asyncio.run(run_proxy_once())

        self.assertEqual(
            warmup_calls,
            [
                (
                    ("worker.example.dev",),
                    (
                        (1, "149.154.175.50"),
                        (1, "149.154.175.52"),
                        (3, "149.154.175.100"),
                        (3, "149.154.175.102"),
                        (5, "91.108.56.100"),
                        (5, "91.108.56.102"),
                        (203, "91.105.192.100"),
                    ),
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()
