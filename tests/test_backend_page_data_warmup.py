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
        queued_tasks: list[tuple[str, str]] = []

        with (
            patch.object(
                post_startup_backend_warmup,
                "schedule_after",
                side_effect=lambda delay_ms, callback: delays.append(delay_ms) or callback(),
            ),
            patch.object(
                post_startup_backend_warmup,
                "enqueue_subsystem_task",
                side_effect=lambda queue, name, target: queued_tasks.append((queue, name)) or target(),
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
            queued_tasks,
            [
                ("appearance", "BackendPageDataWarmup-Appearance"),
                ("logs", "BackendPageDataWarmup-Logs"),
                ("premium", "BackendPageDataWarmup-Premium"),
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

    def test_hosts_page_data_is_warmed_in_background_without_page_host(self) -> None:
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
        startup_host = SimpleNamespace(
            startup_interactive_ready=signal,
            startup_state=SimpleNamespace(interactive_logged=False),
            is_alive=Mock(return_value=True),
        )
        hosts_feature = SimpleNamespace(warm_page_data_cache=Mock(return_value=True))
        metric = Mock()
        delays: list[int] = []
        queued_tasks: list[tuple[str, str]] = []

        with (
            patch.object(
                post_startup_hosts_warmup,
                "schedule_after",
                side_effect=lambda delay_ms, callback: delays.append(delay_ms) or callback(),
            ),
            patch.object(
                post_startup_hosts_warmup,
                "enqueue_subsystem_task",
                side_effect=lambda queue, name, target: queued_tasks.append((queue, name)) or target(),
            ),
        ):
            install_hosts_page_warmup(
                startup_host,
                hosts_feature=hosts_feature,
                log_startup_metric=metric,
            )
            signal.emit("interactive")

        self.assertEqual(delays, [0])
        self.assertEqual(queued_tasks, [("hosts", "HostsPageDataWarmup")])
        hosts_feature.warm_page_data_cache.assert_called_once_with()
        self.assertFalse(hasattr(startup_host, "ensure_page"))
        metric.assert_any_call("StartupHostsPageWarmupQueued", "0ms after interactive")
        metric.assert_any_call("StartupHostsPageWarmupStarted", "backend_cache")
        metric.assert_any_call("StartupHostsPageWarmupFinished", "backend_cache")

    def test_hosts_feature_warms_services_catalog_plan_for_first_open(self) -> None:
        import sys

        from app.feature_facades.hosts import build_hosts_feature

        selection = {"Claude": "xbox_dns"}
        catalog_plan = object()
        catalog_sig = ("hosts_catalog", 1, 2)
        public = SimpleNamespace(
            load_user_selection=Mock(return_value=selection),
            get_catalog_signature=Mock(return_value=catalog_sig),
            create_hosts_runtime=Mock(return_value=object()),
            build_services_catalog_plan=Mock(return_value=catalog_plan),
        )

        metric_stages: list[str] = []

        with (
            patch.dict(sys.modules, {"hosts.public": public}),
            patch(
                "app.feature_facades.hosts.log_ui_timing_since",
                side_effect=lambda _scope, _name, stage, *_args, **_kwargs: metric_stages.append(stage),
            ),
        ):
            feature = build_hosts_feature()

            self.assertTrue(feature.warm_page_data_cache())
            warmed = feature.consume_warmed_services_catalog_plan(
                current_selection=selection,
                direct_title="Напрямую из hosts",
                ai_title="ИИ",
                other_title="Остальные",
            )

        self.assertIsNotNone(warmed)
        self.assertIs(warmed.plan, catalog_plan)
        self.assertEqual(warmed.catalog_signature, catalog_sig)
        public.build_services_catalog_plan.assert_called_once()
        self.assertEqual(public.get_catalog_signature.call_count, 2)
        self.assertEqual(
            metric_stages,
            [
                "hosts_warmup.selection.load",
                "hosts_warmup.runtime.create",
                "hosts_warmup.services_catalog_plan.build",
                "hosts_warmup.catalog_signature.after",
                "hosts_warmup.cache_store",
            ],
        )

    def test_telegram_proxy_page_is_prepared_after_interactive_without_opening_it(self) -> None:
        from app.page_names import PageName
        from main import post_startup_telegram_proxy_warmup
        from main.post_startup_telegram_proxy_warmup import install_telegram_proxy_page_warmup

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
            ensure_page=Mock(return_value=object()),
            show_page=Mock(),
        )
        metric = Mock()
        delays: list[int] = []

        with patch.object(
            post_startup_telegram_proxy_warmup,
            "schedule_after",
            side_effect=lambda delay_ms, callback: delays.append(delay_ms) or callback(),
        ):
            install_telegram_proxy_page_warmup(
                startup_host,
                log_startup_metric=metric,
            )
            signal.emit("interactive")

        self.assertEqual(delays, [3000])
        startup_host.ensure_page.assert_called_once_with(PageName.TELEGRAM_PROXY)
        startup_host.show_page.assert_not_called()
        metric.assert_any_call("StartupTelegramProxyPageWarmupQueued", "3000ms after interactive")
        metric.assert_any_call("StartupTelegramProxyPageWarmupFinished", "ui_page")

    def test_premium_page_uses_warmed_device_snapshot_before_worker(self) -> None:
        from app.feature_facades.premium import PremiumPageData
        from donater.ui.page import PremiumPage

        snapshot = {"device_token": "token", "pair_code": None, "last_check": 123, "device_id": "dev"}
        page = SimpleNamespace(
            _premium_action_runtime=SimpleNamespace(is_running=Mock(return_value=False)),
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
            sidebar_icon_style="standard",
            garland_enabled=False,
            snowflakes_enabled=False,
        )

        appearance.clear_warmed_page_initial_state_cache()
        appearance.store_warmed_page_initial_state(state)

        self.assertIs(appearance.consume_warmed_page_initial_state(), state)
        self.assertIsNone(appearance.consume_warmed_page_initial_state())


if __name__ == "__main__":
    unittest.main()
