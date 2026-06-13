from __future__ import annotations

import os
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from telegram_proxy.config import settings as telegram_proxy_settings
from telegram_proxy.ui.page import TelegramProxyPage


class _FakeToggle:
    def __init__(self, checked: bool) -> None:
        self._checked = checked

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool, block_signals: bool = False) -> None:
        _ = block_signals
        self._checked = bool(checked)

    def setVisible(self, visible: bool) -> None:
        self.visible = bool(visible)


class _FakeVisibleWidget:
    def __init__(self) -> None:
        self.visible = True

    def setVisible(self, visible: bool) -> None:
        self.visible = bool(visible)


def _default_state_without_upstream() -> telegram_proxy_settings.TelegramProxySettingsState:
    return replace(
        telegram_proxy_settings.default_state(),
        upstream_enabled=False,
        upstream_preset_id="",
    )


class TelegramProxyPagePerformanceTests(unittest.TestCase):
    def test_stale_mtproxy_values_in_socks5_do_not_auto_open_advanced_panel(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        state = replace(
            _default_state_without_upstream(),
            mode="socks5",
            mtproxy_secret="63dae4ef747d6b64b652ead084cbcad7",
            fake_tls_domain="cdn.example.com",
            proxy_protocol=True,
        )

        self.assertFalse(TelegramProxyPage._advanced_settings_should_open(page, state))

    def test_saved_socks5_upstream_auto_opens_only_upstream_section(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        state = replace(
            _default_state_without_upstream(),
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
            _default_state_without_upstream(),
            mode="socks5",
            pool_size=6,
        )

        self.assertTrue(TelegramProxyPage._advanced_settings_should_open(page, state))
        self.assertEqual(TelegramProxyPage._advanced_settings_auto_sections(page, state), {"performance"})

    def test_mtproxy_mode_still_auto_opens_advanced_panel(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        state = replace(
            _default_state_without_upstream(),
            mode="mtproxy",
        )

        self.assertTrue(TelegramProxyPage._advanced_settings_should_open(page, state))
        self.assertEqual(TelegramProxyPage._advanced_settings_auto_sections(page, state), {"mtproxy"})

    def test_cloudflare_route_still_auto_opens_advanced_panel(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        state = replace(
            _default_state_without_upstream(),
            cloudflare_enabled=True,
            cloudflare_domains=("example.com",),
        )

        self.assertTrue(TelegramProxyPage._advanced_settings_should_open(page, state))
        self.assertEqual(TelegramProxyPage._advanced_settings_auto_sections(page, state), {"cloudflare"})

    def test_mtproxy_manual_advanced_off_stays_off(self) -> None:
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        advanced_toggle = _FakeToggle(False)
        advanced_card = _FakeVisibleWidget()

        page._advanced_toggle = advanced_toggle
        page._advanced_card = advanced_card
        page._advanced_settings_built = True
        page._proxy_mode_row = SimpleNamespace(currentData=lambda: "mtproxy")
        page._settings_card = _FakeVisibleWidget()
        page._mtproxy_secret_row = _FakeVisibleWidget()
        page._fake_tls_domain_row = _FakeVisibleWidget()
        page._proxy_protocol_toggle = _FakeVisibleWidget()
        page._ensure_advanced_settings_built = lambda: None
        page._update_manual_instructions = lambda: None
        page._apply_cloudflare_ui = lambda: None
        page._apply_auto_advanced_section_visibility = lambda: None

        with patch("telegram_proxy.ui.page.enable_setting_card_group_auto_height", lambda _widget: None):
            TelegramProxyPage._on_advanced_toggled(page, False)

        self.assertFalse(advanced_toggle.isChecked())
        self.assertFalse(advanced_card.visible)


if __name__ == "__main__":
    unittest.main()
