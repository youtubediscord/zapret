# managers/ui_manager.py

from log import log

class UIManager:
    """⚡ Упрощенный менеджер для управления UI компонентами"""
    
    def __init__(self, app_instance):
        self.app = app_instance
    
    def _get_strategy_name(self) -> str:
        """Получает текущее имя стратегии"""
        if hasattr(self.app, 'current_strategy_label'):
            strategy_name = self.app.current_strategy_label.text()
            if strategy_name == "Автостарт DPI отключен":
                from config import get_last_strategy
                return get_last_strategy()
            return strategy_name
        return None

    def update_theme_gallery(self, available_themes: list = None) -> None:
        """Обновляет галерею тем на странице оформления"""
        if hasattr(self.app, 'theme_handler') and self.app.theme_handler:
            self.app.theme_handler.update_available_themes()
            log("Галерея тем обновлена", "DEBUG")


    def update_autostart_ui(self, service_running: bool) -> None:
        """Обновляет интерфейс при включении/выключении автозапуска"""
        try:
            # Используем быструю проверку через реестр если нужно
            if service_running is None:
                from autostart.registry_check import is_autostart_enabled
                service_running = is_autostart_enabled()
            
            # Определяем статус процесса
            process_running = service_running
            if not service_running and hasattr(self.app, 'dpi_starter'):
                process_running = self.app.dpi_starter.check_process_running_wmi(silent=True)
            
            # Обновляем все страницы
            self._update_all_pages(process_running, service_running)
            
            log(f"Автозапуск UI обновлен: {'включен' if service_running else 'выключен'}", "DEBUG")
        except Exception as e:
            log(f"Ошибка в update_autostart_ui: {e}", "ERROR")

    def update_ui_state(self, running: bool) -> None:
        """Обновляет состояние UI в зависимости от статуса запуска DPI"""
        try:
            # Проверяем статус автозапуска
            autostart_active = False
            if hasattr(self.app, 'service_manager'):
                autostart_active = self.app.service_manager.check_autostart_exists()
            
            # Обновляем все страницы
            self._update_all_pages(running, autostart_active)
        except Exception as e:
            log(f"Ошибка в update_ui_state: {e}", "ERROR")
    
    def _update_all_pages(self, is_running: bool, autostart_active: bool) -> None:
        """⚡ Обновляет все страницы одним методом"""
        try:
            strategy_name = self._get_strategy_name()
            
            # Обновляем главную страницу
            if hasattr(self.app, 'home_page'):
                self.app.home_page.update_dpi_status(is_running, strategy_name)
            
            # Обновляем страницу управления
            if hasattr(self.app, 'control_page'):
                self.app.control_page.update_status(is_running)
                if strategy_name:
                    self.app.control_page.update_strategy(strategy_name)
            
            # Обновляем страницу стратегий
            if hasattr(self.app, 'strategies_page') and strategy_name:
                self.app.strategies_page.update_current_strategy(strategy_name)
            
            # Обновляем страницу автозапуска
            if hasattr(self.app, 'autostart_page'):
                self.app.autostart_page.update_status(autostart_active, strategy_name)
        except Exception as e:
            log(f"Ошибка в _update_all_pages: {e}", "DEBUG")

    def update_title_with_subscription_status(self, is_premium: bool, current_theme: str, 
                                            days_remaining: int, source: str = "api") -> None:
        """⚡ Обновляет заголовок окна с информацией о подписке"""
        try:
            from config import APP_VERSION
            base_title = f"Zapret2 v{APP_VERSION}"
            
            # Формируем статус премиума
            if is_premium:
                if days_remaining is not None and days_remaining > 0:
                    if days_remaining <= 7:
                        title = f"{base_title} - Premium ({days_remaining} дн.)"
                    else:
                        title = f"{base_title} - Premium"
                elif days_remaining == 0:
                    title = f"{base_title} - Premium (истекает сегодня)"
                else:
                    title = f"{base_title} - Premium (offline)" if source == "offline" else f"{base_title} - Premium"
            else:
                title = base_title
            
            # Добавляем тему если она премиум
            if current_theme and "(Premium)" in current_theme:
                clean_theme = current_theme.replace(" (Premium)", "").replace(" (заблокировано)", "")
                title += f" | {clean_theme}"
            
            self.app.setWindowTitle(title)
            log(f"Заголовок: {title}", "DEBUG")
        except Exception as e:
            log(f"Ошибка обновления заголовка: {e}", "ERROR")

    def update_subscription_button_text(self, is_premium: bool, days_remaining: int) -> None:
        """⚡ Обновляет текст кнопки подписки"""
        try:
            if not hasattr(self.app, 'subscription_btn'):
                return
            
            # Определяем текст кнопки
            if is_premium:
                if days_remaining is not None and days_remaining > 0:
                    text = f"Premium (осталось {days_remaining} дн.)" if days_remaining <= 7 else "Premium активен"
                elif days_remaining == 0:
                    text = "Premium (истекает сегодня!)"
                else:
                    text = "Premium активен"
            else:
                text = "Получить Premium"
            
            self.app.subscription_btn.setText(text)
        except Exception as e:
            log(f"Ошибка обновления кнопки подписки: {e}", "ERROR")

    def force_enable_combos(self) -> bool:
        """Устаревший метод для обратной совместимости"""
        log("force_enable_combos вызван (пустая заглушка)", "DEBUG")
        return True

    def update_strategies_list(self, force_update: bool = False) -> None:
        """⚡ Обновляет список доступных стратегий"""
        try:
            if not hasattr(self.app, 'strategy_manager'):
                log("Strategy manager не инициализирован", "ERROR")
                return
            
            # Получаем список стратегий
            strategies = self.app.strategy_manager.get_strategies_list(force_update=force_update)
            log(f"Загружено {len(strategies) if strategies else 0} стратегий", "INFO")
            
            # Обновляем текущую метку если нужно
            current_strategy = self._get_strategy_name()
            if current_strategy and current_strategy != "Автостарт DPI отключен":
                if hasattr(self.app, 'current_strategy_label'):
                    self.app.current_strategy_label.setText(current_strategy)
        except Exception as e:
            log(f"Ошибка обновления списка стратегий: {e}", "ERROR")
            if hasattr(self.app, 'set_status'):
                self.app.set_status(f"Ошибка: {e}")
