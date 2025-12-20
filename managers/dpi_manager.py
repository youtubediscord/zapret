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
            self._finish_splash("Готово", "Автозапуск отключен")
            self._update_ui(running=False)
            return

        # 2. Определяем режим запуска (Direct или BAT)
        from strategy_menu import get_strategy_launch_method
        launch_method = get_strategy_launch_method()
        
        # 3. Запускаем соответствующий режим
        if launch_method in ("direct", "direct_orchestra"):
            self._start_direct_mode()
        elif launch_method == "orchestra":
            self._start_orchestra_mode()
        else:
            self._start_bat_mode()
    
    def _update_ui(self, running: bool):
        """Обновляет UI состояние"""
        if hasattr(self.app, 'ui_manager'):
            self.app.ui_manager.update_ui_state(running=running)
    
    def _update_splash(self, progress: int, message: str, subtitle: str = ""):
        """Обновляет splash screen"""
        if hasattr(self.app, 'splash') and self.app.splash:
            self.app.splash.set_progress(progress, message, subtitle)
    
    def _finish_splash(self, message: str, subtitle: str = ""):
        """Завершает splash screen"""
        self._update_splash(100, message, subtitle)

    def _start_direct_mode(self):
        """⚡ Запускает Direct режим (комбинированные стратегии)"""
        from strategy_menu import (
            get_direct_strategy_selections, get_strategy_launch_method,
            is_direct_orchestra_initialized, set_direct_orchestra_initialized, clear_direct_orchestra_strategies
        )
        from strategy_menu.strategy_lists_separated import combine_strategies

        # ✅ При ПЕРВОМ запуске в режиме direct_orchestra - сбрасываем все стратегии в "none"
        launch_method = get_strategy_launch_method()
        if launch_method == "direct_orchestra" and not is_direct_orchestra_initialized():
            log("🆕 Первая инициализация DirectOrchestra при автозапуске - сброс всех стратегий в 'none'", "INFO")
            clear_direct_orchestra_strategies()
            set_direct_orchestra_initialized(True)

        # Получаем выборы пользователя и комбинируем стратегии
        selections = get_direct_strategy_selections()
        combined = combine_strategies(**selections)
        
        # Проверка: есть ли активные категории?
        if combined.get('_active_categories', 0) == 0:
            log("Автозапуск пропущен: нет активных категорий", "INFO")
            self.app.set_status("⚠️ Выберите хотя бы одну категорию")
            self._finish_splash("Готово", "Категории не выбраны")
            self._update_ui(running=False)
            return
        
        # Подготавливаем данные для запуска
        strategy_data = {
            'id': 'DIRECT_MODE',
            'name': 'Прямой запуск',
            'is_combined': True,
            'args': combined['args'],
            'selections': selections
        }
        
        log(f"Автозапуск Direct: {selections}", "INFO")

        # Обновляем UI и запускаем
        self.app.current_strategy_label.setText("Прямой запуск")
        self.app.current_strategy_name = "Прямой запуск"
        self._update_splash(65, "Запуск Direct режима...")
        self.app.dpi_controller.start_dpi_async(selected_mode=strategy_data, launch_method="direct")
        self._update_ui(running=True)

    def _start_bat_mode(self):
        """⚡ Запускает BAT стратегию"""
        from config.reg import get_last_bat_strategy

        strategy_name = get_last_bat_strategy()
        log(f"Автозапуск BAT: «{strategy_name}»", "INFO")

        # Обновляем UI и запускаем
        self.app.current_strategy_label.setText(strategy_name)
        self.app.current_strategy_name = strategy_name
        self._update_splash(65, f"Запуск '{strategy_name}'...")
        self.app.dpi_controller.start_dpi_async(selected_mode=strategy_name, launch_method="bat")
        self._update_ui(running=True)

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

            # Подготавливаем и запускаем
            self._update_splash(65, "Подготовка оркестратора...")

            if not self.app.orchestra_runner.prepare():
                log("Ошибка подготовки оркестратора", "ERROR")
                self.app.set_status("❌ Ошибка подготовки оркестратора")
                self._finish_splash("Ошибка", "Не удалось подготовить оркестратор")
                self._update_ui(running=False)
                return

            self._update_splash(80, "Запуск оркестратора...")

            if not self.app.orchestra_runner.start():
                log("Ошибка запуска оркестратора", "ERROR")
                self.app.set_status("❌ Ошибка запуска оркестратора")
                self._finish_splash("Ошибка", "Не удалось запустить")
                self._update_ui(running=False)
                return

            # Обновляем UI
            self.app.current_strategy_label.setText("Оркестр (автообучение)")
            self.app.current_strategy_name = "Оркестр"
            self._update_ui(running=True)
            self._finish_splash("Готово", "Оркестратор запущен")

            # Запускаем мониторинг на странице оркестра
            if hasattr(self.app, 'orchestra_page'):
                self.app.orchestra_page.start_monitoring()

        except Exception as e:
            log(f"Ошибка запуска Orchestra: {e}", "ERROR")
            self.app.set_status(f"❌ Ошибка: {e}")
            self._finish_splash("Ошибка", str(e))
            self._update_ui(running=False)

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