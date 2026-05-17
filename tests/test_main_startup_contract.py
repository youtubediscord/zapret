from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))


class StartupRuntimeSetupTests(unittest.TestCase):
    def test_phase_two_completion_dispatches_deferred_autostart(self) -> None:
        from main import startup_coordinator
        from main.startup_coordinator import StartupCoordinator

        class Runtime:
            def __init__(self) -> None:
                self.autostart_calls: list[str | None] = []

            def init_launch_runtime_api(self) -> None:
                pass

            def init_launch_runtime(self) -> None:
                pass

            def init_process_monitor(self) -> None:
                pass

            def init_core_startup(self) -> None:
                pass

            def start_autostart(self, launch_method: str | None = None) -> None:
                self.autostart_calls.append(launch_method)

        runtime = Runtime()
        window_shell = SimpleNamespace(
            start_in_tray=False,
            set_status=Mock(),
            mark_startup_interactive=Mock(),
            mark_startup_core_ready=Mock(),
            mark_startup_post_init_done=Mock(),
            init_theme_manager=Mock(),
        )
        tray = SimpleNamespace(
            init=Mock(),
            is_initialized=Mock(return_value=False),
        )
        coordinator = StartupCoordinator(
            runtime_feature=runtime,
            tray_feature=tray,
            window_shell=window_shell,
            log_startup_metric=Mock(),
        )

        with (
            patch.object(startup_coordinator, "run_queued", side_effect=lambda _callback: None),
            patch.object(startup_coordinator, "run_queued_with_str", side_effect=lambda callback, value: callback(value)),
            patch("settings.dpi.strategy_settings.get_strategy_launch_method", return_value="zapret2_mode"),
        ):
            coordinator.run_async_init()
            coordinator._run_phase_two_init()

        self.assertTrue(coordinator._post_init_scheduled)
        self.assertEqual(runtime.autostart_calls, ["zapret2_mode"])
        window_shell.mark_startup_post_init_done.assert_called_once()

    def test_page_actions_are_built_after_notifications_are_attached(self) -> None:
        from main import window_runtime_setup

        calls: list[str] = []
        window = SimpleNamespace()
        app_runtime = SimpleNamespace(
            features=SimpleNamespace(),
            state=SimpleNamespace(),
        )
        page_actions = object()

        def attach_notifications(target, features) -> None:
            calls.append("notifications")
            target.window_notification_center = object()

        def build_page_actions(target) -> object:
            calls.append("page_actions")
            self.assertTrue(hasattr(target, "window_notification_center"))
            return page_actions

        with (
            patch.object(window_runtime_setup, "attach_window_lifecycle", side_effect=lambda *_: calls.append("lifecycle")),
            patch.object(window_runtime_setup, "attach_window_notifications", side_effect=attach_notifications),
            patch.object(window_runtime_setup, "attach_startup_deps_to_window", side_effect=lambda *_: calls.append("startup") or SimpleNamespace(continue_deferred_init=object())),
            patch.object(window_runtime_setup, "attach_window_ui_root", side_effect=lambda *args, **kwargs: calls.append("ui_root")),
            patch.object(window_runtime_setup, "restore_window_geometry", side_effect=lambda *_: calls.append("geometry")),
            patch.object(window_runtime_setup, "connect_window_startup_signals", side_effect=lambda *args, **kwargs: calls.append("signals")),
            patch.object(window_runtime_setup, "show_initial_window_if_needed", side_effect=lambda *_: calls.append("show")),
            patch.object(window_runtime_setup, "start_window_deferred_init", side_effect=lambda *_: calls.append("deferred")),
        ):
            window_runtime_setup.attach_app_runtime_to_window(
                window,
                app_runtime,
                page_actions_factory=build_page_actions,
            )

        self.assertEqual(
            calls,
            [
                "lifecycle",
                "notifications",
                "page_actions",
                "startup",
                "ui_root",
                "geometry",
                "signals",
                "show",
                "deferred",
            ],
        )

    def test_dns_feature_exposes_startup_dns_entrypoint(self) -> None:
        from app.feature_facades.dns import build_dns_feature

        dns_feature = build_dns_feature()

        self.assertTrue(callable(dns_feature.apply_dns_on_startup_async))

    def test_window_startup_metrics_are_imported_for_interactive_ready(self) -> None:
        import main.window_startup as window_startup

        class Signal:
            def __init__(self) -> None:
                self.emitted: list[str] = []

            def emit(self, value: str) -> None:
                self.emitted.append(value)

        window = object.__new__(window_startup.WindowStartupMixin)
        window.startup_state = SimpleNamespace(
            interactive_logged=False,
            interactive_ms=None,
            ttff_ms=None,
        )
        window.startup_interactive_ready = Signal()

        with patch.object(window_startup, "emit_startup_metric") as metric:
            window.mark_startup_interactive("test_ready")

        metric.assert_called_once_with("StartupInteractive", "test_ready")
        self.assertEqual(window.startup_interactive_ready.emitted, ["test_ready"])

    def test_window_page_actions_route_pages_through_adapter(self) -> None:
        from app.page_names import PageName
        from main import window_page_actions
        from main.window_page_actions import build_window_page_actions

        window = SimpleNamespace(
            set_status=Mock(),
            window_notification_center=SimpleNamespace(notify=Mock()),
            request_exit=Mock(),
            open_connection_test=Mock(),
            open_folder=Mock(),
        )
        appearance_actions = SimpleNamespace(
            set_garland_enabled=Mock(),
            set_snowflakes_enabled=Mock(),
            set_window_opacity=Mock(),
        )

        with patch.object(window_page_actions, "show_page", return_value=True) as routed_show_page:
            actions = build_window_page_actions(
                window=window,
                appearance_actions=appearance_actions,
            )
            self.assertTrue(actions.show_page(PageName.ABOUT, allow_internal=True))

        routed_show_page.assert_called_once_with(window, PageName.ABOUT, allow_internal=True)

    def test_window_notifications_route_pages_through_adapter(self) -> None:
        from app.page_names import PageName
        from main import window_notifications_setup
        from main.window_notifications_setup import attach_window_notifications

        captured: dict[str, object] = {}

        class NotificationCenter:
            def __init__(self, *_args, show_page, **_kwargs) -> None:
                captured["show_page"] = show_page
                self.notify = Mock()

            def register_global_error_notifier(self) -> None:
                pass

        window = SimpleNamespace(
            startup_state=object(),
            isVisible=Mock(return_value=True),
            isMinimized=Mock(return_value=False),
            log_startup_metric=Mock(),
        )
        features = SimpleNamespace(
            runtime=SimpleNamespace(configure_notifications=Mock()),
            tray=SimpleNamespace(
                show_notification_if_available=Mock(),
                configure=Mock(),
            ),
        )

        with (
            patch.object(window_notifications_setup, "WindowNotificationCenter", NotificationCenter),
            patch.object(window_notifications_setup, "show_page", return_value=True) as routed_show_page,
        ):
            attach_window_notifications(window, features)
            self.assertTrue(captured["show_page"](PageName.SERVERS, allow_internal=True))

        routed_show_page.assert_called_once_with(window, PageName.SERVERS, allow_internal=True)

    def test_win11_radio_option_recommended_badge_does_not_require_global_flag(self) -> None:
        import ui.widgets.win11_controls as win11_controls

        class Badge:
            def __init__(self, *_args, **_kwargs) -> None:
                pass

        self.assertTrue(hasattr(win11_controls, "_HAS_INFO_BADGE"))

        with patch.object(win11_controls, "_HAS_INFO_BADGE", True):
            self.assertTrue(win11_controls._should_use_info_badge(Badge, object()))

        with patch.object(win11_controls, "_HAS_INFO_BADGE", False):
            self.assertFalse(win11_controls._should_use_info_badge(Badge, object()))

    def test_startup_runtime_keeps_coordinator_alive_for_queued_phase_two(self) -> None:
        from main import startup_coordinator
        from main.window_startup_setup import attach_startup_deps_to_window

        signal = SimpleNamespace(emit=Mock())
        window = SimpleNamespace(
            start_in_tray=False,
            set_status=Mock(),
            mark_startup_interactive=Mock(),
            mark_startup_core_ready=Mock(),
            mark_startup_post_init_done=Mock(),
            log_startup_metric=Mock(),
            finalize_ui_bootstrap_requested=signal,
        )
        features = SimpleNamespace(
            premium=SimpleNamespace(prepare_subscription=Mock()),
            runtime=SimpleNamespace(
                init_launch_runtime_api=Mock(),
                init_launch_runtime=Mock(),
                init_process_monitor=Mock(),
                init_core_startup=Mock(),
            ),
            tray=SimpleNamespace(
                init=Mock(),
                is_initialized=Mock(return_value=False),
            ),
        )

        runtime = attach_startup_deps_to_window(window, features)

        with patch.object(startup_coordinator, "run_queued", side_effect=lambda _callback: None):
            runtime.continue_deferred_init()

        self.assertIsNotNone(runtime.startup_coordinator)
        self.assertIsInstance(runtime.startup_coordinator, startup_coordinator.StartupCoordinator)
        signal.emit.assert_called_once()


