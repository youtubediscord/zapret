from __future__ import annotations

import sys
import tempfile
import types
import unittest
import weakref
from ctypes import addressof
from ctypes import wintypes
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
                self.calls: list[str] = []

            def init_launch_runtime_api(self) -> None:
                self.calls.append("runtime_api")

            def init_launch_runtime(self) -> None:
                self.calls.append("runtime")

            def init_process_monitor(self) -> None:
                self.calls.append("process_monitor")

            def init_core_startup(self) -> None:
                self.calls.append("core_startup")

            def start_autostart(self, launch_method: str | None = None) -> None:
                self.calls.append("autostart")
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
        scheduled: list[tuple[int, object]] = []
        timer_delays: list[int] = []

        with (
            patch.object(startup_coordinator, "run_queued", side_effect=lambda callback: scheduled.append((0, callback))),
            patch.object(
                startup_coordinator.QTimer,
                "singleShot",
                side_effect=lambda delay_ms, callback: (
                    timer_delays.append(int(delay_ms)),
                    scheduled.append((int(delay_ms), callback)),
                ),
            ),
            patch("settings.dpi.strategy_settings.get_strategy_launch_method", return_value="zapret2_mode"),
        ):
            coordinator.run_async_init()
            self.assertEqual(runtime.calls, [])
            while scheduled:
                _delay_ms, callback = scheduled.pop(0)
                callback()

        self.assertTrue(coordinator._post_init_scheduled)
        self.assertEqual(runtime.autostart_calls, ["zapret2_mode"])
        window_shell.mark_startup_interactive.assert_not_called()
        window_shell.mark_startup_post_init_done.assert_called_once()
        self.assertIn(startup_coordinator.STARTUP_STEP_GAP_MS, timer_delays)
        self.assertIn(startup_coordinator.STARTUP_DPI_AUTOSTART_DELAY_MS, timer_delays)
        self.assertEqual(
            runtime.calls,
            [
                "runtime_api",
                "runtime",
                "process_monitor",
                "core_startup",
                "autostart",
            ],
        )

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

    def test_main_defers_late_bootstrap_until_qt_event_loop_runs(self) -> None:
        from main import entry
        import main.application_controller as application_controller_module
        import main.window as window_module
        import main.windows_session_shutdown as shutdown_module

        calls: list[str] = []
        scheduled: list[tuple[int, object]] = []
        timer_delays: list[int] = []
        app_runtime = object()

        class Signal:
            def __init__(self) -> None:
                self._callbacks: list[object] = []

            def connect(self, callback) -> None:
                self._callbacks.append(callback)

            def emit(self, value: str = "") -> None:
                for callback in list(self._callbacks):
                    callback(value)

        startup_signal = Signal()
        window = SimpleNamespace(
            startup_state=SimpleNamespace(interactive_logged=False),
            startup_interactive_ready=startup_signal,
        )

        class App:
            def exec(self) -> int:
                calls.append("app.exec")
                while scheduled:
                    _delay, callback = scheduled.pop(0)
                    callback()
                calls.append("startup_interactive.emit")
                window.startup_state.interactive_logged = True
                startup_signal.emit("ui_ready")
                while scheduled:
                    _delay, callback = scheduled.pop(0)
                    callback()
                return 0

        class Controller:
            def __init__(self, *, window_cls, start_in_tray) -> None:
                calls.append("controller.init")
                self.app_runtime = app_runtime
                self.window_state_actions = object()

            def create_window(self):
                calls.append("create_window")
                return window

        class Ipc:
            def start_server(self, target_window) -> None:
                calls.append("ipc.start")

            def stop(self) -> None:
                calls.append("ipc.stop")

        with (
            patch.object(entry, "shell_bootstrap", return_value=False),
            patch.object(entry, "application_bootstrap", return_value=App()),
            patch.object(entry, "is_qt_event_diagnostic_enabled", return_value=False),
            patch.object(application_controller_module, "ApplicationController", Controller),
            patch.object(window_module, "LupiDPIApp", object()),
            patch.object(shutdown_module, "connect_windows_session_shutdown", side_effect=lambda *_: calls.append("shutdown.hook")),
            patch.object(entry, "_configure_window_appearance", side_effect=lambda *_: calls.append("appearance")),
            patch.object(entry, "_create_ipc_manager", side_effect=lambda: Ipc()),
            patch.object(
                entry.QTimer,
                "singleShot",
                side_effect=lambda delay, callback: (
                    timer_delays.append(int(delay)),
                    calls.append("schedule.late_bootstrap"),
                    scheduled.append((delay, callback)),
                ),
            ),
            patch.object(entry, "_build_application_post_startup_deps", side_effect=lambda **_: calls.append("build_post_startup_deps") or object()),
            patch.object(entry, "_install_post_startup_tasks", side_effect=lambda *_: calls.append("install_post_startup")),
            patch.object(entry.atexit, "register", side_effect=lambda *_: calls.append("atexit.register")),
        ):
            with self.assertRaises(SystemExit):
                entry.main()

        self.assertEqual(timer_delays[0], 0)
        self.assertLess(calls.index("schedule.late_bootstrap"), calls.index("app.exec"))
        self.assertLess(calls.index("app.exec"), calls.index("install_post_startup"))
        self.assertLess(calls.index("startup_interactive.emit"), calls.index("install_post_startup"))
        self.assertLess(calls.index("appearance"), calls.index("install_post_startup"))
        self.assertLess(calls.index("ipc.start"), calls.index("install_post_startup"))

    def test_post_startup_install_is_bound_to_interactive_ready(self) -> None:
        from main import entry

        class Signal:
            def __init__(self) -> None:
                self._callbacks: list[object] = []

            def connect(self, callback) -> None:
                self._callbacks.append(callback)

            def emit(self, value: str = "") -> None:
                for callback in list(self._callbacks):
                    callback(value)

        signal = Signal()
        window = SimpleNamespace(
            startup_state=SimpleNamespace(interactive_logged=False),
            startup_interactive_ready=signal,
        )
        deps = object()
        scheduled: list[tuple[int, object]] = []
        installed: list[object] = []

        with (
            patch.object(
                entry.QTimer,
                "singleShot",
                side_effect=lambda delay, callback: scheduled.append((int(delay), callback)),
            ),
            patch.object(entry, "_install_post_startup_tasks", side_effect=lambda value: installed.append(value)),
        ):
            entry._install_post_startup_tasks_after_interactive(window, deps)
            self.assertEqual(installed, [])
            self.assertEqual(scheduled, [])

            window.startup_state.interactive_logged = True
            signal.emit("ui_ready")
            self.assertEqual(installed, [])
            self.assertEqual(scheduled[0][0], 0)
            scheduled.pop(0)[1]()

        self.assertEqual(installed, [deps])

    def test_entry_keeps_post_startup_imports_out_of_top_level(self) -> None:
        import inspect
        from main import entry

        source = inspect.getsource(entry)
        top_level = source.split("def _create_ipc_manager", 1)[0]

        self.assertNotIn("from startup.ipc_manager import IPCManager", top_level)
        self.assertNotIn("from main.application_post_startup import build_application_post_startup_deps", top_level)
        self.assertNotIn("from main.post_startup import install_post_startup_tasks", top_level)

    def test_post_startup_module_keeps_task_imports_lazy(self) -> None:
        import inspect
        from main import post_startup

        source = inspect.getsource(post_startup)
        top_level = source.split("def install_startup_checks", 1)[0]

        self.assertNotIn("from main.post_startup_checks import", top_level)
        self.assertNotIn("from main.post_startup_dns_warmup import", top_level)
        self.assertNotIn("from main.post_startup_page_warmup import", top_level)
        self.assertNotIn("from main.post_startup_update import", top_level)

    def test_startup_log_contract_accepts_ui_before_runtime_order(self) -> None:
        from main.startup_log_contract import validate_startup_log_contract

        result = validate_startup_log_contract(
            "\n".join(
                (
                    "[12:00:00] [⏱ STARTUP] ⏱ Startup StartupTTFF: 1000ms | first showEvent",
                    "[12:00:01] [⏱ STARTUP] ⏱ Startup StartupInteractive: 1200ms | ui_ready",
                    "[12:00:01] [⏱ STARTUP] ⏱ Startup StartupRuntimeInitQueued: 1450ms | 25ms gaps",
                    "[12:00:02] [⏱ STARTUP] ⏱ Startup StartupCoreReady: 1800ms | startup_coordinator",
                    "[12:00:02] [⏱ STARTUP] ⏱ Startup StartupPostInit: 1900ms | post_init_scheduled",
                    "[12:00:02] [⏱ STARTUP] ⏱ Startup StartupPostInitDeferredStart: 2300ms | zapret2_mode",
                    "[12:00:02] [⏱ STARTUP] ⏱ Startup StartupNetworkDataWarmupQueued: 2400ms | 1200ms after interactive",
                    "[12:00:02] [⏱ STARTUP] ⏱ Startup StartupSidebarSearchQueued: 2500ms | 1000ms after interactive",
                    "[12:00:02] [⏱ STARTUP] ⏱ Startup StartupHiddenModeNavQueued: 2800ms | 1600ms after interactive",
                )
            )
        )

        self.assertTrue(result.ok, result.errors)

    def test_startup_log_contract_rejects_runtime_before_interactive(self) -> None:
        from main.startup_log_contract import validate_startup_log_contract

        result = validate_startup_log_contract(
            "\n".join(
                (
                    "[12:00:00] [⏱ STARTUP] ⏱ Startup StartupTTFF: 1000ms | first showEvent",
                    "[12:00:01] [⏱ STARTUP] ⏱ Startup StartupRuntimeInitQueued: 1100ms | 25ms gaps",
                    "[12:00:01] [⏱ STARTUP] ⏱ Startup StartupInteractive: 1300ms | ui_ready",
                )
            )
        )

        self.assertFalse(result.ok)
        self.assertTrue(any("StartupRuntimeInitQueued" in error for error in result.errors))

    def test_startup_log_contract_rejects_gui_page_warmup_during_startup(self) -> None:
        from main.startup_log_contract import validate_startup_log_contract

        result = validate_startup_log_contract(
            "\n".join(
                (
                    "[12:00:00] [⏱ STARTUP] ⏱ Startup StartupTTFF: 1000ms | first showEvent",
                    "[12:00:01] [⏱ STARTUP] ⏱ Startup StartupInteractive: 1300ms | ui_ready",
                    "[12:00:10] [⏱ STARTUP] ⏱ PageLifecycle: NETWORK warmup 237ms",
                )
            )
        )

        self.assertFalse(result.ok)
        self.assertTrue(any("GUI-прогрев страницы" in error for error in result.errors))

    def test_startup_log_contract_rejects_startup_page_warmup_queue(self) -> None:
        from main.startup_log_contract import validate_startup_log_contract

        result = validate_startup_log_contract(
            "\n".join(
                (
                    "[12:00:00] [⏱ STARTUP] ⏱ Startup StartupTTFF: 1000ms | first showEvent",
                    "[12:00:01] [⏱ STARTUP] ⏱ Startup StartupInteractive: 1300ms | ui_ready",
                    "[12:00:10] [⏱ STARTUP] ⏱ Startup StartupPageNetworkWarmupQueued: 9000ms | NETWORK",
                )
            )
        )

        self.assertFalse(result.ok)
        self.assertTrue(any("Во время запуска можно греть только данные" in error for error in result.errors))

    def test_dns_feature_exposes_startup_dns_entrypoint(self) -> None:
        from app.feature_facades.dns import build_dns_feature

        dns_feature = build_dns_feature()

        self.assertTrue(callable(dns_feature.apply_dns_on_startup_async))
        self.assertTrue(callable(dns_feature.warm_page_data_cache))
        self.assertTrue(callable(dns_feature.consume_warmed_page_data))

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

    def test_initial_manual_launch_state_keeps_runtime_buttons_preparing(self) -> None:
        from app.feature_facades.runtime_parts import RuntimeObjects
        from winws_runtime.state import LaunchRuntimeService

        _ = RuntimeObjects
        state = LaunchRuntimeService.build_initial_ui_state(
            launch_method="zapret2_mode",
            dpi_autostart_enabled=False,
            gui_autostart_enabled=False,
            launch_supported=True,
        )

        self.assertEqual(state.launch_phase, "stopped")
        self.assertTrue(state.launch_busy)
        self.assertIn("Подготов", state.launch_busy_text)

    def test_initial_autostart_state_uses_autostart_pending_without_extra_busy_flag(self) -> None:
        from app.feature_facades.runtime_parts import RuntimeObjects
        from winws_runtime.state import LaunchRuntimeService

        _ = RuntimeObjects
        state = LaunchRuntimeService.build_initial_ui_state(
            launch_method="zapret2_mode",
            dpi_autostart_enabled=True,
            gui_autostart_enabled=False,
            launch_supported=True,
        )

        self.assertEqual(state.launch_phase, "autostart_pending")
        self.assertFalse(state.launch_busy)
        self.assertEqual(state.launch_busy_text, "")

    def test_runtime_init_clears_startup_button_preparation(self) -> None:
        from app.feature_facades.runtime_parts import RuntimeCommandPort

        runtime_object = object()
        runtime_service = SimpleNamespace(set_busy=Mock())
        owner = SimpleNamespace(
            objects=SimpleNamespace(
                launch_runtime_api=object(),
                launch_runtime=None,
                runtime_service=runtime_service,
            ),
            ui_port=SimpleNamespace(require_notifications=Mock(return_value=object())),
        )
        commands = RuntimeCommandPort(owner)
        runtime_commands = SimpleNamespace(init_launch_runtime=Mock(return_value=runtime_object))

        with patch.object(RuntimeCommandPort, "_runtime_commands", staticmethod(lambda: runtime_commands)):
            commands.init_launch_runtime()

        self.assertIs(owner.objects.launch_runtime, runtime_object)
        runtime_service.set_busy.assert_called_once_with(False)

    def test_runtime_api_init_failure_clears_startup_button_preparation(self) -> None:
        from app.feature_facades.runtime_parts import RuntimeCommandPort

        runtime_service = SimpleNamespace(set_busy=Mock(), mark_start_failed=Mock())
        owner = SimpleNamespace(
            objects=SimpleNamespace(
                launch_runtime_api=None,
                runtime_service=runtime_service,
            ),
        )
        commands = RuntimeCommandPort(owner)
        runtime_commands = SimpleNamespace(init_launch_runtime_api=Mock(side_effect=RuntimeError("boom")))

        with patch.object(RuntimeCommandPort, "_runtime_commands", staticmethod(lambda: runtime_commands)):
            with self.assertRaises(RuntimeError):
                commands.init_launch_runtime_api()

        runtime_service.set_busy.assert_called_once_with(False)
        runtime_service.mark_start_failed.assert_called_once_with("boom")

    def test_runtime_init_failure_clears_startup_button_preparation(self) -> None:
        from app.feature_facades.runtime_parts import RuntimeCommandPort

        runtime_service = SimpleNamespace(set_busy=Mock(), mark_start_failed=Mock())
        owner = SimpleNamespace(
            objects=SimpleNamespace(
                launch_runtime_api=object(),
                launch_runtime=None,
                runtime_service=runtime_service,
            ),
            ui_port=SimpleNamespace(require_notifications=Mock(return_value=object())),
        )
        commands = RuntimeCommandPort(owner)
        runtime_commands = SimpleNamespace(init_launch_runtime=Mock(side_effect=RuntimeError("boom")))

        with patch.object(RuntimeCommandPort, "_runtime_commands", staticmethod(lambda: runtime_commands)):
            with self.assertRaises(RuntimeError):
                commands.init_launch_runtime()

        runtime_service.set_busy.assert_called_once_with(False)
        runtime_service.mark_start_failed.assert_called_once_with("boom")

    def test_runtime_feature_assembly_uses_light_state_import_before_ui(self) -> None:
        import inspect
        from app.feature_facades import runtime as runtime_feature_module
        from app.feature_facades import runtime_parts

        runtime_source = inspect.getsource(runtime_feature_module)
        runtime_parts_source = inspect.getsource(runtime_parts)

        self.assertIn("from winws_runtime.state import LaunchRuntimeService", runtime_source)
        self.assertNotIn("from winws_runtime.public import LaunchRuntimeService", runtime_source)
        self.assertNotIn("import winws_runtime.public as runtime_commands", runtime_parts_source)

    def test_non_initial_feature_facades_do_not_import_heavy_command_modules_before_ui(self) -> None:
        import inspect
        from app.feature_facades import (
            blockcheck,
            logs,
            orchestra,
            premium,
            presets,
            profile,
            program_settings,
            tray,
            updater,
        )

        blocked_top_level_imports = {
            blockcheck: (
                "import blockcheck.public as blockcheck_commands",
                "import blockcheck.page_runtime as blockcheck_page_runtime",
                "from blockcheck import commands as blockcheck_worker_commands",
            ),
            logs: (
                "import log.commands as log_commands",
                "import log.runtime_workflow as log_runtime",
            ),
            orchestra: (
                "import orchestra.commands as orchestra_commands",
            ),
            premium: (
                "import donater.commands as premium_commands",
            ),
            presets: (
                "import presets.commands as preset_commands",
                "import presets.display_state as preset_display",
            ),
            profile: (
                "from profile import commands as profile_internal_commands",
                "from profile import settings as profile_settings",
            ),
            program_settings: (
                "import program_settings.public as program_settings_commands",
            ),
            tray: (
                "import tray_commands",
            ),
            updater: (
                "import updater.public as updater_commands",
            ),
        }

        for module, forbidden_imports in blocked_top_level_imports.items():
            source = inspect.getsource(module)
            top_level = source.split("@dataclass", 1)[0]
            for import_line in forbidden_imports:
                self.assertNotIn(import_line, top_level)

    def test_lazy_feature_facades_still_call_loaded_command_modules(self) -> None:
        from app.feature_facades.blockcheck import BlockcheckFeature
        from app.feature_facades.external import ExternalActionsFeature
        from app.feature_facades.logs import LogsFeature
        from app.feature_facades.orchestra import OrchestraFeature
        from app.feature_facades.presets import PresetsFeature
        from app.feature_facades.tray import TrayFeature
        from app.feature_facades.updater import UpdaterFeature

        blockcheck_commands = SimpleNamespace(
            build_language_plan=Mock(return_value="blockcheck-plan"),
        )
        logs_commands = SimpleNamespace(
            build_stats=Mock(return_value="logs-stats"),
        )
        orchestra_commands = SimpleNamespace(
            is_default_blocked_pass_domain=Mock(return_value=True),
        )
        preset_commands = SimpleNamespace(
            get_selected_source_preset_file_name=Mock(return_value="preset.txt"),
        )
        tray_commands = SimpleNamespace(
            show_tray_notification_if_available=Mock(return_value=True),
        )
        updater_commands = SimpleNamespace(
            is_auto_update_enabled=Mock(return_value=True),
        )
        external_actions = SimpleNamespace(
            open_url=Mock(return_value="opened"),
        )

        blockcheck_feature = BlockcheckFeature(presets_feature=object(), profile_feature=object())
        external_actions_feature = ExternalActionsFeature()
        logs_feature = LogsFeature()
        orchestra_feature = OrchestraFeature(whitelist_runtime_service=object())
        presets_feature = PresetsFeature(_services=object())
        tray_feature = TrayFeature(
            _deps=SimpleNamespace(),
            _runtime_feature=SimpleNamespace(),
            _telegram_proxy_feature=SimpleNamespace(),
            _tray_manager="tray-manager",
        )
        updater_feature = UpdaterFeature()

        with (
            patch.object(BlockcheckFeature, "_commands", staticmethod(lambda: blockcheck_commands)),
            patch.object(ExternalActionsFeature, "_actions", staticmethod(lambda: external_actions)),
            patch.object(LogsFeature, "_commands", staticmethod(lambda: logs_commands)),
            patch.object(OrchestraFeature, "_commands", staticmethod(lambda: orchestra_commands)),
            patch.object(PresetsFeature, "_commands", staticmethod(lambda: preset_commands)),
            patch.object(TrayFeature, "_commands", staticmethod(lambda: tray_commands)),
            patch.object(UpdaterFeature, "_commands", staticmethod(lambda: updater_commands)),
        ):
            self.assertEqual(blockcheck_feature.build_language_plan(), "blockcheck-plan")
            self.assertEqual(external_actions_feature.open_url("https://example.org"), "opened")
            self.assertEqual(logs_feature.build_stats(), "logs-stats")
            self.assertTrue(orchestra_feature.is_default_blocked_pass_domain("example.org"))
            self.assertEqual(presets_feature.get_selected_source_preset_file_name("zapret2_mode"), "preset.txt")
            self.assertTrue(tray_feature.show_notification_if_available("Title", "Text"))
            self.assertTrue(updater_feature.is_auto_update_enabled())

        blockcheck_commands.build_language_plan.assert_called_once_with()
        external_actions.open_url.assert_called_once_with("https://example.org")
        logs_commands.build_stats.assert_called_once_with()
        orchestra_commands.is_default_blocked_pass_domain.assert_called_once_with("example.org")
        preset_commands.get_selected_source_preset_file_name.assert_called_once_with(
            "zapret2_mode",
            preset_services=presets_feature._services,
        )
        tray_commands.show_tray_notification_if_available.assert_called_once_with(
            tray_manager="tray-manager",
            title="Title",
            content="Text",
        )
        updater_commands.is_auto_update_enabled.assert_called_once_with()

    def test_external_actions_feature_supports_qt_signal_weakrefs(self) -> None:
        from app.feature_facades.external import ExternalActionsFeature

        feature = ExternalActionsFeature()

        self.assertIs(weakref.ref(feature)(), feature)

    def test_feature_builders_do_not_import_page_command_modules_before_ui(self) -> None:
        import builtins
        from app.feature_facades.autostart import build_autostart_feature
        from app.feature_facades.blobs import build_blobs_feature
        from app.feature_facades.diagnostics import build_diagnostics_feature
        from app.feature_facades.dns import build_dns_feature
        from app.feature_facades.dpi_settings import build_dpi_settings_feature
        from app.feature_facades.external import build_external_actions_feature
        from app.feature_facades.hosts import build_hosts_feature
        from app.feature_facades.lists import build_lists_feature
        from app.feature_facades.orchestra import build_orchestra_feature
        from app.feature_facades.premium import build_premium_feature
        from app.feature_facades.program_settings import build_program_settings_feature
        from app.feature_facades.presets import PresetsFeature
        from app.feature_facades.telegram_proxy import build_telegram_proxy_feature
        from app.feature_facades.updater import build_updater_feature

        blocked_roots = {
            "autostart",
            "blobs",
            "diagnostics",
            "dns",
            "app",
            "core",
            "hosts",
            "lists",
            "orchestra",
            "presets",
            "donater",
            "program_settings",
            "telegram_proxy",
            "updater",
        }
        imported: list[tuple[str, tuple[str, ...]]] = []
        real_import = builtins.__import__

        def tracking_import(name, globals=None, locals=None, fromlist=(), level=0):
            root = str(name or "").split(".", 1)[0]
            if root in blocked_roots:
                imported.append((str(name), tuple(str(item) for item in (fromlist or ()))))
            return real_import(name, globals, locals, fromlist, level)

        runtime_state = SimpleNamespace(set_autostart=Mock())
        premium_deps = SimpleNamespace(
            thread_parent=object(),
            set_status=Mock(),
            update_title_badge=Mock(),
            init_holiday_effects=Mock(),
            mark_startup_ready=Mock(),
        )
        with patch.object(builtins, "__import__", side_effect=tracking_import):
            build_autostart_feature(runtime_state=runtime_state)
            build_blobs_feature()
            build_diagnostics_feature()
            build_dns_feature()
            build_dpi_settings_feature()
            build_external_actions_feature()
            build_hosts_feature()
            build_lists_feature()
            build_orchestra_feature()
            build_premium_feature(deps=premium_deps, ui_state_store=object())
            build_program_settings_feature()
            build_telegram_proxy_feature()
            build_updater_feature()
            PresetsFeature.create(object())

        self.assertEqual(imported, [])

    def test_orchestra_whitelist_runtime_service_is_created_lazily(self) -> None:
        from app.feature_facades.orchestra import OrchestraFeature, build_orchestra_feature

        created_services: list[object] = []
        runtime_service = object()
        commands = SimpleNamespace(
            get_whitelist_snapshot=Mock(return_value="snapshot"),
        )

        def create_runtime_service():
            created_services.append(runtime_service)
            return runtime_service

        with (
            patch.object(OrchestraFeature, "_create_whitelist_runtime_service", staticmethod(create_runtime_service)),
            patch.object(OrchestraFeature, "_commands", staticmethod(lambda: commands)),
        ):
            feature = build_orchestra_feature()
            self.assertEqual(created_services, [])

            self.assertEqual(feature.get_whitelist_snapshot(None), "snapshot")

        self.assertEqual(created_services, [runtime_service])
        commands.get_whitelist_snapshot.assert_called_once_with(
            None,
            whitelist_service=runtime_service,
            refresh=False,
        )

    def test_premium_subscription_ui_actions_are_created_lazily(self) -> None:
        from app.feature_facades.premium import PremiumFeature, build_premium_feature

        created_actions: list[object] = []
        deps = SimpleNamespace(
            thread_parent="thread-parent",
            set_status=Mock(),
            update_title_badge=Mock(),
            init_holiday_effects=Mock(),
            mark_startup_ready=Mock(),
        )
        ui_state_store = object()
        ui_actions = object()
        commands = SimpleNamespace(
            create_subscription_manager=Mock(return_value="manager"),
        )

        def ensure_ui_actions(feature):
            created_actions.append(
                (
                    feature._deps,
                    feature._ui_state_store,
                )
            )
            feature._ui_actions = ui_actions
            return ui_actions

        with (
            patch.object(PremiumFeature, "_ensure_ui_actions", ensure_ui_actions),
            patch.object(PremiumFeature, "_commands", staticmethod(lambda: commands)),
        ):
            feature = build_premium_feature(deps=deps, ui_state_store=ui_state_store)
            self.assertEqual(created_actions, [])

            feature.prepare_subscription()

        self.assertEqual(created_actions, [(deps, ui_state_store)])
        commands.create_subscription_manager.assert_called_once_with(
            thread_parent="thread-parent",
            ui_actions=ui_actions,
        )

    def test_program_settings_runtime_service_is_created_lazily(self) -> None:
        from app.feature_facades.program_settings import ProgramSettingsFeature, build_program_settings_feature

        created_services: list[object] = []
        runtime_service = object()
        commands = SimpleNamespace(
            refresh_program_settings_snapshot=Mock(return_value="snapshot"),
        )

        def create_runtime_service():
            created_services.append(runtime_service)
            return runtime_service

        with (
            patch.object(ProgramSettingsFeature, "_create_runtime_service", staticmethod(create_runtime_service)),
            patch.object(ProgramSettingsFeature, "_commands", staticmethod(lambda: commands)),
        ):
            feature = build_program_settings_feature()
            self.assertEqual(created_services, [])

            self.assertEqual(feature.refresh_program_settings_snapshot(), "snapshot")

        self.assertEqual(created_services, [runtime_service])
        commands.refresh_program_settings_snapshot.assert_called_once_with(runtime_service)

    def test_startup_checks_are_delayed_after_ui_ready(self) -> None:
        from main import post_startup_checks
        from main.post_startup_checks import install_startup_checks

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
        scheduled: list[tuple[int, object]] = []
        thread_names: list[str] = []

        with (
            patch.object(
                post_startup_checks,
                "schedule_after",
                create=True,
                side_effect=lambda delay_ms, callback: scheduled.append((delay_ms, callback)),
            ),
            patch.object(
                post_startup_checks,
                "start_daemon_thread",
                side_effect=lambda name, target: thread_names.append(name),
            ),
        ):
            install_startup_checks(
                startup_host,
                notify_many=Mock(),
                set_status=Mock(),
                log_startup_metric=Mock(),
            )
            signal.emit("ui_ready")

            self.assertEqual(thread_names, [])
            self.assertEqual(len(scheduled), 1)
            self.assertGreaterEqual(scheduled[0][0], 500)

            scheduled[0][1]()
            self.assertEqual(thread_names, ["StartupChecksWorker"])

    def test_deferred_init_marks_ui_interactive_before_delayed_runtime_continue(self) -> None:
        from PyQt6.QtCore import QTimer
        import main.window_startup as window_startup

        calls: list[str] = []
        scheduled: list[tuple[int, object]] = []

        class Signal:
            def emit(self) -> None:
                calls.append("continue_startup")

        window = object.__new__(window_startup.WindowStartupMixin)
        window.startup_state = SimpleNamespace(deferred_init_started=False)
        window.continue_startup_requested = Signal()
        window.build_ui = Mock(side_effect=lambda *_args: calls.append("build_ui"))
        window.mark_startup_interactive = Mock(side_effect=lambda source: calls.append(f"interactive:{source}"))

        with (
            patch.object(
                QTimer,
                "singleShot",
                side_effect=lambda delay_ms, callback: scheduled.append((delay_ms, callback)),
            ),
            patch.object(window_startup, "emit_startup_metric") as metric,
        ):
            window_startup.WindowStartupMixin._deferred_init(window)

        self.assertEqual(
            calls,
            [
                "build_ui",
                "interactive:ui_ready",
            ],
        )
        self.assertEqual(len(scheduled), 1)
        self.assertLessEqual(scheduled[0][0], 250)
        metric.assert_called_once_with("StartupContinueAfterUiReadyQueued", f"{scheduled[0][0]}ms")

        with patch.object(window_startup, "emit_startup_metric") as metric:
            scheduled[0][1]()
        self.assertEqual(calls[-1], "continue_startup")
        metric.assert_called_once_with("StartupContinueAfterUiReadyDispatch", "continue_startup_requested")
        window.mark_startup_interactive.assert_called_once_with("ui_ready")

    def test_eager_page_creation_does_not_pump_qt_events_before_interactive(self) -> None:
        import inspect
        from app.page_names import PageName
        from ui.page_host import WindowPageHost
        import ui.page_host as page_host_module

        calls: list[str] = []

        class Page:
            def objectName(self) -> str:
                return "Page"

            def setObjectName(self, _name: str) -> None:
                pass

        class Factory:
            page_class_specs = {}

            def create_page(self, page_name):
                calls.append(f"create:{page_name.name}")
                return SimpleNamespace(page=Page(), elapsed_ms=1)

        host = WindowPageHost(SimpleNamespace(get_launch_method=lambda: "zapret2_mode"), Factory())

        with (
            patch.object(page_host_module, "apply_ui_language_to_page", side_effect=lambda *_args: None),
            patch.object(page_host_module, "record_startup_page_init_metric", side_effect=lambda *_args: None),
            patch.object(page_host_module, "log_page_metric", side_effect=lambda *_args, **_kwargs: None),
        ):
            host.create_eager_pages((PageName.ZAPRET2_MODE_CONTROL,))

        self.assertEqual(calls, ["create:ZAPRET2_MODE_CONTROL"])
        source = inspect.getsource(WindowPageHost.create_eager_pages)
        self.assertNotIn("pump_startup_ui", source)

    def test_window_geometry_settings_are_read_once_for_startup_restore(self) -> None:
        from settings import store as settings_store

        data = {
            "window": {
                "x": 10,
                "y": 20,
                "width": 1200,
                "height": 800,
                "maximized": True,
            }
        }

        with patch.object(settings_store, "read_settings", return_value=data) as read_settings:
            geometry = settings_store.get_window_geometry()

        self.assertEqual(
            geometry,
            {
                "x": 10,
                "y": 20,
                "width": 1200,
                "height": 800,
                "maximized": True,
            },
        )
        read_settings.assert_called_once_with()

    def test_window_geometry_runtime_loads_saved_geometry_with_single_settings_read(self) -> None:
        from settings import store as settings_store
        from ui.window_geometry_runtime import SettingsWindowGeometryStore

        data = {
            "x": 10,
            "y": 20,
            "width": 1200,
            "height": 800,
            "maximized": True,
        }

        with patch.object(settings_store, "get_window_geometry", return_value=data) as get_geometry:
            geometry = SettingsWindowGeometryStore().load()

        self.assertEqual(geometry.position, (10, 20))
        self.assertEqual(geometry.size, (1200, 800))
        self.assertTrue(geometry.maximized)
        get_geometry.assert_called_once_with()

    def test_initial_ui_state_uses_single_settings_read_and_light_runtime_state_import(self) -> None:
        import inspect
        import app.initial_ui_state as initial_ui_state
        from app.initial_ui_state import build_initial_ui_state

        data = {
            "program": {
                "dpi_autostart": True,
                "gui_autostart_enabled": False,
                "strategy_launch_method": "zapret2_mode",
            }
        }

        source = inspect.getsource(initial_ui_state)
        self.assertIn("from winws_runtime.state import LaunchRuntimeService", source)
        self.assertNotIn("from winws_runtime.public import LaunchRuntimeService", source)

        with patch("settings.store.read_settings", return_value=data) as read_settings:
            state = build_initial_ui_state()

        read_settings.assert_called_once_with()
        self.assertEqual(state.launch_method, "zapret2_mode")

    def test_zapret2_control_defers_heavy_sections_until_startup_interactive(self) -> None:
        from presets.ui.control.zapret2 import page as zapret2_page
        from presets.ui.control.zapret2.page import Zapret2ModeControlPage

        connected: list[object] = []
        scheduled: list[tuple[int, object]] = []

        class Signal:
            def connect(self, callback, *_args, **_kwargs) -> None:
                connected.append(callback)

        control_page = Zapret2ModeControlPage.__new__(Zapret2ModeControlPage)
        control_page._cleanup_in_progress = False
        control_page._deferred_sections_built = False
        control_page._deferred_sections_hydrated = False
        control_page._startup_deferred_sections_waiting = False
        control_page._startup_showevent_profile_logged = False
        control_page._refresh_runtime = SimpleNamespace(additional_settings_dirty=False)
        control_page.deferred_show_requested = SimpleNamespace(emit=Mock())
        control_page.is_page_ready = Mock(return_value=True)
        control_page.run_when_page_ready = Mock(side_effect=lambda callback: callback() or True)
        control_page.window = Mock(
            return_value=SimpleNamespace(
                startup_state=SimpleNamespace(interactive_logged=False),
                startup_interactive_ready=Signal(),
            )
        )

        with patch.object(zapret2_page, "_log_startup_winws2_control_metric"):
            Zapret2ModeControlPage._apply_pending_mode_refresh_if_ready(control_page)

        control_page.deferred_show_requested.emit.assert_not_called()
        self.assertEqual(len(connected), 1)

        control_page.window.return_value.startup_state.interactive_logged = True
        with patch.object(
            zapret2_page.QTimer,
            "singleShot",
            side_effect=lambda delay_ms, callback: scheduled.append((delay_ms, callback)),
        ):
            connected[0]("ui_ready")

        self.assertEqual(len(scheduled), 1)
        self.assertGreaterEqual(scheduled[0][0], 150)
        scheduled[0][1]()

        control_page.deferred_show_requested.emit.assert_called_once()

    def test_zapret2_control_defers_top_summary_data_until_startup_interactive(self) -> None:
        from app.state_store import AppUiState
        from presets.ui.control.zapret2 import page as zapret2_page
        from presets.ui.control.zapret2.page import Zapret2ModeControlPage

        connected: list[object] = []
        scheduled: list[tuple[int, object]] = []

        class Signal:
            def connect(self, callback, *_args, **_kwargs) -> None:
                connected.append(callback)

        control_page = Zapret2ModeControlPage.__new__(Zapret2ModeControlPage)
        control_page._cleanup_in_progress = False
        control_page._startup_top_summary_waiting = False
        control_page._refresh_runtime = SimpleNamespace(additional_settings_dirty=False)
        control_page._ui_language = "ru"
        control_page._ui_state_store = None
        control_page.top_summary = SimpleNamespace(
            set_preset=Mock(),
            set_profile_count=Mock(),
            set_premium=Mock(),
        )
        control_page._presets = SimpleNamespace(
            get_selected_source_preset_display=Mock(return_value=("Preset", "Preset"))
        )
        control_page._profile = SimpleNamespace(get_enabled_profile_count_snapshot=Mock(return_value=2))
        control_page.window = Mock(
            return_value=SimpleNamespace(
                startup_state=SimpleNamespace(interactive_logged=False),
                startup_interactive_ready=Signal(),
            )
        )
        control_page.set_loading = Mock()
        control_page.update_status = Mock()
        control_page.update_strategy = Mock()
        control_page._refresh_last_status_message = Mock()
        control_page._sync_profile_ui_mode_from_settings = Mock()

        Zapret2ModeControlPage._on_ui_state_changed(control_page, AppUiState(), frozenset())

        control_page._presets.get_selected_source_preset_display.assert_not_called()
        control_page._profile.get_enabled_profile_count_snapshot.assert_not_called()
        self.assertEqual(len(connected), 1)

        control_page.window.return_value.startup_state.interactive_logged = True
        control_page.run_when_page_ready = Mock(side_effect=lambda callback: callback() or True)
        with patch.object(
            zapret2_page.QTimer,
            "singleShot",
            side_effect=lambda delay_ms, callback: scheduled.append((delay_ms, callback)),
        ):
            connected[0]("ui_ready")

        self.assertEqual(len(scheduled), 1)
        self.assertGreaterEqual(scheduled[0][0], 150)
        scheduled[0][1]()

        control_page._presets.get_selected_source_preset_display.assert_called_once()
        control_page._profile.get_enabled_profile_count_snapshot.assert_called_once()
        control_page.top_summary.set_preset.assert_called_with("Preset")
        control_page.top_summary.set_profile_count.assert_called_with(2)

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

    def test_control_start_waits_until_runtime_is_available(self) -> None:
        from presets.ui.control import control_page_shared
        from presets.ui.control.control_page_shared import ControlPageActionMixin

        class Page(ControlPageActionMixin):
            def __init__(self) -> None:
                self.loading_calls: list[tuple[bool, str]] = []
                self.status_calls: list[str] = []
                self._runtime_feature = SimpleNamespace(
                    is_available=Mock(side_effect=[False, False, True]),
                    start=Mock(return_value=True),
                )
                self._set_status_callback = self.status_calls.append

            def set_loading(self, loading: bool, text: str = "") -> None:
                self.loading_calls.append((loading, text))

        page = Page()
        scheduled: list[object] = []

        with patch.object(
            control_page_shared.QTimer,
            "singleShot",
            side_effect=lambda _delay_ms, callback: scheduled.append(callback),
        ):
            page._start_dpi()
            self.assertEqual(len(scheduled), 1)
            scheduled.pop(0)()
            self.assertEqual(len(scheduled), 1)
            scheduled.pop(0)()

        page._runtime_feature.start.assert_called_once_with()
        self.assertIn((True, "Подготовка запуска..."), page.loading_calls)
        self.assertEqual(page.loading_calls[-1], (False, ""))
        self.assertIn("Подготовка запуска...", page.status_calls)

    def test_post_startup_tasks_do_not_install_gui_page_warmup(self) -> None:
        from main import post_startup
        from main.post_startup import PostStartupDeps, install_post_startup_tasks

        startup_host = object()
        profile_feature = object()
        log_startup_metric = Mock()
        deps = PostStartupDeps(
            startup_host=startup_host,
            profile_feature=profile_feature,
            dns_feature=object(),
            notify=Mock(),
            notify_many=Mock(),
            set_status=Mock(),
            log_startup_metric=log_startup_metric,
            start_proxy_if_enabled_async=Mock(),
            startup_lists_check=Mock(),
            apply_dns_on_startup_async=Mock(),
            install_tray_post_startup=Mock(),
            updater_feature=Mock(),
        )

        with (
            patch.object(post_startup, "install_startup_checks"),
            patch.object(post_startup, "install_deferred_maintenance"),
            patch.object(post_startup, "install_telegram_proxy_startup"),
            patch.object(post_startup, "install_lists_check"),
            patch.object(post_startup, "install_dns_startup"),
            patch.object(post_startup, "install_dns_page_data_warmup"),
            patch.object(post_startup, "install_profile_warmup"),
            patch.object(post_startup, "install_update_check"),
            patch.object(post_startup, "install_cpu_diagnostic"),
            patch.object(post_startup, "install_qt_event_diagnostic_probe"),
            patch.object(post_startup, "install_global_exception_handler"),
        ):
            install_post_startup_tasks(deps)

        self.assertFalse(hasattr(post_startup, "install_page_warmup"))

    def test_post_startup_tasks_install_profile_warmup(self) -> None:
        from main import post_startup
        from main.post_startup import PostStartupDeps, install_post_startup_tasks

        startup_host = object()
        profile_feature = object()
        log_startup_metric = Mock()
        deps = PostStartupDeps(
            startup_host=startup_host,
            profile_feature=profile_feature,
            dns_feature=object(),
            notify=Mock(),
            notify_many=Mock(),
            set_status=Mock(),
            log_startup_metric=log_startup_metric,
            start_proxy_if_enabled_async=Mock(),
            startup_lists_check=Mock(),
            apply_dns_on_startup_async=Mock(),
            install_tray_post_startup=Mock(),
            updater_feature=Mock(),
        )

        with (
            patch.object(post_startup, "install_startup_checks"),
            patch.object(post_startup, "install_deferred_maintenance"),
            patch.object(post_startup, "install_telegram_proxy_startup"),
            patch.object(post_startup, "install_lists_check"),
            patch.object(post_startup, "install_dns_startup"),
            patch.object(post_startup, "install_dns_page_data_warmup"),
            patch.object(post_startup, "install_profile_warmup") as install_profile_warmup,
            patch.object(post_startup, "install_update_check"),
            patch.object(post_startup, "install_cpu_diagnostic"),
            patch.object(post_startup, "install_qt_event_diagnostic_probe"),
            patch.object(post_startup, "install_global_exception_handler"),
        ):
            install_post_startup_tasks(deps)

        install_profile_warmup.assert_called_once_with(
            startup_host,
            profile_feature=profile_feature,
            log_startup_metric=log_startup_metric,
        )

    def test_post_startup_tasks_install_dns_page_data_warmup(self) -> None:
        from main import post_startup
        from main.post_startup import PostStartupDeps, install_post_startup_tasks

        startup_host = object()
        dns_feature = object()
        log_startup_metric = Mock()
        deps = PostStartupDeps(
            startup_host=startup_host,
            profile_feature=object(),
            dns_feature=dns_feature,
            notify=Mock(),
            notify_many=Mock(),
            set_status=Mock(),
            log_startup_metric=log_startup_metric,
            start_proxy_if_enabled_async=Mock(),
            startup_lists_check=Mock(),
            apply_dns_on_startup_async=Mock(),
            install_tray_post_startup=Mock(),
            updater_feature=Mock(),
        )

        with (
            patch.object(post_startup, "install_startup_checks"),
            patch.object(post_startup, "install_deferred_maintenance"),
            patch.object(post_startup, "install_telegram_proxy_startup"),
            patch.object(post_startup, "install_lists_check"),
            patch.object(post_startup, "install_dns_startup"),
            patch.object(post_startup, "install_dns_page_data_warmup") as install_dns_page_data_warmup,
            patch.object(post_startup, "install_profile_warmup"),
            patch.object(post_startup, "install_update_check"),
            patch.object(post_startup, "install_cpu_diagnostic"),
            patch.object(post_startup, "install_qt_event_diagnostic_probe"),
            patch.object(post_startup, "install_global_exception_handler"),
        ):
            install_post_startup_tasks(deps)

        install_dns_page_data_warmup.assert_called_once_with(
            startup_host,
            dns_feature=dns_feature,
            log_startup_metric=log_startup_metric,
        )

    def test_post_startup_tasks_install_backend_page_data_warmup(self) -> None:
        from main import post_startup
        from main.post_startup import PostStartupDeps, install_post_startup_tasks

        startup_host = object()
        premium_feature = object()
        logs_feature = object()
        log_startup_metric = Mock()
        deps = PostStartupDeps(
            startup_host=startup_host,
            profile_feature=object(),
            dns_feature=object(),
            premium_feature=premium_feature,
            logs_feature=logs_feature,
            notify=Mock(),
            notify_many=Mock(),
            set_status=Mock(),
            log_startup_metric=log_startup_metric,
            start_proxy_if_enabled_async=Mock(),
            startup_lists_check=Mock(),
            apply_dns_on_startup_async=Mock(),
            install_tray_post_startup=Mock(),
            updater_feature=Mock(),
        )

        with (
            patch.object(post_startup, "install_startup_checks"),
            patch.object(post_startup, "install_deferred_maintenance"),
            patch.object(post_startup, "install_telegram_proxy_startup"),
            patch.object(post_startup, "install_lists_check"),
            patch.object(post_startup, "install_dns_startup"),
            patch.object(post_startup, "install_dns_page_data_warmup"),
            patch.object(post_startup, "install_backend_page_data_warmup") as install_backend_page_data_warmup,
            patch.object(post_startup, "install_profile_warmup"),
            patch.object(post_startup, "install_update_check"),
            patch.object(post_startup, "install_cpu_diagnostic"),
            patch.object(post_startup, "install_qt_event_diagnostic_probe"),
            patch.object(post_startup, "install_global_exception_handler"),
        ):
            install_post_startup_tasks(deps)

        install_backend_page_data_warmup.assert_called_once_with(
            startup_host,
            premium_feature=premium_feature,
            logs_feature=logs_feature,
            log_startup_metric=log_startup_metric,
        )

    def test_dns_page_data_warmup_uses_backend_cache_without_page_host(self) -> None:
        from main import post_startup_dns_warmup
        from main.post_startup_dns_warmup import install_dns_page_data_warmup

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
        dns_feature = SimpleNamespace(warm_page_data_cache=Mock(return_value=object()))
        metric = Mock()
        delays: list[int] = []
        thread_names: list[str] = []

        with (
            patch.object(
                post_startup_dns_warmup,
                "schedule_after",
                side_effect=lambda delay_ms, callback: delays.append(delay_ms) or callback(),
            ),
            patch.object(
                post_startup_dns_warmup,
                "start_daemon_thread",
                side_effect=lambda name, target: thread_names.append(name) or target(),
            ),
        ):
            install_dns_page_data_warmup(
                startup_host,
                dns_feature=dns_feature,
                log_startup_metric=metric,
            )
            signal.emit("interactive")

        self.assertEqual(delays, [1200])
        self.assertEqual(thread_names, ["DnsPageDataWarmup"])
        dns_feature.warm_page_data_cache.assert_called_once_with()
        self.assertFalse(hasattr(startup_host, "warm_page"))
        metric.assert_any_call("StartupNetworkDataWarmupQueued", "1200ms after interactive")
        metric.assert_any_call("StartupPostInitNetworkDataWarmupStarted", "backend_cache")

    def test_profile_warmup_orders_current_method_first(self) -> None:
        from main.post_startup_profile_warmup import profile_warmup_methods

        self.assertEqual(
            profile_warmup_methods("zapret1_mode"),
            ("zapret1_mode", "zapret2_mode"),
        )
        self.assertEqual(
            profile_warmup_methods("orchestra"),
            ("zapret2_mode", "zapret1_mode"),
        )

    def test_profile_warmup_runs_methods_in_parallel_after_interactive_ready(self) -> None:
        from main import post_startup_profile_warmup
        from main.post_startup_profile_warmup import install_profile_warmup

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
        profile_feature = SimpleNamespace(list_profiles=Mock(return_value=object()))
        metric = Mock()
        delays: list[int] = []
        thread_names: list[str] = []

        with (
            patch.object(
                post_startup_profile_warmup,
                "schedule_after",
                side_effect=lambda delay_ms, callback: delays.append(delay_ms) or callback(),
            ),
            patch.object(
                post_startup_profile_warmup,
                "start_daemon_thread",
                side_effect=lambda name, target: thread_names.append(name) or target(),
            ),
            patch.object(
                post_startup_profile_warmup,
                "get_strategy_launch_method",
                return_value="zapret1_mode",
            ),
        ):
            install_profile_warmup(
                startup_host,
                profile_feature=profile_feature,
                log_startup_metric=metric,
            )
            signal.emit("interactive")

        self.assertEqual(delays, [1800])
        self.assertEqual(thread_names, ["ProfileWarmup-zapret1_mode", "ProfileWarmup-zapret2_mode"])
        self.assertEqual(
            [recorded_call.args[0] for recorded_call in profile_feature.list_profiles.call_args_list],
            ["zapret1_mode", "zapret2_mode"],
        )
        metric.assert_any_call("StartupProfileWarmupQueued", "1800ms after interactive")
        metric.assert_any_call("StartupProfileWarmupStarted", "zapret1_mode, zapret2_mode")

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

    def test_hide_window_hides_without_changing_window_state(self) -> None:
        from PyQt6.QtCore import Qt
        from ui.window_adapter import hide_window

        calls: list[str] = []

        class Window:
            def windowState(self):
                return Qt.WindowState.WindowMinimized | Qt.WindowState.WindowMaximized

            def setWindowState(self, state) -> None:
                calls.append(f"state:{int(state.value)}")
                self.state = state

            def hide(self) -> None:
                calls.append("hide")

        window = Window()

        hide_window(window)

        self.assertEqual(calls, ["hide"])
        self.assertFalse(hasattr(window, "state"))

    def test_startup_runtime_keeps_coordinator_alive_for_queued_phase_two(self) -> None:
        from main import startup_coordinator
        from main.window_startup_setup import attach_startup_deps_to_window

        signal = SimpleNamespace(emit=Mock())
        window = SimpleNamespace(
            start_in_tray=False,
            set_status=Mock(),
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
    def nativeEvent(self, event_type, message):
        self.calls.append("base_native")
        return (False, 123)

    def showMinimized(self) -> None:
        self.calls.append("base_minimize")

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

    def test_show_event_schedules_titlebar_layout_refresh_after_first_show(self) -> None:
        from main.window_lifecycle import WindowLifecycleMixin

        class Window(WindowLifecycleMixin, _BaseWindowEvents):
            def __init__(self) -> None:
                self.calls: list[str] = []
                self.window_geometry_runtime = SimpleNamespace(
                    apply_saved_maximized_state_if_needed=Mock(),
                    enable_persistence=Mock(),
                )
                self.window_notification_center = None
                self.startup_state = SimpleNamespace(
                    ttff_logged=False,
                    ttff_ms=None,
                )
                self.visual_state = SimpleNamespace(holiday_effects=None)

            def findChildren(self, *_args, **_kwargs):
                return []

        window = Window()
        scheduled_delays: list[int] = []

        def record_single_shot(delay, callback):
            scheduled_delays.append(delay)

        with (
            patch("main.window_lifecycle.refresh_titlebar_layout", create=True) as refresh_titlebar_layout,
            patch("main.window_lifecycle.QTimer.singleShot", side_effect=record_single_shot),
        ):
            window.showEvent(object())

        refresh_titlebar_layout.assert_called_once_with(window)
        self.assertIn(0, scheduled_delays)

    def test_native_minimize_command_hides_to_tray_when_window_setting_is_enabled(self) -> None:
        from main.window_native_commands import SC_MINIMIZE, WM_SYSCOMMAND
        from main.window_lifecycle import WindowLifecycleMixin

        class Window(WindowLifecycleMixin, _BaseWindowEvents):
            def __init__(self) -> None:
                self.calls: list[str] = []
                self.close_to_tray = Mock(side_effect=self._close_to_tray)

            def _close_to_tray(self) -> bool:
                self.calls.append("hide_to_tray")
                return True

        msg = wintypes.MSG()
        msg.message = WM_SYSCOMMAND
        msg.wParam = SC_MINIMIZE
        window = Window()

        with (
            patch("settings.store.get_hide_to_tray_on_minimize_close", return_value=True, create=True),
            patch("main.window_native_commands.sys.platform", "win32"),
        ):
            result = window.nativeEvent(b"windows_generic_MSG", int(addressof(msg)))

        self.assertEqual(result, (True, 0))
        window.close_to_tray.assert_called_once()
        self.assertEqual(window.calls, ["hide_to_tray"])

    def test_native_minimize_command_uses_normal_window_flow_when_setting_is_disabled(self) -> None:
        from main.window_native_commands import SC_MINIMIZE, WM_SYSCOMMAND
        from main.window_lifecycle import WindowLifecycleMixin

        class Window(WindowLifecycleMixin, _BaseWindowEvents):
            def __init__(self) -> None:
                self.calls: list[str] = []
                self.close_to_tray = Mock(return_value=True)

        msg = wintypes.MSG()
        msg.message = WM_SYSCOMMAND
        msg.wParam = SC_MINIMIZE
        window = Window()

        with (
            patch("settings.store.get_hide_to_tray_on_minimize_close", return_value=False, create=True),
            patch("main.window_native_commands.sys.platform", "win32"),
        ):
            result = window.nativeEvent(b"windows_generic_MSG", int(addressof(msg)))

        self.assertEqual(result, (False, 123))
        window.close_to_tray.assert_not_called()
        self.assertEqual(window.calls, ["base_native"])

    def test_show_minimized_hides_to_tray_when_window_setting_is_enabled(self) -> None:
        from main.window_lifecycle import WindowLifecycleMixin

        class Window(WindowLifecycleMixin, _BaseWindowEvents):
            def __init__(self) -> None:
                self.calls: list[str] = []
                self.close_to_tray = Mock(side_effect=self._close_to_tray)

            def _close_to_tray(self) -> bool:
                self.calls.append("hide_to_tray")
                return True

        window = Window()

        with patch("settings.store.get_hide_to_tray_on_minimize_close", return_value=True, create=True):
            window.showMinimized()

        window.close_to_tray.assert_called_once()
        self.assertEqual(window.calls, ["hide_to_tray"])

    def test_show_minimized_uses_normal_window_flow_when_setting_is_disabled(self) -> None:
        from main.window_lifecycle import WindowLifecycleMixin

        class Window(WindowLifecycleMixin, _BaseWindowEvents):
            def __init__(self) -> None:
                self.calls: list[str] = []
                self.close_to_tray = Mock(return_value=True)

        window = Window()

        with patch("settings.store.get_hide_to_tray_on_minimize_close", return_value=False, create=True):
            window.showMinimized()

        window.close_to_tray.assert_not_called()
        self.assertEqual(window.calls, ["base_minimize"])


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

    def test_close_flow_hides_to_tray_without_dialog_when_window_setting_is_enabled(self) -> None:
        from ui.window_close_flow import WindowCloseFlow

        close_dialog_module = types.ModuleType("ui.close_dialog")
        close_dialog_module.ask_close_action = Mock(return_value=None)
        original_close_dialog = sys.modules.get("ui.close_dialog")
        sys.modules["ui.close_dialog"] = close_dialog_module
        try:
            event = SimpleNamespace(ignore=Mock())
            close_state = SimpleNamespace(
                closing_completely=False,
                windows_session_ending=False,
            )
            runtime = SimpleNamespace(snapshot=Mock())
            close_to_tray = Mock(return_value=True)
            flow = WindowCloseFlow(
                parent=object(),
                close_state=close_state,
                runtime_feature=runtime,
                close_to_tray=close_to_tray,
                exit_stop_dpi=Mock(),
                exit_keep_dpi=Mock(),
            )

            with patch("settings.store.get_hide_to_tray_on_minimize_close", return_value=True, create=True):
                self.assertFalse(flow.should_continue_final_close(event))
        finally:
            if original_close_dialog is None:
                sys.modules.pop("ui.close_dialog", None)
            else:
                sys.modules["ui.close_dialog"] = original_close_dialog

        event.ignore.assert_called_once()
        close_to_tray.assert_called_once()
        close_dialog_module.ask_close_action.assert_not_called()
        runtime.snapshot.assert_not_called()

    def test_close_flow_shows_dialog_when_window_setting_is_disabled(self) -> None:
        from ui.window_close_flow import WindowCloseFlow

        close_dialog_module = types.ModuleType("ui.close_dialog")
        close_dialog_module.ask_close_action = Mock(return_value=None)
        original_close_dialog = sys.modules.get("ui.close_dialog")
        sys.modules["ui.close_dialog"] = close_dialog_module
        try:
            event = SimpleNamespace(ignore=Mock())
            close_state = SimpleNamespace(
                closing_completely=False,
                windows_session_ending=False,
            )
            runtime = SimpleNamespace(snapshot=Mock(return_value=SimpleNamespace(launch_running=True)))
            close_to_tray = Mock(return_value=True)
            flow = WindowCloseFlow(
                parent=object(),
                close_state=close_state,
                runtime_feature=runtime,
                close_to_tray=close_to_tray,
                exit_stop_dpi=Mock(),
                exit_keep_dpi=Mock(),
            )

            with patch("settings.store.get_hide_to_tray_on_minimize_close", return_value=False, create=True):
                self.assertFalse(flow.should_continue_final_close(event))
        finally:
            if original_close_dialog is None:
                sys.modules.pop("ui.close_dialog", None)
            else:
                sys.modules["ui.close_dialog"] = original_close_dialog

        event.ignore.assert_called_once()
        runtime.snapshot.assert_called_once()
        close_dialog_module.ask_close_action.assert_called_once_with(
            parent=flow._parent,
            launch_running=True,
        )
        close_to_tray.assert_not_called()

    def test_close_flow_still_shows_dialog_when_runtime_snapshot_fails(self) -> None:
        from ui.window_close_flow import WindowCloseFlow

        close_dialog_module = types.ModuleType("ui.close_dialog")
        close_dialog_module.ask_close_action = Mock(return_value=None)
        original_close_dialog = sys.modules.get("ui.close_dialog")
        sys.modules["ui.close_dialog"] = close_dialog_module
        try:
            event = SimpleNamespace(ignore=Mock())
            close_state = SimpleNamespace(
                closing_completely=False,
                windows_session_ending=False,
            )
            runtime = SimpleNamespace(snapshot=Mock(side_effect=RuntimeError("snapshot failed")))
            flow = WindowCloseFlow(
                parent=object(),
                close_state=close_state,
                runtime_feature=runtime,
                close_to_tray=Mock(),
                exit_stop_dpi=Mock(),
                exit_keep_dpi=Mock(),
            )

            with patch("settings.store.get_hide_to_tray_on_minimize_close", return_value=False, create=True):
                self.assertFalse(flow.should_continue_final_close(event))
        finally:
            if original_close_dialog is None:
                sys.modules.pop("ui.close_dialog", None)
            else:
                sys.modules["ui.close_dialog"] = original_close_dialog

        event.ignore.assert_called_once()
        runtime.snapshot.assert_called_once()
        close_dialog_module.ask_close_action.assert_called_once_with(
            parent=flow._parent,
            launch_running=False,
        )

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
