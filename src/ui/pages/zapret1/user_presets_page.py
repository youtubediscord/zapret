# ui/pages/zapret2/user_presets_page.py
"""Zapret 2 Direct: user presets management."""

from __future__ import annotations

import json
import time
import re
from typing import Optional

from PyQt6.QtCore import (
    Qt,
    pyqtSignal,
    QSize,
    QTimer,
    QFileSystemWatcher,
    QAbstractListModel,
    QModelIndex,
    QRect,
    QEvent,
    QPoint,
    QMimeData,
)
from PyQt6.QtGui import QAction, QColor, QPainter, QFontMetrics, QMouseEvent, QHelpEvent, QTransform, QDrag
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QFileDialog,
    QListView,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QStyle,
    QToolTip,
    QSizePolicy,
    QApplication,
    QFrame,
)
from PyQt6.QtGui import QCursor
import qtawesome as qta

from ui.pages.base_page import BasePage
from ui.pages.preset_actions_menu import show_preset_actions_menu
from ui.pages.preset_rating_menu import show_preset_rating_menu
from core.services import get_preset_store_v1, get_user_presets_runtime_service
from core.runtime.user_presets_runtime_service import UserPresetsRuntimeAdapter
from ui.pages.direct_user_presets_page_controller import (
    DirectUserPresetsPageController,
    DirectUserPresetsPageControllerConfig,
)
from ui.compat_widgets import (
    ActionButton,
    PrimaryActionButton,
    SettingsCard,
    LineEdit,
    set_tooltip,
    style_semantic_caption_label,
)
from ui.main_window_state import MainWindowStateStore
from ui.text_catalog import tr as tr_catalog

try:
    from qfluentwidgets import (
        BodyLabel, CaptionLabel, StrongBodyLabel, SubtitleLabel,
        PushButton as FluentPushButton, PrimaryPushButton, ToolButton, PrimaryToolButton,
        MessageBox, InfoBar, MessageBoxBase, TransparentToolButton, TransparentPushButton, FluentIcon,
        RoundMenu, Action, ListView,
    )
    _HAS_FLUENT_LABELS = True
except ImportError:
    BodyLabel = QLabel
    CaptionLabel = QLabel
    StrongBodyLabel = QLabel
    SubtitleLabel = QLabel
    FluentPushButton = QPushButton
    PrimaryPushButton = QPushButton
    ToolButton = QPushButton
    PrimaryToolButton = QPushButton
    TransparentPushButton = QPushButton
    MessageBox = None
    InfoBar = None
    MessageBoxBase = object
    TransparentToolButton = None
    FluentIcon = None
    RoundMenu = None
    Action = None
    ListView = QListView
    _HAS_FLUENT_LABELS = False


from ui.theme import get_theme_tokens
from ui.theme_semantic import get_semantic_palette
from log import log


_icon_cache: dict[str, object] = {}
_DEFAULT_PRESET_ICON_COLOR = "#5caee8"
_HEX_COLOR_RGB_RE = re.compile(r"^#(?:[0-9a-fA-F]{6})$")
_HEX_COLOR_RGBA_RE = re.compile(r"^#(?:[0-9a-fA-F]{8})$")
_CSS_RGBA_COLOR_RE = re.compile(
    r"^\s*rgba?\(\s*([0-9]{1,3})\s*,\s*([0-9]{1,3})\s*,\s*([0-9]{1,3})\s*(?:,\s*([0-9]*\.?[0-9]+)\s*)?\)\s*$",
    re.IGNORECASE,
)
def _tr_text(key: str, language: str, default: str, **kwargs) -> str:
    text = tr_catalog(key, language=language, default=default)
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text


from ui.pages.user_presets_components import (
    UserPresetsToolbarLayout,
    _PresetListModel,
    _LinkedWheelListView,
    _PresetListDelegate,
    _fluent_icon,
    _make_menu_action,
)

class _CreatePresetDialog(MessageBoxBase):
    """Диалог создания нового пресета."""

    def __init__(self, existing_names: list, parent=None, language: str = "ru"):
        if parent and not parent.isWindow():
            parent = parent.window()
        super().__init__(parent)
        self._ui_language = language

        def _tr(key: str, default: str, **kwargs) -> str:
            return _tr_text(key, self._ui_language, default, **kwargs)

        self._tr = _tr
        self._existing_names = list(existing_names)
        self._source = "current"

        self.titleLabel = SubtitleLabel(
            self._tr("page.z1_user_presets.dialog.create.title", "Новый пресет"),
            self.widget,
        )
        self.subtitleLabel = BodyLabel(
            self._tr(
                "page.z1_user_presets.dialog.create.subtitle",
                "Сохраните текущие настройки как отдельный пресет, чтобы быстро переключаться между конфигурациями.",
            ),
            self.widget,
        )
        self.subtitleLabel.setWordWrap(True)

        name_label = BodyLabel(
            self._tr("page.z1_user_presets.dialog.create.name", "Название"),
            self.widget,
        )
        self.nameEdit = LineEdit(self.widget)
        self.nameEdit.setPlaceholderText(
            self._tr(
                "page.z1_user_presets.dialog.create.placeholder",
                "Например: Игры / YouTube / Дом",
            )
        )
        self.nameEdit.setClearButtonEnabled(True)

        source_row = QHBoxLayout()
        source_label = BodyLabel(
            self._tr("page.z1_user_presets.dialog.create.source", "Создать на основе"),
            self.widget,
        )
        source_row.addWidget(source_label)
        source_row.addStretch()
        try:
            from qfluentwidgets import SegmentedWidget
            self._source_seg = SegmentedWidget(self.widget)
            self._source_seg.addItem(
                "current",
                self._tr("page.z1_user_presets.dialog.create.source.current", "Текущего активного"),
            )
            self._source_seg.addItem(
                "empty",
                self._tr("page.z1_user_presets.dialog.create.source.empty", "Пустого"),
            )
            self._source_seg.setCurrentItem("current")
            self._source_seg.currentItemChanged.connect(lambda k: setattr(self, "_source", k))
            source_row.addWidget(self._source_seg)
        except Exception:
            pass

        self.warningLabel = CaptionLabel("", self.widget)
        style_semantic_caption_label(self.warningLabel, tone="error")
        self.warningLabel.hide()

        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.subtitleLabel)
        self.viewLayout.addWidget(name_label)
        self.viewLayout.addWidget(self.nameEdit)
        self.viewLayout.addLayout(source_row)
        self.viewLayout.addWidget(self.warningLabel)

        self.yesButton.setText(self._tr("page.z1_user_presets.dialog.create.button.create", "Создать"))
        self.cancelButton.setText(self._tr("page.z1_user_presets.dialog.button.cancel", "Отмена"))
        self.widget.setMinimumWidth(420)

    def validate(self) -> bool:
        name = self.nameEdit.text().strip()
        if not name:
            self.warningLabel.setText(
                self._tr("page.z1_user_presets.dialog.validation.enter_name", "Введите название.")
            )
            self.warningLabel.show()
            return False
        self.warningLabel.hide()
        return True


