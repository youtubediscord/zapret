# ui/pages/blobs_page.py
"""Страница управления блобами (Zapret 2 / Direct режим)"""

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QFileDialog, QSizePolicy
)
import qtawesome as qta
import os

from .base_page import BasePage
from ui.compat_widgets import (
    SettingsCard,
    ActionButton,
    PrimaryActionButton,
    QuickActionsBar,
    RefreshButton,
    insert_widget_into_setting_card_group,
    set_tooltip,
)
from ui.theme import get_theme_tokens, get_card_gradient_qss
from ui.theme_refresh import ThemeRefreshController
from ui.text_catalog import tr as tr_catalog
from log import log

try:
    from qfluentwidgets import (
        LineEdit, ComboBox, MessageBox, InfoBar,
        MessageBoxBase, SubtitleLabel, BodyLabel, CaptionLabel,
        TransparentToolButton, TransparentPushButton,
        SettingCardGroup,
    )
    _HAS_FLUENT_INPUTS = True
except ImportError:
    from PyQt6.QtWidgets import (
        QLineEdit as LineEdit, QComboBox as ComboBox,
        QDialog as MessageBoxBase, QPushButton as TransparentToolButton,
        QPushButton as TransparentPushButton,
    )
    MessageBox = None
    InfoBar = None
    SubtitleLabel = QLabel
    BodyLabel = QLabel
    CaptionLabel = QLabel
    SettingCardGroup = None  # type: ignore[assignment]
    _HAS_FLUENT_INPUTS = False


