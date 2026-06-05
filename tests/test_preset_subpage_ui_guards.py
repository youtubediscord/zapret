from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch


class _PlainTextEditor:
    def __init__(self, text: str = "") -> None:
        self._text = str(text)
        self.plain_text_read_calls: list[str] = []
        self.plain_text_calls: list[str] = []

    def toPlainText(self) -> str:  # noqa: N802
        self.plain_text_read_calls.append(self._text)
        return self._text

    def setPlainText(self, text: str) -> None:  # noqa: N802
        value = str(text)
        self.plain_text_calls.append(value)
        self._text = value


class _Button:
    def __init__(self, *, enabled: bool = True) -> None:
        self._enabled = bool(enabled)
        self.enabled_calls: list[bool] = []

    def isEnabled(self) -> bool:  # noqa: N802
        return self._enabled

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802
        value = bool(enabled)
        self.enabled_calls.append(value)
        self._enabled = value


class _Signal:
    def connect(self, _callback) -> None:
        pass


class _Worker:
    def __init__(self) -> None:
        self.activated = _Signal()
        self.failed = _Signal()
        self.finished = _Signal()
        self.start_calls = 0

    def start(self) -> None:
        self.start_calls += 1

    def deleteLater(self) -> None:  # noqa: N802
        pass


class _RunningRuntime:
    def isRunning(self) -> bool:  # noqa: N802
        return True

    def is_running(self) -> bool:
        return True


