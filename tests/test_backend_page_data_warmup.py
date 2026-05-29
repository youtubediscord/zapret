from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch


class BackendPageDataWarmupTests(unittest.TestCase):
    def test_installer_warms_backend_caches_without_page_host(self) -> None:
        from main import post_startup_backend_warmup
        from main.post_startup_backend_warmup import install_backend_page_data_warmup

        class Signal:
            def __init__(self) -> None:
                self._callback = None

            def connect(self, callback) -> None:
                self._callback = callback

            def emit(self, value: str = "") -> None:
                self._callback(value)

        signal = Signal()
        startup_host = SimpleNamespace(
            startup_interactive_ready=signal,
            startup_state=SimpleNamespace(interactive_logged=False),
            is_alive=Mock(return_value=True),
        )
        premium_feature = SimpleNamespace(warm_page_data_cache=Mock())
        logs_feature = SimpleNamespace(warm_page_data_cache=Mock())
        metric = Mock()
        delays: list[int] = []
        thread_names: list[str] = []

        with (
            patch.object(
                post_startup_backend_warmup,
                "schedule_after",
                side_effect=lambda delay_ms, callback: delays.append(delay_ms) or callback(),
            ),
            patch.object(
                post_startup_backend_warmup,
                "start_daemon_thread",
                side_effect=lambda name, target: thread_names.append(name) or target(),
            ),
            patch.object(post_startup_backend_warmup.appearance_settings, "warm_page_initial_state_cache") as warm_appearance,
        ):
            install_backend_page_data_warmup(
                startup_host,
                premium_feature=premium_feature,
                logs_feature=logs_feature,
                log_startup_metric=metric,
            )
            signal.emit("interactive")

        self.assertEqual(delays, [8000, 18000])
        self.assertEqual(
            thread_names,
            [
                "BackendPageDataWarmup-Appearance",
                "BackendPageDataWarmup-Logs",
                "BackendPageDataWarmup-Premium",
            ],
        )
        premium_feature.warm_page_data_cache.assert_called_once_with()
        logs_feature.warm_page_data_cache.assert_called_once_with()
        warm_appearance.assert_called_once_with()
        self.assertFalse(hasattr(startup_host, "warm_page"))
        metric.assert_any_call(
            "StartupBackendPageDataWarmupQueued",
            "8000ms after interactive; premium 18000ms after interactive",
        )
        metric.assert_any_call("StartupBackendPageDataWarmupStarted", "appearance, logs")
        metric.assert_any_call("StartupBackendPageDataWarmupStarted", "premium")

    def test_hosts_page_is_prepared_immediately_after_interactive(self) -> None:
        from app.page_names import PageName
        from main import post_startup_hosts_warmup
        from main.post_startup_hosts_warmup import install_hosts_page_warmup

        class Signal:
            def __init__(self) -> None:
                self._callback = None

            def connect(self, callback) -> None:
                self._callback = callback

            def emit(self, value: str = "") -> None:
                self._callback(value)

        signal = Signal()
        page = SimpleNamespace(warmup_initial_load=Mock(return_value=True))
        startup_host = SimpleNamespace(
            startup_interactive_ready=signal,
            startup_state=SimpleNamespace(interactive_logged=False),
            is_alive=Mock(return_value=True),
            ensure_page=Mock(return_value=page),
        )
        metric = Mock()
        delays: list[int] = []

        with patch.object(
            post_startup_hosts_warmup,
            "schedule_after",
            side_effect=lambda delay_ms, callback: delays.append(delay_ms) or callback(),
        ):
            install_hosts_page_warmup(
                startup_host,
                log_startup_metric=metric,
            )
            signal.emit("interactive")

        self.assertEqual(delays, [0])
        startup_host.ensure_page.assert_called_once_with(PageName.HOSTS)
        page.warmup_initial_load.assert_called_once_with()
        metric.assert_any_call("StartupHostsPageWarmupQueued", "0ms after interactive")
        metric.assert_any_call("StartupHostsPageWarmupStarted", "ensure_page")
        metric.assert_any_call("StartupHostsPageWarmupFinished", "warmup_initial_load")

    def test_premium_page_uses_warmed_device_snapshot_before_worker(self) -> None:
        from app.feature_facades.premium import PremiumPageData
        from donater.ui.page import PremiumPage

        snapshot = {"device_token": "token", "pair_code": None, "last_check": 123, "device_id": "dev"}
        page = SimpleNamespace(
            current_thread=None,
            _premium=SimpleNamespace(consume_warmed_page_data=Mock(return_value=PremiumPageData(device_info=snapshot, premium_state=None))),
            _start_worker_thread=Mock(),
            _on_premium_init_complete=Mock(),
        )

        PremiumPage._start_premium_init_worker(page)

        page._premium.consume_warmed_page_data.assert_called_once_with()
        page._on_premium_init_complete.assert_called_once_with(snapshot)
        page._start_worker_thread.assert_not_called()

    def test_logs_page_applies_warmed_overview_before_runtime_start(self) -> None:
        from log.commands import LogsPageDataState, LogsListState, LogsStatsState
        from log.ui.page import LogsPage

        logs_state = LogsListState(
            entries=[],
            current_log_file="current.log",
            cleanup_deleted=0,
            cleanup_errors=[],
            cleanup_total=0,
        )
        stats_state = LogsStatsState(
            app_logs=1,
            debug_logs=0,
            total_size_mb=0.1,
            max_logs=50,
            max_debug_logs=10,
        )
        cached_state = LogsPageDataState(logs_state=logs_state, stats_state=stats_state)
        calls: list[str] = []
        logs_feature = SimpleNamespace(
            consume_warmed_page_data=Mock(return_value=cached_state),
            run_runtime_init=Mock(return_value=(True, True)),
        )
        page = SimpleNamespace(
            _cleanup_in_progress=False,
            isVisible=Mock(return_value=True),
            _runtime_initialized=False,
            _runtime_started=False,
            _logs=logs_feature,
            _apply_logs_list_state=Mock(side_effect=lambda *_args, **_kwargs: calls.append("cached_logs")),
            _apply_logs_stats_state=Mock(side_effect=lambda *_args, **_kwargs: calls.append("cached_stats")),
            _refresh_logs_list=Mock(),
            _update_stats=Mock(),
            _start_tail_worker=Mock(),
            _log_ui_timing=Mock(),
        )

        LogsPage._run_runtime_init_once(page)

        self.assertEqual(calls, ["cached_logs", "cached_stats"])
        logs_feature.consume_warmed_page_data.assert_called_once_with()
        logs_feature.run_runtime_init.assert_called_once()
        self.assertTrue(page._runtime_initialized)
        self.assertTrue(page._runtime_started)

    def test_appearance_initial_state_cache_is_consumed_once(self) -> None:
        from settings import appearance

        state = appearance.AppearancePageInitialStatePlan(
            display_mode="dark",
            ui_language="ru",
            background_preset="standard",
            rkn_background=None,
            mica_enabled=True,
            window_opacity=100,
            accent_color=None,
            follow_windows_accent=False,
            tinted_background=False,
            tinted_intensity=12,
            animations_enabled=True,
            smooth_scroll_enabled=True,
            editor_smooth_scroll_enabled=True,
            garland_enabled=False,
            snowflakes_enabled=False,
        )

        appearance.clear_warmed_page_initial_state_cache()
        appearance.store_warmed_page_initial_state(state)

        self.assertIs(appearance.consume_warmed_page_initial_state(), state)
        self.assertIsNone(appearance.consume_warmed_page_initial_state())


if __name__ == "__main__":
    unittest.main()
