# ui/pages/dns_check_page.py
"""Страница проверки DNS подмены провайдером."""

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QWidget
)
from PyQt6.QtCore import QThread, QObject, pyqtSignal, Qt
from PyQt6.QtGui import QFont, QTextCursor

from .base_page import BasePage, ScrollBlockingTextEdit
from ui.compat_widgets import SettingsCard, ActionButton
from ui.theme import get_theme_tokens
from ui.theme_semantic import get_semantic_palette
from ui.text_catalog import tr as tr_catalog

try:
    from qfluentwidgets import ProgressBar, IndeterminateProgressBar, InfoBar
    _HAS_FLUENT_PROGRESS = True
except ImportError:
    from PyQt6.QtWidgets import QProgressBar as ProgressBar  # type: ignore[assignment]
    from PyQt6.QtWidgets import QProgressBar as IndeterminateProgressBar  # type: ignore[assignment]
    InfoBar = None
    _HAS_FLUENT_PROGRESS = False

try:
    from qfluentwidgets import StrongBodyLabel, BodyLabel, CaptionLabel
    _HAS_FLUENT_LABELS = True
except ImportError:
    StrongBodyLabel = QLabel; BodyLabel = QLabel; CaptionLabel = QLabel
    _HAS_FLUENT_LABELS = False


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
            parent,
            title_key="page.dns_check.title",
            subtitle_key="page.dns_check.subtitle",
        )
        self.worker = None
        self.thread = None
        self._status_tone = "muted"
        self._status_bold = False
        self._info_icon_labels = []
        self._info_text_labels = []
        self._info_item_keys = [
            "page.dns_check.info.blocking",
            "page.dns_check.info.servers",
            "page.dns_check.info.recommended",
        ]

        self.enable_deferred_ui_build(after_build=self._after_ui_built)

    def _after_ui_built(self) -> None:
        self._apply_page_theme(force=True)
    
    def _build_ui(self):
        """Создаёт интерфейс страницы."""
        tokens = get_theme_tokens()
        # Информационная карточка
        self.info_card = SettingsCard(tr_catalog("page.dns_check.card.what_we_check", language=self._ui_language, default="Что проверяем"))
        info_layout = QVBoxLayout()
        info_layout.setSpacing(8)
        
        info_items = [
            ("fa5s.search", self._info_item_keys[0], "Блокирует ли провайдер сайты через DNS подмену"),
            ("fa5s.server", self._info_item_keys[1], "Какие DNS серверы возвращают корректные адреса"),
            ("fa5s.check-circle", self._info_item_keys[2], "Какой DNS сервер рекомендуется использовать"),
        ]
        
        for icon_name, text_key, default_text in info_items:
            row = QHBoxLayout()
            row.setSpacing(10)
            
            try:
                import qtawesome as qta
                icon_label = QLabel()
                icon_label.setProperty("dnsIconName", icon_name)
                icon_label.setPixmap(qta.icon(icon_name, color=tokens.accent_hex).pixmap(16, 16))
                icon_label.setFixedWidth(20)
                self._info_icon_labels.append(icon_label)
                row.addWidget(icon_label)
            except:
                pass
            
            text_label = BodyLabel(tr_catalog(text_key, language=self._ui_language, default=default_text))
            text_label.setStyleSheet(f"color: {tokens.fg_muted};")
            text_label.setProperty("textKey", text_key)
            text_label.setProperty("textDefault", default_text)
            self._info_text_labels.append(text_label)
            row.addWidget(text_label, 1)
            
            info_layout.addLayout(row)
        
        self.info_card.add_layout(info_layout)
        self.layout.addWidget(self.info_card)
        
        # Карточка с управлением
        self.control_card = SettingsCard(tr_catalog("page.dns_check.card.testing", language=self._ui_language, default="Тестирование"))
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(12)
        
        self.check_button = ActionButton(tr_catalog("page.dns_check.button.start", language=self._ui_language, default="Начать проверку"), "fa5s.play")
        self.check_button.clicked.connect(self.start_check)
        buttons_layout.addWidget(self.check_button, 1)

        self.quick_check_button = ActionButton(tr_catalog("page.dns_check.button.quick", language=self._ui_language, default="Быстрая проверка"), "fa5s.bolt")
        self.quick_check_button.clicked.connect(self.quick_dns_check)
        buttons_layout.addWidget(self.quick_check_button, 1)

        self.save_button = ActionButton(tr_catalog("page.dns_check.button.save", language=self._ui_language, default="Сохранить результаты"), "fa5s.save")
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self.save_results)
        buttons_layout.addWidget(self.save_button, 1)
        self.control_card.add_layout(buttons_layout)
        
        # Прогресс бар
        self.progress_bar = IndeterminateProgressBar(self)
        self.progress_bar.setVisible(False)
        self.control_card.add_widget(self.progress_bar)
        
        # Статус
        self.status_label = CaptionLabel(tr_catalog("page.dns_check.status.ready", language=self._ui_language, default="Готово к проверке"))
        self._set_status(tr_catalog("page.dns_check.status.ready", language=self._ui_language, default="Готово к проверке"), tone="muted", bold=False)
        self.control_card.add_widget(self.status_label)

        self.layout.addWidget(self.control_card)
        
        # Результаты
        self.results_card = SettingsCard(tr_catalog("page.dns_check.card.results", language=self._ui_language, default="Результаты"))
        
        self.result_text = ScrollBlockingTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setFont(QFont("Consolas", 10))
        self.result_text.setMinimumHeight(300)
        self.result_text.setStyleSheet(
            f"""
            QTextEdit {{
                background-color: {tokens.surface_bg};
                color: {tokens.fg};
                border: 1px solid {tokens.surface_border};
                border-radius: 6px;
                padding: 12px;
            }}
            """
        )
        self.results_card.add_widget(self.result_text)
        
        self.layout.addWidget(self.results_card)
        
        # Stretch в конце
        self.layout.addStretch()

    def _set_status(self, text: str, *, tone: str, bold: bool) -> None:
        tokens = get_theme_tokens()
        semantic = get_semantic_palette()
        tone_map = {
            "muted": tokens.fg_muted,
            "accent": tokens.accent_hex,
            "success": semantic.success,
            "warning": semantic.warning,
            "error": semantic.error,
        }
        color = tone_map.get(tone, tokens.fg_muted)
        self.status_label.setText(text)
        self.status_label.setStyleSheet(
            f"color: {color}; padding: 4px 0;"
        )
        self._status_tone = tone
        self._status_bold = bold

    def _apply_page_theme(self, tokens=None, force: bool = False) -> None:
        _ = force
        tokens = tokens or get_theme_tokens()
        for label in list(self._info_text_labels):
            try:
                label.setStyleSheet(f"color: {tokens.fg_muted};")
            except Exception:
                pass

        try:
            import qtawesome as qta

            for icon_label in list(self._info_icon_labels):
                try:
                    icon_name = (icon_label.property("dnsIconName") or "fa5s.search").strip()
                    icon_label.setPixmap(qta.icon(icon_name, color=tokens.accent_hex).pixmap(16, 16))
                except Exception:
                    pass
        except Exception:
            pass

        try:
            self.result_text.setStyleSheet(
                f"""
                QTextEdit {{
                    background-color: {tokens.surface_bg};
                    color: {tokens.fg};
                    border: 1px solid {tokens.surface_border};
                    border-radius: 6px;
                    padding: 12px;
                }}
                """
            )
        except Exception:
            pass

        try:
            self._set_status(self.status_label.text(), tone=self._status_tone, bold=self._status_bold)
        except Exception:
            pass

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
        if _HAS_FLUENT_PROGRESS:
            self.progress_bar.start()
        self._set_status("🔄 Выполняется проверка DNS...", tone="accent", bold=False)
        
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
        tokens = get_theme_tokens()
        semantic = get_semantic_palette()
        # Применяем цветовое форматирование
        if "✅" in text:
            color = semantic.success
        elif "❌" in text:
            color = semantic.error
        elif "⚠️" in text:
            color = semantic.warning
        elif "🚫" in text:
            color = "#e91e63"
        elif "🔍" in text or "📊" in text:
            color = tokens.accent_hex
        elif "=" in text and len(text) > 20:
            color = tokens.fg_faint
        else:
            color = tokens.fg
        
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
        if _HAS_FLUENT_PROGRESS:
            self.progress_bar.stop()
        self.progress_bar.setVisible(False)
        
        # Обновляем статус
        if results and results.get('summary', {}).get('dns_poisoning_detected'):
            self._set_status("⚠️ Обнаружена DNS подмена!", tone="error", bold=True)
        else:
            self._set_status("✅ Проверка завершена", tone="success", bold=True)
        
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
        from PyQt6.QtWidgets import QFileDialog
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
                
                if InfoBar:
                    InfoBar.success(title="Сохранено", content=f"Результаты сохранены в:\n{file_path}", parent=self.window())

                # Открываем папку с файлом
                os.startfile(os.path.dirname(file_path))

            except Exception as e:
                if InfoBar:
                    InfoBar.error(title="Ошибка", content=f"Не удалось сохранить файл:\n{str(e)}", parent=self.window())
    
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

    def _set_card_title(self, card: SettingsCard, text: str) -> None:
        try:
            item = card.main_layout.itemAt(0)
            widget = item.widget() if item else None
            if widget is not None and hasattr(widget, "setText"):
                widget.setText(text)
        except Exception:
            pass

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)

        self._set_card_title(self.info_card, tr_catalog("page.dns_check.card.what_we_check", language=self._ui_language, default="Что проверяем"))
        self._set_card_title(self.control_card, tr_catalog("page.dns_check.card.testing", language=self._ui_language, default="Тестирование"))
        self._set_card_title(self.results_card, tr_catalog("page.dns_check.card.results", language=self._ui_language, default="Результаты"))

        for label in list(self._info_text_labels):
            try:
                key = label.property("textKey")
                default = label.property("textDefault")
                label.setText(tr_catalog(str(key), language=self._ui_language, default=str(default or "")))
            except Exception:
                pass

        self.check_button.setText(tr_catalog("page.dns_check.button.start", language=self._ui_language, default="Начать проверку"))
        self.quick_check_button.setText(tr_catalog("page.dns_check.button.quick", language=self._ui_language, default="Быстрая проверка"))
        self.save_button.setText(tr_catalog("page.dns_check.button.save", language=self._ui_language, default="Сохранить результаты"))
