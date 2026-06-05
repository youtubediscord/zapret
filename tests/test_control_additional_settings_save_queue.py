from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch


class _SaveRuntime:
    def __init__(self, *, running: bool) -> None:
        self.running = bool(running)
        self.started: list[object] = []

    def is_running(self) -> bool:
        return self.running

    def start_qthread_worker(self, *, worker_factory, **_kwargs):
        worker = worker_factory(0)
        self.started.append(worker)
        return 0, worker


def _make_refresh_runtime(*, running: bool):
    from presets.ui.control.refresh_runtime_state import ModeControlRefreshRuntime

    save_runtime = _SaveRuntime(running=running)
    runtime = ModeControlRefreshRuntime()
    runtime.additional_settings_save_runtime = save_runtime
    runtime.additional_settings_save_request_id = 1
    runtime.additional_settings_request_id = 0
    runtime.additional_settings_dirty = False
    runtime.additional_settings_load_runtime = SimpleNamespace(cancel=Mock())
    runtime.mark_additional_settings_written = Mock()
    runtime.next_additional_settings_save_request_id = Mock(return_value=2)
    return runtime, save_runtime


def _make_page(page_cls, runtime):
    page = page_cls.__new__(page_cls)
    page._refresh_runtime = runtime
    page._cleanup_in_progress = False
    page._create_additional_settings_save_worker = Mock(return_value=object())
    return page


