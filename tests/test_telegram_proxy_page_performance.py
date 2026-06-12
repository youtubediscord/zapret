from __future__ import annotations

import os
import unittest
from dataclasses import replace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from telegram_proxy.config import settings as telegram_proxy_settings
from telegram_proxy.ui.page import TelegramProxyPage


class TelegramProxyPagePerformanceTests(unittest.TestCase):
    def test_stale_mtproxy_values_in_socks5_do_not_auto_open_advanced_panel(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        state = replace(
            telegram_proxy_settings.default_state(),
            mode="socks5",
            mtproxy_secret="63dae4ef747d6b64b652ead084cbcad7",
            fake_tls_domain="cdn.example.com",
            proxy_protocol=True,
        )

        self.assertFalse(TelegramProxyPage._advanced_settings_should_open(page, state))

    def test_saved_socks5_upstream_auto_opens_only_upstream_section(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        state = replace(
            telegram_proxy_settings.default_state(),
            mode="socks5",
            upstream_enabled=True,
            upstream_preset_id="no",
            upstream_mode="fallback",
        )

        self.assertTrue(TelegramProxyPage._advanced_settings_should_open(page, state))
        self.assertEqual(TelegramProxyPage._advanced_settings_auto_sections(page, state), {"upstream"})

    def test_saved_performance_value_auto_opens_only_performance_section(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        state = replace(
            telegram_proxy_settings.default_state(),
            mode="socks5",
            pool_size=6,
        )

        self.assertTrue(TelegramProxyPage._advanced_settings_should_open(page, state))
        self.assertEqual(TelegramProxyPage._advanced_settings_auto_sections(page, state), {"performance"})

    def test_mtproxy_mode_still_auto_opens_advanced_panel(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        state = replace(
            telegram_proxy_settings.default_state(),
            mode="mtproxy",
        )

        self.assertTrue(TelegramProxyPage._advanced_settings_should_open(page, state))
        self.assertEqual(TelegramProxyPage._advanced_settings_auto_sections(page, state), {"mtproxy"})

    def test_cloudflare_route_still_auto_opens_advanced_panel(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        state = replace(
            telegram_proxy_settings.default_state(),
            cloudflare_enabled=True,
            cloudflare_domains=("example.com",),
        )

        self.assertTrue(TelegramProxyPage._advanced_settings_should_open(page, state))
        self.assertEqual(TelegramProxyPage._advanced_settings_auto_sections(page, state), {"cloudflare"})


if __name__ == "__main__":
    unittest.main()