class BlobItemWidget(QFrame):
    """Виджет одного блоба в списке"""
    
    deleted = pyqtSignal(str)  # имя блоба
    
    def __init__(self, name: str, info: dict, parent=None, language: str = "ru"):
        super().__init__(parent)
        self.blob_name = name
        self.blob_info = info
        self._ui_language = language

        self._tokens = get_theme_tokens()
        self._current_qss = ""

        self._icon_label = None
        self._name_label = None
        self._user_badge = None
        self._desc_label = None
        self._value_label = None
        self._status_label = None
        self._delete_btn = None

        # Политика размера: предпочитает минимальную ширину
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self._build_ui()
        self._theme_refresh = ThemeRefreshController(self, self._apply_theme)

    def _tr(self, key: str, default: str, **kwargs) -> str:
        text = tr_catalog(key, language=self._ui_language, default=default)
        if kwargs:
            try:
                return text.format(**kwargs)
            except Exception:
                return text
        return text
        
    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)
        
        # Иконка типа
        self._icon_label = QLabel()
        layout.addWidget(self._icon_label)
        
        # Информация о блобе
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        
        # Имя + метка пользовательского
        name_layout = QHBoxLayout()
        name_layout.setSpacing(6)
        
        self._name_label = QLabel(self.blob_name)
        name_layout.addWidget(self._name_label)
        
        if self.blob_info.get("is_user"):
            self._user_badge = QLabel(self._tr("page.blobs.item.user_badge", "пользовательский"))
            self._user_badge.setStyleSheet("""
                QLabel {
                    color: #ffc107;
                    font-size: 10px;
                    background: rgba(255, 193, 7, 0.15);
                    padding: 2px 6px;
                    border-radius: 3px;
                }
            """)
            name_layout.addWidget(self._user_badge)
        
        name_layout.addStretch()
        info_layout.addLayout(name_layout)
        
        # Описание
        desc = self.blob_info.get("description", "")
        if desc:
            self._desc_label = QLabel(desc)
            self._desc_label.setWordWrap(True)
            info_layout.addWidget(self._desc_label)
        
        # Значение (путь или hex)
        value = self.blob_info.get("value", "")
        if value:
            if value.startswith("@"):
                # Показываем только имя файла для путей
                display_value = os.path.basename(value[1:])
            else:
                display_value = value[:50] + "..." if len(value) > 50 else value
            
            value_label = QLabel(display_value)
            self._value_label = value_label
            info_layout.addWidget(self._value_label)
        
        layout.addLayout(info_layout, 1)
        
        # Статус существования файла
        if self.blob_info.get("type") == "file":
            if self.blob_info.get("exists", True):
                self._status_label = QLabel("✓")
                self._status_label.setStyleSheet("color: #6ccb5f; font-size: 14px;")
                set_tooltip(self._status_label, self._tr("page.blobs.item.file_found", "Файл найден"))
            else:
                self._status_label = QLabel("✗")
                self._status_label.setStyleSheet("color: #ff6b6b; font-size: 14px;")
                set_tooltip(self._status_label, self._tr("page.blobs.item.file_missing", "Файл не найден"))
            layout.addWidget(self._status_label)
        
        # Кнопка удаления (только для пользовательских)
        if self.blob_info.get("is_user"):
            self._delete_btn = TransparentToolButton()
            self._delete_btn.setIcon(qta.icon('fa5s.trash-alt', color='#ff6b6b'))
            self._delete_btn.setFixedSize(28, 28)
            self._delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._delete_btn.clicked.connect(self._on_delete)
            layout.addWidget(self._delete_btn)

        self._apply_theme()

    def refresh_theme(self) -> None:
        self._tokens = get_theme_tokens()
        self._apply_theme()

    def set_ui_language(self, language: str) -> None:
        self._ui_language = language
        if self._user_badge is not None:
            self._user_badge.setText(self._tr("page.blobs.item.user_badge", "пользовательский"))
        if self._status_label is not None:
            if self.blob_info.get("exists", True):
                set_tooltip(self._status_label, self._tr("page.blobs.item.file_found", "Файл найден"))
            else:
                set_tooltip(self._status_label, self._tr("page.blobs.item.file_missing", "Файл не найден"))

    def _apply_theme(self) -> None:
        tokens = self._tokens or get_theme_tokens("Темная синяя")

        qss = f"""
            BlobItemWidget {{
                background: {tokens.surface_bg};
                border: 1px solid {tokens.surface_border};
                border-radius: 6px;
                padding: 8px;
            }}
            BlobItemWidget:hover {{
                background: {tokens.surface_bg_hover};
                border: 1px solid {tokens.surface_border_hover};
            }}
        """
        if qss != self._current_qss:
            self._current_qss = qss
            self.setStyleSheet(qss)

        if self._name_label is not None:
            self._name_label.setStyleSheet(
                f"color: {tokens.fg}; font-size: 13px; font-weight: 600;"
            )
        if self._desc_label is not None:
            self._desc_label.setStyleSheet(
                f"color: {tokens.fg_muted}; font-size: 11px;"
            )
        if self._value_label is not None:
            self._value_label.setStyleSheet(
                f"color: {tokens.fg_faint}; font-size: 10px; font-family: Consolas;"
            )

        if self._icon_label is not None:
            if self.blob_info.get("type") == "hex":
                icon_name = "fa5s.hashtag"
                icon_color = "#ffc107"
            else:
                icon_name = "fa5s.file"
                icon_color = tokens.accent_hex
            try:
                self._icon_label.setPixmap(qta.icon(icon_name, color=icon_color).pixmap(16, 16))
            except Exception:
                self._icon_label.setPixmap(qta.icon("fa5s.file", color=tokens.accent_hex).pixmap(16, 16))
            
    def _on_delete(self):
        """Запрос на удаление блоба"""
        box = MessageBox(
            self._tr("page.blobs.dialog.delete.title", "Удаление блоба"),
            self._tr("page.blobs.dialog.delete.body", "Удалить пользовательский блоб '{name}'?", name=self.blob_name),
            self.window(),
        )
        if box.exec():
            self.deleted.emit(self.blob_name)