class ControlAdditionalSettingsSaveQueueTests(unittest.TestCase):
    def test_zapret1_additional_settings_save_keeps_pending_toggles_for_different_settings(self) -> None:
        from presets.ui.control.zapret1.page import Zapret1ModeControlPage

        runtime, save_runtime = _make_refresh_runtime(running=True)
        page = _make_page(Zapret1ModeControlPage, runtime)

        Zapret1ModeControlPage._request_additional_settings_save(
            page,
            "wssize",
            True,
            launch_method="zapret1",
        )
        Zapret1ModeControlPage._request_additional_settings_save(
            page,
            "debug_log",
            False,
            launch_method="zapret1",
        )

        self.assertEqual(save_runtime.started, [])
        self.assertEqual(
            runtime.additional_settings_save_pending,
            [
                ("wssize", True, "zapret1"),
                ("debug_log", False, "zapret1"),
            ],
        )

    def test_zapret2_additional_settings_save_keeps_pending_toggles_for_different_settings(self) -> None:
        from presets.ui.control.zapret2.page import Zapret2ModeControlPage

        runtime, save_runtime = _make_refresh_runtime(running=True)
        page = _make_page(Zapret2ModeControlPage, runtime)

        Zapret2ModeControlPage._request_additional_settings_save(
            page,
            "wssize",
            True,
            launch_method="zapret2",
        )
        Zapret2ModeControlPage._request_additional_settings_save(
            page,
            "debug_log",
            False,
            launch_method="zapret2",
        )

        self.assertEqual(save_runtime.started, [])
        self.assertEqual(
            runtime.additional_settings_save_pending,
            [
                ("wssize", True, "zapret2"),
                ("debug_log", False, "zapret2"),
            ],
        )

    def test_zapret1_additional_settings_save_replaces_pending_toggle_for_same_setting(self) -> None:
        from presets.ui.control.zapret1.page import Zapret1ModeControlPage

        runtime, save_runtime = _make_refresh_runtime(running=True)
        page = _make_page(Zapret1ModeControlPage, runtime)

        Zapret1ModeControlPage._request_additional_settings_save(
            page,
            "debug_log",
            True,
            launch_method="zapret1",
        )
        Zapret1ModeControlPage._request_additional_settings_save(
            page,
            "debug_log",
            False,
            launch_method="zapret1",
        )

        self.assertEqual(save_runtime.started, [])
        self.assertEqual(runtime.additional_settings_save_pending, [("debug_log", False, "zapret1")])

    def test_zapret2_additional_settings_save_replaces_pending_toggle_for_same_setting(self) -> None:
        from presets.ui.control.zapret2.page import Zapret2ModeControlPage

        runtime, save_runtime = _make_refresh_runtime(running=True)
        page = _make_page(Zapret2ModeControlPage, runtime)

        Zapret2ModeControlPage._request_additional_settings_save(
            page,
            "debug_log",
            True,
            launch_method="zapret2",
        )
        Zapret2ModeControlPage._request_additional_settings_save(
            page,
            "debug_log",
            False,
            launch_method="zapret2",
        )

        self.assertEqual(save_runtime.started, [])
        self.assertEqual(runtime.additional_settings_save_pending, [("debug_log", False, "zapret2")])

    def test_zapret1_additional_settings_save_queues_while_restart_is_scheduled(self) -> None:
        from presets.ui.control.zapret1.page import Zapret1ModeControlPage

        runtime, save_runtime = _make_refresh_runtime(running=False)
        runtime.additional_settings_save_start_scheduled = True
        page = _make_page(Zapret1ModeControlPage, runtime)

        Zapret1ModeControlPage._request_additional_settings_save(
            page,
            "debug_log",
            True,
            launch_method="zapret1",
        )

        self.assertEqual(save_runtime.started, [])
        self.assertEqual(runtime.additional_settings_save_pending, [("debug_log", True, "zapret1")])

    def test_zapret2_additional_settings_save_queues_while_restart_is_scheduled(self) -> None:
        from presets.ui.control.zapret2.page import Zapret2ModeControlPage

        runtime, save_runtime = _make_refresh_runtime(running=False)
        runtime.additional_settings_save_start_scheduled = True
        page = _make_page(Zapret2ModeControlPage, runtime)

        Zapret2ModeControlPage._request_additional_settings_save(
            page,
            "debug_log",
            True,
            launch_method="zapret2",
        )

        self.assertEqual(save_runtime.started, [])
        self.assertEqual(runtime.additional_settings_save_pending, [("debug_log", True, "zapret2")])

    def test_zapret1_additional_settings_finished_starts_next_pending_save(self) -> None:
        from presets.ui.control.zapret1.page import Zapret1ModeControlPage

        runtime, save_runtime = _make_refresh_runtime(running=False)
        runtime.additional_settings_save_pending = [("debug_log", True, "zapret1")]
        worker = object()
        page = _make_page(Zapret1ModeControlPage, runtime)
        page._create_additional_settings_save_worker = Mock(return_value=worker)

        callbacks = []
        with patch(
            "presets.ui.control.zapret1.page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            Zapret1ModeControlPage._on_additional_settings_save_worker_finished(page, object())

        page._create_additional_settings_save_worker.assert_not_called()
        self.assertEqual(save_runtime.started, [])
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page._create_additional_settings_save_worker.assert_called_once_with(
            2,
            setting="debug_log",
            enabled=True,
            parent=page,
        )
        self.assertEqual(save_runtime.started, [worker])
        self.assertEqual(runtime.additional_settings_save_pending, [])

    def test_zapret2_additional_settings_finished_starts_next_pending_save(self) -> None:
        from presets.ui.control.zapret2.page import Zapret2ModeControlPage

        runtime, save_runtime = _make_refresh_runtime(running=False)
        runtime.additional_settings_save_pending = [("debug_log", True, "zapret2")]
        worker = object()
        page = _make_page(Zapret2ModeControlPage, runtime)
        page._create_additional_settings_save_worker = Mock(return_value=worker)

        callbacks = []
        with patch(
            "presets.ui.control.zapret2.page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            Zapret2ModeControlPage._on_additional_settings_save_worker_finished(page, object())

        page._create_additional_settings_save_worker.assert_not_called()
        self.assertEqual(save_runtime.started, [])
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page._create_additional_settings_save_worker.assert_called_once_with(
            2,
            setting="debug_log",
            enabled=True,
            parent=page,
        )
        self.assertEqual(save_runtime.started, [worker])
        self.assertEqual(runtime.additional_settings_save_pending, [])

    def test_zapret1_stale_additional_settings_save_finish_does_not_start_pending_save(self) -> None:
        from presets.ui.control.zapret1.page import Zapret1ModeControlPage

        runtime, save_runtime = _make_refresh_runtime(running=False)
        runtime.additional_settings_save_request_id = 2
        runtime.additional_settings_save_pending = [("debug_log", True, "zapret1")]
        page = _make_page(Zapret1ModeControlPage, runtime)

        with patch("presets.ui.control.zapret1.page.QTimer.singleShot") as single_shot:
            Zapret1ModeControlPage._on_additional_settings_save_worker_finished(
                page,
                SimpleNamespace(_request_id=1),
            )

        single_shot.assert_not_called()
        self.assertEqual(save_runtime.started, [])
        self.assertEqual(runtime.additional_settings_save_pending, [("debug_log", True, "zapret1")])

    def test_zapret1_stale_additional_settings_save_object_does_not_start_pending_save(self) -> None:
        from presets.ui.control.zapret1.page import Zapret1ModeControlPage

        runtime, save_runtime = _make_refresh_runtime(running=False)
        save_runtime.worker = object()
        runtime.additional_settings_save_pending = [("debug_log", True, "zapret1")]
        page = _make_page(Zapret1ModeControlPage, runtime)

        with patch("presets.ui.control.zapret1.page.QTimer.singleShot") as single_shot:
            Zapret1ModeControlPage._on_additional_settings_save_worker_finished(page, object())

        single_shot.assert_not_called()
        self.assertEqual(save_runtime.started, [])
        self.assertEqual(runtime.additional_settings_save_pending, [("debug_log", True, "zapret1")])

    def test_zapret2_stale_additional_settings_save_finish_does_not_start_pending_save(self) -> None:
        from presets.ui.control.zapret2.page import Zapret2ModeControlPage

        runtime, save_runtime = _make_refresh_runtime(running=False)
        runtime.additional_settings_save_request_id = 2
        runtime.additional_settings_save_pending = [("debug_log", True, "zapret2")]
        page = _make_page(Zapret2ModeControlPage, runtime)

        with patch("presets.ui.control.zapret2.page.QTimer.singleShot") as single_shot:
            Zapret2ModeControlPage._on_additional_settings_save_worker_finished(
                page,
                SimpleNamespace(_request_id=1),
            )

        single_shot.assert_not_called()
        self.assertEqual(save_runtime.started, [])
        self.assertEqual(runtime.additional_settings_save_pending, [("debug_log", True, "zapret2")])

    def test_zapret2_stale_additional_settings_save_object_does_not_start_pending_save(self) -> None:
        from presets.ui.control.zapret2.page import Zapret2ModeControlPage

        runtime, save_runtime = _make_refresh_runtime(running=False)
        save_runtime.worker = object()
        runtime.additional_settings_save_pending = [("debug_log", True, "zapret2")]
        page = _make_page(Zapret2ModeControlPage, runtime)

        with patch("presets.ui.control.zapret2.page.QTimer.singleShot") as single_shot:
            Zapret2ModeControlPage._on_additional_settings_save_worker_finished(page, object())

        single_shot.assert_not_called()
        self.assertEqual(save_runtime.started, [])
        self.assertEqual(runtime.additional_settings_save_pending, [("debug_log", True, "zapret2")])

    def test_zapret1_additional_settings_save_error_ignored_when_new_save_is_pending(self) -> None:
        from presets.ui.control.zapret1.page import Zapret1ModeControlPage

        runtime, _save_runtime = _make_refresh_runtime(running=False)
        runtime.additional_settings_save_request_id = 4
        runtime.additional_settings_save_pending = [("debug_log", False, "zapret1")]
        page = _make_page(Zapret1ModeControlPage, runtime)
        page.window = Mock(return_value=object())

        with patch("presets.ui.control.zapret1.page.InfoBar.warning") as warning_mock:
            Zapret1ModeControlPage._on_additional_settings_save_failed(page, 4, "debug_log", "stale error")

        warning_mock.assert_not_called()

    def test_zapret2_additional_settings_save_error_ignored_when_new_save_is_pending(self) -> None:
        from presets.ui.control.zapret2.page import Zapret2ModeControlPage

        runtime, _save_runtime = _make_refresh_runtime(running=False)
        runtime.additional_settings_save_request_id = 4
        runtime.additional_settings_save_pending = [("debug_log", False, "zapret2")]
        page = _make_page(Zapret2ModeControlPage, runtime)
        page.window = Mock(return_value=object())

        with patch("qfluentwidgets.InfoBar.warning") as warning_mock:
            Zapret2ModeControlPage._on_additional_settings_save_failed(page, 4, "debug_log", "stale error")

        warning_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
