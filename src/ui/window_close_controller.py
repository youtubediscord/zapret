from __future__ import annotations

from log.log import log



class WindowCloseController:
    """Единый контроллер поведения при закрытии главного окна.

    Здесь решается только пользовательский сценарий закрытия:
    показать диалог, свернуть в трей или выбрать полный выход.
    Само финальное освобождение ресурсов остаётся в main.closeEvent.
    """

    def __init__(self, host) -> None:
        self.host = host

    def should_continue_final_close(self, event) -> bool:
        """Возвращает True только для окончательного закрытия приложения."""
        if self.host._closing_completely:
            return True

        try:
            event.ignore()
        except Exception:
            pass

        try:
            from ui.close_dialog import ask_close_action

            result = ask_close_action(parent=self.host)
            if result is None:
                return False

            if result == "tray":
                minimized = bool(self.host.close_to_tray())
                if not minimized:
                    log("Сценарий 'свернуть в трей' не выполнен: tray manager не готов", "WARNING")
                return False

            if bool(result):
                self.host.exit_stop_dpi()
            else:
                self.host.exit_keep_dpi()
            return False
        except Exception as e:
            log(f"Ошибка пользовательского сценария закрытия окна: {e}", "DEBUG")
            return False
