from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from PyQt6.QtCore import QFileSystemWatcher, QTimer, QObject, QThread, pyqtSignal

from settings.mode import is_preset_launch_method, normalize_launch_method
from log.log import log
from ui.one_shot_worker_runtime import OneShotWorkerRuntime


PRESET_SWITCH_APPLY_DEBOUNCE_MS = 500
PRESET_SWITCH_REFRESH_DEBOUNCE_MS = 180


@dataclass(frozen=True)
class PendingPresetApply:
    launch_method: str
    reason: str
    preset_file_name: str


@dataclass(frozen=True)
class PendingPresetWatch:
    launch_method: str
    preset_file_name: str


class PresetWatchPathResolveWorker(QThread):
    loaded = pyqtSignal(int, str)
    failed = pyqtSignal(int, str)

    def __init__(
        self,
        request_id: int,
        *,
        pending: PendingPresetWatch | None,
        get_preset_source_path_by_file_name,
        get_active_preset_path,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._request_id = int(request_id)
        self._pending = pending
        self._get_preset_source_path_by_file_name = get_preset_source_path_by_file_name
        self._get_active_preset_path = get_active_preset_path

    def run(self) -> None:
        try:
            path = self._resolve_path()
        except Exception as exc:
            self.failed.emit(self._request_id, str(exc))
            return
        self.loaded.emit(self._request_id, str(path or ""))

    def _resolve_path(self) -> str:
        pending = self._pending
        if pending is not None:
            method = normalize_launch_method(pending.launch_method, default="")
            file_name = str(pending.preset_file_name or "").strip()
            resolver = self._get_preset_source_path_by_file_name
            if method and file_name and callable(resolver):
                return str(resolver(method, file_name) or "")
        get_active_path = self._get_active_preset_path
        if callable(get_active_path):
            return str(get_active_path() or "")
        return ""


class PresetRuntimeCoordinator(QObject):
    """Координирует применение выбранного source preset вне UI-страниц.

    UI передаёт callback-и, а правило применения source preset живёт здесь.
    """

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        presets_feature,
        ui_state_store,
        get_launch_method: Callable[[], str],
        get_active_preset_path: Callable[[], str],
        get_preset_source_path_by_file_name: Callable[[str, str], str] | None = None,
        refresh_after_switch: Callable[[], None],
        request_selected_source_preset_apply: Callable[[str, str, str], bool],
        request_preset_content_apply: Callable[[str, str, str], bool],
    ) -> None:
        super().__init__(parent)
        self._presets_feature = presets_feature
        self._ui_state_store = ui_state_store
        self._get_launch_method = get_launch_method
        self._get_active_preset_path = get_active_preset_path
        self._get_preset_source_path_by_file_name = get_preset_source_path_by_file_name
        self._refresh_after_switch = refresh_after_switch
        self._request_selected_source_preset_apply_callback = request_selected_source_preset_apply
        self._request_preset_content_apply = request_preset_content_apply

        self._active_preset_file_watcher: QFileSystemWatcher | None = None
        self._active_preset_file_refresh_timer: QTimer | None = None
        self._preset_switch_refresh_timer: QTimer | None = None
        self._preset_switch_apply_timer: QTimer | None = None
        self._active_preset_file_path: str = ""
        self._pending_preset_apply: PendingPresetApply | None = None
        self._pending_preset_content_apply: PendingPresetApply | None = None
        self._last_active_preset_key: tuple[str, str] | None = None
        self._active_preset_revision_publish_pending = False
        self._active_preset_file_watcher_setup_pending = False
        self._pending_active_preset_watch: PendingPresetWatch | None = None
        self._pending_refresh_after_switch_reason = ""
        self._pending_own_preset_content_file_name = ""
        self._preset_content_apply_timer: QTimer | None = None
        self._active_preset_watch_runtime = OneShotWorkerRuntime()
        self._active_preset_watch_runtime_request_id = 0

    def setup_active_preset_file_watcher(self) -> None:
        watched_path = self._resolve_active_preset_watch_path()
        self._apply_active_preset_watch_path(watched_path)

    def _apply_active_preset_watch_path(self, watched_path: str) -> None:
        if not watched_path:
            return

        watcher = self._active_preset_file_watcher
        if watcher is None:
            watcher = QFileSystemWatcher(self)
            watcher.fileChanged.connect(self._on_active_preset_file_changed)
            self._active_preset_file_watcher = watcher

        timer = self._active_preset_file_refresh_timer
        if timer is None:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(self._run_refresh_after_switch)
            self._active_preset_file_refresh_timer = timer

        self._active_preset_file_path = watched_path

        try:
            current = set(watcher.files() or [])
            desired = {watched_path}
            for path in (current - desired):
                watcher.removePath(path)
            for path in (desired - current):
                watcher.addPath(path)
        except Exception:
            try:
                if watched_path not in (watcher.files() or []):
                    watcher.addPath(watched_path)
            except Exception:
                pass

    def handle_preset_switched(self, launch_method: str, preset_file_name: str) -> None:
        method = normalize_launch_method(launch_method, default="")
        if not self._is_current_preset_method(method):
            return

        selected_file_name = str(preset_file_name or "").strip()
        active_key = (method, selected_file_name.lower())
        active_changed = self._last_active_preset_key != active_key
        self._last_active_preset_key = active_key
        if not active_changed:
            log(
                f"Повторное переключение на тот же preset пропущено: {selected_file_name}",
                "DEBUG",
            )
            return
        log(f"Пресет переключен: {selected_file_name}", "INFO")
        self._schedule_active_preset_file_watcher_setup(
            launch_method=method,
            preset_file_name=selected_file_name,
        )
        self._schedule_selected_source_preset_apply(
            launch_method=method,
            reason="preset_switched",
            preset_file_name=selected_file_name,
        )
        try:
            store = self._ui_state_store
            if store is not None:
                self._publish_active_preset_revision_deferred()
        except Exception:
            pass
        self.schedule_refresh_after_preset_switch()

    def handle_preset_identity_changed(self, launch_method: str, preset_file_name: str) -> None:
        method = normalize_launch_method(launch_method, default="")
        if not self._is_current_preset_method(method):
            return

        log(f"Идентичность активного пресета обновлена: {preset_file_name}", "INFO")
        selected_file_name = str(preset_file_name or "").strip()
        if selected_file_name:
            self._last_active_preset_key = (method, selected_file_name.lower())
        self._schedule_active_preset_file_watcher_setup(
            launch_method=method,
            preset_file_name=selected_file_name,
        )
        try:
            store = self._ui_state_store
            if store is not None:
                self._publish_active_preset_revision_deferred()
        except Exception:
            pass
        self.schedule_refresh_after_preset_switch()

    def handle_preset_content_changed(
        self,
        launch_method: str,
        preset_file_name: str,
        *,
        reason: str = "preset_content_changed",
    ) -> None:
        """Обновляет watcher после сохранения активного source preset-а."""
        method = normalize_launch_method(launch_method, default="")
        current_method = normalize_launch_method(self._get_launch_method(), default="")
        if not method or method != current_method or not is_preset_launch_method(method):
            return

        updated_file_name = str(preset_file_name or "").strip()
        if not updated_file_name or not self._is_selected_source_preset(method, updated_file_name):
            return

        self._schedule_preset_content_apply(
            launch_method=method,
            preset_file_name=updated_file_name,
            reason=reason,
        )

    def _request_selected_source_preset_apply(
        self,
        *,
        launch_method: str,
        reason: str = "preset_switched",
        preset_file_name: str = "",
    ) -> None:
        try:
            method = normalize_launch_method(launch_method, default="")
            if not self._is_current_preset_method(method):
                return
            self._request_selected_source_preset_apply_callback(
                method,
                reason,
                str(preset_file_name or "").strip(),
            )
        except Exception:
            return

    def _schedule_selected_source_preset_apply(
        self,
        *,
        launch_method: str,
        reason: str,
        preset_file_name: str,
        delay_ms: int = PRESET_SWITCH_APPLY_DEBOUNCE_MS,
    ) -> None:
        """Применяет только последний выбранный preset после короткой паузы."""
        method = normalize_launch_method(launch_method, default="")
        apply_reason = str(reason or "preset_switched").strip() or "preset_switched"
        selected_file_name = str(preset_file_name or "").strip()
        self._pending_preset_apply = PendingPresetApply(
            launch_method=method,
            reason=apply_reason,
            preset_file_name=selected_file_name,
        )
        try:
            timer = self._preset_switch_apply_timer
            if timer is None:
                timer = QTimer(self)
                timer.setSingleShot(True)
                timer.timeout.connect(self._apply_pending_selected_source_preset)
                self._preset_switch_apply_timer = timer
            timer.start(max(0, int(delay_ms)))
        except Exception:
            self._apply_pending_selected_source_preset()

    def _apply_pending_selected_source_preset(self) -> None:
        pending = self._pending_preset_apply
        self._pending_preset_apply = None
        if pending is None:
            return
        self._request_selected_source_preset_apply(
            launch_method=pending.launch_method,
            reason=pending.reason,
            preset_file_name=pending.preset_file_name,
        )

    def _schedule_preset_content_apply(
        self,
        *,
        launch_method: str,
        preset_file_name: str,
        reason: str = "preset_content_changed",
        delay_ms: int = 0,
    ) -> None:
        method = normalize_launch_method(launch_method, default="")
        selected_file_name = str(preset_file_name or "").strip()
        apply_reason = str(reason or "preset_content_changed").strip() or "preset_content_changed"
        self._pending_preset_content_apply = PendingPresetApply(
            launch_method=method,
            reason=apply_reason,
            preset_file_name=selected_file_name,
        )
        try:
            timer = self._preset_content_apply_timer
            if timer is None:
                timer = QTimer(self)
                timer.setSingleShot(True)
                timer.timeout.connect(self._apply_pending_preset_content_change)
                self._preset_content_apply_timer = timer
            timer.start(max(0, int(delay_ms)))
        except Exception:
            self._apply_pending_preset_content_change()

    def _apply_pending_preset_content_change(self) -> None:
        pending = self._pending_preset_content_apply
        self._pending_preset_content_apply = None
        if pending is None:
            return

        self._schedule_active_preset_file_watcher_setup(
            launch_method=pending.launch_method,
            preset_file_name=pending.preset_file_name,
        )
        self._pending_own_preset_content_file_name = self._normalize_preset_file_name(pending.preset_file_name)
        self._publish_active_preset_content_changed(pending.preset_file_name, reason=pending.reason)
        self._request_refresh_after_switch(reason=pending.reason)
        self._request_preset_content_apply(
            pending.launch_method,
            pending.reason,
            pending.preset_file_name,
        )

    def _publish_active_preset_content_changed(self, path: str, *, reason: str = "preset_content_changed") -> None:
        if not str(path or "").strip():
            return
        try:
            store = self._ui_state_store
            if store is not None:
                try:
                    store.bump_preset_content_revision(
                        content_change_kind=str(reason or "preset_content_changed").strip()
                    )
                except TypeError as exc:
                    if "content_change_kind" not in str(exc):
                        raise
                    store.bump_preset_content_revision()
        except Exception:
            pass

    def _publish_active_preset_revision_deferred(self) -> None:
        """Будит UI-подписчиков после завершения текущего клика."""
        if self._active_preset_revision_publish_pending:
            return
        self._active_preset_revision_publish_pending = True
        try:
            QTimer.singleShot(0, self._publish_pending_active_preset_revision)
        except Exception:
            self._active_preset_revision_publish_pending = False
            self._publish_active_preset_revision_now()

    def _publish_pending_active_preset_revision(self) -> None:
        self._active_preset_revision_publish_pending = False
        self._publish_active_preset_revision_now()

    def _publish_active_preset_revision_now(self) -> None:
        try:
            store = self._ui_state_store
            if store is not None:
                store.bump_active_preset_revision()
        except Exception:
            pass

    def _resolve_active_preset_watch_path(self) -> str:
        pending = self._pending_active_preset_watch
        self._pending_active_preset_watch = None
        if pending is not None:
            method = normalize_launch_method(pending.launch_method, default="")
            file_name = str(pending.preset_file_name or "").strip()
            resolver = self._get_preset_source_path_by_file_name
            if method and file_name and callable(resolver):
                try:
                    return str(resolver(method, file_name) or "")
                except Exception:
                    pass
        return str(self._get_active_preset_path() or "")

    def _schedule_active_preset_file_watcher_setup(
        self,
        *,
        launch_method: str = "",
        preset_file_name: str = "",
    ) -> None:
        """Перевешивает watcher после текущего GUI-события, не внутри клика."""
        method = normalize_launch_method(launch_method, default="")
        file_name = str(preset_file_name or "").strip()
        if method and file_name:
            self._pending_active_preset_watch = PendingPresetWatch(
                launch_method=method,
                preset_file_name=file_name,
            )
        runtime = self.__dict__.get("_active_preset_watch_runtime")
        if runtime is None:
            runtime = OneShotWorkerRuntime()
            self._active_preset_watch_runtime = runtime
        if runtime.is_running():
            self._active_preset_file_watcher_setup_pending = True
            return
        self._start_active_preset_watch_worker()

    def _start_active_preset_watch_worker(self) -> None:
        runtime = self.__dict__.get("_active_preset_watch_runtime")
        if runtime is None:
            runtime = OneShotWorkerRuntime()
            self._active_preset_watch_runtime = runtime
        pending = self._pending_active_preset_watch
        self._pending_active_preset_watch = None
        try:
            request_id, _worker = runtime.start_qthread_worker(
                worker_factory=lambda request_id: PresetWatchPathResolveWorker(
                    request_id,
                    pending=pending,
                    get_preset_source_path_by_file_name=self._get_preset_source_path_by_file_name,
                    get_active_preset_path=self._get_active_preset_path,
                    parent=self,
                ),
                on_loaded=self._on_active_preset_watch_path_loaded,
                on_failed=self._on_active_preset_watch_path_failed,
                on_finished=self._on_active_preset_watch_worker_finished,
            )
            self._active_preset_watch_runtime_request_id = request_id
        except Exception:
            self._pending_active_preset_watch = pending
            log("PresetRuntimeCoordinator: не удалось запустить Worker watcher активного preset", "DEBUG")

    def _on_active_preset_watch_path_loaded(self, request_id: int, watched_path: str) -> None:
        runtime = self.__dict__.get("_active_preset_watch_runtime")
        if runtime is None or not runtime.is_current(request_id):
            return
        if self.__dict__.get("_active_preset_file_watcher_setup_pending", False):
            return
        self._apply_active_preset_watch_path(str(watched_path or ""))

    def _on_active_preset_watch_path_failed(self, request_id: int, error: str) -> None:
        runtime = self.__dict__.get("_active_preset_watch_runtime")
        if runtime is None or not runtime.is_current(request_id):
            return
        log(f"PresetRuntimeCoordinator: не удалось подготовить watcher активного preset: {error}", "DEBUG")

    def _on_active_preset_watch_worker_finished(self, worker) -> None:
        if not self._accept_current_active_preset_watch_worker_finished(worker):
            return
        if not self.__dict__.get("_active_preset_file_watcher_setup_pending", False):
            return
        self._active_preset_file_watcher_setup_pending = False
        try:
            QTimer.singleShot(0, self._start_active_preset_watch_worker)
        except Exception:
            self._start_active_preset_watch_worker()

    def _accept_current_active_preset_watch_worker_finished(self, worker) -> bool:
        request_id = getattr(worker, "_request_id", None)
        if request_id is None:
            return False
        try:
            current_request_id = int(self.__dict__.get("_active_preset_watch_runtime_request_id", 0) or 0)
            if int(request_id) != current_request_id:
                return False
        except (TypeError, ValueError):
            return False
        self._active_preset_watch_runtime_request_id = 0
        return True

    def _is_selected_source_preset(self, launch_method: str, preset_file_name: str) -> bool:
        try:
            return bool(
                self._presets_feature.is_selected_source_preset_file(
                    launch_method,
                    preset_file_name,
                )
            )
        except Exception:
            return False

    def _is_current_preset_method(self, launch_method: str) -> bool:
        method = normalize_launch_method(launch_method, default="")
        if not method or not is_preset_launch_method(method):
            return False
        current_method = normalize_launch_method(self._get_launch_method(), default="")
        return bool(current_method and method == current_method)

    def schedule_refresh_after_preset_switch(
        self,
        delay_ms: int = PRESET_SWITCH_REFRESH_DEBOUNCE_MS,
        *,
        reason: str = "",
    ) -> None:
        self._pending_refresh_after_switch_reason = str(reason or "").strip()
        try:
            timer = self._preset_switch_refresh_timer
            if timer is None:
                timer = QTimer(self)
                timer.setSingleShot(True)
                timer.timeout.connect(self._run_refresh_after_switch)
                self._preset_switch_refresh_timer = timer
            timer.start(max(0, int(delay_ms)))
        except Exception:
            try:
                self._run_refresh_after_switch()
            except Exception:
                pass

    def _run_refresh_after_switch(self) -> None:
        reason = str(self.__dict__.get("_pending_refresh_after_switch_reason", "") or "").strip()
        self._pending_refresh_after_switch_reason = ""
        self._request_refresh_after_switch(reason=reason)

    def _request_refresh_after_switch(self, *, reason: str = "") -> None:
        refresh = self._refresh_after_switch
        clean_reason = str(reason or "").strip()
        try:
            refresh(reason=clean_reason)
        except TypeError:
            refresh()

    def _on_active_preset_file_changed(self, path: str) -> None:
        try:
            watcher = self._active_preset_file_watcher
            desired = self._active_preset_file_path
            if watcher is not None:
                rearm = desired or path
                if rearm and rearm not in (watcher.files() or []):
                    watcher.addPath(rearm)
        except Exception:
            pass

        if self._consume_own_preset_file_change(path):
            return

        try:
            self._publish_active_preset_content_changed(desired or path)
        except Exception:
            pass

        try:
            timer = self._active_preset_file_refresh_timer
            if timer is not None:
                self._pending_refresh_after_switch_reason = "preset_content_changed"
                timer.start(200)
            else:
                self.schedule_refresh_after_preset_switch(reason="preset_content_changed")
        except Exception:
            try:
                self.schedule_refresh_after_preset_switch(reason="preset_content_changed")
            except Exception:
                pass

    def _consume_own_preset_file_change(self, path: str) -> bool:
        pending_file_name = str(self.__dict__.get("_pending_own_preset_content_file_name", "") or "").strip()
        if not pending_file_name:
            return False
        changed_file_name = self._normalize_preset_file_name(path)
        active_file_name = self._normalize_preset_file_name(self.__dict__.get("_active_preset_file_path", ""))
        if changed_file_name in {pending_file_name, active_file_name}:
            self._pending_own_preset_content_file_name = ""
            return True
        return False

    @staticmethod
    def _normalize_preset_file_name(path_or_file_name: str) -> str:
        text = str(path_or_file_name or "").strip().replace("\\", "/")
        if "/" in text:
            text = text.rsplit("/", 1)[-1]
        return text.lower()