class EarlyStartupCrashTests(unittest.TestCase):
    def test_early_startup_exception_hook_writes_crash_file_near_executable(self) -> None:
        from main.early_startup_crash import write_early_startup_crash

        with tempfile.TemporaryDirectory() as tmp:
            app_dir = Path(tmp)
            fake_exe = app_dir / "Zapret.exe"

            with patch.object(sys, "executable", str(fake_exe)):
                try:
                    raise RuntimeError("boom")
                except RuntimeError:
                    exc_type, exc, tb = sys.exc_info()
                    assert exc_type is not None
                    assert exc is not None
                    write_early_startup_crash(exc_type, exc, tb)

            crash_path = app_dir / "logs" / "crashes" / "early_startup_crash.log"
            text = crash_path.read_text(encoding="utf-8")

        self.assertIn("RuntimeError: boom", text)
        self.assertIn("early startup crash", text.lower())


class _BaseWindowEvents:
    def changeEvent(self, event) -> None:
        self.calls.append("base_change")

    def moveEvent(self, event) -> None:
        self.calls.append("base_move")

    def resizeEvent(self, event) -> None:
        self.calls.append("base_resize")

    def showEvent(self, event) -> None:
        self.calls.append("base_show")

    def isActiveWindow(self) -> bool:
        return True


