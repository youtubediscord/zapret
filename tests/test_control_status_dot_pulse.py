from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock


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


class _ToggleTarget:
    def __init__(self, checked: bool) -> None:
        self.checked = bool(checked)
        self.calls: list[tuple[bool, bool]] = []

    def isChecked(self) -> bool:  # noqa: N802
        return self.checked

    def setChecked(self, checked: bool, block_signals: bool = False) -> None:  # noqa: N802
        self.calls.append((bool(checked), bool(block_signals)))
        self.checked = bool(checked)


class _WidgetStateTarget:
    def __init__(self, *, text: str = "", visible: bool = True, enabled: bool = True) -> None:
        self._text = text
        self._hidden = not bool(visible)
        self._enabled = bool(enabled)
        self.text_calls: list[str] = []
        self.visible_calls: list[bool] = []
        self.enabled_calls: list[bool] = []

    def text(self) -> str:
        return self._text

    def setText(self, text: str) -> None:  # noqa: N802
        self.text_calls.append(str(text))
        self._text = str(text)

    def isHidden(self) -> bool:  # noqa: N802
        return self._hidden

    def setVisible(self, visible: bool) -> None:  # noqa: N802
        self.visible_calls.append(bool(visible))
        self._hidden = not bool(visible)

    def isEnabled(self) -> bool:  # noqa: N802
        return self._enabled

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802
        self.enabled_calls.append(bool(enabled))
        self._enabled = bool(enabled)


