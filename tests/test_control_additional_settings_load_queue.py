from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch


class _LoadRuntime:
    def __init__(self, *, running: bool) -> None:
        self.running = bool(running)
        self.started = 0

    def is_running(self) -> bool:
        return self.running

    def start_qthread_worker(self, **_kwargs) -> None:
        self.started += 1


def _make_refresh_runtime(*, running: bool):
    from presets.ui.control.refresh_runtime_state import ModeControlRefreshRuntime

    load_runtime = _LoadRuntime(running=running)
    runtime = ModeControlRefreshRuntime()
    runtime.additional_settings_load_runtime = load_runtime
    runtime.additional_settings_load_state.runtime = load_runtime
    runtime.additional_settings_dirty = False
    runtime.additional_settings_request_id = 0
    runtime.next_additional_settings_request_id = Mock(return_value=1)
    runtime.accept_additional_settings_result = Mock(return_value=True)

    def _accept_worker_finish(worker, request_attr: str) -> bool:
        request_id = getattr(worker, "_request_id", None)
        if request_id is None:
            return True
        return int(request_id) == int(getattr(runtime, request_attr, -1))

    runtime.accept_worker_finish = _accept_worker_finish
    return runtime, load_runtime


def _make_page(page_cls, runtime):
    page = page_cls.__new__(page_cls)
    page._refresh_runtime = runtime
    page._cleanup_in_progress = False
    page._create_additional_settings_load_worker = Mock(return_value=object())
    page.isVisible = Mock(return_value=True)
    page.run_when_page_ready = Mock()
    return page


