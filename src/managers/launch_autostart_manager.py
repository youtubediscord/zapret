from PyQt6.QtCore import QObject
from log.log import log

from ui.window_adapter import update_window_current_strategy_display

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

        from settings.store import get_dpi_autostart

        if not get_dpi_autostart():
            log("Автозапуск DPI отключён", "INFO")
            self._mark_runtime_stopped()
            return

        from settings.dpi.strategy_settings import get_strategy_launch_method
        resolved_method = str(launch_method or get_strategy_launch_method() or "").strip().lower()

        supported_methods = {
            "zapret2_mode",
            "zapret1_mode",
            "orchestra",
        }
        if resolved_method not in supported_methods:
            log(f"Автозапуск не поддерживается для метода: {resolved_method or 'unknown'}", "WARNING")
            self._mark_runtime_stopped()
            return

        startup_snapshot = self._resolve_startup_snapshot(resolved_method)
        display_name = self._resolve_startup_display_name(resolved_method, startup_snapshot=startup_snapshot)
        if display_name:
            update_window_current_strategy_display(self.app, display_name)

        log(f"Автозапуск передан в единый DPI controller pipeline: {resolved_method}", "INFO")
        self.app.launch_controller.start_dpi_async(
            selected_mode=startup_snapshot.to_selected_mode() if startup_snapshot is not None else None,
            launch_method=resolved_method,
            _startup_autostart=True,
        )

    def _mark_runtime_stopped(self) -> None:
        runtime_service = getattr(self.app, "launch_runtime_service", None)
        if runtime_service is None:
            return
        runtime_service.mark_stopped(clear_error=True)

    def _resolve_startup_snapshot(self, launch_method: str):
        method = str(launch_method or "").strip().lower()
        try:
            if method in {"zapret1_mode", "zapret2_mode"}:
                return self.app.app_context.preset_mode_coordinator.get_startup_snapshot(
                    method,
                    require_filters=True,
                )
        except Exception as e:
            log(f"Не удалось подготовить стартовый пресет для {method}: {e}", "DEBUG")

        return None

    def _resolve_startup_display_name(self, launch_method: str, *, startup_snapshot=None) -> str:
        method = str(launch_method or "").strip().lower()
        try:
            if method in {"zapret1_mode", "zapret2_mode"}:
                snapshot = startup_snapshot or self._resolve_startup_snapshot(method)
                if snapshot is not None:
                    return str(snapshot.display_name or "").strip() or "Пресет"

            if method == "orchestra":
                return "Оркестр"
        except Exception as e:
            log(f"Не удалось определить стартовое имя стратегии для {method}: {e}", "DEBUG")

        return ""
