from __future__ import annotations

import unittest
from dataclasses import replace

from telegram_proxy.config import settings as telegram_proxy_settings
from telegram_proxy.ui.settings_ui_state import (
    build_advanced_settings_auto_sections,
    build_advanced_settings_ui_plan,
)


def _default_state_without_upstream() -> telegram_proxy_settings.TelegramProxySettingsState:
    return replace(
        telegram_proxy_settings.default_state(),
        upstream_enabled=False,
        upstream_preset_id="",
    )


class TelegramProxySettingsUiStateTests(unittest.TestCase):
    def test_auto_sections_come_from_saved_settings(self) -> None:
        state = replace(
            _default_state_without_upstream(),
            mode="mtproxy",
            cloudflare_enabled=True,
            dc_ip=("4:149.154.167.220",),
            pool_size=6,
        )

        self.assertEqual(
            build_advanced_settings_auto_sections(state),
            frozenset({"mtproxy", "upstream", "cloudflare", "dc_ip", "performance"}),
        )

    def test_manual_advanced_mode_shows_all_settings_without_forcing_toggle(self) -> None:
        plan = build_advanced_settings_ui_plan(
            advanced_checked=True,
            proxy_mode="socks5",
            auto_sections=frozenset(),
            cloudflare_enabled=False,
            cloudflare_worker_enabled=False,
        )

        self.assertTrue(plan.advanced_card_visible)
        self.assertFalse(plan.mtproxy_rows_visible)
        self.assertTrue(plan.upstream_controls_visible)
        self.assertTrue(plan.cloudflare_controls_visible)
        self.assertTrue(plan.dc_ip_row_visible)
        self.assertTrue(plan.performance_controls_visible)
        self.assertFalse(plan.cloudflare_domains_visible)
        self.assertFalse(plan.cloudflare_worker_domains_visible)

    def test_mtproxy_manual_off_does_not_reopen_advanced_card(self) -> None:
        plan = build_advanced_settings_ui_plan(
            advanced_checked=False,
            proxy_mode="mtproxy",
            auto_sections=frozenset({"mtproxy", "upstream"}),
            cloudflare_enabled=False,
            cloudflare_worker_enabled=False,
        )

        self.assertFalse(plan.advanced_card_visible)
        self.assertTrue(plan.should_build_advanced_widgets)
        self.assertTrue(plan.mtproxy_rows_visible)
        self.assertTrue(plan.upstream_controls_visible)

    def test_cloudflare_rows_follow_their_own_toggles(self) -> None:
        plan = build_advanced_settings_ui_plan(
            advanced_checked=True,
            proxy_mode="socks5",
            auto_sections=frozenset({"cloudflare"}),
            cloudflare_enabled=True,
            cloudflare_worker_enabled=True,
        )

        self.assertFalse(plan.upstream_controls_visible)
        self.assertTrue(plan.cloudflare_controls_visible)
        self.assertTrue(plan.cloudflare_domains_visible)
        self.assertTrue(plan.cloudflare_worker_domains_visible)
        self.assertTrue(plan.cloudflare_worker_domains_enabled)


if __name__ == "__main__":
    unittest.main()
