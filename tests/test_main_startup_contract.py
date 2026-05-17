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
