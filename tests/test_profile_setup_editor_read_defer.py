from __future__ import annotations

import unittest
from unittest.mock import Mock, patch


class _RawTextEditor:
    def __init__(self, text: str) -> None:
        self._text = str(text)
        self.read_calls = 0

    def toPlainText(self) -> str:  # noqa: N802
        self.read_calls += 1
        return self._text

    def isReadOnly(self) -> bool:  # noqa: N802
        return False


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


class ProfileSetupEditorReadDeferTests(unittest.TestCase):
    def test_raw_profile_save_request_defers_editor_read_until_worker_start(self) -> None:
        from profile.ui.profile_setup_page import ProfileSetupPageBase

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._cleanup_in_progress = False
        page._profile_key = "profile-1"
        page._raw_profile_text = _RawTextEditor("--new\n--lua-desync=latest")
        page._raw_profile_save_runtime = _Runtime(running=False)
        page._raw_profile_save_start_scheduled = False
        page._pending_raw_profile_save = None
        page._pending_profile_setup_write_operations = []
        page._profile_setup_write_operation_start_scheduled = False
        page._list_file_save_runtime = _Runtime(running=False)
        page._settings_save_runtime = _Runtime(running=False)
        page._enabled_save_runtime = _Runtime(running=False)
        page._user_profile_update_runtime = _Runtime(running=False)
        page._user_profile_delete_runtime = _Runtime(running=False)
        page._strategy_apply_runtime = _Runtime(running=False)
        page._strategy_feedback_save_runtime = _Runtime(running=False)
        page._raw_profile_save_button = Mock()
        page._start_raw_profile_save_worker = Mock()

        ProfileSetupPageBase._request_raw_profile_save(page, "profile-1", None)

        self.assertEqual(page._raw_profile_text.read_calls, 0)
        page._start_raw_profile_save_worker.assert_called_once_with("profile-1", None)

    def test_list_file_validation_while_worker_runs_defers_editor_read(self) -> None:
        from profile.ui.profile_setup_page import ProfileSetupPageBase

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._loading = False
        page._cleanup_in_progress = False
        page._list_file_kind = "hostlist"
        page._list_file_text = _RawTextEditor("latest.example")
        page._list_file_validation_timer = None
        page._list_file_validation_runtime = _Runtime(running=True)
        page._list_file_validation_request_id = 0
        page._list_file_validation_start_scheduled = False
        page._pending_list_file_validation = None
        page._list_file_status_label = Mock()
        page.create_profile_list_file_validation_worker = Mock(return_value=object())

        ProfileSetupPageBase._on_list_file_text_changed(page)

        self.assertEqual(page._list_file_text.read_calls, 0)
        self.assertEqual(page._pending_list_file_validation, {"kind": "hostlist", "text": None})
        page.create_profile_list_file_validation_worker.assert_not_called()

        page._list_file_validation_runtime.running = False
        callbacks = []
        with patch(
            "profile.ui.profile_setup_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            ProfileSetupPageBase._on_list_file_validation_worker_finished(page, object())

        self.assertEqual(page._list_file_text.read_calls, 0)
        self.assertEqual(len(callbacks), 1)

        page._list_file_validation_runtime = _StartRuntime()
        callbacks[0]()

        self.assertEqual(page._list_file_text.read_calls, 1)
        page.create_profile_list_file_validation_worker.assert_called_once_with(
            1,
            kind="hostlist",
            text="latest.example",
            parent=page,
        )

    def test_raw_profile_save_while_worker_runs_defers_editor_read(self) -> None:
        from profile.ui.profile_setup_page import ProfileSetupPageBase

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._loading = False
        page._cleanup_in_progress = False
        page._profile_key = "profile-1"
        page._raw_profile_text = _RawTextEditor("--new\n--lua-desync=latest")
        page._raw_profile_save_runtime = _Runtime(running=True)
        page._raw_profile_save_start_scheduled = False
        page._pending_raw_profile_save = None
        page._pending_profile_setup_write_operations = []
        page._profile_setup_write_operation_start_scheduled = False
        page._list_file_save_runtime = _Runtime(running=False)
        page._settings_save_runtime = _Runtime(running=False)
        page._enabled_save_runtime = _Runtime(running=False)
        page._user_profile_update_runtime = _Runtime(running=False)
        page._user_profile_delete_runtime = _Runtime(running=False)
        page._strategy_apply_runtime = _Runtime(running=False)
        page._strategy_feedback_save_runtime = _Runtime(running=False)
        page._raw_profile_save_button = Mock()
        page._queue_profile_setup_write_operation = Mock()
        page._start_raw_profile_save_worker = Mock()

        ProfileSetupPageBase._on_raw_profile_save_clicked(page)

        self.assertEqual(page._raw_profile_text.read_calls, 0)
        self.assertEqual(page._pending_raw_profile_save, ("profile-1", None))
        page._queue_profile_setup_write_operation.assert_called_once_with(
            {"kind": "raw_profile_save", "profile_key": "profile-1", "text": None}
        )
        page._start_raw_profile_save_worker.assert_not_called()

        page._raw_profile_save_runtime.running = False
        callbacks = []
        with patch(
            "profile.ui.profile_setup_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            ProfileSetupPageBase._on_raw_profile_save_worker_finished(page, object())

        self.assertEqual(page._raw_profile_text.read_calls, 0)
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        self.assertEqual(page._raw_profile_text.read_calls, 0)
        page._start_raw_profile_save_worker.assert_called_once_with(
            "profile-1",
            None,
        )
        self.assertIsNone(page._pending_raw_profile_save)

    def test_raw_profile_save_worker_start_reads_editor_once(self) -> None:
        from profile.ui.profile_setup_page import ProfileSetupPageBase

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._raw_profile_text = _RawTextEditor("--new\n--lua-desync=latest")
        page._raw_profile_text_cache = None
        page._raw_profile_save_runtime = _StartRuntime()
        page._raw_profile_save_request_id = 0
        page._raw_profile_save_button = None
        page.create_profile_raw_text_save_worker = Mock(return_value=object())

        ProfileSetupPageBase._start_raw_profile_save_worker(page, "profile-1", None)

        self.assertEqual(page._raw_profile_text.read_calls, 1)
        page.create_profile_raw_text_save_worker.assert_called_once_with(
            1,
            "profile-1",
            "--new\n--lua-desync=latest",
            parent=page,
        )


if __name__ == "__main__":
    unittest.main()
