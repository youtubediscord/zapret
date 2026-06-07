from __future__ import annotations

import unittest
from unittest.mock import Mock
from unittest.mock import patch

from app.state_store import AppUiState


class ControlTopSummaryRefreshGuardTests(unittest.TestCase):
    def _assert_subscription_change_updates_premium_without_worker(self, page_cls) -> None:
        page = page_cls.__new__(page_cls)
        page._cleanup_in_progress = False
        page.top_summary = Mock()
        page._request_top_summary_worker = Mock(
            side_effect=AssertionError("subscription-only change must not reload preset/profile summary")
        )
        page.set_loading = Mock()
        page.update_status = Mock()
        page.update_strategy = Mock(side_effect=AssertionError("subscription-only change must not repaint strategy state"))

        page_cls._on_ui_state_changed(
            page,
            AppUiState(subscription_is_premium=True, subscription_days_remaining=14),
            frozenset({"subscription_is_premium", "subscription_days_remaining"}),
        )

        page.top_summary.set_premium.assert_called_once_with(
            is_premium=True,
            days_remaining=14,
        )
        page._request_top_summary_worker.assert_not_called()

    def _assert_subscription_change_skips_runtime_repaint(self, page_cls) -> None:
        page = page_cls.__new__(page_cls)
        page._cleanup_in_progress = False
        page.top_summary = Mock()
        page._request_top_summary_worker = Mock()
        page.set_loading = Mock(side_effect=AssertionError("subscription-only change must not repaint loading controls"))
        page.update_status = Mock(side_effect=AssertionError("subscription-only change must not repaint runtime status"))
        page.update_strategy = Mock()

        page_cls._on_ui_state_changed(
            page,
            AppUiState(subscription_is_premium=True, subscription_days_remaining=14),
            frozenset({"subscription_is_premium", "subscription_days_remaining"}),
        )

        page.set_loading.assert_not_called()
        page.update_status.assert_not_called()
        page.update_strategy.assert_not_called()

    def test_zapret1_subscription_change_skips_top_summary_worker(self) -> None:
        from presets.ui.control.zapret1.page import Zapret1ModeControlPage

        self._assert_subscription_change_updates_premium_without_worker(Zapret1ModeControlPage)

    def test_zapret2_subscription_change_skips_top_summary_worker(self) -> None:
        from presets.ui.control.zapret2.page import Zapret2ModeControlPage

        self._assert_subscription_change_updates_premium_without_worker(Zapret2ModeControlPage)

    def test_zapret1_subscription_change_skips_runtime_repaint(self) -> None:
        from presets.ui.control.zapret1.page import Zapret1ModeControlPage

        self._assert_subscription_change_skips_runtime_repaint(Zapret1ModeControlPage)

    def test_zapret2_subscription_change_skips_runtime_repaint(self) -> None:
        from presets.ui.control.zapret2.page import Zapret2ModeControlPage

        self._assert_subscription_change_skips_runtime_repaint(Zapret2ModeControlPage)

    def test_control_pages_delay_top_summary_worker_after_active_preset_switch(self) -> None:
        from presets.ui.control.refresh_runtime_state import ModeControlRefreshRuntime
        from presets.ui.control.zapret1.page import Zapret1ModeControlPage
        from presets.ui.control.zapret2.page import Zapret2ModeControlPage

        for page_cls, module_name in (
            (Zapret1ModeControlPage, "presets.ui.control.zapret1.page"),
            (Zapret2ModeControlPage, "presets.ui.control.zapret2.page"),
        ):
            with self.subTest(page_cls=page_cls.__name__):
                page = page_cls.__new__(page_cls)
                page._cleanup_in_progress = False
                page._refresh_runtime = ModeControlRefreshRuntime()
                page.isVisible = Mock(return_value=True)
                page.run_when_page_ready = Mock()
                page._request_top_summary_worker = Mock()
                page._schedule_additional_settings_reload_after_preset_switch = Mock()

                callbacks = []
                with patch(
                    f"{module_name}.QTimer.singleShot",
                    side_effect=lambda delay_ms, callback: callbacks.append((delay_ms, callback)),
                ):
                    page_cls._on_ui_state_changed(
                        page,
                        AppUiState(current_strategy_summary="Профили"),
                        frozenset({"active_preset_revision"}),
                    )
                    page_cls._on_ui_state_changed(
                        page,
                        AppUiState(current_strategy_summary="Профили"),
                        frozenset({"active_preset_revision"}),
                    )

                page._request_top_summary_worker.assert_not_called()
                self.assertEqual(len(callbacks), 1)

                callbacks[0][1]()

                page._request_top_summary_worker.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
