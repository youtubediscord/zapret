from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from profile.profile_setup_loader import ProfileListFileLoadResult
from profile.ui.profile_setup_page import ProfileSetupPageBase
from ui.one_shot_worker_runtime import OneShotWorkerRuntime


class _Signal:
    def connect(self, _callback) -> None:
        return None


class _Worker:
    loaded = _Signal()
    failed = _Signal()
    finished = _Signal()

    def __init__(self, *, running: bool = False, request_id: int | None = None) -> None:
        self._running = running
        if request_id is not None:
            self._request_id = int(request_id)
        self.start = Mock()
        self.deleteLater = Mock()

    def isRunning(self) -> bool:  # noqa: N802
        return self._running


def _load_result(
    profile_key: str,
    *,
    filter_kind: str = "hostlist",
    filter_value: str = "lists/example.txt",
    file_name: str = "example.txt",
    state=None,
) -> ProfileListFileLoadResult:
    return ProfileListFileLoadResult(
        profile_key=profile_key,
        filter_kind=filter_kind,
        filter_value=filter_value,
        file_name=file_name,
        state=state if state is not None else SimpleNamespace(display_path=f"lists/{file_name}"),
    )


class ProfileListFileLoadQueueTests(unittest.TestCase):
    def test_list_file_load_keeps_pending_request_while_worker_runs(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._editor_tab_built = True
        page._profile_key = "profile-1"
        page._list_file_load_runtime = OneShotWorkerRuntime()
        page._list_file_load_runtime.worker = _Worker(running=True)
        page._pending_list_file_load = False

        ProfileSetupPageBase._request_list_file_editor_state(page)

        self.assertTrue(page._pending_list_file_load)

    def test_list_file_load_worker_finished_starts_pending_request(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        old_worker = _Worker(running=False)
        next_worker = _Worker(running=False)
        page._editor_tab_built = True
        page._profile_key = "profile-1"
        page._list_file_load_runtime = OneShotWorkerRuntime()
        page._list_file_load_runtime.worker = old_worker
        page._list_file_load_runtime.request_id = 0
        page._list_file_load_runtime_worker = old_worker
        page._pending_list_file_load = True
        page._list_file_load_request_id = 0
        page._list_file_status_label = None
        page._current_filter_kind = Mock(return_value="hostlist")
        page._current_filter_value = Mock(return_value="example.com")
        page.create_profile_list_file_load_worker = Mock(return_value=next_worker)

        with patch(
            "profile.ui.profile_setup_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callback(),
        ):
            ProfileSetupPageBase._on_list_file_worker_finished(page, old_worker)

        page.create_profile_list_file_load_worker.assert_called_once_with(
            1,
            "profile-1",
            filter_kind="hostlist",
            filter_value="example.com",
            parent=page,
        )
        next_worker.start.assert_called_once_with()
        self.assertFalse(page._pending_list_file_load)

    def test_real_list_file_worker_finish_starts_pending_profile_load(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        old_worker = _Worker(running=True, request_id=1)
        next_worker = _Worker(running=False, request_id=2)
        page._editor_tab_built = True
        page._profile_key = "profile-facebook"
        page._list_file_load_runtime = OneShotWorkerRuntime()
        page._list_file_load_runtime.worker = old_worker
        page._list_file_load_runtime.request_id = 1
        page._list_file_load_request_id = 1
        page._list_file_load_state = None
        page._list_file_status_label = None
        page._current_filter_kind = Mock(return_value="hostlist")
        page._current_filter_value = Mock(return_value="lists/facebook.txt")
        page.create_profile_list_file_load_worker = Mock(return_value=next_worker)

        ProfileSetupPageBase._request_list_file_editor_state(page)

        self.assertTrue(page._pending_list_file_load)
        self.assertEqual(page._list_file_load_request_id, 1)

        old_worker._running = False
        with patch(
            "profile.ui.profile_setup_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callback(),
        ):
            ProfileSetupPageBase._on_list_file_worker_finished(page, old_worker)

        page.create_profile_list_file_load_worker.assert_called_once_with(
            2,
            "profile-facebook",
            filter_kind="hostlist",
            filter_value="lists/facebook.txt",
            parent=page,
        )
        next_worker.start.assert_called_once_with()
        self.assertFalse(page._pending_list_file_load)

    def test_profile_switch_drops_old_list_file_load_result(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        old_worker = _Worker(running=True, request_id=1)
        page._profile_key = "profile-rutracker"
        page._payload = object()
        page._pending_profile_setup_payload_apply = object()
        page._profile_setup_payload_apply_scheduled = True
        page._last_profile_setup_payload_apply_signature = object()
        page._pending_list_file_state_apply = object()
        page._list_file_state_apply_scheduled = True
        page._list_file_dirty = False
        page._list_file_load_runtime = OneShotWorkerRuntime()
        page._list_file_load_runtime.worker = old_worker
        page._list_file_load_runtime.request_id = 1
        page._list_file_load_request_id = 1
        page._list_file_load_state = None
        page._current_filter_kind = Mock(return_value="hostlist")
        page._current_filter_value = Mock(return_value="lists/facebook.txt")
        page.reload_current_profile = Mock()
        page._schedule_list_file_editor_state_apply = Mock(
            side_effect=AssertionError("old profile list file state must not be applied after profile switch")
        )

        ProfileSetupPageBase.show_profile(page, "profile-facebook")
        ProfileSetupPageBase._on_list_file_editor_state_loaded(
            page,
            1,
            _load_result(
                "profile-rutracker",
                filter_kind="hostlist",
                filter_value="lists/rutracker.txt",
                file_name="rutracker.txt",
            ),
        )

        page.reload_current_profile.assert_called_once_with()
        page._schedule_list_file_editor_state_apply.assert_not_called()
        self.assertEqual(page._profile_key, "profile-facebook")

    def test_list_file_loaded_result_is_ignored_when_file_identity_changed(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._profile_key = "profile-facebook"
        page._list_file_load_request_id = 4
        page._list_file_load_state = None
        page._list_file_dirty = True
        page._current_filter_kind = Mock(return_value="hostlist")
        page._current_filter_value = Mock(return_value="lists/facebook.txt")
        page._schedule_list_file_editor_state_apply = Mock(
            side_effect=AssertionError("old list file result must not apply to a different current file")
        )

        ProfileSetupPageBase._on_list_file_editor_state_loaded(
            page,
            4,
            _load_result(
                "profile-facebook",
                filter_kind="hostlist",
                filter_value="lists/steam.txt",
                file_name="steam.txt",
            ),
        )

        self.assertTrue(page._list_file_dirty)
        page._schedule_list_file_editor_state_apply.assert_not_called()

    def test_list_file_loaded_result_is_ignored_when_result_filter_value_changed(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._profile_key = "profile-facebook"
        page._list_file_load_request_id = 4
        page._list_file_load_state = None
        page._list_file_dirty = True
        page._current_filter_kind = Mock(return_value="hostlist")
        page._current_filter_value = Mock(return_value="lists/facebook.txt")
        page._schedule_list_file_editor_state_apply = Mock(
            side_effect=AssertionError("result filter_value must match the current list file")
        )

        ProfileSetupPageBase._on_list_file_editor_state_loaded(
            page,
            4,
            _load_result(
                "profile-facebook",
                filter_kind="hostlist",
                filter_value="lists/steam.txt",
                file_name="facebook.txt",
            ),
        )

        self.assertTrue(page._list_file_dirty)
        page._schedule_list_file_editor_state_apply.assert_not_called()

    def test_list_file_loaded_result_is_ignored_when_filter_kind_changed(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._profile_key = "profile-facebook"
        page._list_file_load_request_id = 4
        page._list_file_load_state = None
        page._list_file_dirty = True
        page._current_filter_kind = Mock(return_value="hostlist")
        page._current_filter_value = Mock(return_value="lists/facebook.txt")
        page._schedule_list_file_editor_state_apply = Mock(
            side_effect=AssertionError("ipset result must not apply to the current hostlist editor")
        )

        ProfileSetupPageBase._on_list_file_editor_state_loaded(
            page,
            4,
            _load_result(
                "profile-facebook",
                filter_kind="ipset",
                filter_value="lists/facebook.txt",
                file_name="facebook.txt",
            ),
        )

        self.assertTrue(page._list_file_dirty)
        page._schedule_list_file_editor_state_apply.assert_not_called()

    def test_list_file_loaded_result_is_ignored_while_new_load_is_pending(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._list_file_load_request_id = 2
        page._pending_list_file_load = True
        page._list_file_dirty = True
        page._schedule_list_file_editor_state_apply = Mock(
            side_effect=AssertionError("pending newer list file load must own the editor state")
        )

        ProfileSetupPageBase._on_list_file_editor_state_loaded(page, 2, _load_result("profile-1"))

        self.assertTrue(page._pending_list_file_load)
        self.assertTrue(page._list_file_dirty)
        page._schedule_list_file_editor_state_apply.assert_not_called()


if __name__ == "__main__":
    unittest.main()
