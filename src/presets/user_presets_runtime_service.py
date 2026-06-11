from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
import time
import weakref

from PyQt6.QtCore import QThread, QTimer, pyqtSignal

from log.log import log
from presets.icon_color import normalize_preset_icon_color
from ui.latest_value_worker_state import LatestValueWorkerState
from ui.one_shot_worker_runtime import OneShotWorkerRuntime
from ui.queued_worker_state import QueuedWorkerState


USER_PRESETS_TIMING_LOG_LEVEL = "⏱ PRESETS"
USER_PRESETS_VISIBLE_TIMING_LABELS = frozenset(
    {
        "user_presets.rows_plan.build",
        "user_presets.rows_plan.apply",
    }
)


def _log_user_presets_timing(label: str, started_at: float, *, extra: str = "") -> None:
    try:
        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        extra_text = f" | {extra}" if extra else ""
        level = USER_PRESETS_TIMING_LOG_LEVEL if label in USER_PRESETS_VISIBLE_TIMING_LABELS else "DEBUG"
        log(f"{label}: {elapsed_ms:.1f}ms{extra_text}", level)
    except Exception:
        pass


@dataclass(slots=True)
class UserPresetsRuntimeAdapter:
    bulk_reset_running: Callable[[], bool]
    read_single_metadata: Callable[[str], tuple[str, dict[str, object]] | None]
    selected_source_file_name: Callable[[], str]
    presets_dir: Callable[[], Path]
    cached_metadata: Callable[[], dict[str, dict[str, object]] | None]
    load_all_metadata: Callable[[], dict[str, dict[str, object]]]
    load_folder_state: Callable[[], dict[str, Any]]
    build_rows_plan: Callable[..., object]
    apply_rows_plan: Callable[[object, float | None], None]


@dataclass(slots=True)
class UserPresetsWatcherSyncPlan:
    remove_paths: list[str]
    add_paths: list[str]