class _RenamePresetDialog(MessageBoxBase):
    """Диалог переименования пресета."""

    def __init__(self, current_name: str, existing_names: list, parent=None, language: str = "ru"):
        if parent and not parent.isWindow():
            parent = parent.window()
        super().__init__(parent)
        self._ui_language = language

        def _tr(key: str, default: str, **kwargs) -> str:
            return _tr_text(key, self._ui_language, default, **kwargs)

        self._tr = _tr
        self._current_name = str(current_name or "")
        self._existing_names = [n for n in existing_names if n != self._current_name]

        self.titleLabel = SubtitleLabel(
            self._tr("page.z1_user_presets.dialog.rename.title", "Переименовать"),
            self.widget,
        )
        self.subtitleLabel = BodyLabel(
            self._tr(
                "page.z1_user_presets.dialog.rename.subtitle",
                "Имя пресета отображается в списке и используется для переключения.",
            ),
            self.widget,
        )
        self.subtitleLabel.setWordWrap(True)

        from_label = CaptionLabel(
            self._tr(
                "page.z1_user_presets.dialog.rename.current_name",
                "Текущее имя: {name}",
                name=self._current_name,
            ),
            self.widget,
        )
        name_label = BodyLabel(
            self._tr("page.z1_user_presets.dialog.rename.new_name", "Новое имя"),
            self.widget,
        )
        self.nameEdit = LineEdit(self.widget)
        self.nameEdit.setText(self._current_name)
        self.nameEdit.setPlaceholderText(
            self._tr("page.z1_user_presets.dialog.rename.placeholder", "Новое имя...")
        )
        self.nameEdit.selectAll()
        self.nameEdit.setClearButtonEnabled(True)

        self.warningLabel = CaptionLabel("", self.widget)
        style_semantic_caption_label(self.warningLabel, tone="error")
        self.warningLabel.hide()

        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.subtitleLabel)
        self.viewLayout.addWidget(from_label)
        self.viewLayout.addWidget(name_label)
        self.viewLayout.addWidget(self.nameEdit)
        self.viewLayout.addWidget(self.warningLabel)

        self.yesButton.setText(self._tr("page.z1_user_presets.dialog.rename.button", "Переименовать"))
        self.cancelButton.setText(self._tr("page.z1_user_presets.dialog.button.cancel", "Отмена"))
        self.widget.setMinimumWidth(420)

    def validate(self) -> bool:
        name = self.nameEdit.text().strip()
        if not name:
            self.warningLabel.setText(
                self._tr("page.z1_user_presets.dialog.validation.enter_name", "Введите название.")
            )
            self.warningLabel.show()
            return False
        if name == self._current_name:
            self.warningLabel.hide()
            return True
        self.warningLabel.hide()
        return True


class _ResetAllPresetsDialog(MessageBoxBase):
    """Диалог подтверждения перезаписи пресетов из шаблонов."""

    def __init__(self, parent=None, language: str = "ru"):
        if parent and not parent.isWindow():
            parent = parent.window()
        super().__init__(parent)
        self._ui_language = language
        self.titleLabel = SubtitleLabel(
            _tr_text(
                "page.z1_user_presets.dialog.reset_all.title",
                self._ui_language,
                "Вернуть заводские пресеты",
            ),
            self.widget,
        )
        self.bodyLabel = BodyLabel(
            _tr_text(
                "page.z1_user_presets.dialog.reset_all.body",
                self._ui_language,
                "Стандартные пресеты будут восстановлены как после установки.\n"
                "Ваши изменения в стандартных пресетах будут потеряны.\n"
                "Пользовательские пресеты с другими именами останутся.\n"
                "Текущий активный пресет будет применен заново автоматически.",
            ),
            self.widget,
        )
        self.bodyLabel.setWordWrap(True)
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.bodyLabel)
        self.yesButton.setText(
            _tr_text(
                "page.z1_user_presets.dialog.reset_all.button",
                self._ui_language,
                "Вернуть заводские",
            )
        )
        self.cancelButton.setText(
            _tr_text("page.z1_user_presets.dialog.button.cancel", self._ui_language, "Отмена")
        )
        self.widget.setMinimumWidth(380)


