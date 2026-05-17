from __future__ import annotations

from log.log import log


def connect_windows_session_shutdown(app, window) -> None:
    """Подключает быстрый выход при завершении сеанса Windows."""
    signal = getattr(app, "commitDataRequest", None)
    if signal is None:
        log("Qt commitDataRequest недоступен: обработчик завершения Windows не подключён", "DEBUG")
        return

    def _on_commit_data_request(_session_manager=None) -> None:
        try:
            window.exit_for_windows_session_end()
        except Exception as exc:
            log(f"Ошибка обработки завершения сеанса Windows: {exc}", "WARNING")

    try:
        signal.connect(_on_commit_data_request)
        log("Обработчик завершения сеанса Windows подключён", "DEBUG")
    except Exception as exc:
        log(f"Не удалось подключить обработчик завершения сеанса Windows: {exc}", "WARNING")


__all__ = ["connect_windows_session_shutdown"]
