# ui/pages/custom_domains_page.py
"""Страница управления пользовательскими доменами (other2.txt)"""

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, 
    QMessageBox, QLineEdit
)
from urllib.parse import urlparse
import re
import os

from .base_page import BasePage, ScrollBlockingPlainTextEdit
from ui.sidebar import SettingsCard, ActionButton
from log import log

def split_domains(text: str) -> list[str]:
    """
    Разделяет домены по пробелам/запятым и склеенные домены.
    'vk.com youtube.com' -> ['vk.com', 'youtube.com']
    'vk.comyoutube.com' -> ['vk.com', 'youtube.com']

    ВАЖНО: Если домены разделены пробелами, они НЕ считаются склеенными.
    Склеенные - только когда нет пробела: vk.comyoutube.com
    """
    # Сначала разделяем по пробелам, табам, запятым
    parts = re.split(r'[\s,;]+', text)

    result = []
    for part in parts:
        part = part.strip().lower()
        if not part or part.startswith('#'):
            if part:
                result.append(part)
            continue

        # Пробуем разделить склеенные домены ТОЛЬКО если это одна строка без пробелов
        # Если пользователь ввёл "genshin-impact-map.app sample.com" с пробелом,
        # они уже разделены выше и сюда приходят отдельно
        separated = _split_glued_domains(part)
        result.extend(separated)

    return result

def _split_glued_domains(text: str) -> list[str]:
    """
    Разделяет склеенные домены типа vk.comyoutube.com
    Ищем паттерн: домен.TLD + начало нового домена (буквы + точка)

    ВАЖНО: Не разделяем если после TLD идёт часть того же домена.
    Например: genshin-impact-map.appsample.com - это ОДИН домен, не разделяем.
    Разделяем только очевидные случаи типа vk.comyoutube.com
    """
    if not text or len(text) < 5:
        return [text] if text else []

    # Проверяем: если строка выглядит как валидный домен (заканчивается на TLD) - не разделяем
    # Это предотвращает разделение something.appsample.com
    valid_tld_pattern = r'\.(com|ru|org|net|io|me|by|uk|de|fr|it|es|nl|pl|ua|kz|su|co|tv|cc|to|ai|gg|info|biz|xyz|dev|app|pro|online|store|cloud|shop|blog|tech|site|рф)$'
    if re.search(valid_tld_pattern, text, re.IGNORECASE):
        # Строка заканчивается на валидный TLD - это нормальный домен
        # Проверим нет ли ЯВНО склеенных доменов (TLD + домен + TLD)
        # Например: vk.comyoutube.com - есть .com в середине И .com в конце

        # Паттерн: TLD + буквы + точка + что-то + TLD в конце
        # Это поймает vk.comyoutube.com но НЕ поймает genshin-impact-map.appsample.com
        glued_pattern = r'(\.(com|ru|org|net|io|me))([a-z]{2,}[a-z0-9-]*\.[a-z]{2,})$'
        match = re.search(glued_pattern, text, re.IGNORECASE)
        if match:
            # Нашли склеенные домены: первый заканчивается на TLD, второй - полноценный домен
            end_of_first = match.start() + len(match.group(1))
            first_domain = text[:end_of_first]
            second_domain = match.group(3)
            return [first_domain, second_domain]

        # Не нашли склеенных - возвращаем как есть
        return [text]

    # Строка НЕ заканчивается на валидный TLD - возможно мусор, возвращаем как есть
    return [text]


