from __future__ import annotations

import os

from log import log
from ui.page_names import PageName
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

    def delayed_dpi_start(self) -> None:
        """Выполняет отложенный запуск DPI с проверкой наличия автозапуска."""
        if hasattr(self, "launch_autostart_manager"):
            self.launch_autostart_manager.delayed_dpi_start()

    def on_strategy_selected_from_dialog(self, strategy_id: str, strategy_name: str) -> None:
        """Обрабатывает выбор стратегии из диалога."""
        try:
            log(f"Выбрана стратегия: {strategy_name} (ID: {strategy_id})", level="INFO")

            from settings.dpi.strategy_settings import get_strategy_launch_method

            launch_method = get_strategy_launch_method()

            if launch_method == "direct_zapret2":
                try:
                    preset = self.app_context.direct_flow_coordinator.get_selected_source_manifest("direct_zapret2")
                    preset_name = str(getattr(preset, "name", "") or "")
                    display_name = f"Пресет: {preset_name}"
                except Exception:
                    display_name = "Пресет"
                strategy_name = display_name
                log(f"Установлено имя пресета для direct_zapret2: {display_name}", "DEBUG")
            elif strategy_id == "DIRECT_MODE" or launch_method == "direct_zapret1":
                if launch_method == "direct_zapret1":
                    try:
                        preset = self.app_context.direct_flow_coordinator.get_selected_source_manifest("direct_zapret1")
                        preset_name = str(getattr(preset, "name", "") or "")
                        display_name = f"Пресет: {preset_name}"
                    except Exception:
                        display_name = "Пресет"
                else:
                    log(
                        f"Выбран неподдерживаемый direct-режим запуска: {launch_method}",
                        "ERROR",
                    )
                    self.set_status("Ошибка: выбран удалённый или неподдерживаемый режим запуска")
                    return
                strategy_name = display_name
                log(f"Установлено простое название для режима {launch_method}: {display_name}", "DEBUG")

            ensure_window_adapter(self).update_current_strategy_display(strategy_name)

            if launch_method in ("direct_zapret2", "direct_zapret1", "orchestra"):
                log(
                    f"Запуск {launch_method} передан в единый DPI controller pipeline",
                    "INFO",
                )
                self.launch_controller.start_dpi_async(selected_mode=None, launch_method=launch_method)
            else:
                raise RuntimeError(f"Неподдерживаемый метод запуска: {launch_method}")

        except Exception as e:
            log(f"Ошибка при установке выбранной стратегии: {str(e)}", level="❌ ERROR")
            import traceback

            log(f"Traceback: {traceback.format_exc()}", "DEBUG")
            self.set_status(f"Ошибка при установке стратегии: {str(e)}")

    def show_subscription_dialog(self) -> None:
        """Переключается на страницу Premium."""
        try:
            ensure_window_adapter(self).show_page(PageName.PREMIUM)
        except Exception as e:
            log(f"Ошибка при переходе на страницу Premium: {e}", level="❌ ERROR")

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
