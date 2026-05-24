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


if __name__ == "__main__":
    unittest.main()
