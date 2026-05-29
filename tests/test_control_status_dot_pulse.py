from __future__ import annotations

import unittest
from types import SimpleNamespace


class _TextTarget:
    def __init__(self) -> None:
        self.text = ""

    def setText(self, text: str) -> None:  # noqa: N802
        self.text = text


class _VisibleTarget:
    def __init__(self) -> None:
        self.visible = None

    def setVisible(self, visible: bool) -> None:  # noqa: N802
        self.visible = bool(visible)


class _StatusDot:
    def __init__(self) -> None:
        self.color = ""
        self.started = 0
        self.stopped = 0

    def set_color(self, color: str) -> None:
        self.color = color

    def start_pulse(self) -> None:
        self.started += 1

    def stop_pulse(self) -> None:
        self.stopped += 1


class ControlStatusDotPulseTests(unittest.TestCase):
    def _apply_plan(self, *, pulsing: bool) -> _StatusDot:
        from presets.ui.control.control_page_runtime_shared import apply_status_plan

        dot = _StatusDot()
        apply_status_plan(
            SimpleNamespace(
                phase="running",
                title="Zapret работает",
                description="Обход блокировок активен",
                dot_color="#6ccb5f",
                pulsing=pulsing,
                show_start=False,
                show_stop_only=True,
                show_stop_and_exit=True,
            ),
            status_title=_TextTarget(),
            status_desc=_TextTarget(),
            status_dot=dot,
            start_btn=_VisibleTarget(),
            stop_winws_btn=_VisibleTarget(),
            stop_and_exit_btn=_VisibleTarget(),
            update_stop_button_text=lambda: None,
        )
        return dot

    def test_apply_status_plan_starts_pulse_when_plan_requests_it(self) -> None:
        dot = self._apply_plan(pulsing=True)

        self.assertEqual(dot.started, 1)
        self.assertEqual(dot.stopped, 0)

    def test_apply_status_plan_stops_pulse_when_plan_is_static(self) -> None:
        dot = self._apply_plan(pulsing=False)

        self.assertEqual(dot.started, 0)
        self.assertEqual(dot.stopped, 1)

    def test_running_status_pulses_for_both_control_modes(self) -> None:
        from presets.ui.control import control_runtime
        from presets.ui.control.zapret2 import page_runtime as zapret2_page_runtime

        winws1_plan = control_runtime.build_status_plan(state="running", last_error="", language="ru")
        winws2_plan = zapret2_page_runtime.build_status_plan(state="running", last_error="", language="ru")

        self.assertTrue(winws1_plan.pulsing)
        self.assertTrue(winws2_plan.pulsing)


if __name__ == "__main__":
    unittest.main()
