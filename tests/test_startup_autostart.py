from __future__ import annotations

import sys
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
            require_filters=True,
        )
        runtime_service.mark_start_failed.assert_called_once()
        launch_runtime.start_dpi_async.assert_not_called()
        presets_feature.refresh_launch_summary_in_store.assert_not_called()


if __name__ == "__main__":
    unittest.main()
