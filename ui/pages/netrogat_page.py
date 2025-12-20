# ui/pages/netrogat_page.py
"""Страница управления исключениями netrogat.txt"""

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QLineEdit,
)

from .base_page import BasePage, ScrollBlockingPlainTextEdit
from ui.sidebar import SettingsCard, ActionButton
from log import log
from utils.netrogat_manager import (
    load_netrogat,
    save_netrogat,
    add_missing_defaults,
    _normalize_domain,
)
import re

def split_domains(text: str) -> list[str]:
    """Разделяет домены по пробелам и склеенные."""
    parts = re.split(r'[\s,;]+', text)
    result = []
    for part in parts:
        part = part.strip().lower()
        if not part or part.startswith('#'):
            if part:
                result.append(part)
            continue
        separated = _split_glued_domains(part)
        result.extend(separated)
    return result

def _split_glued_domains(text: str) -> list[str]:
    """Разделяет склеенные домены типа vk.comyoutube.com"""
    if not text or len(text) < 5:
        return [text] if text else []
    
    # Паттерн: TLD за которым идёт начало нового домена (буквы + точка)
    pattern = r'(\.(com|ru|org|net|io|me|by|uk|de|fr|it|es|nl|pl|ua|kz|su|co|tv|cc|to|ai|gg|info|biz|xyz|dev|app|pro|online|store|cloud|shop|blog|tech|site|рф))([a-z][a-z0-9-]*\.)'
    
    result = []
    remaining = text
    
    while remaining:
        match = re.search(pattern, remaining, re.IGNORECASE)
        if match:
            end_of_first = match.start() + len(match.group(1))
            first_domain = remaining[:end_of_first]
            result.append(first_domain)
            remaining = remaining[end_of_first:]
        else:
            if remaining:
                result.append(remaining)
            break
    
    return result if result else [text]


