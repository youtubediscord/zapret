# managers/subscription_manager.py

from PyQt6.QtCore import QThread, QObject, pyqtSignal
from PyQt6.QtWidgets import QMessageBox, QApplication
from log import log


class SubscriptionManager:
    """Менеджер для работы с подписками и донатами"""
    
    def __init__(self, app_instance):
        self.app = app_instance
        self.donate_checker = None
        
    def initialize_async(self):
        """Асинхронная инициализация и проверка подписки"""
        
        class SubscriptionInitWorker(QObject):
            finished = pyqtSignal(object, bool)  # donate_checker, success
            progress = pyqtSignal(str)
            
            def run(self):
                try:
                    self.progress.emit("Инициализация системы подписок...")
                    
                    # Создаем DonateChecker
                    from donater import DonateChecker
                    donate_checker = DonateChecker()
                    
                    self.progress.emit("Проверка статуса подписки...")
                    
                    # ✅ ИСПОЛЬЗУЕМ НОВЫЙ API - check_device_activation()
                    # Этот метод автоматически делает первую проверку
                    activation_info = donate_checker.check_device_activation()
                    
                    log(f"Статус подписки: {activation_info.get('status', 'unknown')}", "INFO")
                    
                    self.finished.emit(donate_checker, True)
                    
                except Exception as e:
                    log(f"Ошибка инициализации подписок: {e}", "❌ ERROR")
                    import traceback
                    log(f"Traceback: {traceback.format_exc()}", "DEBUG")
                    self.finished.emit(None, False)
        
        # Показываем что идет загрузка
        self.app.set_status("Инициализация подписок...")
        
        self._subscription_thread = QThread()
        self._subscription_worker = SubscriptionInitWorker()
        self._subscription_worker.moveToThread(self._subscription_thread)
        
        self._subscription_thread.started.connect(self._subscription_worker.run)
        self._subscription_worker.progress.connect(self.app.set_status)
        self._subscription_worker.finished.connect(self._on_subscription_ready)
        self._subscription_worker.finished.connect(self._subscription_thread.quit)
        self._subscription_worker.finished.connect(self._subscription_worker.deleteLater)
        self._subscription_thread.finished.connect(self._subscription_thread.deleteLater)
        
        self._subscription_thread.start()

    def _on_subscription_ready(self, donate_checker, success):
        """✅ ОБНОВЛЕННЫЙ обработчик готовности подписки"""
        if not success or not donate_checker:
            log("DonateChecker не инициализирован", "⚠ WARNING")
            # ✅ ИСПОЛЬЗУЕМ UI MANAGER
            if hasattr(self.app, 'ui_manager'):
                self.app.ui_manager.update_title_with_subscription_status(False, None, 0)
            self.app.set_status("Ошибка инициализации подписок")
            return

        # Сохраняем checker
        self.donate_checker = donate_checker
        self.app.donate_checker = donate_checker
        
        # ✅ ДОБАВЛЯЕМ ПРОВЕРКУ перед обновлением ссылки
        if hasattr(self.app, 'theme_manager'):
            self.app.theme_manager.donate_checker = donate_checker
            self.app.theme_manager.reapply_saved_theme_if_premium()
        else:
            log("theme_manager еще не готов, пропускаем обновление тем", "DEBUG")
            
        # ✅ ПОЛУЧАЕМ ИНФОРМАЦИЮ через НОВЫЙ API
        try:
            sub_info = donate_checker.get_full_subscription_info()
            
            log(f"Информация о подписке получена: premium={sub_info['is_premium']}, "
                f"days={sub_info['days_remaining']}, level={sub_info['subscription_level']}", "DEBUG")
            
        except Exception as e:
            log(f"Ошибка получения информации о подписке: {e}", "❌ ERROR")
            # Fallback значения
            sub_info = {
                'is_premium': False,
                'status_msg': 'Ошибка проверки',
                'days_remaining': None,
                'subscription_level': '–'
            }
        
        # ✅ ИСПОЛЬЗУЕМ UI MANAGER для обновления UI
        current_theme = getattr(self.app.theme_manager, 'current_theme', None) if hasattr(self.app, 'theme_manager') else None
        
        if hasattr(self.app, 'ui_manager'):
            self.app.ui_manager.update_title_with_subscription_status(
                sub_info['is_premium'],
                current_theme,
                sub_info['days_remaining']
            )
            
            self.app.ui_manager.update_subscription_button_text(
                sub_info['is_premium'],
                sub_info['days_remaining']
            )
        
        # ✅ ОБНОВЛЯЕМ КАРТОЧКИ НА ГЛАВНОЙ И СТРАНИЦЕ "О ПРОГРАММЕ"
        if hasattr(self.app, 'update_subscription_display'):
            self.app.update_subscription_display(
                sub_info['is_premium'],
                sub_info['days_remaining'] if sub_info['days_remaining'] and sub_info['days_remaining'] > 0 else None
            )
            log(f"Обновлены карточки подписки: premium={sub_info['is_premium']}", "DEBUG")

        # Обновляем темы через UI Manager
        if hasattr(self.app, 'theme_manager') and hasattr(self.app, 'ui_manager'):
            available_themes = self.app.theme_manager.get_available_themes()
            self.app.ui_manager.update_theme_gallery(available_themes)
        
        # ✅ Инициализируем гирлянду после получения статуса подписки
        if hasattr(self.app, '_init_garland_from_registry'):
            self.app._init_garland_from_registry()
            
        self.app.set_status("Подписка инициализирована")
        log(f"Подписка готова: {'Premium' if sub_info['is_premium'] else 'Free'} "
            f"(уровень: {sub_info['subscription_level']})", "INFO")

    def handle_subscription_status_change(self, was_premium, is_premium):
        """Обрабатывает изменение статуса подписки"""
        log(f"Статус подписки изменился: {was_premium} -> {is_premium}", "INFO")
        
        # ✅ ИСПОЛЬЗУЕМ UI MANAGER для обновления галереи тем
        if hasattr(self.app, 'theme_manager') and hasattr(self.app, 'ui_manager'):
            available_themes = self.app.theme_manager.get_available_themes()
            current_theme = self.app.theme_manager.current_theme
            
            # Обновляем галерею тем через UI Manager
            self.app.ui_manager.update_theme_gallery(available_themes)
            
            # Обновляем премиум статус на странице оформления
            if hasattr(self.app, 'appearance_page'):
                self.app.appearance_page.set_premium_status(is_premium)
                self.app.appearance_page.set_current_theme(current_theme)
        
        # Показываем уведомления
        self._show_subscription_notifications(was_premium, is_premium)
        
        # Обновляем UI элементы
        self._update_subscription_ui_elements()

    def _find_alternative_theme(self, available_themes, current_selection):
        """Находит альтернативную тему при изменении статуса подписки"""
        clean_theme_name = self.app.theme_manager.get_clean_theme_name(current_selection)
        
        # Ищем тему с таким же базовым именем
        theme_found = False
        for theme in available_themes:
            if self.app.theme_manager.get_clean_theme_name(theme) == clean_theme_name:
                # Обновляем выбор в галерее
                if hasattr(self.app, 'appearance_page'):
                    self.app.appearance_page.set_current_theme(theme)
                theme_found = True
                break
        
        # Если не нашли похожую тему
        if not theme_found:
            for theme in available_themes:
                if "(заблокировано)" not in theme and "(Premium)" not in theme:
                    # Обновляем выбор в галерее и применяем тему
                    if hasattr(self.app, 'appearance_page'):
                        self.app.appearance_page.set_current_theme(theme)
                    self.app.theme_manager.apply_theme_async(theme, persist=True)
                    log(f"Автоматически выбрана тема: {theme}", "INFO")
                    break

    def _show_subscription_notifications(self, was_premium, is_premium):
        """Показывает уведомления об изменении статуса подписки"""
        if is_premium and not was_premium:
            # Подписка активирована
            self.app.set_status("✅ Подписка активирована! Премиум темы доступны")
            
            if hasattr(self.app, 'tray_manager') and self.app.tray_manager:
                self.app.tray_manager.show_notification(
                    "Подписка активирована", 
                    "Премиум темы теперь доступны!"
                )
            
            QMessageBox.information(
                self.app,
                "Подписка активирована",
                "Ваша Premium подписка успешно активирована!\n\n"
                "Теперь вам доступны:\n"
                "• Эксклюзивные темы оформления\n"
                "• Приоритетная поддержка\n"
                "• Ранний доступ к новым функциям\n\n"
                "Спасибо за поддержку проекта!"
            )
            
        elif not is_premium and was_premium:
            # Подписка истекла
            self.app.set_status("❌ Подписка истекла. Премиум темы недоступны")
            
            if hasattr(self.app, 'tray_manager') and self.app.tray_manager:
                self.app.tray_manager.show_notification(
                    "Подписка истекла", 
                    "Премиум темы больше недоступны"
                )
            
            self._show_subscription_expired_dialog()

    def _show_subscription_expired_dialog(self):
        """Показывает диалог истечения подписки"""
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setWindowTitle("Подписка истекла")
        msg.setText("Ваша Premium подписка истекла")
        msg.setInformativeText(
            "Премиум функции больше недоступны.\n\n"
            "Чтобы продолжить использовать эксклюзивные темы "
            "и другие преимущества, пожалуйста, продлите подписку."
        )
        
        msg.addButton("Продлить подписку", QMessageBox.ButtonRole.AcceptRole)
        msg.addButton("Позже", QMessageBox.ButtonRole.RejectRole)
        
        if msg.exec() == 0:  # Кнопка "Продлить подписку"
            self.app.show_subscription_dialog()

    def _update_subscription_ui_elements(self):
        """Обновляет UI элементы, зависящие от подписки"""
        try:
            if hasattr(self.app, 'button_grid'):
                self.app.button_grid.update()
            
            QApplication.processEvents()
            
        except Exception as e:
            log(f"Ошибка при обновлении UI после изменения подписки: {e}", "❌ ERROR")

    def update_subscription_ui(self):
        """✅ ОБНОВЛЕННЫЙ метод обновления UI после проверки подписки"""
        try:
            # Проверяем наличие theme_manager
            if not hasattr(self.app, 'theme_manager'):
                log("theme_manager еще не инициализирован, пропускаем обновление", "DEBUG")
                return
            
            if not self.donate_checker:
                log("donate_checker не инициализирован", "⚠ WARNING")
                return
            
            # ✅ ИСПОЛЬЗУЕМ НОВЫЙ API
            try:
                sub_info = self.donate_checker.get_full_subscription_info()
                
                is_premium = sub_info['is_premium']
                status_msg = sub_info['status_msg']
                days_remaining = sub_info['days_remaining']
                
                log(f"Обновление UI подписки: premium={is_premium}, days={days_remaining}", "DEBUG")
                
            except Exception as e:
                log(f"Ошибка получения информации о подписке: {e}", "❌ ERROR")
                # Fallback значения
                is_premium = False
                status_msg = "Ошибка проверки"
                days_remaining = None
            
            # Получаем текущую тему
            current_theme = self.app.theme_manager.current_theme
            
            # ✅ ИСПОЛЬЗУЕМ UI MANAGER
            if hasattr(self.app, 'ui_manager'):
                self.app.ui_manager.update_title_with_subscription_status(
                    is_premium, 
                    current_theme, 
                    days_remaining
                )
                
                # Обновляем кнопку подписки
                self.app.ui_manager.update_subscription_button_text(
                    is_premium,
                    days_remaining
                )
                
                # Обновляем галерею тем через UI Manager
                if hasattr(self.app, 'theme_manager'):
                    available_themes = self.app.theme_manager.get_available_themes()
                    self.app.ui_manager.update_theme_gallery(available_themes)
                    
                    # Обновляем премиум статус на странице оформления
                    if hasattr(self.app, 'appearance_page'):
                        self.app.appearance_page.set_premium_status(is_premium)
                        self.app.appearance_page.set_current_theme(self.app.theme_manager.current_theme)
            
            # ✅ ОБНОВЛЯЕМ КАРТОЧКИ НА ГЛАВНОЙ И СТРАНИЦЕ "О ПРОГРАММЕ"
            if hasattr(self.app, 'update_subscription_display'):
                self.app.update_subscription_display(
                    is_premium,
                    days_remaining if days_remaining and days_remaining > 0 else None
                )
            
            self.app.set_status(f"Статус подписки: {status_msg}")
            log(f"Статус подписки обновлен: {'Premium' if is_premium else 'Free'}", "INFO")
            
        except Exception as e:
            log(f"Ошибка при обновлении UI подписки: {e}", "❌ ERROR")
            import traceback
            log(f"Traceback: {traceback.format_exc()}", "DEBUG")
            self.app.set_status("Ошибка проверки подписки")
    
    def check_and_update_subscription(self, silent=False):
        """
        ✅ НОВЫЙ метод для ручной проверки подписки
        
        Args:
            silent: Если True, не показывать уведомления об успехе
        """
        try:
            if not self.donate_checker:
                log("donate_checker не инициализирован", "⚠ WARNING")
                if not silent:
                    self.app.set_status("Ошибка: менеджер подписок не готов")
                return False
            
            # Получаем текущий статус
            old_info = self.donate_checker.get_full_subscription_info()
            was_premium = old_info['is_premium']
            
            # Проверяем статус заново (обновляем с сервера)
            activation_info = self.donate_checker.check_device_activation()
            
            # Получаем новый статус
            new_info = self.donate_checker.get_full_subscription_info()
            is_premium = new_info['is_premium']
            
            # Если статус изменился
            if was_premium != is_premium:
                self.handle_subscription_status_change(was_premium, is_premium)
            
            # Обновляем UI
            self.update_subscription_ui()
            
            if not silent:
                self.app.set_status(f"Подписка проверена: {new_info['status_msg']}")
            
            return True
            
        except Exception as e:
            log(f"Ошибка проверки подписки: {e}", "❌ ERROR")
            if not silent:
                self.app.set_status(f"Ошибка проверки подписки: {e}")
            return False