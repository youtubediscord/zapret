from PyQt6.QtCore import QObject
from log import log
from ui.window_adapter import ensure_window_adapter

class LaunchAutostartManager(QObject):
    """⚡ Упрощенный менеджер для автозапуска launch-контура."""
    
    def __init__(self, app_instance):
        super().__init__()
        self.app = app_instance
        self._autostart_initiated = False

    def delayed_dpi_start(self, launch_method: str | None = None) -> None:
        """Запускает автозапуск через один общий dispatcher."""

        # Защита от двойного вызова
        if self._autostart_initiated:
            log("Автозапуск DPI уже выполнен", "DEBUG")
            return

        self._autostart_initiated = True

        from config import get_dpi_autostart
        if not get_dpi_autostart():
            log("Автозапуск DPI отключён", "INFO")
            self._mark_runtime_stopped()
            return

        from settings.dpi.strategy_settings import get_strategy_launch_method
        resolved_method = str(launch_method or get_strategy_launch_method() or "").strip().lower()

        supported_methods = {
            "direct_zapret2",
            "direct_zapret1",
            "orchestra",
        }
        if resolved_method not in supported_methods:
            log(f"Автозапуск не поддерживается для метода: {resolved_method or 'unknown'}", "WARNING")
            self._mark_runtime_stopped()
            return

        display_name = self._resolve_startup_display_name(resolved_method)
        if display_name:
            ensure_window_adapter(self.app).update_current_strategy_display(display_name)

        log(f"Автозапуск передан в единый DPI controller pipeline: {resolved_method}", "INFO")
        self.app.launch_controller.start_dpi_async(selected_mode=None, launch_method=resolved_method)

    def _mark_runtime_stopped(self) -> None:
        runtime_service = getattr(self.app, "launch_runtime_service", None)
        if runtime_service is None:
            return
        runtime_service.mark_stopped(clear_error=True)

    def _resolve_startup_display_name(self, launch_method: str) -> str:
        method = str(launch_method or "").strip().lower()
        try:
            if method in {"direct_zapret1", "direct_zapret2"}:
                snapshot = self.app.app_context.direct_flow_coordinator.get_startup_snapshot(method)
                return str(snapshot.display_name or "").strip() or "Пресет"

            if method == "orchestra":
                return "Оркестр"
        except Exception as e:
            log(f"Не удалось определить стартовое имя стратегии для {method}: {e}", "DEBUG")

        return ""
