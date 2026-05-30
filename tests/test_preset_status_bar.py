from __future__ import annotations

import inspect
import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

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


class _RunningRuntimeOwner(_StoppedRuntimeOwner):
    def __init__(self) -> None:
        super().__init__()
        self.pending_switch_calls = 0

    def is_running(self) -> bool:
        return True

    def _process_pending_presets_switch(self) -> None:
        self.pending_switch_calls += 1


class _RuntimeToggleButton:
    def __init__(self) -> None:
        self.text_calls: list[str] = []
        self.icon_calls: list[object] = []
        self.enabled_calls: list[bool] = []

    def setText(self, text: str) -> None:  # noqa: N802
        self.text_calls.append(str(text))

    def setIcon(self, icon) -> None:  # noqa: N802
        self.icon_calls.append(icon)

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802
        self.enabled_calls.append(bool(enabled))


class _TextWidget:
    def __init__(self, text: str = "") -> None:
        self._text = str(text)
        self.text_calls: list[str] = []

    def text(self) -> str:
        return self._text

    def setText(self, text: str) -> None:  # noqa: N802
        value = str(text)
        self.text_calls.append(value)
        self._text = value


class _VisibleWidget:
    def __init__(self, visible: bool = True) -> None:
        self._visible = bool(visible)
        self.visible_calls: list[bool] = []

    def isVisible(self) -> bool:  # noqa: N802
        return self._visible

    def setVisible(self, visible: bool) -> None:  # noqa: N802
        value = bool(visible)
        self.visible_calls.append(value)
        self._visible = value


class _SpinnerWidget:
    def __init__(self) -> None:
        self.started = 0
        self.stopped = 0
        self.hidden = 0

    def start(self) -> None:
        self.started += 1

    def stop(self) -> None:
        self.stopped += 1

    def hide(self) -> None:
        self.hidden += 1


class _BreadcrumbWidget:
    def __init__(self) -> None:
        self.block_calls: list[bool] = []
        self.clear_calls = 0
        self.items: list[tuple[str, str]] = []

    def blockSignals(self, blocked: bool) -> None:  # noqa: N802
        self.block_calls.append(bool(blocked))

    def clear(self) -> None:
        self.clear_calls += 1
        self.items.clear()

    def addItem(self, key: str, text: str) -> None:  # noqa: N802
        self.items.append((str(key), str(text)))


class PresetStatusBarPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def test_spinner_import_is_static_for_packaged_build(self) -> None:
        import presets.ui.common.preset_status_bar as preset_status_bar

        source = inspect.getsource(preset_status_bar)

        self.assertIn("from ui.widgets.win11_spinner import Win11Spinner", source)
        self.assertNotIn("from ui.widgets import Win11Spinner", source)

    def test_preset_header_text_update_skips_duplicate_text(self) -> None:
        from presets.ui.common.preset_subpage_base import set_text_if_changed

        widget = _TextWidget("Активный пресет")

        self.assertFalse(set_text_if_changed(widget, "Активный пресет"))
        self.assertEqual(widget.text_calls, [])

        self.assertTrue(set_text_if_changed(widget, "Пользовательский пресет"))
        self.assertEqual(widget.text_calls, ["Пользовательский пресет"])

    def test_preset_header_visibility_update_skips_duplicate_state(self) -> None:
        from presets.ui.common.preset_subpage_base import set_visible_if_changed

        widget = _VisibleWidget(False)

        self.assertFalse(set_visible_if_changed(widget, False))
        self.assertEqual(widget.visible_calls, [])

        self.assertTrue(set_visible_if_changed(widget, True))
        self.assertEqual(widget.visible_calls, [True])

    def test_preset_breadcrumb_rebuild_skips_duplicate_items(self) -> None:
        from presets.ui.common.preset_subpage_base import PresetRawEditorPage

        breadcrumb = _BreadcrumbWidget()
        page = SimpleNamespace(
            _breadcrumb=breadcrumb,
            _breadcrumb_root_text=lambda: "Управление",
            _breadcrumb_parent_text=lambda: "Мои пресеты",
            _breadcrumb_current_text=lambda: "Default",
        )

        PresetRawEditorPage._rebuild_breadcrumb(page)
        PresetRawEditorPage._rebuild_breadcrumb(page)

        self.assertEqual(breadcrumb.clear_calls, 1)
        self.assertEqual(
            breadcrumb.items,
            [
                ("root", "Управление"),
                ("list", "Мои пресеты"),
                ("raw_preset", "Default"),
            ],
        )

    def test_loaded_status_uses_success_check_and_clear_text(self) -> None:
        from presets.ui.common.preset_status_bar import build_preset_status_plan

        plan = build_preset_status_plan("loaded", launch_method=ZAPRET2_MODE)

        self.assertEqual(plan.text, "Пресет загружен")
        self.assertEqual(plan.mode, "success")
        self.assertEqual(plan.indicator, "check")

    def test_status_bar_theme_refresh_skips_duplicate_text(self) -> None:
        from unittest.mock import Mock, patch

        from presets.ui.common.preset_status_bar import PresetStatusBar, PresetStatusPlan

        plan = PresetStatusPlan("Пресет применён", "success", "check")
        bar = PresetStatusBar.__new__(PresetStatusBar)
        bar._last_plan = plan
        bar._last_theme_key = ("#5caee8", False)
        bar._last_indicator = "check"
        bar.spinner = _SpinnerWidget()
        bar.check_label = _VisibleWidget(True)
        bar.text_label = _TextWidget("Пресет применён")
        bar._apply_mode_style = Mock()

        with patch("presets.ui.common.preset_status_bar._status_theme_key", return_value=("#8cc63f", False)):
            PresetStatusBar.set_plan(bar, plan)

        self.assertEqual(bar.text_label.text_calls, [])
        bar._apply_mode_style.assert_called_once_with("success")

    def test_switch_preset_sets_busy_status_until_runtime_finishes_or_skips(self) -> None:
        from winws_runtime.runtime.restart_flow import switch_presets_async

        owner = _StoppedRuntimeOwner()

        switch_presets_async(owner, ZAPRET2_MODE)

        self.assertEqual(
            owner._runtime_service_obj.busy_calls,
            [(True, "Применяем пресет..."), (False, "")],
        )

    def test_debounced_preset_switch_coalesces_multiple_apply_requests(self) -> None:
        from unittest.mock import patch
        from winws_runtime.runtime.restart_flow import switch_presets_async

        class _Signal:
            def __init__(self) -> None:
                self.callback = None

            def connect(self, callback) -> None:
                self.callback = callback

        class _FakeTimer:
            instances = []

            def __init__(self) -> None:
                self.timeout = _Signal()
                self.start_count = 0
                self.delay_ms = None
                self.active = False
                _FakeTimer.instances.append(self)

            def setSingleShot(self, _single_shot: bool) -> None:
                pass

            def start(self, delay_ms: int) -> None:
                self.start_count += 1
                self.delay_ms = delay_ms
                self.active = True

            def stop(self) -> None:
                self.active = False

            def isActive(self) -> bool:
                return self.active

            def fire(self) -> None:
                self.active = False
                self.timeout.callback()

        owner = _StoppedRuntimeOwner()

        with patch("winws_runtime.runtime.restart_flow.QTimer", _FakeTimer):
            switch_presets_async(owner, ZAPRET2_MODE, delay_ms=900)
            switch_presets_async(owner, ZAPRET2_MODE, delay_ms=900)

            self.assertEqual(owner._presets_switch_requested_generation, 0)
            self.assertEqual(len(_FakeTimer.instances), 1)
            self.assertEqual(_FakeTimer.instances[0].start_count, 2)
            self.assertEqual(_FakeTimer.instances[0].delay_ms, 900)

            _FakeTimer.instances[0].fire()

        self.assertEqual(owner._presets_switch_requested_generation, 1)
        self.assertEqual(
            owner._runtime_service_obj.busy_calls,
            [(True, "Применяем пресет..."), (False, "")],
        )

    def test_stale_preset_switch_finish_does_not_clear_busy_or_status(self) -> None:
        from unittest.mock import patch
        from winws_runtime.runtime.restart_flow import handle_presets_switch_finished

        owner = _RunningRuntimeOwner()
        owner._presets_switch_requested_generation = 7
        owner._presets_switch_completed_generation = 5

        with (
            patch("winws_runtime.runtime.restart_flow.QTimer.singleShot") as single_shot,
            patch("winws_runtime.runtime.restart_flow.set_runtime_owner_status") as set_status,
            patch("winws_runtime.runtime.restart_flow.maybe_restart_discord_after_runtime_apply") as maybe_restart,
        ):
            single_shot.side_effect = lambda _delay, callback: callback()

            handle_presets_switch_finished(owner, True, "", 6, ZAPRET2_MODE, False)

        self.assertEqual(owner._runtime_service_obj.busy_calls, [])
        self.assertEqual(owner._presets_switch_completed_generation, 6)
        self.assertEqual(owner.pending_switch_calls, 1)
        single_shot.assert_called_once()
        set_status.assert_not_called()
        maybe_restart.assert_not_called()

    def test_current_preset_switch_finish_clears_busy_and_sets_status(self) -> None:
        from unittest.mock import patch
        from winws_runtime.runtime.restart_flow import handle_presets_switch_finished

        owner = _RunningRuntimeOwner()
        owner._presets_switch_requested_generation = 7
        owner._presets_switch_completed_generation = 6

        with (
            patch("winws_runtime.runtime.restart_flow.QTimer.singleShot") as single_shot,
            patch("winws_runtime.runtime.restart_flow.set_runtime_owner_status") as set_status,
            patch("winws_runtime.runtime.restart_flow.maybe_restart_discord_after_runtime_apply") as maybe_restart,
        ):
            handle_presets_switch_finished(owner, True, "", 7, ZAPRET2_MODE, False)

        self.assertEqual(owner._runtime_service_obj.busy_calls, [(False, "")])
        self.assertEqual(owner._presets_switch_completed_generation, 7)
        single_shot.assert_not_called()
        set_status.assert_called_once_with(owner, "✅ Пресет успешно применён")
        maybe_restart.assert_called_once_with(owner, skip_first_start=False)

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

    def test_title_status_icon_is_icon_only_and_larger_than_text_bar_icon(self) -> None:
        from presets.ui.common.preset_status_bar import PresetStatusIcon, build_preset_status_plan

        icon = PresetStatusIcon(size=24)
        icon.set_plan(build_preset_status_plan("applied", launch_method=ZAPRET2_MODE))

        self.assertFalse(hasattr(icon, "text_label"))
        self.assertEqual(icon.minimumWidth(), 28)
        self.assertEqual(icon.minimumHeight(), 28)
        self.assertEqual(icon.check_label.size().width(), 24)
        self.assertTrue(icon.check_label.isVisible())
        self.assertIn("background-color: #8cc63f", icon.check_label.styleSheet())
        self.assertIn("border-radius: 12px", icon.check_label.styleSheet())
        self.assertIn("color: #ffffff", icon.check_label.styleSheet())
        self.assertNotIn("font-weight: 700", icon.check_label.styleSheet())

    def test_status_bar_skips_duplicate_plan_render(self) -> None:
        from presets.ui.common.preset_status_bar import PresetStatusBar, build_preset_status_plan

        status_bar = PresetStatusBar()
        plan = build_preset_status_plan("applied", launch_method=ZAPRET2_MODE)
        status_bar.set_plan(plan)
        status_bar.spinner.stop = Mock(side_effect=AssertionError("same status must not stop spinner again"))
        status_bar.spinner.start = Mock(side_effect=AssertionError("same status must not start spinner again"))
        status_bar.check_label.setVisible = Mock(side_effect=AssertionError("same status must not update visibility"))
        status_bar.text_label.setText = Mock(side_effect=AssertionError("same status must not rewrite text"))

        status_bar.set_plan(plan)

        status_bar.spinner.stop.assert_not_called()
        status_bar.spinner.start.assert_not_called()
        status_bar.check_label.setVisible.assert_not_called()
        status_bar.text_label.setText.assert_not_called()

    def test_status_bar_text_change_keeps_same_indicator_render(self) -> None:
        from presets.ui.common.preset_status_bar import PresetStatusBar, build_preset_status_plan

        status_bar = PresetStatusBar()
        status_bar.set_plan(build_preset_status_plan("saved", launch_method=ZAPRET2_MODE, text="Сохранено"))
        status_bar.spinner.stop = Mock(side_effect=AssertionError("same indicator must not stop spinner again"))
        status_bar.spinner.start = Mock(side_effect=AssertionError("same indicator must not start spinner again"))
        status_bar.check_label.setVisible = Mock(side_effect=AssertionError("same indicator must not update visibility"))

        status_bar.set_plan(build_preset_status_plan("saved", launch_method=ZAPRET2_MODE, text="Сохранено повторно"))

        status_bar.spinner.stop.assert_not_called()
        status_bar.spinner.start.assert_not_called()
        status_bar.check_label.setVisible.assert_not_called()

    def test_title_status_icon_skips_duplicate_plan_render(self) -> None:
        from presets.ui.common.preset_status_bar import PresetStatusIcon, build_preset_status_plan

        icon = PresetStatusIcon(size=24)
        plan = build_preset_status_plan("applied", launch_method=ZAPRET2_MODE)
        icon.set_plan(plan)
        icon.spinner.stop = Mock(side_effect=AssertionError("same status must not stop spinner again"))
        icon.spinner.start = Mock(side_effect=AssertionError("same status must not start spinner again"))
        icon.check_label.setVisible = Mock(side_effect=AssertionError("same status must not update visibility"))
        icon.setToolTip = Mock(side_effect=AssertionError("same status must not rewrite tooltip"))
        icon.setVisible = Mock(side_effect=AssertionError("same status must not update visibility"))

        icon.set_plan(plan)

        icon.spinner.stop.assert_not_called()
        icon.spinner.start.assert_not_called()
        icon.check_label.setVisible.assert_not_called()
        icon.setToolTip.assert_not_called()
        icon.setVisible.assert_not_called()

    def test_title_status_icon_text_change_keeps_same_indicator_render(self) -> None:
        from presets.ui.common.preset_status_bar import PresetStatusIcon, build_preset_status_plan

        icon = PresetStatusIcon(size=24)
        icon.set_plan(build_preset_status_plan("saved", launch_method=ZAPRET2_MODE, text="Сохранено"))
        icon.spinner.stop = Mock(side_effect=AssertionError("same indicator must not stop spinner again"))
        icon.spinner.start = Mock(side_effect=AssertionError("same indicator must not start spinner again"))
        icon.check_label.setVisible = Mock(side_effect=AssertionError("same indicator must not update visibility"))
        icon.setVisible = Mock(side_effect=AssertionError("same indicator must not update widget visibility"))

        icon.set_plan(build_preset_status_plan("saved", launch_method=ZAPRET2_MODE, text="Сохранено повторно"))

        icon.spinner.stop.assert_not_called()
        icon.spinner.start.assert_not_called()
        icon.check_label.setVisible.assert_not_called()
        icon.setVisible.assert_not_called()

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

    def test_raw_editor_runtime_toggle_skips_duplicate_button_render(self) -> None:
        from presets.ui.common.preset_subpage_base import (
            RuntimeToggleButtonPlan,
            apply_runtime_toggle_button_plan,
        )

        button = _RuntimeToggleButton()
        plan = RuntimeToggleButtonPlan(
            text="Запустить",
            icon_name="PLAY",
            should_stop=False,
            enabled=True,
        )

        self.assertFalse(
            apply_runtime_toggle_button_plan(
                button,
                plan,
                runtime_available=True,
                icon_factory=lambda name: f"icon:{name}",
            )
        )
        self.assertEqual(button.text_calls, ["Запустить"])
        self.assertEqual(button.icon_calls, ["icon:PLAY"])
        self.assertEqual(button.enabled_calls, [True])

        button.setText = Mock(side_effect=AssertionError("same runtime toggle must not rewrite text"))
        button.setIcon = Mock(side_effect=AssertionError("same runtime toggle must not rewrite icon"))
        button.setEnabled = Mock(side_effect=AssertionError("same runtime toggle must not rewrite enabled"))

        self.assertFalse(
            apply_runtime_toggle_button_plan(
                button,
                plan,
                runtime_available=True,
                icon_factory=lambda name: f"icon:{name}",
            )
        )

        button.setText.assert_not_called()
        button.setIcon.assert_not_called()
        button.setEnabled.assert_not_called()

    def test_raw_editor_runtime_toggle_enabled_change_keeps_same_text_and_icon(self) -> None:
        from presets.ui.common.preset_subpage_base import (
            RuntimeToggleButtonPlan,
            apply_runtime_toggle_button_plan,
        )

        button = _RuntimeToggleButton()
        plan = RuntimeToggleButtonPlan(
            text="Запустить",
            icon_name="PLAY",
            should_stop=False,
            enabled=True,
        )

        apply_runtime_toggle_button_plan(
            button,
            plan,
            runtime_available=False,
            icon_factory=lambda name: f"icon:{name}",
        )
        button.setText = Mock(side_effect=AssertionError("enabled-only change must not rewrite text"))
        button.setIcon = Mock(side_effect=AssertionError("enabled-only change must not rewrite icon"))

        apply_runtime_toggle_button_plan(
            button,
            plan,
            runtime_available=True,
            icon_factory=lambda name: f"icon:{name}",
        )

        button.setText.assert_not_called()
        button.setIcon.assert_not_called()
        self.assertEqual(button.enabled_calls, [False, True])


if __name__ == "__main__":
    unittest.main()
