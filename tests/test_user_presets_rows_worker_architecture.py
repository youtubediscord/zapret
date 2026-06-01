from __future__ import annotations

import inspect
import unittest


class UserPresetsRowsWorkerArchitectureTests(unittest.TestCase):
    def test_runtime_starts_metadata_workers_through_shared_runtime(self) -> None:
        import presets.user_presets_runtime_service as runtime_service

        service_source = inspect.getsource(runtime_service.UserPresetsRuntimeService)
        start_sources = "\n".join(
            (
                inspect.getsource(runtime_service.UserPresetsRuntimeService._request_single_metadata_refresh),
                inspect.getsource(runtime_service.UserPresetsRuntimeService.load_presets),
                inspect.getsource(runtime_service.UserPresetsRuntimeService._request_rows_plan_refresh),
            )
        )

        self.assertIn("OneShotWorkerRuntime", service_source)
        self.assertIn("start_qthread_worker", start_sources)
        self.assertNotIn("worker.start()", start_sources)

    def test_runtime_service_keeps_worker_identity_only_in_shared_runtime(self) -> None:
        import presets.user_presets_runtime_service as runtime_service

        service_source = inspect.getsource(runtime_service.UserPresetsRuntimeService)

        self.assertNotIn("self._metadata_load_worker", service_source)
        self.assertNotIn("self._single_metadata_worker", service_source)
        self.assertNotIn("self._rows_plan_worker", service_source)
        self.assertNotIn("def _worker_runtime_is_running", service_source)

    def test_runtime_finished_handlers_leave_worker_deletion_to_shared_runtime(self) -> None:
        import presets.user_presets_runtime_service as runtime_service

        finish_sources = "\n".join(
            (
                inspect.getsource(runtime_service.UserPresetsRuntimeService._on_single_metadata_worker_finished),
                inspect.getsource(runtime_service.UserPresetsRuntimeService._on_metadata_worker_finished),
                inspect.getsource(runtime_service.UserPresetsRuntimeService._on_rows_plan_worker_finished),
            )
        )

        self.assertNotIn("worker.deleteLater()", finish_sources)

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
        loaded_source = inspect.getsource(runtime_service.UserPresetsRuntimeService._on_rows_plan_loaded)
        apply_source = inspect.getsource(runtime_service.UserPresetsRuntimeService._run_scheduled_rows_plan_apply)

        self.assertIn("_build_rows_plan", worker_source)
        self.assertIn("_schedule_rows_plan_apply", loaded_source)
        self.assertIn("adapter.apply_rows_plan", apply_source)
        self.assertNotIn("adapter.apply_rows_plan", loaded_source)
        self.assertNotIn("build_preset_rows_plan", loaded_source)
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

    def test_file_watcher_change_handler_does_not_stat_changed_preset_on_gui_thread(self) -> None:
        import presets.user_presets_runtime_service as runtime_service

        source = inspect.getsource(runtime_service.UserPresetsRuntimeService.on_preset_file_changed)

        self.assertNotIn(".exists()", source)

    def test_user_presets_page_has_no_legacy_gui_rows_rebuild_entrypoint(self) -> None:
        from presets.ui.common.user_presets_page import UserPresetsPageBase
        import presets.ui.common.user_presets_page as page_module

        self.assertFalse(hasattr(UserPresetsPageBase, "_rebuild_presets_rows"))
        self.assertFalse(hasattr(page_module, "rebuild_presets_rows"))

    def test_user_presets_runtime_keeps_only_worker_plan_apply_path(self) -> None:
        import presets.ui.common.user_presets_page_runtime as runtime_module

        self.assertTrue(hasattr(runtime_module, "apply_presets_rows_plan"))
        self.assertFalse(hasattr(runtime_module, "rebuild_presets_rows"))

    def test_user_presets_listing_api_has_no_legacy_active_preset_name_reader(self) -> None:
        import presets.ui.common.user_presets_page_runtime as runtime_module

        self.assertFalse(hasattr(runtime_module.UserPresetsPageRuntime, "get_active_preset_name_light"))
        self.assertNotIn(
            "get_active_preset_name_light",
            inspect.getsource(runtime_module.UserPresetsListingApi),
        )

    def test_user_presets_page_has_no_legacy_selected_source_reader(self) -> None:
        from presets.ui.common.user_presets_page import UserPresetsPageBase

        self.assertFalse(hasattr(UserPresetsPageBase, "_get_selected_source_preset_file_name_light"))


if __name__ == "__main__":
    unittest.main()
