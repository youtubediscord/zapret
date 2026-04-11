# managers/subscription_manager.py

from typing import Any, Dict, Optional

from PyQt6.QtCore import QThread, QObject, pyqtSignal
from app_notifications import advisory_notification
from log import log


class SubscriptionManager:
    """Менеджер для работы с подписками и донатами"""
    
    def __init__(self, app_instance):
        self.app = app_instance
        self.donate_checker = None
        self._last_is_premium: Optional[bool] = None
        self._refresh_thread: Optional[QThread] = None
        self._refresh_worker: Optional[QObject] = None
        
    def initialize_async(self):
        """Асинхронная инициализация и проверка подписки"""
        
        class SubscriptionInitWorker(QObject):
            finished = pyqtSignal(object, object, bool)  # donate_checker, activation_info, success
            progress = pyqtSignal(str)
            
            def run(self):
                try:
                    self.progress.emit("Инициализация системы подписок...")
                    
                    # Создаем DonateChecker
                    from donater.donate import DonateChecker
                    donate_checker = DonateChecker()
                    
                    self.progress.emit("Проверка статуса подписки...")
                    
                    # На старте используем кэш/оффлайн статус без сети,
                    # а сетевую проверку выполняем позже отложенным фоновым таском.
                    activation_info = donate_checker.check_device_activation(use_cache=True)
                    
                    log(f"Статус подписки: {activation_info.get('status', 'unknown')}", "INFO")
                    
                    self.finished.emit(donate_checker, activation_info, True)
                    
                except Exception as e:
                    log(f"Ошибка инициализации подписок: {e}", "❌ ERROR")
                    import traceback
                    log(f"Traceback: {traceback.format_exc()}", "DEBUG")
                    self.finished.emit(None, None, False)
        
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

    @staticmethod
    def _build_subscription_info(activation_info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        info = activation_info if isinstance(activation_info, dict) else {}
        is_premium = bool(info.get('activated') or info.get('is_premium'))
        days_remaining = info.get('days_remaining') if is_premium else None
        return {
            'is_premium': is_premium,
            'status_msg': str(info.get('status') or ('Premium активен' if is_premium else 'Не активировано')),
            'days_remaining': days_remaining,
            'subscription_level': str(info.get('subscription_level') or ('zapretik' if is_premium else '–')),
        }

    def _apply_subscription_info_to_ui(self, sub_info: Dict[str, Any], *, status_message: Optional[str] = None):
        is_premium = bool(sub_info.get('is_premium'))
        days_remaining = sub_info.get('days_remaining')
        store = getattr(self.app, 'ui_state_store', None)
        if store is not None:
            store.set_subscription(is_premium, days_remaining)

        current_theme = getattr(self.app.theme_manager, 'current_theme', None) if hasattr(self.app, 'theme_manager') else None

        if hasattr(self.app, 'ui_manager'):
            self.app.ui_manager.update_title_with_subscription_status(
                is_premium,
                current_theme,
                days_remaining
            )
            log(f"Обновлены карточки подписки: premium={is_premium}", "DEBUG")

        if hasattr(self.app, 'theme_manager') and hasattr(self.app, 'ui_manager'):
            available_themes = self.app.theme_manager.get_available_themes()
            self.app.ui_manager.update_theme_gallery(available_themes)

        self._last_is_premium = is_premium
        if status_message:
            self.app.set_status(status_message)

    def _on_subscription_ready(self, donate_checker, activation_info, success):
        """✅ ОБНОВЛЕННЫЙ обработчик готовности подписки"""
        if not success or not donate_checker:
            log("DonateChecker не инициализирован", "⚠ WARNING")
            # ✅ ИСПОЛЬЗУЕМ UI MANAGER
            if hasattr(self.app, 'ui_manager'):
                self.app.ui_manager.update_title_with_subscription_status(False, None, 0)
            self.app.set_status("Ошибка инициализации подписок")
            try:
                if hasattr(self.app, '_mark_startup_subscription_ready'):
                    self.app._mark_startup_subscription_ready("subscription_init_failed")
            except Exception:
                pass
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
            
        # ✅ ИСПОЛЬЗУЕМ РЕЗУЛЬТАТ ВОРКЕРА (без повторного запроса к API в UI-потоке)
        try:
            sub_info = self._build_subscription_info(activation_info)
            
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
        
        self._apply_subscription_info_to_ui(sub_info)
        
        # ✅ Инициализируем гирлянду после получения статуса подписки
        if hasattr(self.app, '_init_garland_from_registry'):
            self.app._init_garland_from_registry()
            
        self.app.set_status("Подписка инициализирована")
        log(f"Подписка готова: {'Premium' if sub_info['is_premium'] else 'Free'} "
            f"(уровень: {sub_info['subscription_level']})", "INFO")
        try:
            if hasattr(self.app, '_mark_startup_subscription_ready'):
                self.app._mark_startup_subscription_ready("subscription_ready")
        except Exception:
            pass

    def handle_subscription_status_change(self, was_premium, is_premium):
        """Обрабатывает изменение статуса подписки"""
        log(f"Статус подписки изменился: {was_premium} -> {is_premium}", "INFO")
        
        # ✅ ИСПОЛЬЗУЕМ UI MANAGER для обновления галереи тем
        if hasattr(self.app, 'theme_manager') and hasattr(self.app, 'ui_manager'):
            available_themes = self.app.theme_manager.get_available_themes()
            
            # Обновляем галерею тем через UI Manager
            self.app.ui_manager.update_theme_gallery(available_themes)
        
        # Показываем уведомления
        self._show_subscription_notifications(was_premium, is_premium)
        
        # Обновляем UI элементы
        self._update_subscription_ui_elements()

    def _show_subscription_notifications(self, was_premium, is_premium):
        """Показывает уведомления об изменении статуса подписки"""
        controller = getattr(self.app, 'window_notification_controller', None)

        if is_premium and not was_premium:
            # Подписка активирована
            self.app.set_status("✅ Подписка активирована! Премиум темы доступны")

            if controller is not None:
                controller.notify(
                    advisory_notification(
                        level="success",
                        title="Подписка активирована",
                        content=(
                            "Ваша Premium подписка успешно активирована. Теперь доступны "
                            "эксклюзивные темы оформления, приоритетная поддержка и ранний доступ к новым функциям."
                        ),
                        source="subscription.activated",
                        presentation="infobar",
                        queue="immediate",
                        duration=6000,
                        dedupe_key="subscription.activated",
                        tray_title="Подписка активирована",
                        tray_content="Премиум темы теперь доступны!",
                    )
                )
            
        elif not is_premium and was_premium:
            # Подписка истекла
            self.app.set_status("❌ Подписка истекла. Премиум темы недоступны")

            if controller is not None:
                controller.notify(
                    advisory_notification(
                        level="warning",
                        title="Подписка истекла",
                        content=(
                            "Ваша Premium подписка истекла. Премиум функции больше недоступны. "
                            "Продлите подписку для доступа к эксклюзивным темам."
                        ),
                        source="subscription.expired",
                        presentation="infobar",
                        queue="immediate",
                        duration=6000,
                        dedupe_key="subscription.expired",
                        tray_title="Подписка истекла",
                        tray_content="Премиум темы больше недоступны",
                    )
                )

    def _update_subscription_ui_elements(self):
        pass

    def update_subscription_ui(self):
        """✅ ОБНОВЛЕННЫЙ метод обновления UI после проверки подписки"""
        return self.update_subscription_ui_with_data(None)

    def update_subscription_ui_with_data(self, sub_info: Optional[Dict[str, Any]] = None):
        """Обновляет UI подписки без блокирующих сетевых вызовов в UI-потоке."""
        try:
            # Проверяем наличие theme_manager
            if not hasattr(self.app, 'theme_manager'):
                log("theme_manager еще не инициализирован, пропускаем обновление", "DEBUG")
                return
            
            if not self.donate_checker:
                log("donate_checker еще не готов, пропускаем обновление UI подписки", "DEBUG")
                return
            
            ui_info: Dict[str, Any]
            if sub_info is None:
                fetched_info = self.donate_checker.get_full_subscription_info(use_cache=True)
                ui_info = fetched_info if isinstance(fetched_info, dict) else {
                    'is_premium': False,
                    'status_msg': 'Не активировано',
                    'days_remaining': None,
                    'subscription_level': '–',
                }
            elif isinstance(sub_info, dict):
                ui_info = sub_info
            else:
                ui_info = {
                    'is_premium': False,
                    'status_msg': 'Не активировано',
                    'days_remaining': None,
                    'subscription_level': '–',
                }

            self._apply_subscription_info_to_ui(
                ui_info,
                status_message=f"Статус подписки: {ui_info.get('status_msg', 'Не активировано')}"
            )
            log(f"Статус подписки обновлен: {'Premium' if ui_info.get('is_premium') else 'Free'}", "INFO")
            
        except Exception as e:
            log(f"Ошибка при обновлении UI подписки: {e}", "❌ ERROR")
            import traceback
            log(f"Traceback: {traceback.format_exc()}", "DEBUG")
            self.app.set_status("Ошибка проверки подписки")
    
    def check_and_update_subscription(self, silent=False):
        """Back-compat обертка: запуск асинхронной проверки подписки."""
        return self.check_and_update_subscription_async(silent=silent)

    def check_and_update_subscription_async(self, silent: bool = False):
        """Асинхронно проверяет подписку без блокировки UI."""
        try:
            if not self.donate_checker:
                log_level = "DEBUG" if silent else "⚠ WARNING"
                log("donate_checker еще не готов, пропускаем проверку подписки", log_level)
                if not silent:
                    self.app.set_status("Подписка еще инициализируется")
                return False

            # Не запускаем повторную проверку пока текущая не завершилась
            if self._refresh_thread is not None:
                try:
                    if self._refresh_thread.isRunning():
                        log("Проверка подписки уже выполняется, пропускаем", "DEBUG")
                        return False
                except RuntimeError:
                    self._refresh_thread = None
                    self._refresh_worker = None

            previous_is_premium = self._last_is_premium

            class SubscriptionRefreshWorker(QObject):
                finished = pyqtSignal(object, bool, str)  # activation_info, success, error

                def __init__(self, donate_checker):
                    super().__init__()
                    self.donate_checker = donate_checker

                def run(self):
                    try:
                        activation_info = self.donate_checker.check_device_activation(use_cache=False, automatic=True)
                        self.finished.emit(activation_info, True, "")
                    except Exception as e:
                        self.finished.emit(None, False, str(e))

            self._refresh_thread = QThread()
            self._refresh_worker = SubscriptionRefreshWorker(self.donate_checker)
            self._refresh_worker.moveToThread(self._refresh_thread)

            self._refresh_thread.started.connect(self._refresh_worker.run)

            def _on_refresh_finished(activation_info, success, error_msg):
                if not success:
                    log(f"Ошибка проверки подписки: {error_msg}", "❌ ERROR")
                    if not silent:
                        self.app.set_status(f"Ошибка проверки подписки: {error_msg}")
                    return

                sub_info = self._build_subscription_info(activation_info)
                is_premium = sub_info['is_premium']

                if previous_is_premium is not None and previous_is_premium != is_premium:
                    self.handle_subscription_status_change(previous_is_premium, is_premium)

                status_message = None if silent else f"Подписка проверена: {sub_info['status_msg']}"
                self._apply_subscription_info_to_ui(sub_info, status_message=status_message)

            def _cleanup_refresh_objects():
                self._refresh_worker = None
                self._refresh_thread = None

            self._refresh_worker.finished.connect(_on_refresh_finished)
            self._refresh_worker.finished.connect(self._refresh_thread.quit)
            self._refresh_worker.finished.connect(self._refresh_worker.deleteLater)
            self._refresh_thread.finished.connect(self._refresh_thread.deleteLater)
            self._refresh_thread.finished.connect(_cleanup_refresh_objects)

            self._refresh_thread.start()
            return True
            
        except Exception as e:
            log(f"Ошибка проверки подписки: {e}", "❌ ERROR")
            if not silent:
                self.app.set_status(f"Ошибка проверки подписки: {e}")
            return False
