from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from profile.ui.profile_setup_page import ProfileSetupPageBase


class _Signal:
    def connect(self, _callback) -> None:
        return None


class _Worker:
    saved = _Signal()
    failed = _Signal()
    finished = _Signal()

    def __init__(self) -> None:
        self.start = Mock()
        self.deleteLater = Mock()


class _Runtime:
    def __init__(self, *, running: bool = False) -> None:
        self.running = running

    def is_running(self) -> bool:
        return self.running

    def start_qthread_worker(self, *, worker_factory, **_kwargs):
        worker = worker_factory(0)
        worker.start()
        return 0, worker


class ProfileSetupWriteSerializationTests(unittest.TestCase):
    def test_profile_setup_write_queue_lives_in_queued_worker_state(self) -> None:
        import inspect
        from ui.queued_worker_state import QueuedWorkerState

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        module_source = inspect.getsource(
            __import__("profile.ui.profile_setup_page", fromlist=[""])
        )
        init_source = inspect.getsource(ProfileSetupPageBase.__init__)
        queue_source = inspect.getsource(ProfileSetupPageBase._queue_profile_setup_write_operation)
        start_next_source = inspect.getsource(ProfileSetupPageBase._start_next_profile_setup_write_operation)
        schedule_source = inspect.getsource(ProfileSetupPageBase._schedule_profile_setup_write_operation_start)
        cleanup_source = inspect.getsource(ProfileSetupPageBase.cleanup)

        self.assertIsInstance(ProfileSetupPageBase._profile_setup_write_state_obj(page), QueuedWorkerState)
        self.assertIn("from ui.queued_worker_state import QueuedWorkerState", module_source)
        self.assertIn("_profile_setup_write_state = QueuedWorkerState", init_source)
        self.assertIn("_profile_setup_write_state_obj()", queue_source)
        self.assertIn("state.pop_next()", start_next_source)
        self.assertIn("state.start_scheduled", schedule_source)
        self.assertIn("_profile_setup_write_state_obj().reset()", cleanup_source)
        self.assertNotIn("self._pending_profile_setup_write_operations: list", init_source)

    def test_user_profile_write_queue_lives_in_queued_worker_state(self) -> None:
        import inspect
        from ui.queued_worker_state import QueuedWorkerState

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        module_source = inspect.getsource(
            __import__("profile.ui.profile_setup_page", fromlist=[""])
        )
        init_source = inspect.getsource(ProfileSetupPageBase.__init__)
        queue_source = inspect.getsource(ProfileSetupPageBase._queue_user_profile_write_operation)
        pop_source = inspect.getsource(ProfileSetupPageBase._pop_next_pending_user_profile_write_operation)
        has_pending_source = inspect.getsource(ProfileSetupPageBase._has_pending_user_profile_write_operation)
        schedule_source = inspect.getsource(ProfileSetupPageBase._schedule_next_pending_user_profile_write_operation_start)
        cleanup_source = inspect.getsource(ProfileSetupPageBase.cleanup)

        self.assertIsInstance(ProfileSetupPageBase._user_profile_write_state_obj(page), QueuedWorkerState)
        self.assertIn("from ui.queued_worker_state import QueuedWorkerState", module_source)
        self.assertIn("_user_profile_write_state = QueuedWorkerState", init_source)
        self.assertIn("_user_profile_write_state_obj()", queue_source)
        self.assertIn("state.pop_next()", pop_source)
        self.assertIn("_user_profile_write_state_obj().has_pending()", has_pending_source)
        self.assertIn("state.start_scheduled", schedule_source)
        self.assertIn("_user_profile_write_state_obj().reset()", cleanup_source)

    def test_raw_profile_save_waits_while_settings_save_runs(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._settings_save_runtime = _Runtime(running=True)
        page._raw_profile_save_runtime = _Runtime(running=False)
        page._raw_profile_save_request_id = 0
        page._pending_settings_save = None
        page._pending_raw_profile_save = None
        page._pending_profile_setup_write_operations = []
        page._profile_key = "profile-1"
        page._raw_profile_save_button = None
        page.create_profile_raw_text_save_worker = Mock(return_value=_Worker())

        ProfileSetupPageBase._request_raw_profile_save(page, "profile-1", "--new\n--lua-desync=split")

        page.create_profile_raw_text_save_worker.assert_not_called()
        self.assertEqual(
            page._pending_profile_setup_write_operations,
            [
                {
                    "kind": "raw_profile_save",
                    "profile_key": "profile-1",
                    "text": "--new\n--lua-desync=split",
                }
            ],
        )

        page._settings_save_runtime.running = False
        callbacks = []
        with patch(
            "profile.ui.profile_setup_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            ProfileSetupPageBase._on_settings_save_worker_finished(page, object())

        page.create_profile_raw_text_save_worker.assert_not_called()
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page.create_profile_raw_text_save_worker.assert_called_once_with(
            1,
            "profile-1",
            "--new\n--lua-desync=split",
            parent=page,
        )

    def test_repeated_raw_profile_save_keeps_only_latest_pending_text(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._settings_save_runtime = _Runtime(running=True)
        page._raw_profile_save_runtime = _Runtime(running=False)
        page._pending_settings_save = None
        page._pending_raw_profile_save = None
        page._pending_profile_setup_write_operations = []
        page._profile_key = "profile-1"
        page.create_profile_raw_text_save_worker = Mock(return_value=_Worker())

        ProfileSetupPageBase._request_raw_profile_save(page, "profile-1", "--lua-desync=split")
        ProfileSetupPageBase._request_raw_profile_save(page, "profile-1", "--lua-desync=fake")

        page.create_profile_raw_text_save_worker.assert_not_called()
        self.assertEqual(
            page._pending_profile_setup_write_operations,
            [
                {
                    "kind": "raw_profile_save",
                    "profile_key": "profile-1",
                    "text": "--lua-desync=fake",
                }
            ],
        )

    def test_user_profile_update_queue_keeps_latest_update_for_same_profile(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._user_profile_update_runtime = _Runtime(running=True)
        page._user_profile_delete_runtime = _Runtime(running=False)
        page._pending_user_profile_operations = []
        page._pending_user_profile_updates = []
        page._pending_user_profile_deletes = []
        page._user_profile_update_request_id = 0
        page._set_user_profile_actions_enabled = Mock()
        page.create_profile_user_update_worker = Mock(return_value=_Worker())

        ProfileSetupPageBase._request_user_profile_update(
            page,
            "user-1",
            name="Old",
            protocol="tcp",
            ports="443",
        )
        ProfileSetupPageBase._request_user_profile_update(
            page,
            "user-1",
            name="Latest",
            protocol="udp",
            ports="443,500",
        )

        page.create_profile_user_update_worker.assert_not_called()
        self.assertEqual(
            page._pending_user_profile_operations,
            [
                {
                    "action": "update",
                    "profile_id": "user-1",
                    "name": "Latest",
                    "protocol": "udp",
                    "ports": "443,500",
                }
            ],
        )
        self.assertEqual(
            page._pending_user_profile_updates,
            [
                {
                    "profile_id": "user-1",
                    "name": "Latest",
                    "protocol": "udp",
                    "ports": "443,500",
                }
            ],
        )

    def test_stale_user_profile_update_worker_finished_does_not_start_pending_operation(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._user_profile_update_runtime = _Runtime(running=False)
        page._user_profile_delete_runtime = _Runtime(running=False)
        page._user_profile_update_runtime_worker = object()
        page._user_profile_write_operation_start_scheduled = False
        page._pending_user_profile_operations = [
            {"action": "delete", "profile_id": "user-2", "name": "", "protocol": "", "ports": ""}
        ]
        page._pending_user_profile_updates = []
        page._pending_user_profile_deletes = ["user-2"]
        page._set_user_profile_buttons_enabled = Mock()
        callbacks = []

        with patch(
            "profile.ui.profile_setup_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            ProfileSetupPageBase._on_user_profile_update_worker_finished(page, object())

        self.assertEqual(callbacks, [])
        self.assertEqual(
            page._pending_user_profile_operations,
            [{"action": "delete", "profile_id": "user-2", "name": "", "protocol": "", "ports": ""}],
        )
        page._set_user_profile_buttons_enabled.assert_not_called()

    def test_stale_user_profile_delete_worker_finished_does_not_start_pending_operation(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._user_profile_update_runtime = _Runtime(running=False)
        page._user_profile_delete_runtime = _Runtime(running=False)
        page._user_profile_delete_runtime_worker = object()
        page._user_profile_write_operation_start_scheduled = False
        page._pending_user_profile_operations = [
            {
                "action": "update",
                "profile_id": "user-1",
                "name": "Latest",
                "protocol": "tcp",
                "ports": "443",
            }
        ]
        page._pending_user_profile_updates = [
            {"profile_id": "user-1", "name": "Latest", "protocol": "tcp", "ports": "443"}
        ]
        page._pending_user_profile_deletes = []
        page._set_user_profile_buttons_enabled = Mock()
        callbacks = []

        with patch(
            "profile.ui.profile_setup_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            ProfileSetupPageBase._on_user_profile_delete_worker_finished(page, object())

        self.assertEqual(callbacks, [])
        self.assertEqual(
            page._pending_user_profile_operations,
            [
                {
                    "action": "update",
                    "profile_id": "user-1",
                    "name": "Latest",
                    "protocol": "tcp",
                    "ports": "443",
                }
            ],
        )
        page._set_user_profile_buttons_enabled.assert_not_called()

    def test_raw_profile_save_waits_while_next_write_start_is_scheduled(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._profile_setup_write_operation_start_scheduled = True
        page._raw_profile_save_runtime = _Runtime(running=False)
        page._raw_profile_save_request_id = 0
        page._pending_raw_profile_save = None
        page._pending_profile_setup_write_operations = []
        page._profile_key = "profile-1"
        page._raw_profile_save_button = None
        page.create_profile_raw_text_save_worker = Mock(return_value=_Worker())

        ProfileSetupPageBase._request_raw_profile_save(page, "profile-1", "--lua-desync=fake")

        page.create_profile_raw_text_save_worker.assert_not_called()
        self.assertEqual(page._pending_raw_profile_save, ("profile-1", "--lua-desync=fake"))
        self.assertEqual(
            page._pending_profile_setup_write_operations,
            [
                {
                    "kind": "raw_profile_save",
                    "profile_key": "profile-1",
                    "text": "--lua-desync=fake",
                }
            ],
        )

    def test_scheduled_raw_profile_save_uses_latest_request_before_worker_starts(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._raw_profile_save_runtime = _Runtime(running=False)
        page._raw_profile_save_request_id = 0
        page._pending_raw_profile_save = None
        page._pending_profile_setup_write_operations = []
        page._profile_key = "profile-1"
        page._raw_profile_save_button = None
        page.create_profile_raw_text_save_worker = Mock(return_value=_Worker())
        callbacks = []

        with patch(
            "profile.ui.profile_setup_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            ProfileSetupPageBase._schedule_profile_setup_write_operation_start(
                page,
                {
                    "kind": "raw_profile_save",
                    "profile_key": "profile-1",
                    "text": "--lua-desync=old",
                },
            )
            ProfileSetupPageBase._request_raw_profile_save(page, "profile-1", "--lua-desync=latest")

        page.create_profile_raw_text_save_worker.assert_not_called()
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page.create_profile_raw_text_save_worker.assert_called_once_with(
            1,
            "profile-1",
            "--lua-desync=latest",
            parent=page,
        )
        self.assertEqual(page._pending_profile_setup_write_operations, [])
        self.assertIsNone(page._pending_raw_profile_save)

    def test_strategy_apply_waits_while_raw_profile_save_runs(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._raw_profile_save_runtime = _Runtime(running=True)
        page._strategy_apply_runtime = _Runtime(running=False)
        page._strategy_apply_request_id = 0
        page._strategy_apply_runtime_strategy_id = ""
        page._strategy_apply_runtime_branch_id = ""
        page._pending_strategy_apply = None
        page._pending_profile_setup_write_operations = []
        page._profile_key = "profile-1"
        page._payload = SimpleNamespace(strategy_branches=(), current_strategy_branch_id="")
        page.create_profile_strategy_apply_worker = Mock(return_value=_Worker())

        ProfileSetupPageBase._request_strategy_apply(page, "tls_fake")

        page.create_profile_strategy_apply_worker.assert_not_called()
        self.assertEqual(
            page._pending_profile_setup_write_operations,
            [{"kind": "strategy_apply", "strategy_id": "tls_fake", "branch_id": ""}],
        )

        page._raw_profile_save_runtime.running = False
        callbacks = []
        with patch(
            "profile.ui.profile_setup_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            ProfileSetupPageBase._on_raw_profile_save_worker_finished(page, object())

        page.create_profile_strategy_apply_worker.assert_not_called()
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page.create_profile_strategy_apply_worker.assert_called_once_with(
            1,
            profile_key="profile-1",
            strategy_id="tls_fake",
            parent=page,
        )

    def test_enabled_noop_does_not_enter_write_queue_while_other_save_runs(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._loading = False
        page._profile_key = "profile-1"
        page._settings_save_runtime = _Runtime(running=True)
        page._enabled_save_runtime = _Runtime(running=False)
        page._enabled_save_runtime_enabled = None
        page._pending_enabled_save = None
        page._pending_profile_setup_write_operations = []
        page._payload = SimpleNamespace(item=SimpleNamespace(enabled=True))
        page.create_profile_enabled_save_worker = Mock(return_value=_Worker())

        ProfileSetupPageBase._on_enabled_changed(page, 2)

        page.create_profile_enabled_save_worker.assert_not_called()
        self.assertEqual(page._pending_profile_setup_write_operations, [])

    def test_legacy_pending_settings_save_restarts_later_after_worker_finished(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._settings_save_runtime = _Runtime(running=False)
        page._settings_save_request_id = 0
        page._pending_profile_setup_write_operations = []
        page._pending_settings_save = {
            "profile_key": "profile-1",
            "filter_kind": "hostlist",
            "filter_value": "example.com",
            "in_range": "x",
            "out_range": "a",
        }
        page.create_profile_settings_save_worker = Mock(return_value=_Worker())
        callbacks = []

        with patch(
            "profile.ui.profile_setup_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            ProfileSetupPageBase._on_settings_save_worker_finished(page, object())

        page.create_profile_settings_save_worker.assert_not_called()
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page.create_profile_settings_save_worker.assert_called_once_with(
            1,
            profile_key="profile-1",
            filter_kind="hostlist",
            filter_value="example.com",
            in_range="x",
            out_range="a",
            parent=page,
        )

    def test_legacy_pending_raw_profile_save_restarts_later_after_worker_finished(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._raw_profile_save_runtime = _Runtime(running=False)
        page._raw_profile_save_request_id = 0
        page._raw_profile_save_button = None
        page._pending_profile_setup_write_operations = []
        page._pending_raw_profile_save = ("profile-1", "--new\n--lua-desync=split")
        page.create_profile_raw_text_save_worker = Mock(return_value=_Worker())
        callbacks = []

        with patch(
            "profile.ui.profile_setup_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            ProfileSetupPageBase._on_raw_profile_save_worker_finished(page, object())

        page.create_profile_raw_text_save_worker.assert_not_called()
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page.create_profile_raw_text_save_worker.assert_called_once_with(
            1,
            "profile-1",
            "--new\n--lua-desync=split",
            parent=page,
        )

    def test_legacy_pending_strategy_apply_restarts_later_after_worker_finished(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._strategy_apply_runtime = _Runtime(running=False)
        page._strategy_apply_request_id = 0
        page._strategy_apply_runtime_strategy_id = "old"
        page._strategy_apply_runtime_branch_id = ""
        page._pending_profile_setup_write_operations = []
        page._pending_strategy_apply = "tls_fake"
        page._profile_key = "profile-1"
        page.create_profile_strategy_apply_worker = Mock(return_value=_Worker())
        callbacks = []

        with patch(
            "profile.ui.profile_setup_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            ProfileSetupPageBase._on_strategy_apply_worker_finished(page, object())

        page.create_profile_strategy_apply_worker.assert_not_called()
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page.create_profile_strategy_apply_worker.assert_called_once_with(
            1,
            profile_key="profile-1",
            strategy_id="tls_fake",
            parent=page,
        )

    def test_pending_strategy_feedback_save_restarts_later_after_worker_finished(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._strategy_feedback_save_runtime = _Runtime(running=False)
        page._strategy_feedback_save_request_id = 0
        page._pending_strategy_feedback_save = {"rating": "work", "favorite": True}
        page._profile_key = "profile-1"
        page._payload = SimpleNamespace(item=SimpleNamespace(strategy_id="tls_fake"))
        page.create_profile_strategy_feedback_save_worker = Mock(return_value=_Worker())
        callbacks = []

        with patch(
            "profile.ui.profile_setup_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            ProfileSetupPageBase._on_strategy_feedback_save_worker_finished(page, object())

        page.create_profile_strategy_feedback_save_worker.assert_not_called()
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page.create_profile_strategy_feedback_save_worker.assert_called_once_with(
            1,
            profile_key="profile-1",
            strategy_id="tls_fake",
            rating="work",
            favorite=True,
            parent=page,
        )


if __name__ == "__main__":
    unittest.main()
