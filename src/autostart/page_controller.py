from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from log import log


class AutostartDetectorWorker(QThread):
    """Фоновая проверка канонического GUI-автозапуска."""

    finished = pyqtSignal(bool)

    def run(self):
        try:
            self.finished.emit(AutostartPageController.detect_autostart_enabled())
        except Exception as exc:
            log(f"AutostartDetectorWorker error: {exc}", "WARNING")
            self.finished.emit(False)


class AutostartPageController:
    @staticmethod
    def create_detector_worker() -> AutostartDetectorWorker:
        return AutostartDetectorWorker()

    @staticmethod
    def detect_autostart_enabled() -> bool:
        from autostart.registry_check import is_autostart_enabled

        return bool(is_autostart_enabled())

    @staticmethod
    def should_schedule_initial_detection(*, runtime_initialized: bool) -> bool:
        return not bool(runtime_initialized)

    @staticmethod
    def should_start_detection(*, detection_pending: bool, worker_running: bool) -> bool:
        return not bool(detection_pending) and not bool(worker_running)

    @staticmethod
    def resolve_app_init(parent_widget, *, strategy_name: str | None, strategy_not_selected_text: str) -> tuple[object | None, str | None, str]:
        app_instance = None
        widget = parent_widget
        while widget is not None:
            if hasattr(widget, "dpi_controller"):
                app_instance = widget
                log("AutostartPage: app_instance найден через parent", "DEBUG")
                break
            widget = widget.parent() if hasattr(widget, "parent") else None

        resolved_strategy = strategy_name
        if app_instance is not None and not resolved_strategy:
            store = getattr(app_instance, "ui_state_store", None)
            if store is not None:
                current = store.snapshot().current_strategy_summary
                if current:
                    resolved_strategy = current

        return app_instance, resolved_strategy, resolved_strategy or strategy_not_selected_text

    @staticmethod
    def disable_autostart() -> int:
        from autostart.autostart_remove import AutoStartCleaner

        cleaner = AutoStartCleaner()
        return int(cleaner.run(remove_canonical=True, remove_legacy=True) or 0)

    @staticmethod
    def setup_gui_autostart(*, status_cb=None) -> bool:
        from autostart.autostart_exe import setup_autostart_for_exe

        return bool(setup_autostart_for_exe(status_cb=status_cb))
