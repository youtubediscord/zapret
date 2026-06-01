from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from profile.ui.profile_setup_page import ProfileSetupPageBase


class _Signal:
    def connect(self, _callback) -> None:
        return None


class _Worker:
    deleted = _Signal()
    failed = _Signal()
    finished = _Signal()

    def __init__(self) -> None:
        self.start = Mock()
        self.deleteLater = Mock()


class _Runtime:
    def __init__(self, *, running: bool) -> None:
        self.running = bool(running)

    def is_running(self) -> bool:
        return self.running

    def start_qthread_worker(self, *, worker_factory, **_kwargs):
        worker = worker_factory(0)
        worker.start()
        return 0, worker


class ProfileSetupDeleteQueueTests(unittest.TestCase):
    def test_user_profile_delete_queues_pending_requests_while_worker_runs(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._user_profile_delete_runtime = _Runtime(running=True)
        page._pending_user_profile_deletes = []
        page.create_profile_user_delete_worker = Mock()

        ProfileSetupPageBase._request_user_profile_delete(page, "user-1")
        ProfileSetupPageBase._request_user_profile_delete(page, "user-2")

        page.create_profile_user_delete_worker.assert_not_called()
        self.assertEqual(page._pending_user_profile_deletes, ["user-1", "user-2"])

    def test_user_profile_delete_worker_finished_starts_next_pending_delete(self) -> None:
        runtime = _Runtime(running=False)
        worker = _Worker()
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._user_profile_delete_request_id = 1
        page._user_profile_delete_runtime = runtime
        page._pending_user_profile_deletes = ["user-2"]
        page._update_user_profile_button = Mock()
        page._delete_user_profile_button = Mock()
        page.create_profile_user_delete_worker = Mock(return_value=worker)

        callbacks = []
        with patch(
            "profile.ui.profile_setup_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            ProfileSetupPageBase._on_user_profile_delete_worker_finished(page, object())

        page.create_profile_user_delete_worker.assert_not_called()
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page.create_profile_user_delete_worker.assert_called_once_with(
            2,
            profile_id="user-2",
            parent=page,
        )
        worker.start.assert_called_once_with()
        page._update_user_profile_button.setEnabled.assert_called_once_with(False)
        page._delete_user_profile_button.setEnabled.assert_called_once_with(False)
        self.assertEqual(page._pending_user_profile_deletes, [])

    def test_user_profile_delete_waits_while_update_worker_runs(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._user_profile_update_runtime = _Runtime(running=True)
        page._user_profile_delete_runtime = _Runtime(running=False)
        page._user_profile_delete_request_id = 0
        page._pending_user_profile_operations = []
        page._pending_user_profile_deletes = []
        page._update_user_profile_button = Mock()
        page._delete_user_profile_button = Mock()
        page.create_profile_user_delete_worker = Mock(return_value=_Worker())

        ProfileSetupPageBase._request_user_profile_delete(page, "user-3")

        page.create_profile_user_delete_worker.assert_not_called()
        self.assertEqual(
            page._pending_user_profile_operations,
            [
                {
                    "action": "delete",
                    "profile_id": "user-3",
                    "name": "",
                    "protocol": "",
                    "ports": "",
                }
            ],
        )

    def test_user_profile_update_waits_while_delete_worker_runs(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._user_profile_update_runtime = _Runtime(running=False)
        page._user_profile_delete_runtime = _Runtime(running=True)
        page._user_profile_update_request_id = 0
        page._pending_user_profile_operations = []
        page._pending_user_profile_updates = []
        page._update_user_profile_button = Mock()
        page._delete_user_profile_button = Mock()
        update_worker = _Worker()
        update_worker.updated = _Signal()
        page.create_profile_user_update_worker = Mock(return_value=update_worker)

        ProfileSetupPageBase._request_user_profile_update(
            page,
            "user-4",
            name="Updated",
            protocol="tcp",
            ports="80,443",
        )

        page.create_profile_user_update_worker.assert_not_called()
        self.assertEqual(
            page._pending_user_profile_operations,
            [
                {
                    "action": "update",
                    "profile_id": "user-4",
                    "name": "Updated",
                    "protocol": "tcp",
                    "ports": "80,443",
                }
            ],
        )

    def test_user_profile_update_waits_while_next_write_start_is_scheduled(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._user_profile_write_operation_start_scheduled = True
        page._user_profile_update_runtime = _Runtime(running=False)
        page._user_profile_delete_runtime = _Runtime(running=False)
        page._user_profile_update_request_id = 0
        page._pending_user_profile_operations = []
        page._pending_user_profile_updates = []
        page._update_user_profile_button = Mock()
        page._delete_user_profile_button = Mock()
        update_worker = _Worker()
        update_worker.updated = _Signal()
        page.create_profile_user_update_worker = Mock(return_value=update_worker)

        ProfileSetupPageBase._request_user_profile_update(
            page,
            "user-5",
            name="Latest",
            protocol="udp",
            ports="443",
        )

        page.create_profile_user_update_worker.assert_not_called()
        self.assertEqual(
            page._pending_user_profile_operations,
            [
                {
                    "action": "update",
                    "profile_id": "user-5",
                    "name": "Latest",
                    "protocol": "udp",
                    "ports": "443",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