class Zapret1UserPresetsPage(BasePage):
    preset_open_requested = pyqtSignal(str)  # file_name
    back_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(
            "Мои пресеты",
            "",
            parent,
            title_key="page.z1_user_presets.title",
        )
        self._page_api = DirectUserPresetsPageController(
            DirectUserPresetsPageControllerConfig(
                launch_method="direct_zapret1",
                selection_key="winws1",
                hierarchy_scope="preset_zapret1",
                empty_not_found_key="page.z1_user_presets.empty.not_found",
                empty_none_key="page.z1_user_presets.empty.none",
                list_log_prefix="Z1UserPresetsPage",
                activate_error_level="warning",
                activate_error_mode="friendly",
                copy_hierarchy_meta_on_duplicate=True,
                get_preset_store=get_preset_store_v1,
            )
        ).build_page_api()
        self._runtime_service = get_user_presets_runtime_service("preset_zapret1")
        self._runtime_service.attach_page(self, self._build_runtime_adapter())

        self._back_btn = None
        self._configs_title_label = None
        self._get_configs_btn = None

        # Back navigation (breadcrumb — to Zapret1DirectControlPage)
        try:
            tokens = get_theme_tokens()
            _back_btn = TransparentPushButton()
            _back_btn.setText(self._tr("page.z1_user_presets.back.control", "Управление"))
            _back_btn.setIcon(qta.icon("fa5s.chevron-left", color=tokens.fg_muted))
            _back_btn.setIconSize(QSize(12, 12))
            _back_btn.clicked.connect(self.back_clicked.emit)
            self._back_btn = _back_btn
            _back_row_layout = QHBoxLayout()
            _back_row_layout.setContentsMargins(0, 0, 0, 0)
            _back_row_layout.setSpacing(0)
            _back_row_layout.addWidget(_back_btn)
            _back_row_layout.addStretch()
            _back_row_widget = QWidget()
            _back_row_widget.setLayout(_back_row_layout)
            self.layout.insertWidget(0, _back_row_widget)
        except Exception:
            pass

        self._presets_model: Optional[_PresetListModel] = None
        self._presets_delegate: Optional[_PresetListDelegate] = None
        self._last_page_theme_key: tuple[str, str, str] | None = None

        self._bulk_reset_running = False
        self._layout_resync_timer = QTimer(self)
        self._layout_resync_timer.setSingleShot(True)
        self._layout_resync_timer.timeout.connect(self._resync_layout_metrics)
        self._layout_resync_delayed_timer = QTimer(self)
        self._layout_resync_delayed_timer.setSingleShot(True)
        self._layout_resync_delayed_timer.timeout.connect(self._resync_layout_metrics)

        self._preset_search_timer = QTimer(self)
        self._preset_search_timer.setSingleShot(True)
        self._preset_search_timer.timeout.connect(self._apply_preset_search)
        self._preset_search_input: Optional[QLineEdit] = None
        self._toolbar_layout: Optional[UserPresetsToolbarLayout] = None

        self._ui_state_store: Optional[MainWindowStateStore] = None
        self._ui_state_unsubscribe = None
        self._build_ui()
        self._after_ui_built()

    def _tr(self, key: str, default: str, **kwargs) -> str:
        return _tr_text(key, self._ui_language, default, **kwargs)

    def _build_runtime_adapter(self) -> UserPresetsRuntimeAdapter:
        return UserPresetsRuntimeAdapter(
            bulk_reset_running=lambda: bool(self._bulk_reset_running),
            read_single_metadata=self._listing_api().read_single_preset_list_metadata_light,
            selected_source_file_name=self._listing_api().get_selected_source_preset_file_name_light,
            presets_dir=self._listing_api().get_presets_dir_light,
            load_all_metadata=self._listing_api().load_preset_list_metadata_light,
            rebuild_rows=lambda all_presets, started_at=None: self._rebuild_presets_rows(
                all_presets,
                started_at=started_at,
            ),
            delete_preset_meta=lambda name: self._get_hierarchy_store().delete_preset_meta(
                name,
                display_name=self._resolve_display_name(name),
            ),
        )

    def _on_store_changed(self):
        self._runtime_service.on_store_changed()

    def _on_store_updated(self, file_name_or_name: str):
        self._runtime_service.on_store_updated(file_name_or_name)

    def _on_store_switched(self, _name: str):
        self._runtime_service.on_store_switched(_name)

    def _on_ui_state_changed(self, state: AppUiState, changed_fields: frozenset[str]) -> None:
        self._runtime_service.on_ui_state_changed(state, changed_fields)

    def _controller_api(self):
        return self._page_api

    def _listing_api(self):
        return self._controller_api().listing

    def _actions_api(self):
        return self._controller_api().actions

    def _storage_api(self):
        return self._controller_api().storage

    def _list_preset_entries_light(self) -> list[dict[str, object]]:
        return self._listing_api().list_preset_entries_light()

    def _get_selected_source_preset_file_name_light(self) -> str:
        return self._listing_api().get_selected_source_preset_file_name_light()

    def _load_preset_list_metadata_light(self) -> dict[str, dict[str, object]]:
        return self._listing_api().load_preset_list_metadata_light()

    def _get_presets_dir_light(self):
        return self._listing_api().get_presets_dir_light()

    def _read_single_preset_list_metadata_light(self, file_name_or_name: str) -> tuple[str, dict[str, object]] | None:
        return self._listing_api().read_single_preset_list_metadata_light(file_name_or_name)

    def _resolve_display_name(self, reference: str) -> str:
        return self._listing_api().resolve_display_name(reference)

    def _get_preset_store(self):
        return self._storage_api().get_preset_store()

    def _is_builtin_preset_file(self, name: str) -> bool:
        return self._storage_api().is_builtin_preset_file_with_cache(
            name,
            self._runtime_service.cached_presets_metadata(),
        )

    def _hierarchy_scope_key(self) -> str:
        return "preset_zapret1"

    def _get_hierarchy_store(self):
        return self._storage_api().get_hierarchy_store()

    def on_page_activated(self, first_show: bool) -> None:
        _ = first_show
        self._resync_layout_metrics()
        if self._runtime_service.is_ui_dirty():
            self.refresh_presets_view_if_possible()
        else:
            self._update_presets_view_height()
        self._schedule_layout_resync(include_delayed=True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._resync_layout_metrics()
        self._schedule_layout_resync()

    def on_page_hidden(self) -> None:
        self._layout_resync_timer.stop()
        self._layout_resync_delayed_timer.stop()

    def _after_ui_built(self) -> None:
        started_at = time.perf_counter()
        self._apply_page_theme(force=True)

        try:
            store = self._get_preset_store()
            store.presets_changed.connect(self._on_store_changed)
            store.preset_switched.connect(self._on_store_switched)
            store.preset_updated.connect(self._on_store_updated)
        except Exception:
            pass
        try:
            self._start_watching_presets()
        except Exception:
            pass

        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        log(f"Z1UserPresetsPage: lazy ui init {elapsed_ms}ms", "DEBUG")

    def bind_ui_state_store(self, store: MainWindowStateStore) -> None:
        if self._ui_state_store is store:
            return

        unsubscribe = getattr(self, "_ui_state_unsubscribe", None)
        if callable(unsubscribe):
            try:
                unsubscribe()
            except Exception:
                pass

        self._ui_state_store = store
        self._ui_state_unsubscribe = store.subscribe(
            self._on_ui_state_changed,
            fields={"preset_structure_revision"},
            emit_initial=False,
        )

    def _schedule_layout_resync(self, include_delayed: bool = False):
        self._layout_resync_timer.start(0)
        if include_delayed:
            self._layout_resync_delayed_timer.start(220)

    def _resync_layout_metrics(self):
        toolbar_layout = getattr(self, "_toolbar_layout", None)
        if toolbar_layout is not None:
            toolbar_layout.refresh_for_viewport(self.viewport().width(), self.layout.contentsMargins())
        self._update_presets_view_height()

    def set_smooth_scroll_enabled(self, enabled: bool) -> None:
        list_widget = getattr(self, "presets_list", None)
        delegate = getattr(list_widget, "scrollDelegate", None)
        if delegate is None:
            return
        try:
            from qfluentwidgets.common.smooth_scroll import SmoothMode
            mode = SmoothMode.COSINE if enabled else SmoothMode.NO_SMOOTH

            if hasattr(delegate, "useAni"):
                if not hasattr(delegate, "_zapret_base_use_ani"):
                    delegate._zapret_base_use_ani = bool(delegate.useAni)
                delegate.useAni = bool(delegate._zapret_base_use_ani) if enabled else False

            for smooth_attr in ("verticalSmoothScroll", "horizonSmoothScroll"):
                smooth = getattr(delegate, smooth_attr, None)
                smooth_setter = getattr(smooth, "setSmoothMode", None)
                if callable(smooth_setter):
                    smooth_setter(mode)

            setter = getattr(delegate, "setSmoothMode", None)
            if callable(setter):
                try:
                    setter(mode)
                except TypeError:
                    setter(mode, Qt.Orientation.Vertical)
            elif hasattr(delegate, "smoothMode"):
                delegate.smoothMode = mode
        except Exception:
            pass

    def _start_watching_presets(self):
        self._runtime_service.start_watching_presets()

    def _build_ui(self):
        tokens = get_theme_tokens()
        semantic = get_semantic_palette(tokens.theme_name)

        # This page should scroll only inside the presets list.
        # The outer BasePage scroll creates a second scrollbar and makes wheel
        # scrolling jump between two containers.
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.verticalScrollBar().hide()

        # Presets community link
        configs_card = SettingsCard()
        configs_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        configs_layout = QHBoxLayout()
        configs_layout.setSpacing(12)
        self._configs_icon = QLabel()
        self._configs_icon.setPixmap(qta.icon("fa5b.github", color=tokens.accent_hex).pixmap(18, 18))
        configs_layout.addWidget(self._configs_icon)
        configs_title = StrongBodyLabel(
            self._tr(
                "page.z1_user_presets.configs.title",
                "Обменивайтесь пресетами и категориями в разделе GitHub Discussions",
            )
        )
        self._configs_title_label = configs_title
        configs_title.setWordWrap(True)
        configs_title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        configs_title.setMinimumWidth(0)
        configs_layout.addWidget(configs_title, 1)
        get_configs_btn = PrimaryActionButton(
            self._tr("page.z1_user_presets.configs.button", "Получить конфиги"),
            "fa5s.external-link-alt",
        )
        self._get_configs_btn = get_configs_btn
        get_configs_btn.setFixedHeight(36)
        get_configs_btn.clicked.connect(self._open_new_configs_post)
        configs_layout.addWidget(get_configs_btn)
        configs_card.add_layout(configs_layout)
        self.add_widget(configs_card)

        # Buttons: create + import (above the preset list)
        self.add_spacing(12)
        toolbar_layout = UserPresetsToolbarLayout(self)
        self._toolbar_layout = toolbar_layout

        # "Restore deleted presets" button
        self._restore_deleted_btn = toolbar_layout.create_action_button(
            self._tr("page.z1_user_presets.button.restore_deleted", "Восстановить удалённые пресеты"),
            "fa5s.undo",
        )
        self._restore_deleted_btn.clicked.connect(self._on_restore_deleted)
        self._restore_deleted_btn.setVisible(False)

        self.create_btn = toolbar_layout.create_primary_tool_button(
            PrimaryToolButton,
            FluentIcon.ADD if FluentIcon else None,
        )
        set_tooltip(
            self.create_btn,
            self._tr("page.z1_user_presets.tooltip.create", "Создать новый пресет"),
        )
        self.create_btn.clicked.connect(self._on_create_clicked)

        self.import_btn = toolbar_layout.create_action_button(
            self._tr("page.z1_user_presets.button.import", "Импорт"),
            "fa5s.file-import",
        )
        set_tooltip(
            self.import_btn,
            self._tr("page.z1_user_presets.tooltip.import", "Импорт пресета из файла"),
        )
        self.import_btn.clicked.connect(self._on_import_clicked)

        self.reset_all_btn = toolbar_layout.create_action_button(
            self._tr("page.z1_user_presets.button.reset_all", "Вернуть заводские"),
            "fa5s.undo",
        )
        set_tooltip(
            self.reset_all_btn,
            self._tr(
                "page.z1_user_presets.tooltip.reset_all",
                "Восстанавливает стандартные пресеты. Ваши изменения в стандартных пресетах будут потеряны.",
            ),
        )
        self.reset_all_btn.clicked.connect(self._on_reset_all_presets_clicked)

        self.presets_info_btn = toolbar_layout.create_action_button(
            self._tr("page.z1_user_presets.button.wiki", "Вики по пресетам"),
            "fa5s.info-circle",
        )
        self.presets_info_btn.clicked.connect(self._open_presets_info)

        self.info_btn = toolbar_layout.create_action_button(
            self._tr("page.z1_user_presets.button.what_is_this", "Что это такое?"),
            "fa5s.question-circle",
        )
        self.info_btn.clicked.connect(self._on_info_clicked)

        toolbar_layout.set_buttons([
            self.create_btn,
            self.import_btn,
            self._restore_deleted_btn,
            self.reset_all_btn,
            self.presets_info_btn,
            self.info_btn,
        ])
        toolbar_layout.refresh_for_viewport(self.viewport().width(), self.layout.contentsMargins())
        self.add_widget(toolbar_layout.container)

        self.add_spacing(4)

        # Search presets by name (filters the list).
        self._preset_search_input = LineEdit()
        self._preset_search_input.setPlaceholderText(
            self._tr("page.z1_user_presets.search.placeholder", "Поиск пресетов по имени...")
        )
        self._preset_search_input.setClearButtonEnabled(True)
        self._preset_search_input.setFixedHeight(34)
        self._preset_search_input.setProperty("noDrag", True)
        self._preset_search_input.textChanged.connect(self._on_preset_search_text_changed)
        self.add_widget(self._preset_search_input)

        self.presets_list = _LinkedWheelListView(self, draggable_kinds={"preset", "folder"})
        self.presets_list.setObjectName("userPresetsList")
        self.presets_list.setMouseTracking(True)
        self.presets_list.setSelectionMode(QListView.SelectionMode.SingleSelection)
        self.presets_list.setEditTriggers(QListView.EditTrigger.NoEditTriggers)
        self.presets_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.presets_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.presets_list.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.presets_list.setUniformItemSizes(False)
        self.presets_list.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.presets_list.setProperty("uiList", True)
        self.presets_list.setProperty("noDrag", True)
        self.presets_list.viewport().setProperty("noDrag", True)
        self.presets_list.preset_activated.connect(self._on_activate_preset)
        self.presets_list.preset_move_requested.connect(self._move_preset_by_step)
        self.presets_list.item_dropped.connect(self._on_item_dropped)
        self.presets_list.preset_context_requested.connect(self._on_preset_context_requested)
        self.presets_list.setDragEnabled(True)
        self.presets_list.setAcceptDrops(True)
        self.presets_list.setDropIndicatorShown(True)
        self.presets_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.presets_list.setDragDropMode(QListView.DragDropMode.DragDrop)

        self._presets_model = _PresetListModel(self.presets_list)
        self._presets_delegate = _PresetListDelegate(self.presets_list, language_scope="z1", help_name_role="file_name")
        self._presets_delegate.set_ui_language(self._ui_language)
        self._presets_delegate.action_triggered.connect(self._on_preset_list_action)
        self.presets_list.setModel(self._presets_model)
        self.presets_list.setItemDelegate(self._presets_delegate)
        self.presets_list.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.presets_list.setFrameShape(QFrame.Shape.NoFrame)
        self.presets_list.verticalScrollBar().setSingleStep(28)
        try:
            from config.reg import get_smooth_scroll_enabled
            smooth_enabled = get_smooth_scroll_enabled()
            self.set_smooth_scroll_enabled(smooth_enabled)
        except Exception:
            pass
        self.add_widget(self.presets_list)

        # Make outer page scrolling feel less sluggish on long lists.
        self.verticalScrollBar().setSingleStep(48)

    def _on_info_clicked(self) -> None:
        if MessageBox:
            box = MessageBox(
                self._tr("page.z1_user_presets.info.title", "Что это такое?"),
                self._tr(
                    "page.z1_user_presets.info.body",
                    'Здесь кнопка для нубов — "хочу чтобы нажал и всё работало". '
                    "Выбираете любой пресет — тыкаете — перезагружаете вкладку и смотрите, "
                    "что ресурс открывается (или не открывается). Если не открывается — тыкаете на следующий пресет. "
                    "Также здесь можно создавать, импортировать, экспортировать и переключать пользовательские пресеты.",
                ),
                self.window(),
            )
            box.cancelButton.hide()
            box.exec()

    def _apply_page_theme(self, tokens=None, force: bool = False) -> None:
        try:
            tokens = tokens or get_theme_tokens()
            theme_key = (str(tokens.theme_name), str(tokens.accent_hex), str(tokens.surface_bg))
            if not force and theme_key == self._last_page_theme_key:
                return

            semantic = get_semantic_palette(tokens.theme_name)

            if getattr(self, "_configs_icon", None) is not None:
                self._configs_icon.setPixmap(qta.icon("fa5b.github", color=tokens.accent_hex).pixmap(18, 18))

            # _restore_deleted_btn is ActionButton — self-styling, skip explicit update

            # create_btn is PrimaryToolButton — self-styling, skip explicit update
            # import_btn / presets_info_btn are ActionButton — self-styling, skip explicit update

            if getattr(self, "reset_all_btn", None) is not None:
                try:
                    self.reset_all_btn.setIcon(qta.icon("fa5s.undo", color=tokens.fg))
                except Exception:
                    pass

            if getattr(self, "presets_list", None) is not None:
                self.presets_list.viewport().update()

            self._last_page_theme_key = theme_key
            self._schedule_layout_resync()

        except Exception as e:
            log(f"Ошибка применения темы на странице пресетов: {e}", "DEBUG")

    def _on_preset_search_text_changed(self, _text: str) -> None:
        # Debounce to avoid reloading on every keystroke.
        try:
            self._preset_search_timer.start(180)
        except Exception:
            self._refresh_presets_view_from_cache()

    def _apply_preset_search(self) -> None:
        if not self.isVisible():
            self._runtime_service.set_ui_dirty(True)
            return
        self._refresh_presets_view_from_cache()

    def _update_presets_view_height(self):
        if not self._presets_model or not hasattr(self, "presets_list"):
            return

        viewport_height = self.viewport().height()
        if viewport_height <= 0:
            return

        top = max(0, self.presets_list.geometry().top())
        bottom_margin = self.layout.contentsMargins().bottom()
        target_height = max(220, viewport_height - top - bottom_margin)

        if self.presets_list.minimumHeight() != target_height:
            self.presets_list.setMinimumHeight(target_height)
        if self.presets_list.maximumHeight() != target_height:
            self.presets_list.setMaximumHeight(target_height)

    def _show_inline_action_create(self):
        dlg = _CreatePresetDialog([], self.window(), language=self._ui_language)
        if not dlg.exec():
            return

        name = dlg.nameEdit.text().strip()
        from_current = getattr(dlg, "_source", "current") == "current"

        try:
            result = self._actions_api().create_preset(name=name, from_current=from_current)
            if result.structure_changed:
                self._runtime_service.mark_presets_structure_changed()
            log(result.log_message, result.log_level)
        except Exception as e:
            log(f"Ошибка создания пресета: {e}", "ERROR")
            InfoBar.error(
                title=self._tr("common.error.title", "Ошибка"),
                content=self._tr("page.z1_user_presets.error.generic", "Ошибка: {error}", error=e),
                parent=self.window(),
            )

    def _show_inline_action_rename(self, current_name: str):
        display_name = self._resolve_display_name(current_name)
        if self._is_builtin_preset_file(current_name):
            InfoBar.warning(
                title=self._tr("common.error.title", "Ошибка"),
                content="Встроенный пресет нельзя переименовать. Можно создать копию и работать уже с ней.",
                parent=self.window(),
            )
            return
        dlg = _RenamePresetDialog(display_name, [], self.window(), language=self._ui_language)
        if not dlg.exec():
            return

        new_name = dlg.nameEdit.text().strip()
        if not new_name or new_name == display_name:
            return

        try:
            result = self._actions_api().rename_preset(current_name=current_name, new_name=new_name)
            if result.structure_changed:
                self._runtime_service.mark_presets_structure_changed()
            log(result.log_message, result.log_level)
        except Exception as e:
            log(f"Ошибка переименования пресета: {e}", "ERROR")
            InfoBar.error(
                title=self._tr("common.error.title", "Ошибка"),
                content=self._tr("page.z1_user_presets.error.generic", "Ошибка: {error}", error=e),
                parent=self.window(),
            )

    def _on_create_clicked(self):
        self._show_inline_action_create()

    def _on_import_clicked(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self._tr("page.z1_user_presets.file_dialog.import_title", "Импортировать пресет"),
            "",
            "Preset files (*.txt);;All files (*.*)",
        )

        if not file_path:
            return

        try:
            result = self._actions_api().import_preset_from_file(file_path=file_path)
            if result.structure_changed:
                self._runtime_service.mark_presets_structure_changed()
            log(result.log_message, result.log_level)
            if result.infobar_level == "warning":
                InfoBar.warning(title=result.infobar_title, content=result.infobar_content, parent=self.window())
            else:
                InfoBar.success(title=result.infobar_title, content=result.infobar_content, parent=self.window())

        except Exception as e:
            log(f"Ошибка импорта пресета: {e}", "ERROR")
            InfoBar.error(
                title=self._tr("common.error.title", "Ошибка"),
                content=self._tr("page.z1_user_presets.error.import_exception", "Ошибка импорта: {error}", error=e),
                parent=self.window(),
            )

    def _on_reset_all_presets_clicked(self):
        dlg = _ResetAllPresetsDialog(self.window(), language=self._ui_language)
        if not dlg.exec():
            return

        self._bulk_reset_running = True
        try:
            result = self._actions_api().reset_all_presets()
            if result.structure_changed:
                self._runtime_service.mark_presets_structure_changed()
            log(result.log_message, result.log_level)
            self._show_reset_all_result(result.success_count, result.total_count)

        except Exception as e:
            log(f"Ошибка массового восстановления пресетов: {e}", "ERROR")
            InfoBar.error(
                title=self._tr("common.error.title", "Ошибка"),
                content=self._tr(
                    "page.z1_user_presets.error.reset_all_exception",
                    "Ошибка восстановления пресетов: {error}",
                    error=e,
                ),
                parent=self.window(),
            )
        finally:
            self._bulk_reset_running = False
            if self._runtime_service.is_ui_dirty() and self.isVisible():
                self.refresh_presets_view_if_possible()

    def _show_reset_all_result(self, success_count: int, total_count: int) -> None:
        total = int(total_count or 0)
        ok = int(success_count or 0)
        try:
            self.reset_all_btn.setText(f"{ok}/{total}")
            icon_name = "fa5s.check" if total > 0 and ok >= total else "fa5s.exclamation-triangle"
            self.reset_all_btn.setIcon(qta.icon(icon_name, color=get_theme_tokens().fg))
        except Exception:
            pass
        QTimer.singleShot(3000, self._restore_reset_all_button_label)

    def _restore_reset_all_button_label(self) -> None:
        try:
            self.reset_all_btn.setText(
                self._tr("page.z1_user_presets.button.reset_all", "Вернуть заводские")
            )
            self.reset_all_btn.setIcon(qta.icon("fa5s.undo", color=get_theme_tokens().fg))
        except Exception:
            pass

    def _load_presets(self):
        self._runtime_service.load_presets()

    def refresh_presets_view_if_possible(self) -> None:
        self._runtime_service.refresh_presets_view_if_possible()

    def _refresh_presets_view_from_cache(self) -> None:
        self._runtime_service.refresh_presets_view_from_cache()

    def _rebuild_presets_rows(self, all_presets: dict[str, dict[str, object]], *, started_at: float | None = None) -> None:
        try:
            view_state = self._runtime_service.capture_presets_view_state() if hasattr(self, "presets_list") else {}
            active_file_name = self._get_selected_source_preset_file_name_light()
            plan = self._listing_api().build_preset_rows_plan(
                all_presets=all_presets,
                query=self._runtime_service.current_search_query(),
                active_file_name=active_file_name,
                language=self._ui_language,
            )

            if self._presets_delegate:
                self._presets_delegate.reset_interaction_state()
            if self._presets_model:
                self._presets_model.set_rows(plan.rows)
            self._runtime_service.ensure_preset_list_current_index()
            if view_state:
                self._runtime_service.restore_presets_view_state(view_state)

            # Update restore-deleted button visibility
            self._restore_deleted_btn.setVisible(self._storage_api().has_deleted_presets())

            self._update_presets_view_height()
            self._schedule_layout_resync()
            if started_at is not None:
                elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                log(
                    f"Z1UserPresetsPage: lightweight list reload {elapsed_ms}ms ({plan.total_presets} presets)",
                    "DEBUG",
                )

        except Exception as e:
            log(f"Ошибка загрузки пресетов: {e}", "ERROR")

    def _on_preset_list_action(self, action: str, name: str):
        handlers = {
            "activate": self._on_activate_preset,
            "open": self._open_preset_subpage,
            "pin": self._on_toggle_pin_preset,
            "rating": self._on_rate_preset,
            "move_up": lambda preset_name: self._move_preset_by_step(preset_name, -1),
            "move_down": lambda preset_name: self._move_preset_by_step(preset_name, 1),
            "edit": self._on_edit_preset,
            "rename": self._on_rename_preset,
            "duplicate": self._on_duplicate_preset,
            "reset": self._on_reset_preset,
            "delete": self._on_delete_preset,
            "export": self._on_export_preset,
        }
        handler = handlers.get(action)
        if handler:
            handler(name)

    def _open_preset_subpage(self, name: str):
        self.preset_open_requested.emit(name)

    def _on_preset_context_requested(self, name: str, global_pos: QPoint):
        self._on_edit_preset(name, global_pos=global_pos)

    def _on_toggle_pin_preset(self, name: str):
        try:
            display_name = self._resolve_display_name(name)
            pinned = self._storage_api().toggle_preset_pin(name, display_name)
            log(f"Пресет '{display_name}' {'закреплён' if pinned else 'откреплён'}", "INFO")
            self._refresh_presets_view_from_cache()
        except Exception as e:
            log(f"Ошибка закрепления пресета: {e}", "ERROR")

    def _on_rate_preset(self, name: str):
        self._show_rating_menu(name)

    def _move_preset_by_step(self, name: str, direction: int):
        try:
            moved = self._storage_api().move_preset_by_step(
                name,
                direction,
                cached_metadata=self._runtime_service.cached_presets_metadata(),
            )
            if moved:
                self._refresh_presets_view_from_cache()
        except Exception as e:
            log(f"Ошибка перестановки пресета: {e}", "ERROR")

    def _on_item_dropped(self, source_kind: str, source_id: str, target_kind: str, target_id: str):
        try:
            moved = self._storage_api().move_preset_on_drop(
                source_kind=source_kind,
                source_id=source_id,
                target_kind=target_kind,
                target_id=target_id,
                cached_metadata=self._runtime_service.cached_presets_metadata(),
            )
            if moved:
                self._refresh_presets_view_from_cache()
        except Exception as e:
            log(f"Ошибка перетаскивания элемента: {e}", "ERROR")

    def _on_activate_preset(self, name: str):
        display_name = self._resolve_display_name(name)
        result = self._actions_api().activate_preset(file_name=name, display_name=display_name)
        log(result.log_message, result.log_level)
        if result.ok and result.activated_file_name:
            self._runtime_service.apply_active_preset_marker_for_target(result.activated_file_name)
            return

        if result.infobar_level == "warning":
            InfoBar.warning(
                title=result.infobar_title or self._tr("common.error.title", "Ошибка"),
                content=result.infobar_content,
                parent=self.window(),
            )

    def _on_edit_preset(self, name: str, global_pos: QPoint | None = None):
        is_builtin = self._is_builtin_preset_file(name)
        chosen = show_preset_actions_menu(
            self,
            global_pos=global_pos,
            is_builtin=is_builtin,
            labels={
                "open": self._tr("page.z1_user_presets.menu.open", "Открыть"),
                "rating": self._tr("page.z1_user_presets.menu.rating", "Рейтинг"),
                "move_up": self._tr("page.z1_user_presets.menu.move_up", "Переместить выше"),
                "move_down": self._tr("page.z1_user_presets.menu.move_down", "Переместить ниже"),
                "rename": self._tr("page.z1_user_presets.menu.rename", "Переименовать"),
                "duplicate": self._tr("page.z1_user_presets.menu.duplicate", "Дублировать"),
                "export": self._tr("page.z1_user_presets.menu.export", "Экспорт"),
                "reset": self._tr("page.z1_user_presets.menu.reset", "Сбросить"),
                "delete": self._tr("page.z1_user_presets.menu.delete", "Удалить"),
            },
            make_menu_action=_make_menu_action,
            icon_resolver=_fluent_icon,
            round_menu_cls=RoundMenu if RoundMenu is not None and Action is not None else None,
        )
        if chosen:
            self._on_preset_list_action(chosen, name)

    def _show_rating_menu(self, name: str, global_pos: QPoint | None = None):
        display_name = self._resolve_display_name(name)
        show_preset_rating_menu(
            self,
            preset_file_name=name,
            display_name=display_name,
            hierarchy_store=self._get_hierarchy_store(),
            refresh_callback=lambda: self._refresh_presets_view_from_cache(),
            clear_label=self._tr("page.z1_user_presets.menu.rating_clear", "Сбросить рейтинг"),
            global_pos=global_pos,
        )

    def _on_rename_preset(self, name: str):
        if self._is_builtin_preset_file(name):
            InfoBar.warning(
                title=self._tr("common.error.title", "Ошибка"),
                content="Встроенный пресет нельзя переименовать. Создайте копию, если нужен свой вариант.",
                parent=self.window(),
            )
            return
        self._show_inline_action_rename(name)

    def _on_duplicate_preset(self, name: str):
        try:
            display_name = self._resolve_display_name(name)
            result = self._actions_api().duplicate_preset(file_name=name, display_name=display_name)
            if result.structure_changed:
                self._runtime_service.mark_presets_structure_changed()
            log(result.log_message, result.log_level)

        except Exception as e:
            log(f"Ошибка дублирования пресета: {e}", "ERROR")
            InfoBar.error(
                title=self._tr("common.error.title", "Ошибка"),
                content=self._tr("page.z1_user_presets.error.generic", "Ошибка: {error}", error=e),
                parent=self.window(),
            )

    def _on_reset_preset(self, name: str):
        try:
            display_name = self._resolve_display_name(name)
            if MessageBox:
                box = MessageBox(
                    self._tr("page.z1_user_presets.dialog.reset_single.title", "Сбросить пресет?"),
                    self._tr(
                        "page.z1_user_presets.dialog.reset_single.body",
                        "Пресет '{name}' будет перезаписан данными из шаблона.\n"
                        "Все изменения в этом пресете будут потеряны.\n"
                        "Этот пресет станет активным и будет применен заново.",
                        name=display_name,
                    ),
                    self.window(),
                )
                box.yesButton.setText(
                    self._tr("page.z1_user_presets.dialog.reset_single.button", "Сбросить")
                )
                box.cancelButton.setText(
                    self._tr("page.z1_user_presets.dialog.button.cancel", "Отмена")
                )
                if not box.exec():
                    return

            result = self._actions_api().reset_preset_to_template(file_name=name, display_name=display_name)
            log(result.log_message, result.log_level)

        except Exception as e:
            log(f"Ошибка сброса пресета: {e}", "ERROR")
            InfoBar.error(
                title=self._tr("common.error.title", "Ошибка"),
                content=self._tr("page.z1_user_presets.error.generic", "Ошибка: {error}", error=e),
                parent=self.window(),
            )

    def _on_delete_preset(self, name: str):
        try:
            display_name = self._resolve_display_name(name)
            if self._storage_api().is_builtin_preset_file(name):
                result = self._actions_api().delete_preset(file_name=name, display_name=display_name)
                if result.infobar_level == "warning":
                    InfoBar.warning(
                        title=self._tr("common.error.title", "Ошибка"),
                        content=result.infobar_content,
                        parent=self.window(),
                    )
                return
            if MessageBox:
                box = MessageBox(
                    self._tr("page.z1_user_presets.dialog.delete_single.title", "Удалить пресет?"),
                    self._tr(
                        "page.z1_user_presets.dialog.delete_single.body",
                        "Пресет '{name}' будет удален из списка пользовательских пресетов.\n"
                        "Изменения в этом пресете будут потеряны.\n"
                        "Вернуть его можно только через восстановление удаленных пресетов (если доступен шаблон).",
                        name=display_name,
                    ),
                    self.window(),
                )
                box.yesButton.setText(
                    self._tr("page.z1_user_presets.dialog.delete_single.button", "Удалить")
                )
                box.cancelButton.setText(
                    self._tr("page.z1_user_presets.dialog.button.cancel", "Отмена")
                )
                if not box.exec():
                    return

            result = self._actions_api().delete_preset(file_name=name, display_name=display_name)
            if result.error_code == "not_found":
                log(result.log_message, result.log_level)
                self._runtime_service.recover_missing_deleted_preset(name)
                return
            if result.structure_changed:
                self._runtime_service.mark_presets_structure_changed()
            log(result.log_message, result.log_level)

        except Exception as e:
            log(f"Ошибка удаления пресета: {e}", "ERROR")
            InfoBar.error(
                title=self._tr("common.error.title", "Ошибка"),
                content=self._tr("page.z1_user_presets.error.generic", "Ошибка: {error}", error=e),
                parent=self.window(),
            )

    def _on_export_preset(self, name: str):
        display_name = self._resolve_display_name(name)
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self._tr("page.z1_user_presets.file_dialog.export_title", "Экспортировать пресет"),
            f"{display_name}.txt",
            "Preset files (*.txt);;All files (*.*)",
        )

        if not file_path:
            return

        try:
            result = self._actions_api().export_preset(file_name=name, file_path=file_path, display_name=display_name)
            log(result.log_message, result.log_level)
            if result.infobar_level == "success":
                InfoBar.success(title=result.infobar_title, content=result.infobar_content, parent=self.window())

        except Exception as e:
            log(f"Ошибка экспорта пресета: {e}", "ERROR")
            InfoBar.error(
                title=self._tr("common.error.title", "Ошибка"),
                content=self._tr("page.z1_user_presets.error.generic", "Ошибка: {error}", error=e),
                parent=self.window(),
            )

    def _on_restore_deleted(self):
        """Restore all previously deleted presets that have matching templates."""
        try:
            result = self._actions_api().restore_deleted_presets()
            if result.structure_changed:
                self._runtime_service.mark_presets_structure_changed()
            log(result.log_message, result.log_level)
        except Exception as e:
            log(f"Ошибка восстановления удалённых пресетов: {e}", "ERROR")
            InfoBar.error(
                title=self._tr("common.error.title", "Ошибка"),
                content=self._tr(
                    "page.z1_user_presets.error.restore_deleted",
                    "Ошибка восстановления: {error}",
                    error=e,
                ),
                parent=self.window(),
            )

    def _on_dpi_reload_needed(self):
        try:
            from dpi.direct_runtime_apply_policy import request_direct_runtime_content_apply
            parent_app = getattr(self, "parent_app", None)
            if parent_app is not None:
                request_direct_runtime_content_apply(
                    parent_app,
                    launch_method="direct_zapret1",
                    reason="user_preset_saved",
                )
        except Exception as e:
            log(f"Ошибка перезапуска DPI: {e}", "ERROR")

    def _open_presets_info(self):
        """Открывает страницу с информацией о пресетах."""
        result = self._actions_api().open_presets_info()
        log(result.log_message, result.log_level)
        if (not result.ok) and result.infobar_level == "warning":
            InfoBar.warning(
                title=result.infobar_title or self._tr("common.error.title", "Ошибка"),
                content=result.infobar_content,
                parent=self.window(),
            )

    def _open_new_configs_post(self):
        result = self._actions_api().open_new_configs_post()
        log(result.log_message, result.log_level)
        if (not result.ok) and result.infobar_level == "warning":
            InfoBar.warning(
                title=result.infobar_title or self._tr("common.error.title", "Ошибка"),
                content=result.infobar_content,
                parent=self.window(),
            )

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)

        if self._back_btn is not None:
            self._back_btn.setText(self._tr("page.z1_user_presets.back.control", "Управление"))

        if self._configs_title_label is not None:
            self._configs_title_label.setText(
                self._tr(
                    "page.z1_user_presets.configs.title",
                    "Обменивайтесь пресетами и категориями в разделе GitHub Discussions",
                )
            )
        if self._get_configs_btn is not None:
            self._get_configs_btn.setText(self._tr("page.z1_user_presets.configs.button", "Получить конфиги"))

        if self._restore_deleted_btn is not None:
            self._restore_deleted_btn.setText(
                self._tr("page.z1_user_presets.button.restore_deleted", "Восстановить удалённые пресеты")
            )

        if self.create_btn is not None:
            set_tooltip(self.create_btn, self._tr("page.z1_user_presets.tooltip.create", "Создать новый пресет"))

        if self.import_btn is not None:
            self.import_btn.setText(self._tr("page.z1_user_presets.button.import", "Импорт"))
            set_tooltip(self.import_btn, self._tr("page.z1_user_presets.tooltip.import", "Импорт пресета из файла"))
        if self.reset_all_btn is not None:
            current_text = self.reset_all_btn.text() or ""
            if "/" not in current_text:
                self.reset_all_btn.setText(self._tr("page.z1_user_presets.button.reset_all", "Вернуть заводские"))
            set_tooltip(
                self.reset_all_btn,
                self._tr(
                    "page.z1_user_presets.tooltip.reset_all",
                    "Восстанавливает стандартные пресеты. Ваши изменения в стандартных пресетах будут потеряны.",
                ),
            )

        if self.presets_info_btn is not None:
            self.presets_info_btn.setText(self._tr("page.z1_user_presets.button.wiki", "Вики по пресетам"))
        if self.info_btn is not None:
            self.info_btn.setText(self._tr("page.z1_user_presets.button.what_is_this", "Что это такое?"))

        if self._preset_search_input is not None:
            self._preset_search_input.setPlaceholderText(
                self._tr("page.z1_user_presets.search.placeholder", "Поиск пресетов по имени...")
            )

        if self._presets_delegate is not None:
            self._presets_delegate.set_ui_language(self._ui_language)

        toolbar_layout = getattr(self, "_toolbar_layout", None)
        if toolbar_layout is not None:
            toolbar_layout.refresh_for_viewport(self.viewport().width(), self.layout.contentsMargins())
        self._refresh_presets_view_from_cache()
