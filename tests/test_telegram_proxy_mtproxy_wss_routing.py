from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch


class TelegramProxyMtproxyWssRoutingTests(unittest.TestCase):
    def test_mtproxy_cdn_dc_skips_unsafe_cross_dc_wss_relays(self) -> None:
        from telegram_proxy.wss_proxy import TelegramWSProxy

        class _Pool:
            def __init__(self) -> None:
                self.calls = []

            async def get(self, dc, is_media, target_ip, domains):
                self.calls.append((dc, is_media, target_ip, tuple(domains)))
                return None

        async def fake_tcp_fallback(*args, **_kwargs):
            tcp_calls.append(args)

        tcp_calls = []
        pool = _Pool()
        proxy = TelegramWSProxy()
        proxy._ws_pool = pool
        proxy._mtproxy_tcp_fallback = fake_tcp_fallback

        with patch("telegram_proxy.wss_proxy.RawWebSocket.connect") as connect:
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

        self.assertEqual(pool.calls, [])
        connect.assert_not_called()
        self.assertEqual(len(tcp_calls), 1)
        self.assertEqual(tcp_calls[0][-2:], (203, False))
        self.assertEqual(proxy.stats.wss_connections, 0)


if __name__ == "__main__":
    unittest.main()