class ControlAdditionalSettingsLoadQueueTests(unittest.TestCase):
    def test_additional_settings_load_queue_uses_shared_latest_worker_state(self) -> None:
        import inspect

        from presets.ui.control.refresh_runtime_state import ModeControlRefreshRuntime
        from ui.latest_value_worker_state import LatestValueWorkerState

        runtime = ModeControlRefreshRuntime()
        runtime_source = inspect.getsource(ModeControlRefreshRuntime.__init__)

        self.assertIsInstance(runtime.additional_settings_load_state, LatestValueWorkerState)
        self.assertNotIn("self.additional_settings_load_pending = False", runtime_source)
        self.assertNotIn("self.additional_settings_load_start_scheduled = False", runtime_source)

    def test_refresh_runtime_rejects_stale_additional_settings_load_worker_object(self) -> None:
        from presets.ui.control.refresh_runtime_state import ModeControlRefreshRuntime

        runtime = ModeControlRefreshRuntime()
        runtime.additional_settings_load_runtime = SimpleNamespace(worker=object())

        self.assertFalse(
            runtime.accept_worker_finish(object(), "additional_settings_request_id")
        )

    def test_zapret1_additional_settings_reload_marks_pending_while_worker_runs(self) -> None:
        from presets.ui.control.zapret1.page import Zapret1ModeControlPage

        runtime, load_runtime = _make_refresh_runtime(running=True)
        page = _make_page(Zapret1ModeControlPage, runtime)

        Zapret1ModeControlPage._schedule_additional_settings_reload(page, force=True)

        self.assertTrue(runtime.additional_settings_load_pending)
        self.assertTrue(runtime.additional_settings_dirty)
        self.assertEqual(load_runtime.started, 0)

    def test_zapret2_additional_settings_reload_marks_pending_while_worker_runs(self) -> None:
        from presets.ui.control.zapret2.page import Zapret2ModeControlPage

        runtime, load_runtime = _make_refresh_runtime(running=True)
        page = _make_page(Zapret2ModeControlPage, runtime)

        Zapret2ModeControlPage._schedule_additional_settings_reload(page, force=True)

        self.assertTrue(runtime.additional_settings_load_pending)
        self.assertTrue(runtime.additional_settings_dirty)
        self.assertEqual(load_runtime.started, 0)

    def test_zapret1_additional_settings_finished_starts_pending_reload(self) -> None:
        from presets.ui.control.zapret1.page import Zapret1ModeControlPage

        runtime, load_runtime = _make_refresh_runtime(running=False)
        runtime.additional_settings_load_pending = True
        runtime.additional_settings_dirty = True
        page = _make_page(Zapret1ModeControlPage, runtime)

        callbacks = []
        with patch(
            "presets.ui.control.zapret1.page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            Zapret1ModeControlPage._on_additional_settings_load_worker_finished(page, object())

        self.assertFalse(runtime.additional_settings_load_pending)
        self.assertEqual(load_runtime.started, 0)
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        self.assertEqual(load_runtime.started, 1)

    def test_zapret2_additional_settings_finished_starts_pending_reload(self) -> None:
        from presets.ui.control.zapret2.page import Zapret2ModeControlPage

        runtime, load_runtime = _make_refresh_runtime(running=False)
        runtime.additional_settings_load_pending = True
        runtime.additional_settings_dirty = True
        page = _make_page(Zapret2ModeControlPage, runtime)

        callbacks = []
        with patch(
            "presets.ui.control.zapret2.page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            Zapret2ModeControlPage._on_additional_settings_load_worker_finished(page, object())

        self.assertFalse(runtime.additional_settings_load_pending)
        self.assertEqual(load_runtime.started, 0)
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        self.assertEqual(load_runtime.started, 1)

    def test_zapret1_stale_additional_settings_finish_does_not_start_pending_reload(self) -> None:
        from presets.ui.control.zapret1.page import Zapret1ModeControlPage

        runtime, load_runtime = _make_refresh_runtime(running=False)
        runtime.additional_settings_request_id = 2
        runtime.additional_settings_load_pending = True
        page = _make_page(Zapret1ModeControlPage, runtime)

        with patch("presets.ui.control.zapret1.page.QTimer.singleShot") as single_shot:
            Zapret1ModeControlPage._on_additional_settings_load_worker_finished(
                page,
                SimpleNamespace(_request_id=1),
            )

        single_shot.assert_not_called()
        self.assertTrue(runtime.additional_settings_load_pending)
        self.assertEqual(load_runtime.started, 0)

    def test_zapret2_stale_additional_settings_finish_does_not_start_pending_reload(self) -> None:
        from presets.ui.control.zapret2.page import Zapret2ModeControlPage

        runtime, load_runtime = _make_refresh_runtime(running=False)
        runtime.additional_settings_request_id = 2
        runtime.additional_settings_load_pending = True
        page = _make_page(Zapret2ModeControlPage, runtime)

        with patch("presets.ui.control.zapret2.page.QTimer.singleShot") as single_shot:
            Zapret2ModeControlPage._on_additional_settings_load_worker_finished(
                page,
                SimpleNamespace(_request_id=1),
            )

        single_shot.assert_not_called()
        self.assertTrue(runtime.additional_settings_load_pending)
        self.assertEqual(load_runtime.started, 0)

    def test_zapret1_additional_settings_reload_waits_while_restart_is_scheduled(self) -> None:
        from presets.ui.control.zapret1.page import Zapret1ModeControlPage

        runtime, load_runtime = _make_refresh_runtime(running=False)
        runtime.additional_settings_load_pending = True
        runtime.additional_settings_dirty = True
        page = _make_page(Zapret1ModeControlPage, runtime)

        callbacks = []
        with patch(
            "presets.ui.control.zapret1.page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            Zapret1ModeControlPage._on_additional_settings_load_worker_finished(page, object())

        self.assertTrue(runtime.additional_settings_load_start_scheduled)

        Zapret1ModeControlPage._schedule_additional_settings_reload(page, force=True)

        self.assertEqual(load_runtime.started, 0)
        self.assertTrue(runtime.additional_settings_load_pending)
        self.assertTrue(runtime.additional_settings_dirty)
        self.assertEqual(len(callbacks), 1)

    def test_zapret2_additional_settings_reload_waits_while_restart_is_scheduled(self) -> None:
        from presets.ui.control.zapret2.page import Zapret2ModeControlPage

        runtime, load_runtime = _make_refresh_runtime(running=False)
        runtime.additional_settings_load_pending = True
        runtime.additional_settings_dirty = True
        page = _make_page(Zapret2ModeControlPage, runtime)

        callbacks = []
        with patch(
            "presets.ui.control.zapret2.page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            Zapret2ModeControlPage._on_additional_settings_load_worker_finished(page, object())

        self.assertTrue(runtime.additional_settings_load_start_scheduled)

        Zapret2ModeControlPage._schedule_additional_settings_reload(page, force=True)

        self.assertEqual(load_runtime.started, 0)
        self.assertTrue(runtime.additional_settings_load_pending)
        self.assertTrue(runtime.additional_settings_dirty)
        self.assertEqual(len(callbacks), 1)

    def test_zapret1_additional_settings_result_ignored_when_new_load_is_pending(self) -> None:
        from presets.ui.control.zapret1.page import Zapret1ModeControlPage

        runtime, _load_runtime = _make_refresh_runtime(running=False)
        runtime.additional_settings_load_pending = True
        page = _make_page(Zapret1ModeControlPage, runtime)
        page._apply_additional_settings_state = Mock()

        Zapret1ModeControlPage._on_additional_settings_loaded(page, 1, {"discord_restart": True})

        page._apply_additional_settings_state.assert_not_called()

    def test_zapret2_additional_settings_result_ignored_when_new_load_is_pending(self) -> None:
        from presets.ui.control.zapret2.page import Zapret2ModeControlPage

        runtime, _load_runtime = _make_refresh_runtime(running=False)
        runtime.additional_settings_load_pending = True
        page = _make_page(Zapret2ModeControlPage, runtime)
        page._apply_additional_settings_state = Mock()

        Zapret2ModeControlPage._on_additional_settings_loaded(page, 1, {"discord_restart": True})

        page._apply_additional_settings_state.assert_not_called()

    def test_control_pages_delay_additional_settings_reload_after_active_preset_switch(self) -> None:
        from app.state_store import AppUiState
        from presets.ui.control.zapret1.page import Zapret1ModeControlPage
        from presets.ui.control.zapret2.page import Zapret2ModeControlPage

        for page_cls, module_name in (
            (Zapret1ModeControlPage, "presets.ui.control.zapret1.page"),
            (Zapret2ModeControlPage, "presets.ui.control.zapret2.page"),
        ):
            with self.subTest(page_cls=page_cls.__name__):
                runtime, _load_runtime = _make_refresh_runtime(running=False)
                page = page_cls.__new__(page_cls)
                page._cleanup_in_progress = False
                page._refresh_runtime = runtime
                page.isVisible = Mock(return_value=True)
                page.run_when_page_ready = Mock()
                page._schedule_additional_settings_reload = Mock()
                page._schedule_top_summary_reload_after_preset_switch = Mock()
                page._refresh_preset_name = Mock()
                page._apply_selected_preset_name_fast = Mock()
                page._refresh_top_summary = Mock()
                page._apply_top_summary_premium = Mock()
                page.set_loading = Mock()
                page.update_status = Mock()
                page.update_strategy = Mock()
                page._refresh_last_status_message = Mock()

                callbacks = []
                with patch(
                    f"{module_name}.QTimer.singleShot",
                    side_effect=lambda delay_ms, callback: callbacks.append((delay_ms, callback)),
                ):
                    page_cls._on_ui_state_changed(
                        page,
                        AppUiState(current_strategy_summary="Профили"),
                        frozenset({"active_preset_revision"}),
                    )
                    page_cls._on_ui_state_changed(
                        page,
                        AppUiState(current_strategy_summary="Профили"),
                        frozenset({"active_preset_revision"}),
                    )

                page._schedule_additional_settings_reload.assert_not_called()
                self.assertTrue(runtime.additional_settings_dirty)
                self.assertTrue(getattr(runtime, "additional_settings_reload_after_preset_switch_scheduled", False))
                self.assertEqual(len(callbacks), 1)

                callbacks[0][1]()

                self.assertFalse(getattr(runtime, "additional_settings_reload_after_preset_switch_scheduled", False))
                page._schedule_additional_settings_reload.assert_called_once_with(force=True)


if __name__ == "__main__":
    unittest.main()
