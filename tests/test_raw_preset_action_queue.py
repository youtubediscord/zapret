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


class RawPresetActionQueueTests(unittest.TestCase):
    def test_raw_preset_action_queues_next_request_while_worker_runs(self) -> None:
        from presets.ui.common.preset_subpage_base import PresetRawEditorPage

        page = PresetRawEditorPage.__new__(PresetRawEditorPage)
        page._raw_action_runtime = _Runtime(running=True)
        page._raw_action_request_id = 1
        page._pending_raw_preset_actions = []
        page.create_raw_preset_action_worker = Mock()

        PresetRawEditorPage._request_raw_preset_action(
            page,
            "duplicate",
            file_name="Default.txt",
            new_name="Default copy.txt",
        )

        page.create_raw_preset_action_worker.assert_not_called()
        self.assertEqual(
            page._pending_raw_preset_actions,
            [
                {
                    "action": "duplicate",
                    "payload": {
                        "file_name": "Default.txt",
                        "new_name": "Default copy.txt",
                    },
                },
            ],
        )

    def test_raw_preset_action_worker_finished_starts_pending_request(self) -> None:
        from presets.ui.common.preset_subpage_base import PresetRawEditorPage

        runtime = _Runtime(running=False)
        worker = object()
        page = PresetRawEditorPage.__new__(PresetRawEditorPage)
        page._raw_action_runtime = runtime
        page._raw_action_request_id = 1
        page._pending_raw_preset_actions = [
            {
                "action": "reset",
                "payload": {"file_name": "Default.txt"},
            }
        ]
        page._cleanup_in_progress = False
        page.create_raw_preset_action_worker = Mock(return_value=worker)

        PresetRawEditorPage._on_raw_preset_action_worker_finished(page, object())

        page.create_raw_preset_action_worker.assert_called_once_with(
            2,
            action="reset",
            payload={"file_name": "Default.txt"},
            parent=page,
        )
        self.assertEqual(runtime.started, [worker])
        self.assertEqual(page._pending_raw_preset_actions, [])


if __name__ == "__main__":
    unittest.main()
