# ui/theme_subscription_manager.py
"""
Менеджер для работы с темами и подписками.
Содержит всю логику обновления UI в зависимости от статуса подписки и текущей темы.
"""

from typing import Optional
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QWidget
from log import log
from config import APP_VERSION
from ui.theme import COMMON_STYLE

def apply_initial_theme(app):
    """
    Применяет начальную тему при запуске приложения.
    
    Args:
        app: Экземпляр QApplication
    """
    try:
        import qt_material
        qt_material.apply_stylesheet(app, 'dark_blue.xml')
        log("Начальная тема применена", "INFO")
    except Exception as e:
        log(f"Ошибка применения начальной темы: {e}", "❌ ERROR")
        # Fallback - используем базовые стили Qt
        app.setStyleSheet("")


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
        
        # Обновляем title_label с цветным статусом
        base_label_title = "Zapret 2 GUI"
        
        # Определяем текущую тему
        actual_current_theme = current_theme
        if not actual_current_theme and hasattr(self, 'theme_manager'):
            actual_current_theme = getattr(self.theme_manager, 'current_theme', None)
        
        # ✅ title_label больше не используется в новом интерфейсе
        # Статус отображается только в заголовке окна (setWindowTitle выше)
        pass
    
    def _get_free_indicator_color(self, current_theme: str = None) -> str:
        """
        Возвращает цвет для индикатора [FREE] на основе текущей темы.
        
        Args:
            current_theme: Название текущей темы
            
        Returns:
            str: Цвет в формате hex
        """
        try:
            theme_name = current_theme
            if not theme_name and hasattr(self, 'theme_manager'):
                theme_name = getattr(self.theme_manager, 'current_theme', None)
            
            if not theme_name:
                return "#000000"
            
            # Специальная обработка для полностью черной темы
            if theme_name == "Полностью черная":
                return "#ffffff"  # Белый цвет для полностью черной темы
            
            # Определяем цвет на основе названия темы
            if (theme_name.startswith("Темная") or 
                theme_name == "РКН Тян" or 
                theme_name.startswith("AMOLED")):
                return "#BBBBBB"
            elif theme_name.startswith("Светлая"):
                return "#000000"
            else:
                return "#000000"
                
        except Exception as e:
            log(f"Ошибка определения цвета FREE индикатора: {e}", "❌ ERROR")
            return "#000000"
    
    def _get_premium_indicator_color(self, current_theme: str = None) -> str:
        """
        Возвращает цвет для индикатора премиум статуса.
        
        Args:
            current_theme: Название текущей темы
            
        Returns:
            str: Цвет в формате hex
        """
        try:
            theme_name = current_theme
            if not theme_name and hasattr(self, 'theme_manager'):
                theme_name = getattr(self.theme_manager, 'current_theme', None)
            
            if not theme_name:
                return "#FFD700"
            
            # Специальная обработка для полностью черной темы
            if theme_name == "Полностью черная":
                log("Применяем золотой цвет для PREMIUM в полностью черной теме", "DEBUG")
                return "#FFD700"
            
            # Для остальных тем определяем цвет на основе button_color
            try:
                from ui.theme import THEMES
                if theme_name in THEMES:
                    theme_info = THEMES[theme_name]
                    button_color = theme_info.get("button_color", "0, 119, 255")
                    
                    # Преобразуем RGB в hex
                    if ',' in button_color:
                        try:
                            rgb_values = [int(x.strip()) for x in button_color.split(',')]
                            hex_color = f"#{rgb_values[0]:02x}{rgb_values[1]:02x}{rgb_values[2]:02x}"
                            log(f"Цвет PREMIUM индикатора для темы {theme_name}: {hex_color}", "DEBUG")
                            return hex_color
                        except (ValueError, IndexError):
                            return "#4CAF50"
            except ImportError:
                pass
            
            return "#4CAF50"
            
        except Exception as e:
            log(f"Ошибка определения цвета PREMIUM индикатора: {e}", "❌ ERROR")
            return "#4CAF50"
    
    def update_subscription_button_text(self, is_premium: bool = False,
                                      days_remaining: Optional[int] = None):
        """
        ✅ ОБНОВЛЕНО: Обновляет текст кнопки подписки
        
        Args:
            is_premium: True если пользователь имеет премиум подписку
            days_remaining: Количество дней до окончания подписки (может быть None)
        """
        if not hasattr(self, 'subscription_btn'):
            return
        
        if is_premium:
            # ✅ ОБРАБОТКА ВСЕХ СЛУЧАЕВ
            if days_remaining is not None:
                if days_remaining > 0:
                    button_text = f" Premium ({days_remaining} дн.)"
                elif days_remaining == 0:
                    button_text = " Истекает сегодня!"
                else:
                    # Отрицательное (не должно быть)
                    button_text = " Premium истёк"
            else:
                # None - offline или безлимит
                button_text = " Premium активен"
        else:
            button_text = " Premium и VPN"
        
        self.subscription_btn.setText(button_text)
        log(f"Текст кнопки подписки обновлен: {button_text.strip()}", "DEBUG")
    
    def debug_theme_colors(self):
        """
        ✅ ОБНОВЛЕНО: Отладочный метод для проверки цветов темы
        """
        if hasattr(self, 'theme_manager'):
            current_theme = self.theme_manager.current_theme
            log(f"=== ОТЛАДКА ЦВЕТОВ ТЕМЫ ===", "DEBUG")
            log(f"Текущая тема: {current_theme}", "DEBUG")
            
            # Проверяем тип donate_checker
            checker_info = "отсутствует"
            if hasattr(self, 'donate_checker') and self.donate_checker:
                checker_info = f"{self.donate_checker.__class__.__name__}"
            log(f"DonateChecker: {checker_info}", "DEBUG")
            
            if hasattr(self, 'donate_checker') and self.donate_checker:
                try:
                    # ✅ ИСПОЛЬЗУЕМ НОВЫЙ API
                    sub_info = self.donate_checker.get_full_subscription_info()
                    
                    is_prem = sub_info['is_premium']
                    status_msg = sub_info['status_msg']
                    days = sub_info['days_remaining']
                    level = sub_info['subscription_level']
                    
                    premium_color = self._get_premium_indicator_color(current_theme)
                    free_color = self._get_free_indicator_color(current_theme)
                    
                    log(f"Премиум статус: {is_prem}", "DEBUG")
                    log(f"Статус сообщение: '{status_msg}'", "DEBUG")
                    log(f"Дни до окончания: {days}", "DEBUG")
                    log(f"Уровень подписки: {level}", "DEBUG")
                    log(f"Цвет PREMIUM индикатора: {premium_color}", "DEBUG")
                    log(f"Цвет FREE индикатора: {free_color}", "DEBUG")
                    
                    # Текущий текст заголовка
                    if hasattr(self, 'title_label'):
                        current_title = self.title_label.text()
                        log(f"Текущий заголовок: '{current_title}'", "DEBUG")
                    
                except Exception as e:
                    log(f"Ошибка отладки цветов: {e}", "❌ ERROR")
                    import traceback
                    log(f"Traceback: {traceback.format_exc()}", "DEBUG")
            
            log(f"=== КОНЕЦ ОТЛАДКИ ===", "DEBUG")
    
    def change_theme(self, theme_name: str):
        """Обработчик изменения темы."""
        # ✅ Проверяем и создаем theme_handler если нужно
        if not hasattr(self, 'theme_handler'):
            self.init_theme_handler()
        
        if hasattr(self, 'theme_handler') and self.theme_handler:
            self.theme_handler.change_theme(theme_name)
            # ✅ ОПТИМИЗАЦИЯ: Убран вызов debug_theme_colors из production
        else:
            log("ThemeHandler не инициализирован", "❌ ERROR")
            self.set_status("Ошибка: обработчик тем не инициализирован")

    def init_theme_handler(self):
        """Инициализирует theme_handler после создания theme_manager"""
        if not hasattr(self, 'theme_handler'):
            from ui.theme import ThemeHandler
            self.theme_handler = ThemeHandler(self, target_widget=self.main_widget)
            log("ThemeHandler инициализирован", "DEBUG")