class NetrogatPage(BasePage):
    """Страница исключений netrogat.txt"""

    data_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(
            "Исключения",
            "Управление списком исключений netrogat.txt. Изменения сохраняются автоматически.",
            parent,
        )
        self._build_ui()
        QTimer.singleShot(100, self._load)

    def _build_ui(self):
        # Описание
        desc_card = SettingsCard()
        desc = QLabel(
            "Список доменов, которые не следует трогать (netrogat.txt).\n"
            "Изменения сохраняются автоматически. Поддерживается Ctrl+Z."
        )
        desc.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-size: 13px;")
        desc.setWordWrap(True)
        desc_card.add_widget(desc)
        self.layout.addWidget(desc_card)

        # Добавление домена
        add_card = SettingsCard("Добавить домен")
        add_layout = QHBoxLayout()
        add_layout.setSpacing(8)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Например: example.com, site.com или через пробел")
        self.input.setStyleSheet(
            """
            QLineEdit {
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                padding: 10px 12px;
                color: #ffffff;
                font-size: 13px;
            }
            QLineEdit:focus { border: 1px solid #60cdff; }
        """
        )
        self.input.returnPressed.connect(self._add)
        add_layout.addWidget(self.input, 1)

        self.add_btn = ActionButton("Добавить", "fa5s.plus", accent=True)
        self.add_btn.setFixedHeight(38)
        self.add_btn.clicked.connect(self._add)
        add_layout.addWidget(self.add_btn)

        add_card.add_layout(add_layout)
        self.layout.addWidget(add_card)

        # Действия
        actions_card = SettingsCard("Действия")
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(8)

        add_defaults_btn = ActionButton("Добавить недостающие", "fa5s.plus-circle")
        add_defaults_btn.setFixedHeight(36)
        add_defaults_btn.clicked.connect(self._add_missing_defaults)
        actions_layout.addWidget(add_defaults_btn)

        open_btn = ActionButton("Открыть файл", "fa5s.external-link-alt")
        open_btn.setFixedHeight(36)
        open_btn.clicked.connect(self._open_file)
        actions_layout.addWidget(open_btn)

        clear_btn = ActionButton("Очистить всё", "fa5s.trash-alt")
        clear_btn.setFixedHeight(36)
        clear_btn.clicked.connect(self._clear_all)
        actions_layout.addWidget(clear_btn)

        actions_layout.addStretch()
        actions_card.add_layout(actions_layout)
        self.layout.addWidget(actions_card)

        # Текстовый редактор (вместо списка)
        editor_card = SettingsCard("Исключения (редактор)")
        editor_layout = QVBoxLayout()
        editor_layout.setSpacing(8)

        self.text_edit = ScrollBlockingPlainTextEdit()
        self.text_edit.setPlaceholderText(
            "Домены по одному на строку:\n"
            "gosuslugi.ru\n"
            "vk.com\n\n"
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

        editor_card.add_layout(editor_layout)
        self.layout.addWidget(editor_card)

        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-size: 11px;")
        self.layout.addWidget(self.status_label)

    def _load(self):
        domains = load_netrogat()
        # Блокируем сигнал чтобы не срабатывало автосохранение
        self.text_edit.blockSignals(True)
        self.text_edit.setPlainText('\n'.join(domains))
        self.text_edit.blockSignals(False)
        self._update_status()
        log(f"Загружено {len(domains)} доменов netrogat", "INFO")

    def _on_text_changed(self):
        self._save_timer.start(500)
        self._update_status()

    def _auto_save(self):
        self._save()
        self.status_label.setText(self.status_label.text() + " • ✅ Сохранено")

    def _save(self):
        text = self.text_edit.toPlainText()
        domains = []
        normalized_lines = []  # Для обновления UI
        
        for line in text.split('\n'):
            line = line.strip()
            if not line:
                continue
            # Сохраняем комментарии как есть
            if line.startswith('#'):
                domains.append(line)
                normalized_lines.append(line)
                continue
            
            # Разделяем склеенные домены (vk.comyoutube.com -> vk.com, youtube.com)
            separated = split_domains(line)
            
            for item in separated:
                # Нормализуем каждый домен
                norm = _normalize_domain(item)
                if norm:
                    if norm not in domains:
                        domains.append(norm)
                        normalized_lines.append(norm)
                else:
                    # Невалидная строка - оставляем как есть
                    normalized_lines.append(item)
        
        if save_netrogat(domains):
            # Обновляем UI - заменяем URL на домены
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
            
            self.data_changed.emit()

    def _update_status(self):
        text = self.text_edit.toPlainText()
        lines = [l.strip() for l in text.split('\n') if l.strip() and not l.strip().startswith('#')]
        self.status_label.setText(f"📊 Доменов: {len(lines)}")

    def _add(self):
        raw = self.input.text().strip()
        if not raw:
            return

        # Разделяем на несколько доменов
        parts = split_domains(raw)
        if not parts:
            QMessageBox.warning(self.window(), "Ошибка", "Не удалось распознать домен.")
            return

        # Проверяем дубликаты
        current = self.text_edit.toPlainText()
        current_domains = [l.strip().lower() for l in current.split('\n') if l.strip() and not l.strip().startswith('#')]

        added = []
        skipped = []
        invalid = []

        for part in parts:
            if part.startswith('#'):
                continue
            norm = _normalize_domain(part)
            if not norm:
                invalid.append(part)
                continue
            if norm.lower() in current_domains or norm.lower() in [a.lower() for a in added]:
                skipped.append(norm)
                continue
            added.append(norm)

        if not added and not skipped and invalid:
            QMessageBox.warning(self.window(), "Ошибка", "Не удалось распознать домены.")
            return

        if not added and skipped:
            if len(skipped) == 1:
                QMessageBox.information(self.window(), "Информация", f"Домен уже есть:\n{skipped[0]}")
            else:
                QMessageBox.information(self.window(), "Информация", f"Все домены уже есть ({len(skipped)})")
            return

        # Добавляем в конец
        if current and not current.endswith('\n'):
            current += '\n'
        current += '\n'.join(added)

        self.text_edit.setPlainText(current)
        self.input.clear()

        # Показываем результат если были пропущенные
        if skipped:
            QMessageBox.information(
                self.window(),
                "Добавлено",
                f"Добавлено: {len(added)}\nПропущено (дубликаты): {len(skipped)}"
            )

    def _clear_all(self):
        text = self.text_edit.toPlainText().strip()
        if not text:
            return
        reply = QMessageBox.question(
            self.window(),
            "Очистить всё",
            "Удалить все домены?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.text_edit.clear()
            log("Очистили netrogat.txt", "INFO")

    def _open_file(self):
        try:
            from config import NETROGAT_PATH
            import subprocess
            import os

            # Сохраняем перед открытием
            self._save()

            if NETROGAT_PATH and os.path.exists(NETROGAT_PATH):
                subprocess.run(["explorer", "/select,", NETROGAT_PATH])
            else:
                from config import LISTS_FOLDER
                subprocess.run(["explorer", LISTS_FOLDER])
        except Exception as e:
            log(f"Ошибка открытия netrogat.txt: {e}", "ERROR")
            QMessageBox.warning(self.window(), "Ошибка", f"Не удалось открыть:\n{e}")

    def _add_missing_defaults(self):
        # Получаем текущие домены из редактора
        text = self.text_edit.toPlainText()
        current_domains = []
        for line in text.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                norm = _normalize_domain(line)
                if norm:
                    current_domains.append(norm)
        
        new_domains, added = add_missing_defaults(current_domains)
        if added == 0:
            QMessageBox.information(self.window(), "Готово", "Все домены по умолчанию уже есть.")
            return
        
        # Обновляем редактор
        self.text_edit.blockSignals(True)
        self.text_edit.setPlainText('\n'.join(new_domains))
        self.text_edit.blockSignals(False)
        
        self._save()
        self._update_status()
        QMessageBox.information(self.window(), "Готово", f"Добавлено доменов: {added}")
