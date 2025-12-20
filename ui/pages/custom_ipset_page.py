# ui/pages/custom_ipset_page.py
"""Страница управления пользовательскими IP (my-ipset.txt)"""

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel,
    QMessageBox, QLineEdit
)
import ipaddress
import os

from .base_page import BasePage, ScrollBlockingPlainTextEdit
from ui.sidebar import SettingsCard, ActionButton
from log import log
import re


def split_ip_entries(text: str) -> list[str]:
    """Разделяет IP по пробелам, запятым, точкам с запятой."""
    parts = re.split(r'[\s,;]+', text)
    return [p.strip() for p in parts if p.strip()]


class CustomIpSetPage(BasePage):
    """Страница управления пользовательскими IP (my-ipset.txt)"""

    ipset_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(
            "Мои IP",
            "Пользовательский список IP/подсетей (my-ipset.txt). Изменения сохраняются автоматически.",
            parent,
        )
        self._build_ui()
        QTimer.singleShot(100, self._load_entries)

    @staticmethod
    def normalize_ip_entry(text: str) -> str | None:
        """Приводит IP/подсеть к каноничному виду, либо None если некорректно.
        Диапазоны (a-b) не поддерживаются.
        Поддерживает извлечение IP из URL (https://1.2.3.4/...)
        """
        line = text.strip()
        if not line or line.startswith("#"):
            return None

        # Извлекаем IP из URL если это ссылка
        if "://" in line:
            try:
                from urllib.parse import urlparse
                parsed = urlparse(line)
                host = parsed.netloc or parsed.path.split('/')[0]
                # Убираем порт если есть
                host = host.split(':')[0]
                line = host
            except:
                pass

        # Диапазоны не поддерживаются
        if "-" in line:
            return None

        # Подсеть
        if "/" in line:
            try:
                net = ipaddress.ip_network(line, strict=False)
                return net.with_prefixlen
            except Exception:
                return None

        # Одиночный IP
        try:
            addr = ipaddress.ip_address(line)
            return str(addr)
        except Exception:
            return None

    def _build_ui(self):
        desc_card = SettingsCard()
        desc = QLabel(
            "Добавляйте свои IP/подсети. Поддерживаются форматы:\n"
            "• Одиночный IP: 1.2.3.4\n"
            "• Подсеть: 10.0.0.0/8\n"
            "Диапазоны (a-b) не поддерживаются. Поддерживается Ctrl+Z."
        )
        desc.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-size: 13px;")
        desc.setWordWrap(True)
        desc_card.add_widget(desc)
        self.layout.addWidget(desc_card)

        add_card = SettingsCard("Добавить IP/подсеть")
        add_layout = QHBoxLayout()
        add_layout.setSpacing(8)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Например: 1.2.3.4 или 10.0.0.0/8")
        self.input.setStyleSheet("""
            QLineEdit {
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                padding: 10px 12px;
                color: #ffffff;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #60cdff;
            }
        """)
        self.input.returnPressed.connect(self._add_entry)
        add_layout.addWidget(self.input, 1)

        self.add_btn = ActionButton("Добавить", "fa5s.plus", accent=True)
        self.add_btn.setFixedHeight(38)
        self.add_btn.clicked.connect(self._add_entry)
        add_layout.addWidget(self.add_btn)

        add_card.add_layout(add_layout)
        self.layout.addWidget(add_card)

        actions_card = SettingsCard("Действия")
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(8)

        self.open_btn = ActionButton("Открыть файл", "fa5s.external-link-alt")
        self.open_btn.setFixedHeight(36)
        self.open_btn.clicked.connect(self._open_file)
        actions_layout.addWidget(self.open_btn)

        self.clear_btn = ActionButton("Очистить всё", "fa5s.trash-alt")
        self.clear_btn.setFixedHeight(36)
        self.clear_btn.clicked.connect(self._clear_all)
        actions_layout.addWidget(self.clear_btn)

        actions_layout.addStretch()
        actions_card.add_layout(actions_layout)
        self.layout.addWidget(actions_card)

        # Текстовый редактор (вместо списка)
        editor_card = SettingsCard("Мой IP-список (редактор)")
        editor_layout = QVBoxLayout()
        editor_layout.setSpacing(8)

        self.text_edit = ScrollBlockingPlainTextEdit()
        self.text_edit.setPlaceholderText(
            "IP/подсети по одному на строку:\n"
            "192.168.0.1\n"
            "10.0.0.0/8\n\n"
            "Комментарии начинаются с #"
        )
        self.text_edit.setStyleSheet("""
            QPlainTextEdit {
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 12px;
                color: #ffffff;
                font-family: Consolas, 'Courier New', monospace;
                font-size: 13px;
            }
            QPlainTextEdit:focus {
                border: 1px solid #60cdff;
            }
        """)
        self.text_edit.setMinimumHeight(350)

        # Автосохранение
        self._save_timer = QTimer()
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._auto_save)
        self.text_edit.textChanged.connect(self._on_text_changed)

        editor_layout.addWidget(self.text_edit)

        hint = QLabel("💡 Изменения сохраняются автоматически через 500мс")
        hint.setStyleSheet("color: rgba(255, 255, 255, 0.4); font-size: 11px;")
        editor_layout.addWidget(hint)

        # Метка ошибок валидации
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #ff6b6b; font-size: 11px;")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        editor_layout.addWidget(self.error_label)

        editor_card.add_layout(editor_layout)
        self.layout.addWidget(editor_card)

        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-size: 11px;")
        self.layout.addWidget(self.status_label)
        
        # Стили для валидации
        self._normal_style = """
            QPlainTextEdit {
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 12px;
                color: #ffffff;
                font-family: Consolas, 'Courier New', monospace;
                font-size: 13px;
            }
            QPlainTextEdit:focus {
                border: 1px solid #60cdff;
            }
        """
        self._error_style = """
            QPlainTextEdit {
                background: rgba(255, 100, 100, 0.08);
                border: 2px solid #ff6b6b;
                border-radius: 8px;
                padding: 12px;
                color: #ffffff;
                font-family: Consolas, 'Courier New', monospace;
                font-size: 13px;
            }
        """

    def _load_entries(self):
        """Загружает список из my-ipset.txt"""
        try:
            from utils.ipsets_manager import MY_IPSET_PATH

            entries = []
            if os.path.exists(MY_IPSET_PATH):
                with open(MY_IPSET_PATH, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            entries.append(line)

            # Блокируем сигнал чтобы не срабатывало автосохранение
            self.text_edit.blockSignals(True)
            self.text_edit.setPlainText('\n'.join(entries))
            self.text_edit.blockSignals(False)
            
            self._update_status()
            log(f"Загружено {len(entries)} строк из my-ipset.txt", "INFO")
        except Exception as e:
            log(f"Ошибка загрузки my-ipset.txt: {e}", "ERROR")
            self.status_label.setText(f"❌ Ошибка: {e}")

    def _on_text_changed(self):
        self._save_timer.start(500)
        self._update_status()

    def _auto_save(self):
        self._save_entries()
        self.status_label.setText(self.status_label.text() + " • ✅ Сохранено")

    def _save_entries(self):
        """Сохраняет список в my-ipset.txt"""
        try:
            from utils.ipsets_manager import MY_IPSET_PATH

            os.makedirs(os.path.dirname(MY_IPSET_PATH), exist_ok=True)
            
            text = self.text_edit.toPlainText()
            entries = []
            normalized_lines = []  # Для обновления UI
            
            for line in text.split('\n'):
                line = line.strip()
                if not line:
                    continue
                # Сохраняем комментарии как есть
                if line.startswith('#'):
                    entries.append(line)
                    normalized_lines.append(line)
                    continue
                
                # Разделяем по пробелам/запятым (1.1.1.1 2.2.2.2 -> отдельные строки)
                separated = split_ip_entries(line)
                
                for item in separated:
                    # Нормализуем каждый IP/подсеть
                    norm = self.normalize_ip_entry(item)
                    if norm:
                        if norm not in entries:
                            entries.append(norm)
                            normalized_lines.append(norm)
                    else:
                        # Невалидная строка - оставляем как есть
                        normalized_lines.append(item)

            with open(MY_IPSET_PATH, "w", encoding="utf-8") as f:
                for entry in entries:
                    f.write(f"{entry}\n")

            # Обновляем UI - заменяем URL на IP
            new_text = '\n'.join(normalized_lines)
            if new_text != text:
                cursor = self.text_edit.textCursor()
                pos = cursor.position()
                
                self.text_edit.blockSignals(True)
                self.text_edit.setPlainText(new_text)
                
                # Восстанавливаем позицию курсора
                cursor = self.text_edit.textCursor()
                cursor.setPosition(min(pos, len(new_text)))
                self.text_edit.setTextCursor(cursor)
                self.text_edit.blockSignals(False)

            log(f"Сохранено {len(entries)} строк в my-ipset.txt", "SUCCESS")
            self.ipset_changed.emit()
        except Exception as e:
            log(f"Ошибка сохранения my-ipset.txt: {e}", "ERROR")

    def _update_status(self):
        text = self.text_edit.toPlainText()
        lines = [l.strip() for l in text.split('\n') if l.strip() and not l.strip().startswith('#')]
        
        # Валидируем строки
        invalid_lines = []
        for i, line in enumerate(text.split('\n'), 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # Разделяем по пробелам
            for item in split_ip_entries(line):
                if not self.normalize_ip_entry(item):
                    invalid_lines.append(f"Строка {i}: {item}")
        
        # Обновляем UI
        if invalid_lines:
            self.text_edit.setStyleSheet(self._error_style)
            self.error_label.setText("❌ Неверный формат:\n" + "\n".join(invalid_lines[:5]))
            if len(invalid_lines) > 5:
                self.error_label.setText(self.error_label.text() + f"\n... и ещё {len(invalid_lines) - 5}")
            self.error_label.show()
        else:
            self.text_edit.setStyleSheet(self._normal_style)
            self.error_label.hide()
        
        self.status_label.setText(f"📊 Записей: {len(lines)}")

    def _add_entry(self):
        text = self.input.text().strip()
        if not text:
            return

        norm = self.normalize_ip_entry(text)
        if not norm:
            QMessageBox.warning(
                self.window(),
                "Ошибка",
                "Не удалось распознать IP или подсеть.\n"
                "Примеры:\n- 1.2.3.4\n- 10.0.0.0/8\nДиапазоны a-b не поддерживаются.",
            )
            return

        # Проверяем дубликат
        current = self.text_edit.toPlainText()
        current_entries = [l.strip().lower() for l in current.split('\n') if l.strip() and not l.strip().startswith('#')]
        
        if norm.lower() in current_entries:
            QMessageBox.information(self.window(), "Информация", f"Запись уже есть:\n{norm}")
            return

        # Добавляем в конец
        if current and not current.endswith('\n'):
            current += '\n'
        current += norm
        
        self.text_edit.setPlainText(current)
        self.input.clear()

    def _clear_all(self):
        text = self.text_edit.toPlainText().strip()
        if not text:
            return
        reply = QMessageBox.question(
            self.window(),
            "Очистить всё",
            "Удалить все записи?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.text_edit.clear()
            log("Все записи my-ipset.txt удалены", "INFO")

    def _open_file(self):
        try:
            from utils.ipsets_manager import MY_IPSET_PATH
            import subprocess

            # Сохраняем перед открытием
            self._save_entries()

            if os.path.exists(MY_IPSET_PATH):
                subprocess.run(["explorer", "/select,", MY_IPSET_PATH])
            else:
                os.makedirs(os.path.dirname(MY_IPSET_PATH), exist_ok=True)
                with open(MY_IPSET_PATH, "w", encoding="utf-8") as f:
                    f.write("# Пользовательские IP-адреса и подсети\n")
                subprocess.run(["explorer", os.path.dirname(MY_IPSET_PATH)])
        except Exception as e:
            log(f"Ошибка открытия my-ipset.txt: {e}", "ERROR")
            QMessageBox.warning(self.window(), "Ошибка", f"Не удалось открыть:\n{e}")
