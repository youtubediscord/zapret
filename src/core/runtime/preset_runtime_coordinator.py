from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Callable, Optional

from PyQt6.QtCore import QFileSystemWatcher, QTimer, QObject

from settings.mode import is_preset_launch_method, normalize_launch_method
from log.log import log


PRESET_SWITCH_APPLY_DEBOUNCE_MS = 500


@dataclass(frozen=True)
class PendingPresetApply:
    launch_method: str
    reason: str
    preset_file_name: str


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
        refresh_after_switch: Callable[[], None],
        request_runtime_content_apply: Callable[[str, str, str], bool],
    ) -> None:
        super().__init__(parent)
        self._presets_feature = presets_feature
        self._ui_state_store = ui_state_store
        self._get_launch_method = get_launch_method
        self._get_active_preset_path = get_active_preset_path
        self._refresh_after_switch = refresh_after_switch
        self._request_runtime_content_apply = request_runtime_content_apply

        self._active_preset_file_watcher: QFileSystemWatcher | None = None
        self._active_preset_file_refresh_timer: QTimer | None = None
        self._preset_switch_refresh_timer: QTimer | None = None
        self._preset_switch_apply_timer: QTimer | None = None
        self._active_preset_file_path: str = ""
        self._pending_preset_apply: PendingPresetApply | None = None

    def setup_active_preset_file_watcher(self) -> None:
        watched_path = self._get_active_preset_path()
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
            timer.timeout.connect(self._refresh_after_switch)
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

        log(f"Пресет переключен: {preset_file_name}", "INFO")
        selected_file_name = str(preset_file_name or "").strip()
        self.setup_active_preset_file_watcher()
        self._schedule_selected_source_preset_apply(
            launch_method=method,
            reason="preset_switched",
            preset_file_name=selected_file_name,
        )
        try:
            store = self._ui_state_store
            if store is not None:
                store.bump_active_preset_revision()
        except Exception:
            pass
        self.schedule_refresh_after_preset_switch()

    def handle_preset_identity_changed(self, launch_method: str, preset_file_name: str) -> None:
        method = normalize_launch_method(launch_method, default="")
        if not self._is_current_preset_method(method):
            return

        log(f"Идентичность активного пресета обновлена: {preset_file_name}", "INFO")
        self.setup_active_preset_file_watcher()
        try:
            store = self._ui_state_store
            if store is not None:
                store.bump_active_preset_revision()
        except Exception:
            pass
        self.schedule_refresh_after_preset_switch()

    def handle_preset_content_changed(self, launch_method: str, preset_file_name: str) -> None:
        """Обновляет watcher после сохранения активного source preset-а."""
        method = normalize_launch_method(launch_method, default="")
        current_method = normalize_launch_method(self._get_launch_method(), default="")
        if not method or method != current_method or not is_preset_launch_method(method):
            return

        updated_file_name = str(preset_file_name or "").strip()
        if not updated_file_name or not self._is_selected_source_preset(method, updated_file_name):
            return

        old_path = self._active_preset_file_path
        self.setup_active_preset_file_watcher()
        new_path = str(self._get_active_preset_path() or "").strip()
        if new_path:
            self._publish_active_preset_content_changed(new_path)

        if not self._same_path(old_path, new_path):
            log(
                f"Активный preset сохранён в новом source-файле: {new_path or updated_file_name}",
                "INFO",
            )
            self._request_selected_source_preset_apply(
                launch_method=method,
                reason="preset_content_changed",
                preset_file_name=updated_file_name,
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
            self._request_runtime_content_apply(
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

    def _publish_active_preset_content_changed(self, path: str) -> None:
        if not str(path or "").strip():
            return
        try:
            store = self._ui_state_store
            if store is not None:
                store.bump_preset_content_revision()
        except Exception:
            pass

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

    @staticmethod
    def _same_path(left: str, right: str) -> bool:
        left_value = str(left or "").strip()
        right_value = str(right or "").strip()
        if not left_value or not right_value:
            return left_value == right_value
        return (
            os.path.abspath(left_value).replace("\\", "/").lower()
            == os.path.abspath(right_value).replace("\\", "/").lower()
        )

    def schedule_refresh_after_preset_switch(self, delay_ms: int = 0) -> None:
        try:
            timer = self._preset_switch_refresh_timer
            if timer is None:
                timer = QTimer(self)
                timer.setSingleShot(True)
                timer.timeout.connect(self._refresh_after_switch)
                self._preset_switch_refresh_timer = timer
            timer.start(max(0, int(delay_ms)))
        except Exception:
            try:
                self._refresh_after_switch()
            except Exception:
                pass

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

        try:
            self._publish_active_preset_content_changed(desired or path)
        except Exception:
            pass

        try:
            timer = self._active_preset_file_refresh_timer
            if timer is not None:
                timer.start(200)
            else:
                self.schedule_refresh_after_preset_switch()
        except Exception:
            try:
                self.schedule_refresh_after_preset_switch()
            except Exception:
                pass
