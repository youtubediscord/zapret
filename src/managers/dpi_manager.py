from PyQt6.QtCore import QObject
from log import log

class DPIManager(QObject):
    """⚡ Упрощенный менеджер для управления DPI операциями"""
    
    def __init__(self, app_instance):
        super().__init__()
        self.app = app_instance
        self._autostart_initiated = False

    def delayed_dpi_start(self) -> None:
        """⚡ Быстрый автозапуск DPI при старте приложения"""
        
        # Защита от двойного вызова
        if self._autostart_initiated:
            log("Автозапуск DPI уже выполнен", "DEBUG")
            return
        
        self._autostart_initiated = True
        
        # 1. Проверяем, включен ли автозапуск
        from config import get_dpi_autostart
        if not get_dpi_autostart():
            log("Автозапуск DPI отключён", "INFO")
            self._set_runtime_dpi_running(False)
            return

        # 2. Определяем режим запуска (Direct или BAT)
        from strategy_menu import get_strategy_launch_method
        launch_method = get_strategy_launch_method()

        # 3. Запускаем соответствующий режим
        # ⚠️ ВАЖНО: direct_zapret2 обрабатывается отдельно в initialization_manager._start_direct_zapret2_autostart()
        # и использует preset файл, поэтому НЕ включаем его здесь (иначе будет двойной вызов и перезапись файла)
        if launch_method == "direct_zapret2_orchestra":
            self._start_direct_mode()
        elif launch_method == "direct_zapret1":
            self._start_direct_zapret1_mode()
        elif launch_method == "orchestra":
            self._start_orchestra_mode()
        else:
            log(f"Неизвестный метод автозапуска: {launch_method}", "WARNING")
    
    def _set_runtime_dpi_running(self, running: bool) -> None:
        runtime_service = getattr(self.app, "dpi_runtime_service", None)
        if runtime_service is None:
            return
        if running:
            runtime_service.mark_running()
        else:
            runtime_service.mark_stopped(clear_error=True)

    def _start_direct_mode(self):
        """⚡ Запускает direct_zapret2_orchestra через preset файл"""
        from strategy_menu import get_strategy_launch_method
        from preset_orchestra_zapret2 import (
            ensure_default_preset_exists,
            get_active_preset_path,
            get_active_preset_name,
        )

        launch_method = get_strategy_launch_method()
        if launch_method != "direct_zapret2_orchestra":
            log(f"_start_direct_mode вызван для неподдерживаемого режима: {launch_method}", "WARNING")
            self._set_runtime_dpi_running(False)
            return

        if not ensure_default_preset_exists():
            log("Автозапуск direct_zapret2_orchestra пропущен: не удалось создать preset-zapret2-orchestra.txt", "WARNING")
            self._set_runtime_dpi_running(False)
            return

        preset_path = get_active_preset_path()
        if not preset_path.exists():
            log("Автозапуск direct_zapret2_orchestra пропущен: preset-zapret2-orchestra.txt не найден", "INFO")
            self.app.set_status("⚠️ Выберите стратегию в разделе Оркестратор Z2")
            self._set_runtime_dpi_running(False)
            return

        preset_name = get_active_preset_name() or "Default"
        strategy_data = {
            'is_preset_file': True,
            'name': f"Пресет оркестра: {preset_name}",
            'preset_path': str(preset_path),
        }

        log(f"Автозапуск direct_zapret2_orchestra из preset файла: {preset_path}", "INFO")
        if hasattr(self.app, "update_current_strategy_display"):
            self.app.update_current_strategy_display(f"Пресет оркестра: {preset_name}")
        self.app.dpi_controller.start_dpi_async(selected_mode=strategy_data, launch_method=launch_method)

    def _start_direct_zapret1_mode(self):
        """⚡ Запускает режим Zapret1 через выбранный source-пресет"""
        try:
            from core.services import get_direct_flow_coordinator

            profile = get_direct_flow_coordinator().ensure_launch_profile("direct_zapret1", require_filters=False)
            strategy_data = profile.to_selected_mode()
        except Exception as e:
            log(f"Автозапуск Zapret1 пропущен: {e}", "WARNING")
            self.app.set_status("⚠️ Не удалось подготовить пресет для запуска")
            self._set_runtime_dpi_running(False)
            return

        log(f"Автозапуск Zapret1 из выбранного source-пресета: {profile.launch_config_path}", "INFO")
        if hasattr(self.app, "update_current_strategy_display"):
            self.app.update_current_strategy_display(profile.display_name)
        self.app.dpi_controller.start_dpi_async(selected_mode=strategy_data, launch_method="direct_zapret1")

    def _start_orchestra_mode(self):
        """⚡ Запускает режим Оркестра (автообучение)"""
        try:
            from orchestra import OrchestraRunner

            log("Автозапуск Orchestra: автообучение", "INFO")

            # Создаём runner если его нет
            if not hasattr(self.app, 'orchestra_runner'):
                self.app.orchestra_runner = OrchestraRunner()

            # Устанавливаем callback для авторестарта при Discord FAIL
            self.app.orchestra_runner.restart_callback = self._on_discord_fail_restart

            # НЕ используем callback - UI обновляется через таймер (чтение лог-файла)
            # Это безопаснее, т.к. callback вызывается из reader thread

            if not self.app.orchestra_runner.prepare():
                log("Ошибка подготовки оркестратора", "ERROR")
                self.app.set_status("❌ Ошибка подготовки оркестратора")
                self._set_runtime_dpi_running(False)
                return

            if not self.app.orchestra_runner.start():
                log("Ошибка запуска оркестратора", "ERROR")
                self.app.set_status("❌ Ошибка запуска оркестратора")
                self._set_runtime_dpi_running(False)
                return

            # Обновляем UI
            if hasattr(self.app, "update_current_strategy_display"):
                self.app.update_current_strategy_display("Оркестр")
            runtime_service = getattr(self.app, "dpi_runtime_service", None)
            if runtime_service is not None:
                runtime_service.begin_start(launch_method="orchestra")
                runtime_service.mark_running()

            # Запускаем мониторинг на странице оркестра
            if hasattr(self.app, 'orchestra_page'):
                self.app.orchestra_page.start_monitoring()

        except Exception as e:
            log(f"Ошибка запуска Orchestra: {e}", "ERROR")
            self.app.set_status(f"❌ Ошибка: {e}")
            self._set_runtime_dpi_running(False)

    def _on_discord_fail_restart(self):
        """Callback для перезапуска Discord при FAIL"""
        try:
            from PyQt6.QtCore import QTimer
            log("🔄 Запланирован перезапуск Discord из-за FAIL", "WARNING")

            # Используем QTimer для выполнения в главном потоке
            QTimer.singleShot(500, self._do_discord_restart)

        except Exception as e:
            log(f"Ошибка планирования перезапуска Discord: {e}", "ERROR")

    def _do_discord_restart(self):
        """Выполняет перезапуск Discord"""
        try:
            log("🔄 Перезапуск Discord из-за FAIL...", "INFO")

            if hasattr(self.app, 'discord_manager') and self.app.discord_manager:
                self.app.discord_manager.restart_discord_if_running()
            else:
                log("discord_manager недоступен", "WARNING")

        except Exception as e:
            log(f"Ошибка перезапуска Discord: {e}", "ERROR")
            if hasattr(self.app, 'set_status'):
                self.app.set_status("⚠️ Не удалось перезапустить Discord")
