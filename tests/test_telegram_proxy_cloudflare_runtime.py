from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, patch


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

    def test_advanced_performance_settings_are_saved_through_runtime_command(self) -> None:
        import telegram_proxy.runtime.commands as commands

        with (
            patch("telegram_proxy.config.settings.set_pool_size") as set_pool_size,
            patch("telegram_proxy.config.settings.set_buffer_kb") as set_buffer_kb,
        ):
            commands.save_settings_action("pool_size", value=8)
            commands.save_settings_action("buffer_kb", value=512)

        set_pool_size.assert_called_once_with(8)
        set_buffer_kb.assert_called_once_with(512)

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

    def test_cloudflare_failures_are_written_to_user_log_with_next_route(self) -> None:
        from telegram_proxy.proxy.cloudflare import CloudflareFallbackConfig
        from telegram_proxy.wss_proxy import TelegramWSProxy

        logs: list[str] = []

        async def fake_connect(*_args, **_kwargs):
            raise TimeoutError()

        proxy = TelegramWSProxy(
            on_log=logs.append,
            cloudflare_config=CloudflareFallbackConfig(
                enabled=True,
                domains=("first.example.com",),
            ),
        )

        with patch("telegram_proxy.wss_proxy.RawWebSocket.connect", side_effect=fake_connect):
            ok = asyncio.run(
                proxy._cloudflare_fallback(
                    None,
                    None,
                    "91.105.192.100",
                    443,
                    b"x" * 64,
                    False,
                    "test",
                    203,
                    False,
                )
            )

        self.assertFalse(ok)
        joined = "\n".join(logs)
        self.assertIn("route=Cloudflare", joined)
        self.assertIn("dc=203", joined)
        self.assertIn("target=91.105.192.100:443", joined)
        self.assertIn("result=error", joined)
        self.assertIn("TimeoutError", joined)
        self.assertIn("next=try next Cloudflare domain or TCP fallback", joined)

    def test_disabled_cloudflare_is_not_logged_as_cloudflare_route(self) -> None:
        from telegram_proxy.wss_proxy import TelegramWSProxy

        logs: list[str] = []
        proxy = TelegramWSProxy(on_log=logs.append)

        ok = asyncio.run(
            proxy._cloudflare_fallback(
                None,
                None,
                "91.105.192.100",
                443,
                b"x" * 64,
                False,
                "test",
                203,
                False,
            )
        )

        self.assertFalse(ok)
        self.assertNotIn("route=Cloudflare", "\n".join(logs))

    def test_http_transport_uses_upstream_fallback_immediately(self) -> None:
        from telegram_proxy.proxy.routing import UpstreamProxyConfig
        from telegram_proxy.wss_proxy import TelegramWSProxy

        class _Reader:
            async def readexactly(self, size):
                init = b"GET /api HTTP/1.1\r\nHost: telegram\r\n\r\n"
                return init[:size].ljust(size, b"x")

        class _Writer:
            def get_extra_info(self, name, default=None):
                if name == "peername":
                    return ("127.0.0.1", 34567)
                return default

            def close(self):
                return None

            async def wait_closed(self):
                return None

        logs: list[str] = []
        proxy = TelegramWSProxy(
            on_log=logs.append,
            upstream_config=UpstreamProxyConfig(
                enabled=True,
                host="127.0.0.1",
                port=1080,
                mode="fallback",
            ),
        )
        upstream = AsyncMock(return_value=True)
        proxy._upstream_proxy_connect = upstream

        with (
            patch("telegram_proxy.wss_proxy.socks5.handshake", return_value=("149.154.175.50", 80)),
            patch("telegram_proxy.wss_proxy.asyncio.open_connection", new_callable=AsyncMock) as direct_tcp,
        ):
            asyncio.run(proxy._handle_socks5_client(_Reader(), _Writer()))

        direct_tcp.assert_not_called()
        upstream.assert_awaited_once()
        args = upstream.await_args.args
        self.assertEqual(args[2:4], ("149.154.175.50", 80))
        joined = "\n".join(logs)
        self.assertIn("HTTP transport -> upstream (fallback mode)", joined)
        self.assertEqual(len(proxy.stats.route_events), 1)
        self.assertEqual(proxy.stats.route_events[0].route, "внешний SOCKS5")

    def test_http_transport_uses_upstream_fallback_without_direct_probe(self) -> None:
        from telegram_proxy.proxy.routing import UpstreamProxyConfig
        from telegram_proxy.wss_proxy import TelegramWSProxy

        class _Reader:
            async def readexactly(self, size):
                init = b"GET /api HTTP/1.1\r\nHost: telegram\r\n\r\n"
                return init[:size].ljust(size, b"x")

        class _Writer:
            def get_extra_info(self, name, default=None):
                if name == "peername":
                    return ("127.0.0.1", 34567)
                return default

            def close(self):
                return None

            async def wait_closed(self):
                return None

        logs: list[str] = []
        proxy = TelegramWSProxy(
            on_log=logs.append,
            upstream_config=UpstreamProxyConfig(
                enabled=True,
                host="127.0.0.1",
                port=1080,
                mode="fallback",
            ),
        )
        upstream = AsyncMock(return_value=True)
        proxy._upstream_proxy_connect = upstream

        with (
            patch("telegram_proxy.wss_proxy.socks5.handshake", return_value=("149.154.175.50", 80)),
            patch("telegram_proxy.wss_proxy.asyncio.open_connection", new_callable=AsyncMock) as direct_tcp,
        ):
            asyncio.run(proxy._handle_socks5_client(_Reader(), _Writer()))

        direct_tcp.assert_not_called()
        upstream.assert_awaited_once()
        self.assertIn("HTTP transport -> upstream (fallback mode)", "\n".join(logs))

    def test_http_transport_uses_upstream_immediately_after_learned_direct_block(self) -> None:
        from telegram_proxy.proxy.routing import UpstreamProxyConfig
        from telegram_proxy.wss_proxy import TelegramWSProxy

        class _Reader:
            async def readexactly(self, size):
                init = b"GET /api HTTP/1.1\r\nHost: telegram\r\n\r\n"
                return init[:size].ljust(size, b"x")

        class _Writer:
            def get_extra_info(self, name, default=None):
                if name == "peername":
                    return ("127.0.0.1", 34567)
                return default

            def close(self):
                return None

            async def wait_closed(self):
                return None

        async def fail_direct_tcp(*_args, **_kwargs):
            raise TimeoutError()

        logs: list[str] = []
        proxy = TelegramWSProxy(
            on_log=logs.append,
            upstream_config=UpstreamProxyConfig(
                enabled=True,
                host="127.0.0.1",
                port=1080,
                mode="fallback",
            ),
        )
        upstream = AsyncMock(return_value=True)
        proxy._upstream_proxy_connect = upstream

        with (
            patch("telegram_proxy.wss_proxy.socks5.handshake", return_value=("149.154.167.41", 80)),
            patch("telegram_proxy.wss_proxy.asyncio.open_connection", side_effect=fail_direct_tcp),
        ):
            asyncio.run(proxy._handle_socks5_client(_Reader(), _Writer()))

        upstream.assert_awaited_once()
        upstream.reset_mock()

        with (
            patch("telegram_proxy.wss_proxy.socks5.handshake", return_value=("149.154.167.51", 80)),
            patch("telegram_proxy.wss_proxy.asyncio.open_connection", new_callable=AsyncMock) as direct_tcp,
        ):
            asyncio.run(proxy._handle_socks5_client(_Reader(), _Writer()))

        direct_tcp.assert_not_called()
        upstream.assert_awaited_once()
        self.assertIn("HTTP transport -> upstream (fallback mode)", "\n".join(logs))

    def test_http_transport_records_failure_for_status_without_upstream(self) -> None:
        from telegram_proxy.wss_proxy import TelegramWSProxy

        class _Reader:
            async def readexactly(self, size):
                init = b"GET /api HTTP/1.1\r\nHost: telegram\r\n\r\n"
                return init[:size].ljust(size, b"x")

        class _Writer:
            def get_extra_info(self, name, default=None):
                if name == "peername":
                    return ("127.0.0.1", 34567)
                return default

            def close(self):
                return None

            async def wait_closed(self):
                return None

        async def fail_direct_tcp(*_args, **_kwargs):
            raise TimeoutError()

        logs: list[str] = []
        proxy = TelegramWSProxy(on_log=logs.append)

        with (
            patch("telegram_proxy.wss_proxy.socks5.handshake", return_value=("149.154.175.50", 80)),
            patch("telegram_proxy.wss_proxy.asyncio.open_connection", side_effect=fail_direct_tcp),
        ):
            asyncio.run(proxy._handle_socks5_client(_Reader(), _Writer()))

        self.assertEqual(len(proxy.stats.route_events), 1)
        event = proxy.stats.route_events[0]
        self.assertEqual(event.dc, 0)
        self.assertEqual(event.route, "HTTP direct TCP")
        self.assertIn("ошибка", event.status)
        self.assertIn("TimeoutError", event.reason)

    def test_upstream_connect_failure_is_written_to_detailed_route_log(self) -> None:
        from telegram_proxy.proxy.routing import UpstreamProxyConfig
        from telegram_proxy.wss_proxy import TelegramWSProxy

        logs: list[str] = []
        proxy = TelegramWSProxy(
            on_log=logs.append,
            upstream_config=UpstreamProxyConfig(
                enabled=True,
                host="127.0.0.1",
                port=1080,
                username="secret-user",
                password="secret-pass",
                tls=True,
                mode="fallback",
            ),
        )

        async def fail_upstream(*_args, **_kwargs):
            raise TimeoutError()

        with patch("telegram_proxy.wss_proxy.socks5.connect_via_socks5", side_effect=fail_upstream):
            ok = asyncio.run(
                proxy._upstream_proxy_connect(
                    None,
                    None,
                    "149.154.175.50",
                    443,
                    b"x" * 64,
                    "test",
                    1,
                    False,
                )
            )

        self.assertFalse(ok)
        joined = "\n".join(logs)
        self.assertIn("upstream proxy -> 127.0.0.1:1080 tls=yes", joined)
        self.assertIn("route=upstream SOCKS5", joined)
        self.assertIn("dc=1", joined)
        self.assertIn("target=149.154.175.50:443 via 127.0.0.1:1080", joined)
        self.assertIn("result=error", joined)
        self.assertIn("TimeoutError", joined)
        self.assertIn("next=none", joined)
        self.assertNotIn("secret-user", joined)
        self.assertNotIn("secret-pass", joined)

    def test_upstream_replaces_telegram_ipv6_media_target_with_same_dc_ipv4(self) -> None:
        from telegram_proxy.proxy.routing import UpstreamProxyConfig
        from telegram_proxy.wss_proxy import TelegramWSProxy

        class _RemoteWriter:
            def __init__(self):
                self.transport = None

            def write(self, _data):
                return None

            async def drain(self):
                return None

        class _ClientReader:
            pass

        class _ClientWriter:
            pass

        async def fake_connect(*args, **_kwargs):
            seen.append(args)
            return object(), _RemoteWriter()

        async def fake_relay(*_args, **_kwargs):
            return (0, False)

        seen: list[tuple] = []
        proxy = TelegramWSProxy(
            upstream_config=UpstreamProxyConfig(
                enabled=True,
                host="127.0.0.1",
                port=1080,
                mode="fallback",
            ),
        )
        proxy._relay_tcp = fake_relay

        with patch("telegram_proxy.wss_proxy.socks5.connect_via_socks5", side_effect=fake_connect):
            ok = asyncio.run(
                proxy._upstream_proxy_connect(
                    _ClientReader(),
                    _ClientWriter(),
                    "2001:b28:f23d:f001:0:0:0:7",
                    443,
                    b"x" * 64,
                    "test",
                    1,
                    True,
                )
            )

        self.assertTrue(ok)
        self.assertEqual(seen[0][2:4], ("149.154.175.52", 443))

    def test_upstream_tries_next_bundled_proxy_after_connect_failure(self) -> None:
        from telegram_proxy.proxy.routing import UpstreamProxyConfig, UpstreamProxyEndpoint
        from telegram_proxy.wss_proxy import TelegramWSProxy

        class _RemoteWriter:
            def __init__(self):
                self.transport = None

            def write(self, _data):
                return None

            async def drain(self):
                return None

        async def fake_connect(proxy_host, *_args, **_kwargs):
            seen_hosts.append(proxy_host)
            if proxy_host == "bad.proxy":
                raise ConnectionResetError()
            return object(), _RemoteWriter()

        async def fake_relay(*_args, **_kwargs):
            return (1, False)

        seen_hosts: list[str] = []
        proxy = TelegramWSProxy(
            upstream_config=UpstreamProxyConfig(
                enabled=True,
                host="bad.proxy",
                port=443,
                mode="always",
                fallback_proxies=(
                    UpstreamProxyEndpoint(host="good.proxy", port=443),
                ),
            ),
        )
        proxy._relay_tcp = fake_relay

        with patch("telegram_proxy.wss_proxy.socks5.connect_via_socks5", side_effect=fake_connect):
            ok = asyncio.run(
                proxy._upstream_proxy_connect(
                    object(),
                    object(),
                    "149.154.175.50",
                    443,
                    b"x" * 64,
                    "test",
                    1,
                    False,
                )
            )

        self.assertTrue(ok)
        self.assertEqual(seen_hosts, ["bad.proxy", "good.proxy"])

    def test_upstream_zero_recv_temporarily_prefers_next_bundled_proxy(self) -> None:
        from telegram_proxy.proxy.routing import UpstreamProxyConfig, UpstreamProxyEndpoint
        from telegram_proxy.wss_proxy import TelegramWSProxy

        class _RemoteWriter:
            def __init__(self):
                self.transport = None

            def write(self, _data):
                return None

            async def drain(self):
                return None

        async def fake_connect(proxy_host, *_args, **_kwargs):
            seen_hosts.append(proxy_host)
            return object(), _RemoteWriter()

        async def fake_relay(*_args, **_kwargs):
            return (0, False)

        async def run_three(proxy: TelegramWSProxy):
            for index in range(3):
                await proxy._upstream_proxy_connect(
                    object(),
                    object(),
                    "149.154.175.50",
                    443,
                    b"x" * 64,
                    f"test-{index}",
                    1,
                    False,
                )

        seen_hosts: list[str] = []
        logs: list[str] = []
        proxy = TelegramWSProxy(
            on_log=logs.append,
            upstream_config=UpstreamProxyConfig(
                enabled=True,
                host="slow.proxy",
                port=443,
                mode="always",
                fallback_proxies=(
                    UpstreamProxyEndpoint(host="fast.proxy", port=443),
                ),
            ),
        )
        proxy._relay_tcp = fake_relay

        with patch("telegram_proxy.wss_proxy.socks5.connect_via_socks5", side_effect=fake_connect):
            asyncio.run(run_three(proxy))

        self.assertEqual(seen_hosts, ["slow.proxy", "slow.proxy", "fast.proxy"])
        self.assertIn("temporarily deprioritized after recv=0", "\n".join(logs))

    def test_upstream_tls_fallback_stays_before_plain_legacy_after_penalty(self) -> None:
        from telegram_proxy.proxy.routing import UpstreamProxyConfig, UpstreamProxyEndpoint
        from telegram_proxy.wss_proxy import TelegramWSProxy

        class _RemoteWriter:
            def __init__(self):
                self.transport = None

            def write(self, _data):
                return None

            async def drain(self):
                return None

        async def fake_connect(proxy_host, *_args, **_kwargs):
            seen_hosts.append(proxy_host)
            return object(), _RemoteWriter()

        async def fake_relay(*_args, **_kwargs):
            return (0, False)

        async def run_three(proxy: TelegramWSProxy):
            for index in range(3):
                await proxy._upstream_proxy_connect(
                    object(),
                    object(),
                    "149.154.175.50",
                    443,
                    b"x" * 64,
                    f"test-{index}",
                    1,
                    False,
                )

        seen_hosts: list[str] = []
        proxy = TelegramWSProxy(
            upstream_config=UpstreamProxyConfig(
                enabled=True,
                host="slow.tls",
                port=443,
                tls=True,
                mode="always",
                fallback_proxies=(
                    UpstreamProxyEndpoint(host="legacy.plain", port=443, tls=False),
                    UpstreamProxyEndpoint(host="fast.tls", port=443, tls=True),
                ),
            ),
        )
        proxy._relay_tcp = fake_relay

        with patch("telegram_proxy.wss_proxy.socks5.connect_via_socks5", side_effect=fake_connect):
            asyncio.run(run_three(proxy))

        self.assertEqual(seen_hosts, ["slow.tls", "slow.tls", "fast.tls"])

    def test_upstream_http80_zero_recv_temporarily_prefers_next_bundled_proxy(self) -> None:
        from telegram_proxy.proxy.routing import UpstreamProxyConfig, UpstreamProxyEndpoint
        from telegram_proxy.wss_proxy import TelegramWSProxy

        class _RemoteWriter:
            def __init__(self):
                self.transport = None

            def write(self, _data):
                return None

            async def drain(self):
                return None

        async def fake_connect(proxy_host, *_args, **_kwargs):
            seen_hosts.append(proxy_host)
            return object(), _RemoteWriter()

        async def fake_relay(*_args, **_kwargs):
            return (0, False)

        async def run_three(proxy: TelegramWSProxy):
            for index in range(3):
                await proxy._upstream_proxy_connect(
                    object(),
                    object(),
                    "149.154.167.41",
                    80,
                    b"x" * 64,
                    f"test-{index}",
                    0,
                    False,
                )

        seen_hosts: list[str] = []
        logs: list[str] = []
        proxy = TelegramWSProxy(
            on_log=logs.append,
            upstream_config=UpstreamProxyConfig(
                enabled=True,
                host="primary.tls",
                port=443,
                tls=True,
                mode="always",
                fallback_proxies=(
                    UpstreamProxyEndpoint(host="backup.tls", port=443, tls=True),
                ),
            ),
        )
        proxy._relay_tcp = fake_relay

        with patch("telegram_proxy.wss_proxy.socks5.connect_via_socks5", side_effect=fake_connect):
            asyncio.run(run_three(proxy))

        self.assertEqual(seen_hosts, ["primary.tls", "primary.tls", "backup.tls"])
        self.assertIn("temporarily deprioritized after recv=0", "\n".join(logs))

    def test_upstream_plain_legacy_is_skipped_when_tls_candidates_exist(self) -> None:
        from telegram_proxy.proxy.routing import UpstreamProxyConfig, UpstreamProxyEndpoint
        from telegram_proxy.wss_proxy import TelegramWSProxy

        proxy = TelegramWSProxy(
            upstream_config=UpstreamProxyConfig(
                enabled=True,
                host="primary.tls",
                port=443,
                tls=True,
                mode="always",
                fallback_proxies=(
                    UpstreamProxyEndpoint(host="legacy.plain", port=443, tls=False),
                    UpstreamProxyEndpoint(host="backup.tls", port=443, tls=True),
                ),
            ),
        )

        self.assertEqual(
            [endpoint.host for endpoint in proxy._upstream_proxy_candidates()],
            ["primary.tls", "backup.tls"],
        )

    def test_upstream_connect_failure_is_temporarily_deprioritized_next_time(self) -> None:
        from telegram_proxy.proxy.routing import UpstreamProxyConfig, UpstreamProxyEndpoint
        from telegram_proxy.wss_proxy import TelegramWSProxy

        class _RemoteWriter:
            def __init__(self):
                self.transport = None

            def write(self, _data):
                return None

            async def drain(self):
                return None

        async def fake_connect(proxy_host, *_args, **_kwargs):
            seen_hosts.append(proxy_host)
            if proxy_host == "timeout.proxy":
                raise TimeoutError()
            return object(), _RemoteWriter()

        async def fake_relay(*_args, **_kwargs):
            return (1, False)

        async def run_two(proxy: TelegramWSProxy):
            for index in range(2):
                await proxy._upstream_proxy_connect(
                    object(),
                    object(),
                    "149.154.175.50",
                    80,
                    b"x" * 64,
                    f"test-{index}",
                    0,
                    False,
                )

        seen_hosts: list[str] = []
        logs: list[str] = []
        proxy = TelegramWSProxy(
            on_log=logs.append,
            upstream_config=UpstreamProxyConfig(
                enabled=True,
                host="timeout.proxy",
                port=443,
                tls=True,
                mode="always",
                fallback_proxies=(
                    UpstreamProxyEndpoint(host="fast.proxy", port=443, tls=True),
                ),
            ),
        )
        proxy._relay_tcp = fake_relay

        with patch("telegram_proxy.wss_proxy.socks5.connect_via_socks5", side_effect=fake_connect):
            asyncio.run(run_two(proxy))

        self.assertEqual(seen_hosts, ["timeout.proxy", "fast.proxy", "fast.proxy"])
        self.assertIn("temporarily deprioritized after connect TimeoutError", "\n".join(logs))

    def test_repeated_upstream_connect_failures_extend_penalty(self) -> None:
        from telegram_proxy.proxy.routing import UpstreamProxyConfig, UpstreamProxyEndpoint
        from telegram_proxy.wss_proxy import TelegramWSProxy

        proxy = TelegramWSProxy(
            upstream_config=UpstreamProxyConfig(
                enabled=True,
                host="timeout.tls",
                port=443,
                tls=True,
                mode="always",
                fallback_proxies=(
                    UpstreamProxyEndpoint(host="fast.tls", port=443, tls=True),
                ),
            ),
        )
        timeout_endpoint = proxy._upstream_proxy_candidates()[0]

        with patch("telegram_proxy.wss_proxy.time.monotonic", return_value=100.0):
            proxy._mark_upstream_connect_failure(timeout_endpoint, "test-1", TimeoutError())
        with patch("telegram_proxy.wss_proxy.time.monotonic", return_value=161.0):
            proxy._mark_upstream_connect_failure(timeout_endpoint, "test-2", TimeoutError())
        with patch("telegram_proxy.wss_proxy.time.monotonic", return_value=222.0):
            hosts = [endpoint.host for endpoint in proxy._upstream_proxy_candidates()]

        self.assertEqual(hosts, ["fast.tls", "timeout.tls"])

    def test_upstream_connect_rechecks_candidate_order_after_failure(self) -> None:
        from telegram_proxy.proxy.routing import UpstreamProxyConfig, UpstreamProxyEndpoint
        from telegram_proxy.wss_proxy import TelegramWSProxy

        class _RemoteWriter:
            def __init__(self):
                self.transport = None

        stale_endpoint = UpstreamProxyEndpoint(host="stale.tls", port=443, tls=True)
        proxy = TelegramWSProxy(
            upstream_config=UpstreamProxyConfig(
                enabled=True,
                host="primary.tls",
                port=443,
                tls=True,
                mode="always",
                fallback_proxies=(
                    stale_endpoint,
                    UpstreamProxyEndpoint(host="fresh.tls", port=443, tls=True),
                ),
            ),
        )

        seen_hosts: list[str] = []

        async def fake_connect(proxy_host, *_args, **_kwargs):
            seen_hosts.append(proxy_host)
            if proxy_host == "primary.tls":
                proxy._mark_upstream_connect_failure(stale_endpoint, "other-request", TimeoutError())
                raise TimeoutError()
            return object(), _RemoteWriter()

        with patch("telegram_proxy.wss_proxy.socks5.connect_via_socks5", side_effect=fake_connect):
            result = asyncio.run(
                proxy._open_upstream_proxy(
                    upstream_host="149.154.175.50",
                    upstream_port=80,
                    label="test",
                    dc=0,
                    is_media=False,
                )
            )

        self.assertIsNotNone(result)
        self.assertEqual(seen_hosts, ["primary.tls", "fresh.tls"])

    def test_upstream_connect_uses_bounded_failover_timeout(self) -> None:
        from telegram_proxy.proxy.routing import UpstreamProxyConfig, UpstreamProxyEndpoint
        from telegram_proxy.wss_proxy import TelegramWSProxy

        class _RemoteWriter:
            def __init__(self):
                self.transport = None

            def write(self, _data):
                return None

            async def drain(self):
                return None

        async def fake_connect(proxy_host, *_args, **kwargs):
            timeouts.append(kwargs["timeout"])
            if proxy_host == "timeout.tls":
                raise TimeoutError()
            return object(), _RemoteWriter()

        async def fake_relay(*_args, **_kwargs):
            return (1, False)

        timeouts: list[float] = []
        proxy = TelegramWSProxy(
            upstream_config=UpstreamProxyConfig(
                enabled=True,
                host="timeout.tls",
                port=443,
                tls=True,
                mode="always",
                fallback_proxies=(
                    UpstreamProxyEndpoint(host="fast.tls", port=443, tls=True),
                ),
            ),
        )
        proxy._relay_tcp = fake_relay

        with patch("telegram_proxy.wss_proxy.socks5.connect_via_socks5", side_effect=fake_connect):
            asyncio.run(
                proxy._upstream_proxy_connect(
                    object(),
                    object(),
                    "149.154.175.50",
                    80,
                    b"x" * 64,
                    "test",
                    0,
                    False,
                )
            )

        self.assertGreaterEqual(timeouts[0], 5.0)
        self.assertLessEqual(timeouts[0], 6.0)

    def test_no_wss_dc_uses_upstream_fallback_without_direct_tcp_probe(self) -> None:
        from telegram_proxy.proxy.routing import UpstreamProxyConfig
        from telegram_proxy.wss_proxy import TelegramWSProxy

        async def fake_upstream(_client_reader, _client_writer, target_host, target_port, _init, _label, dc, is_media):
            upstream_calls.append((target_host, target_port, dc, is_media))
            return True

        async def fail_direct_tcp(*_args, **_kwargs):
            raise AssertionError("direct TCP should not be probed before upstream for DC without WSS")

        upstream_calls: list[tuple[str, int, int, bool]] = []
        logs: list[str] = []
        proxy = TelegramWSProxy(
            on_log=logs.append,
            upstream_config=UpstreamProxyConfig(
                enabled=True,
                host="proxy.local",
                port=443,
                mode="fallback",
            ),
        )
        proxy._upstream_proxy_connect = fake_upstream

        with patch("telegram_proxy.wss_proxy.asyncio.open_connection", side_effect=fail_direct_tcp):
            asyncio.run(
                proxy._tcp_fallback(
                    object(),
                    object(),
                    "149.154.175.100",
                    443,
                    b"x" * 64,
                    "test",
                    3,
                    False,
                )
            )

        self.assertEqual(upstream_calls, [("149.154.175.100", 443, 3, False)])
        self.assertIn("DC3 no WSS relay -> upstream proxy", "\n".join(logs))

    def test_http_upstream_relay_does_not_block_mtproto_upstream_relay(self) -> None:
        from telegram_proxy.proxy.routing import UpstreamProxyConfig
        from telegram_proxy.wss_proxy import TelegramWSProxy

        class _RemoteWriter:
            def __init__(self):
                self.transport = None

            def write(self, _data):
                return None

            async def drain(self):
                return None

        async def fake_connect(_proxy_host, _proxy_port, _target_host, target_port, **_kwargs):
            connected_ports.append(target_port)
            return object(), _RemoteWriter()

        async def fake_relay(*_args, dc=0, **_kwargs):
            if dc == 0:
                http_relay_started.set()
                await release_http_relay.wait()
            return (1, False)

        async def run_pair(proxy: TelegramWSProxy):
            http_task = asyncio.create_task(
                proxy._upstream_proxy_connect(
                    object(),
                    object(),
                    "149.154.167.41",
                    80,
                    b"x" * 64,
                    "http",
                    0,
                    False,
                )
            )
            await asyncio.wait_for(http_relay_started.wait(), timeout=0.5)
            mtproto_task = asyncio.create_task(
                proxy._upstream_proxy_connect(
                    object(),
                    object(),
                    "149.154.175.100",
                    443,
                    b"x" * 64,
                    "dc3",
                    3,
                    False,
                )
            )
            await asyncio.wait_for(mtproto_task, timeout=0.5)
            release_http_relay.set()
            await asyncio.wait_for(http_task, timeout=0.5)

        connected_ports: list[int] = []
        http_relay_started = asyncio.Event()
        release_http_relay = asyncio.Event()
        proxy = TelegramWSProxy(
            upstream_config=UpstreamProxyConfig(
                enabled=True,
                host="proxy.local",
                port=443,
                mode="fallback",
            ),
            pool_size=1,
        )
        proxy._relay_tcp = fake_relay

        with patch("telegram_proxy.wss_proxy.socks5.connect_via_socks5", side_effect=fake_connect):
            asyncio.run(run_pair(proxy))

        self.assertEqual(connected_ports, [80, 443])

    def test_upstream_active_relays_are_limited_by_pool_size(self) -> None:
        from telegram_proxy.proxy.routing import UpstreamProxyConfig
        from telegram_proxy.wss_proxy import TelegramWSProxy

        class _RemoteWriter:
            def __init__(self):
                self.transport = None

            def write(self, _data):
                return None

            async def drain(self):
                return None

        async def fake_connect(*_args, **_kwargs):
            return object(), _RemoteWriter()

        async def fake_relay(*_args, **_kwargs):
            nonlocal active_relays, max_active_relays
            active_relays += 1
            max_active_relays = max(max_active_relays, active_relays)
            await asyncio.sleep(0.02)
            active_relays -= 1
            return (1, False)

        async def run_many(proxy: TelegramWSProxy):
            await asyncio.gather(
                *(
                    proxy._upstream_proxy_connect(
                        object(),
                        object(),
                        "149.154.175.50",
                        443,
                        b"x" * 64,
                        f"test-{index}",
                        1,
                        False,
                    )
                    for index in range(5)
                )
            )

        active_relays = 0
        max_active_relays = 0
        proxy = TelegramWSProxy(
            upstream_config=UpstreamProxyConfig(
                enabled=True,
                host="proxy.local",
                port=443,
                mode="always",
            ),
            pool_size=2,
        )
        proxy._relay_tcp = fake_relay

        with patch("telegram_proxy.wss_proxy.socks5.connect_via_socks5", side_effect=fake_connect):
            asyncio.run(run_many(proxy))

        self.assertLessEqual(max_active_relays, 2)

    def test_upstream_burst_is_spread_across_bundled_proxies(self) -> None:
        from telegram_proxy.proxy.routing import UpstreamProxyConfig, UpstreamProxyEndpoint
        from telegram_proxy.wss_proxy import TelegramWSProxy

        class _RemoteWriter:
            def __init__(self):
                self.transport = None

            def write(self, _data):
                return None

            async def drain(self):
                return None

        async def fake_connect(proxy_host, *_args, **_kwargs):
            seen_hosts.append(proxy_host)
            await asyncio.sleep(0.02)
            return object(), _RemoteWriter()

        async def fake_relay(*_args, **_kwargs):
            await asyncio.sleep(0.02)
            return (1, False)

        async def run_many(proxy: TelegramWSProxy):
            await asyncio.gather(
                *(
                    proxy._upstream_proxy_connect(
                        object(),
                        object(),
                        "149.154.175.50",
                        443,
                        b"x" * 64,
                        f"test-{index}",
                        1,
                        False,
                    )
                    for index in range(3)
                )
            )

        seen_hosts: list[str] = []
        proxy = TelegramWSProxy(
            upstream_config=UpstreamProxyConfig(
                enabled=True,
                host="primary.tls",
                port=443,
                tls=True,
                mode="always",
                fallback_proxies=(
                    UpstreamProxyEndpoint(host="backup-a.tls", port=443, tls=True),
                    UpstreamProxyEndpoint(host="backup-b.tls", port=443, tls=True),
                ),
            ),
            pool_size=3,
        )
        proxy._relay_tcp = fake_relay

        with patch("telegram_proxy.wss_proxy.socks5.connect_via_socks5", side_effect=fake_connect):
            asyncio.run(run_many(proxy))

        self.assertEqual(set(seen_hosts), {"primary.tls", "backup-a.tls", "backup-b.tls"})

    def test_proxy_server_is_bound_before_explicit_single_start_serving(self) -> None:
        from telegram_proxy.wss_proxy import TelegramWSProxy

        class _Server:
            def __init__(self):
                self.start_serving_calls = 0

            async def start_serving(self):
                self.start_serving_calls += 1

            def close(self):
                return None

            async def wait_closed(self):
                return None

        class _WsPool:
            def __init__(self, *_args, **_kwargs):
                return None

            async def warmup(self):
                return None

            async def close_all(self):
                return None

        class _WorkerPool(_WsPool):
            async def warmup(self, *_args, **_kwargs):
                return None

        server = _Server()

        async def fake_start_server(*_args, **_kwargs):
            return server

        async def run_proxy_once():
            proxy = TelegramWSProxy(port=0)
            await proxy.start()
            await proxy.stop()

        with (
            patch("telegram_proxy.wss_proxy.asyncio.start_server", side_effect=fake_start_server) as start_server,
            patch("telegram_proxy.wss_proxy._WsPool", _WsPool),
            patch("telegram_proxy.wss_proxy.CloudflareWorkerPool", _WorkerPool),
        ):
            asyncio.run(run_proxy_once())

        self.assertEqual(server.start_serving_calls, 1)
        self.assertEqual(start_server.await_args.kwargs.get("start_serving"), False)

    def test_upstream_connect_limit_is_not_created_before_proxy_event_loop(self) -> None:
        from telegram_proxy.wss_proxy import TelegramWSProxy

        proxy = TelegramWSProxy(port=0, pool_size=2)

        self.assertIsNone(proxy._upstream_connect_semaphore)
        self.assertIsNone(proxy._http_upstream_connect_semaphore)

    def test_upstream_socks5_client_sends_ipv6_address_type(self) -> None:
        from telegram_proxy.proxy import socks5

        class _Reader:
            def __init__(self):
                self._chunks = [
                    b"\x05\x00",
                    b"\x05\x00\x00\x04",
                    b"\x00" * 18,
                ]

            async def readexactly(self, _size):
                return self._chunks.pop(0)

        class _Writer:
            def __init__(self):
                self.writes: list[bytes] = []

            def write(self, data):
                self.writes.append(bytes(data))

            async def drain(self):
                return None

            def close(self):
                return None

        async def fake_open_connection(*_args, **_kwargs):
            writer = _Writer()
            opened.append(writer)
            return _Reader(), writer

        opened: list[_Writer] = []
        with patch("telegram_proxy.proxy.socks5.asyncio.open_connection", side_effect=fake_open_connection):
            asyncio.run(
                socks5.connect_via_socks5(
                    "127.0.0.1",
                    1080,
                    "2001:b28:f23d:f001:0:0:0:7",
                    443,
                )
            )

        request = opened[0].writes[1]
        self.assertEqual(request[:4], b"\x05\x01\x00\x04")
        self.assertEqual(len(request), 4 + 16 + 2)

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
