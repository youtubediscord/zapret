from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock


class _LoadRuntime:
    def __init__(self, *, running: bool) -> None:
        self.running = bool(running)
        self.started = 0

    def is_running(self) -> bool:
        return self.running

    def start_qthread_worker(self, **_kwargs) -> None:
        self.started += 1


def _make_refresh_runtime(*, running: bool):
    load_runtime = _LoadRuntime(running=running)
    runtime = SimpleNamespace(
        additional_settings_load_runtime=load_runtime,
        additional_settings_load_pending=False,
        additional_settings_dirty=False,
        additional_settings_request_id=0,
        next_additional_settings_request_id=Mock(return_value=1),
    )
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

        Zapret1ModeControlPage._on_additional_settings_load_worker_finished(page, object())

        self.assertFalse(runtime.additional_settings_load_pending)
        self.assertEqual(load_runtime.started, 1)

    def test_zapret2_additional_settings_finished_starts_pending_reload(self) -> None:
        from presets.ui.control.zapret2.page import Zapret2ModeControlPage

        runtime, load_runtime = _make_refresh_runtime(running=False)
        runtime.additional_settings_load_pending = True
        runtime.additional_settings_dirty = True
        page = _make_page(Zapret2ModeControlPage, runtime)

        Zapret2ModeControlPage._on_additional_settings_load_worker_finished(page, object())

        self.assertFalse(runtime.additional_settings_load_pending)
        self.assertEqual(load_runtime.started, 1)


if __name__ == "__main__":
    unittest.main()
