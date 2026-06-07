from __future__ import annotations

import unittest
from unittest.mock import Mock


class _RawTextEditor:
    def __init__(self, text: str) -> None:
        self._text = str(text)
        self.read_calls = 0

    def toPlainText(self) -> str:  # noqa: N802
        self.read_calls += 1
        return self._text


class _Runtime:
    def __init__(self, *, running: bool) -> None:
        self.running = bool(running)

    def is_running(self) -> bool:
        return self.running


class _StartRuntime(_Runtime):
    def __init__(self) -> None:
        super().__init__(running=False)

    def start_qthread_worker(self, *, worker_factory, **_kwargs):
        worker = worker_factory(0)
        return 0, worker


class RawPresetEditorReadDeferTests(unittest.TestCase):
    def test_raw_preset_save_request_defers_editor_read_until_worker_start(self) -> None:
        from presets.ui.common.preset_subpage_base import PresetRawEditorPage

        page = PresetRawEditorPage.__new__(PresetRawEditorPage)
        page._cleanup_in_progress = False
        page._preset_path = "C:/Zapret/Dev/presets/winws2/Default.txt"
        page._preset_file_name = "Default.txt"
        page._raw_editor_text_snapshot = None
        page.editor = _RawTextEditor("--new\n--filter-tcp=443\n")
        page._raw_save_runtime = _Runtime(running=False)
        page._raw_activate_runtime = _Runtime(running=False)
        page._raw_action_runtime = _Runtime(running=False)
        page._raw_preset_save_start_scheduled = False
        page._raw_preset_activation_start_scheduled = False
        page._raw_preset_write_operation_start_scheduled = False
        page._pending_raw_preset_save = None
        page._pending_raw_preset_write_operations = []
        page._start_raw_preset_save_worker = Mock()

        self.assertTrue(PresetRawEditorPage._save_file(page, publish_content_changed=True))

        self.assertEqual(page.editor.read_calls, 0)
        page._start_raw_preset_save_worker.assert_called_once_with(
            file_name="Default.txt",
            source_text=None,
            publish_content_changed=True,
        )

    def test_raw_preset_save_while_action_runs_defers_editor_read(self) -> None:
        from presets.ui.common.preset_subpage_base import PresetRawEditorPage

        page = PresetRawEditorPage.__new__(PresetRawEditorPage)
        page._cleanup_in_progress = False
        page._preset_path = "C:/Zapret/Dev/presets/winws2/Default.txt"
        page._preset_file_name = "Default.txt"
        page._raw_editor_text_snapshot = None
        page.editor = _RawTextEditor("--new\n--filter-tcp=443\n")
        page._raw_save_runtime = _Runtime(running=False)
        page._raw_activate_runtime = _Runtime(running=False)
        page._raw_action_runtime = _Runtime(running=True)
        page._raw_preset_save_start_scheduled = False
        page._raw_preset_activation_start_scheduled = False
        page._raw_preset_write_operation_start_scheduled = False
        page._pending_raw_preset_save = None
        page._pending_raw_preset_write_operations = []
        page._raw_save_request_id = 0
        page._raw_save_succeeded = True
        page._set_footer = Mock()
        page.create_raw_preset_save_worker = Mock(return_value=object())

        self.assertTrue(PresetRawEditorPage._save_file(page, publish_content_changed=True))

        self.assertEqual(page.editor.read_calls, 0)
        page.create_raw_preset_save_worker.assert_not_called()
        self.assertEqual(
            page._pending_raw_preset_write_operations,
            [
                {
                    "kind": "save",
                    "file_name": "Default.txt",
                    "source_text": None,
                    "publish_content_changed": True,
                }
            ],
        )

        page._raw_action_runtime.running = False
        page._raw_save_runtime = _StartRuntime()

        self.assertTrue(PresetRawEditorPage._start_next_raw_preset_write_operation(page))

        self.assertEqual(page.editor.read_calls, 1)
        page.create_raw_preset_save_worker.assert_called_once_with(
            1,
            file_name="Default.txt",
            source_text="--new\n--filter-tcp=443\n",
            publish_content_changed=True,
            parent=page,
        )

    def test_queued_raw_preset_save_defers_editor_read_until_worker_start(self) -> None:
        from presets.ui.common.preset_subpage_base import PresetRawEditorPage

        page = PresetRawEditorPage.__new__(PresetRawEditorPage)
        page._cleanup_in_progress = False
        page._raw_save_runtime = _Runtime(running=False)
        page._raw_activate_runtime = _Runtime(running=False)
        page._raw_action_runtime = _Runtime(running=False)
        page._raw_preset_save_start_scheduled = False
        page._raw_preset_activation_start_scheduled = False
        page._raw_preset_write_operation_start_scheduled = False
        page._raw_editor_text_snapshot = None
        page.editor = _RawTextEditor("--new\n--filter-tcp=443\n")
        page._pending_raw_preset_write_operations = [
            {
                "kind": "save",
                "file_name": "Default.txt",
                "source_text": None,
                "publish_content_changed": True,
            }
        ]
        page._start_raw_preset_save_worker = Mock()

        self.assertTrue(PresetRawEditorPage._start_next_raw_preset_write_operation(page))

        self.assertEqual(page.editor.read_calls, 0)
        page._start_raw_preset_save_worker.assert_called_once_with(
            file_name="Default.txt",
            source_text=None,
            publish_content_changed=True,
        )


if __name__ == "__main__":
    unittest.main()
