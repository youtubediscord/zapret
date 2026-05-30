from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))


class StartupAutostartTests(unittest.TestCase):
    def test_preset_autostart_stops_with_error_when_startup_preset_is_not_ready(self) -> None:
        from winws_runtime.runtime.autostart import start_dpi_autostart

        runtime_service = SimpleNamespace(
            mark_start_failed=Mock(),
            mark_stopped=Mock(),
        )
        launch_runtime = SimpleNamespace(start_dpi_async=Mock())
        presets_feature = SimpleNamespace(
            get_launch_snapshot=Mock(side_effect=RuntimeError("Пресеты не найдены")),
            refresh_launch_summary_in_store=Mock(),
        )
        runtime_feature = SimpleNamespace(
            objects=SimpleNamespace(
                runtime_service=runtime_service,
                launch_runtime=launch_runtime,
            ),
            dependencies=SimpleNamespace(
                presets_feature=presets_feature,
                profile_feature=object(),
            ),
        )
        startup_state = SimpleNamespace(dpi_autostart_initiated=False)

        with patch("program_settings.public.is_auto_dpi_enabled", return_value=True):
            start_dpi_autostart(
                startup_state,
                runtime_feature=runtime_feature,
                ui_state=object(),
                launch_method="zapret2_mode",
            )

        presets_feature.get_launch_snapshot.assert_called_once_with(
            "zapret2_mode",
            require_filters=False,
        )
        runtime_service.mark_start_failed.assert_called_once()
        launch_runtime.start_dpi_async.assert_not_called()
        presets_feature.refresh_launch_summary_in_store.assert_not_called()

    def test_preset_autostart_resolves_snapshot_without_gui_thread_filter_validation(self) -> None:
        from winws_runtime.runtime.autostart import start_dpi_autostart

        snapshot = SimpleNamespace(to_selected_mode=Mock(return_value={"is_preset_file": True}))
        runtime_service = SimpleNamespace(
            mark_start_failed=Mock(),
            mark_stopped=Mock(),
        )
        launch_runtime = SimpleNamespace(start_dpi_async=Mock())
        presets_feature = SimpleNamespace(
            get_launch_snapshot=Mock(return_value=snapshot),
            refresh_launch_summary_in_store=Mock(),
        )
        runtime_feature = SimpleNamespace(
            objects=SimpleNamespace(
                runtime_service=runtime_service,
                launch_runtime=launch_runtime,
            ),
            dependencies=SimpleNamespace(
                presets_feature=presets_feature,
                profile_feature=object(),
            ),
        )
        startup_state = SimpleNamespace(dpi_autostart_initiated=False)

        with patch("program_settings.public.is_auto_dpi_enabled", return_value=True):
            start_dpi_autostart(
                startup_state,
                runtime_feature=runtime_feature,
                ui_state=object(),
                launch_method="zapret2_mode",
            )

        presets_feature.get_launch_snapshot.assert_called_once_with(
            "zapret2_mode",
            require_filters=False,
        )
        launch_runtime.start_dpi_async.assert_called_once_with(
            selected_mode={"is_preset_file": True},
            launch_method="zapret2_mode",
            _startup_autostart=True,
        )

    def test_preset_autostart_reuses_already_running_expected_process(self) -> None:
        from winws_runtime.runtime.autostart import start_dpi_autostart

        runtime_service = SimpleNamespace(
            bootstrap_probe=Mock(),
            mark_start_failed=Mock(),
            mark_stopped=Mock(),
        )
        launch_runtime = SimpleNamespace(start_dpi_async=Mock())
        launch_runtime_api = SimpleNamespace(is_expected_running=Mock(return_value=True))
        presets_feature = SimpleNamespace(
            get_launch_snapshot=Mock(),
            refresh_launch_summary_in_store=Mock(),
        )
        runtime_feature = SimpleNamespace(
            objects=SimpleNamespace(
                runtime_service=runtime_service,
                launch_runtime=launch_runtime,
                launch_runtime_api=launch_runtime_api,
            ),
            dependencies=SimpleNamespace(
                presets_feature=presets_feature,
                profile_feature=object(),
            ),
        )
        startup_state = SimpleNamespace(dpi_autostart_initiated=False)

        with patch("program_settings.public.is_auto_dpi_enabled", return_value=True):
            start_dpi_autostart(
                startup_state,
                runtime_feature=runtime_feature,
                ui_state=object(),
                launch_method="zapret2_mode",
            )

        launch_runtime_api.is_expected_running.assert_called_once_with(silent=True)
        runtime_service.bootstrap_probe.assert_called_once_with(
            True,
            launch_method="zapret2_mode",
            expected_process="winws2.exe",
        )
        launch_runtime.start_dpi_async.assert_not_called()
        presets_feature.get_launch_snapshot.assert_not_called()
        presets_feature.refresh_launch_summary_in_store.assert_not_called()

    def test_startup_autostart_skips_expensive_preset_prevalidation_in_gui_thread(self) -> None:
        from winws_runtime.flow import start_preparation

        selected_mode = {
            "is_preset_file": True,
            "name": "Пресет",
            "preset_path": __file__,
        }

        with patch.object(
            start_preparation,
            "validate_presets_before_launch",
            side_effect=AssertionError("startup autostart must not prevalidate preset in GUI thread"),
        ):
            request, warnings = start_preparation.prepare_start_request(
                selected_mode,
                "zapret2_mode",
                presets_feature=object(),
                skip_preset_prevalidation=True,
            )

        self.assertEqual(request.selected_mode, selected_mode)
        self.assertEqual(warnings, [])

    def test_start_flow_passes_startup_autostart_flag_to_request_builder(self) -> None:
        from winws_runtime.runtime import start_flow
        from winws_runtime.runtime.start_workers import PreparedDpiStartRequest

        runtime_owner = SimpleNamespace(
            _runtime_feature=SimpleNamespace(
                dependencies=SimpleNamespace(
                    presets_feature=object(),
                ),
            ),
            _pending_launch_warnings=[],
        )
        request = PreparedDpiStartRequest(
            launch_method="zapret2_mode",
            selected_mode={"is_preset_file": True},
            mode_name="Пресет",
            method_name="прямой winws2",
        )

        with patch.object(
            start_flow,
            "prepare_start_request",
            return_value=(request, []),
        ) as prepare:
            result = start_flow.build_start_request(
                runtime_owner,
                selected_mode={"is_preset_file": True},
                launch_method="zapret2_mode",
                startup_autostart=True,
            )

        self.assertIs(result, request)
        self.assertTrue(prepare.call_args.kwargs["skip_preset_prevalidation"])

    def test_start_flow_marks_start_worker_as_startup_autostart(self) -> None:
        from winws_runtime.runtime import start_flow
        from winws_runtime.runtime.start_workers import PreparedDpiStartRequest

        request = PreparedDpiStartRequest(
            launch_method="zapret2_mode",
            selected_mode={"is_preset_file": True},
            mode_name="Пресет",
            method_name="прямой winws2",
        )
        runtime_owner = SimpleNamespace(
            _runtime_feature=SimpleNamespace(),
            _runtime_api=Mock(return_value=object()),
            _runtime_service=Mock(return_value=SimpleNamespace(set_busy=Mock())),
            _begin_runtime_start=Mock(),
            _on_dpi_start_finished=Mock(),
        )

        with (
            patch.object(start_flow, "prepare_start_preflight", return_value=True),
            patch.object(start_flow, "build_start_request", return_value=request),
            patch.object(start_flow, "set_runtime_owner_status"),
            patch.object(start_flow, "runtime_owner_status_callback", return_value=Mock()),
            patch.object(start_flow, "start_worker_thread") as start_worker_thread,
        ):
            start_flow.start_dpi_async(
                runtime_owner,
                selected_mode=request.selected_mode,
                launch_method="zapret2_mode",
                startup_autostart=True,
            )

        worker = start_worker_thread.call_args.kwargs["worker"]
        self.assertTrue(worker._startup_autostart)

    def test_startup_manifest_cache_signature_does_not_read_preset_body(self) -> None:
        import inspect
        from presets.mode_coordinator import PresetModeCoordinator

        source = inspect.getsource(PresetModeCoordinator._selected_manifest_cache_key)

        self.assertIn("path_stat_signature(settings_path)", source)
        self.assertIn("path_stat_signature(preset_path)", source)
        self.assertNotIn("path_cache_signature(settings_path)", source)
        self.assertNotIn("path_cache_signature(preset_path)", source)

    def test_startup_worker_rejects_preset_without_enabled_profiles_before_stop(self) -> None:
        from winws_runtime.runtime.start_workers import PresetLaunchStartWorker

        with tempfile.TemporaryDirectory() as tmp_dir:
            preset_path = Path(tmp_dir) / "only-skipped.txt"
            preset_path.write_text("--new\n--skip\n--filter-tcp=80\n", encoding="utf-8")

            worker = PresetLaunchStartWorker(
                {"is_preset_file": True, "preset_path": str(preset_path), "name": "Пресет"},
                "zapret2_mode",
                runtime_feature=SimpleNamespace(),
                runtime_api=SimpleNamespace(),
            )

            ok = worker._validate_preset_before_stop(
                is_preset_file=True,
                preset_path=str(preset_path),
                skip_stop=False,
            )

        self.assertFalse(ok)
        self.assertIn("нет включённых profile", worker._last_error_message)

    def test_startup_worker_uses_short_stable_window_for_autostart(self) -> None:
        from winws_runtime.runtime.start_workers import PresetLaunchStartWorker

        with tempfile.TemporaryDirectory() as tmp_dir:
            preset_path = Path(tmp_dir) / "ready.txt"
            preset_path.write_text("--new\n--filter-tcp=80\n", encoding="utf-8")

            worker = PresetLaunchStartWorker(
                {"is_preset_file": True, "preset_path": str(preset_path), "name": "Пресет"},
                "zapret2_mode",
                runtime_feature=SimpleNamespace(),
                runtime_api=SimpleNamespace(),
                startup_autostart=True,
            )
            runner = SimpleNamespace(start_from_preset_file=Mock(return_value=True))

            with patch("winws_runtime.runners.runner_factory.get_strategy_runner", return_value=runner):
                self.assertTrue(worker._start_presets_with_runner(str(preset_path), "Пресет"))

        kwargs = runner.start_from_preset_file.call_args.kwargs
        self.assertLess(kwargs["_stable_start_window_seconds"], 1.0)

    def test_winws1_retry_preserves_short_startup_stable_window(self) -> None:
        from winws_runtime.runners.zapret1_runner import Winws1StrategyRunner

        runner = object.__new__(Winws1StrategyRunner)
        runner._last_spawn_exit_code = 34
        runner._last_spawn_stderr = "windivert conflict"
        runner._should_retry_transient_windivert_service_error = Mock(return_value=False)
        runner._is_windivert_system_error = Mock(return_value=False)
        runner._is_windivert_conflict_error = Mock(return_value=True)
        runner._start_from_preset_file_locked = Mock(return_value=True)

        self.assertTrue(
            runner._maybe_retry_after_failed_spawn_locked(
                "preset.txt",
                "Preset",
                retry_count=0,
                max_retries=2,
                stable_start_window_seconds=0.35,
            )
        )

        self.assertEqual(
            runner._start_from_preset_file_locked.call_args.kwargs["stable_start_window_seconds"],
            0.35,
        )


if __name__ == "__main__":
    unittest.main()
