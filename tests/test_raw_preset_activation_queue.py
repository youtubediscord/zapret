from __future__ import annotations

import unittest
from unittest.mock import Mock, patch


class _Runtime:
    def __init__(self, *, running: bool) -> None:
        self.running = bool(running)
        self.started: list[object] = []

    def is_running(self) -> bool:
        return self.running

    def start_qthread_worker(self, *, worker_factory, **_kwargs):
        worker = worker_factory(0)
        self.started.append(worker)
        return 0, worker


class RawPresetActivationQueueTests(unittest.TestCase):
    def test_raw_preset_activation_queues_current_file_while_worker_runs(self) -> None:
        from presets.ui.common.preset_subpage_base import PresetRawEditorPage

        page = PresetRawEditorPage.__new__(PresetRawEditorPage)
        page._raw_activate_runtime = _Runtime(running=True)
        page._raw_activate_request_id = 1
        page._preset_file_name = "Default.txt"
        page._pending_raw_preset_activation = ""
        page.activateButton = None
        page.create_raw_preset_activate_worker = Mock()

        PresetRawEditorPage._request_preset_activation(page)

        page.create_raw_preset_activate_worker.assert_not_called()
        self.assertEqual(page._pending_raw_preset_activation, "Default.txt")

    def test_raw_preset_activation_worker_finished_starts_pending_file(self) -> None:
        from presets.ui.common.preset_subpage_base import PresetRawEditorPage

        runtime = _Runtime(running=False)
        worker = object()
        page = PresetRawEditorPage.__new__(PresetRawEditorPage)
        page._raw_activate_runtime = runtime
        page._raw_activate_request_id = 1
        page._pending_raw_preset_activation = "Next.txt"
        page._cleanup_in_progress = False
        page.activateButton = None
        page.create_raw_preset_activate_worker = Mock(return_value=worker)
        callbacks = []

        with patch(
            "presets.ui.common.preset_subpage_base.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            PresetRawEditorPage._on_preset_activation_worker_finished(page, object())

        page.create_raw_preset_activate_worker.assert_not_called()
        self.assertEqual(runtime.started, [])
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page.create_raw_preset_activate_worker.assert_called_once_with(2, "Next.txt", page)
        self.assertEqual(runtime.started, [worker])
        self.assertEqual(page._pending_raw_preset_activation, "")

    def test_scheduled_pending_activation_keeps_latest_file_before_worker_starts(self) -> None:
        from presets.ui.common.preset_subpage_base import PresetRawEditorPage

        runtime = _Runtime(running=False)
        worker = object()
        page = PresetRawEditorPage.__new__(PresetRawEditorPage)
        page._raw_activate_runtime = runtime
        page._raw_save_runtime = _Runtime(running=False)
        page._raw_action_runtime = _Runtime(running=False)
        page._raw_activate_request_id = 1
        page._preset_file_name = "Latest.txt"
        page._pending_raw_preset_activation = "Old.txt"
        page._pending_raw_preset_write_operations = []
        page._cleanup_in_progress = False
        page.activateButton = None
        page.create_raw_preset_activate_worker = Mock(return_value=worker)
        callbacks = []

        with patch(
            "presets.ui.common.preset_subpage_base.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            PresetRawEditorPage._on_preset_activation_worker_finished(page, object())
            PresetRawEditorPage._request_preset_activation(page)

        page.create_raw_preset_activate_worker.assert_not_called()
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page.create_raw_preset_activate_worker.assert_called_once_with(2, "Latest.txt", page)
        self.assertEqual(runtime.started, [worker])
        self.assertEqual(page._pending_raw_preset_activation, "")

    def test_activation_result_ignored_when_next_activation_is_pending(self) -> None:
        from presets.ui.common.preset_subpage_base import PresetRawEditorPage

        page = PresetRawEditorPage.__new__(PresetRawEditorPage)
        page._raw_activate_request_id = 3
        page._pending_raw_preset_activation = "Next.txt"
        page._preset_name = "Old"
        page._refresh_header = Mock(
            side_effect=AssertionError("pending activation must own the success state")
        )
        page._set_footer = Mock()
        page._show_success = Mock()

        PresetRawEditorPage._on_preset_activation_finished(page, 3, True)

        page._refresh_header.assert_not_called()
        page._set_footer.assert_not_called()
        page._show_success.assert_not_called()
        self.assertEqual(page._pending_raw_preset_activation, "Next.txt")

    def test_activation_rejection_ignored_when_next_activation_is_pending(self) -> None:
        from presets.ui.common.preset_subpage_base import PresetRawEditorPage

        page = PresetRawEditorPage.__new__(PresetRawEditorPage)
        page._raw_activate_request_id = 3
        page._pending_raw_preset_activation = "Next.txt"
        page._preset_name = "Old"
        page._show_error = Mock(
            side_effect=AssertionError("pending activation must own the rejected state")
        )

        PresetRawEditorPage._on_preset_activation_finished(page, 3, False)

        page._show_error.assert_not_called()
        self.assertEqual(page._pending_raw_preset_activation, "Next.txt")

    def test_activation_error_ignored_when_next_activation_is_pending(self) -> None:
        from presets.ui.common.preset_subpage_base import PresetRawEditorPage

        page = PresetRawEditorPage.__new__(PresetRawEditorPage)
        page._raw_activate_request_id = 3
        page._pending_raw_preset_activation = "Next.txt"
        page._show_error = Mock(
            side_effect=AssertionError("pending activation must own the error state")
        )

        PresetRawEditorPage._on_preset_activation_failed(page, 3, "old error")

        page._show_error.assert_not_called()
        self.assertEqual(page._pending_raw_preset_activation, "Next.txt")


if __name__ == "__main__":
    unittest.main()
