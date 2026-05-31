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
