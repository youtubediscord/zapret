# lists/ui/ipset_page.py
"""Страница управления IP-сетами"""

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QFrame)
from PyQt6.QtGui import QFont

try:
    from qfluentwidgets import StrongBodyLabel, BodyLabel, CaptionLabel, InfoBar, SettingCardGroup
    _HAS_FLUENT_LABELS = True
except ImportError:
    StrongBodyLabel = QLabel; BodyLabel = QLabel; CaptionLabel = QLabel
    InfoBar = None
    SettingCardGroup = None  # type: ignore[assignment]
    _HAS_FLUENT_LABELS = False

from ui.pages.base_page import BasePage
from ui.compat_widgets import SettingsCard, ActionButton, QuickActionsBar, insert_widget_into_setting_card_group, set_tooltip
from ui.theme import get_cached_qta_pixmap, get_theme_tokens
from ui.text_catalog import tr as tr_catalog
from log.log import log



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
        self._actions_group = None
        self._actions_bar = None
        self.open_ipset_btn = None
        self._info_card = None
        self._files_info_state = {
            "text": "",
            "key": "page.ipset.files.loading",
            "default": "Загрузка информации...",
            "kwargs": {},
        }
        self._runtime_initialized = False
        self._cleanup_in_progress = False

        self._build_ui()
        self._apply_page_theme(force=True)
        self._run_runtime_init_once()

    def _run_runtime_init_once(self) -> None:
        if self._runtime_initialized:
            return
        self._runtime_initialized = True
        QTimer.singleShot(0, lambda: (not self._cleanup_in_progress) and self._load_info())

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
        self._actions_card = None
        self._actions_group = SettingCardGroup(
            self._tr("page.ipset.section.actions", "Действия"),
            self.content,
        )
        self._actions_bar = QuickActionsBar(self.content)
        self.open_ipset_btn = ActionButton(
            self._tr("page.ipset.button.open", "Открыть"),
            "fa5s.folder-open",
        )
        self.open_ipset_btn.clicked.connect(self._open_ipset_folder)
        set_tooltip(
            self.open_ipset_btn,
            self._tr(
                "page.ipset.action.open_folder.description",
                "Открыть папку со списками IP и подсетей для ручной проверки и редактирования.",
            ),
        )
        self._actions_bar.add_button(self.open_ipset_btn)
        insert_widget_into_setting_card_group(self._actions_group, 1, self._actions_bar)
        self.layout.addWidget(self._actions_group)
        
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
        
        self.layout.addStretch()

    def _apply_page_theme(self, tokens=None, force: bool = False) -> None:
        _ = force
        tokens = tokens or get_theme_tokens()
        if self._desc_label is not None:
            self._desc_label.setStyleSheet(f"color: {tokens.fg_muted};")
        if self._open_icon_label is not None:
            self._open_icon_label.setPixmap(get_cached_qta_pixmap('fa5s.folder-open', color=tokens.accent_hex, size=18))
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
        if self._actions_group is not None:
            try:
                self._actions_group.titleLabel.setText(self._tr("page.ipset.section.actions", "Действия"))
            except Exception:
                pass
        if self._info_card is not None:
            self._info_card.set_title(self._tr("page.ipset.section.info", "Информация"))
        if hasattr(self, "open_ipset_btn") and self.open_ipset_btn is not None:
            self.open_ipset_btn.setText(self._tr("page.ipset.button.open", "Открыть"))
            set_tooltip(
                self.open_ipset_btn,
                self._tr(
                    "page.ipset.action.open_folder.description",
                    "Открыть папку со списками IP и подсетей для ручной проверки и редактирования.",
                )
            )
        self._render_files_info()

    def _open_ipset_folder(self):
        """Открывает папку IP-сетов"""
        try:
            from lists.core.paths import get_lists_dir

            import os
            os.startfile(get_lists_dir())
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
        if self._cleanup_in_progress:
            return
        try:
            from lists.core.paths import get_lists_dir

            import os
            lists_folder = get_lists_dir()
            
            if not os.path.exists(lists_folder):
                self._set_files_info(
                    key="page.ipset.files.not_found",
                    default="Папка не найдена",
                )
                return
                
            # Ищем файлы с IP
            ipset_files = [f for f in os.listdir(lists_folder) 
                          if f.endswith('.txt') and ('ip' in f.lower() or 'subnet' in f.lower())]
            
            total_ips = 0
            for f in ipset_files[:10]:
                try:
                    path = os.path.join(lists_folder, f)
                    with open(path, 'r', encoding='utf-8', errors='ignore') as file:
                        total_ips += sum(1 for line in file if line.strip() and not line.startswith('#'))
                except:
                    pass
                    
            self._set_files_info(
                key="page.ipset.files.summary",
                default="📁 Папка: {folder}\n📄 IP-файлов: {files_count}\n🌐 Примерно IP/подсетей: {total_ips}",
                folder=lists_folder,
                files_count=len(ipset_files),
                total_ips=f"{total_ips:,}",
            )
        except Exception as e:
            self._set_files_info(
                key="page.ipset.files.error",
                default="Ошибка загрузки информации: {error}",
                error=e,
            )

    def cleanup(self) -> None:
        self._cleanup_in_progress = True
