from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from presets.ui.common.preset_subpage_base import PresetRawEditorPage


class _Runtime:
    def __init__(self, *, running: bool = False) -> None:
        self.running = running
        self.started: list[object] = []

    def is_running(self) -> bool:
        return self.running

    def start_qthread_worker(self, *, worker_factory, **_kwargs):
        worker = worker_factory(0)
        self.started.append(worker)
        return 0, worker


class RawPresetWriteSerializationTests(unittest.TestCase):
    def test_raw_preset_action_waits_while_activation_runs(self) -> None:
        worker = object()
        page = PresetRawEditorPage.__new__(PresetRawEditorPage)
        page._raw_activate_runtime = _Runtime(running=True)
        page._raw_action_runtime = _Runtime(running=False)
        page._raw_action_request_id = 0
        page._pending_raw_preset_activation = ""
        page._pending_raw_preset_actions = []
        page._pending_raw_preset_write_operations = []
        page.create_raw_preset_action_worker = Mock(return_value=worker)

        PresetRawEditorPage._request_raw_preset_action(page, "export", file_name="Default.txt")

        page.create_raw_preset_action_worker.assert_not_called()
        self.assertEqual(
            page._pending_raw_preset_write_operations,
            [
                {
                    "kind": "action",
                    "action": "export",
                    "payload": {"file_name": "Default.txt"},
                }
            ],
        )

        page._raw_activate_runtime.running = False
        callbacks = []
        with patch(
            "presets.ui.common.preset_subpage_base.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            PresetRawEditorPage._on_preset_activation_worker_finished(page, object())

        page.create_raw_preset_action_worker.assert_not_called()
        self.assertEqual(page._raw_action_runtime.started, [])
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page.create_raw_preset_action_worker.assert_called_once_with(
            1,
            action="export",
            payload={"file_name": "Default.txt"},
            parent=page,
        )
        self.assertEqual(page._raw_action_runtime.started, [worker])

    def test_raw_preset_activation_waits_while_action_runs(self) -> None:
        worker = object()
        page = PresetRawEditorPage.__new__(PresetRawEditorPage)
        page._raw_action_runtime = _Runtime(running=True)
        page._raw_activate_runtime = _Runtime(running=False)
        page._raw_activate_request_id = 0
        page._preset_file_name = "Next.txt"
        page._pending_raw_preset_activation = ""
        page._pending_raw_preset_actions = []
        page._pending_raw_preset_write_operations = []
        page.activateButton = None
        page.create_raw_preset_activate_worker = Mock(return_value=worker)

        PresetRawEditorPage._request_preset_activation(page)

        page.create_raw_preset_activate_worker.assert_not_called()
        self.assertEqual(
            page._pending_raw_preset_write_operations,
            [{"kind": "activate", "file_name": "Next.txt"}],
        )

        page._raw_action_runtime.running = False
        callbacks = []
        with patch(
            "presets.ui.common.preset_subpage_base.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            PresetRawEditorPage._on_raw_preset_action_worker_finished(page, object())

        page.create_raw_preset_activate_worker.assert_not_called()
        self.assertEqual(page._raw_activate_runtime.started, [])
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page.create_raw_preset_activate_worker.assert_called_once_with(1, "Next.txt", page)
        self.assertEqual(page._raw_activate_runtime.started, [worker])

    def test_stale_raw_preset_action_worker_finished_does_not_start_pending_activation(self) -> None:
        old_worker = object()
        current_worker = object()
        page = PresetRawEditorPage.__new__(PresetRawEditorPage)
        page._raw_action_runtime_worker = current_worker
        page._raw_action_runtime = _Runtime(running=False)
        page._raw_activate_runtime = _Runtime(running=False)
        page._raw_save_runtime = _Runtime(running=False)
        page._raw_preset_write_operation_start_scheduled = False
        page._raw_preset_save_start_scheduled = False
        page._raw_preset_activation_start_scheduled = False
        page._cleanup_in_progress = False
        page._pending_raw_preset_write_operations = [{"kind": "activate", "file_name": "Next.txt"}]
        page.create_raw_preset_activate_worker = Mock()
        callbacks = []

        with patch(
            "presets.ui.common.preset_subpage_base.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            PresetRawEditorPage._on_raw_preset_action_worker_finished(page, old_worker)

        self.assertIs(page._raw_action_runtime_worker, current_worker)
        self.assertEqual(callbacks, [])
        page.create_raw_preset_activate_worker.assert_not_called()
        self.assertEqual(
            page._pending_raw_preset_write_operations,
            [{"kind": "activate", "file_name": "Next.txt"}],
        )

    def test_cleared_raw_preset_action_worker_finished_does_not_start_pending_activation(self) -> None:
        old_worker = object()
        page = PresetRawEditorPage.__new__(PresetRawEditorPage)
        page._raw_action_runtime_worker = None
        page._pending_raw_preset_write_operations = [{"kind": "activate", "file_name": "Next.txt"}]
        page.create_raw_preset_activate_worker = Mock()
        callbacks = []

        with patch(
            "presets.ui.common.preset_subpage_base.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            PresetRawEditorPage._on_raw_preset_action_worker_finished(page, old_worker)

        self.assertIsNone(page._raw_action_runtime_worker)
        self.assertEqual(callbacks, [])
        page.create_raw_preset_activate_worker.assert_not_called()
        self.assertEqual(
            page._pending_raw_preset_write_operations,
            [{"kind": "activate", "file_name": "Next.txt"}],
        )

    def test_duplicate_raw_preset_action_is_not_replayed_from_old_queue(self) -> None:
        worker = object()
        page = PresetRawEditorPage.__new__(PresetRawEditorPage)
        page._raw_action_runtime = _Runtime(running=True)
        page._raw_activate_runtime = _Runtime(running=False)
        page._raw_action_request_id = 0
        page._pending_raw_preset_activation = ""
        page._pending_raw_preset_actions = []
        page._pending_raw_preset_write_operations = []
        page._cleanup_in_progress = False
        page.create_raw_preset_action_worker = Mock(return_value=worker)

        for _ in range(2):
            PresetRawEditorPage._request_raw_preset_action(
                page,
                "export",
                file_name="Default.txt",
            )

        self.assertEqual(
            page._pending_raw_preset_write_operations,
            [
                {
                    "kind": "action",
                    "action": "export",
                    "payload": {"file_name": "Default.txt"},
                }
            ],
        )
        self.assertEqual(
            page._pending_raw_preset_actions,
            [],
        )

        page._raw_action_runtime.running = False
        callbacks = []
        with patch(
            "presets.ui.common.preset_subpage_base.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            PresetRawEditorPage._on_raw_preset_action_worker_finished(page, object())
            PresetRawEditorPage._on_raw_preset_action_worker_finished(page, object())

        page.create_raw_preset_action_worker.assert_not_called()
        self.assertEqual(page._raw_action_runtime.started, [])
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page.create_raw_preset_action_worker.assert_called_once_with(
            1,
            action="export",
            payload={"file_name": "Default.txt"},
            parent=page,
        )
        self.assertEqual(page._raw_action_runtime.started, [worker])

    def test_different_raw_preset_actions_are_kept_in_order(self) -> None:
        page = PresetRawEditorPage.__new__(PresetRawEditorPage)
        page._raw_action_runtime = _Runtime(running=True)
        page._raw_activate_runtime = _Runtime(running=False)
        page._pending_raw_preset_activation = ""
        page._pending_raw_preset_actions = []
        page._pending_raw_preset_write_operations = []
        page.create_raw_preset_action_worker = Mock()

        PresetRawEditorPage._request_raw_preset_action(
            page,
            "export",
            file_name="Default.txt",
        )
        PresetRawEditorPage._request_raw_preset_action(
            page,
            "delete",
            file_name="Default.txt",
        )

        page.create_raw_preset_action_worker.assert_not_called()
        self.assertEqual(
            page._pending_raw_preset_write_operations,
            [
                {
                    "kind": "action",
                    "action": "export",
                    "payload": {"file_name": "Default.txt"},
                },
                {
                    "kind": "action",
                    "action": "delete",
                    "payload": {"file_name": "Default.txt"},
                },
            ],
        )

    def test_raw_preset_action_waits_while_save_runs(self) -> None:
        page = PresetRawEditorPage.__new__(PresetRawEditorPage)
        page._raw_save_runtime = _Runtime(running=True)
        page._raw_action_runtime = _Runtime(running=False)
        page._raw_activate_runtime = _Runtime(running=False)
        page._pending_raw_preset_write_operations = []
        page.create_raw_preset_action_worker = Mock()

        PresetRawEditorPage._request_raw_preset_action(
            page,
            "rename",
            file_name="Default.txt",
            new_name="Default copy.txt",
        )

        page.create_raw_preset_action_worker.assert_not_called()
        self.assertEqual(
            page._pending_raw_preset_write_operations,
            [
                {
                    "kind": "action",
                    "action": "rename",
                    "payload": {
                        "file_name": "Default.txt",
                        "new_name": "Default copy.txt",
                    },
                }
            ],
        )

    def test_raw_preset_action_waits_while_next_write_start_is_scheduled(self) -> None:
        page = PresetRawEditorPage.__new__(PresetRawEditorPage)
        page._raw_preset_write_operation_start_scheduled = True
        page._raw_save_runtime = _Runtime(running=False)
        page._raw_action_runtime = _Runtime(running=False)
        page._raw_activate_runtime = _Runtime(running=False)
        page._pending_raw_preset_write_operations = []
        page._raw_action_request_id = 0
        page.create_raw_preset_action_worker = Mock()

        PresetRawEditorPage._request_raw_preset_action(
            page,
            "rename",
            file_name="Default.txt",
            new_name="Default copy.txt",
        )

        page.create_raw_preset_action_worker.assert_not_called()
        self.assertEqual(
            page._pending_raw_preset_write_operations,
            [
                {
                    "kind": "action",
                    "action": "rename",
                    "payload": {
                        "file_name": "Default.txt",
                        "new_name": "Default copy.txt",
                    },
                }
            ],
        )

    def test_raw_preset_save_waits_while_action_runs(self) -> None:
        page = PresetRawEditorPage.__new__(PresetRawEditorPage)
        page._raw_save_runtime = _Runtime(running=False)
        page._raw_action_runtime = _Runtime(running=True)
        page._raw_activate_runtime = _Runtime(running=False)
        page._pending_raw_preset_save = None
        page._pending_raw_preset_write_operations = []
        page._raw_save_request_id = 0
        page._set_footer = Mock()
        page.create_raw_preset_save_worker = Mock()

        self.assertTrue(
            PresetRawEditorPage._request_raw_preset_save(
                page,
                file_name="Default.txt",
                source_text="--new\n",
                publish_content_changed=True,
            )
        )

        page.create_raw_preset_save_worker.assert_not_called()
        self.assertEqual(
            page._pending_raw_preset_write_operations,
            [
                {
                    "kind": "save",
                    "file_name": "Default.txt",
                    "source_text": "--new\n",
                    "publish_content_changed": True,
                }
            ],
        )

    def test_scheduled_raw_preset_save_uses_latest_text_before_worker_starts(self) -> None:
        worker = object()
        page = PresetRawEditorPage.__new__(PresetRawEditorPage)
        page._raw_save_runtime = _Runtime(running=False)
        page._raw_action_runtime = _Runtime(running=False)
        page._raw_activate_runtime = _Runtime(running=False)
        page._raw_save_request_id = 0
        page._pending_raw_preset_save = ("Default.txt", "--new\nold", False)
        page._pending_raw_preset_write_operations = []
        page._after_raw_preset_save = None
        page._cleanup_in_progress = False
        page._set_footer = Mock()
        page.create_raw_preset_save_worker = Mock(return_value=worker)
        callbacks = []

        with patch(
            "presets.ui.common.preset_subpage_base.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            PresetRawEditorPage._on_raw_preset_save_worker_finished(page, object())
            PresetRawEditorPage._request_raw_preset_save(
                page,
                file_name="Default.txt",
                source_text="--new\nlatest",
                publish_content_changed=True,
            )

        page.create_raw_preset_save_worker.assert_not_called()
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page.create_raw_preset_save_worker.assert_called_once_with(
            1,
            file_name="Default.txt",
            source_text="--new\nlatest",
            publish_content_changed=True,
            parent=page,
        )
        self.assertEqual(page._pending_raw_preset_save, None)
        self.assertEqual(page._pending_raw_preset_write_operations, [])


if __name__ == "__main__":
    unittest.main()
