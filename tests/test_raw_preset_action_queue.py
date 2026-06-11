from __future__ import annotations

from types import SimpleNamespace
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


class RawPresetActionQueueTests(unittest.TestCase):
    def test_raw_preset_action_queues_next_request_while_worker_runs(self) -> None:
        from presets.ui.common.preset_subpage_base import PresetRawEditorPage

        page = PresetRawEditorPage.__new__(PresetRawEditorPage)
        page._raw_action_runtime = _Runtime(running=True)
        page._raw_action_request_id = 1
        page._pending_raw_preset_actions = []
        page._pending_raw_preset_write_operations = []
        page.create_raw_preset_action_worker = Mock()

        PresetRawEditorPage._request_raw_preset_action(
            page,
            "duplicate",
            file_name="Default.txt",
            new_name="Default copy.txt",
        )

        page.create_raw_preset_action_worker.assert_not_called()
        self.assertEqual(
            page._pending_raw_preset_write_operations,
            [
                {
                    "kind": "action",
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
        page._pending_raw_preset_actions = []
        page._pending_raw_preset_write_operations = [
            {
                "kind": "action",
                "action": "reset",
                "payload": {"file_name": "Default.txt"},
            }
        ]
        page._cleanup_in_progress = False
        page.create_raw_preset_action_worker = Mock(return_value=worker)
        callbacks = []

        with patch(
            "presets.ui.common.preset_subpage_base.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            PresetRawEditorPage._on_raw_preset_action_worker_finished(page, SimpleNamespace(_request_id=1))

        page.create_raw_preset_action_worker.assert_not_called()
        self.assertEqual(runtime.started, [])
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page.create_raw_preset_action_worker.assert_called_once_with(
            2,
            action="reset",
            payload={"file_name": "Default.txt"},
            parent=page,
        )
        self.assertEqual(runtime.started, [worker])
        self.assertEqual(page._pending_raw_preset_write_operations, [])

    def test_raw_preset_action_result_ignored_when_next_action_is_pending(self) -> None:
        from presets.ui.common.preset_subpage_base import PresetRawEditorPage

        updated = SimpleNamespace(name="Renamed", file_name="Renamed.txt", kind="user")
        page = PresetRawEditorPage.__new__(PresetRawEditorPage)
        page._raw_action_request_id = 3
        page._pending_raw_preset_write_operations = [
            {
                "kind": "action",
                "action": "duplicate",
                "payload": {"file_name": "Default.txt"},
            }
        ]
        page._preset_name = "Default"
        page._preset_file_name = "Default.txt"
        page._preset_path = "C:/Zapret/Dev/presets/winws2/Default.txt"
        page._preset_origin = "user"
        page._notify_preset_structure_changed = Mock(
            side_effect=AssertionError("pending action must own structure changes")
        )
        page._load_file = Mock(side_effect=AssertionError("pending action must own file reload"))
        page._refresh_header = Mock()
        page._show_success = Mock()

        PresetRawEditorPage._on_raw_preset_action_finished(
            page,
            3,
            "rename",
            (updated, "C:/Zapret/Dev/presets/winws2/Renamed.txt"),
            {"new_name": "Renamed"},
        )

        self.assertEqual(page._preset_name, "Default")
        self.assertEqual(page._preset_file_name, "Default.txt")
        self.assertEqual(page._preset_path, "C:/Zapret/Dev/presets/winws2/Default.txt")
        page._notify_preset_structure_changed.assert_not_called()
        page._load_file.assert_not_called()
        page._refresh_header.assert_not_called()
        page._show_success.assert_not_called()

    def test_raw_preset_action_error_ignored_when_next_action_is_pending(self) -> None:
        from presets.ui.common.preset_subpage_base import PresetRawEditorPage

        page = PresetRawEditorPage.__new__(PresetRawEditorPage)
        page._raw_action_request_id = 3
        page._pending_raw_preset_write_operations = [
            {
                "kind": "action",
                "action": "duplicate",
                "payload": {"file_name": "Default.txt"},
            }
        ]
        page._show_error = Mock(
            side_effect=AssertionError("pending action must own the error message")
        )

        PresetRawEditorPage._on_raw_preset_action_failed(
            page,
            3,
            "rename",
            "old error",
            {"new_name": "Renamed"},
        )

        page._show_error.assert_not_called()


if __name__ == "__main__":
    unittest.main()
