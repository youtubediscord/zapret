from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from presets.user_presets_action_workers import UserPresetStorageActionWorker
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


class _Runtime:
    def __init__(self, *, running: bool = False) -> None:
        self._running = running

    def is_running(self) -> bool:
        return self._running


class UserPresetStorageQueueTests(unittest.TestCase):
    def test_move_step_worker_adds_destination_context_from_result(self) -> None:
        completed = []
        worker = UserPresetStorageActionWorker(
            7,
            toggle_preset_pin=Mock(),
            set_preset_rating=Mock(),
            move_preset_by_step=Mock(
                return_value={
                    "ok": True,
                    "destination_kind": "preset_after",
                    "destination_id": "Other.txt",
                    "destination_folder_key": "common",
                }
            ),
            move_preset_on_drop=Mock(),
            load_folder_state=lambda: {"folders": {}, "items": {}},
            action="move_step",
            name="Preset.txt",
            direction=1,
        )
        worker.completed.connect(lambda request_id, action, result, context: completed.append((request_id, action, result, context)))

        worker.run()

        self.assertEqual(len(completed), 1)
        request_id, action, result, context = completed[0]
        self.assertEqual(request_id, 7)
        self.assertEqual(action, "move_step")
        self.assertTrue(result)
        self.assertEqual(context["destination_kind"], "preset_after")
        self.assertEqual(context["destination_id"], "Other.txt")
        self.assertEqual(context["destination_folder_key"], "common")

    def test_storage_action_queues_pending_actions_while_worker_runs(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_storage_action_runtime = _Runtime(running=True)
        page._pending_preset_storage_actions = []

        UserPresetsPageBase._request_preset_storage_action(
            page,
            "rating",
            name="Preset.txt",
            display_name="Preset",
            rating=8,
        )
        UserPresetsPageBase._request_preset_storage_action(
            page,
            "move_step",
            name="Second.txt",
            display_name="Second",
            direction=1,
        )

        self.assertEqual(
            page._pending_preset_storage_actions,
            [
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
                {
                    "action": "move_step",
                    "name": "Second.txt",
                    "display_name": "Second",
                    "rating": 0,
                    "direction": 1,
                    "cached_metadata": None,
                    "source_kind": "",
                    "source_id": "",
                    "destination_kind": "",
                    "destination_id": "",
                    "destination_folder_key": "",
                },
            ],
        )

    def test_rating_action_queue_keeps_latest_rating_for_same_preset(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_storage_action_runtime = _Runtime(running=True)
        page._pending_preset_write_actions = []
        page._pending_preset_storage_actions = []

        UserPresetsPageBase._request_preset_storage_action(
            page,
            "rating",
            name="Preset.txt",
            display_name="Preset",
            rating=3,
        )
        UserPresetsPageBase._request_preset_storage_action(
            page,
            "rating",
            name="Preset.txt",
            display_name="Preset",
            rating=9,
        )

        self.assertEqual(
            page._pending_preset_storage_actions,
            [
                {
                    "action": "rating",
                    "name": "Preset.txt",
                    "display_name": "Preset",
                    "rating": 9,
                    "direction": 0,
                    "cached_metadata": None,
                    "source_kind": "",
                    "source_id": "",
                    "destination_kind": "",
                    "destination_id": "",
                    "destination_folder_key": "",
                },
            ],
        )
        self.assertEqual(
            [
                (operation["kind"], operation["action"], operation["name"], operation["rating"])
                for operation in page._pending_preset_write_actions
            ],
            [("storage", "rating", "Preset.txt", 9)],
        )

    def test_storage_action_worker_finished_starts_pending_action(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        old_worker = _Worker(running=False)
        old_worker._request_id = 0
        next_worker = _Worker(running=False)
        page._preset_storage_action_request_id = 0
        page.create_preset_storage_action_worker = Mock(return_value=next_worker)
        page._pending_preset_storage_actions = [
            {
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
        ]

        callbacks = []
        with patch(
            "presets.ui.common.user_presets_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            UserPresetsPageBase._on_preset_storage_action_worker_finished(page, old_worker)

        page.create_preset_storage_action_worker.assert_not_called()
        next_worker.start.assert_not_called()
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

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
        self.assertEqual(page._pending_preset_storage_actions, [])

    def test_storage_action_error_ignored_when_next_write_is_pending(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_storage_action_request_id = 4
        page._pending_preset_write_actions = [
            {
                "kind": "storage",
                "action": "rating",
                "name": "Preset.txt",
                "display_name": "Preset",
                "rating": 9,
            }
        ]
        page._pending_preset_storage_actions = [
            {
                "action": "rating",
                "name": "Preset.txt",
                "display_name": "Preset",
                "rating": 9,
            }
        ]

        with patch("presets.ui.common.user_presets_page.log") as log_mock:
            UserPresetsPageBase._on_preset_storage_action_failed(page, 4, "rating", "old error", {})

        log_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