class AddBlobDialog(MessageBoxBase):
    """Диалог добавления нового блоба (qfluentwidgets MessageBoxBase)"""

    def __init__(self, parent=None, language: str = "ru"):
        super().__init__(parent)
        self._ui_language = language

        def _tr(key: str, default: str, **kwargs) -> str:
            text = tr_catalog(key, language=self._ui_language, default=default)
            if kwargs:
                try:
                    return text.format(**kwargs)
                except Exception:
                    return text
            return text

        self._tr = _tr

        # Заголовок
        self.titleLabel = SubtitleLabel(self._tr("page.blobs.dialog.add.title", "Добавить блоб"), self.widget)

        # Имя
        name_label = BodyLabel(self._tr("page.blobs.dialog.add.name", "Имя"), self.widget)
        self.name_edit = LineEdit(self.widget)
        self.name_edit.setPlaceholderText(self._tr("page.blobs.dialog.add.name.placeholder", "Латиница, цифры, подчеркивания"))

        # Тип
        type_label = BodyLabel(self._tr("page.blobs.dialog.add.type", "Тип"), self.widget)
        self.type_combo = ComboBox(self.widget)
        self.type_combo.addItem(self._tr("page.blobs.dialog.add.type.file", "Файл (.bin)"), userData="file")
        self.type_combo.addItem(self._tr("page.blobs.dialog.add.type.hex", "Hex значение"), userData="hex")
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)

        # Значение + кнопка обзора
        value_label = BodyLabel(self._tr("page.blobs.dialog.add.value", "Значение"), self.widget)
        self._value_container = QWidget(self.widget)
        value_layout = QHBoxLayout(self._value_container)
        value_layout.setContentsMargins(0, 0, 0, 0)
        value_layout.setSpacing(6)
        self.value_edit = LineEdit(self._value_container)
        self.value_edit.setPlaceholderText(self._tr("page.blobs.dialog.add.value.path_placeholder", "Путь к файлу"))
        value_layout.addWidget(self.value_edit, 1)
        self.browse_btn = TransparentToolButton(self._value_container)
        self.browse_btn.setIcon(qta.icon("fa5s.folder-open", color="#888"))
        self.browse_btn.setFixedSize(32, 32)
        set_tooltip(self.browse_btn, self._tr("page.blobs.dialog.add.browse.tooltip", "Выбрать файл"))
        self.browse_btn.clicked.connect(self._browse_file)
        value_layout.addWidget(self.browse_btn)

        # Описание
        desc_label = BodyLabel(self._tr("page.blobs.dialog.add.description", "Описание (опционально)"), self.widget)
        self.desc_edit = LineEdit(self.widget)
        self.desc_edit.setPlaceholderText(self._tr("page.blobs.dialog.add.description.placeholder", "Краткое описание блоба"))

        # Строка ошибки
        self._error_label = CaptionLabel("", self.widget)
        try:
            from qfluentwidgets import isDarkTheme as _idt
            _err_clr = "#ff6b6b" if _idt() else "#dc2626"
        except Exception:
            _err_clr = "#dc2626"
        self._error_label.setStyleSheet(f"color: {_err_clr};")
        self._error_label.hide()

        # Добавляем всё в viewLayout
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(name_label)
        self.viewLayout.addWidget(self.name_edit)
        self.viewLayout.addWidget(type_label)
        self.viewLayout.addWidget(self.type_combo)
        self.viewLayout.addWidget(value_label)
        self.viewLayout.addWidget(self._value_container)
        self.viewLayout.addWidget(desc_label)
        self.viewLayout.addWidget(self.desc_edit)
        self.viewLayout.addWidget(self._error_label)

        self.yesButton.setText(self._tr("page.blobs.dialog.add.button.add", "Добавить"))
        self.cancelButton.setText(self._tr("page.blobs.dialog.add.button.cancel", "Отмена"))
        self.widget.setMinimumWidth(400)

    def _on_type_changed(self, index):
        """Переключение типа блоба"""
        blob_type = self.type_combo.currentData()
        self.browse_btn.setVisible(blob_type == "file")
        if blob_type == "hex":
            self.value_edit.setPlaceholderText(
                self._tr("page.blobs.dialog.add.value.hex_placeholder", "Hex значение (например: 0x0E0E0F0E)")
            )
        else:
            self.value_edit.setPlaceholderText(
                self._tr("page.blobs.dialog.add.value.path_placeholder_bin", "Путь к .bin файлу")
            )

    def _browse_file(self):
        """Выбор файла"""
        from config import BIN_FOLDER

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self._tr("page.blobs.dialog.add.browse.title", "Выберите файл блоба"),
            BIN_FOLDER,
            "Binary files (*.bin);;All files (*.*)",
        )
        if file_path:
            if file_path.startswith(BIN_FOLDER):
                file_path = os.path.relpath(file_path, BIN_FOLDER)
            self.value_edit.setText(file_path)

    def validate(self) -> bool:
        """Вызывается при нажатии кнопки Добавить — возвращает False чтобы оставить диалог открытым."""
        import re

        name = self.name_edit.text().strip()
        value = self.value_edit.text().strip()

        if not name:
            self._show_error(self._tr("page.blobs.dialog.add.error.name_required", "Введите имя блоба"))
            return False

        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', name):
            self._show_error(
                self._tr(
                    "page.blobs.dialog.add.error.name_invalid",
                    "Имя должно начинаться с буквы и содержать только латиницу, цифры и подчеркивания",
                )
            )
            return False

        if not value:
            self._show_error(self._tr("page.blobs.dialog.add.error.value_required", "Введите значение блоба"))
            return False

        blob_type = self.type_combo.currentData()
        if blob_type == "hex" and not value.startswith("0x"):
            self._show_error(self._tr("page.blobs.dialog.add.error.hex_prefix", "Hex значение должно начинаться с 0x"))
            return False

        return True

    def _show_error(self, msg: str) -> None:
        self._error_label.setText(msg)
        self._error_label.show()

    def get_data(self) -> dict:
        """Возвращает данные нового блоба"""
        return {
            "name": self.name_edit.text().strip(),
            "type": self.type_combo.currentData(),
            "value": self.value_edit.text().strip(),
            "description": self.desc_edit.text().strip(),
        }


