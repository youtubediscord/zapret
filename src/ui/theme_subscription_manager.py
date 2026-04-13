# ui/theme_subscription_manager.py
"""
Менеджер для работы с темами и подписками.
Содержит всю логику обновления UI в зависимости от статуса подписки и текущей темы.
"""

from typing import Optional
from PyQt6.QtWidgets import QWidget
from log.log import log

from config.build_info import APP_VERSION


class ThemeSubscriptionManager:
    """
    Миксин-класс для управления темами и отображением статуса подписки.
    Должен использоваться вместе с основным классом окна.
    """

    def update_title_with_subscription_status(self: QWidget, is_premium: bool = False, 
                                            current_theme: str = None, 
                                            days_remaining: Optional[int] = None,
                                            source: str = "api"):
        """
        ✅ ОБНОВЛЕНО: Обновляет заголовок окна с информацией о подписке
        
        Args:
            is_premium: True если пользователь имеет премиум подписку
            current_theme: Текущая тема интерфейса
            days_remaining: Количество дней до окончания подписки (None для offline/безлимит)
            source: Источник данных ('api', 'offline', 'init')
        """
        # Обновляем системный заголовок окна
        base_title = f'Zapret2 v{APP_VERSION}'
        
        if is_premium:
            # ✅ ОБРАБОТКА ВСЕХ СЛУЧАЕВ
            if days_remaining is not None:
                if days_remaining > 0:
                    premium_text = f" [PREMIUM - {days_remaining} дн.]"
                elif days_remaining == 0:
                    premium_text = " [PREMIUM - истекает сегодня]"
                else:
                    # Отрицательное значение (не должно быть в новой системе)
                    premium_text = " [PREMIUM - истёк]"
            else:
                # None - offline режим или безлимитная подписка
                if source == "offline":
                    premium_text = " [PREMIUM - offline]"
                else:
                    premium_text = " [PREMIUM]"
                
            full_title = f"{base_title}{premium_text}"
            self.setWindowTitle(full_title)
            log(f"Заголовок окна обновлен: {full_title} (source: {source})", "DEBUG")
        else:
            self.setWindowTitle(base_title)
            log(f"Заголовок окна: FREE режим (source: {source})", "DEBUG")

        # ✅ title_label больше не используется в новом интерфейсе
        # Статус отображается только в заголовке окна (setWindowTitle выше)


