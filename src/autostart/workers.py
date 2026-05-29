from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from log.log import log


class AutostartActionWorker(QThread):
    completed = pyqtSignal(int, str, object, object)
    failed = pyqtSignal(int, str, str, object)
    status = pyqtSignal(int, str, str)

    def __init__(
        self,
        request_id: int,
        *,
        action: str,
        enabled: bool | None = None,
        strategy_name: str | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._action = str(action or "").strip()
        self._enabled = None if enabled is None else bool(enabled)
        self._strategy_name = strategy_name

    def run(self) -> None:
        import autostart.public as autostart_public

        context = {
            "enabled": self._enabled,
            "strategy_name": self._strategy_name,
        }

        def emit_status(message: str) -> None:
            self.status.emit(self._request_id, self._action, str(message or ""))

        try:
            if self._action == "enable":
                result = autostart_public.enable_gui_autostart(status_cb=emit_status)
                if getattr(result, "success", False):
                    autostart_public.save_gui_autostart_enabled(True)
            elif self._action == "disable":
                result = autostart_public.disable_gui_autostart()
                if getattr(result, "success", False):
                    autostart_public.save_gui_autostart_enabled(False)
            elif self._action == "save_state":
                result = autostart_public.save_gui_autostart_enabled(bool(self._enabled))
            else:
                raise ValueError(f"Неизвестное действие автозапуска: {self._action}")
        except Exception as exc:
            log(f"AutostartActionWorker: не удалось выполнить {self._action}: {exc}", "WARNING")
            self.failed.emit(self._request_id, self._action, str(exc), context)
            return
        self.completed.emit(self._request_id, self._action, result, context)


class AutostartModeLoadWorker(QThread):
    loaded = pyqtSignal(int, str)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)

    def run(self) -> None:
        import autostart.public as autostart_public

        try:
            method = str(autostart_public.get_current_launch_method() or "").strip()
        except Exception as exc:
            log(f"AutostartModeLoadWorker: не удалось загрузить режим запуска: {exc}", "WARNING")
            self.failed.emit(self._request_id, str(exc))
            return
        self.loaded.emit(self._request_id, method)
