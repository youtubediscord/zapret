from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from presets.ui.common.user_presets_page import UserPresetsPageBase
from ui.one_shot_worker_runtime import OneShotWorkerRuntime


class _Signal:
    def __init__(self) -> None:
        self.callbacks = []

    def connect(self, callback) -> None:
        self.callbacks.append(callback)


class _Worker:
    def __init__(self, *, running: bool = False) -> None:
        self._running = running
        self.completed = _Signal()
        self.failed = _Signal()
        self.finished = _Signal()
        self.start = Mock()
        self.deleteLater = Mock()

    def isRunning(self) -> bool:  # noqa: N802
        return self._running


class UserPresetEditActionQueueTests(unittest.TestCase):
    def test_edit_action_queues_next_request_while_worker_runs(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_edit_action_runtime = OneShotWorkerRuntime()
        page._preset_edit_action_runtime.worker = _Worker(running=True)
        page._preset_edit_action_request_id = 1
        page._preset_edit_action_pending = []
        page.create_preset_edit_action_worker = Mock()

        UserPresetsPageBase._request_preset_edit_action(
            page,
            "rename",
            current_name="Old.txt",
            new_name="New.txt",
        )

        page.create_preset_edit_action_worker.assert_not_called()
        self.assertEqual(
            page._preset_edit_action_pending,
            [
                {
                    "action": "rename",
                    "name": "",
                    "current_name": "Old.txt",
                    "new_name": "New.txt",
                    "from_current": False,
                },
            ],
        )

    def test_edit_action_worker_finished_starts_pending_request(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        old_worker = _Worker(running=False)
        next_worker = _Worker(running=False)
        page._preset_edit_action_runtime = OneShotWorkerRuntime()
        page._preset_edit_action_request_id = 1
        page._preset_edit_action_pending = [
            {
                "action": "create",
                "name": "Preset",
                "current_name": "",
                "new_name": "",
                "from_current": True,
            },
        ]
        page.create_preset_edit_action_worker = Mock(return_value=next_worker)

        callbacks = []
        with patch(
            "presets.ui.common.user_presets_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            UserPresetsPageBase._on_preset_edit_action_worker_finished(page, old_worker)

        page.create_preset_edit_action_worker.assert_not_called()
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page.create_preset_edit_action_worker.assert_called_once_with(
            2,
            action="create",
            name="Preset",
            current_name="",
            new_name="",
            from_current=True,
        )
        next_worker.start.assert_called_once_with()
        self.assertEqual(page._preset_edit_action_pending, [])


if __name__ == "__main__":
    unittest.main()
