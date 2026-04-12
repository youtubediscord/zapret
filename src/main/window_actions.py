from __future__ import annotations

from log import log
from ui.page_method_dispatch import request_blockcheck_diagnostics_focus
from ui.window_adapter import ensure_window_adapter
from utils import run_hidden


class WindowActionsMixin:
    def set_status(self, text: str) -> None:
        """Пишет пользовательский статус в лог.

        Раньше этот helper складывал текст в window-level UI store, но отдельного
        глобального потребителя у такого канала больше нет. Оставляем единый
        entry-point для вызовов, но без декоративной записи в неиспользуемое
        состояние окна.
        """
        level = "INFO"
        lower_text = text.lower()
        if "работает" in lower_text or "запущен" in lower_text or "успешно" in lower_text:
            level = "INFO"
        elif "останов" in lower_text or "ошибка" in lower_text or "выключен" in lower_text:
            level = "WARNING"
        elif "внимание" in lower_text or "предупреждение" in lower_text:
            level = "WARNING"
        log(str(text or ""), level)

    def open_folder(self) -> None:
        """Opens the DPI folder."""
        try:
            run_hidden("explorer.exe .", shell=True)
        except Exception as e:
            self.set_status(f"Ошибка при открытии папки: {str(e)}")

    def open_connection_test(self) -> None:
        """Переключает на вкладку диагностики соединений."""
        try:
            adapter = ensure_window_adapter(self)
            if adapter.show_page(PageName.BLOCKCHECK):
                adapter.route_search_result(PageName.BLOCKCHECK, "diagnostics")
                request_blockcheck_diagnostics_focus(self)
                log("Открыта вкладка диагностики в BlockCheck", "INFO")
        except Exception as e:
            log(f"Ошибка при открытии вкладки тестирования: {e}", "❌ ERROR")
            self.set_status(f"Ошибка: {e}")