class CustomDomainsPage(BasePage):
    """Страница управления пользовательскими доменами"""
    
    domains_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(
            "Мои домены", 
            "Управление пользовательскими доменами (other2.txt)", 
            parent
        )
        self._build_ui()
        QTimer.singleShot(100, self._load_domains)
        
    def _build_ui(self):
        """Строит UI страницы"""
        
        # Описание
        desc_card = SettingsCard()
        desc = QLabel(
            "Добавляйте свои домены для обхода блокировок. "
            "URL автоматически преобразуются в домены. "
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
        
        self.domain_input = QLineEdit()
        self.domain_input.setPlaceholderText("Введите домен или URL (например: example.com или https://site.com/page)")
        self.domain_input.setStyleSheet("""
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
        self.domain_input.returnPressed.connect(self._add_domain)
        add_layout.addWidget(self.domain_input, 1)
        
        self.add_btn = ActionButton("Добавить", "fa5s.plus", accent=True)
        self.add_btn.setFixedHeight(38)
        self.add_btn.clicked.connect(self._add_domain)
        add_layout.addWidget(self.add_btn)
        
        add_card.add_layout(add_layout)
        self.layout.addWidget(add_card)
        
        # Действия
        actions_card = SettingsCard("Действия")
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(8)
        
        # Открыть файл
        self.open_file_btn = ActionButton("Открыть файл", "fa5s.external-link-alt")
        self.open_file_btn.setFixedHeight(36)
        self.open_file_btn.clicked.connect(self._open_file)
        actions_layout.addWidget(self.open_file_btn)
        
        # Очистить всё
        self.clear_btn = ActionButton("Очистить всё", "fa5s.trash-alt")
        self.clear_btn.setFixedHeight(36)
        self.clear_btn.clicked.connect(self._clear_all)
        actions_layout.addWidget(self.clear_btn)
        
        actions_layout.addStretch()
        actions_card.add_layout(actions_layout)
        self.layout.addWidget(actions_card)
        
        # Текстовый редактор (вместо списка)
        editor_card = SettingsCard("Мои домены (редактор)")
        editor_layout = QVBoxLayout()
        editor_layout.setSpacing(8)
        
        self.text_edit = ScrollBlockingPlainTextEdit()
        self.text_edit.setPlaceholderText(
            "Домены по одному на строку:\n"
            "example.com\n"
            "subdomain.site.org\n\n"
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
        
        # Подсказка
        hint = QLabel("💡 Изменения сохраняются автоматически через 500мс")
        hint.setStyleSheet("color: rgba(255, 255, 255, 0.4); font-size: 11px;")
        editor_layout.addWidget(hint)
        
        editor_card.add_layout(editor_layout)
        self.layout.addWidget(editor_card)
        
        # Статистика
        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-size: 11px;")
        self.layout.addWidget(self.status_label)
        
    def _load_domains(self):
        """Загружает домены из файла"""
        try:
            from config import OTHER2_PATH
            
            domains = []
            
            if os.path.exists(OTHER2_PATH):
                with open(OTHER2_PATH, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            domains.append(line)
            
            # Блокируем сигнал чтобы не срабатывало автосохранение
            self.text_edit.blockSignals(True)
            self.text_edit.setPlainText('\n'.join(domains))
            self.text_edit.blockSignals(False)
            
            self._update_status()
            log(f"Загружено {len(domains)} строк из other2.txt", "INFO")
            
        except Exception as e:
            log(f"Ошибка загрузки доменов: {e}", "ERROR")
            self.status_label.setText(f"❌ Ошибка: {e}")
            
    def _on_text_changed(self):
        """Запускает таймер автосохранения"""
        self._save_timer.start(500)
        self._update_status()
        
    def _auto_save(self):
        """Автосохранение"""
        self._save_domains()
        self.status_label.setText(self.status_label.text() + " • ✅ Сохранено")
        
    def _save_domains(self):
        """Сохраняет домены в файл"""
        try:
            from config import OTHER2_PATH
            os.makedirs(os.path.dirname(OTHER2_PATH), exist_ok=True)
            
            text = self.text_edit.toPlainText()
            domains = []
            normalized_lines = []  # Для обновления UI
            
            for line in text.split('\n'):
                line = line.strip()
                if not line:
                    continue
                if line.startswith('#'):
                    # Сохраняем комментарии как есть
                    domains.append(line)
                    normalized_lines.append(line)
                    continue
                
                # Разделяем склеенные домены (vk.comyoutube.com -> vk.com, youtube.com)
                separated = split_domains(line)
                
                for item in separated:
                    # Нормализуем каждый домен
                    domain = self._extract_domain(item)
                    if domain:
                        if domain not in domains:
                            domains.append(domain)
                            normalized_lines.append(domain)
                    else:
                        # Невалидная строка - оставляем как есть
                        normalized_lines.append(item)
            
            with open(OTHER2_PATH, 'w', encoding='utf-8') as f:
                for domain in domains:
                    f.write(f"{domain}\n")
            
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
            
            log(f"Сохранено {len(domains)} строк в other2.txt", "SUCCESS")
            self.domains_changed.emit()
            
        except Exception as e:
            log(f"Ошибка сохранения доменов: {e}", "ERROR")
            
    def _update_status(self):
        """Обновляет статус"""
        text = self.text_edit.toPlainText()
        lines = [l.strip() for l in text.split('\n') if l.strip() and not l.strip().startswith('#')]
        self.status_label.setText(f"📊 Доменов: {len(lines)}")
        
    def _extract_domain(self, text: str) -> str:
        """Извлекает домен из URL или текста"""
        text = text.strip()
        
        # Убираем точку в начале (.com -> com)
        if text.startswith('.'):
            text = text[1:]
        
        # Если похоже на URL - парсим
        if '://' in text or text.startswith('www.'):
            if not text.startswith(('http://', 'https://')):
                text = 'https://' + text
            try:
                parsed = urlparse(text)
                domain = parsed.netloc or parsed.path.split('/')[0]
                if domain.startswith('www.'):
                    domain = domain[4:]
                domain = domain.split(':')[0]
                if domain.startswith('.'):
                    domain = domain[1:]
                return domain.lower()
            except:
                pass
        
        # Проверяем что это валидный домен
        domain = text.split('/')[0].split(':')[0].lower()
        if domain.startswith('www.'):
            domain = domain[4:]
        if domain.startswith('.'):
            domain = domain[1:]
        
        # Одиночные TLD (com, ru, org) - валидны
        if re.match(r'^[a-z]{2,10}$', domain):
            return domain
        
        # Домен с точкой (example.com)
        if '.' in domain and len(domain) > 3:
            if re.match(r'^[a-z0-9][a-z0-9\-\.]*[a-z0-9]$', domain):
                return domain
        
        return None
        
    def _add_domain(self):
        """Добавляет домен"""
        text = self.domain_input.text().strip()
        if not text:
            return
        
        domain = self._extract_domain(text)
        
        if not domain:
            QMessageBox.warning(
                self.window(), 
                "Ошибка", 
                f"Не удалось распознать домен:\n{text}\n\n"
                "Введите корректный домен (например: example.com)"
            )
            return
        
        # Проверяем дубликат
        current = self.text_edit.toPlainText()
        current_domains = [l.strip().lower() for l in current.split('\n') if l.strip() and not l.strip().startswith('#')]
        
        if domain.lower() in current_domains:
            QMessageBox.information(
                self.window(), 
                "Информация", 
                f"Домен уже добавлен:\n{domain}"
            )
            return
        
        # Добавляем в конец
        if current and not current.endswith('\n'):
            current += '\n'
        current += domain
        
        self.text_edit.setPlainText(current)
        self.domain_input.clear()
        
        log(f"Добавлен домен: {domain}", "SUCCESS")
                
    def _clear_all(self):
        """Очищает все домены"""
        text = self.text_edit.toPlainText().strip()
        if not text:
            return
        
        reply = QMessageBox.question(
            self.window(),
            "Очистить всё",
            "Удалить все домены?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.text_edit.clear()
            log("Все домены удалены", "INFO")
                
    def _open_file(self):
        """Открывает файл в проводнике"""
        try:
            from config import OTHER2_PATH
            import subprocess
            
            # Сначала сохраняем
            self._save_domains()
            
            if os.path.exists(OTHER2_PATH):
                subprocess.run(['explorer', '/select,', OTHER2_PATH])
            else:
                os.makedirs(os.path.dirname(OTHER2_PATH), exist_ok=True)
                with open(OTHER2_PATH, 'w', encoding='utf-8') as f:
                    pass
                subprocess.run(['explorer', os.path.dirname(OTHER2_PATH)])
                
        except Exception as e:
            log(f"Ошибка открытия файла: {e}", "ERROR")
            QMessageBox.warning(self.window(), "Ошибка", f"Не удалось открыть:\n{e}")
