from __future__ import annotations

import inspect
import unittest
from unittest.mock import Mock, patch


class StartupBootstrapMetricsTests(unittest.TestCase):
    def test_qt_runtime_logs_bootstrap_substeps(self) -> None:
        from main import qt_runtime

        source = "\n".join(
            (
                inspect.getsource(qt_runtime.ensure_qt_runtime),
                inspect.getsource(qt_runtime.application_bootstrap),
            )
        )

        self.assertIn("StartupQtRuntimeQApplication", source)
        self.assertIn("_connect_qfluent_accent_signal_lazy", source)
        self.assertIn("StartupQtComboPopupGuard", source)
        self.assertIn("StartupQtAnimationCompat", source)
        self.assertIn("StartupQtAccentSignal", source)
        self.assertIn("StartupQtRuntimeReadyHooks", source)
        self.assertIn("StartupQtCrashHandler", source)
        self.assertIn("StartupQtThemeMode", source)
        self.assertIn("StartupQtApplicationIcon", source)
        self.assertIn("StartupQtAccent", source)

    def test_qt_runtime_defers_theme_module_import_for_accent_signal(self) -> None:
        from main import qt_runtime

        source = inspect.getsource(qt_runtime.ensure_qt_runtime)
        lazy_source = inspect.getsource(qt_runtime._connect_qfluent_accent_signal_lazy)

        self.assertNotIn("from ui.theme import connect_qfluent_accent_signal", source)
        self.assertIn("from ui.theme import invalidate_theme_tokens_cache", lazy_source)

    def test_qt_scroll_style_is_not_installed_in_early_application_bootstrap(self) -> None:
        from main import qt_runtime

        source = inspect.getsource(qt_runtime.application_bootstrap)

        self.assertNotIn("_install_non_transient_scrollbars_style", source)

    def test_application_icon_has_one_early_owner(self) -> None:
        from app.feature_facades.tray import TrayFeature
        from main import qt_runtime
        from main.tray_window_port import TrayWindowPort
        import tray_commands
        from ui.fluent_app_window import ZapretFluentWindow

        bootstrap_source = inspect.getsource(qt_runtime.application_bootstrap)
        owner_source = inspect.getsource(qt_runtime._apply_application_icon)
        window_source = inspect.getsource(ZapretFluentWindow)
        tray_source = inspect.getsource(TrayFeature._init_manager)
        tray_port_source = inspect.getsource(TrayWindowPort)
        tray_resolver_source = inspect.getsource(tray_commands.resolve_tray_icon_path)

        self.assertIn("_apply_application_icon(app)", bootstrap_source)
        self.assertIn("app.setWindowIcon(icon)", owner_source)
        self.assertIn("_sync_titlebar_icon_from_application", window_source)
        self.assertNotIn("setWindowIcon", window_source)
        self.assertNotIn("setWindowIcon", tray_source)
        self.assertNotIn("setWindowIcon", tray_port_source)
        self.assertNotIn("set_application_icon_from_path", tray_source)
        self.assertNotIn("set_application_icon_from_path", tray_port_source)
        self.assertIn("resolve_existing_app_icon_path", tray_resolver_source)
        self.assertNotIn("ICON_DEV_PATH", tray_resolver_source)
        self.assertNotIn("ICON_PATH", tray_resolver_source)

    def test_application_icon_owner_sets_valid_icon_once(self) -> None:
        from main import qt_runtime

        app = Mock()
        icon = Mock()
        icon.isNull.return_value = False
        with (
            patch(
                "app.app_icon_resources.resolve_existing_app_icon_path",
                return_value=r"C:\Zapret\Dev\ico\ZapretDevLogo4.ico",
            ),
            patch("PyQt6.QtGui.QIcon", return_value=icon) as icon_factory,
        ):
            result = qt_runtime._apply_application_icon(app)

        icon_factory.assert_called_once_with(r"C:\Zapret\Dev\ico\ZapretDevLogo4.ico")
        app.setWindowIcon.assert_called_once_with(icon)
        self.assertEqual(result, r"C:\Zapret\Dev\ico\ZapretDevLogo4.ico")

    def test_qt_runtime_does_not_read_windows_accent_during_startup(self) -> None:
        from main import qt_runtime

        source = inspect.getsource(qt_runtime.application_bootstrap)

        self.assertNotIn("load_windows_system_accent", source)
        self.assertNotIn("save_accent_color", source)
        self.assertIn("load_accent_color", source)

    def test_entry_logs_pre_window_bootstrap_substeps(self) -> None:
        from main import entry

        source = "\n".join(
            (
                inspect.getsource(entry.main),
                inspect.getsource(entry._finish_event_loop_bootstrap),
            )
        )

        self.assertIn("StartupSettingsMaterialize", source)
        self.assertIn("StartupShellBootstrap", source)
        self.assertIn("StartupApplicationBootstrap", source)
        self.assertIn("StartupApplicationControllerImport", source)
        self.assertIn("StartupWindowClassImport", source)
        self.assertIn("StartupApplicationControllerInit", source)
        self.assertIn("StartupLateBootstrapShutdownHook", source)
        self.assertIn("StartupLateBootstrapAppearance", source)
        self.assertIn("StartupLateBootstrapShowBridge", source)
        self.assertIn("StartupLateBootstrapDeferredHooks", source)
        self.assertIn("StartupLateBootstrapTotal", source)

    def test_window_constructor_logs_bootstrap_substeps(self) -> None:
        from main.window_startup import WindowStartupMixin
        from ui.fluent_app_window import ZapretFluentWindow

        constructor_source = inspect.getsource(WindowStartupMixin.__init__)
        deferred_launch_method_logger = getattr(
            WindowStartupMixin,
            "_log_launch_method_after_ui_ready",
            None,
        )
        self.assertIsNotNone(deferred_launch_method_logger)
        source = "\n".join(
            (
                constructor_source,
                inspect.getsource(deferred_launch_method_logger),
                inspect.getsource(WindowStartupMixin._continue_startup_after_ui_ready),
                inspect.getsource(ZapretFluentWindow.__init__),
                inspect.getsource(ZapretFluentWindow._sync_titlebar_icon_from_application),
            )
        )

        self.assertIn("StartupWindowCtorSuper", source)
        self.assertIn("StartupWindowLaunchMethod", source)
        self.assertNotIn("get_strategy_launch_method", constructor_source)
        self.assertIn("StartupFluentWindowSuper", source)
        self.assertIn("_sync_titlebar_icon_from_application", source)
        self.assertNotIn("StartupFluentWindowIconDeferred", source)
        self.assertNotIn("self._app_icon_deferred_started", source)

    def test_application_controller_logs_runtime_and_attach_substeps(self) -> None:
        from main.application_controller import ApplicationController

        source = inspect.getsource(ApplicationController.create_window)

        self.assertIn("StartupAppRuntimeBuild", source)
        self.assertIn("StartupWindowAttachRuntime", source)
        self.assertIn("StartupWindowRegisterAppWindow", source)
        self.assertIn("StartupWindowTrayPort", source)
        self.assertIn("StartupWindowFeatureDeps", source)
        self.assertIn("StartupWindowStateActions", source)
        self.assertIn("StartupWindowFeatureDepsFactory", source)
        self.assertIn("StartupWindowInitialUiState", source)

    def test_app_runtime_logs_build_substeps(self) -> None:
        from app import runtime

        source = inspect.getsource(runtime.build_app_runtime)

        self.assertIn("StartupAppRuntimePaths", source)
        self.assertIn("StartupAppRuntimeStateAccess", source)
        self.assertIn("StartupAppRuntimeFeatureDeps", source)
        self.assertIn("StartupAppRuntimeFeatures", source)

    def test_feature_assembly_logs_feature_build_substeps(self) -> None:
        from app import feature_assembly

        source = "\n".join(
            (
                inspect.getsource(feature_assembly.build_preset_profile_features),
                inspect.getsource(feature_assembly.build_app_features),
            )
        )

        self.assertIn("StartupFeatureAssemblyImports", source)
        self.assertIn("StartupFeatureAssemblyOrchestra", source)
        self.assertIn("StartupFeatureAssemblyPresetProfileImport", source)
        self.assertIn("StartupFeatureAssemblyPresets", source)
        self.assertIn("StartupFeatureAssemblyProfile", source)
        self.assertIn("StartupFeatureAssemblyRuntime", source)
        self.assertIn("StartupFeatureAssemblyTelegramProxy", source)
        self.assertIn("StartupFeatureAssemblyTray", source)
        self.assertIn("StartupFeatureAssemblySecondary", source)


if __name__ == "__main__":
    unittest.main()
