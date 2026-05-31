from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
import weakref

from PyQt6.QtCore import QThread, QTimer, pyqtSignal

from log.log import log
from presets.icon_color import normalize_preset_icon_color


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
        try:
            active_file_name = str(self._selected_source_file_name() or "").strip()
            plan = self._build_rows_plan(
                all_presets=self._all_presets,
                query=self._query,
                active_file_name=active_file_name,
                language=self._language,
                folder_state=self._folder_state,
            )
        except Exception as exc:
            self.failed.emit(self._request_id, str(exc))
            return
        self.loaded.emit(self._request_id, plan, self._started_at)


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
        self._metadata_load_worker: UserPresetsMetadataLoadWorker | None = None
        self._metadata_load_pending_page = None
        self._metadata_load_start_scheduled = False
        self._single_metadata_request_id = 0
        self._single_metadata_worker: UserPresetsSingleMetadataWorker | None = None
        self._single_metadata_pending: list[str] = []
        self._single_metadata_start_scheduled = False
        self._rows_plan_request_id = 0
        self._rows_plan_worker: UserPresetsRowsPlanWorker | None = None
        self._rows_plan_pending: tuple[dict[str, dict[str, object]], dict[str, Any] | None, float | None, object] | None = None
        self._rows_plan_apply_scheduled = False
        self._pending_rows_plan_apply: tuple[object, float | None, object] | None = None
        self._watched_preset_files_sync_scheduled = False
        self._watched_preset_files_sync_pending: tuple[object, set[str] | None] | None = None

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

        worker = self._single_metadata_worker
        if worker is not None or self.__dict__.get("_single_metadata_start_scheduled", False):
            try:
                if worker is None or worker.isRunning():
                    if normalized_file_name not in self._single_metadata_pending:
                        self._single_metadata_pending.append(normalized_file_name)
                    return
            except Exception:
                return

        self._single_metadata_request_id += 1
        request_id = self._single_metadata_request_id
        worker = UserPresetsSingleMetadataWorker(
            request_id,
            normalized_file_name,
            adapter.read_single_metadata,
            page,
        )
        self._single_metadata_worker = worker
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
        worker.finished.connect(lambda w=worker, p=page: self._on_single_metadata_worker_finished(w, p))
        worker.start()

    def _on_single_metadata_loaded(self, request_id: int, file_name: str, refreshed, page=None) -> None:
        if request_id != self._single_metadata_request_id:
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
        page = self._resolve_page(page)
        self._ui_dirty = True
        log(f"Ошибка обновления metadata preset-а {file_name}: {error}", "ERROR")
        if page.isVisible():
            self.schedule_presets_reload(page, 0)

    def _on_single_metadata_worker_finished(self, worker: UserPresetsSingleMetadataWorker, page=None) -> None:
        if self._single_metadata_worker is worker:
            self._single_metadata_worker = None
        worker.deleteLater()
        if self._single_metadata_pending:
            self._schedule_single_metadata_refresh(page)

    def _schedule_single_metadata_refresh(self, page=None) -> None:
        if self.__dict__.get("_single_metadata_start_scheduled", False):
            return
        self._single_metadata_start_scheduled = True
        try:
            QTimer.singleShot(0, lambda p=page: self._run_scheduled_single_metadata_refresh(p))
        except Exception:
            self._run_scheduled_single_metadata_refresh(page)

    def _run_scheduled_single_metadata_refresh(self, page=None) -> None:
        self._single_metadata_start_scheduled = False
        if not self._single_metadata_pending:
            return
        pending_file_name = self._single_metadata_pending.pop(0)
        self._request_single_metadata_refresh(pending_file_name, page)

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
        for row in range(page._presets_model.rowCount()):
            index = page._presets_model.index(row, 0)
            if str(index.data(kind_role) or "") == "preset":
                page.presets_list.setCurrentIndex(index)
                break

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
            page.refresh_presets_view_if_possible()

    def start_watching_presets(self, page=None) -> None:
        page = self._resolve_page(page)
        adapter = self._resolve_adapter()
        try:
            if self._watcher_active:
                return

            presets_dir = adapter.presets_dir()
            presets_dir.mkdir(parents=True, exist_ok=True)

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
            if dir_path not in self._file_watcher.directories():
                self._file_watcher.addPath(dir_path)

            self.sync_watched_preset_files(page)
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
        self._metadata_load_pending_page = None
        self._metadata_load_start_scheduled = False
        self._single_metadata_pending.clear()
        self._single_metadata_start_scheduled = False
        self._rows_plan_pending = None
        self._rows_plan_apply_scheduled = False
        self._pending_rows_plan_apply = None
        self._watched_preset_files_sync_scheduled = False
        self._watched_preset_files_sync_pending = None
        for attr in ("_metadata_load_worker", "_single_metadata_worker", "_rows_plan_worker"):
            worker = getattr(self, attr, None)
            if worker is None:
                continue
            try:
                worker.quit()
            except Exception:
                pass
            setattr(self, attr, None)

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

            desired_paths = {
                str(presets_dir / file_name)
                for file_name in file_names
                if file_name
            }
            current_paths = set(watcher.files() or [])

            remove_paths = sorted(current_paths - desired_paths)
            add_paths = sorted(desired_paths - current_paths)

            if remove_paths:
                watcher.removePaths(remove_paths)
            if add_paths:
                watcher.addPaths(add_paths)
        except Exception as e:
            log(f"Ошибка синхронизации watcher файлов пресетов: {e}", "DEBUG")

    def _schedule_watched_preset_files_sync(self, page=None, file_names: set[str] | None = None) -> None:
        page = self._resolve_page(page)
        normalized_file_names = (
            {
                str(file_name or "").strip()
                for file_name in (file_names or set())
                if str(file_name or "").strip()
            }
            if file_names is not None
            else None
        )
        self._watched_preset_files_sync_pending = (page, normalized_file_names)
        if self._watched_preset_files_sync_scheduled:
            return
        self._watched_preset_files_sync_scheduled = True
        try:
            QTimer.singleShot(0, self._run_scheduled_watched_preset_files_sync)
        except Exception:
            self._run_scheduled_watched_preset_files_sync()

    def _run_scheduled_watched_preset_files_sync(self) -> None:
        pending = self._watched_preset_files_sync_pending
        self._watched_preset_files_sync_pending = None
        self._watched_preset_files_sync_scheduled = False
        if pending is None:
            return
        page, file_names = pending
        self.sync_watched_preset_files(page, file_names)

    def load_presets(self, page=None) -> None:
        page = self._resolve_page(page)
        adapter = self._resolve_adapter()
        worker = self._metadata_load_worker
        if (
            (worker is not None and worker.isRunning())
            or self.__dict__.get("_metadata_load_start_scheduled", False)
        ):
            self._metadata_load_pending_page = page
            self._ui_dirty = True
            return

        self._ui_dirty = False
        self._metadata_load_request_id += 1
        request_id = self._metadata_load_request_id
        worker = UserPresetsMetadataLoadWorker(request_id, adapter.load_all_metadata, adapter.load_folder_state, page)
        self._metadata_load_worker = worker
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
        worker.finished.connect(lambda w=worker: self._on_metadata_worker_finished(w))
        worker.start()

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
        page = self._resolve_page(page)
        adapter = self._resolve_adapter()
        self._cached_presets_metadata = dict(all_presets)
        self._cached_folder_state = dict(folder_state or {})
        self._schedule_watched_preset_files_sync(page, set(all_presets.keys()))
        if not page.isVisible():
            self._ui_dirty = True
            return
        self._ui_dirty = False
        self._request_rows_plan_refresh(all_presets, self._cached_folder_state, started_at, page)

    def _on_metadata_failed(self, request_id: int, error: str, page=None) -> None:
        if request_id != self._metadata_load_request_id:
            return
        _ = self._resolve_page(page)
        self._ui_dirty = True
        log(f"Ошибка загрузки пресетов: {error}", "ERROR")

    def _on_metadata_worker_finished(self, worker: UserPresetsMetadataLoadWorker) -> None:
        if self._metadata_load_worker is worker:
            self._metadata_load_worker = None
        worker.deleteLater()
        pending_page = self._metadata_load_pending_page
        if pending_page is not None:
            self._schedule_metadata_load()

    def _schedule_metadata_load(self) -> None:
        if self.__dict__.get("_metadata_load_start_scheduled", False):
            return
        self._metadata_load_start_scheduled = True
        try:
            QTimer.singleShot(0, self._run_scheduled_metadata_load)
        except Exception:
            self._run_scheduled_metadata_load()

    def _run_scheduled_metadata_load(self) -> None:
        self._metadata_load_start_scheduled = False
        pending_page = self.__dict__.get("_metadata_load_pending_page")
        self._metadata_load_pending_page = None
        if pending_page is None:
            return
        self.load_presets(pending_page)

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

        worker = self._rows_plan_worker
        if worker is not None:
            try:
                if worker.isRunning():
                    self._rows_plan_pending = (dict(all_presets or {}), dict(folder_state or {}), started_at, page)
                    return
            except Exception:
                return

        self._rows_plan_request_id += 1
        request_id = self._rows_plan_request_id
        worker = UserPresetsRowsPlanWorker(
            request_id,
            build_rows_plan,
            all_presets=all_presets,
            query=self.current_search_query(page),
            selected_source_file_name=adapter.selected_source_file_name,
            language=str(getattr(page, "_ui_language", "") or ""),
            folder_state=folder_state,
            started_at=started_at,
            parent=page,
        )
        self._rows_plan_worker = worker
        worker.loaded.connect(lambda rid, plan, started, p=page: self._on_rows_plan_loaded(rid, plan, started, p))
        worker.failed.connect(lambda rid, error, p=page: self._on_rows_plan_failed(rid, error, p))
        worker.finished.connect(lambda w=worker: self._on_rows_plan_worker_finished(w))
        worker.start()

    def _on_rows_plan_loaded(self, request_id: int, plan, started_at: float | None, page=None) -> None:
        if request_id != self._rows_plan_request_id:
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
        plan, started_at, page = pending
        _ = self._resolve_page(page)
        adapter = self._resolve_adapter()
        if callable(adapter.apply_rows_plan):
            adapter.apply_rows_plan(plan, started_at)

    def _on_rows_plan_failed(self, request_id: int, error: str, page=None) -> None:
        if request_id != self._rows_plan_request_id:
            return
        self._ui_dirty = True
        log(f"Ошибка подготовки списка пресетов: {error}", "ERROR")

    def _on_rows_plan_worker_finished(self, worker: UserPresetsRowsPlanWorker) -> None:
        if self._rows_plan_worker is worker:
            self._rows_plan_worker = None
        worker.deleteLater()
        pending = self._rows_plan_pending
        self._rows_plan_pending = None
        if pending is not None:
            all_presets, folder_state, started_at, page = pending
            self._schedule_rows_plan_refresh(all_presets, folder_state, started_at, page)

    def _schedule_rows_plan_refresh(
        self,
        all_presets: dict[str, dict[str, object]],
        folder_state: dict[str, Any] | None,
        started_at: float | None,
        page=None,
    ) -> None:
        try:
            QTimer.singleShot(
                0,
                lambda p=page, presets=all_presets, state=folder_state, started=started_at: self._request_rows_plan_refresh(
                    presets,
                    state,
                    started,
                    p,
                ),
            )
        except Exception:
            self._request_rows_plan_refresh(all_presets, folder_state, started_at, page)

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
