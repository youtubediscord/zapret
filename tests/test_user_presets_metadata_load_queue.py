from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PyQt6.QtWidgets import QApplication


class _Signal:
    def __init__(self) -> None:
        self.callbacks = []

    def connect(self, callback) -> None:
        self.callbacks.append(callback)


class _MetadataWorker:
    instances = []

    def __init__(self, request_id, load_all_metadata, load_folder_state, page) -> None:
        self.request_id = request_id
        self.load_all_metadata = load_all_metadata
        self.load_folder_state = load_folder_state
        self.page = page
        self.loaded = _Signal()
        self.failed = _Signal()
        self.finished = _Signal()
        self.start_calls = 0
        self.delete_later_calls = 0
        self._running = False
        self.__class__.instances.append(self)

    def isRunning(self) -> bool:  # noqa: N802
        return self._running

    def start(self) -> None:
        self.start_calls += 1
        self._running = True

    def deleteLater(self) -> None:  # noqa: N802
        self.delete_later_calls += 1
        self._running = False


class _SingleMetadataWorker:
    instances = []

    def __init__(self, request_id, file_name, read_single_metadata, page) -> None:
        self.request_id = request_id
        self.file_name = file_name
        self.read_single_metadata = read_single_metadata
        self.page = page
        self.loaded = _Signal()
        self.failed = _Signal()
        self.finished = _Signal()
        self.start_calls = 0
        self._running = False
        self.__class__.instances.append(self)

    def isRunning(self) -> bool:  # noqa: N802
        return self._running

    def start(self) -> None:
        self.start_calls += 1
        self._running = True

    def deleteLater(self) -> None:  # noqa: N802
        self._running = False


class _RowsPlanWorker:
    instances = []

    def __init__(
        self,
        request_id,
        build_rows_plan,
        *,
        all_presets,
        query,
        selected_source_file_name,
        language,
        folder_state,
        started_at,
        parent,
    ) -> None:
        self.request_id = request_id
        self.build_rows_plan = build_rows_plan
        self.all_presets = all_presets
        self.query = query
        self.selected_source_file_name = selected_source_file_name
        self.language = language
        self.folder_state = folder_state
        self.started_at = started_at
        self.parent = parent
        self.loaded = _Signal()
        self.failed = _Signal()
        self.finished = _Signal()
        self.start_calls = 0
        self._running = False
        self.__class__.instances.append(self)

    def isRunning(self) -> bool:  # noqa: N802
        return self._running

    def start(self) -> None:
        self.start_calls += 1
        self._running = True

    def deleteLater(self) -> None:  # noqa: N802
        self._running = False


class _Watcher:
    def __init__(self, files=()) -> None:
        self._files = set(files or ())
        self.add_calls: list[list[str]] = []
        self.remove_calls: list[list[str]] = []

    def files(self):
        return sorted(self._files)

    def addPaths(self, paths):  # noqa: N802
        normalized = [str(path) for path in paths]
        self.add_calls.append(normalized)
        self._files.update(normalized)

    def removePaths(self, paths):  # noqa: N802
        normalized = [str(path) for path in paths]
        self.remove_calls.append(normalized)
        for path in normalized:
            self._files.discard(path)


class UserPresetsMetadataLoadQueueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        _MetadataWorker.instances.clear()
        _SingleMetadataWorker.instances.clear()
        _RowsPlanWorker.instances.clear()

    def test_full_metadata_load_replays_latest_request_after_running_worker_finishes(self) -> None:
        from presets.user_presets_runtime_service import UserPresetsRuntimeAdapter, UserPresetsRuntimeService

        page = SimpleNamespace(isVisible=lambda: True)
        adapter = UserPresetsRuntimeAdapter(
            bulk_reset_running=lambda: False,
            read_single_metadata=lambda _name: None,
            selected_source_file_name=lambda: "",
            presets_dir=lambda: None,
            cached_metadata=lambda: {},
            load_all_metadata=lambda: {},
            load_folder_state=lambda: {},
            build_rows_plan=lambda _metadata, _folder_state: object(),
            apply_rows_plan=lambda _plan, _started_at: None,
        )
        service = UserPresetsRuntimeService()
        service.attach_page(page, adapter)

        scheduled_callbacks = []

        with patch(
            "presets.user_presets_runtime_service.UserPresetsMetadataLoadWorker",
            _MetadataWorker,
        ), patch(
            "presets.user_presets_runtime_service.QTimer.singleShot",
            side_effect=lambda _delay, callback: scheduled_callbacks.append(callback),
        ):
            service.load_presets(page)
            service.load_presets(page)

            self.assertEqual(len(_MetadataWorker.instances), 1)

            service._metadata_load_runtime.worker = None
            service._on_metadata_worker_finished(_MetadataWorker.instances[0])

            self.assertEqual(len(_MetadataWorker.instances), 1)
            self.assertEqual(len(scheduled_callbacks), 1)
            scheduled_callbacks[0]()

        self.assertEqual(len(_MetadataWorker.instances), 2)
        self.assertEqual(_MetadataWorker.instances[1].request_id, 2)
        self.assertEqual(_MetadataWorker.instances[1].start_calls, 1)

    def test_full_metadata_scheduled_restart_waits_for_event_loop_callback(self) -> None:
        from presets.user_presets_runtime_service import UserPresetsRuntimeAdapter, UserPresetsRuntimeService

        page = SimpleNamespace(isVisible=lambda: True)
        adapter = UserPresetsRuntimeAdapter(
            bulk_reset_running=lambda: False,
            read_single_metadata=lambda _name: None,
            selected_source_file_name=lambda: "",
            presets_dir=lambda: None,
            cached_metadata=lambda: {},
            load_all_metadata=lambda: {},
            load_folder_state=lambda: {},
            build_rows_plan=lambda _metadata, _folder_state: object(),
            apply_rows_plan=lambda _plan, _started_at: None,
        )
        service = UserPresetsRuntimeService()
        service.attach_page(page, adapter)
        scheduled_callbacks = []

        with patch(
            "presets.user_presets_runtime_service.UserPresetsMetadataLoadWorker",
            _MetadataWorker,
        ), patch(
            "presets.user_presets_runtime_service.QTimer.singleShot",
            side_effect=lambda _delay, callback: scheduled_callbacks.append(callback),
        ):
            service.load_presets(page)
            service.load_presets(page)
            service._metadata_load_runtime.worker = None
            service._on_metadata_worker_finished(_MetadataWorker.instances[0])
            service.load_presets(page)

            self.assertEqual(len(_MetadataWorker.instances), 1)
            self.assertEqual(len(scheduled_callbacks), 1)

            scheduled_callbacks[0]()

        self.assertEqual(len(_MetadataWorker.instances), 2)
        self.assertEqual(_MetadataWorker.instances[1].start_calls, 1)

    def test_stale_full_metadata_worker_finish_does_not_restart_pending_load(self) -> None:
        from presets.user_presets_runtime_service import UserPresetsRuntimeAdapter, UserPresetsRuntimeService

        page = SimpleNamespace(isVisible=lambda: True)
        adapter = UserPresetsRuntimeAdapter(
            bulk_reset_running=lambda: False,
            read_single_metadata=lambda _name: None,
            selected_source_file_name=lambda: "",
            presets_dir=lambda: None,
            cached_metadata=lambda: {},
            load_all_metadata=lambda: {},
            load_folder_state=lambda: {},
            build_rows_plan=lambda _metadata, _folder_state: object(),
            apply_rows_plan=lambda _plan, _started_at: None,
        )
        service = UserPresetsRuntimeService()
        service.attach_page(page, adapter)
        service._metadata_load_request_id = 2
        service._metadata_load_pending_page = page
        service._schedule_metadata_load = Mock()

        service._on_metadata_worker_finished(SimpleNamespace(_request_id=1))

        service._schedule_metadata_load.assert_not_called()
        self.assertIs(service._metadata_load_pending_page, page)

    def test_stale_full_metadata_worker_object_finish_does_not_restart_pending_load(self) -> None:
        from presets.user_presets_runtime_service import UserPresetsRuntimeAdapter, UserPresetsRuntimeService

        page = SimpleNamespace(isVisible=lambda: True)
        adapter = UserPresetsRuntimeAdapter(
            bulk_reset_running=lambda: False,
            read_single_metadata=lambda _name: None,
            selected_source_file_name=lambda: "",
            presets_dir=lambda: None,
            cached_metadata=lambda: {},
            load_all_metadata=lambda: {},
            load_folder_state=lambda: {},
            build_rows_plan=lambda _metadata, _folder_state: object(),
            apply_rows_plan=lambda _plan, _started_at: None,
        )
        service = UserPresetsRuntimeService()
        service.attach_page(page, adapter)
        service._metadata_load_runtime.worker = object()
        service._metadata_load_pending_page = page
        service._schedule_metadata_load = Mock()

        service._on_metadata_worker_finished(object())

        service._schedule_metadata_load.assert_not_called()
        self.assertIs(service._metadata_load_pending_page, page)

    def test_duplicate_single_metadata_update_skips_visible_refresh(self) -> None:
        from presets.user_presets_runtime_service import UserPresetsRuntimeAdapter, UserPresetsRuntimeService

        page = SimpleNamespace(isVisible=lambda: True)
        adapter = UserPresetsRuntimeAdapter(
            bulk_reset_running=lambda: False,
            read_single_metadata=lambda _name: None,
            selected_source_file_name=lambda: "",
            presets_dir=lambda: None,
            cached_metadata=lambda: {},
            load_all_metadata=lambda: {},
            load_folder_state=lambda: {},
            build_rows_plan=lambda _metadata, _folder_state: object(),
            apply_rows_plan=lambda _plan, _started_at: None,
        )
        service = UserPresetsRuntimeService()
        service.attach_page(page, adapter)
        metadata = {
            "display_name": "Default",
            "description": "",
            "modified_display": "today",
        }
        service._single_metadata_request_id = 3
        service._cached_presets_metadata = {"Default.txt": dict(metadata)}
        service.sync_watched_preset_files = Mock(
            side_effect=AssertionError("duplicate metadata must not resync watcher paths")
        )
        service.try_apply_single_preset_metadata_update = Mock(
            side_effect=AssertionError("duplicate metadata must not repaint preset row")
        )
        service.refresh_presets_view_from_cache = Mock(
            side_effect=AssertionError("duplicate metadata must not refresh preset list")
        )

        service._on_single_metadata_loaded(3, "Default.txt", ("Default.txt", dict(metadata)), page)

        self.assertEqual(service._cached_presets_metadata, {"Default.txt": metadata})

    def test_single_metadata_result_ignored_when_same_file_is_pending(self) -> None:
        from presets.user_presets_runtime_service import UserPresetsRuntimeAdapter, UserPresetsRuntimeService

        page = SimpleNamespace(isVisible=lambda: True)
        adapter = UserPresetsRuntimeAdapter(
            bulk_reset_running=lambda: False,
            read_single_metadata=lambda _name: None,
            selected_source_file_name=lambda: "",
            presets_dir=lambda: None,
            cached_metadata=lambda: {},
            load_all_metadata=lambda: {},
            load_folder_state=lambda: {},
            build_rows_plan=lambda _metadata, _folder_state: object(),
            apply_rows_plan=lambda _plan, _started_at: None,
        )
        service = UserPresetsRuntimeService()
        service.attach_page(page, adapter)
        service._single_metadata_request_id = 3
        service._single_metadata_pending = ["Default.txt"]
        service._cached_presets_metadata = {"Default.txt": {"display_name": "Old"}}
        service._schedule_watched_preset_files_sync = Mock()
        service.try_apply_single_preset_metadata_update = Mock()
        service.refresh_presets_view_from_cache = Mock()

        service._on_single_metadata_loaded(
            3,
            "Default.txt",
            ("Default.txt", {"display_name": "New"}),
            page,
        )

        self.assertEqual(service._cached_presets_metadata, {"Default.txt": {"display_name": "Old"}})
        service._schedule_watched_preset_files_sync.assert_not_called()
        service.try_apply_single_preset_metadata_update.assert_not_called()
        service.refresh_presets_view_from_cache.assert_not_called()

    def test_single_metadata_error_ignored_when_same_file_is_pending(self) -> None:
        import presets.user_presets_runtime_service as runtime_service
        from presets.user_presets_runtime_service import UserPresetsRuntimeAdapter, UserPresetsRuntimeService

        page = SimpleNamespace(isVisible=lambda: True)
        adapter = UserPresetsRuntimeAdapter(
            bulk_reset_running=lambda: False,
            read_single_metadata=lambda _name: None,
            selected_source_file_name=lambda: "",
            presets_dir=lambda: None,
            cached_metadata=lambda: {},
            load_all_metadata=lambda: {},
            load_folder_state=lambda: {},
            build_rows_plan=lambda _metadata, _folder_state: object(),
            apply_rows_plan=lambda _plan, _started_at: None,
        )
        service = UserPresetsRuntimeService()
        service.attach_page(page, adapter)
        service._single_metadata_request_id = 3
        service._single_metadata_pending = ["Default.txt"]
        service._ui_dirty = False
        service.schedule_presets_reload = Mock()

        with patch.object(runtime_service, "log") as log_mock:
            service._on_single_metadata_failed(3, "Default.txt", "stale error", page)

        self.assertFalse(service._ui_dirty)
        service.schedule_presets_reload.assert_not_called()
        log_mock.assert_not_called()

    def test_store_switch_defers_dirty_list_reload_after_local_active_marker_update(self) -> None:
        from presets.user_presets_runtime_service import UserPresetsRuntimeAdapter, UserPresetsRuntimeService

        page = SimpleNamespace(isVisible=lambda: True)
        page.refresh_presets_view_if_possible = Mock(
            side_effect=AssertionError("preset switch must not rebuild the list inline")
        )
        adapter = UserPresetsRuntimeAdapter(
            bulk_reset_running=lambda: False,
            read_single_metadata=lambda _name: None,
            selected_source_file_name=lambda: "Next.txt",
            presets_dir=lambda: None,
            cached_metadata=lambda: {},
            load_all_metadata=lambda: {},
            load_folder_state=lambda: {},
            build_rows_plan=lambda _metadata, _folder_state: object(),
            apply_rows_plan=lambda _plan, _started_at: None,
        )
        service = UserPresetsRuntimeService()
        service.attach_page(page, adapter)
        service._ui_dirty = True
        service.apply_active_preset_marker_for_file = Mock(return_value=True)
        service.schedule_presets_reload = Mock()

        service.on_store_switched("Next.txt", page)

        service.apply_active_preset_marker_for_file.assert_called_once_with("Next.txt", page=page)
        page.refresh_presets_view_if_possible.assert_not_called()
        service.schedule_presets_reload.assert_called_once_with(page)

    def test_store_switch_defers_dirty_list_reload_after_optimistic_marker(self) -> None:
        from presets.user_presets_runtime_service import UserPresetsRuntimeAdapter, UserPresetsRuntimeService

        page = SimpleNamespace(isVisible=lambda: True)
        page.refresh_presets_view_if_possible = Mock(
            side_effect=AssertionError("preset switch must not rebuild the list inline")
        )
        adapter = UserPresetsRuntimeAdapter(
            bulk_reset_running=lambda: False,
            read_single_metadata=lambda _name: None,
            selected_source_file_name=lambda: "Next.txt",
            presets_dir=lambda: None,
            cached_metadata=lambda: {},
            load_all_metadata=lambda: {},
            load_folder_state=lambda: {},
            build_rows_plan=lambda _metadata, _folder_state: object(),
            apply_rows_plan=lambda _plan, _started_at: None,
        )
        service = UserPresetsRuntimeService()
        service.attach_page(page, adapter)
        service._ui_dirty = True
        service.apply_active_preset_marker_for_file = Mock(return_value=False)
        service.schedule_presets_reload = Mock()

        service.on_store_switched("Next.txt", page)

        service.apply_active_preset_marker_for_file.assert_called_once_with("Next.txt", page=page)
        page.refresh_presets_view_if_possible.assert_not_called()
        service.schedule_presets_reload.assert_called_once_with(page)

    def test_metadata_loaded_defers_watcher_sync_after_rows_request(self) -> None:
        from presets.user_presets_runtime_service import UserPresetsRuntimeAdapter, UserPresetsRuntimeService

        page = SimpleNamespace(isVisible=lambda: True)
        adapter = UserPresetsRuntimeAdapter(
            bulk_reset_running=lambda: False,
            read_single_metadata=lambda _name: None,
            selected_source_file_name=lambda: "",
            presets_dir=lambda: None,
            cached_metadata=lambda: {},
            load_all_metadata=lambda: {},
            load_folder_state=lambda: {},
            build_rows_plan=lambda _metadata, _folder_state: object(),
            apply_rows_plan=lambda _plan, _started_at: None,
        )
        service = UserPresetsRuntimeService()
        service.attach_page(page, adapter)
        service._metadata_load_request_id = 7
        calls: list[str] = []
        service.sync_watched_preset_files = Mock(side_effect=lambda *_args, **_kwargs: calls.append("watcher"))
        service._request_rows_plan_refresh = Mock(side_effect=lambda *_args, **_kwargs: calls.append("rows"))

        service._on_metadata_loaded(7, {"Default.txt": {}}, {}, 0.0, page)

        self.assertEqual(calls, ["rows"])
        self._app.processEvents()
        self.assertEqual(calls, ["rows", "watcher"])

    def test_metadata_load_result_ignored_when_new_load_is_pending(self) -> None:
        from presets.user_presets_runtime_service import UserPresetsRuntimeAdapter, UserPresetsRuntimeService

        page = SimpleNamespace(isVisible=lambda: True)
        adapter = UserPresetsRuntimeAdapter(
            bulk_reset_running=lambda: False,
            read_single_metadata=lambda _name: None,
            selected_source_file_name=lambda: "",
            presets_dir=lambda: None,
            cached_metadata=lambda: {},
            load_all_metadata=lambda: {},
            load_folder_state=lambda: {},
            build_rows_plan=lambda _metadata, _folder_state: object(),
            apply_rows_plan=lambda _plan, _started_at: None,
        )
        service = UserPresetsRuntimeService()
        service.attach_page(page, adapter)
        service._metadata_load_request_id = 7
        service._metadata_load_pending_page = page
        service._cached_presets_metadata = {"Old.txt": {}}
        service._cached_folder_state = {"items": {"Old.txt": {}}}
        service._schedule_watched_preset_files_sync = Mock()
        service._request_rows_plan_refresh = Mock()

        service._on_metadata_loaded(7, {"New.txt": {}}, {"items": {"New.txt": {}}}, 1.5, page)

        self.assertEqual(service._cached_presets_metadata, {"Old.txt": {}})
        self.assertEqual(service._cached_folder_state, {"items": {"Old.txt": {}}})
        service._schedule_watched_preset_files_sync.assert_not_called()
        service._request_rows_plan_refresh.assert_not_called()

    def test_metadata_load_error_ignored_when_new_load_is_pending(self) -> None:
        import presets.user_presets_runtime_service as runtime_service
        from presets.user_presets_runtime_service import UserPresetsRuntimeAdapter, UserPresetsRuntimeService

        page = SimpleNamespace(isVisible=lambda: True)
        adapter = UserPresetsRuntimeAdapter(
            bulk_reset_running=lambda: False,
            read_single_metadata=lambda _name: None,
            selected_source_file_name=lambda: "",
            presets_dir=lambda: None,
            cached_metadata=lambda: {},
            load_all_metadata=lambda: {},
            load_folder_state=lambda: {},
            build_rows_plan=lambda _metadata, _folder_state: object(),
            apply_rows_plan=lambda _plan, _started_at: None,
        )
        service = UserPresetsRuntimeService()
        service.attach_page(page, adapter)
        service._metadata_load_request_id = 7
        service._metadata_load_pending_page = page
        service._ui_dirty = False

        with patch.object(runtime_service, "log") as log_mock:
            service._on_metadata_failed(7, "stale error", page)

        self.assertFalse(service._ui_dirty)
        log_mock.assert_not_called()

    def test_single_metadata_pending_refresh_restarts_after_worker_signal_returns(self) -> None:
        from presets.user_presets_runtime_service import UserPresetsRuntimeAdapter, UserPresetsRuntimeService

        page = SimpleNamespace(isVisible=lambda: True)
        adapter = UserPresetsRuntimeAdapter(
            bulk_reset_running=lambda: False,
            read_single_metadata=lambda _name: None,
            selected_source_file_name=lambda: "",
            presets_dir=lambda: None,
            cached_metadata=lambda: {},
            load_all_metadata=lambda: {},
            load_folder_state=lambda: {},
            build_rows_plan=lambda _metadata, _folder_state: object(),
            apply_rows_plan=lambda _plan, _started_at: None,
        )
        service = UserPresetsRuntimeService()
        service.attach_page(page, adapter)
        worker = SimpleNamespace(deleteLater=Mock())
        service._single_metadata_worker = worker
        service._single_metadata_pending = ["Default.txt"]
        service._request_single_metadata_refresh = Mock()
        scheduled_callbacks = []

        with patch(
            "presets.user_presets_runtime_service.QTimer.singleShot",
            side_effect=lambda _delay, callback: scheduled_callbacks.append(callback),
        ):
            service._on_single_metadata_worker_finished(worker, page)

        service._request_single_metadata_refresh.assert_not_called()
        self.assertEqual(len(scheduled_callbacks), 1)

        scheduled_callbacks[0]()

        service._request_single_metadata_refresh.assert_called_once_with("Default.txt", page)

    def test_stale_single_metadata_worker_finish_does_not_restart_pending_refresh(self) -> None:
        from presets.user_presets_runtime_service import UserPresetsRuntimeAdapter, UserPresetsRuntimeService

        page = SimpleNamespace(isVisible=lambda: True)
        adapter = UserPresetsRuntimeAdapter(
            bulk_reset_running=lambda: False,
            read_single_metadata=lambda _name: None,
            selected_source_file_name=lambda: "",
            presets_dir=lambda: None,
            cached_metadata=lambda: {},
            load_all_metadata=lambda: {},
            load_folder_state=lambda: {},
            build_rows_plan=lambda _metadata, _folder_state: object(),
            apply_rows_plan=lambda _plan, _started_at: None,
        )
        service = UserPresetsRuntimeService()
        service.attach_page(page, adapter)
        service._single_metadata_request_id = 2
        service._single_metadata_pending = ["Default.txt"]
        service._request_single_metadata_refresh = Mock()
        single_shot = Mock()

        with patch(
            "presets.user_presets_runtime_service.QTimer.singleShot",
            single_shot,
        ):
            service._on_single_metadata_worker_finished(SimpleNamespace(_request_id=1), page)

        single_shot.assert_not_called()
        service._request_single_metadata_refresh.assert_not_called()
        self.assertEqual(service._single_metadata_pending, ["Default.txt"])

    def test_stale_single_metadata_worker_object_finish_does_not_restart_pending_refresh(self) -> None:
        from presets.user_presets_runtime_service import UserPresetsRuntimeAdapter, UserPresetsRuntimeService

        page = SimpleNamespace(isVisible=lambda: True)
        adapter = UserPresetsRuntimeAdapter(
            bulk_reset_running=lambda: False,
            read_single_metadata=lambda _name: None,
            selected_source_file_name=lambda: "",
            presets_dir=lambda: None,
            cached_metadata=lambda: {},
            load_all_metadata=lambda: {},
            load_folder_state=lambda: {},
            build_rows_plan=lambda _metadata, _folder_state: object(),
            apply_rows_plan=lambda _plan, _started_at: None,
        )
        service = UserPresetsRuntimeService()
        service.attach_page(page, adapter)
        service._single_metadata_runtime.worker = object()
        service._single_metadata_pending = ["Default.txt"]
        service._request_single_metadata_refresh = Mock()
        single_shot = Mock()

        with patch(
            "presets.user_presets_runtime_service.QTimer.singleShot",
            single_shot,
        ):
            service._on_single_metadata_worker_finished(object(), page)

        single_shot.assert_not_called()
        service._request_single_metadata_refresh.assert_not_called()
        self.assertEqual(service._single_metadata_pending, ["Default.txt"])

    def test_single_metadata_scheduled_restart_queues_next_file_without_immediate_worker(self) -> None:
        from presets.user_presets_runtime_service import UserPresetsRuntimeAdapter, UserPresetsRuntimeService

        page = SimpleNamespace(isVisible=lambda: True)
        adapter = UserPresetsRuntimeAdapter(
            bulk_reset_running=lambda: False,
            read_single_metadata=lambda _name: None,
            selected_source_file_name=lambda: "",
            presets_dir=lambda: None,
            cached_metadata=lambda: {},
            load_all_metadata=lambda: {},
            load_folder_state=lambda: {},
            build_rows_plan=lambda _metadata, _folder_state: object(),
            apply_rows_plan=lambda _plan, _started_at: None,
        )
        service = UserPresetsRuntimeService()
        service.attach_page(page, adapter)
        worker = SimpleNamespace(deleteLater=Mock())
        service._single_metadata_worker = worker
        service._single_metadata_pending = ["First.txt"]
        scheduled_callbacks = []

        with patch(
            "presets.user_presets_runtime_service.UserPresetsSingleMetadataWorker",
            _SingleMetadataWorker,
        ), patch(
            "presets.user_presets_runtime_service.QTimer.singleShot",
            side_effect=lambda _delay, callback: scheduled_callbacks.append(callback),
        ):
            service._on_single_metadata_worker_finished(worker, page)
            service._request_single_metadata_refresh("Second.txt", page)

            self.assertEqual(_SingleMetadataWorker.instances, [])
            self.assertEqual(service._single_metadata_pending, ["First.txt", "Second.txt"])

            scheduled_callbacks[0]()

        self.assertEqual([worker.file_name for worker in _SingleMetadataWorker.instances], ["First.txt"])
        self.assertEqual(service._single_metadata_pending, ["Second.txt"])

    def test_rows_plan_pending_refresh_restarts_after_worker_signal_returns(self) -> None:
        from presets.user_presets_runtime_service import UserPresetsRuntimeAdapter, UserPresetsRuntimeService

        page = SimpleNamespace(isVisible=lambda: True)
        adapter = UserPresetsRuntimeAdapter(
            bulk_reset_running=lambda: False,
            read_single_metadata=lambda _name: None,
            selected_source_file_name=lambda: "",
            presets_dir=lambda: None,
            cached_metadata=lambda: {},
            load_all_metadata=lambda: {},
            load_folder_state=lambda: {},
            build_rows_plan=lambda _metadata, _folder_state: object(),
            apply_rows_plan=lambda _plan, _started_at: None,
        )
        service = UserPresetsRuntimeService()
        service.attach_page(page, adapter)
        worker = SimpleNamespace(deleteLater=Mock())
        service._rows_plan_worker = worker
        service._rows_plan_pending = ({"Default.txt": {}}, {"items": {}}, 1.5, page)
        service._request_rows_plan_refresh = Mock()
        scheduled_callbacks = []

        with patch(
            "presets.user_presets_runtime_service.QTimer.singleShot",
            side_effect=lambda _delay, callback: scheduled_callbacks.append(callback),
        ):
            service._on_rows_plan_worker_finished(worker)

        service._request_rows_plan_refresh.assert_not_called()
        self.assertEqual(len(scheduled_callbacks), 1)

        scheduled_callbacks[0]()

        service._request_rows_plan_refresh.assert_called_once_with({"Default.txt": {}}, {"items": {}}, 1.5, page)

    def test_stale_rows_plan_worker_finish_does_not_restart_pending_refresh(self) -> None:
        from presets.user_presets_runtime_service import UserPresetsRuntimeAdapter, UserPresetsRuntimeService

        page = SimpleNamespace(isVisible=lambda: True)
        adapter = UserPresetsRuntimeAdapter(
            bulk_reset_running=lambda: False,
            read_single_metadata=lambda _name: None,
            selected_source_file_name=lambda: "",
            presets_dir=lambda: None,
            cached_metadata=lambda: {},
            load_all_metadata=lambda: {},
            load_folder_state=lambda: {},
            build_rows_plan=lambda _metadata, _folder_state: object(),
            apply_rows_plan=lambda _plan, _started_at: None,
        )
        service = UserPresetsRuntimeService()
        service.attach_page(page, adapter)
        service._rows_plan_request_id = 2
        service._rows_plan_pending = ({"Default.txt": {}}, {"items": {}}, 1.5, page)
        service._request_rows_plan_refresh = Mock()
        single_shot = Mock()

        with patch(
            "presets.user_presets_runtime_service.QTimer.singleShot",
            single_shot,
        ):
            service._on_rows_plan_worker_finished(SimpleNamespace(_request_id=1))

        single_shot.assert_not_called()
        service._request_rows_plan_refresh.assert_not_called()
        self.assertEqual(service._rows_plan_pending, ({"Default.txt": {}}, {"items": {}}, 1.5, page))

    def test_stale_rows_plan_worker_object_finish_does_not_restart_pending_refresh(self) -> None:
        from presets.user_presets_runtime_service import UserPresetsRuntimeAdapter, UserPresetsRuntimeService

        page = SimpleNamespace(isVisible=lambda: True)
        adapter = UserPresetsRuntimeAdapter(
            bulk_reset_running=lambda: False,
            read_single_metadata=lambda _name: None,
            selected_source_file_name=lambda: "",
            presets_dir=lambda: None,
            cached_metadata=lambda: {},
            load_all_metadata=lambda: {},
            load_folder_state=lambda: {},
            build_rows_plan=lambda _metadata, _folder_state: object(),
            apply_rows_plan=lambda _plan, _started_at: None,
        )
        service = UserPresetsRuntimeService()
        service.attach_page(page, adapter)
        service._rows_plan_runtime.worker = object()
        service._rows_plan_pending = ({"Default.txt": {}}, {"items": {}}, 1.5, page)
        service._request_rows_plan_refresh = Mock()
        single_shot = Mock()

        with patch(
            "presets.user_presets_runtime_service.QTimer.singleShot",
            single_shot,
        ):
            service._on_rows_plan_worker_finished(object())

        single_shot.assert_not_called()
        service._request_rows_plan_refresh.assert_not_called()
        self.assertEqual(service._rows_plan_pending, ({"Default.txt": {}}, {"items": {}}, 1.5, page))

    def test_rows_plan_scheduled_restart_uses_latest_pending_request(self) -> None:
        from presets.user_presets_runtime_service import UserPresetsRuntimeAdapter, UserPresetsRuntimeService

        page = SimpleNamespace(isVisible=lambda: True)
        adapter = UserPresetsRuntimeAdapter(
            bulk_reset_running=lambda: False,
            read_single_metadata=lambda _name: None,
            selected_source_file_name=lambda: "",
            presets_dir=lambda: None,
            cached_metadata=lambda: {},
            load_all_metadata=lambda: {},
            load_folder_state=lambda: {},
            build_rows_plan=lambda _metadata, _folder_state: object(),
            apply_rows_plan=lambda _plan, _started_at: None,
        )
        service = UserPresetsRuntimeService()
        service.attach_page(page, adapter)
        worker = SimpleNamespace(deleteLater=Mock())
        service._rows_plan_worker = worker
        service._rows_plan_pending = ({"Old.txt": {}}, {"items": {}}, 1.5, page)
        scheduled_callbacks = []

        with patch(
            "presets.user_presets_runtime_service.UserPresetsRowsPlanWorker",
            _RowsPlanWorker,
        ), patch(
            "presets.user_presets_runtime_service.QTimer.singleShot",
            side_effect=lambda _delay, callback: scheduled_callbacks.append(callback),
        ):
            service._on_rows_plan_worker_finished(worker)
            service._request_rows_plan_refresh({"Latest.txt": {}}, {"items": {"Latest.txt": {}}}, 2.5, page)

            self.assertEqual(_RowsPlanWorker.instances, [])
            self.assertEqual(len(scheduled_callbacks), 1)

            scheduled_callbacks[0]()

        self.assertEqual(len(_RowsPlanWorker.instances), 1)
        self.assertEqual(_RowsPlanWorker.instances[0].all_presets, {"Latest.txt": {}})
        self.assertEqual(_RowsPlanWorker.instances[0].started_at, 2.5)

    def test_rows_plan_result_ignored_when_new_plan_is_pending(self) -> None:
        from presets.user_presets_runtime_service import UserPresetsRuntimeAdapter, UserPresetsRuntimeService

        page = SimpleNamespace(isVisible=lambda: True)
        adapter = UserPresetsRuntimeAdapter(
            bulk_reset_running=lambda: False,
            read_single_metadata=lambda _name: None,
            selected_source_file_name=lambda: "",
            presets_dir=lambda: None,
            cached_metadata=lambda: {},
            load_all_metadata=lambda: {},
            load_folder_state=lambda: {},
            build_rows_plan=lambda _metadata, _folder_state: object(),
            apply_rows_plan=lambda _plan, _started_at: None,
        )
        service = UserPresetsRuntimeService()
        service.attach_page(page, adapter)
        service._rows_plan_request_id = 4
        service._rows_plan_pending = ({"Latest.txt": {}}, {"items": {}}, 2.5, page)
        service._schedule_rows_plan_apply = Mock()

        service._on_rows_plan_loaded(4, "old-plan", 1.5, page)

        service._schedule_rows_plan_apply.assert_not_called()

    def test_pending_rows_plan_apply_is_ignored_when_new_plan_is_pending(self) -> None:
        from presets.user_presets_runtime_service import UserPresetsRuntimeAdapter, UserPresetsRuntimeService

        page = SimpleNamespace(isVisible=lambda: True)
        adapter = UserPresetsRuntimeAdapter(
            bulk_reset_running=lambda: False,
            read_single_metadata=lambda _name: None,
            selected_source_file_name=lambda: "",
            presets_dir=lambda: None,
            cached_metadata=lambda: {},
            load_all_metadata=lambda: {},
            load_folder_state=lambda: {},
            build_rows_plan=lambda _metadata, _folder_state: object(),
            apply_rows_plan=Mock(),
        )
        service = UserPresetsRuntimeService()
        service.attach_page(page, adapter)
        service._pending_rows_plan_apply = ("old-plan", 1.5, page)
        service._rows_plan_apply_scheduled = True
        service._rows_plan_pending = ({"Latest.txt": {}}, {"items": {}}, 2.5, page)

        service._run_scheduled_rows_plan_apply()

        adapter.apply_rows_plan.assert_not_called()

    def test_rows_plan_error_ignored_when_new_plan_is_pending(self) -> None:
        import presets.user_presets_runtime_service as runtime_service
        from presets.user_presets_runtime_service import UserPresetsRuntimeAdapter, UserPresetsRuntimeService

        page = SimpleNamespace(isVisible=lambda: True)
        adapter = UserPresetsRuntimeAdapter(
            bulk_reset_running=lambda: False,
            read_single_metadata=lambda _name: None,
            selected_source_file_name=lambda: "",
            presets_dir=lambda: None,
            cached_metadata=lambda: {},
            load_all_metadata=lambda: {},
            load_folder_state=lambda: {},
            build_rows_plan=lambda _metadata, _folder_state: object(),
            apply_rows_plan=lambda _plan, _started_at: None,
        )
        service = UserPresetsRuntimeService()
        service.attach_page(page, adapter)
        service._rows_plan_request_id = 4
        service._rows_plan_pending = ({"Latest.txt": {}}, {"items": {}}, 2.5, page)
        service._ui_dirty = False

        with patch.object(runtime_service, "log") as log_mock:
            service._on_rows_plan_failed(4, "old error", page)

        self.assertFalse(service._ui_dirty)
        log_mock.assert_not_called()

    def test_remove_deleted_preset_locally_does_not_write_folder_meta_from_gui_path(self) -> None:
        from presets.user_presets_runtime_service import UserPresetsRuntimeAdapter, UserPresetsRuntimeService

        model = Mock()
        model.remove_preset.return_value = True
        page = SimpleNamespace(isVisible=lambda: True, _presets_model=model)
        adapter = UserPresetsRuntimeAdapter(
            bulk_reset_running=lambda: False,
            read_single_metadata=lambda _name: None,
            selected_source_file_name=lambda: "",
            presets_dir=lambda: None,
            cached_metadata=lambda: {},
            load_all_metadata=lambda: {},
            load_folder_state=lambda: {},
            build_rows_plan=lambda _metadata, _folder_state: object(),
            apply_rows_plan=lambda _plan, _started_at: None,
        )
        service = UserPresetsRuntimeService()
        service.attach_page(page, adapter)
        service._cached_presets_metadata = {"Deleted.txt": {}}
        service.sync_watched_preset_files = Mock()

        self.assertTrue(service.remove_deleted_preset_locally("Deleted.txt", page))

        self.assertFalse(hasattr(adapter, "delete_preset_item_meta"))

    def test_watched_preset_files_sync_merges_pending_file_sets(self) -> None:
        from presets.user_presets_runtime_service import UserPresetsRuntimeService

        import presets.user_presets_runtime_service as runtime_service

        page = SimpleNamespace()
        service = UserPresetsRuntimeService()
        service.sync_watched_preset_files = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(runtime_service, "QTimer", SimpleNamespace(singleShot=single_shot)):
            service._schedule_watched_preset_files_sync(page, {"Alpha.txt", "Beta.txt"})
            service._schedule_watched_preset_files_sync(page, {"Beta.txt", "Gamma.txt"})

        single_shot.assert_called_once()

        single_shot.call_args.args[1]()

        service.sync_watched_preset_files.assert_called_once_with(
            page,
            {"Alpha.txt", "Beta.txt", "Gamma.txt"},
        )

    def test_watched_preset_files_sync_runs_in_small_gui_batches(self) -> None:
        from pathlib import Path

        from presets.user_presets_runtime_service import UserPresetsRuntimeAdapter, UserPresetsRuntimeService

        import presets.user_presets_runtime_service as runtime_service

        page = SimpleNamespace()
        presets_dir = Path("/tmp/presets")
        adapter = UserPresetsRuntimeAdapter(
            bulk_reset_running=lambda: False,
            read_single_metadata=lambda _name: None,
            selected_source_file_name=lambda: "",
            presets_dir=lambda: presets_dir,
            cached_metadata=lambda: {},
            load_all_metadata=lambda: {},
            load_folder_state=lambda: {},
            build_rows_plan=lambda _metadata, _folder_state: object(),
            apply_rows_plan=lambda _plan, _started_at: None,
        )
        service = UserPresetsRuntimeService()
        service.attach_page(page, adapter)
        service._file_watcher = _Watcher()
        service._watched_preset_files_sync_batch_size = 2
        callbacks = []

        with patch.object(
            runtime_service,
            "QTimer",
            SimpleNamespace(singleShot=lambda _delay, callback: callbacks.append(callback)),
        ):
            service.sync_watched_preset_files(
                page,
                {"Alpha.txt", "Beta.txt", "Gamma.txt", "Omega.txt", "Zeta.txt"},
            )

            self.assertEqual(
                service._file_watcher.add_calls,
                [[str(presets_dir / "Alpha.txt"), str(presets_dir / "Beta.txt")]],
            )
            self.assertEqual(len(callbacks), 1)

            callbacks.pop(0)()

            self.assertEqual(
                service._file_watcher.add_calls[1],
                [str(presets_dir / "Gamma.txt"), str(presets_dir / "Omega.txt")],
            )
            self.assertEqual(len(callbacks), 1)

            callbacks.pop(0)()

        self.assertEqual(
            service._file_watcher.add_calls[2],
            [str(presets_dir / "Zeta.txt")],
        )
        self.assertEqual(callbacks, [])


if __name__ == "__main__":
    unittest.main()