class _ProgressTarget:
    def __init__(self) -> None:
        self.started = 0
        self.stopped = 0

    def start(self) -> None:
        self.started += 1

    def stop(self) -> None:
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

    def test_apply_status_plan_skips_duplicate_render(self) -> None:
        from presets.ui.control.control_page_runtime_shared import apply_status_plan

        plan = SimpleNamespace(
            phase="running",
            title="Zapret работает",
            description="Обход блокировок активен",
            dot_color="#6ccb5f",
            pulsing=True,
            show_start=False,
            show_stop_only=True,
            show_stop_and_exit=True,
        )
        status_title = _TextTarget()
        status_desc = _TextTarget()
        status_dot = _StatusDot()
        start_btn = _VisibleTarget()
        stop_winws_btn = _VisibleTarget()
        stop_and_exit_btn = _VisibleTarget()
        update_stop_button_text = Mock()

        apply_status_plan(
            plan,
            status_title=status_title,
            status_desc=status_desc,
            status_dot=status_dot,
            start_btn=start_btn,
            stop_winws_btn=stop_winws_btn,
            stop_and_exit_btn=stop_and_exit_btn,
            update_stop_button_text=update_stop_button_text,
        )
        status_title.setText = Mock(side_effect=AssertionError("same status must not rewrite title"))
        status_desc.setText = Mock(side_effect=AssertionError("same status must not rewrite description"))
        status_dot.set_color = Mock(side_effect=AssertionError("same status must not rewrite dot color"))
        status_dot.start_pulse = Mock(side_effect=AssertionError("same status must not restart pulse"))
        status_dot.stop_pulse = Mock(side_effect=AssertionError("same status must not stop pulse"))
        start_btn.setVisible = Mock(side_effect=AssertionError("same status must not rewrite start visibility"))
        stop_winws_btn.setVisible = Mock(side_effect=AssertionError("same status must not rewrite stop visibility"))
        stop_and_exit_btn.setVisible = Mock(side_effect=AssertionError("same status must not rewrite exit visibility"))
        update_stop_button_text.side_effect = AssertionError("same status must not rewrite stop button text")

        self.assertTrue(apply_status_plan(
            plan,
            status_title=status_title,
            status_desc=status_desc,
            status_dot=status_dot,
            start_btn=start_btn,
            stop_winws_btn=stop_winws_btn,
            stop_and_exit_btn=stop_and_exit_btn,
            update_stop_button_text=update_stop_button_text,
        ))

        status_title.setText.assert_not_called()
        status_desc.setText.assert_not_called()
        status_dot.set_color.assert_not_called()
        status_dot.start_pulse.assert_not_called()
        status_dot.stop_pulse.assert_not_called()
        start_btn.setVisible.assert_not_called()
        stop_winws_btn.setVisible.assert_not_called()
        stop_and_exit_btn.setVisible.assert_not_called()

    def test_apply_status_plan_skips_unchanged_text_and_visibility_when_dot_changes(self) -> None:
        from presets.ui.control.control_page_runtime_shared import apply_status_plan

        first_plan = SimpleNamespace(
            phase="running",
            title="Zapret работает",
            description="Обход блокировок активен",
            dot_color="#6ccb5f",
            pulsing=True,
            show_start=False,
            show_stop_only=True,
            show_stop_and_exit=True,
        )
        second_plan = SimpleNamespace(
            phase="running",
            title="Zapret работает",
            description="Обход блокировок активен",
            dot_color="#7aa7ff",
            pulsing=True,
            show_start=False,
            show_stop_only=True,
            show_stop_and_exit=True,
        )
        status_title = _WidgetStateTarget(text="Zapret работает")
        status_desc = _WidgetStateTarget(text="Обход блокировок активен")
        status_dot = _StatusDot()
        start_btn = _WidgetStateTarget(visible=False)
        stop_winws_btn = _WidgetStateTarget(visible=True)
        stop_and_exit_btn = _WidgetStateTarget(visible=True)

        apply_status_plan(
            first_plan,
            status_title=status_title,
            status_desc=status_desc,
            status_dot=status_dot,
            start_btn=start_btn,
            stop_winws_btn=stop_winws_btn,
            stop_and_exit_btn=stop_and_exit_btn,
            update_stop_button_text=lambda: None,
        )
        status_title.text_calls.clear()
        status_desc.text_calls.clear()
        start_btn.visible_calls.clear()
        stop_winws_btn.visible_calls.clear()
        stop_and_exit_btn.visible_calls.clear()

        apply_status_plan(
            second_plan,
            status_title=status_title,
            status_desc=status_desc,
            status_dot=status_dot,
            start_btn=start_btn,
            stop_winws_btn=stop_winws_btn,
            stop_and_exit_btn=stop_and_exit_btn,
            update_stop_button_text=lambda: None,
        )

        self.assertEqual(status_dot.color, "#7aa7ff")
        self.assertEqual(status_title.text_calls, [])
        self.assertEqual(status_desc.text_calls, [])
        self.assertEqual(start_btn.visible_calls, [])
        self.assertEqual(stop_winws_btn.visible_calls, [])
        self.assertEqual(stop_and_exit_btn.visible_calls, [])

    def test_last_status_message_skips_duplicate_render(self) -> None:
        from presets.ui.control.control_page_runtime_shared import apply_last_status_message

        message_label = _TextTarget()
        message_dot = _StatusDot()

        apply_last_status_message(
            "Пресет успешно применён",
            message_label=message_label,
            message_dot=message_dot,
            empty_text="Нет сообщений",
        )
        message_label.setText = Mock(side_effect=AssertionError("same message must not rewrite label"))
        message_dot.set_color = Mock(side_effect=AssertionError("same message must not rewrite dot color"))
        message_dot.stop_pulse = Mock(side_effect=AssertionError("same message must not stop pulse again"))

        apply_last_status_message(
            "Пресет успешно применён",
            message_label=message_label,
            message_dot=message_dot,
            empty_text="Нет сообщений",
        )

        message_label.setText.assert_not_called()
        message_dot.set_color.assert_not_called()
        message_dot.stop_pulse.assert_not_called()

    def test_set_toggle_checked_skips_duplicate_state(self) -> None:
        from presets.ui.control.control_page_runtime_shared import set_toggle_checked

        toggle = _ToggleTarget(True)

        set_toggle_checked(toggle, True)

        self.assertEqual(toggle.calls, [])

    def test_set_toggle_checked_applies_changed_state_with_blocked_signals(self) -> None:
        from presets.ui.control.control_page_runtime_shared import set_toggle_checked

        toggle = _ToggleTarget(False)

        set_toggle_checked(toggle, True)

        self.assertEqual(toggle.calls, [(True, True)])
        self.assertTrue(toggle.checked)

    def test_widget_text_visibility_and_enabled_updates_skip_duplicate_state(self) -> None:
        from presets.ui.control.control_page_runtime_shared import (
            set_enabled_if_changed,
            set_text_if_changed,
            set_visible_if_changed,
        )

        widget = _WidgetStateTarget(text="Запуск", visible=True, enabled=False)

        self.assertFalse(set_text_if_changed(widget, "Запуск"))
        self.assertFalse(set_visible_if_changed(widget, True))
        self.assertFalse(set_enabled_if_changed(widget, False))

        self.assertEqual(widget.text_calls, [])
        self.assertEqual(widget.visible_calls, [])
        self.assertEqual(widget.enabled_calls, [])

    def test_widget_text_visibility_and_enabled_updates_apply_changed_state(self) -> None:
        from presets.ui.control.control_page_runtime_shared import (
            set_enabled_if_changed,
            set_text_if_changed,
            set_visible_if_changed,
        )

        widget = _WidgetStateTarget(text="Запуск", visible=True, enabled=False)

        self.assertTrue(set_text_if_changed(widget, "Остановка"))
        self.assertTrue(set_visible_if_changed(widget, False))
        self.assertTrue(set_enabled_if_changed(widget, True))

        self.assertEqual(widget.text_calls, ["Остановка"])
        self.assertEqual(widget.visible_calls, [False])
        self.assertEqual(widget.enabled_calls, [True])

    def test_progress_active_update_skips_duplicate_start_and_stop(self) -> None:
        from presets.ui.control.control_page_runtime_shared import set_progress_active_if_changed

        progress = _ProgressTarget()

        self.assertTrue(set_progress_active_if_changed(progress, True))
        self.assertFalse(set_progress_active_if_changed(progress, True))
        self.assertTrue(set_progress_active_if_changed(progress, False))
        self.assertFalse(set_progress_active_if_changed(progress, False))

        self.assertEqual(progress.started, 1)
        self.assertEqual(progress.stopped, 1)

    def test_running_status_pulses_for_both_control_modes(self) -> None:
        from presets.ui.control import control_runtime
        from presets.ui.control.zapret2 import page_runtime as zapret2_page_runtime

        winws1_plan = control_runtime.build_status_plan(state="running", last_error="", language="ru")
        winws2_plan = zapret2_page_runtime.build_status_plan(state="running", last_error="", language="ru")

        self.assertTrue(winws1_plan.pulsing)
        self.assertTrue(winws2_plan.pulsing)


if __name__ == "__main__":
    unittest.main()
