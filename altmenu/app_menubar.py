# altmenu/app_menubar.py

from PyQt6.QtWidgets import (QMenuBar, QWidget, QMessageBox, QApplication, 
                            QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                            QTextEdit, QLineEdit, QPushButton, QDialogButtonBox)
from PyQt6.QtGui     import QKeySequence, QAction
from PyQt6.QtCore    import Qt, QThread, QSettings
import webbrowser

from config import APP_VERSION, get_dpi_autostart, set_dpi_autostart # build_info moved to config/__init__.py
from config.urls import INFO_URL
from .about_dialog import AboutDialog
from .defender_manager import WindowsDefenderManager
from .max_blocker import MaxBlockerManager

from utils import run_hidden
from log import log, global_logger

from startup import get_remove_windows_terminal, set_remove_windows_terminal

class LogReportDialog(QDialog):
    """Диалог для ввода описания проблемы и контактов при отправке лога"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Отправка лога в техподдержку")
        self.setModal(True)
        self.setMinimumWidth(500)
        
        # Основной layout
        layout = QVBoxLayout()
        
        # Заголовок
        header_label = QLabel(
            "<h3>Отправка лога файла</h3>"
            "<p>Опишите проблему и оставьте контакты для обратной связи (необязательно):</p>"
        )
        header_label.setWordWrap(True)
        layout.addWidget(header_label)
        
        # Поле для описания проблемы
        problem_label = QLabel("Описание проблемы:")
        layout.addWidget(problem_label)
        
        self.problem_text = QTextEdit()
        self.problem_text.setPlaceholderText(
            "Опишите, что не работает или какая ошибка возникает.\n"
            "Например: Discord не открывается, показывает белый экран..."
        )
        self.problem_text.setMaximumHeight(150)
        layout.addWidget(self.problem_text)
        
        # Поле для Telegram контакта
        tg_label = QLabel("Telegram для связи (необязательно):")
        layout.addWidget(tg_label)
        
        self.tg_contact = QLineEdit()
        self.tg_contact.setPlaceholderText("@username или ссылка на профиль")
        layout.addWidget(self.tg_contact)
        
        # Информация
        info_label = QLabel(
            "<p style='color: gray; font-size: 10pt;'>"
            "💡 Ваши данные будут отправлены только в канал техподдержки<br>"
            "📋 Лог файл поможет разработчикам найти и исправить проблему"
            "</p>"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Кнопки
        button_box = QDialogButtonBox()
        
        send_button = button_box.addButton("Отправить", QDialogButtonBox.ButtonRole.AcceptRole)
        send_button.setDefault(True)
        
        cancel_button = button_box.addButton("Отмена", QDialogButtonBox.ButtonRole.RejectRole)
        
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        
        layout.addWidget(button_box)
        
        self.setLayout(layout)
    
    def get_report_data(self):
        """Возвращает введенные данные"""
        return {
            'problem': self.problem_text.toPlainText().strip(),
            'telegram': self.tg_contact.text().strip()
        }


class AppMenuBar(QMenuBar):
    """
    Верхняя строка меню («Alt-меню»).
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._pw = parent
        self._settings = QSettings("ZapretGUI", "Zapret") # для сохранения настроек
        self._set_status = getattr(parent, "set_status", lambda *_: None)

        # -------- 1. Настройки -------------------------------------------------
        file_menu = self.addMenu("&Настройки")

        # Чек-бокс Автозагрузка DPI»
        self.auto_dpi_act = QAction("Автозагрузка DPI", self, checkable=True)
        self.auto_dpi_act.setChecked(get_dpi_autostart())
        self.auto_dpi_act.toggled.connect(self.toggle_dpi_autostart)
        file_menu.addAction(self.auto_dpi_act)

        self.clear_cache = file_menu.addAction("Сбросить программу")
        self.clear_cache.triggered.connect(self.clear_startup_cache)

        file_menu.addSeparator()

        # Windows Defender
        file_menu.addSeparator()
        self.defender_act = QAction("Отключить Windows Defender", self, checkable=True)
        self.defender_act.setChecked(self._get_defender_disabled())
        self.defender_act.toggled.connect(self.toggle_windows_defender)
        file_menu.addAction(self.defender_act)

        self.remove_wt_act = QAction("Удалять Windows Terminal", self, checkable=True)
        self.remove_wt_act.setChecked(get_remove_windows_terminal())
        self.remove_wt_act.toggled.connect(self.toggle_remove_windows_terminal)
        file_menu.addAction(self.remove_wt_act)

        # Блокировка MAX
        self.block_max_act = QAction("Блокировать установку MAX", self, checkable=True)
        self.block_max_act.setChecked(self._get_max_blocked())
        self.block_max_act.toggled.connect(self.toggle_max_blocker)
        file_menu.addAction(self.block_max_act)

        file_menu.addSeparator()

        act_exit = QAction("Скрыть GUI в трей", self, shortcut=QKeySequence("Ctrl+Q"))
        act_exit.triggered.connect(parent.close)
        file_menu.addAction(act_exit)

        full_exit_act = QAction("Полностью выйти", self, shortcut=QKeySequence("Ctrl+Shift+Q"))
        full_exit_act.triggered.connect(self.full_exit)
        file_menu.addAction(full_exit_act)

        """
        # === ХОСТЛИСТЫ ===
        hostlists_menu = self.addMenu("&Хостлисты")
        
        update_exclusions_action = QAction("Обновить исключения с сервера", self)
        update_exclusions_action.triggered.connect(self._update_exclusions)
        hostlists_menu.addAction(update_exclusions_action)
        
        exclude_sites_action = QAction("Добавить свой домен в исключения", self)
        exclude_sites_action.triggered.connect(self._exclude_custom_sites)
        hostlists_menu.addAction(exclude_sites_action)
        
        hostlists_menu.addSeparator()
        
        update_custom_sites_action = QAction("Обновить кастомные сайты с сервера", self)
        update_custom_sites_action.triggered.connect(self._update_custom_sites)
        hostlists_menu.addAction(update_custom_sites_action)
        
        add_custom_sites_action = QAction("Добавить свой домен в кастомные сайты", self)
        add_custom_sites_action.triggered.connect(self._add_custom_sites)
        hostlists_menu.addAction(add_custom_sites_action)
        
        hostlists_menu.addSeparator()
        """

        # -------- 2. «Справка» ---------------------------------------------
        help_menu = self.addMenu("&Справка")

        act_help = QAction("❓ Что это такое? (Руководство)", self)
        act_help.triggered.connect(self.open_info)
        help_menu.addAction(act_help)

        act_support = QAction("💬 Поддержка (запросить помощь)", self)
        act_support.triggered.connect(self.open_support)
        help_menu.addAction(act_support)

        act_support = QAction("🤖 На андроид (ByeByeDPI)", self)
        act_support.triggered.connect(self.show_byedpi_info)
        help_menu.addAction(act_support)

        act_about = QAction("ℹ О программе…", self)
        act_about.triggered.connect(lambda: AboutDialog(parent).exec())
        help_menu.addAction(act_about)

    def show_byedpi_info(self):
        """Открывает PDF руководство пользователя"""
        try:
            from config import HELP_FOLDER
            import os
            
            pdf_path = os.path.join(HELP_FOLDER, "ByeByeDPI - Что это такое.pdf")
            
            if not os.path.exists(pdf_path):
                log(f"PDF руководство не найдено: {pdf_path}", "❌ ERROR")
                
                QMessageBox.warning(
                    self,
                    "Файл не найден",
                    f"Руководство пользователя не найдено:\n{pdf_path}\n\n"
                    "Пожалуйста, переустановите программу или обратитесь в поддержку."
                )
                return
            
            log(f"Открываем PDF руководство: {pdf_path}", "INFO")
            os.startfile(pdf_path)
            log("PDF руководство успешно открыто", "✅ SUCCESS")
            
        except Exception as e:
            log(f"Ошибка при открытии PDF руководства: {e}", "❌ ERROR")
            
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Не удалось открыть руководство пользователя:\n{str(e)}\n\n"
                "Попробуйте открыть файл вручную из папки Help."
            )

    def clear_startup_cache(self):
        """Очищает кэш проверок запуска"""
        from startup.check_cache import startup_cache
        try:
            startup_cache.invalidate_cache()
            QMessageBox.information(self._pw, "Настройки программы сброшены", 
                                  "Кэш проверок запуска и настройки программы успешно очищены.\n"
                                  "При следующем запуске все проверки будут выполнены заново.")
            log("Кэш проверок запуска очищен пользователем", "INFO")
        except Exception as e:
            QMessageBox.warning(self._pw, "Ошибка", 
                              f"Не удалось очистить кэш: {e}")
            log(f"Ошибка очистки кэша: {e}", "❌ ERROR")

    def create_premium_menu(self):
        """Создает меню Premium функций"""
        premium_menu = self.addMenu("💎 Premium")
        
        # Управление подпиской
        subscription_action = premium_menu.addAction("📋 Управление подпиской")
        subscription_action.triggered.connect(self._pw.show_subscription_dialog)
        
        premium_menu.addSeparator()
        
        # Информация о сервере
        server_info_action = premium_menu.addAction("⚙️ Статус сервера")
        server_info_action.triggered.connect(self._pw.get_boosty_server_info)

        # Переключение сервера
        server_toggle_action = premium_menu.addAction("🔄 Переключить сервер")
        server_toggle_action.triggered.connect(self._pw.toggle_boosty_server)

        premium_menu.addSeparator()
        
        telegram_action = premium_menu.addAction("🌐 Открыть Telegram")
        from config.telegram_links import open_telegram_link
        telegram_action.triggered.connect(lambda: open_telegram_link("zapretvpns_bot"))
        
        return premium_menu

    # ==================================================================
    #  Обработчики чек-боксов
    # ==================================================================
    def toggle_remove_windows_terminal(self, enabled: bool):
        """
        Включает / выключает удаление Windows Terminal при запуске программы.
        """
        set_remove_windows_terminal(enabled)

        msg = ("Windows Terminal будет удаляться при запуске программы"
               if enabled
               else "Удаление Windows Terminal отключено")
        self._set_status(msg)
        
        if not enabled:
            # При отключении показываем предупреждение
            warning_msg = (
                "Внимание! Windows Terminal может мешать работе программы.\n\n"
                "Если у вас возникнут проблемы с работой DPI-обхода, "
                "рекомендуется включить эту опцию обратно."
            )
            QMessageBox.warning(self._pw, "Предупреждение", warning_msg)
        else:
            QMessageBox.information(self._pw, "Удаление Windows Terminal", msg)

    def toggle_dpi_autostart(self, enabled: bool):
        set_dpi_autostart(enabled)

        msg = ("DPI будет включаться автоматически при старте программы"
               if enabled
               else "Автозагрузка DPI отключена")
        self._set_status(msg)
        QMessageBox.information(self._pw, "Автозагрузка DPI", msg)

    # ==================================================================
    #  Полный выход (убираем трей +, при желании, останавливаем DPI)
    # ==================================================================

    def full_exit(self):
        # -----------------------------------------------------------------
        # 1. Диалог на русском, но с англ. подсказками в тексте
        # -----------------------------------------------------------------
        box = QMessageBox(self._pw)
        box.setWindowTitle("Выход")
        box.setIcon(QMessageBox.Icon.Question)

        # сам текст оставляем без изменений
        box.setText(
            "Остановить DPI-службу перед выходом?\n"
            "Да – остановить DPI и выйти\n"
            "Нет  – выйти, не останавливая DPI\n"
            "Отмена – остаться в программе"
        )

        # добавляем три стандартные кнопки
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes |
            QMessageBox.StandardButton.No  |
            QMessageBox.StandardButton.Cancel
        )
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)

        # ─── Русифицируем подписи ────────────────────────────────────────
        box.button(QMessageBox.StandardButton.Yes).setText("Да")
        box.button(QMessageBox.StandardButton.No).setText("Нет")
        box.button(QMessageBox.StandardButton.Cancel).setText("Отмена")

        # показываем диалог
        resp = box.exec()

        if resp == QMessageBox.StandardButton.Cancel:
            return                      # пользователь передумал

        stop_dpi_required = resp == QMessageBox.StandardButton.Yes

        # -----------------------------------------------------------------
        # 2. Дальше логика выхода (как раньше)
        # -----------------------------------------------------------------
        if stop_dpi_required:
            try:
                from dpi.stop import stop_dpi
                stop_dpi(self._pw)
            except Exception as e:
                QMessageBox.warning(
                    self._pw, "Ошибка DPI",
                    f"Не удалось остановить DPI:\n{e}"
                )

        if hasattr(self._pw, "process_monitor") and self._pw.process_monitor:
            self._pw.process_monitor.stop()

        if hasattr(self._pw, "tray_manager"):
            self._pw.tray_manager.tray_icon.hide()

        self._pw._allow_close = True
        QApplication.quit()

    # ==================================================================
    #  Справка
    # ==================================================================
    def open_info(self):
        try:
            import webbrowser
            webbrowser.open(INFO_URL)
            self._set_status("Открываю руководство…")
        except Exception as e:
            err = f"Ошибка при открытии руководства: {e}"
            self._set_status(err)
            QMessageBox.warning(self._pw, "Ошибка", err)

    def open_support(self):
        try:
            from config.telegram_links import open_telegram_link
            open_telegram_link("zaprethelp")
            self._set_status("Открываю поддержку...")
        except Exception as e:
            err = f"Ошибка при открытии поддержки: {e}"
            self._set_status(err)
            QMessageBox.warning(self._pw, "Ошибка", err)

    def show_logs(self):
        """
        Переключается на вкладку Логи в основном интерфейсе.
        """
        try:
            # Находим главное окно и переключаемся на страницу логов
            main_window = self._pw
            if main_window and hasattr(main_window, 'main_widget'):
                main_content = main_window.main_widget
                if hasattr(main_content, 'sidebar') and hasattr(main_content, 'pages_stack'):
                    # Индекс страницы логов (6 - после Оформление)
                    logs_page_index = 6
                    main_content.sidebar.set_current_index(logs_page_index)
                    main_content.pages_stack.setCurrentIndex(logs_page_index)
                    log("Переключение на страницу логов", "DEBUG")
                    return
            
            # Fallback: если не нашли - открываем папку с логами
            import subprocess
            from config import LOGS_FOLDER
            subprocess.run(['explorer', LOGS_FOLDER], check=False)
            
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self._pw or self,
                                "Ошибка",
                                f"Не удалось открыть логи:\n{e}")

    def send_log_to_tg_with_report(self):
        """Показывает диалог для описания проблемы, затем отправляет лог"""
        import time
        now = time.time()
        interval = 1 * 60  # 1 минута

        # Проверяем интервал
        last = self._settings.value("last_full_log_send", 0.0, type=float)
        
        if now - last < interval:
            remaining = int((interval - (now - last)) // 60) + 1
            QMessageBox.information(self._pw, "Отправка логов",
                f"Лог отправлялся недавно.\n"
                f"Следующая отправка возможна через {remaining} мин.")
            return

        # Проверяем настройки бота
        from tgram.tg_log_bot import check_bot_connection
        
        if not check_bot_connection():
            msg_box = QMessageBox(self._pw)
            msg_box.setWindowTitle("Бот не настроен")
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setText(
                "Бот для отправки логов не настроен или недоступен.\n\n"
                "Для настройки:\n"
                "1. Создайте бота через @BotFather в Telegram\n"
                "2. Получите токен бота\n"
                "3. Создайте канал/чат для логов\n"
                "4. Добавьте бота в канал как администратора\n"
                "5. Обновите настройки в файле tg_log_bot.py"
            )
            msg_box.exec()
            return

        # Показываем диалог для ввода описания проблемы
        report_dialog = LogReportDialog(self._pw)
        if report_dialog.exec() != QDialog.DialogCode.Accepted:
            return  # Пользователь отменил отправку
        
        report_data = report_dialog.get_report_data()

        # Запоминаем время отправки
        self._settings.setValue("last_full_log_send", now)

        # Подготовка к отправке
        from tgram.tg_log_full import TgSendWorker
        from tgram.tg_log_delta import get_client_id
        import os

        # Используем текущий лог файл
        from log import global_logger
        LOG_PATH = global_logger.log_file if hasattr(global_logger, 'log_file') else None
        
        if not LOG_PATH or not os.path.exists(LOG_PATH):
            QMessageBox.warning(self._pw, "Ошибка", "Файл лога не найден")
            return
        
        # Формируем подпись с информацией о файле и проблеме
        import platform
        log_filename = os.path.basename(LOG_PATH)
        
        caption = f"📋 Ручная отправка лога\n"
        caption += f"📁 Файл: {log_filename}\n"
        caption += f"Zapret2 v{APP_VERSION}\n"
        caption += f"ID: {get_client_id()}\n"
        caption += f"Host: {platform.node()}\n"
        caption += f"Time: {time.strftime('%d.%m.%Y %H:%M:%S')}\n"
        
        # Добавляем описание проблемы и контакты, если они указаны
        if report_data['problem']:
            caption += f"\n🔴 Проблема:\n{report_data['problem']}\n"
        
        if report_data['telegram']:
            caption += f"\n📱 Telegram: {report_data['telegram']}\n"

        action = self.sender()
        if action:
            action.setEnabled(False)

        wnd = self._pw
        if hasattr(wnd, "set_status"):
            wnd.set_status("Отправка лога...")

        # Создаем воркер с флагом use_log_bot=True
        thr = QThread(self)
        worker = TgSendWorker(LOG_PATH, caption, use_log_bot=True)
        worker.moveToThread(thr)
        thr.started.connect(worker.run)

        def _on_done(ok: bool, extra_wait: float, error_msg: str = ""):
            if ok:
                if hasattr(wnd, "set_status"):
                    wnd.set_status("Лог отправлен")
            else:
                if extra_wait > 0:
                    QMessageBox.warning(wnd, "Слишком часто",
                        f"Слишком частые запросы.\n"
                        f"Повторите через {int(extra_wait/60)} минут.")
                else:
                    QMessageBox.warning(wnd, "Ошибка",
                        f"Не удалось отправить лог.\n\n"
                        f"Причина: {error_msg or 'Неизвестная ошибка'}\n\n"
                        f"Попробуйте позже или обратитесь в поддержку.")
                
                if hasattr(wnd, "set_status"):
                    wnd.set_status("Ошибка отправки лога")
            
            # Очистка
            worker.deleteLater()
            thr.quit()
            thr.wait()
            if action:
                action.setEnabled(True)

        worker.finished.connect(_on_done)

        # Сохраняем ссылку на поток
        self._log_send_thread = thr
        thr.start()

    def _get_defender_disabled(self) -> bool:
        """Проверяет, отключен ли Windows Defender"""
        try:
            manager = WindowsDefenderManager()
            return manager.is_defender_disabled()
        except Exception as e:
            log(f"Ошибка при проверке состояния Windows Defender: {e}", "❌ ERROR")
            return False

    def toggle_windows_defender(self, disable: bool):
        """Включает/выключает Windows Defender"""
        import ctypes
        
        # Проверяем права администратора
        if not ctypes.windll.shell32.IsUserAnAdmin():
            QMessageBox.critical(
                self._pw,
                "Требуются права администратора",
                "Для управления Windows Defender требуются права администратора.\n\n"
                "Перезапустите программу от имени администратора."
            )
            # Откатываем галочку
            self.defender_act.blockSignals(True)
            self.defender_act.setChecked(not disable)
            self.defender_act.blockSignals(False)
            return
        
        try:
            manager = WindowsDefenderManager(status_callback=self._set_status)
            
            if disable:
                # Показываем предупреждение перед отключением
                msg_box = QMessageBox(self._pw)
                msg_box.setWindowTitle("Отключение Windows Defender")
                msg_box.setIcon(QMessageBox.Icon.Warning)
                msg_box.setText(
                    "Вы действительно хотите отключить Windows Defender?\n\n"
                )
                msg_box.setInformativeText(
                    "Отключение Windows Defender:\n"
                    "• Отключит защиту в реальном времени\n"
                    "• Отключит облачную защиту\n"
                    "• Отключит автоматическую отправку образцов\n"
                    "• Может потребовать перезагрузки для полного применения\n\n"
                )
                msg_box.setStandardButtons(
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                msg_box.setDefaultButton(QMessageBox.StandardButton.No)
                
                if msg_box.exec() != QMessageBox.StandardButton.Yes:
                    # Пользователь отменил - откатываем галочку
                    self.defender_act.blockSignals(True)
                    self.defender_act.setChecked(False)
                    self.defender_act.blockSignals(False)
                    return
                
                # Отключаем Defender
                self._set_status("Отключение Windows Defender...")
                success, count = manager.disable_defender()
                
                if success:
                    # Сохраняем настройку
                    from .defender_manager import set_defender_disabled
                    set_defender_disabled(True)
                    
                    QMessageBox.information(
                        self._pw,
                        "Windows Defender отключен",
                        f"Windows Defender успешно отключен.\n"
                        f"Применено {count} настроек.\n\n"
                        "Для полного применения изменений может потребоваться перезагрузка."
                    )
                    log(f"Windows Defender отключен пользователем", "⚠️ WARNING")
                else:
                    QMessageBox.critical(
                        self._pw,
                        "Ошибка",
                        "Не удалось отключить Windows Defender.\n"
                        "Возможно, некоторые настройки заблокированы системой."
                    )
                    # Откатываем настройку
                    self.defender_act.blockSignals(True)
                    self.defender_act.setChecked(False)
                    self.defender_act.blockSignals(False)
                    
            else:
                # Включение Windows Defender
                msg_box = QMessageBox(self._pw)
                msg_box.setWindowTitle("Включение Windows Defender")
                msg_box.setIcon(QMessageBox.Icon.Question)
                msg_box.setText(
                    "Включить Windows Defender обратно?\n\n"
                    "Это восстановит защиту вашего компьютера."
                )
                msg_box.setStandardButtons(
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)
                
                if msg_box.exec() != QMessageBox.StandardButton.Yes:
                    # Пользователь отменил - возвращаем галочку
                    self.defender_act.blockSignals(True)
                    self.defender_act.setChecked(True)
                    self.defender_act.blockSignals(False)
                    return
                
                # Включаем Defender
                self._set_status("Включение Windows Defender...")
                success, count = manager.enable_defender()
                
                if success:
                    # Сохраняем настройку
                    from .defender_manager import set_defender_disabled
                    set_defender_disabled(False)
                    
                    QMessageBox.information(
                        self._pw,
                        "Windows Defender включен",
                        f"Windows Defender успешно включен.\n"
                        f"Выполнено {count} операций.\n\n"
                        "Защита вашего компьютера восстановлена."
                    )
                    log("Windows Defender включен пользователем", "✅ INFO")
                else:
                    QMessageBox.warning(
                        self._pw,
                        "Частичный успех",
                        "Windows Defender включен частично.\n"
                        "Для полного восстановления может потребоваться перезагрузка."
                    )
                    
            self._set_status("Готово")
            
        except Exception as e:
            log(f"Ошибка при переключении Windows Defender: {e}", "❌ ERROR")
            QMessageBox.critical(
                self._pw,
                "Ошибка",
                f"Произошла ошибка при изменении настроек Windows Defender:\n{e}"
            )
            # В случае ошибки откатываем галочку
            self.defender_act.blockSignals(True)
            self.defender_act.setChecked(not disable)
            self.defender_act.blockSignals(False)

    def _get_max_blocked(self) -> bool:
        """Проверяет, включена ли блокировка MAX"""
        try:
            from .max_blocker import is_max_blocked
            return is_max_blocked()
        except Exception as e:
            log(f"Ошибка при проверке блокировки MAX: {e}", "❌ ERROR")
            return False

    def toggle_max_blocker(self, enable: bool):
        """Включает/выключает блокировку программы MAX"""
        try:
            manager = MaxBlockerManager(status_callback=self._set_status)
            
            if enable:
                # Показываем предупреждение перед включением
                msg_box = QMessageBox(self._pw)
                msg_box.setWindowTitle("Блокировка MAX")
                msg_box.setIcon(QMessageBox.Icon.Information)
                msg_box.setText(
                    "Включить блокировку установки и работы программы MAX?\n\n"
                    "Это действие:"
                )
                msg_box.setInformativeText(
                    "• Заблокирует запуск max.exe, max.msi и других файлов MAX\n"
                    "• Создаст файлы-блокировки в папках установки\n"
                    "• Добавит правила блокировки в Windows Firewall (при наличии прав)\n"
                    "• Заблокирует домены MAX в файле hosts\n\n"
                    "В итоге даже если мессенджер Max поставиться будет тёмный экран, в результате чего он будет выглядеть так, будто не может подключиться к своим серверам."
                )
                msg_box.setStandardButtons(
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)
                
                if msg_box.exec() != QMessageBox.StandardButton.Yes:
                    # Пользователь отменил - откатываем галочку
                    self.block_max_act.blockSignals(True)
                    self.block_max_act.setChecked(False)
                    self.block_max_act.blockSignals(False)
                    return
                
                # Включаем блокировку
                success, message = manager.enable_blocking()
                
                if success:
                    QMessageBox.information(
                        self._pw,
                        "Блокировка включена",
                        message
                    )
                    log("Блокировка MAX включена пользователем", "🛡️ INFO")
                else:
                    QMessageBox.warning(
                        self._pw,
                        "Ошибка",
                        f"Не удалось полностью включить блокировку:\n{message}"
                    )
                    # Откатываем галочку
                    self.block_max_act.blockSignals(True)
                    self.block_max_act.setChecked(False)
                    self.block_max_act.blockSignals(False)
                    
            else:
                # Отключение блокировки
                msg_box = QMessageBox(self._pw)
                msg_box.setWindowTitle("Отключение блокировки MAX")
                msg_box.setIcon(QMessageBox.Icon.Question)
                msg_box.setText(
                    "Отключить блокировку программы MAX?\n\n"
                    "Это удалит все созданные блокировки и правила."
                )
                msg_box.setStandardButtons(
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                msg_box.setDefaultButton(QMessageBox.StandardButton.No)
                
                if msg_box.exec() != QMessageBox.StandardButton.Yes:
                    # Пользователь отменил - возвращаем галочку
                    self.block_max_act.blockSignals(True)
                    self.block_max_act.setChecked(True)
                    self.block_max_act.blockSignals(False)
                    return
                
                # Отключаем блокировку
                success, message = manager.disable_blocking()
                
                if success:
                    QMessageBox.information(
                        self._pw,
                        "Блокировка отключена",
                        message
                    )
                    log("Блокировка MAX отключена пользователем", "✅ INFO")
                else:
                    QMessageBox.warning(
                        self._pw,
                        "Ошибка",
                        f"Не удалось полностью отключить блокировку:\n{message}"
                    )
                    
            self._set_status("Готово")
            
        except Exception as e:
            log(f"Ошибка при переключении блокировки MAX: {e}", "❌ ERROR")
            QMessageBox.critical(
                self._pw,
                "Ошибка",
                f"Произошла ошибка при изменении блокировки MAX:\n{e}"
            )
            # В случае ошибки откатываем галочку
            self.block_max_act.blockSignals(True)
            self.block_max_act.setChecked(not enable)
            self.block_max_act.blockSignals(False)