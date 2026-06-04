from __future__ import annotations

import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.feature_facades.blobs import build_blobs_feature
import blobs.ui.runtime_helpers as blobs_runtime_helpers
import blobs.ui.page as blobs_page
from blobs.ui.page import BlobsPage
import blobs.workers as blobs_workers


class BlobsWorkerArchitectureTests(unittest.TestCase):
    def test_blobs_feature_does_not_expose_heavy_direct_actions(self) -> None:
        feature = build_blobs_feature()

        for attr_name in (
            "get_blobs_info",
            "save_user_blob",
            "delete_user_blob",
            "reload_blobs",
            "open_bin_folder",
            "open_blobs_json",
        ):
            self.assertFalse(hasattr(feature, attr_name), attr_name)

    def test_blobs_workers_receive_commands_from_feature(self) -> None:
        feature_source = inspect.getsource(build_blobs_feature)
        worker_source = "\n".join(
            (
                inspect.getsource(blobs_workers.BlobsLoadWorker),
                inspect.getsource(blobs_workers.BlobActionWorker),
                inspect.getsource(blobs_workers.BlobOpenActionWorker),
            )
        )

        self.assertNotIn("blobs_feature=feature", feature_source)
        self.assertNotIn("self._blobs", worker_source)
        self.assertNotIn("import blobs.public", worker_source)
        self.assertIn("get_blobs_info=", feature_source)
        self.assertIn("reload_blobs=", feature_source)
        self.assertIn("save_user_blob=", feature_source)
        self.assertIn("delete_user_blob=", feature_source)
        self.assertIn("open_bin_folder=", feature_source)
        self.assertIn("open_blobs_json=", feature_source)
        self.assertIn("self._get_blobs_info", worker_source)
        self.assertIn("self._reload_blobs", worker_source)
        self.assertIn("self._save_user_blob", worker_source)
        self.assertIn("self._delete_user_blob", worker_source)
        self.assertIn("self._open_bin_folder", worker_source)
        self.assertIn("self._open_blobs_json", worker_source)

    def test_blobs_runtime_helpers_do_not_keep_direct_open_actions(self) -> None:
        helper_names = set(vars(blobs_runtime_helpers))

        self.assertNotIn("reload_blobs_data", helper_names)
        self.assertNotIn("open_bin_folder_action", helper_names)
        self.assertNotIn("open_json_action", helper_names)

    def test_blobs_page_uses_one_shot_runtime_for_workers(self) -> None:
        page_source = inspect.getsource(BlobsPage)
        load_source = inspect.getsource(BlobsPage._start_blobs_load_worker)
        action_source = inspect.getsource(BlobsPage._start_blob_action_worker)
        open_source = inspect.getsource(BlobsPage._start_blob_open_action_worker)
        cleanup_source = inspect.getsource(BlobsPage.cleanup)

        self.assertIn("OneShotWorkerRuntime", page_source)
        self.assertIn("_blobs_load_runtime", page_source)
        self.assertIn("_blob_action_runtime", page_source)
        self.assertIn("_blob_open_action_runtime", page_source)
        for source in (load_source, action_source, open_source):
            self.assertIn("start_qthread_worker", source)
            self.assertNotIn("worker.start()", source)
        self.assertIn("_blobs_load_runtime.stop", cleanup_source)
        self.assertIn("_blob_action_runtime.stop", cleanup_source)
        self.assertIn("_blob_open_action_runtime.stop", cleanup_source)

    def test_blobs_load_pending_restarts_after_event_loop_turn(self) -> None:
        page = BlobsPage.__new__(BlobsPage)
        page._cleanup_in_progress = False
        page._blobs_load_pending = True
        page._blobs_load_pending_reload = True
        page._start_blobs_load_worker = Mock()
        page.reload_btn = SimpleNamespace(set_loading=Mock())
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(blobs_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            BlobsPage._on_blobs_load_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_blobs_load_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_blobs_load_worker.assert_called_once_with(reload=True)

    def test_stale_blobs_load_worker_finished_does_not_restart_pending_load(self) -> None:
        page = BlobsPage.__new__(BlobsPage)
        page._cleanup_in_progress = False
        page._blobs_load_runtime = SimpleNamespace(request_id=3)
        page._blobs_load_pending = True
        page._blobs_load_pending_reload = True
        page._start_blobs_load_worker = Mock()
        page.reload_btn = SimpleNamespace(set_loading=Mock())
        single_shot = Mock()

        with patch.object(blobs_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            BlobsPage._on_blobs_load_worker_finished(page, SimpleNamespace(_request_id=2))

        single_shot.assert_not_called()
        page._start_blobs_load_worker.assert_not_called()
        self.assertTrue(page._blobs_load_pending)
        self.assertTrue(page._blobs_load_pending_reload)

    def test_stale_blobs_load_worker_object_finished_does_not_restart_pending_load(self) -> None:
        old_worker = object()
        current_worker = object()
        page = BlobsPage.__new__(BlobsPage)
        page._cleanup_in_progress = False
        page._blobs_load_runtime = SimpleNamespace(request_id=3, worker=current_worker)
        page._blobs_load_pending = True
        page._blobs_load_pending_reload = True
        page._start_blobs_load_worker = Mock()
        page.reload_btn = SimpleNamespace(set_loading=Mock())
        single_shot = Mock()

        with patch.object(blobs_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            BlobsPage._on_blobs_load_worker_finished(page, old_worker)

        single_shot.assert_not_called()
        page._start_blobs_load_worker.assert_not_called()
        self.assertTrue(page._blobs_load_pending)
        self.assertTrue(page._blobs_load_pending_reload)

    def test_blobs_load_scheduled_start_uses_latest_pending_reload(self) -> None:
        page = BlobsPage.__new__(BlobsPage)
        page._cleanup_in_progress = False
        page._blobs_load_pending = True
        page._blobs_load_pending_reload = False
        page._blobs_load_start_scheduled = False
        page._blobs_load_runtime = SimpleNamespace(is_running=Mock(return_value=False), start_qthread_worker=Mock())
        page._start_blobs_load_worker = Mock()
        page.reload_btn = SimpleNamespace(set_loading=Mock())
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(blobs_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            BlobsPage._on_blobs_load_worker_finished(page, object())
            BlobsPage._request_blobs_load(page, reload=True)

        single_shot.call_args.args[1]()

        page._start_blobs_load_worker.assert_called_once_with(reload=True)

    def test_blob_action_pending_restarts_after_event_loop_turn(self) -> None:
        page = BlobsPage.__new__(BlobsPage)
        page._cleanup_in_progress = False
        page._blob_action_pending = [{"action": "delete", "name": "a.bin"}]
        page._start_blob_action_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(blobs_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            BlobsPage._on_blob_action_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_blob_action_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_blob_action_worker.assert_called_once_with({"action": "delete", "name": "a.bin"})

    def test_stale_blob_action_worker_finished_does_not_restart_pending_action(self) -> None:
        page = BlobsPage.__new__(BlobsPage)
        page._cleanup_in_progress = False
        page._blob_action_runtime = SimpleNamespace(request_id=7)
        page._blob_action_pending = [{"action": "delete", "name": "a.bin"}]
        page._start_blob_action_worker = Mock()
        single_shot = Mock()

        with patch.object(blobs_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            BlobsPage._on_blob_action_worker_finished(page, SimpleNamespace(_request_id=6))

        single_shot.assert_not_called()
        page._start_blob_action_worker.assert_not_called()
        self.assertEqual(page._blob_action_pending, [{"action": "delete", "name": "a.bin"}])

    def test_stale_blob_action_worker_object_finished_does_not_restart_pending_action(self) -> None:
        old_worker = object()
        current_worker = object()
        page = BlobsPage.__new__(BlobsPage)
        page._cleanup_in_progress = False
        page._blob_action_runtime = SimpleNamespace(request_id=7, worker=current_worker)
        page._blob_action_pending = [{"action": "delete", "name": "a.bin"}]
        page._start_blob_action_worker = Mock()
        single_shot = Mock()

        with patch.object(blobs_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            BlobsPage._on_blob_action_worker_finished(page, old_worker)

        single_shot.assert_not_called()
        page._start_blob_action_worker.assert_not_called()
        self.assertEqual(page._blob_action_pending, [{"action": "delete", "name": "a.bin"}])

    def test_blob_action_scheduled_start_queues_next_payload(self) -> None:
        page = BlobsPage.__new__(BlobsPage)
        page._cleanup_in_progress = False
        page._blob_action_start_scheduled = False
        page._blob_action_pending = []
        page._start_blob_action_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        old_payload = {"action": "delete", "name": "old.bin"}
        new_payload = {"action": "delete", "name": "new.bin"}
        with patch.object(blobs_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            BlobsPage._schedule_blob_action_worker_start(page, old_payload)
            BlobsPage._schedule_blob_action_worker_start(page, new_payload)

        single_shot.assert_called_once()
        self.assertEqual(page._blob_action_pending, [new_payload])

        single_shot.call_args.args[1]()

        page._start_blob_action_worker.assert_called_once_with(old_payload)
        self.assertEqual(page._blob_action_pending, [new_payload])

    def test_duplicate_blob_action_is_queued_once(self) -> None:
        page = BlobsPage.__new__(BlobsPage)
        page._blob_action_runtime = SimpleNamespace(is_running=Mock(return_value=True))
        page._blob_action_start_scheduled = False
        page._blob_action_pending = []
        page._start_blob_action_worker = Mock()

        BlobsPage._request_blob_action(page, "delete", name="same.bin")
        BlobsPage._request_blob_action(page, "delete", name="same.bin")

        self.assertEqual(
            page._blob_action_pending,
            [
                {
                    "action": "delete",
                    "name": "same.bin",
                    "blob_type": "",
                    "value": "",
                    "description": "",
                }
            ],
        )
        page._start_blob_action_worker.assert_not_called()

    def test_blob_open_action_pending_restarts_after_event_loop_turn(self) -> None:
        page = BlobsPage.__new__(BlobsPage)
        page._cleanup_in_progress = False
        page._blob_open_action_pending = ["blobs_json"]
        page._start_blob_open_action_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(blobs_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            BlobsPage._on_blob_open_action_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_blob_open_action_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_blob_open_action_worker.assert_called_once_with("blobs_json")

    def test_stale_blob_open_action_worker_finished_does_not_restart_pending_open(self) -> None:
        page = BlobsPage.__new__(BlobsPage)
        page._cleanup_in_progress = False
        page._blob_open_action_runtime = SimpleNamespace(request_id=5)
        page._blob_open_action_pending = ["blobs_json"]
        page._start_blob_open_action_worker = Mock()
        single_shot = Mock()

        with patch.object(blobs_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            BlobsPage._on_blob_open_action_worker_finished(page, SimpleNamespace(_request_id=4))

        single_shot.assert_not_called()
        page._start_blob_open_action_worker.assert_not_called()
        self.assertEqual(page._blob_open_action_pending, ["blobs_json"])

    def test_stale_blob_open_action_worker_object_finished_does_not_restart_pending_open(self) -> None:
        old_worker = object()
        current_worker = object()
        page = BlobsPage.__new__(BlobsPage)
        page._cleanup_in_progress = False
        page._blob_open_action_runtime = SimpleNamespace(request_id=5, worker=current_worker)
        page._blob_open_action_pending = ["blobs_json"]
        page._start_blob_open_action_worker = Mock()
        single_shot = Mock()

        with patch.object(blobs_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            BlobsPage._on_blob_open_action_worker_finished(page, old_worker)

        single_shot.assert_not_called()
        page._start_blob_open_action_worker.assert_not_called()
        self.assertEqual(page._blob_open_action_pending, ["blobs_json"])

    def test_blob_open_action_scheduled_start_queues_next_action(self) -> None:
        page = BlobsPage.__new__(BlobsPage)
        page._cleanup_in_progress = False
        page._blob_open_action_start_scheduled = False
        page._blob_open_action_pending = []
        page._start_blob_open_action_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(blobs_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            BlobsPage._schedule_blob_open_action_worker_start(page, "bin_folder")
            BlobsPage._schedule_blob_open_action_worker_start(page, "blobs_json")

        single_shot.assert_called_once()
        self.assertEqual(page._blob_open_action_pending, ["blobs_json"])

        single_shot.call_args.args[1]()

        page._start_blob_open_action_worker.assert_called_once_with("bin_folder")
        self.assertEqual(page._blob_open_action_pending, ["blobs_json"])

    def test_duplicate_blob_open_action_is_queued_once(self) -> None:
        page = BlobsPage.__new__(BlobsPage)
        page._blob_open_action_runtime = SimpleNamespace(is_running=Mock(return_value=True))
        page._blob_open_action_start_scheduled = False
        page._blob_open_action_pending = []
        page._start_blob_open_action_worker = Mock()

        BlobsPage._request_blob_open_action(page, "blobs_json")
        BlobsPage._request_blob_open_action(page, "blobs_json")

        self.assertEqual(page._blob_open_action_pending, ["blobs_json"])
        page._start_blob_open_action_worker.assert_not_called()


if __name__ == "__main__":
    unittest.main()
