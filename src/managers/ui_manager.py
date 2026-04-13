# managers/ui_manager.py

from log.log import log


class UIManager:
    """Менеджер UI-вещей, не связанных с runtime-состоянием запуска."""
    
    def __init__(self, app_instance):
        self.app = app_instance

    def update_title_with_subscription_status(self, is_premium: bool, current_theme: str, 
                                            days_remaining: int, source: str = "api") -> None:
        """⚡ Обновляет заголовок окна с информацией о подписке"""
        try:
            from config.build_info import APP_VERSION

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
