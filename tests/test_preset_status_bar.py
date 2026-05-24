from __future__ import annotations

import inspect
import unittest

from settings.mode import ZAPRET1_MODE, ZAPRET2_MODE


class _RuntimeService:
    def __init__(self) -> None:
        self.busy_calls: list[tuple[bool, str]] = []

    def set_busy(self, busy: bool, text: str = "") -> bool:
        self.busy_calls.append((bool(busy), str(text or "")))
        return True


class _StoppedRuntimeOwner:
    def __init__(self) -> None:
        self._presets_switch_method = ""
        self._presets_switch_requested_generation = 0
        self._presets_switch_completed_generation = 0
        self._presets_switch_thread = None
        self._dpi_start_thread = None
        self._dpi_stop_thread = None
        self._runtime_service_obj = _RuntimeService()

    def _runtime_service(self):
        return self._runtime_service_obj

    def is_running(self) -> bool:
        return False


class PresetStatusBarPlanTests(unittest.TestCase):
    def test_spinner_import_is_static_for_packaged_build(self) -> None:
        import presets.ui.common.preset_status_bar as preset_status_bar

        source = inspect.getsource(preset_status_bar)

        self.assertIn("from ui.widgets.win11_spinner import Win11Spinner", source)
        self.assertNotIn("from ui.widgets import Win11Spinner", source)

    def test_loaded_status_uses_success_check_and_clear_text(self) -> None:
        from presets.ui.common.preset_status_bar import build_preset_status_plan

        plan = build_preset_status_plan("loaded", launch_method=ZAPRET2_MODE)

        self.assertEqual(plan.text, "Пресет загружен")
        self.assertEqual(plan.mode, "success")
        self.assertEqual(plan.indicator, "check")

    def test_switch_preset_sets_busy_status_until_runtime_finishes_or_skips(self) -> None:
        from winws_runtime.runtime.restart_flow import switch_presets_async

        owner = _StoppedRuntimeOwner()

        switch_presets_async(owner, ZAPRET2_MODE)

        self.assertEqual(
            owner._runtime_service_obj.busy_calls,
            [(True, "Применяем пресет..."), (False, "")],
        )

    def test_selected_status_names_winws_when_process_is_not_running(self) -> None:
        from presets.ui.common.preset_status_bar import build_preset_status_plan

        winws2_plan = build_preset_status_plan("selected_stopped", launch_method=ZAPRET2_MODE)
        winws1_plan = build_preset_status_plan("selected_stopped", launch_method=ZAPRET1_MODE)

        self.assertEqual(winws2_plan.text, "Пресет выбран, winws2 не запущен")
        self.assertEqual(winws1_plan.text, "Пресет выбран, winws не запущен")
        self.assertEqual(winws2_plan.indicator, "check")
        self.assertEqual(winws1_plan.indicator, "check")

    def test_applying_status_uses_spinner_and_requested_text(self) -> None:
        from presets.ui.common.preset_status_bar import build_preset_status_plan

        plan = build_preset_status_plan("applying", launch_method=ZAPRET2_MODE)

        self.assertEqual(plan.text, "Применяем пресет...")
        self.assertEqual(plan.mode, "busy")
        self.assertEqual(plan.indicator, "spinner")

    def test_runtime_state_overrides_loaded_text_while_preset_switch_is_busy(self) -> None:
        from presets.ui.common.preset_status_bar import build_runtime_preset_status_plan

        plan = build_runtime_preset_status_plan(
            base_status="loaded",
            launch_method=ZAPRET2_MODE,
            runtime_launch_method=ZAPRET2_MODE,
            launch_busy=True,
            launch_busy_text="Применяем пресет...",
            last_status_message="",
        )

        self.assertEqual(plan.text, "Применяем пресет...")
        self.assertEqual(plan.indicator, "spinner")

    def test_runtime_state_keeps_applied_status_after_success_message(self) -> None:
        from presets.ui.common.preset_status_bar import build_runtime_preset_status_plan

        plan = build_runtime_preset_status_plan(
            base_status="loaded",
            launch_method=ZAPRET2_MODE,
            runtime_launch_method=ZAPRET2_MODE,
            launch_busy=False,
            launch_busy_text="",
            last_status_message="Пресет успешно применён",
        )

        self.assertEqual(plan.text, "Пресет применён")
        self.assertEqual(plan.mode, "success")
        self.assertEqual(plan.indicator, "check")

    def test_raw_editor_runtime_toggle_uses_single_button_plan(self) -> None:
        from presets.ui.common.preset_subpage_base import build_runtime_toggle_button_plan

        stopped_plan = build_runtime_toggle_button_plan(
            launch_phase="stopped",
            launch_running=False,
            launch_busy=False,
        )
        running_plan = build_runtime_toggle_button_plan(
            launch_phase="running",
            launch_running=True,
            launch_busy=False,
        )
        stopping_plan = build_runtime_toggle_button_plan(
            launch_phase="stopping",
            launch_running=True,
            launch_busy=True,
        )

        self.assertEqual(stopped_plan.text, "Запустить")
        self.assertFalse(stopped_plan.should_stop)
        self.assertTrue(stopped_plan.enabled)
        self.assertEqual(running_plan.text, "Остановить")
        self.assertTrue(running_plan.should_stop)
        self.assertTrue(running_plan.enabled)
        self.assertEqual(stopping_plan.text, "Остановить")
        self.assertTrue(stopping_plan.should_stop)
        self.assertFalse(stopping_plan.enabled)


if __name__ == "__main__":
    unittest.main()
