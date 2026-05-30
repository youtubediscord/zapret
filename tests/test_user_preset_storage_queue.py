from __future__ import annotations

import unittest
from unittest.mock import Mock

from presets.ui.common.user_presets_page import UserPresetsPageBase


class _Signal:
    def connect(self, _callback) -> None:
        return None


class _Worker:
    completed = _Signal()
    failed = _Signal()
    finished = _Signal()

    def __init__(self, *, running: bool = False) -> None:
        self._running = running
        self.start = Mock()
        self.deleteLater = Mock()

    def isRunning(self) -> bool:  # noqa: N802
        return self._running


class UserPresetStorageQueueTests(unittest.TestCase):
    def test_storage_action_keeps_latest_pending_action_while_worker_runs(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_storage_action_worker = _Worker(running=True)
        page._pending_preset_storage_action = None

        UserPresetsPageBase._request_preset_storage_action(
            page,
            "rating",
            name="Preset.txt",
            display_name="Preset",
            rating=8,
        )

        self.assertEqual(
            page._pending_preset_storage_action,
            {
                "action": "rating",
                "name": "Preset.txt",
                "display_name": "Preset",
                "rating": 8,
                "direction": 0,
                "cached_metadata": None,
                "source_kind": "",
                "source_id": "",
                "destination_kind": "",
                "destination_id": "",
                "destination_folder_key": "",
            },
        )

    def test_storage_action_worker_finished_starts_pending_action(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        old_worker = _Worker(running=False)
        next_worker = _Worker(running=False)
        page._preset_storage_action_worker = old_worker
        page._preset_storage_action_request_id = 0
        page.create_preset_storage_action_worker = Mock(return_value=next_worker)
        page._pending_preset_storage_action = {
            "action": "move_step",
            "name": "Preset.txt",
            "display_name": "Preset",
            "rating": 0,
            "direction": 1,
            "cached_metadata": {"Preset.txt": {"display_name": "Preset"}},
            "source_kind": "",
            "source_id": "",
            "destination_kind": "",
            "destination_id": "",
            "destination_folder_key": "",
        }

        UserPresetsPageBase._on_preset_storage_action_worker_finished(page, old_worker)

        page.create_preset_storage_action_worker.assert_called_once_with(
            1,
            action="move_step",
            name="Preset.txt",
            display_name="Preset",
            rating=0,
            direction=1,
            cached_metadata={"Preset.txt": {"display_name": "Preset"}},
            source_kind="",
            source_id="",
            destination_kind="",
            destination_id="",
            destination_folder_key="",
        )
        next_worker.start.assert_called_once_with()
        self.assertIsNone(page._pending_preset_storage_action)


if __name__ == "__main__":
    unittest.main()
