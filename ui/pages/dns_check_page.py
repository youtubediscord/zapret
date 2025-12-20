# ui/pages/dns_check_page.py
"""Страница проверки DNS подмены провайдером."""

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, 
    QProgressBar, QFrame, QWidget
)
from PyQt6.QtCore import QThread, QObject, pyqtSignal, Qt
from PyQt6.QtGui import QFont, QTextCursor

from .base_page import BasePage, ScrollBlockingTextEdit
from ui.sidebar import SettingsCard, ActionButton


class DNSCheckWorker(QObject):
    """Worker для выполнения DNS проверки в отдельном потоке"""
    update_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int)  # current, total
    finished_signal = pyqtSignal(dict)
    
    def run(self):
        try:
            from dns_checker import DNSChecker
            checker = DNSChecker()
            results = checker.check_dns_poisoning(log_callback=self.update_signal.emit)
            self.finished_signal.emit(results)
        except Exception as e:
            self.update_signal.emit(f"❌ Ошибка: {str(e)}")
            self.finished_signal.emit({})


class DNSCheckPage(BasePage):
    """Страница проверки DNS подмены провайдером."""
    
    def __init__(self, parent=None):
        super().__init__(
            "Проверка DNS подмены",
            "Проверка резолвинга доменов YouTube и Discord через различные DNS серверы",
            parent
        )
        self.worker = None
        self.thread = None
        self._build_ui()
    
    def _build_ui(self):
        """Создаёт интерфейс страницы."""
        # Информационная карточка
        info_card = SettingsCard("Что проверяем")
        info_layout = QVBoxLayout()
        info_layout.setSpacing(8)
        
        info_items = [
            ("fa5s.search", "Блокирует ли провайдер сайты через DNS подмену"),
            ("fa5s.server", "Какие DNS серверы возвращают корректные адреса"),
            ("fa5s.check-circle", "Какой DNS сервер рекомендуется использовать"),
        ]
        
        for icon_name, text in info_items:
            row = QHBoxLayout()
            row.setSpacing(10)
            
            try:
                import qtawesome as qta
                icon_label = QLabel()
                icon_label.setPixmap(qta.icon(icon_name, color='#60cdff').pixmap(16, 16))
                icon_label.setFixedWidth(20)
                row.addWidget(icon_label)
            except:
                pass
            
            text_label = QLabel(text)
            text_label.setStyleSheet("color: rgba(255, 255, 255, 0.8); font-size: 13px;")
            row.addWidget(text_label, 1)
            
            info_layout.addLayout(row)
        
        info_card.add_layout(info_layout)
        self.layout.addWidget(info_card)
        
        # Карточка с управлением
        control_card = SettingsCard("Тестирование")
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(12)
        
        self.check_button = ActionButton("Начать проверку", "fa5s.play")
        self.check_button.setMinimumHeight(40)
        self.check_button.clicked.connect(self.start_check)
        buttons_layout.addWidget(self.check_button)
        
        self.quick_check_button = ActionButton("Быстрая проверка", "fa5s.bolt")
        self.quick_check_button.setMinimumHeight(40)
        self.quick_check_button.clicked.connect(self.quick_dns_check)
        buttons_layout.addWidget(self.quick_check_button)
        
        self.save_button = ActionButton("Сохранить результаты", "fa5s.save")
        self.save_button.setMinimumHeight(40)
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self.save_results)
        buttons_layout.addWidget(self.save_button)
        
        buttons_layout.addStretch()
        control_card.add_layout(buttons_layout)
        
        # Прогресс бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: rgba(255, 255, 255, 0.1);
                border: none;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background-color: #60cdff;
                border-radius: 3px;
            }
        """)
        control_card.add_widget(self.progress_bar)
        
        # Статус
        self.status_label = QLabel("Готово к проверке")
        self.status_label.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 12px; padding: 4px 0;")
        control_card.add_widget(self.status_label)
        
        self.layout.addWidget(control_card)
        
        # Результаты
        results_card = SettingsCard("Результаты")
        
        self.result_text = ScrollBlockingTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setFont(QFont("Consolas", 10))
        self.result_text.setMinimumHeight(300)
        self.result_text.setStyleSheet("""
            QTextEdit {
                background-color: rgba(0, 0, 0, 0.3);
                color: #d4d4d4;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                padding: 12px;
            }
        """)
        results_card.add_widget(self.result_text)
        
        self.layout.addWidget(results_card)
        
        # Stretch в конце
        self.layout.addStretch()
    
    def start_check(self):
        """Начинает полную проверку DNS."""
        if self.thread and self.thread.isRunning():
            return
        
        self.result_text.clear()
        self.check_button.setEnabled(False)
        self.quick_check_button.setEnabled(False)
        self.save_button.setEnabled(False)
        
        # Показываем прогресс
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Неопределённый прогресс
        self.status_label.setText("🔄 Выполняется проверка DNS...")
        self.status_label.setStyleSheet("color: #60cdff; font-size: 12px; padding: 4px 0;")
        
        # Создаём поток и worker
        self.thread = QThread()
        self.worker = DNSCheckWorker()
        self.worker.moveToThread(self.thread)
        
        # Подключаем сигналы
        self.thread.started.connect(self.worker.run)
        self.worker.update_signal.connect(self.append_result)
        self.worker.finished_signal.connect(self.on_check_finished)
        
        # Запускаем
        self.thread.start()
    
    def append_result(self, text):
        """Добавляет текст в результаты с форматированием."""
        # Применяем цветовое форматирование
        if "✅" in text:
            color = "#6ccb5f"
        elif "❌" in text:
            color = "#ff6b6b"
        elif "⚠️" in text:
            color = "#ffc107"
        elif "🚫" in text:
            color = "#e91e63"
        elif "🔍" in text or "📊" in text:
            color = "#60cdff"
        elif "=" in text and len(text) > 20:
            color = "rgba(255, 255, 255, 0.4)"
        else:
            color = "#d4d4d4"
        
        # Форматируем текст
        formatted_text = f'<span style="color: {color};">{text}</span>'
        
        # Добавляем в текстовое поле
        cursor = self.result_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(formatted_text + "<br>")
        
        # Автопрокрутка
        self.result_text.verticalScrollBar().setValue(
            self.result_text.verticalScrollBar().maximum()
        )
    
    def on_check_finished(self, results):
        """Обработчик завершения проверки."""
        self.check_button.setEnabled(True)
        self.quick_check_button.setEnabled(True)
        self.save_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        # Обновляем статус
        if results and results.get('summary', {}).get('dns_poisoning_detected'):
            self.status_label.setText("⚠️ Обнаружена DNS подмена!")
            self.status_label.setStyleSheet("color: #ff6b6b; font-size: 12px; font-weight: bold; padding: 4px 0;")
        else:
            self.status_label.setText("✅ Проверка завершена")
            self.status_label.setStyleSheet("color: #6ccb5f; font-size: 12px; font-weight: bold; padding: 4px 0;")
        
        # Очистка потока
        if self.thread:
            self.thread.quit()
            self.thread.wait(500)  # Короткий таймаут (поток уже завершается)
            self.thread.deleteLater()
            self.thread = None
        
        if self.worker:
            self.worker.deleteLater()
            self.worker = None
    
    def quick_dns_check(self):
        """Выполняет быструю проверку только системного DNS."""
        import socket
        
        self.result_text.clear()
        self.append_result("⚡ БЫСТРАЯ ПРОВЕРКА СИСТЕМНОГО DNS")
        self.append_result("=" * 45)
        self.append_result("")
        
        test_domains = {
            'YouTube': 'www.youtube.com',
            'Discord': 'discord.com',
            'Google': 'google.com',
            'Cloudflare': 'cloudflare.com',
        }
        
        all_ok = True
        for name, domain in test_domains.items():
            try:
                ip = socket.gethostbyname(domain)
                self.append_result(f"✅ {name} ({domain}): {ip}")
            except Exception as e:
                self.append_result(f"❌ {name} ({domain}): Ошибка - {e}")
                all_ok = False
        
        self.append_result("")
        if all_ok:
            self.append_result("✅ Все домены резолвятся корректно")
        else:
            self.append_result("⚠️ Есть проблемы с резолвингом некоторых доменов")
        
        self.save_button.setEnabled(True)
    
    def save_results(self):
        """Сохраняет результаты в файл."""
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        from datetime import datetime
        import os
        
        # Выбираем путь для сохранения
        default_filename = f"dns_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить результаты DNS проверки",
            default_filename,
            "Text Files (*.txt);;All Files (*.*)"
        )
        
        if file_path:
            try:
                # Получаем текст без HTML тегов
                plain_text = self.result_text.toPlainText()
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("DNS CHECK RESULTS\n")
                    f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("=" * 60 + "\n\n")
                    f.write(plain_text)
                
                QMessageBox.information(
                    self,
                    "Сохранено",
                    f"Результаты сохранены в:\n{file_path}"
                )
                
                # Открываем папку с файлом
                os.startfile(os.path.dirname(file_path))
                
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Ошибка",
                    f"Не удалось сохранить файл:\n{str(e)}"
                )
    
    def cleanup(self):
        """Очистка потоков при закрытии"""
        from log import log
        try:
            if self.thread and self.thread.isRunning():
                log("Останавливаем DNS check worker...", "DEBUG")
                self.thread.quit()
                if not self.thread.wait(2000):
                    log("⚠ DNS check worker не завершился, принудительно завершаем", "WARNING")
                    try:
                        self.thread.terminate()
                        self.thread.wait(500)
                    except:
                        pass
        except Exception as e:
            log(f"Ошибка при очистке dns_check_page: {e}", "DEBUG")

