from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from presets.ui.common.user_presets_page import UserPresetsPageBase


class _Signal:
    def connect(self, _callback) -> None:
        return None


class _Worker:
    completed = _Signal()
    failed = _Signal()
    finished = _Signal()

    def __init__(self) -> None:
        self.start = Mock()
        self.deleteLater = Mock()


class _Runtime:
    def __init__(self, *, running: bool = False) -> None:
        self._running = bool(running)

    def is_running(self) -> bool:
        return self._running

    def start_qthread_worker(self, *, worker_factory, **_kwargs):
        worker = worker_factory(0)
        worker.start()
        return 0, worker


class _ActivationWorker(_Worker):
    activated = _Signal()


class UserPresetWriteSerializationTests(unittest.TestCase):
    def test_storage_action_waits_while_item_action_worker_runs(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_item_action_runtime = _Runtime(running=True)
        page._preset_storage_action_runtime = _Runtime(running=False)
        page._pending_preset_write_actions = []
        page._pending_preset_storage_actions = []
        page._preset_storage_action_request_id = 0
        page.create_preset_storage_action_worker = Mock(return_value=_Worker())

        UserPresetsPageBase._request_preset_storage_action(
            page,
            "rating",
            name="Preset.txt",
            display_name="Preset",
            rating=7,
        )

        page.create_preset_storage_action_worker.assert_not_called()
        self.assertEqual(
            page._pending_preset_write_actions,
            [
                {
                    "kind": "storage",
                    "action": "rating",
                    "name": "Preset.txt",
                    "display_name": "Preset",
                    "rating": 7,
                    "direction": 0,
                    "cached_metadata": None,
                    "source_kind": "",
                    "source_id": "",
                    "destination_kind": "",
                    "destination_id": "",
                    "destination_folder_key": "",
                    "file_name": "",
                    "file_path": "",
                }
            ],
        )

    def test_storage_action_waits_while_next_write_start_is_scheduled(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_write_action_start_scheduled = True
        page._preset_item_action_runtime = _Runtime(running=False)
        page._preset_storage_action_runtime = _Runtime(running=False)
        page._pending_preset_write_actions = []
        page._pending_preset_storage_actions = []
        page._preset_storage_action_request_id = 0
        page.create_preset_storage_action_worker = Mock(return_value=_Worker())

        UserPresetsPageBase._request_preset_storage_action(
            page,
            "rating",
            name="Preset.txt",
            display_name="Preset",
            rating=7,
        )

        page.create_preset_storage_action_worker.assert_not_called()
        self.assertEqual(page._pending_preset_write_actions[0]["kind"], "storage")
        self.assertEqual(page._pending_preset_storage_actions[0]["action"], "rating")

    def test_item_action_waits_while_storage_action_worker_runs(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_item_action_runtime = _Runtime(running=False)
        page._preset_storage_action_runtime = _Runtime(running=True)
        page._pending_preset_write_actions = []
        page._preset_item_action_pending = []
        page._preset_item_action_request_id = 0
        page.create_preset_item_action_worker = Mock(return_value=_Worker())

        UserPresetsPageBase._request_preset_item_action(
            page,
            "delete",
            file_name="Preset.txt",
            display_name="Preset",
        )

        page.create_preset_item_action_worker.assert_not_called()
        self.assertEqual(
            page._pending_preset_write_actions,
            [
                {
                    "kind": "item",
                    "action": "delete",
                    "name": "",
                    "display_name": "Preset",
                    "rating": 0,
                    "direction": 0,
                    "cached_metadata": None,
                    "source_kind": "",
                    "source_id": "",
                    "destination_kind": "",
                    "destination_id": "",
                    "destination_folder_key": "",
                    "file_name": "Preset.txt",
                    "file_path": "",
                }
            ],
        )

    def test_activation_waits_while_item_action_worker_runs(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_item_action_runtime = _Runtime(running=True)
        page._preset_storage_action_runtime = _Runtime(running=False)
        page._preset_activate_runtime = _Runtime(running=False)
        page._pending_preset_write_actions = []
        page._pending_preset_activation = None
        page._restore_preset_activation_marker_file_name = ""
        page._preset_activate_request_id = 0
        page._runtime_service = Mock()
        page.create_preset_activate_worker = Mock(return_value=_ActivationWorker())

        UserPresetsPageBase._request_preset_activation(page, "Next.txt", "Next")

        page.create_preset_activate_worker.assert_not_called()
        page._runtime_service.apply_active_preset_marker_for_file.assert_not_called()
        self.assertEqual(
            page._pending_preset_write_actions,
            [
                {
                    "kind": "activate",
                    "action": "",
                    "name": "",
                    "display_name": "Next",
                    "rating": 0,
                    "direction": 0,
                    "cached_metadata": None,
                    "source_kind": "",
                    "source_id": "",
                    "destination_kind": "",
                    "destination_id": "",
                    "destination_folder_key": "",
                    "file_name": "Next.txt",
                    "file_path": "",
                }
            ],
        )

        page._preset_item_action_runtime._running = False
        callbacks = []
        with patch(
            "presets.ui.common.user_presets_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            UserPresetsPageBase._on_preset_item_action_worker_finished(page, object())

        page.create_preset_activate_worker.assert_not_called()
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page.create_preset_activate_worker.assert_called_once_with(
            1,
            file_name="Next.txt",
            display_name="Next",
        )
        page._runtime_service.apply_active_preset_marker_for_file.assert_called_once_with("Next.txt")

    def test_scheduled_activation_uses_latest_request_before_worker_starts(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_activate_runtime = _Runtime(running=False)
        page._preset_item_action_runtime = _Runtime(running=False)
        page._preset_bulk_action_runtime = _Runtime(running=False)
        page._preset_edit_action_runtime = _Runtime(running=False)
        page._preset_storage_action_runtime = _Runtime(running=False)
        page._preset_activate_request_id = 0
        page._pending_preset_activation = None
        page._pending_preset_write_actions = []
        page._restore_preset_activation_marker_file_name = ""
        page._runtime_service = Mock()
        page.create_preset_activate_worker = Mock(return_value=_ActivationWorker())
        callbacks = []

        with patch(
            "presets.ui.common.user_presets_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            UserPresetsPageBase._schedule_preset_write_action_start(
                page,
                {
                    "kind": "activate",
                    "file_name": "Old.txt",
                    "display_name": "Old",
                },
            )
            UserPresetsPageBase._request_preset_activation(page, "Latest.txt", "Latest")

        page.create_preset_activate_worker.assert_not_called()
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page.create_preset_activate_worker.assert_called_once_with(
            1,
            file_name="Latest.txt",
            display_name="Latest",
        )
        page._runtime_service.apply_active_preset_marker_for_file.assert_called_once_with("Latest.txt")
        self.assertEqual(page._pending_preset_write_actions, [])
        self.assertIsNone(page._pending_preset_activation)

    def test_edit_action_waits_while_activation_worker_runs(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_activate_runtime = _Runtime(running=True)
        page._preset_item_action_runtime = _Runtime(running=False)
        page._preset_bulk_action_runtime = _Runtime(running=False)
        page._preset_edit_action_runtime = _Runtime(running=False)
        page._preset_storage_action_runtime = _Runtime(running=False)
        page._pending_preset_write_actions = []
        page._preset_edit_action_pending = []
        page._preset_edit_action_request_id = 0
        page.create_preset_edit_action_worker = Mock(return_value=_Worker())

        UserPresetsPageBase._request_preset_edit_action(
            page,
            "rename",
            current_name="Old.txt",
            new_name="New.txt",
        )

        page.create_preset_edit_action_worker.assert_not_called()
        self.assertEqual(page._pending_preset_write_actions[0]["kind"], "edit")

        page._preset_activate_runtime._running = False
        callbacks = []
        with patch(
            "presets.ui.common.user_presets_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            UserPresetsPageBase._on_preset_activate_worker_finished(page, object())

        page.create_preset_edit_action_worker.assert_not_called()
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page.create_preset_edit_action_worker.assert_called_once_with(
            1,
            action="rename",
            name="",
            current_name="Old.txt",
            new_name="New.txt",
            from_current=False,
        )

    def test_bulk_action_waits_while_edit_action_worker_runs(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_activate_runtime = _Runtime(running=False)
        page._preset_item_action_runtime = _Runtime(running=False)
        page._preset_bulk_action_runtime = _Runtime(running=False)
        page._preset_edit_action_runtime = _Runtime(running=True)
        page._preset_storage_action_runtime = _Runtime(running=False)
        page._pending_preset_write_actions = []
        page._preset_bulk_action_pending = []
        page._preset_bulk_action_request_id = 0
        page._preset_bulk_action_kind = ""
        page.create_preset_bulk_action_worker = Mock(return_value=_Worker())

        self.assertTrue(
            UserPresetsPageBase._request_preset_bulk_action(
                page,
                "import",
                file_path="C:/Temp/Preset.txt",
            )
        )

        page.create_preset_bulk_action_worker.assert_not_called()
        self.assertEqual(page._pending_preset_write_actions[0]["kind"], "bulk")

        page._preset_edit_action_runtime._running = False
        callbacks = []
        with patch(
            "presets.ui.common.user_presets_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            UserPresetsPageBase._on_preset_edit_action_worker_finished(page, object())

        page.create_preset_bulk_action_worker.assert_not_called()
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page.create_preset_bulk_action_worker.assert_called_once_with(
            1,
            action="import",
            file_path="C:/Temp/Preset.txt",
        )

    def test_legacy_pending_edit_action_restarts_later_after_worker_finished(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_activate_runtime = _Runtime(running=False)
        page._preset_item_action_runtime = _Runtime(running=False)
        page._preset_bulk_action_runtime = _Runtime(running=False)
        page._preset_edit_action_runtime = _Runtime(running=False)
        page._preset_storage_action_runtime = _Runtime(running=False)
        page._pending_preset_write_actions = []
        page._preset_edit_action_pending = [
            {
                "action": "rename",
                "name": "Old.txt",
                "current_name": "Old.txt",
                "new_name": "New.txt",
                "from_current": False,
            }
        ]
        page._preset_edit_action_request_id = 0
        page.create_preset_edit_action_worker = Mock(return_value=_Worker())
        callbacks = []

        with patch(
            "presets.ui.common.user_presets_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            UserPresetsPageBase._on_preset_edit_action_worker_finished(page, object())

        page.create_preset_edit_action_worker.assert_not_called()
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page.create_preset_edit_action_worker.assert_called_once_with(
            1,
            action="rename",
            name="Old.txt",
            current_name="Old.txt",
            new_name="New.txt",
            from_current=False,
        )

    def test_legacy_pending_bulk_action_restarts_later_after_worker_finished(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_activate_runtime = _Runtime(running=False)
        page._preset_item_action_runtime = _Runtime(running=False)
        page._preset_bulk_action_runtime = _Runtime(running=False)
        page._preset_edit_action_runtime = _Runtime(running=False)
        page._preset_storage_action_runtime = _Runtime(running=False)
        page._pending_preset_write_actions = []
        page._preset_bulk_action_pending = [{"action": "import", "file_path": "C:/Temp/Preset.txt"}]
        page._preset_bulk_action_request_id = 0
        page._preset_bulk_action_kind = ""
        page._bulk_reset_running = False
        page.create_preset_bulk_action_worker = Mock(return_value=_Worker())
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
            1,
            action="import",
            file_path="C:/Temp/Preset.txt",
        )

    def test_cleanup_clears_pending_write_actions(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._pending_preset_activation = ("Preset.txt", "Preset")
        page._restore_preset_activation_marker_file_name = "Old.txt"
        page._pending_preset_write_actions = [{"kind": "item", "action": "delete"}]
        page._pending_preset_storage_actions = [{"action": "rating"}]
        page._preset_item_action_pending = [{"action": "delete"}]
        page._preset_folder_action_pending = []
        page._preset_open_folder_pending = True
        page._preset_bulk_action_kind = "reset_all"
        page._bulk_reset_running = True
        for attr in (
            "_preset_activate_request_id",
            "_preset_item_action_request_id",
            "_preset_bulk_action_request_id",
            "_preset_edit_action_request_id",
            "_preset_storage_action_request_id",
            "_preset_folder_action_request_id",
            "_preset_open_folder_request_id",
            "_preset_link_action_request_id",
        ):
            setattr(page, attr, 0)

        UserPresetsPageBase._stop_action_workers_for_cleanup(page)

        self.assertEqual(page._pending_preset_write_actions, [])
        self.assertEqual(page._pending_preset_storage_actions, [])
        self.assertEqual(page._preset_item_action_pending, [])


if __name__ == "__main__":
    unittest.main()
