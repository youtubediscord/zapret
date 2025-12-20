"""Новая вкладка диагностики соединений в стиле Windows 11."""

import os
import platform
import time

from PyQt6.QtCore import Qt, QThread, QTimer
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QProgressBar,
    QFrame,
)

from .base_page import BasePage, ScrollBlockingTextEdit
from ui.sidebar import SettingsCard, ActionButton
from connection_test import ConnectionTestWorker, LogSendWorker
from config import LOGS_FOLDER, APP_VERSION
from tgram.tg_log_bot import check_bot_connection
from tgram.tg_log_delta import get_client_id


class StatusBadge(QLabel):
    """Небольшой бейдж состояния."""

    COLORS = {
        "info": "#60cdff",
        "success": "#6ccb5f",
        "warning": "#ffc107",
        "error": "#ff6b6b",
        "muted": "rgba(255, 255, 255, 0.6)",
    }

    def __init__(self, text: str = "", status: str = "muted", parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedHeight(28)
        self.set_status(text, status)

    def set_status(self, text: str, status: str = "muted"):
        color = self.COLORS.get(status, self.COLORS["muted"])
        self.setText(text)
        self.setStyleSheet(
            f"""
            QLabel {{
                color: {color};
                background-color: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 14px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 600;
            }}
            """
        )


class ConnectionTestPage(BasePage):
    """Страница теста соединений, заменяющая старое диалоговое окно."""

    def __init__(self, parent=None):
        super().__init__(
            "Диагностика соединения",
            "Автотест Discord и YouTube, проверка DNS подмены и отправка логов в поддержку",
            parent,
        )
        self.is_testing = False
        self.is_sending_log = False
        self.worker = None
        self.worker_thread = None
        self.log_send_thread = None
        self.log_send_worker = None
        self.stop_check_timer = None

        # Контейнер с ограниченной шириной, чтобы не расползалось за края
        self.container = QWidget(self.content)
        self.container.setObjectName("connectionContainer")
        self.container.setMaximumWidth(1080)
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(14)
        self.container_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        self._build_header()
        self._build_controls()
        self._build_log_viewer()

        # Добавляем контейнер на страницу
        self.add_widget(self.container)
        self.add_spacing(8)

    # ──────────────────────────────────────────────────────────────
    # UI
    # ──────────────────────────────────────────────────────────────
    def _build_header(self):
        hero = QFrame(self.container)
        hero.setObjectName("connectionHero")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(20, 18, 20, 18)
        hero_layout.setSpacing(8)

        title = QLabel("Диагностика сетевых соединений")
        title.setStyleSheet(
            """
            QLabel {
                color: #ffffff;
                font-size: 22px;
                font-weight: 700;
                font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;
            }
            """
        )

        subtitle = QLabel(
            "Проверьте доступность Discord и YouTube, найдите подмену DNS и быстро отправьте лог в поддержку."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(
            """
            QLabel {
                color: rgba(255, 255, 255, 0.7);
                font-size: 13px;
            }
            """
        )

        badges_layout = QHBoxLayout()
        badges_layout.setSpacing(8)
        self.status_badge = StatusBadge("Готово к тестированию", "info")
        self.progress_badge = StatusBadge("Ожидает запуска", "muted")
        badges_layout.addWidget(self.status_badge)
        badges_layout.addWidget(self.progress_badge)
        badges_layout.addStretch()

        hero_layout.addWidget(title)
        hero_layout.addWidget(subtitle)
        hero_layout.addLayout(badges_layout)

        hero.setStyleSheet(
            """
            QFrame#connectionHero {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                            stop:0 rgba(96, 205, 255, 0.12),
                                            stop:1 rgba(32, 32, 40, 0.5));
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 12px;
            }
            """
        )

        self.container_layout.addWidget(hero)

    def _build_controls(self):
        card = SettingsCard("Тестирование")

        # Тип теста
        selector_row = QHBoxLayout()
        selector_row.setSpacing(12)
        selector_row.addWidget(QLabel("Выбор теста:"))

        self.test_combo = QComboBox()
        self.test_combo.addItems(
            [
                "🌐 Все тесты (Discord + YouTube)",
                "🎮 Только Discord",
                "🎬 Только YouTube",
            ]
        )
        self.test_combo.setStyleSheet(
            """
            QComboBox {
                padding: 8px 12px;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                background: rgba(255, 255, 255, 0.04);
                color: #ffffff;
                font-size: 12px;
            }
            QComboBox QAbstractItemView {
                background: #1e1e1e;
                selection-background-color: #60cdff;
                selection-color: #000;
            }
            """
        )
        selector_row.addWidget(self.test_combo, 1)
        card.add_layout(selector_row)

        # Кнопки - первый ряд (основные)
        buttons_row1 = QHBoxLayout()
        buttons_row1.setSpacing(8)

        self.start_btn = ActionButton("Запустить тест", "fa5s.play", accent=True)
        self.start_btn.clicked.connect(self.start_test)
        buttons_row1.addWidget(self.start_btn)

        self.stop_btn = ActionButton("Стоп", "fa5s.stop")
        self.stop_btn.clicked.connect(self.stop_test)
        self.stop_btn.setEnabled(False)
        buttons_row1.addWidget(self.stop_btn)

        buttons_row1.addStretch()
        card.add_layout(buttons_row1)

        # Кнопки - второй ряд (дополнительные)
        buttons_row2 = QHBoxLayout()
        buttons_row2.setSpacing(8)

        self.send_log_btn = ActionButton("Отправить лог", "fa5s.paper-plane")
        self.send_log_btn.clicked.connect(self.send_log_to_telegram)
        self.send_log_btn.setEnabled(False)
        buttons_row2.addWidget(self.send_log_btn)

        buttons_row2.addStretch()
        card.add_layout(buttons_row2)

        # Прогресс + статус
        status_layout = QHBoxLayout()
        status_layout.setSpacing(12)

        self.status_label = QLabel("Готово к тестированию")
        self.status_label.setStyleSheet(
            """
            QLabel {
                color: rgba(255, 255, 255, 0.75);
                font-size: 12px;
                font-weight: 500;
            }
            """
        )
        status_layout.addWidget(self.status_label, 1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet(
            """
            QProgressBar {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 6px;
                color: #ffffff;
                text-align: center;
                padding: 2px;
            }
            QProgressBar::chunk {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #60cdff, stop:1 #4FA3FF);
                border-radius: 4px;
            }
            """
        )
        status_layout.addWidget(self.progress_bar, 1)

        card.add_layout(status_layout)
        self.container_layout.addWidget(card)

    def _build_log_viewer(self):
        log_card = SettingsCard("Результат тестирования")
        self.result_text = ScrollBlockingTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setStyleSheet(
            """
            QTextEdit {
                background: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 8px;
                color: #e0e0e0;
                font-family: 'Cascadia Code', 'Consolas', monospace;
                font-size: 12px;
            }
            """
        )
        log_card.add_widget(self.result_text)
        self.container_layout.addWidget(log_card)

    # ──────────────────────────────────────────────────────────────
    # Логика теста
    # ──────────────────────────────────────────────────────────────
    def start_test(self):
        if self.is_testing:
            self._append("ℹ️ Тест уже выполняется. Дождитесь завершения.")
            return

        selection = self.test_combo.currentText()
        test_type = "all"
        if "Discord" in selection and "YouTube" not in selection:
            test_type = "discord"
        elif "YouTube" in selection and "Discord" not in selection:
            test_type = "youtube"

        self.result_text.clear()
        self._append(f"🚀 Запуск тестирования: {selection}")
        self._append("=" * 50)

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.test_combo.setEnabled(False)
        self.send_log_btn.setEnabled(False)
        self._set_status("🔄 Тестирование в процессе...", "info")
        self.status_badge.set_status("Тест выполняется", "info")
        self.progress_badge.set_status("Идёт проверка", "info")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)

        self.worker_thread = QThread(self)
        self.worker = ConnectionTestWorker(test_type)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.update_signal.connect(self._on_worker_update)
        self.worker.finished_signal.connect(self._on_worker_finished)
        self.worker.finished_signal.connect(self.worker_thread.quit)
        self.worker.finished_signal.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)

        self.is_testing = True
        self.worker_thread.start()

    def stop_test(self):
        if not self.worker or not self.worker_thread:
            return

        self._append("\n⚠️ Остановка теста...")
        self._set_status("⏹️ Останавливаем...", "warning")
        self.worker.stop_gracefully()

        self.stop_check_timer = QTimer(self)
        self.stop_check_attempts = 0

        def check_thread():
            if not self.stop_check_timer:
                return
            self.stop_check_attempts += 1
            if not self.worker_thread or not self.worker_thread.isRunning():
                if self.stop_check_timer:
                    self.stop_check_timer.stop()
                self._append("✅ Тест остановлен")
                self._on_worker_finished()
            elif self.stop_check_attempts > 50:
                if self.stop_check_timer:
                    self.stop_check_timer.stop()
                self._append("⚠️ Принудительная остановка...")
                if self.worker_thread:
                    self.worker_thread.terminate()
                    QTimer.singleShot(800, self._finalize_stop)

        self.stop_check_timer.timeout.connect(check_thread)
        self.stop_check_timer.start(100)

    def _finalize_stop(self):
        self._on_worker_finished()

    def _on_worker_update(self, message: str):
        if "DNS" in message and "подмен" in message:
            self._append(message)
            self._append("💡 Совет: откройте вкладку «DNS подмена» для детального анализа")
        else:
            self._append(message)

        scrollbar = self.result_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _on_worker_finished(self):
        self.is_testing = False
        self.worker = None
        self.worker_thread = None
        self.stop_check_timer = None

        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.test_combo.setEnabled(True)
        self.send_log_btn.setEnabled(True)
        self.progress_bar.setVisible(False)

        self.status_badge.set_status("Тест завершён", "success")
        self.progress_badge.set_status("Готово к отправке лога", "muted")
        self._set_status("✅ Тестирование завершено", "success")
        self._append("\n" + "=" * 50)
        self._append("🎉 Тестирование завершено! Лог готов к отправке.")

    # ──────────────────────────────────────────────────────────────
    # DNS и лог
    # ──────────────────────────────────────────────────────────────
    def send_log_to_telegram(self):
        if self.is_sending_log:
            self._append("ℹ️ Лог уже отправляется...")
            return

        temp_log_path = os.path.join(LOGS_FOLDER, "connection_test_temp.log")
        if not os.path.exists(temp_log_path):
            self._append("❌ Лог не найден. Сначала выполните тестирование.")
            self._set_status("Лог не найден", "error")
            return

        try:
            bot_connected = check_bot_connection()
            error_msg = None if bot_connected else "Не удалось подключиться к Telegram боту"
        except Exception as exc:  # pragma: no cover - сеть/бот
            bot_connected = False
            error_msg = str(exc)

        if not bot_connected:
            self._append(f"⚠️ {error_msg}. Сохраните лог вручную.")
            self.save_log_locally()
            return

        test_type = self.test_combo.currentText()
        caption = (
            f"📊 <b>Лог тестирования соединений</b>\n"
            f"Тип: {test_type}\n"
            f"Zapret2 v{APP_VERSION}\n"
            f"ID: <code>{get_client_id()}</code>\n"
            f"Host: {platform.node()}\n"
            f"Time: {time.strftime('%d.%m.%Y %H:%M:%S')}"
        )

        self.send_log_btn.setEnabled(False)
        self.is_sending_log = True
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self._set_status("📤 Отправка лога...", "info")

        self.log_send_thread = QThread(self)
        self.log_send_worker = LogSendWorker(temp_log_path, caption)
        self.log_send_worker.moveToThread(self.log_send_thread)
        self.log_send_thread.started.connect(self.log_send_worker.run)
        self.log_send_worker.finished.connect(self._on_log_sent)
        self.log_send_worker.finished.connect(self.log_send_thread.quit)
        self.log_send_worker.finished.connect(self.log_send_worker.deleteLater)
        self.log_send_thread.finished.connect(self.log_send_thread.deleteLater)
        self.log_send_thread.start()

    def _on_log_sent(self, success: bool, message: str):
        self.progress_bar.setVisible(False)
        self.is_sending_log = False
        self.send_log_btn.setEnabled(True)
        self.log_send_worker = None
        self.log_send_thread = None

        if success:
            self._set_status("✅ Лог отправлен", "success")
            self._append("✅ Лог успешно отправлен в поддержку.")
            try:
                temp_log_path = os.path.join(LOGS_FOLDER, "connection_test_temp.log")
                if os.path.exists(temp_log_path):
                    os.remove(temp_log_path)
            except Exception:
                pass
        else:
            self._set_status("❌ Ошибка отправки", "error")
            self._append(f"❌ Ошибка отправки: {message}")
            self._append("💡 Сохраняем лог локально.")
            self.save_log_locally()

    def save_log_locally(self):
        temp_log_path = os.path.join(LOGS_FOLDER, "connection_test_temp.log")
        if not os.path.exists(temp_log_path):
            self._append("❌ Файл лога не найден.")
            return

        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            save_path = os.path.join(LOGS_FOLDER, f"connection_test_{timestamp}.log")
            with open(temp_log_path, "r", encoding="utf-8-sig") as src, open(
                save_path, "w", encoding="utf-8-sig"
            ) as dest:
                dest.write(src.read())
            self._append(f"💾 Лог сохранён: {save_path}")
            os.startfile(save_path) if platform.system().lower() == "windows" else None
        except Exception as exc:
            self._append(f"❌ Не удалось сохранить лог: {exc}")

    # ──────────────────────────────────────────────────────────────
    # Вспомогательное
    # ──────────────────────────────────────────────────────────────
    def _append(self, text: str):
        self.result_text.append(text)

    def _set_status(self, text: str, status: str = "muted"):
        self.status_label.setText(text)
        self.status_badge.set_status(text, status)
    
    def cleanup(self):
        """Очистка потоков при закрытии"""
        from log import log
        try:
            if self.worker_thread and self.worker_thread.isRunning():
                log("Останавливаем connection test worker...", "DEBUG")
                if self.worker:
                    self.worker.stop_gracefully()
                self.worker_thread.quit()
                if not self.worker_thread.wait(2000):
                    log("⚠ Connection test worker не завершился, принудительно завершаем", "WARNING")
                    try:
                        self.worker_thread.terminate()
                        self.worker_thread.wait(500)
                    except:
                        pass
            
            if self.log_send_thread and self.log_send_thread.isRunning():
                log("Останавливаем log send worker...", "DEBUG")
                self.log_send_thread.quit()
                if not self.log_send_thread.wait(2000):
                    log("⚠ Log send worker не завершился, принудительно завершаем", "WARNING")
                    try:
                        self.log_send_thread.terminate()
                        self.log_send_thread.wait(500)
                    except:
                        pass
        except Exception as e:
            log(f"Ошибка при очистке connection_page: {e}", "DEBUG")


