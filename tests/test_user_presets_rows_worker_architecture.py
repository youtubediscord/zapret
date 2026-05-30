from __future__ import annotations

import inspect
import unittest


class UserPresetsRowsWorkerArchitectureTests(unittest.TestCase):
    def test_runtime_refresh_requests_rows_plan_worker_instead_of_building_rows_in_gui(self) -> None:
        from presets.user_presets_runtime_service import UserPresetsRuntimeService

        refresh_source = inspect.getsource(UserPresetsRuntimeService.refresh_presets_view_from_cache)
        loaded_source = inspect.getsource(UserPresetsRuntimeService._on_metadata_loaded)
        request_source = inspect.getsource(UserPresetsRuntimeService._request_rows_plan_refresh)

        self.assertIn("_request_rows_plan_refresh", refresh_source)
        self.assertIn("_request_rows_plan_refresh", loaded_source)
        self.assertNotIn("adapter.rebuild_rows(", refresh_source)
        self.assertNotIn("adapter.rebuild_rows(", loaded_source)
        self.assertNotIn("adapter.rebuild_rows(", request_source)

    def test_rows_plan_worker_builds_plan_before_gui_applies_rows(self) -> None:
        import presets.user_presets_runtime_service as runtime_service

        self.assertTrue(hasattr(runtime_service, "UserPresetsRowsPlanWorker"))
        worker_source = inspect.getsource(runtime_service.UserPresetsRowsPlanWorker.run)
        apply_source = inspect.getsource(runtime_service.UserPresetsRuntimeService._on_rows_plan_loaded)

        self.assertIn("_build_rows_plan", worker_source)
        self.assertIn("adapter.apply_rows_plan", apply_source)
        self.assertNotIn("build_preset_rows_plan", apply_source)

    def test_rows_plan_worker_resolves_active_preset_inside_worker(self) -> None:
        import presets.user_presets_runtime_service as runtime_service

        worker_init_source = inspect.getsource(runtime_service.UserPresetsRowsPlanWorker.__init__)
        worker_run_source = inspect.getsource(runtime_service.UserPresetsRowsPlanWorker.run)
        request_source = inspect.getsource(runtime_service.UserPresetsRuntimeService._request_rows_plan_refresh)

        self.assertIn("selected_source_file_name", worker_init_source)
        self.assertIn("self._selected_source_file_name()", worker_run_source)
        self.assertIn("selected_source_file_name=adapter.selected_source_file_name", request_source)
        self.assertNotIn("active_file_name=adapter.selected_source_file_name()", request_source)

    def test_single_metadata_update_uses_model_active_marker_without_settings_read(self) -> None:
        import presets.user_presets_runtime_service as runtime_service

        source = inspect.getsource(runtime_service.UserPresetsRuntimeService.try_apply_single_preset_metadata_update)

        self.assertIn("active_preset_file_name", source)
        self.assertNotIn("adapter.selected_source_file_name()", source)

    def test_watcher_sync_does_not_stat_every_preset_file_on_gui_thread(self) -> None:
        import presets.user_presets_runtime_service as runtime_service

        source = inspect.getsource(runtime_service.UserPresetsRuntimeService.sync_watched_preset_files)

        self.assertNotIn("Path(path).exists()", source)

    def test_runtime_service_does_not_keep_legacy_active_marker_settings_read_api(self) -> None:
        import presets.user_presets_runtime_service as runtime_service

        self.assertFalse(hasattr(runtime_service.UserPresetsRuntimeService, "apply_active_preset_marker"))


if __name__ == "__main__":
    unittest.main()
