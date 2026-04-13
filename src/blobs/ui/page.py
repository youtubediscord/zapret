# blobs/ui/page.py
"""Страница управления блобами (Zapret 2 / Direct режим)"""

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QLabel
)

from ui.pages.base_page import BasePage
from blobs.ui.build import build_blobs_page_header
from blobs.ui.components import BlobItemWidget
from blobs.ui.runtime_helpers import (
    add_blob_via_dialog,
    apply_blobs_language,
    delete_blob_named,
    filter_blobs_in_ui,
    load_blobs_into_ui,
    open_bin_folder_action,
    open_json_action,
    reload_blobs_data,
)
from ui.compat_widgets import (
    ActionButton,
    PrimaryActionButton,
    QuickActionsBar,
    RefreshButton,
)
from ui.theme import get_cached_qta_pixmap, get_theme_tokens
from ui.text_catalog import tr as tr_catalog
from log.log import log


try:
    from qfluentwidgets import (
        LineEdit, MessageBox, InfoBar,
        SettingCardGroup,
    )
    _HAS_FLUENT_INPUTS = True
except ImportError:
    from PyQt6.QtWidgets import (
        QLineEdit as LineEdit,
    )
    MessageBox = None
    InfoBar = None
    SettingCardGroup = None  # type: ignore[assignment]
    _HAS_FLUENT_INPUTS = False


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
        self._cleanup_in_progress = False
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
        QTimer.singleShot(0, lambda: (not self._cleanup_in_progress) and self._load_blobs())

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
        widgets = build_blobs_page_header(
            page=self,
            has_fluent_inputs=_HAS_FLUENT_INPUTS,
            setting_card_group_cls=SettingCardGroup,
            line_edit_cls=LineEdit,
            action_button_cls=ActionButton,
            primary_action_button_cls=PrimaryActionButton,
            quick_actions_bar_cls=QuickActionsBar,
            refresh_button_cls=RefreshButton,
            add_widget=self.add_widget,
            tr_fn=self._tr,
            on_back=self.back_clicked.emit,
            on_add_blob=self._add_blob,
            on_reload_blobs=self._reload_blobs,
            on_open_bin_folder=self._open_bin_folder,
            on_open_json=self._open_json,
            on_filter_blobs=self._filter_blobs,
        )
        self._back_btn = widgets.back_btn
        self._desc_label = widgets.desc_label
        self._actions_group = widgets.actions_group
        self._actions_meta_card = widgets.actions_meta_card
        self._actions_bar = widgets.actions_bar
        self.add_btn = widgets.add_btn
        self.reload_btn = widgets.reload_btn
        self.open_folder_btn = widgets.open_folder_btn
        self.open_json_btn = widgets.open_json_btn
        self.count_label = widgets.count_label
        self._filter_icon_label = widgets.filter_icon_label
        self.filter_edit = widgets.filter_edit
        self.blobs_container = widgets.blobs_container
        self.blobs_layout = widgets.blobs_layout
        
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
                get_cached_qta_pixmap('fa5s.search', color=tokens.fg_faint, size=14)
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
        load_blobs_into_ui(
            cleanup_in_progress=self._cleanup_in_progress,
            blobs_layout=self.blobs_layout,
            ui_language=self._ui_language,
            tr_fn=self._tr,
            on_delete_blob=self._delete_blob,
            count_label=self.count_label,
            apply_page_theme=self._apply_page_theme,
            log_error=lambda text: log(text, "ERROR"),
            log_debug=lambda text: log(text, "DEBUG"),
        )
            
    def _filter_blobs(self, text: str):
        """Фильтрует блобы по тексту"""
        filter_blobs_in_ui(
            cleanup_in_progress=self._cleanup_in_progress,
            blobs_layout=self.blobs_layout,
            text=text,
        )
                    
    def _add_blob(self):
        """Открывает диалог добавления блоба"""
        add_blob_via_dialog(
            window=self.window(),
            ui_language=self._ui_language,
            reload_callback=self._load_blobs,
            tr_fn=self._tr,
            info_bar_cls=InfoBar,
            log_info=lambda text: log(text, "INFO"),
            log_error=lambda text: log(text, "ERROR"),
        )
                
    def _delete_blob(self, name: str):
        """Удаляет пользовательский блоб"""
        delete_blob_named(
            name=name,
            reload_callback=self._load_blobs,
            tr_fn=self._tr,
            info_bar_cls=InfoBar,
            window=self.window(),
            log_info=lambda text: log(text, "INFO"),
            log_error=lambda text: log(text, "ERROR"),
        )
            
    def _reload_blobs(self):
        """Перезагружает блобы из JSON"""
        reload_blobs_data(
            cleanup_in_progress=self._cleanup_in_progress,
            reload_btn=self.reload_btn,
            reload_callback=self._load_blobs,
            log_info=lambda text: log(text, "INFO"),
            log_error=lambda text: log(text, "ERROR"),
        )
            
    def _open_bin_folder(self):
        """Открывает папку bin"""
        open_bin_folder_action(
            tr_fn=self._tr,
            info_bar_cls=InfoBar,
            window=self.window(),
            log_error=lambda text: log(text, "ERROR"),
        )
            
    def _open_json(self):
        """Открывает файл blobs.json в редакторе"""
        open_json_action(
            tr_fn=self._tr,
            info_bar_cls=InfoBar,
            window=self.window(),
            log_error=lambda text: log(text, "ERROR"),
        )

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)
        apply_blobs_language(
            tr_fn=self._tr,
            back_btn=getattr(self, "_back_btn", None),
            desc_label=self._desc_label,
            actions_group=self._actions_group,
            add_btn=self.add_btn,
            reload_btn=self.reload_btn,
            open_folder_btn=self.open_folder_btn,
            open_json_btn=self.open_json_btn,
            filter_edit=self.filter_edit,
            reload_callback=self._load_blobs,
        )

    def cleanup(self) -> None:
        self._cleanup_in_progress = True
