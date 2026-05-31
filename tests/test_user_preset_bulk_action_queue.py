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


class UserPresetBulkActionQueueTests(unittest.TestCase):
    def test_bulk_action_queues_request_while_worker_runs(self) -> None:
        from presets.ui.common.user_presets_page import UserPresetsPageBase

        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_bulk_action_runtime = _Runtime(running=True)
        page._preset_bulk_action_request_id = 1
        page._preset_bulk_action_pending = []
        page.create_preset_bulk_action_worker = Mock()

        result = UserPresetsPageBase._request_preset_bulk_action(
            page,
            "import",
            file_path="C:/Temp/Preset.txt",
        )

        self.assertTrue(result)
        page.create_preset_bulk_action_worker.assert_not_called()
        self.assertEqual(
            page._preset_bulk_action_pending,
            [
                {
                    "action": "import",
                    "file_path": "C:/Temp/Preset.txt",
                },
            ],
        )

    def test_bulk_action_worker_finished_starts_pending_request(self) -> None:
        from presets.ui.common.user_presets_page import UserPresetsPageBase

        runtime = _Runtime(running=False)
        worker = object()
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_bulk_action_runtime = runtime
        page._preset_bulk_action_request_id = 1
        page._preset_bulk_action_kind = "import"
        page._preset_bulk_action_pending = [
            {
                "action": "reset_all",
                "file_path": "",
            }
        ]
        page._cleanup_in_progress = False
        page._bulk_reset_running = False
        page.create_preset_bulk_action_worker = Mock(return_value=worker)

        callbacks = []
        with patch(
            "presets.ui.common.user_presets_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            UserPresetsPageBase._on_preset_bulk_action_worker_finished(page, object())

        page.create_preset_bulk_action_worker.assert_not_called()
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page.create_preset_bulk_action_worker.assert_called_once_with(
            2,
            action="reset_all",
            file_path="",
        )
        self.assertEqual(runtime.started, [worker])
        self.assertEqual(page._preset_bulk_action_pending, [])
        self.assertEqual(page._preset_bulk_action_kind, "reset_all")


if __name__ == "__main__":
    unittest.main()
