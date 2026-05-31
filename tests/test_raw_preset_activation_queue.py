from __future__ import annotations

import unittest
from unittest.mock import Mock


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

        PresetRawEditorPage._on_preset_activation_worker_finished(page, object())

        page.create_raw_preset_activate_worker.assert_called_once_with(2, "Next.txt", page)
        self.assertEqual(runtime.started, [worker])
        self.assertEqual(page._pending_raw_preset_activation, "")


if __name__ == "__main__":
    unittest.main()