class BlobsPage(BasePage):
    """Страница управления блобами"""

    back_clicked = pyqtSignal()  # → PageName.ZAPRET2_DIRECT_CONTROL

    def __init__(self, parent=None):
        super().__init__(
            "Блобы",
            "Управление бинарными данными для стратегий",
            parent,
            title_key="page.blobs.title",
            subtitle_key="page.blobs.subtitle",
        )

        self._desc_label = None
        self._filter_icon_label = None
        self._runtime_initialized = False
        self._actions_group = None
        self._actions_meta_card = None
        self._actions_bar = None

        self._build_ui()
        self._apply_page_theme(force=True)
        self._run_runtime_init_once()

    def _run_runtime_init_once(self) -> None:
        if self._runtime_initialized:
            return
        self._runtime_initialized = True
        QTimer.singleShot(0, self._load_blobs)

    def _tr(self, key: str, default: str, **kwargs) -> str:
        text = tr_catalog(key, language=self._ui_language, default=default)
        if kwargs:
            try:
                return text.format(**kwargs)
            except Exception:
                return text
        return text

    def _build_ui(self):
        """Строит UI страницы"""

        # ── Кнопка «назад» ────────────────────────────────────────────────────
        if _HAS_FLUENT_INPUTS:
            from PyQt6.QtCore import QSize
            back_btn = TransparentPushButton(parent=self)
            back_btn.setText(self._tr("page.blobs.button.back", "Управление"))
            self._back_btn = back_btn
            back_btn.setIcon(qta.icon("fa5s.chevron-left", color="#888"))
            back_btn.setIconSize(QSize(12, 12))
            back_btn.clicked.connect(self.back_clicked.emit)
            back_row_widget = QWidget()
            back_row_layout = QHBoxLayout(back_row_widget)
            back_row_layout.setContentsMargins(0, 0, 0, 0)
            back_row_layout.addWidget(back_btn)
            back_row_layout.addStretch()
            # Insert BEFORE title (index 0) so the button sits at the very top
            self.vBoxLayout.insertWidget(0, back_row_widget)

        # Описание
        desc_card = SettingsCard()
        desc = QLabel(
            self._tr(
                "page.blobs.description",
                "Блобы — это бинарные данные (файлы .bin или hex-значения), используемые в стратегиях для имитации TLS/QUIC пакетов.\nВы можете добавлять свои блобы для кастомных стратегий.",
            )
        )
        self._desc_label = desc
        desc.setWordWrap(True)
        desc_card.add_widget(desc)
        self.layout.addWidget(desc_card)
        
        # Панель действий
        if SettingCardGroup is not None and _HAS_FLUENT_INPUTS:
            actions_group = SettingCardGroup(
                self._tr("page.blobs.section.actions", "Действия"),
                self.content,
            )
            self._actions_group = actions_group
            self._actions_bar = QuickActionsBar(self.content)

            self.add_btn = PrimaryActionButton(
                self._tr("page.blobs.button.add", "Добавить блоб"),
                "fa5s.plus",
            )
            self.add_btn.clicked.connect(self._add_blob)
            set_tooltip(
                self.add_btn,
                self._tr(
                    "page.blobs.action.add.description",
                    "Открыть форму создания нового пользовательского блоба для стратегий.",
                ),
            )

            self.reload_btn = RefreshButton()
            self.reload_btn.clicked.connect(self._reload_blobs)
            set_tooltip(
                self.reload_btn,
                self._tr("page.blobs.button.reload", "Обновить список блобов"),
            )

            self.open_folder_btn = ActionButton(
                self._tr("page.blobs.button.bin_folder", "Папка bin"),
                "fa5s.folder-open",
            )
            self.open_folder_btn.clicked.connect(self._open_bin_folder)
            set_tooltip(
                self.open_folder_btn,
                self._tr(
                    "page.blobs.action.bin_folder.description",
                    "Открыть папку bin с бинарными blob-файлами.",
                ),
            )

            self.open_json_btn = ActionButton(
                self._tr("page.blobs.button.open_json", "Открыть JSON"),
                "fa5s.file-code",
            )
            self.open_json_btn.clicked.connect(self._open_json)
            set_tooltip(
                self.open_json_btn,
                self._tr(
                    "page.blobs.action.open_json.description",
                    "Открыть blobs.json с индексом blob-описаний.",
                ),
            )

            self._actions_bar.add_buttons([self.add_btn, self.reload_btn, self.open_folder_btn, self.open_json_btn])
            insert_widget_into_setting_card_group(actions_group, 1, self._actions_bar)

            meta_card = SettingsCard()
            self._actions_meta_card = meta_card
            self.count_label = QLabel("")
            meta_card.add_widget(self.count_label)
            actions_group.addSettingCard(meta_card)
            self.layout.addWidget(actions_group)
        else:
            actions_card = SettingsCard()
            actions_layout = QHBoxLayout()
            actions_layout.setSpacing(8)
            
            # Кнопка добавления
            self.add_btn = ActionButton(self._tr("page.blobs.button.add", "Добавить блоб"), "fa5s.plus")
            self.add_btn.clicked.connect(self._add_blob)
            actions_layout.addWidget(self.add_btn)
            
            # Кнопка перезагрузки
            self.reload_btn = RefreshButton()
            self.reload_btn.clicked.connect(self._reload_blobs)
            actions_layout.addWidget(self.reload_btn)
            
            # Открыть папку bin
            self.open_folder_btn = ActionButton(self._tr("page.blobs.button.bin_folder", "Папка bin"), "fa5s.folder-open")
            self.open_folder_btn.clicked.connect(self._open_bin_folder)
            actions_layout.addWidget(self.open_folder_btn)
            
            # Открыть JSON
            self.open_json_btn = ActionButton(self._tr("page.blobs.button.open_json", "Открыть JSON"), "fa5s.file-code")
            self.open_json_btn.clicked.connect(self._open_json)
            actions_layout.addWidget(self.open_json_btn)
            
            actions_layout.addStretch()
            actions_card.add_layout(actions_layout)
            
            # Счётчик под кнопками
            self.count_label = QLabel("")
            actions_card.add_widget(self.count_label)
            
            self.layout.addWidget(actions_card)
        
        # Фильтр поиска
        filter_card = SettingsCard()
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(8)
        
        filter_icon = QLabel()
        self._filter_icon_label = filter_icon
        filter_layout.addWidget(filter_icon)
        
        self.filter_edit = LineEdit()
        self.filter_edit.setPlaceholderText(self._tr("page.blobs.filter.placeholder", "Фильтр по имени..."))
        self.filter_edit.textChanged.connect(self._filter_blobs)
        filter_layout.addWidget(self.filter_edit, 1)
        
        filter_card.add_layout(filter_layout)
        self.layout.addWidget(filter_card)
        
        # Контейнер для блобов
        self.blobs_container = QWidget()
        self.blobs_container.setStyleSheet("background: transparent;")
        self.blobs_container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self.blobs_layout = QVBoxLayout(self.blobs_container)
        self.blobs_layout.setContentsMargins(0, 0, 0, 0)
        self.blobs_layout.setSpacing(6)
        
        self.layout.addWidget(self.blobs_container)
        
    def _apply_page_theme(self, tokens=None, force: bool = False) -> None:
        _ = force
        tokens = tokens or get_theme_tokens()

        if self._desc_label is not None:
            self._desc_label.setStyleSheet(
                f"color: {tokens.fg_muted}; font-size: 13px;"
            )

        if hasattr(self, "count_label") and self.count_label is not None:
            self.count_label.setStyleSheet(
                f"color: {tokens.fg_faint}; font-size: 11px; padding-top: 4px;"
            )

        if self._filter_icon_label is not None:
            self._filter_icon_label.setPixmap(
                qta.icon('fa5s.search', color=tokens.fg_faint).pixmap(14, 14)
            )

        # filter_edit is a qfluentwidgets LineEdit — it styles itself.

        # Update section headers + blob items.
        if hasattr(self, "blobs_layout") and self.blobs_layout is not None:
            for i in range(self.blobs_layout.count()):
                item = self.blobs_layout.itemAt(i)
                w = item.widget() if item else None
                if w is None:
                    continue
                if isinstance(w, BlobItemWidget):
                    try:
                        w.refresh_theme()
                    except Exception:
                        pass
                elif isinstance(w, QLabel):
                    section = w.property("blobSection")
                    if section == "user":
                        w.setStyleSheet(
                            "color: #ffc107; font-size: 12px; font-weight: 600; padding: 8px 4px 4px 4px;"
                        )
                    elif section == "system":
                        w.setStyleSheet(
                            f"color: {tokens.fg_faint}; font-size: 12px; font-weight: 600; padding: 12px 4px 4px 4px;"
                        )
                    elif section == "error":
                        w.setStyleSheet("color: #ff6b6b; font-size: 13px;")
        
    def _load_blobs(self):
        """Загружает и отображает список блобов"""
        try:
            from launcher_common.blobs import get_blobs_info
            
            # Очищаем контейнер
            while self.blobs_layout.count():
                item = self.blobs_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            
            blobs_info = get_blobs_info()
            
            # Разделяем на пользовательские и системные
            user_blobs = {k: v for k, v in blobs_info.items() if v.get("is_user")}
            system_blobs = {k: v for k, v in blobs_info.items() if not v.get("is_user")}
            
            # Секция пользовательских блобов
            if user_blobs:
                user_header = QLabel(
                    self._tr("page.blobs.section.user", "★ Пользовательские ({count})", count=len(user_blobs))
                )
                user_header.setProperty("blobSection", "user")
                self.blobs_layout.addWidget(user_header)
                
                for name, info in sorted(user_blobs.items()):
                    item = BlobItemWidget(name, info, language=self._ui_language)
                    item.deleted.connect(self._delete_blob)
                    self.blobs_layout.addWidget(item)
            
            # Секция системных блобов
            if system_blobs:
                system_header = QLabel(
                    self._tr("page.blobs.section.system", "Системные ({count})", count=len(system_blobs))
                )
                system_header.setProperty("blobSection", "system")
                self.blobs_layout.addWidget(system_header)
                
                for name, info in sorted(system_blobs.items()):
                    item = BlobItemWidget(name, info, language=self._ui_language)
                    self.blobs_layout.addWidget(item)
            
            # Обновляем счётчик
            total = len(blobs_info)
            user_count = len(user_blobs)
            self.count_label.setText(
                self._tr("page.blobs.count", "{total} блобов ({user} пользовательских)", total=total, user=user_count)
            )

            # Refresh styles for newly created widgets.
            self._apply_page_theme(force=True)
            
        except Exception as e:
            log(f"Ошибка загрузки блобов: {e}", "ERROR")
            import traceback
            log(traceback.format_exc(), "DEBUG")
            
            error_label = QLabel(
                self._tr("page.blobs.error.load", "❌ Ошибка загрузки: {error}", error=e)
            )
            error_label.setProperty("blobSection", "error")
            self.blobs_layout.addWidget(error_label)

            self._apply_page_theme(force=True)
            
    def _filter_blobs(self, text: str):
        """Фильтрует блобы по тексту"""
        text = text.lower()
        for i in range(self.blobs_layout.count()):
            item = self.blobs_layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                if isinstance(widget, BlobItemWidget):
                    # Показываем если имя или описание содержит текст
                    match = (text in widget.blob_name.lower() or 
                            text in widget.blob_info.get("description", "").lower())
                    widget.setVisible(match)
                elif isinstance(widget, QLabel):
                    # Заголовки секций - показываем всегда
                    pass
                    
    def _add_blob(self):
        """Открывает диалог добавления блоба"""
        dialog = AddBlobDialog(self.window(), language=self._ui_language)
        if dialog.exec():
            data = dialog.get_data()
            try:
                from launcher_common.blobs import save_user_blob

                if save_user_blob(data["name"], data["type"], data["value"], data["description"]):
                    log(f"Добавлен блоб: {data['name']}", "INFO")
                    self._load_blobs()
                else:
                    InfoBar.warning(
                        title=self._tr("common.error.title", "Ошибка"),
                        content=self._tr("page.blobs.error.save", "Не удалось сохранить блоб"),
                        parent=self.window(),
                    )

            except Exception as e:
                log(f"Ошибка добавления блоба: {e}", "ERROR")
                InfoBar.warning(
                    title=self._tr("common.error.title", "Ошибка"),
                    content=self._tr("page.blobs.error.add", "Не удалось добавить блоб: {error}", error=e),
                    parent=self.window(),
                )
                
    def _delete_blob(self, name: str):
        """Удаляет пользовательский блоб"""
        try:
            from launcher_common.blobs import delete_user_blob
            
            if delete_user_blob(name):
                log(f"Удалён блоб: {name}", "INFO")
                self._load_blobs()
            else:
                InfoBar.warning(
                    title=self._tr("common.error.title", "Ошибка"),
                    content=self._tr("page.blobs.error.delete_named", "Не удалось удалить блоб '{name}'", name=name),
                    parent=self.window(),
                )

        except Exception as e:
            log(f"Ошибка удаления блоба: {e}", "ERROR")
            InfoBar.warning(
                title=self._tr("common.error.title", "Ошибка"),
                content=self._tr("page.blobs.error.delete", "Не удалось удалить блоб: {error}", error=e),
                parent=self.window(),
            )
            
    def _reload_blobs(self):
        """Перезагружает блобы из JSON"""
        self.reload_btn.set_loading(True)
        try:
            from launcher_common.blobs import reload_blobs
            reload_blobs()
            self._load_blobs()
            log("Блобы перезагружены", "INFO")
        except Exception as e:
            log(f"Ошибка перезагрузки блобов: {e}", "ERROR")
        finally:
            self.reload_btn.set_loading(False)
            
    def _open_bin_folder(self):
        """Открывает папку bin"""
        try:
            from config import BIN_FOLDER
            os.startfile(BIN_FOLDER)
        except Exception as e:
            log(f"Ошибка открытия папки: {e}", "ERROR")
            InfoBar.warning(
                title=self._tr("common.error.title", "Ошибка"),
                content=self._tr("page.blobs.error.open_folder", "Не удалось открыть папку: {error}", error=e),
                parent=self.window(),
            )
            
    def _open_json(self):
        """Открывает файл blobs.json в редакторе"""
        try:
            from config import INDEXJSON_FOLDER
            json_path = os.path.join(INDEXJSON_FOLDER, "blobs.json")
            os.startfile(json_path)
        except Exception as e:
            log(f"Ошибка открытия JSON: {e}", "ERROR")
            InfoBar.warning(
                title=self._tr("common.error.title", "Ошибка"),
                content=self._tr("page.blobs.error.open_file", "Не удалось открыть файл: {error}", error=e),
                parent=self.window(),
            )

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)

        if hasattr(self, "_back_btn") and self._back_btn is not None:
            self._back_btn.setText(self._tr("page.blobs.button.back", "Управление"))
        if self._desc_label is not None:
            self._desc_label.setText(
                self._tr(
                    "page.blobs.description",
                    "Блобы — это бинарные данные (файлы .bin или hex-значения), используемые в стратегиях для имитации TLS/QUIC пакетов.\nВы можете добавлять свои блобы для кастомных стратегий.",
                )
            )

        try:
            title_label = getattr(getattr(self, "_actions_group", None), "titleLabel", None)
            if title_label is not None:
                title_label.setText(self._tr("page.blobs.section.actions", "Действия"))
        except Exception:
            pass

        self.add_btn.setText(self._tr("page.blobs.button.add", "Добавить блоб"))
        self.open_folder_btn.setText(self._tr("page.blobs.button.bin_folder", "Папка bin"))
        self.open_json_btn.setText(self._tr("page.blobs.button.open_json", "Открыть JSON"))
        set_tooltip(
            self.add_btn,
            self._tr(
                "page.blobs.action.add.description",
                "Открыть форму создания нового пользовательского блоба для стратегий.",
            ),
        )
        set_tooltip(
            self.reload_btn,
            self._tr("page.blobs.button.reload", "Обновить список блобов"),
        )
        set_tooltip(
            self.open_folder_btn,
            self._tr(
                "page.blobs.action.bin_folder.description",
                "Открыть папку bin с бинарными blob-файлами.",
            ),
        )
        set_tooltip(
            self.open_json_btn,
            self._tr(
                "page.blobs.action.open_json.description",
                "Открыть blobs.json с индексом blob-описаний.",
            ),
        )
        self.filter_edit.setPlaceholderText(self._tr("page.blobs.filter.placeholder", "Фильтр по имени..."))

        self._load_blobs()
