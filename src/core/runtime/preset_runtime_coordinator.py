from __future__ import annotations

import os
from typing import Callable, Optional

from PyQt6.QtCore import QFileSystemWatcher, QTimer, QObject

from launcher_common.preset_runner_support import publish_active_preset_content_changed
from log import log
from dpi.runtime_preset_switch_policy import request_runtime_preset_switch


class PresetRuntimeCoordinator(QObject):
    """Coordinates preset-switch runtime behavior outside of UI pages.

    Responsibilities:
    - watch the active preset file for external/source changes
    - request process restart after preset switch
    - invoke UI refresh callbacks after preset changes

    UI code should provide callbacks, but the runtime policy itself lives here.
    """

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        get_launch_method: Callable[[], str],
        get_active_preset_path: Callable[[], str],
        is_dpi_running: Callable[[], bool],
        restart_dpi_async: Callable[[], None],
        switch_direct_preset_async: Callable[[str], None],
        refresh_after_switch: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self._get_launch_method = get_launch_method
        self._get_active_preset_path = get_active_preset_path
        self._is_dpi_running = is_dpi_running
        self._restart_dpi_async = restart_dpi_async
        self._switch_direct_preset_async = switch_direct_preset_async
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
        self.request_dpi_restart_after_preset_switch()
        try:
            parent = self.parent()
            store = getattr(parent, "ui_state_store", None)
            if store is not None:
                store.bump_active_preset_revision()
        except Exception:
            pass
        self.schedule_refresh_after_preset_switch()

    def request_dpi_restart_after_preset_switch(self) -> None:
        try:
            launch_method = str(self._get_launch_method() or "").strip().lower()
            parent = self.parent()
            if parent is None:
                return
            request_runtime_preset_switch(
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


def resolve_active_preset_watch_path() -> str:
    try:
        from strategy_menu import get_strategy_launch_method

        method = (get_strategy_launch_method() or "").strip().lower()
    except Exception:
        method = ""

    try:
        if method == "direct_zapret2":
            from core.services import get_direct_flow_coordinator

            return os.fspath(get_direct_flow_coordinator().get_selected_source_path("direct_zapret2"))
    except Exception:
        return ""

    return ""