class PresetSubpageUiGuardTests(unittest.TestCase):
    def test_raw_preset_load_while_worker_runs_queues_latest_request(self) -> None:
        from presets.ui.common.preset_subpage_base import PresetRawEditorPage

        runtime = SimpleNamespace(
            is_running=Mock(return_value=True),
            start_qthread_worker=Mock(),
        )
        page = PresetRawEditorPage.__new__(PresetRawEditorPage)
        page._raw_load_runtime = runtime
        page._raw_load_request_id = 2
        page._raw_load_pending = False
        page._raw_load_start_scheduled = False
        page._is_loading = False
        page._preset_file_name = "Default.txt"
        page._set_footer = Mock()
        page.create_raw_preset_load_worker = Mock()

        PresetRawEditorPage._request_raw_preset_text(page)

        self.assertEqual(page._raw_load_request_id, 3)
        self.assertTrue(page._raw_load_pending)
        self.assertTrue(page._is_loading)
        page._set_footer.assert_called_once_with("Загрузка...")
        runtime.start_qthread_worker.assert_not_called()
        page.create_raw_preset_load_worker.assert_not_called()

    def test_pending_raw_preset_load_restarts_after_worker_signal(self) -> None:
        from presets.ui.common.preset_subpage_base import PresetRawEditorPage

        worker = object()
        page = PresetRawEditorPage.__new__(PresetRawEditorPage)
        page._cleanup_in_progress = False
        page._raw_load_runtime_worker = worker
        page._raw_load_pending = True
        page._raw_load_start_scheduled = False
        page._request_raw_preset_text = Mock()
        callbacks = []

        with patch(
            "presets.ui.common.preset_subpage_base.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            PresetRawEditorPage._on_raw_preset_worker_finished(page, worker)

        page._request_raw_preset_text.assert_not_called()
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        self.assertFalse(page._raw_load_pending)
        page._request_raw_preset_text.assert_called_once_with()

    def test_raw_preset_load_skips_duplicate_plain_text_update(self) -> None:
        from presets.ui.common.preset_subpage_base import PresetRawEditorPage

        page = PresetRawEditorPage.__new__(PresetRawEditorPage)
        page._raw_load_request_id = 3
        page._preset_file_name = "Default.txt"
        page._preset_name = "Default"
        page._preset_path = None
        page._preset_origin = "user"
        page._is_loading = True
        page.editor = _PlainTextEditor("--new\n--filter-tcp=443\n")
        page._set_footer = Mock()
        page._refresh_header = Mock()
        callbacks = []

        result = SimpleNamespace(
            file_name="Default.txt",
            display_name="Default",
            path="C:/Zapret/Dev/presets/winws2/Default.txt",
            origin="user",
            text="--new\n--filter-tcp=443\n",
            footer_text="Готово",
        )

        with patch(
            "presets.ui.common.preset_subpage_base.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            PresetRawEditorPage._on_raw_preset_text_loaded(page, 3, result)

        self.assertEqual(page.editor.plain_text_calls, [])
        page._set_footer.assert_not_called()
        page._refresh_header.assert_not_called()
        self.assertTrue(page._is_loading)
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        self.assertEqual(page.editor.plain_text_calls, [])
        page._set_footer.assert_called_once_with("Готово")
        page._refresh_header.assert_called_once_with()
        self.assertFalse(page._is_loading)

    def test_raw_preset_load_applies_editor_text_after_worker_signal(self) -> None:
        from presets.ui.common.preset_subpage_base import PresetRawEditorPage

        page = PresetRawEditorPage.__new__(PresetRawEditorPage)
        page._raw_load_request_id = 4
        page._cleanup_in_progress = False
        page._preset_file_name = "Default.txt"
        page._preset_name = "Default"
        page._preset_path = None
        page._preset_origin = "user"
        page._is_loading = True
        page.editor = _PlainTextEditor("")
        page._set_footer = Mock()
        page._refresh_header = Mock()
        callbacks = []

        result = SimpleNamespace(
            file_name="Default.txt",
            display_name="Default",
            path="C:/Zapret/Dev/presets/winws2/Default.txt",
            origin="user",
            text="--new\n--filter-tcp=443\n",
            footer_text="Готово",
        )

        with patch(
            "presets.ui.common.preset_subpage_base.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            PresetRawEditorPage._on_raw_preset_text_loaded(page, 4, result)

        self.assertEqual(page.editor.plain_text_calls, [])
        page._set_footer.assert_not_called()
        page._refresh_header.assert_not_called()
        self.assertTrue(page._is_loading)
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        self.assertEqual(page.editor.plain_text_calls, [result.text])
        page._set_footer.assert_called_once_with("Готово")
        page._refresh_header.assert_called_once_with()
        self.assertFalse(page._is_loading)

    def test_raw_preset_activation_skips_duplicate_button_disable(self) -> None:
        from presets.ui.common.preset_subpage_base import PresetRawEditorPage

        worker = _Worker()
        page = PresetRawEditorPage.__new__(PresetRawEditorPage)
        page._raw_activate_request_id = 0
        page._preset_file_name = "Default.txt"
        page.activateButton = _Button(enabled=False)
        page.create_raw_preset_activate_worker = Mock(return_value=worker)

        PresetRawEditorPage._request_preset_activation(page)

        self.assertEqual(page.activateButton.enabled_calls, [])
        page.create_raw_preset_activate_worker.assert_called_once_with(1, "Default.txt", page)
        self.assertEqual(worker.start_calls, 1)

    def test_raw_preset_save_while_worker_runs_defers_editor_read(self) -> None:
        from presets.ui.common.preset_subpage_base import PresetRawEditorPage

        page = PresetRawEditorPage.__new__(PresetRawEditorPage)
        page._cleanup_in_progress = False
        page._preset_path = object()
        page._preset_file_name = "Default.txt"
        page._raw_save_runtime = _RunningRuntime()
        page._pending_raw_preset_save = None
        page.editor = _PlainTextEditor("--new\n--filter-tcp=443\n")

        self.assertTrue(PresetRawEditorPage._save_file(page, publish_content_changed=True))

        self.assertEqual(page.editor.plain_text_read_calls, [])
        self.assertEqual(page._pending_raw_preset_save, ("Default.txt", None, True))

    def test_pending_raw_preset_save_restarts_after_worker_signal(self) -> None:
        from presets.ui.common.preset_subpage_base import PresetRawEditorPage

        page = PresetRawEditorPage.__new__(PresetRawEditorPage)
        page._cleanup_in_progress = False
        page._pending_raw_preset_save = ("Default.txt", None, True)
        page._after_raw_preset_save = None
        page._save_file = Mock(return_value=True)
        callbacks = []

        with patch(
            "presets.ui.common.preset_subpage_base.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            PresetRawEditorPage._on_raw_preset_save_worker_finished(page, object())

        page._save_file.assert_not_called()
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page._save_file.assert_called_once_with(publish_content_changed=True)

    def test_status_message_update_skips_runtime_toggle_render(self) -> None:
        from app.state_store import AppUiState
        from presets.ui.common.preset_subpage_base import PresetRawEditorPage

        page = PresetRawEditorPage.__new__(PresetRawEditorPage)
        page._cleanup_in_progress = False
        page._render_runtime_toggle = Mock(
            side_effect=AssertionError("status message must not repaint runtime toggle")
        )
        page._render_footer_status = Mock()

        PresetRawEditorPage._on_ui_state_changed(
            page,
            AppUiState(last_status_message="Запущено"),
            frozenset({"last_status_message"}),
        )

        page._render_runtime_toggle.assert_not_called()
        page._render_footer_status.assert_called_once()


if __name__ == "__main__":
    unittest.main()
