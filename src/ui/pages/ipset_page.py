# ui/pages/ipset_page.py
"""Страница управления IP-сетами"""

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QFrame)
from PyQt6.QtGui import QFont
import qtawesome as qta

try:
    from qfluentwidgets import StrongBodyLabel, BodyLabel, CaptionLabel, InfoBar
    _HAS_FLUENT_LABELS = True
except ImportError:
    StrongBodyLabel = QLabel; BodyLabel = QLabel; CaptionLabel = QLabel
    InfoBar = None
    _HAS_FLUENT_LABELS = False

from .base_page import BasePage
from ui.compat_widgets import SettingsCard, ActionButton
from ui.theme import get_theme_tokens
from ui.text_catalog import tr as tr_catalog
from log import log


class IpsetPage(BasePage):
    """Страница управления IP-сетами"""
    
    def __init__(self, parent=None):
        super().__init__(
            "IPset",
            "Управление IP-адресами и подсетями",
            parent,
            title_key="page.ipset.title",
            subtitle_key="page.ipset.subtitle",
        )
        self._desc_label = None
        self._open_icon_label = None
        self._open_text_label = None
        self._actions_card = None
        self._info_card = None
        self._files_info_state = {
            "text": "",
            "key": "page.ipset.files.loading",
            "default": "Загрузка информации...",
            "kwargs": {},
        }

        self.enable_deferred_ui_build(after_build=self._after_ui_built)

    def _after_ui_built(self) -> None:
        self._apply_page_theme(force=True)

    def _tr(self, key: str, default: str, **kwargs) -> str:
        text = tr_catalog(key, language=self._ui_language, default=default)
        if kwargs:
            try:
                return text.format(**kwargs)
            except Exception:
                return text
        return text

    def _set_files_info(self, *, key: str | None = None, default: str = "", text: str | None = None, **kwargs) -> None:
        if key:
            rendered = self._tr(key, default, **kwargs)
            self._files_info_state = {
                "text": rendered,
                "key": key,
                "default": default,
                "kwargs": dict(kwargs),
            }
            self.files_info_label.setText(rendered)
            return

        rendered_text = text if text is not None else ""
        self._files_info_state = {
            "text": rendered_text,
            "key": None,
            "default": "",
            "kwargs": {},
        }
        self.files_info_label.setText(rendered_text)

    def _render_files_info(self) -> None:
        state = self._files_info_state
        key = state.get("key")
        if key:
            self.files_info_label.setText(
                self._tr(
                    key,
                    state.get("default") or "",
                    **(state.get("kwargs") or {}),
                )
            )
            return
        self.files_info_label.setText(state.get("text") or "")
        
    def _build_ui(self):
        """Строит UI страницы"""
        tokens = get_theme_tokens()
        
        # Описание
        desc_card = SettingsCard()
        desc = CaptionLabel(
            self._tr(
                "page.ipset.description",
                "IP-сеты содержат IP-адреса и подсети для обхода блокировок по IP.\n"
                "Используются когда блокировка происходит на уровне IP-адресов.",
            )
        )
        self._desc_label = desc
        desc.setStyleSheet(f"color: {tokens.fg_muted};")
        desc.setWordWrap(True)
        desc_card.add_widget(desc)
        self.layout.addWidget(desc_card)
        
        # Кнопки действий
        actions_card = SettingsCard(self._tr("page.ipset.section.actions", "Действия"))
        self._actions_card = actions_card
        actions_layout = QVBoxLayout()
        actions_layout.setSpacing(8)
        
        # Открыть папку
        open_row = QWidget()
        open_layout = QHBoxLayout(open_row)
        open_layout.setContentsMargins(0, 0, 0, 0)
        
        open_icon = QLabel()
        self._open_icon_label = open_icon
        open_icon.setPixmap(qta.icon('fa5s.folder-open', color=tokens.accent_hex).pixmap(18, 18))
        open_layout.addWidget(open_icon)
        
        open_text = BodyLabel(self._tr("page.ipset.open_folder.label", "Открыть папку IP-сетов"))
        self._open_text_label = open_text
        open_text.setStyleSheet(f"color: {tokens.fg};")
        open_layout.addWidget(open_text, 1)
        
        self.open_ipset_btn = ActionButton(self._tr("page.ipset.button.open", "Открыть"), "fa5s.external-link-alt")
        self.open_ipset_btn.setFixedHeight(32)
        self.open_ipset_btn.clicked.connect(self._open_ipset_folder)
        open_layout.addWidget(self.open_ipset_btn)
        
        actions_layout.addWidget(open_row)
        
        actions_card.add_layout(actions_layout)
        self.layout.addWidget(actions_card)
        
        # Информация о файлах
        info_card = SettingsCard(self._tr("page.ipset.section.info", "Информация"))
        self._info_card = info_card
        info_layout = QVBoxLayout()
        info_layout.setSpacing(8)
        
        self.files_info_label = CaptionLabel(self._tr("page.ipset.files.loading", "Загрузка информации..."))
        self.files_info_label.setStyleSheet(f"color: {tokens.fg_muted};")
        self.files_info_label.setWordWrap(True)
        info_layout.addWidget(self.files_info_label)
        
        info_card.add_layout(info_layout)
        self.layout.addWidget(info_card)
        
        # Загружаем информацию
        QTimer.singleShot(100, self._load_info)
        
        self.layout.addStretch()

    def _apply_page_theme(self, tokens=None, force: bool = False) -> None:
        _ = force
        tokens = tokens or get_theme_tokens()
        if self._desc_label is not None:
            self._desc_label.setStyleSheet(f"color: {tokens.fg_muted};")
        if self._open_icon_label is not None:
            self._open_icon_label.setPixmap(qta.icon('fa5s.folder-open', color=tokens.accent_hex).pixmap(18, 18))
        if self._open_text_label is not None:
            self._open_text_label.setStyleSheet(f"color: {tokens.fg};")
        if self.files_info_label is not None:
            self.files_info_label.setStyleSheet(f"color: {tokens.fg_muted};")

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)

        if self._desc_label is not None:
            self._desc_label.setText(
                self._tr(
                    "page.ipset.description",
                    "IP-сеты содержат IP-адреса и подсети для обхода блокировок по IP.\n"
                    "Используются когда блокировка происходит на уровне IP-адресов.",
                )
            )
        if self._actions_card is not None:
            self._actions_card.set_title(self._tr("page.ipset.section.actions", "Действия"))
        if self._info_card is not None:
            self._info_card.set_title(self._tr("page.ipset.section.info", "Информация"))
        if self._open_text_label is not None:
            self._open_text_label.setText(self._tr("page.ipset.open_folder.label", "Открыть папку IP-сетов"))
        self.open_ipset_btn.setText(self._tr("page.ipset.button.open", "Открыть"))
        self._render_files_info()

    def _open_ipset_folder(self):
        """Открывает папку IP-сетов"""
        try:
            from config import LISTS_FOLDER
            import os
            os.startfile(LISTS_FOLDER)
        except Exception as e:
            log(f"Ошибка открытия папки: {e}", "ERROR")
            if InfoBar is not None:
                InfoBar.error(
                    title=self._tr("common.error.title", "Ошибка"),
                    content=self._tr(
                        "page.ipset.error.open_folder",
                        "Не удалось открыть папку:\n{error}",
                        error=e,
                    ),
                    parent=self.window(),
                    duration=5000,
                )
            
    def _load_info(self):
        """Загружает информацию о файлах"""
        try:
            from config import LISTS_FOLDER
            import os
            
            if not os.path.exists(LISTS_FOLDER):
                self._set_files_info(
                    key="page.ipset.files.not_found",
                    default="Папка не найдена",
                )
                return
                
            # Ищем файлы с IP
            ipset_files = [f for f in os.listdir(LISTS_FOLDER) 
                          if f.endswith('.txt') and ('ip' in f.lower() or 'subnet' in f.lower())]
            
            total_ips = 0
            for f in ipset_files[:10]:
                try:
                    path = os.path.join(LISTS_FOLDER, f)
                    with open(path, 'r', encoding='utf-8', errors='ignore') as file:
                        total_ips += sum(1 for line in file if line.strip() and not line.startswith('#'))
                except:
                    pass
                    
            self._set_files_info(
                key="page.ipset.files.summary",
                default="📁 Папка: {folder}\n📄 IP-файлов: {files_count}\n🌐 Примерно IP/подсетей: {total_ips}",
                folder=LISTS_FOLDER,
                files_count=len(ipset_files),
                total_ips=f"{total_ips:,}",
            )
            
        except Exception as e:
            self._set_files_info(
                key="page.ipset.files.error",
                default="Ошибка загрузки информации: {error}",
                error=e,
            )
