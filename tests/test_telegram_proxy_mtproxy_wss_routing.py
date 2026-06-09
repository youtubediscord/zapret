from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch


class TelegramProxyMtproxyWssRoutingTests(unittest.TestCase):
    def test_mtproxy_cdn_dc_tries_fallback_wss_relays_before_tcp(self) -> None:
        from telegram_proxy.wss_proxy import TelegramWSProxy

        class _Pool:
            def __init__(self) -> None:
                self.calls = []

            async def get(self, dc, is_media, target_ip, domains):
                self.calls.append((dc, is_media, target_ip, tuple(domains)))
                return None

        class _Ws:
            def __init__(self) -> None:
                self.sent = []

            async def send(self, data):
                self.sent.append(data)

        async def fake_relay_mtproxy_wss(**_kwargs):
            return None

        async def fake_tcp_fallback(*args, **_kwargs):
            tcp_calls.append(args)

        connect_calls = []
        tcp_calls = []
        pool = _Pool()
        proxy = TelegramWSProxy()
        proxy._ws_pool = pool
        proxy._mtproxy_tcp_fallback = fake_tcp_fallback

        async def fake_connect(host, domain, path="/apiws", timeout=10.0, **_kwargs):
            connect_calls.append((host, domain, path, timeout))
            return _Ws()

        with (
            patch("telegram_proxy.wss_proxy.RawWebSocket.connect", side_effect=fake_connect),
            patch("telegram_proxy.wss_proxy.relay_mtproxy_wss", side_effect=fake_relay_mtproxy_wss),
        ):
            asyncio.run(
                proxy._tunnel_mtproxy_via_wss(
                    None,
                    None,
                    203,
                    False,
                    b"x" * 64,
                    object(),
                    b"\xef\xef\xef\xef",
                    "91.105.192.100",
                    443,
                    "test",
                )
            )

        self.assertTrue(pool.calls, "DC203 should reach fallback WSS relay selection")
        self.assertEqual(pool.calls[0][0], 203)
        self.assertIn("kws2.web.telegram.org", pool.calls[0][3])
        self.assertEqual(connect_calls[0][1], "kws2.web.telegram.org")
        self.assertEqual(tcp_calls, [])
        self.assertEqual(proxy.stats.wss_connections, 1)


if __name__ == "__main__":
    unittest.main()
