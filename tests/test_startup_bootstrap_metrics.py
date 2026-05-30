from __future__ import annotations

import inspect
import unittest


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

    def test_entry_logs_pre_window_bootstrap_substeps(self) -> None:
        from main import entry

        source = inspect.getsource(entry.main)

        self.assertIn("StartupSettingsMaterialize", source)
        self.assertIn("StartupShellBootstrap", source)
        self.assertIn("StartupApplicationBootstrap", source)
        self.assertIn("StartupApplicationControllerImport", source)
        self.assertIn("StartupWindowClassImport", source)
        self.assertIn("StartupApplicationControllerInit", source)

    def test_window_constructor_logs_bootstrap_substeps(self) -> None:
        from main.window_startup import WindowStartupMixin
        from ui.fluent_app_window import ZapretFluentWindow

        source = "\n".join(
            (
                inspect.getsource(WindowStartupMixin.__init__),
                inspect.getsource(ZapretFluentWindow.__init__),
                inspect.getsource(ZapretFluentWindow._schedule_app_icon_after_interactive),
                inspect.getsource(ZapretFluentWindow._apply_app_icon_deferred),
            )
        )

        self.assertIn("StartupWindowCtorSuper", source)
        self.assertIn("StartupWindowLaunchMethod", source)
        self.assertIn("StartupFluentWindowSuper", source)
        self.assertIn("StartupFluentWindowIconDeferred", source)
        self.assertIn("startup_interactive_ready.connect", source)
        self.assertIn("self._app_icon_deferred_started", source)

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