class WindowLifecycleEarlyEventTests(unittest.TestCase):
    def test_resize_move_and_show_events_do_not_require_attached_runtime(self) -> None:
        from main.window_lifecycle import WindowLifecycleMixin

        class Window(WindowLifecycleMixin, _BaseWindowEvents):
            def __init__(self) -> None:
                self.calls: list[str] = []

            def findChildren(self, *_args, **_kwargs):
                return []

        window = Window()

        window.resizeEvent(object())
        window.moveEvent(object())
        window.showEvent(object())

        self.assertEqual(window.calls, ["base_resize", "base_move", "base_show"])

    def test_resize_and_show_events_use_runtime_after_it_is_attached(self) -> None:
        from main.window_lifecycle import WindowLifecycleMixin

        class Window(WindowLifecycleMixin, _BaseWindowEvents):
            def __init__(self) -> None:
                self.calls: list[str] = []
                self.window_geometry_runtime = SimpleNamespace(
                    on_geometry_changed=Mock(),
                    apply_saved_maximized_state_if_needed=Mock(),
                    enable_persistence=Mock(),
                )
                self.window_notification_center = SimpleNamespace(
                    schedule_startup_notification_queue=Mock(),
                )
                self.startup_state = SimpleNamespace(
                    ttff_logged=False,
                    ttff_ms=None,
                )
                self.visual_state = SimpleNamespace(holiday_effects=None)

            def findChildren(self, *_args, **_kwargs):
                return []

        window = Window()

        with patch("main.window_lifecycle.QTimer.singleShot", side_effect=lambda *_args, **_kwargs: None):
            window.resizeEvent(object())
            window.showEvent(object())

        window.window_geometry_runtime.on_geometry_changed.assert_called_once()
        window.window_geometry_runtime.apply_saved_maximized_state_if_needed.assert_called_once()
        window.window_notification_center.schedule_startup_notification_queue.assert_called_once_with(0)
        self.assertTrue(window.startup_state.ttff_logged)


class WindowsSessionShutdownTests(unittest.TestCase):
    def test_close_flow_skips_dialog_when_windows_session_is_ending(self) -> None:
        from ui.window_close_flow import WindowCloseFlow

        close_dialog_module = types.ModuleType("ui.close_dialog")
        close_dialog_module.ask_close_action = Mock(return_value=None)
        original_close_dialog = sys.modules.get("ui.close_dialog")
        sys.modules["ui.close_dialog"] = close_dialog_module
        try:
            event = SimpleNamespace(ignore=Mock())
            close_state = SimpleNamespace(
                closing_completely=False,
                windows_session_ending=True,
            )
            runtime = SimpleNamespace(snapshot=Mock())
            flow = WindowCloseFlow(
                parent=object(),
                close_state=close_state,
                runtime_feature=runtime,
                close_to_tray=Mock(),
                exit_stop_dpi=Mock(),
                exit_keep_dpi=Mock(),
            )

            self.assertTrue(flow.should_continue_final_close(event))
        finally:
            if original_close_dialog is None:
                sys.modules.pop("ui.close_dialog", None)
            else:
                sys.modules["ui.close_dialog"] = original_close_dialog

        event.ignore.assert_not_called()
        close_dialog_module.ask_close_action.assert_not_called()
        runtime.snapshot.assert_not_called()

    def test_session_shutdown_attempts_fast_dpi_stop_and_quits_without_second_stop(self) -> None:
        from main.application_lifecycle import ApplicationLifecycle

        close_state = SimpleNamespace(
            is_exiting=False,
            stop_dpi_on_exit=True,
            closing_completely=False,
            windows_session_ending=False,
        )
        window_port = SimpleNamespace(persist_geometry=Mock())
        runtime_feature = SimpleNamespace(shutdown_sync=Mock())
        lifecycle = ApplicationLifecycle(
            window_port=window_port,
            close_state=close_state,
            runtime_feature=runtime_feature,
            premium_feature=object(),
            telegram_proxy_feature=object(),
            tray_feature=SimpleNamespace(hide_icon_for_exit=Mock()),
        )

        with patch("main.application_lifecycle.QApplication") as q_application:
            lifecycle.exit_for_windows_session_end()

        self.assertTrue(close_state.is_exiting)
        self.assertTrue(close_state.closing_completely)
        self.assertTrue(close_state.windows_session_ending)
        self.assertFalse(close_state.stop_dpi_on_exit)
        window_port.persist_geometry.assert_called_once_with(
            context="windows_session_end",
            level="DEBUG",
        )
        runtime_feature.shutdown_sync.assert_called_once_with(
            reason="windows_session_end",
            include_cleanup=False,
            cleanup_services=False,
            update_runtime_state=False,
        )
        q_application.closeAllWindows.assert_called_once()
        q_application.processEvents.assert_called_once()
        q_application.quit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
