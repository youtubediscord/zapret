from __future__ import annotations

import importlib
import inspect
from pathlib import Path
import time
import unittest

import telegram_proxy.manager as telegram_manager
import telegram_proxy.runtime.commands as telegram_commands
import telegram_proxy.runtime.plans as telegram_plans


class TelegramProxyActionsArchitectureTests(unittest.TestCase):
    def test_wss_pools_skip_websockets_with_closing_transport(self) -> None:
        import asyncio

        from telegram_proxy.proxy.pool import CloudflareWorkerPool, WsPool
        from telegram_proxy.proxy.stats import ProxyStats

        class _Transport:
            def is_closing(self) -> bool:
                return True

        class _Writer:
            transport = _Transport()

        class _WebSocket:
            _closed = False
            writer = _Writer()

            async def close(self) -> None:
                self._closed = True

        async def run_check() -> None:
            stats = ProxyStats()

            ws_pool = WsPool(stats, pool_size=0)
            ws_pool._idle[(2, False)] = [(_WebSocket(), time.monotonic())]
            self.assertIsNone(await ws_pool.get(2, False, "149.154.167.220", ["kws2.web.telegram.org"]))
            self.assertEqual(stats.pool_hits, 0)
            self.assertEqual(stats.pool_misses, 1)

            worker_pool = CloudflareWorkerPool(stats, pool_size=0)
            worker_pool._idle[(2, "worker.example.dev", "149.154.167.51")] = [
                (_WebSocket(), time.monotonic())
            ]
            self.assertIsNone(await worker_pool.get(2, "worker.example.dev", "149.154.167.51"))
            self.assertEqual(stats.cloudflare_worker_pool_hits, 0)
            self.assertEqual(stats.cloudflare_worker_pool_misses, 1)

        asyncio.run(run_check())

    def test_external_open_actions_live_in_commands_not_actions(self) -> None:
        commands_source = inspect.getsource(telegram_commands)
        plans_source = inspect.getsource(telegram_plans)

        self.assertNotIn("subprocess", plans_source)
        self.assertNotIn("webbrowser.open", plans_source)
        self.assertNotIn("open_log_file", plans_source)
        self.assertNotIn("open_external_link", plans_source)

        self.assertIn("def open_log_file", commands_source)
        self.assertIn("def open_external_link", commands_source)
        self.assertIn("subprocess.Popen", commands_source)
        self.assertIn("webbrowser.open", commands_source)

    def test_upstream_config_builder_has_single_settings_owner(self) -> None:
        manager_source = inspect.getsource(telegram_manager.build_upstream_proxy_config_from_settings)
        commands_source = inspect.getsource(telegram_commands.build_upstream_config)

        self.assertIn("telegram_proxy.config.settings", manager_source)
        self.assertIn("build_upstream_config", manager_source)
        self.assertNotIn("get_tg_proxy_upstream_enabled", manager_source)
        self.assertNotIn("get_tg_proxy_upstream_host", manager_source)
        self.assertIn("telegram_proxy.config.settings", commands_source)

    def test_wss_proxy_is_split_into_focused_modules(self) -> None:
        transport = importlib.import_module("telegram_proxy.proxy.transport")
        routing = importlib.import_module("telegram_proxy.proxy.routing")
        relay = importlib.import_module("telegram_proxy.proxy.relay")
        stats = importlib.import_module("telegram_proxy.proxy.stats")
        mtproto = importlib.import_module("telegram_proxy.proxy.mtproto")
        pool = importlib.import_module("telegram_proxy.proxy.pool")
        wss_proxy = importlib.import_module("telegram_proxy.wss_proxy")

        self.assertIs(wss_proxy.RawWebSocket, transport.RawWebSocket)
        self.assertIs(wss_proxy.WsHandshakeError, transport.WsHandshakeError)
        self.assertIs(wss_proxy.UpstreamProxyConfig, routing.UpstreamProxyConfig)
        self.assertIs(wss_proxy.check_relay_reachable, routing.check_relay_reachable)
        self.assertIs(wss_proxy.RELAY_BUFFER, relay.RELAY_BUFFER)
        self.assertIs(wss_proxy.ProxyStats, stats.ProxyStats)
        self.assertIs(wss_proxy._MsgSplitter, mtproto.MsgSplitter)
        self.assertIs(wss_proxy._WsPool, pool.WsPool)

        wss_source = inspect.getsource(wss_proxy)
        self.assertNotIn("def _dc_from_init", wss_source)
        self.assertNotIn("def _patch_init_dc", wss_source)
        self.assertNotIn("class _MsgSplitter", wss_source)
        self.assertNotIn("class _WsPool", wss_source)
        self.assertNotIn("transparent_port_to_dc", wss_source)
        self.assertNotIn("TRANSPARENT_PORT_BASE", wss_source)
        self.assertNotIn("telegram_proxy.raw_websocket", wss_source)
        self.assertNotIn("telegram_proxy.relay", wss_source)
        self.assertNotIn("telegram_proxy.routing", wss_source)
        self.assertNotIn("telegram_proxy.stats", wss_source)
        self.assertIn("relay_tcp(", wss_source)
        self.assertIn("relay_wss(", wss_source)
        self.assertIn("should_route_upstream(", wss_source)

    def test_proxy_network_helpers_live_under_proxy_package(self) -> None:
        root = Path(__file__).resolve().parents[1]
        telegram_proxy_root = root / "src" / "telegram_proxy"
        proxy_root = telegram_proxy_root / "proxy"

        self.assertTrue((proxy_root / "__init__.py").exists())
        self.assertTrue((proxy_root / "transport.py").exists())
        self.assertTrue((proxy_root / "relay.py").exists())
        self.assertTrue((proxy_root / "routing.py").exists())
        self.assertTrue((proxy_root / "stats.py").exists())
        self.assertTrue((proxy_root / "mtproto.py").exists())
        self.assertTrue((proxy_root / "pool.py").exists())
        self.assertTrue((proxy_root / "dc_map.py").exists())
        self.assertTrue((proxy_root / "socks5.py").exists())

        self.assertFalse((telegram_proxy_root / "raw_websocket.py").exists())
        self.assertFalse((telegram_proxy_root / "relay.py").exists())
        self.assertFalse((telegram_proxy_root / "routing.py").exists())
        self.assertFalse((telegram_proxy_root / "stats.py").exists())
        self.assertFalse((telegram_proxy_root / "dc_map.py").exists())
        self.assertFalse((telegram_proxy_root / "socks5.py").exists())

    def test_removed_transparent_mode_has_no_proxy_helpers(self) -> None:
        dc_map = importlib.import_module("telegram_proxy.proxy.dc_map")

        self.assertFalse(hasattr(dc_map, "TRANSPARENT_PORT_BASE"))
        self.assertFalse(hasattr(dc_map, "dc_to_transparent_port"))
        self.assertFalse(hasattr(dc_map, "transparent_port_to_dc"))

    def test_config_and_diagnostics_live_in_focused_packages(self) -> None:
        root = Path(__file__).resolve().parents[1]
        telegram_proxy_root = root / "src" / "telegram_proxy"
        config_root = telegram_proxy_root / "config"
        diagnostics_root = telegram_proxy_root / "diagnostics"

        settings = importlib.import_module("telegram_proxy.config.settings")
        upstream_catalog = importlib.import_module("telegram_proxy.config.upstream_catalog")
        diagnostics_runner = importlib.import_module("telegram_proxy.diagnostics.runner")

        self.assertTrue((config_root / "__init__.py").exists())
        self.assertTrue((config_root / "settings.py").exists())
        self.assertTrue((config_root / "upstream_catalog.py").exists())
        self.assertTrue((diagnostics_root / "__init__.py").exists())
        self.assertTrue((diagnostics_root / "runner.py").exists())

        self.assertTrue(hasattr(settings, "build_upstream_config"))
        self.assertTrue(hasattr(upstream_catalog, "UpstreamCatalog"))
        self.assertTrue(hasattr(diagnostics_runner, "run_all"))

        self.assertFalse((telegram_proxy_root / "settings.py").exists())
        self.assertFalse((telegram_proxy_root / "upstream_catalog.py").exists())
        self.assertFalse((telegram_proxy_root / "diagnostics.py").exists())

    def test_runtime_layer_lives_in_runtime_package(self) -> None:
        root = Path(__file__).resolve().parents[1]
        telegram_proxy_root = root / "src" / "telegram_proxy"
        runtime_root = telegram_proxy_root / "runtime"

        commands = importlib.import_module("telegram_proxy.runtime.commands")
        plans = importlib.import_module("telegram_proxy.runtime.plans")
        workers = importlib.import_module("telegram_proxy.runtime.workers")
        public = importlib.import_module("telegram_proxy.public")

        self.assertTrue((runtime_root / "__init__.py").exists())
        self.assertTrue((runtime_root / "commands.py").exists())
        self.assertTrue((runtime_root / "plans.py").exists())
        self.assertTrue((runtime_root / "workers.py").exists())

        self.assertTrue(hasattr(commands, "get_start_config"))
        self.assertTrue(hasattr(plans, "TelegramProxyActionResult"))
        self.assertTrue(hasattr(workers, "TelegramProxyStartWorker"))
        self.assertIs(public.TelegramProxyStartConfig, commands.TelegramProxyStartConfig)

        self.assertFalse((telegram_proxy_root / "actions.py").exists())
        self.assertFalse((telegram_proxy_root / "commands.py").exists())
        self.assertFalse((telegram_proxy_root / "workers.py").exists())


if __name__ == "__main__":
    unittest.main()
