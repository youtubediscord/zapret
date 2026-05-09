from __future__ import annotations

import os
from typing import Callable, Optional

from PyQt6.QtCore import QFileSystemWatcher, QTimer, QObject

from winws_runtime.flow.preset_switch_policy import request_selected_source_preset_apply
from winws_runtime.runners.preset_runner_support import publish_active_preset_content_changed
from log.log import log



class PresetRuntimeCoordinator(QObject):
    """Координирует применение выбранного source preset вне UI-страниц.

    UI передаёт callback-и, а правило применения source preset живёт здесь.
    """

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        get_launch_method: Callable[[], str],
        get_active_preset_path: Callable[[], str],
        is_dpi_running: Callable[[], bool],
        restart_dpi_async: Callable[[], None],
        switch_presets_async: Callable[[str], None],
        refresh_after_switch: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self._get_launch_method = get_launch_method
        self._get_active_preset_path = get_active_preset_path
        self._is_dpi_running = is_dpi_running
        self._restart_dpi_async = restart_dpi_async
        self._switch_presets_async = switch_presets_async
        self._refresh_after_switch = refresh_after_switch

        self._active_preset_file_watcher: QFileSystemWatcher | None = None
        self._active_preset_file_refresh_timer: QTimer | None = None
        self._preset_switch_refresh_timer: QTimer | None = None
        self._active_preset_file_path: str = ""
        self._last_switched_preset_file_name: str = ""

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

    def handle_preset_switched(self, preset_file_name: str) -> None:
        log(f"Пресет переключен: {preset_file_name}", "INFO")
        self._last_switched_preset_file_name = str(preset_file_name or "").strip()
        self.setup_active_preset_file_watcher()
        self._request_selected_source_preset_apply()
        try:
            parent = self.parent()
            store = getattr(parent, "ui_state_store", None)
            if store is not None:
                store.bump_active_preset_revision()
        except Exception:
            pass
        self.schedule_refresh_after_preset_switch()

    def handle_preset_identity_changed(self, preset_file_name: str) -> None:
        log(f"Идентичность активного пресета обновлена: {preset_file_name}", "INFO")
        self._last_switched_preset_file_name = str(preset_file_name or "").strip()
        self.setup_active_preset_file_watcher()
        try:
            parent = self.parent()
            store = getattr(parent, "ui_state_store", None)
            if store is not None:
                store.bump_active_preset_revision()
        except Exception:
            pass
        self.schedule_refresh_after_preset_switch()

    def _request_selected_source_preset_apply(self) -> None:
        try:
            launch_method = str(self._get_launch_method() or "").strip().lower()
            parent = self.parent()
            if parent is None:
                return
            request_selected_source_preset_apply(
                parent,
                launch_method=launch_method,
                reason="preset_switched",
                preset_file_name=str(getattr(self, "_last_switched_preset_file_name", "") or ""),
            )
        except Exception:
            return

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
            publish_active_preset_content_changed(desired or path)
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