class UserPresetsMetadataLoadWorker(QThread):
    loaded = pyqtSignal(int, dict, dict, float)
    failed = pyqtSignal(int, str)

    def __init__(
        self,
        request_id: int,
        load_all_metadata: Callable[[], dict[str, dict[str, object]]],
        load_folder_state: Callable[[], dict[str, Any]],
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._load_all_metadata = load_all_metadata
        self._load_folder_state = load_folder_state

    def run(self) -> None:
        import time

        started_at = time.perf_counter()
        try:
            all_presets = dict(self._load_all_metadata())
            folder_state = dict(self._load_folder_state() or {})
            elapsed_ms = (time.perf_counter() - started_at) * 1000.0
            log(f"user_presets.metadata.read: {elapsed_ms:.1f}ms ({len(all_presets)} presets)", "DEBUG")
        except Exception as exc:
            self.failed.emit(self._request_id, str(exc))
            return
        self.loaded.emit(self._request_id, all_presets, folder_state, started_at)


class UserPresetsSingleMetadataWorker(QThread):
    loaded = pyqtSignal(int, str, object)
    failed = pyqtSignal(int, str, str)

    def __init__(
        self,
        request_id: int,
        file_name: str,
        read_single_metadata: Callable[[str], tuple[str, dict[str, object]] | None],
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._file_name = str(file_name or "").strip()
        self._read_single_metadata = read_single_metadata

    def run(self) -> None:
        try:
            refreshed = self._read_single_metadata(self._file_name)
        except Exception as exc:
            self.failed.emit(self._request_id, self._file_name, str(exc))
            return
        self.loaded.emit(self._request_id, self._file_name, refreshed)


class UserPresetsRowsPlanWorker(QThread):
    loaded = pyqtSignal(int, object, object)
    failed = pyqtSignal(int, str)

    def __init__(
        self,
        request_id: int,
        build_rows_plan,
        *,
        all_presets: dict[str, dict[str, object]],
        query: str,
        selected_source_file_name: Callable[[], str],
        language: str,
        folder_state: dict[str, Any] | None = None,
        started_at: float | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._build_rows_plan = build_rows_plan
        self._all_presets = dict(all_presets or {})
        self._query = str(query or "")
        self._selected_source_file_name = selected_source_file_name
        self._language = str(language or "")
        self._folder_state = dict(folder_state or {})
        self._started_at = started_at

    def run(self) -> None:
        started_at = time.perf_counter()
        try:
            active_file_name = str(self._selected_source_file_name() or "").strip()
            plan = self._build_rows_plan(
                all_presets=self._all_presets,
                query=self._query,
                active_file_name=active_file_name,
                language=self._language,
                folder_state=self._folder_state,
            )
            _log_user_presets_timing(
                "user_presets.rows_plan.build",
                started_at,
                extra=f"{len(self._all_presets)} presets",
            )
        except Exception as exc:
            self.failed.emit(self._request_id, str(exc))
            return
        self.loaded.emit(self._request_id, plan, self._started_at)


class UserPresetsWatcherSyncPlanWorker(QThread):
    loaded = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(
        self,
        request_id: int,
        *,
        presets_dir: Path,
        file_names: set[str],
        current_paths: set[str],
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._presets_dir = Path(presets_dir)
        self._file_names = {
            str(file_name or "").strip()
            for file_name in (file_names or set())
            if str(file_name or "").strip()
        }
        self._current_paths = {str(path or "").strip() for path in (current_paths or set()) if str(path or "").strip()}

    def run(self) -> None:
        try:
            desired_paths = {
                str(self._presets_dir / file_name)
                for file_name in self._file_names
                if file_name
            }
            current_paths = set(self._current_paths)
            plan = UserPresetsWatcherSyncPlan(
                remove_paths=sorted(current_paths - desired_paths),
                add_paths=sorted(desired_paths - current_paths),
            )
        except Exception as exc:
            self.failed.emit(self._request_id, str(exc))
            return
        self.loaded.emit(self._request_id, plan)


class UserPresetsRuntimeService:
    def __init__(self, *, scope_key: str = "") -> None:
        self._scope_key = str(scope_key or "").strip()
        self._ui_dirty = True
        self._cached_presets_metadata: dict[str, dict[str, object]] = {}
        self._cached_folder_state: dict[str, Any] | None = None
        self._file_watcher = None
        self._watcher_active = False
        self._watcher_reload_timer = None
        self._attached_page_ref = None
        self._attached_adapter: UserPresetsRuntimeAdapter | None = None
        self._metadata_load_request_id = 0
        self._metadata_load_runtime = OneShotWorkerRuntime()
        self._metadata_load_state = LatestValueWorkerState(self._metadata_load_runtime, empty_value=None)
        self._single_metadata_request_id = 0
        self._single_metadata_runtime = OneShotWorkerRuntime()
        self._single_metadata_state = QueuedWorkerState[str](self._single_metadata_runtime)
        self._rows_plan_request_id = 0
        self._rows_plan_runtime = OneShotWorkerRuntime()
        self._rows_plan_state = LatestValueWorkerState(self._rows_plan_runtime, empty_value=None, pending=None)
        self._rows_plan_apply_scheduled = False
        self._pending_rows_plan_apply: tuple[object, float | None, object] | None = None
        self._watched_preset_files_sync_state = LatestValueWorkerState(None, empty_value=None, pending=None)
        self._watched_preset_files_sync_batch_state = LatestValueWorkerState(None, empty_value=None, pending=None)
        self._watched_preset_files_sync_batch_size = 64
        self._watched_preset_files_sync_plan_request_id = 0
        self._watched_preset_files_sync_plan_runtime = OneShotWorkerRuntime()
        self._watched_preset_files_sync_plan_state = LatestValueWorkerState(
            self._watched_preset_files_sync_plan_runtime,
            empty_value=None,
            pending=None,
        )

    def is_ui_dirty(self) -> bool:
        return bool(self._ui_dirty)

    def set_ui_dirty(self, value: bool) -> None:
        self._ui_dirty = bool(value)

    def cached_presets_metadata(self) -> dict[str, dict[str, object]]:
        return self._cached_presets_metadata

    def cached_folder_state(self) -> dict[str, Any] | None:
        return dict(self._cached_folder_state) if self._cached_folder_state is not None else None

    def update_cached_folder_state(self, folder_state: dict[str, Any] | None) -> None:
        if isinstance(folder_state, dict):
            self._cached_folder_state = dict(folder_state)

    @staticmethod
    def _make_page_ref(page):
        try:
            return weakref.ref(page)
        except TypeError:
            return lambda: page

    def _resolve_page(self, page=None):
        if page is not None:
            return page
        try:
            if self._attached_page_ref is not None:
                resolved = self._attached_page_ref()
                if resolved is not None:
                    return resolved
        except Exception:
            pass
        raise RuntimeError("user presets page is not attached")

    def _resolve_adapter(self, adapter: UserPresetsRuntimeAdapter | None = None) -> UserPresetsRuntimeAdapter:
        if adapter is not None:
            return adapter
        attached = self._attached_adapter
        if attached is not None:
            return attached
        raise RuntimeError("user presets runtime adapter is not attached")

    def attach_page(self, page, adapter: UserPresetsRuntimeAdapter) -> None:
        current_page = None
        try:
            if self._attached_page_ref is not None:
                current_page = self._attached_page_ref()
        except Exception:
            current_page = None

        self._attached_adapter = adapter
        if current_page is page and self._watcher_reload_timer is not None:
            return
        self._attached_page_ref = self._make_page_ref(page)
        try:
            from PyQt6.QtCore import QTimer

            timer = QTimer(page)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda p=page: self.reload_presets_from_watcher(p))
            self._watcher_reload_timer = timer
        except Exception:
            self._watcher_reload_timer = None

    def on_store_changed(self, page=None) -> None:
        page = self._resolve_page(page)
        _ = self._resolve_adapter()
        self.mark_presets_structure_changed(page)

    def mark_presets_structure_changed(self, page=None) -> None:
        page = self._resolve_page(page)
        adapter = self._resolve_adapter()
        self._ui_dirty = True
        if adapter.bulk_reset_running():
            return
        if page.isVisible():
            self.schedule_presets_reload(page, 0)

    def on_ui_state_changed(self, _state, changed_fields: frozenset[str], page=None) -> None:
        if "preset_structure_revision" in changed_fields:
            self.mark_presets_structure_changed(page)

    def on_store_content_changed(self, file_name: str, page=None) -> None:
        page = self._resolve_page(page)
        adapter = self._resolve_adapter()
        if adapter.bulk_reset_running():
            return

        self._request_single_metadata_refresh(file_name, page)

    def _request_single_metadata_refresh(self, file_name: str, page=None) -> None:
        page = self._resolve_page(page)
        adapter = self._resolve_adapter()
        normalized_file_name = str(file_name or "").strip()
        if not normalized_file_name:
            return

        state = self._single_metadata_state_obj()
        if state.is_busy():
            self._queue_single_metadata_refresh(normalized_file_name)
            return

        self._start_single_metadata_refresh_worker(normalized_file_name, page)

    def _queue_single_metadata_refresh(self, file_name: str) -> None:
        normalized_file_name = str(file_name or "").strip()
        if not normalized_file_name:
            return
        state = self._single_metadata_state_obj()
        if normalized_file_name not in state.pending:
            state.pending.append(normalized_file_name)

    def _start_single_metadata_refresh_worker(self, file_name: str, page=None) -> None:
        page = self._resolve_page(page)
        adapter = self._resolve_adapter()
        normalized_file_name = str(file_name or "").strip()
        if not normalized_file_name:
            return

        def bind_worker(worker) -> None:
            worker.loaded.connect(
                lambda rid, changed_file_name, refreshed, p=page: self._on_single_metadata_loaded(
                    rid,
                    changed_file_name,
                    refreshed,
                    p,
                )
            )
            worker.failed.connect(
                lambda rid, changed_file_name, error, p=page: self._on_single_metadata_failed(
                    rid,
                    changed_file_name,
                    error,
                    p,
                )
            )

        request_id, _worker = self._single_metadata_runtime.start_qthread_worker(
            worker_factory=lambda request_id: UserPresetsSingleMetadataWorker(
                request_id,
                normalized_file_name,
                adapter.read_single_metadata,
                page,
            ),
            bind_worker=bind_worker,
            on_finished=lambda worker, p=page: self._on_single_metadata_worker_finished(worker, p),
        )
        self._single_metadata_request_id = request_id

    def _on_single_metadata_loaded(self, request_id: int, file_name: str, refreshed, page=None) -> None:
        if request_id != self._single_metadata_request_id:
            return
        if str(file_name or "").strip() in self._single_metadata_state_obj().pending:
            return
        page = self._resolve_page(page)
        adapter = self._resolve_adapter()
        if refreshed is None:
            self._ui_dirty = True
            if page.isVisible():
                self.schedule_presets_reload(page, 0)
            return

        normalized_file_name, metadata = refreshed
        metadata = dict(metadata or {})
        had_cached_metadata = normalized_file_name in self._cached_presets_metadata
        previous_metadata = dict(self._cached_presets_metadata.get(normalized_file_name) or {})
        if had_cached_metadata and previous_metadata == metadata:
            return
        self._cached_presets_metadata[normalized_file_name] = metadata
        self._schedule_watched_preset_files_sync(page)
        if page.isVisible():
            if self.try_apply_single_preset_metadata_update(
                normalized_file_name,
                previous_metadata=previous_metadata,
                next_metadata=metadata,
                page=page,
            ):
                return
            self.refresh_presets_view_from_cache(page)
        else:
            self._ui_dirty = True

    def _on_single_metadata_failed(self, request_id: int, file_name: str, error: str, page=None) -> None:
        if request_id != self._single_metadata_request_id:
            return
        if str(file_name or "").strip() in self._single_metadata_state_obj().pending:
            return
        page = self._resolve_page(page)
        self._ui_dirty = True
        log(f"Ошибка обновления metadata preset-а {file_name}: {error}", "ERROR")
        if page.isVisible():
            self.schedule_presets_reload(page, 0)

    def _on_single_metadata_worker_finished(self, worker: UserPresetsSingleMetadataWorker, page=None) -> None:
        if not self._is_current_worker_finish(worker, "_single_metadata_request_id"):
            return
        if self._single_metadata_state_obj().has_pending():
            self._schedule_single_metadata_refresh(page)

    def _schedule_single_metadata_refresh(self, page=None) -> None:
        state = self._single_metadata_state_obj()
        if state.start_scheduled:
            return
        state.start_scheduled = True
        try:
            QTimer.singleShot(0, lambda p=page: self._run_scheduled_single_metadata_refresh(p))
        except Exception:
            self._run_scheduled_single_metadata_refresh(page)

    def _run_scheduled_single_metadata_refresh(self, page=None) -> None:
        state = self._single_metadata_state_obj()
        state.start_scheduled = False
        if not state.has_pending():
            return
        pending_file_name = state.pop_next()
        self._request_single_metadata_refresh(pending_file_name, page)

    def _single_metadata_state_obj(self) -> QueuedWorkerState[str]:
        state = self.__dict__.get("_single_metadata_state")
        if state is None:
            runtime = self.__dict__.get("_single_metadata_runtime")
            if runtime is None:
                runtime = OneShotWorkerRuntime()
                self._single_metadata_runtime = runtime
            state = QueuedWorkerState[str](runtime)
            self._single_metadata_state = state
        return state

    @property
    def _single_metadata_pending(self):
        return self._single_metadata_state_obj().pending

    @_single_metadata_pending.setter
    def _single_metadata_pending(self, value) -> None:
        self._single_metadata_state_obj().pending = list(value or [])

    @property
    def _single_metadata_start_scheduled(self) -> bool:
        return bool(self._single_metadata_state_obj().start_scheduled)

    @_single_metadata_start_scheduled.setter
    def _single_metadata_start_scheduled(self, value: bool) -> None:
        self._single_metadata_state_obj().start_scheduled = bool(value)

    def current_search_query(self, page=None) -> str:
        page = self._resolve_page(page)
        try:
            if page._preset_search_input is not None:
                return str(page._preset_search_input.text() or "").strip().lower()
        except Exception:
            pass
        return ""

    def capture_presets_view_state(self, page=None) -> dict[str, object]:
        page = self._resolve_page(page)
        state = {
            "current_file_name": "",
            "scroll_value": 0,
        }
        try:
            current_index = page.presets_list.currentIndex()
            if current_index.isValid():
                file_role = getattr(type(page._presets_model), "FileNameRole", None)
                if file_role is not None:
                    state["current_file_name"] = str(current_index.data(file_role) or "")
        except Exception:
            pass
        try:
            scrollbar = page.presets_list.verticalScrollBar()
            if scrollbar is not None:
                state["scroll_value"] = int(scrollbar.value())
        except Exception:
            pass
        return state

    def restore_presets_view_state(self, state: dict[str, object], page=None) -> None:
        page = self._resolve_page(page)
        target_file_name = str((state or {}).get("current_file_name") or "").strip()
        if target_file_name:
            self.set_current_preset_index(target_file_name, page=page)
        try:
            scrollbar = page.presets_list.verticalScrollBar()
            if scrollbar is not None:
                scroll_value = int((state or {}).get("scroll_value") or 0)
                if int(scrollbar.value()) != scroll_value:
                    scrollbar.setValue(scroll_value)
        except Exception:
            pass

    def set_current_preset_index(
        self,
        file_name: str,
        *,
        page=None,
    ) -> None:
        page = self._resolve_page(page)
        if page._presets_model is None or not hasattr(page, "presets_list"):
            return

        preset_file_name = str(file_name or "").strip()
        if not preset_file_name:
            return

        row = page._presets_model.find_preset_row(preset_file_name)
        if row < 0:
            return
        index = page._presets_model.index(row, 0)
        if index.isValid():
            try:
                if page.presets_list.currentIndex() == index:
                    return
            except Exception:
                pass
            page.presets_list.setCurrentIndex(index)

    def apply_active_preset_marker_for_file(
        self,
        file_name: str,
        *,
        page=None,
    ) -> bool:
        page = self._resolve_page(page)
        if page._presets_model is None:
            return False
        changed = page._presets_model.set_active_preset(
            str(file_name or "").strip(),
        )
        if changed and hasattr(page, "presets_list"):
            self.set_current_preset_index(
                file_name,
                page=page,
            )
        return changed

    def active_preset_file_name(self, page=None) -> str:
        page = self._resolve_page(page)
        model = getattr(page, "_presets_model", None)
        getter = getattr(model, "active_preset_file_name", None)
        if not callable(getter):
            return ""
        try:
            return str(getter() or "").strip()
        except Exception:
            return ""

    def ensure_preset_list_current_index(self, page=None) -> None:
        page = self._resolve_page(page)
        if page._presets_model is None:
            return
        current = page.presets_list.currentIndex()
        model_type = type(page._presets_model)
        kind_role = getattr(model_type, "KindRole", None)
        if current.isValid() and str(current.data(kind_role) or "") == "preset":
            return
        first_preset_row = getattr(page._presets_model, "first_preset_row", None)
        if not callable(first_preset_row):
            return
        try:
            row = int(first_preset_row())
        except (TypeError, ValueError):
            return
        if row < 0:
            return
        index = page._presets_model.index(row, 0)
        if index.isValid():
            page.presets_list.setCurrentIndex(index)

    def try_apply_single_preset_metadata_update(
        self,
        normalized_file_name: str,
        *,
        previous_metadata: dict[str, object],
        next_metadata: dict[str, object],
        page=None,
    ) -> bool:
        page = self._resolve_page(page)
        model = page._presets_model
        if model is None or model.find_preset_row(normalized_file_name) < 0:
            return False

        previous_display_name = str(previous_metadata.get("display_name") or normalized_file_name).strip()
        next_display_name = str(next_metadata.get("display_name") or normalized_file_name).strip()
        if previous_display_name != next_display_name:
            return False

        query = self.current_search_query(page)
        if query and query not in next_display_name.lower():
            return False

        active_file_name = self.active_preset_file_name(page)
        return model.update_preset_row(
            normalized_file_name,
            name=next_display_name,
            description=str(next_metadata.get("description") or ""),
            date=str(next_metadata.get("modified_display") or ""),
            is_active=bool(normalized_file_name and normalized_file_name == active_file_name),
            is_builtin=bool(next_metadata.get("is_builtin", False)),
            icon_color=normalize_preset_icon_color(str(next_metadata.get("icon_color") or "")),
        )

    def on_store_switched(self, name: str, page=None) -> None:
        page = self._resolve_page(page)
        adapter = self._resolve_adapter()
        if adapter.bulk_reset_running():
            return
        switched_file_name = str(name or "").strip()
        marker_changed = (
            self.apply_active_preset_marker_for_file(switched_file_name, page=page)
            if switched_file_name
            else False
        )
        if marker_changed and not self._ui_dirty:
            return
        if not self._ui_dirty and self._cached_presets_metadata and not marker_changed:
            return
        self._ui_dirty = True
        if page.isVisible():
            self.schedule_presets_reload(page)

    def start_watching_presets(self, page=None) -> None:
        page = self._resolve_page(page)
        adapter = self._resolve_adapter()
        try:
            if self._watcher_active:
                return

            presets_dir = adapter.presets_dir()

            if not self._file_watcher:
                from PyQt6.QtCore import QFileSystemWatcher

                watcher = QFileSystemWatcher(page)
                watcher.directoryChanged.connect(
                    lambda path: self.on_presets_dir_changed(path)
                )
                watcher.fileChanged.connect(
                    lambda path: self.on_preset_file_changed(path)
                )
                self._file_watcher = watcher

            dir_path = str(presets_dir)
            directory_watched = True
            if dir_path not in self._file_watcher.directories():
                directory_watched = bool(self._file_watcher.addPath(dir_path))
            if not directory_watched:
                self._ui_dirty = True
                if (
                    not self.__dict__.get("_watcher_directory_prepare_requested", False)
                    and not self.__dict__.get("_watcher_directory_prepare_retry_from_metadata", False)
                ):
                    self._watcher_directory_prepare_requested = True
                    self.load_presets(page)
                return

            self.sync_watched_preset_files(page)
            self._watcher_directory_prepare_requested = False
            self._watcher_active = True
        except Exception as e:
            log(f"Ошибка запуска мониторинга пресетов: {e}", "DEBUG")

    def stop_watching_presets(self, page=None) -> None:
        _ = self._resolve_page(page)
        try:
            self._stop_metadata_workers()
            if not self._watcher_active:
                timer = self._watcher_reload_timer
                if timer is not None:
                    timer.stop()
                self._ui_dirty = True
                return
            timer = self._watcher_reload_timer
            if timer is not None:
                timer.stop()
            if self._file_watcher:
                directories = self._file_watcher.directories()
                files = self._file_watcher.files()
                if directories:
                    self._file_watcher.removePaths(directories)
                if files:
                    self._file_watcher.removePaths(files)
            self._watcher_active = False
            self._ui_dirty = True
        except Exception as e:
            log(f"Ошибка остановки мониторинга пресетов: {e}", "DEBUG")

    def _stop_metadata_workers(self) -> None:
        self._metadata_load_request_id += 1
        self._single_metadata_request_id += 1
        self._rows_plan_request_id += 1
        self._metadata_load_state_obj().reset()
        self._single_metadata_state_obj().reset()
        self._rows_plan_state_obj().reset()
        self._rows_plan_apply_scheduled = False
        self._pending_rows_plan_apply = None
        self._watched_preset_files_sync_plan_request_id += 1
        self._watched_preset_files_sync_state_obj().reset()
        self._watched_preset_files_sync_plan_state_obj().reset()
        self._watched_preset_files_sync_batch_state_obj().reset()
        for attr, warning_prefix in (
            ("_metadata_load_runtime", "user presets metadata load worker"),
            ("_single_metadata_runtime", "user presets single metadata worker"),
            ("_rows_plan_runtime", "user presets rows plan worker"),
            ("_watched_preset_files_sync_plan_runtime", "user presets watcher sync plan worker"),
        ):
            runtime = getattr(self, attr, None)
            if runtime is not None:
                runtime.stop(blocking=False, warning_prefix=warning_prefix)
                runtime.cancel()

    def on_presets_dir_changed(self, path: str, page=None) -> None:
        page = self._resolve_page(page)
        try:
            log(f"Обнаружены изменения в папке пресетов: {path}", "DEBUG")
            self.schedule_presets_reload(page)
        except Exception as e:
            log(f"Ошибка обработки изменений папки пресетов: {e}", "DEBUG")

    def on_preset_file_changed(self, path: str, page=None) -> None:
        page = self._resolve_page(page)
        try:
            changed_path = Path(path)
            if self._file_watcher is not None:
                normalized_path = str(changed_path)
                if normalized_path not in self._file_watcher.files():
                    self._file_watcher.addPath(normalized_path)

            file_name = changed_path.name
            if file_name:
                self.on_store_content_changed(file_name, page)
        except Exception as e:
            log(f"Ошибка обработки изменений файла пресета: {e}", "DEBUG")

    def schedule_presets_reload(self, page=None, delay_ms: int = 500) -> None:
        page = self._resolve_page(page)
        try:
            if self._watcher_reload_timer is None:
                self.attach_page(page)
            if self._watcher_reload_timer is None:
                raise RuntimeError("watcher reload timer not initialized")
            self._watcher_reload_timer.stop()
            self._watcher_reload_timer.start(delay_ms)
        except Exception as e:
            log(f"Ошибка планирования обновления пресетов: {e}", "DEBUG")

    def reload_presets_from_watcher(self, page=None) -> None:
        page = self._resolve_page(page)
        if not page.isVisible():
            self._ui_dirty = True
            return
        self.load_presets(page)

    def sync_watched_preset_files(self, page=None, file_names: set[str] | None = None) -> None:
        page = self._resolve_page(page)
        adapter = self._resolve_adapter()
        watcher = self._file_watcher
        if watcher is None:
            return

        try:
            presets_dir = adapter.presets_dir()
            if file_names is None:
                file_names = {
                    str(file_name or "").strip()
                    for file_name in self._cached_presets_metadata.keys()
                    if str(file_name or "").strip()
                }

            current_paths = set(watcher.files() or [])
            self._request_watched_preset_files_sync_plan(
                page,
                presets_dir=presets_dir,
                file_names=file_names,
                current_paths=current_paths,
            )
        except Exception as e:
            log(f"Ошибка синхронизации watcher файлов пресетов: {e}", "DEBUG")

    def _request_watched_preset_files_sync_plan(
        self,
        page,
        *,
        presets_dir: Path,
        file_names: set[str],
        current_paths: set[str],
    ) -> None:
        plan_state = self._watched_preset_files_sync_plan_state_obj()
        if plan_state.is_busy():
            plan_state.pending = (page, set(file_names or set()))
            return

        def bind_worker(worker) -> None:
            worker.loaded.connect(
                lambda rid, plan, p=page: self._on_watched_preset_files_sync_plan_loaded(rid, plan, p)
            )
            worker.failed.connect(
                lambda rid, error, p=page: self._on_watched_preset_files_sync_plan_failed(rid, error, p)
            )

        request_id, _worker = self._watched_preset_files_sync_plan_runtime.start_qthread_worker(
            worker_factory=lambda request_id: UserPresetsWatcherSyncPlanWorker(
                request_id,
                presets_dir=presets_dir,
                file_names=set(file_names or set()),
                current_paths=set(current_paths or set()),
                parent=page,
            ),
            bind_worker=bind_worker,
            on_finished=self._on_watched_preset_files_sync_plan_worker_finished,
        )
        self._watched_preset_files_sync_plan_request_id = request_id

    def _on_watched_preset_files_sync_plan_loaded(self, request_id: int, plan, page=None) -> None:
        if request_id != self._watched_preset_files_sync_plan_request_id:
            return
        if self._watched_preset_files_sync_plan_state_obj().has_pending():
            return
        page = self._resolve_page(page)
        self._start_watched_preset_files_sync_batches(
            page,
            list(getattr(plan, "remove_paths", []) or []),
            list(getattr(plan, "add_paths", []) or []),
        )

    def _on_watched_preset_files_sync_plan_failed(self, request_id: int, error: str, _page=None) -> None:
        if request_id != self._watched_preset_files_sync_plan_request_id:
            return
        log(f"Ошибка подготовки watcher файлов пресетов: {error}", "DEBUG")

    def _on_watched_preset_files_sync_plan_worker_finished(self, worker: UserPresetsWatcherSyncPlanWorker) -> None:
        if not self._is_current_worker_finish(worker, "_watched_preset_files_sync_plan_request_id"):
            return
        plan_state = self._watched_preset_files_sync_plan_state_obj()
        pending = plan_state.pending
        plan_state.pending = plan_state.empty_value
        if pending is None:
            return
        page, file_names = pending
        self._schedule_watched_preset_files_sync(page, file_names)

    def _start_watched_preset_files_sync_batches(self, page, remove_paths: list[str], add_paths: list[str]) -> None:
        batch_state = self._watched_preset_files_sync_batch_state_obj()
        batch_state.pending = (page, list(remove_paths or []), list(add_paths or []))
        batch_state.start_scheduled = False
        self._run_next_watched_preset_files_sync_batch()

    def _run_next_watched_preset_files_sync_batch(self) -> None:
        batch_state = self._watched_preset_files_sync_batch_state_obj()
        batch_state.start_scheduled = False
        pending = batch_state.pending
        if pending is None:
            return
        page, remove_paths, add_paths = pending
        watcher = self.__dict__.get("_file_watcher")
        if watcher is None:
            batch_state.pending = batch_state.empty_value
            return

        try:
            batch_size = int(self.__dict__.get("_watched_preset_files_sync_batch_size", 64) or 64)
        except (TypeError, ValueError):
            batch_size = 64
        batch_size = max(1, batch_size)

        slots = batch_size
        remove_batch = remove_paths[:slots]
        if remove_batch:
            watcher.removePaths(remove_batch)
            remove_paths = remove_paths[len(remove_batch):]
            slots -= len(remove_batch)

        add_batch = add_paths[:slots] if slots > 0 else []
        if add_batch:
            watcher.addPaths(add_batch)
            add_paths = add_paths[len(add_batch):]

        if remove_paths or add_paths:
            batch_state.pending = (page, remove_paths, add_paths)
            self._schedule_watched_preset_files_sync_batch()
            return

        batch_state.pending = batch_state.empty_value

    def _schedule_watched_preset_files_sync_batch(self) -> None:
        batch_state = self._watched_preset_files_sync_batch_state_obj()
        if batch_state.start_scheduled:
            return
        batch_state.start_scheduled = True
        self._single_shot_or_run(0, self._run_next_watched_preset_files_sync_batch)

    def _schedule_watched_preset_files_sync(self, page=None, file_names: set[str] | None = None) -> None:
        page = self._resolve_page(page)
        sync_state = self._watched_preset_files_sync_state_obj()
        normalized_file_names = (
            {
                str(file_name or "").strip()
                for file_name in (file_names or set())
                if str(file_name or "").strip()
            }
            if file_names is not None
            else None
        )
        pending = sync_state.pending
        if pending is not None:
            _pending_page, pending_file_names = pending
            if pending_file_names is None or normalized_file_names is None:
                normalized_file_names = None
            else:
                normalized_file_names = set(pending_file_names) | set(normalized_file_names)
        sync_state.pending = (page, normalized_file_names)
        if sync_state.start_scheduled:
            return
        sync_state.start_scheduled = True
        self._single_shot_or_run(0, self._run_scheduled_watched_preset_files_sync)

    def _run_scheduled_watched_preset_files_sync(self) -> None:
        pending = self._watched_preset_files_sync_state_obj().take_pending_for_scheduled_start()
        if pending is None:
            return
        page, file_names = pending
        self.sync_watched_preset_files(page, file_names)

    def load_presets(self, page=None) -> None:
        page = self._resolve_page(page)
        adapter = self._resolve_adapter()
        metadata_load_state = self._metadata_load_state_obj()
        if metadata_load_state.is_busy():
            metadata_load_state.pending = page
            self._ui_dirty = True
            return

        self._ui_dirty = False

        def bind_worker(worker) -> None:
            worker.loaded.connect(
                lambda rid, all_presets, folder_state, started_at, p=page: self._on_metadata_loaded(
                    rid,
                    all_presets,
                    folder_state,
                    started_at,
                    p,
                )
            )
            worker.failed.connect(lambda rid, error, p=page: self._on_metadata_failed(rid, error, p))

        request_id, _worker = self._metadata_load_runtime.start_qthread_worker(
            worker_factory=lambda request_id: UserPresetsMetadataLoadWorker(
                request_id,
                adapter.load_all_metadata,
                adapter.load_folder_state,
                page,
            ),
            bind_worker=bind_worker,
            on_finished=self._on_metadata_worker_finished,
        )
        self._metadata_load_request_id = request_id

    def _on_metadata_loaded(
        self,
        request_id: int,
        all_presets: dict,
        folder_state: dict,
        started_at: float,
        page=None,
    ) -> None:
        if request_id != self._metadata_load_request_id:
            return
        if self._metadata_load_state_obj().has_pending():
            return
        page = self._resolve_page(page)
        self._cached_presets_metadata = dict(all_presets)
        self._cached_folder_state = dict(folder_state or {})
        if self.__dict__.pop("_watcher_directory_prepare_requested", False) and not self._watcher_active:
            self._watcher_directory_prepare_retry_from_metadata = True
            try:
                self.start_watching_presets(page)
            finally:
                self._watcher_directory_prepare_retry_from_metadata = False
        self._schedule_watched_preset_files_sync(page, set(all_presets.keys()))
        if not page.isVisible():
            self._ui_dirty = True
            return
        self._ui_dirty = False
        self._request_rows_plan_refresh(all_presets, self._cached_folder_state, started_at, page)

    def _on_metadata_failed(self, request_id: int, error: str, page=None) -> None:
        if request_id != self._metadata_load_request_id:
            return
        if self._metadata_load_state_obj().has_pending():
            return
        _ = self._resolve_page(page)
        self._ui_dirty = True
        log(f"Ошибка загрузки пресетов: {error}", "ERROR")

    def _on_metadata_worker_finished(self, worker: UserPresetsMetadataLoadWorker) -> None:
        if not self._is_current_worker_finish(worker, "_metadata_load_request_id"):
            return
        if self._metadata_load_state_obj().has_pending():
            self._schedule_metadata_load()

    def _schedule_metadata_load(self) -> None:
        self._metadata_load_state_obj().schedule_start(
            self._single_shot_or_run,
            self._run_scheduled_metadata_load,
        )

    def _run_scheduled_metadata_load(self) -> None:
        pending_page = self._metadata_load_state_obj().take_pending_for_scheduled_start()
        if pending_page is None:
            return
        self.load_presets(pending_page)

    def _metadata_load_state_obj(self) -> LatestValueWorkerState:
        state = self.__dict__.get("_metadata_load_state")
        if state is None:
            runtime = self.__dict__.get("_metadata_load_runtime")
            if runtime is None:
                runtime = OneShotWorkerRuntime()
                self._metadata_load_runtime = runtime
            state = LatestValueWorkerState(runtime, empty_value=None)
            self._metadata_load_state = state
        return state

    @property
    def _metadata_load_pending_page(self):
        return self._metadata_load_state_obj().pending

    @_metadata_load_pending_page.setter
    def _metadata_load_pending_page(self, value) -> None:
        self._metadata_load_state_obj().pending = value

    @property
    def _metadata_load_start_scheduled(self) -> bool:
        return bool(self._metadata_load_state_obj().start_scheduled)

    @_metadata_load_start_scheduled.setter
    def _metadata_load_start_scheduled(self, value: bool) -> None:
        self._metadata_load_state_obj().start_scheduled = bool(value)

    def refresh_presets_view_if_possible(self, page=None) -> None:
        page = self._resolve_page(page)
        if self._cached_presets_metadata:
            self._ui_dirty = False
            self.refresh_presets_view_from_cache(page)
            return
        adapter = self._resolve_adapter()
        try:
            cached = adapter.cached_metadata()
        except Exception:
            cached = None
        if cached:
            self._cached_presets_metadata = dict(cached)
            self._ui_dirty = False
            self.refresh_presets_view_from_cache(page)
            return
        self.load_presets(page)

    def refresh_presets_view_from_cache(self, page=None) -> None:
        _ = self._resolve_page(page)
        if not self._cached_presets_metadata:
            self.load_presets(page)
            return
        if self._cached_folder_state is None:
            self.load_presets(page)
            return
        self._request_rows_plan_refresh(self._cached_presets_metadata, self._cached_folder_state, None, page)

    def _request_rows_plan_refresh(
        self,
        all_presets: dict[str, dict[str, object]],
        folder_state: dict[str, Any] | None,
        started_at: float | None,
        page=None,
    ) -> None:
        page = self._resolve_page(page)
        adapter = self._resolve_adapter()
        build_rows_plan = adapter.build_rows_plan
        pending_request = (dict(all_presets or {}), dict(folder_state or {}), started_at, page)
        rows_plan_state = self._rows_plan_state_obj()

        if rows_plan_state.is_busy():
            rows_plan_state.pending = pending_request
            return

        def bind_worker(worker) -> None:
            worker.loaded.connect(lambda rid, plan, started, p=page: self._on_rows_plan_loaded(rid, plan, started, p))
            worker.failed.connect(lambda rid, error, p=page: self._on_rows_plan_failed(rid, error, p))

        request_id, _worker = self._rows_plan_runtime.start_qthread_worker(
            worker_factory=lambda request_id: UserPresetsRowsPlanWorker(
                request_id,
                build_rows_plan,
                all_presets=all_presets,
                query=self.current_search_query(page),
                selected_source_file_name=adapter.selected_source_file_name,
                language=str(getattr(page, "_ui_language", "") or ""),
                folder_state=folder_state,
                started_at=started_at,
                parent=page,
            ),
            bind_worker=bind_worker,
            on_finished=self._on_rows_plan_worker_finished,
        )
        self._rows_plan_request_id = request_id

    def _on_rows_plan_loaded(self, request_id: int, plan, started_at: float | None, page=None) -> None:
        if request_id != self._rows_plan_request_id:
            return
        if self._rows_plan_state_obj().has_pending():
            return
        page = self._resolve_page(page)
        self._schedule_rows_plan_apply(plan, started_at, page)

    def _schedule_rows_plan_apply(self, plan, started_at: float | None, page=None) -> None:
        self._pending_rows_plan_apply = (plan, started_at, page)
        if self.__dict__.get("_rows_plan_apply_scheduled", False):
            return
        self._rows_plan_apply_scheduled = True
        try:
            QTimer.singleShot(0, self._run_scheduled_rows_plan_apply)
        except Exception:
            self._run_scheduled_rows_plan_apply()

    def _run_scheduled_rows_plan_apply(self) -> None:
        pending = self.__dict__.get("_pending_rows_plan_apply")
        self._pending_rows_plan_apply = None
        self._rows_plan_apply_scheduled = False
        if pending is None:
            return
        if (
            self._rows_plan_state_obj().has_pending()
            or self._rows_plan_state_obj().start_scheduled
        ):
            return
        plan, started_at, page = pending
        _ = self._resolve_page(page)
        adapter = self._resolve_adapter()
        if callable(adapter.apply_rows_plan):
            apply_started_at = time.perf_counter()
            try:
                adapter.apply_rows_plan(plan, started_at)
            finally:
                _log_user_presets_timing("user_presets.rows_plan.apply", apply_started_at)

    def _on_rows_plan_failed(self, request_id: int, error: str, page=None) -> None:
        if request_id != self._rows_plan_request_id:
            return
        if self._rows_plan_state_obj().has_pending():
            return
        self._ui_dirty = True
        log(f"Ошибка подготовки списка пресетов: {error}", "ERROR")

    def _on_rows_plan_worker_finished(self, worker: UserPresetsRowsPlanWorker) -> None:
        if not self._is_current_worker_finish(worker, "_rows_plan_request_id"):
            return
        if self._rows_plan_state_obj().has_pending():
            self._schedule_rows_plan_refresh()

    def _schedule_rows_plan_refresh(self) -> None:
        self._rows_plan_state_obj().schedule_start(
            self._single_shot_or_run,
            self._run_scheduled_rows_plan_refresh,
        )

    def _run_scheduled_rows_plan_refresh(self) -> None:
        pending = self._rows_plan_state_obj().take_pending_for_scheduled_start()
        if pending is None:
            return
        all_presets, folder_state, started_at, page = pending
        self._request_rows_plan_refresh(all_presets, folder_state, started_at, page)

    def _rows_plan_state_obj(self) -> LatestValueWorkerState:
        state = self.__dict__.get("_rows_plan_state")
        if state is None:
            runtime = self.__dict__.get("_rows_plan_runtime")
            if runtime is None:
                runtime = OneShotWorkerRuntime()
                self._rows_plan_runtime = runtime
            state = LatestValueWorkerState(runtime, empty_value=None, pending=None)
            self._rows_plan_state = state
        return state

    @property
    def _rows_plan_pending(self):
        return self._rows_plan_state_obj().pending

    @_rows_plan_pending.setter
    def _rows_plan_pending(self, value) -> None:
        self._rows_plan_state_obj().pending = value

    def _watched_preset_files_sync_state_obj(self) -> LatestValueWorkerState:
        state = self.__dict__.get("_watched_preset_files_sync_state")
        if state is None:
            pending = self.__dict__.pop("_watched_preset_files_sync_pending", None)
            start_scheduled = bool(self.__dict__.pop("_watched_preset_files_sync_scheduled", False))
            state = LatestValueWorkerState(
                None,
                empty_value=None,
                pending=pending,
                start_scheduled=start_scheduled,
            )
            self.__dict__["_watched_preset_files_sync_state"] = state
        return state

    @property
    def _watched_preset_files_sync_pending(self):
        return self._watched_preset_files_sync_state_obj().pending

    @_watched_preset_files_sync_pending.setter
    def _watched_preset_files_sync_pending(self, value) -> None:
        self._watched_preset_files_sync_state_obj().pending = value

    @property
    def _watched_preset_files_sync_scheduled(self) -> bool:
        return bool(self._watched_preset_files_sync_state_obj().start_scheduled)

    @_watched_preset_files_sync_scheduled.setter
    def _watched_preset_files_sync_scheduled(self, value: bool) -> None:
        self._watched_preset_files_sync_state_obj().start_scheduled = bool(value)

    def _watched_preset_files_sync_plan_state_obj(self) -> LatestValueWorkerState:
        state = self.__dict__.get("_watched_preset_files_sync_plan_state")
        runtime = self.__dict__.get("_watched_preset_files_sync_plan_runtime")
        if state is None:
            pending = self.__dict__.pop("_watched_preset_files_sync_plan_pending", None)
            state = LatestValueWorkerState(runtime, empty_value=None, pending=pending)
            self.__dict__["_watched_preset_files_sync_plan_state"] = state
        elif getattr(state, "runtime", None) is None and runtime is not None:
            state.runtime = runtime
        return state

    @property
    def _watched_preset_files_sync_plan_pending(self):
        return self._watched_preset_files_sync_plan_state_obj().pending

    @_watched_preset_files_sync_plan_pending.setter
    def _watched_preset_files_sync_plan_pending(self, value) -> None:
        self._watched_preset_files_sync_plan_state_obj().pending = value

    def _watched_preset_files_sync_batch_state_obj(self) -> LatestValueWorkerState:
        state = self.__dict__.get("_watched_preset_files_sync_batch_state")
        if state is None:
            pending = self.__dict__.pop("_watched_preset_files_sync_batch_pending", None)
            start_scheduled = bool(self.__dict__.pop("_watched_preset_files_sync_batch_scheduled", False))
            state = LatestValueWorkerState(
                None,
                empty_value=None,
                pending=pending,
                start_scheduled=start_scheduled,
            )
            self.__dict__["_watched_preset_files_sync_batch_state"] = state
        return state

    @property
    def _watched_preset_files_sync_batch_pending(self):
        return self._watched_preset_files_sync_batch_state_obj().pending

    @_watched_preset_files_sync_batch_pending.setter
    def _watched_preset_files_sync_batch_pending(self, value) -> None:
        self._watched_preset_files_sync_batch_state_obj().pending = value

    @property
    def _watched_preset_files_sync_batch_scheduled(self) -> bool:
        return bool(self._watched_preset_files_sync_batch_state_obj().start_scheduled)

    @_watched_preset_files_sync_batch_scheduled.setter
    def _watched_preset_files_sync_batch_scheduled(self, value: bool) -> None:
        self._watched_preset_files_sync_batch_state_obj().start_scheduled = bool(value)

    def _single_shot_or_run(self, _delay: int, callback) -> None:
        try:
            QTimer.singleShot(0, callback)
        except Exception:
            callback()

    def remove_deleted_preset_locally(self, name: str, page=None) -> bool:
        page = self._resolve_page(page)
        adapter = self._resolve_adapter()
        normalized_name = str(name or "").strip()
        if not normalized_name:
            return False

        removed_metadata = False
        for key in _preset_metadata_keys(normalized_name):
            if key in self._cached_presets_metadata:
                self._cached_presets_metadata.pop(key, None)
                removed_metadata = True

        model = getattr(page, "_presets_model", None)
        if model is None or not model.remove_preset(normalized_name):
            return False

        self._schedule_watched_preset_files_sync(page, set(self._cached_presets_metadata.keys()))
        self._ui_dirty = not removed_metadata
        return True

    def add_created_preset_locally(self, file_name: str, display_name: str, page=None) -> bool:
        page = self._resolve_page(page)
        normalized_file_name = str(file_name or "").strip()
        normalized_display_name = str(display_name or normalized_file_name).strip() or normalized_file_name
        if not normalized_file_name:
            return False

        query = self.current_search_query(page)
        metadata = {
            "file_name": normalized_file_name,
            "display_name": normalized_display_name,
            "description": "",
            "modified_display": "",
            "is_builtin": False,
            "icon_color": "",
        }
        self._cached_presets_metadata[normalized_file_name] = metadata

        folder_key = "common"
        try:
            from presets.folders import classify_preset_folder

            folder_key = classify_preset_folder(normalized_display_name or normalized_file_name, self._scope_key)
        except Exception:
            folder_key = "common"

        if self._cached_folder_state is not None:
            self._cached_folder_state.setdefault("items", {}).setdefault(
                normalized_file_name,
                {"folder_key": folder_key, "order": None, "rating": 0},
            )

        self._schedule_watched_preset_files_sync(page, set(self._cached_presets_metadata.keys()))
        self._request_single_metadata_refresh(normalized_file_name, page)

        if query and query not in normalized_display_name.lower():
            self._ui_dirty = False
            return True

        model = getattr(page, "_presets_model", None)
        if model is None:
            return False
        if not model.insert_preset(
            {
                "kind": "preset",
                "name": normalized_display_name,
                "file_name": normalized_file_name,
                "description": "",
                "date": "",
                "is_active": False,
                "is_builtin": False,
                "icon_color": "",
                "depth": 1,
                "folder_key": folder_key,
                "is_pinned": False,
                "rating": 0,
            }
        ):
            return False

        self._ui_dirty = False
        return True

    def _is_current_worker_finish(self, worker, request_attr: str) -> bool:
        request_id = getattr(worker, "_request_id", getattr(worker, "request_id", None))
        if request_id is None:
            runtime_attr = {
                "_metadata_load_request_id": "_metadata_load_runtime",
                "_single_metadata_request_id": "_single_metadata_runtime",
                "_rows_plan_request_id": "_rows_plan_runtime",
                "_watched_preset_files_sync_plan_request_id": "_watched_preset_files_sync_plan_runtime",
            }.get(str(request_attr or ""))
            current_runtime = getattr(self, str(runtime_attr or ""), None)
            current_worker = getattr(current_runtime, "worker", None)
            if current_worker is not None:
                return worker is current_worker
            return True
        try:
            return int(request_id) == int(getattr(self, request_attr, -1))
        except (TypeError, ValueError):
            return False

    def rename_preset_locally(self, current_name: str, next_file_name: str, display_name: str, page=None) -> bool:
        page = self._resolve_page(page)
        current_file_name = str(current_name or "").strip()
        new_file_name = str(next_file_name or "").strip()
        new_display_name = str(display_name or "").strip()
        if not current_file_name or not new_file_name:
            return False

        query = self.current_search_query(page)
        if query and query not in new_display_name.lower():
            return False

        model = getattr(page, "_presets_model", None)
        if model is None or not model.rename_preset(current_file_name, new_file_name, name=new_display_name):
            return False

        metadata = None
        for key in _preset_metadata_keys(current_file_name):
            candidate = self._cached_presets_metadata.pop(key, None)
            if isinstance(candidate, dict):
                metadata = dict(candidate)
                break
        if metadata is None:
            metadata = {}
        metadata["file_name"] = new_file_name
        metadata["display_name"] = new_display_name or new_file_name
        self._cached_presets_metadata[new_file_name] = metadata
        self._schedule_watched_preset_files_sync(page, set(self._cached_presets_metadata.keys()))
        self._ui_dirty = False
        return True

    def recover_missing_deleted_preset(self, name: str, page=None) -> None:
        page = self._resolve_page(page)

        normalized_name = str(name or "").strip()
        if normalized_name:
            self._cached_presets_metadata.pop(normalized_name, None)
            if not normalized_name.lower().endswith(".txt"):
                self._cached_presets_metadata.pop(f"{normalized_name}.txt", None)

        if page.isVisible() and self._cached_presets_metadata:
            self._ui_dirty = False
            self.refresh_presets_view_from_cache(page)
            return

        self._ui_dirty = True
        if page.isVisible():
            self.load_presets(page)


def _preset_metadata_keys(name: str) -> tuple[str, ...]:
    normalized_name = str(name or "").strip()
    if not normalized_name:
        return ()
    if normalized_name.lower().endswith(".txt"):
        return (normalized_name,)
    return (normalized_name, f"{normalized_name}.txt")
