from __future__ import annotations

import inspect
import unittest


class SidebarStateWorkerBoundaryTests(unittest.TestCase):
    def test_sidebar_expanded_state_save_goes_through_program_settings_feature(self) -> None:
        from app.feature_facades.program_settings import ProgramSettingsFeature
        import program_settings.workers as workers
        import ui.navigation.sidebar_builder as sidebar_builder
        from ui.window_bootstrap_runtime import WindowRuntimeBootstrapDeps, initialize_build_ui_state
        from ui.window_ui_session import WindowUiSession
        from main.window_page_deps_setup import attach_window_ui_root

        feature_source = inspect.getsource(ProgramSettingsFeature)
        worker_source = inspect.getsource(workers.SidebarExpandedStateSaveWorker.run)
        builder_source = inspect.getsource(sidebar_builder._start_sidebar_expanded_save_worker)
        deps_source = inspect.getsource(WindowRuntimeBootstrapDeps)
        session_source = inspect.getsource(WindowUiSession)
        init_source = inspect.getsource(initialize_build_ui_state)
        root_source = inspect.getsource(attach_window_ui_root)

        self.assertIn("create_sidebar_expanded_save_worker", feature_source)
        self.assertIn("save_ui_state_settings=self.save_ui_state_settings", feature_source)
        self.assertIn("SidebarExpandedStateSaveWorker", feature_source)
        self.assertTrue(hasattr(workers, "SidebarExpandedStateSaveWorker"))
        self.assertNotIn("settings.store", worker_source)
        self.assertNotIn("set_ui_state_settings", builder_source)
        self.assertNotIn("ui.navigation.sidebar_state_worker", builder_source)
        self.assertIn("sidebar_expanded_save_worker_factory", deps_source)
        self.assertIn("sidebar_expanded_save_worker_factory", session_source)
        self.assertIn("sidebar_expanded_save_worker_factory", init_source)
        self.assertIn("features.program_settings.create_sidebar_expanded_save_worker", root_source)


if __name__ == "__main__":
    unittest.main()
