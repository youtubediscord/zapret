from __future__ import annotations

from dataclasses import replace

from PyQt6.QtCore import QModelIndex, QRect, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFontMetrics, QPainter
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QAbstractScrollArea,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from log.log import log
from profile.match_filters import filter_values
from profile.editable_settings import normalize_filter_value
from profile.ui.profile_setup_controls import (
    range_expression_from_controls,
    set_combo_by_data,
    set_range_controls,
    sync_range_value_enabled,
)
from profile.setup_controller import ProfileSetupController
from profile.strategy_visuals import describe_strategy_visual
from profile.strategy_state import ProfileStrategyState
from profile.ui.user_profile_dialog import CreateUserProfileDialog
from qfluentwidgets import (
    BodyLabel,
    BreadcrumbBar,
    CaptionLabel,
    CheckBox,
    ComboBox,
    InfoBar,
    LineEdit,
    MessageBox,
    PlainTextEdit,
    FluentIcon,
    SearchLineEdit,
    SegmentedWidget,
    PushButton,
)
from settings.mode import ZAPRET1_MODE, ZAPRET2_MODE, is_preset_launch_method, is_zapret2_launch_method
from ui.pages.base_page import BasePage
from ui.fluent_widgets import set_tooltip
from app.ui_texts import tr as tr_catalog
from ui.theme import get_cached_qta_pixmap, get_theme_tokens, to_qcolor
from ui.widgets.fluent_item_tooltip import FluentItemToolTipController
from ui.widgets.fluent_scrollbar import install_fluent_scrollbars
from ui.widgets.hover_row import paint_profile_hover_row, profile_hover_row_rect


class ProfileStrategyListDelegate(QStyledItemDelegate):
    """Рисует готовые стратегии как единый текстовый список."""

    def __init__(self, view: QListWidget):
        super().__init__(view)
        self._tooltip = FluentItemToolTipController(view.viewport())

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        tokens = get_theme_tokens()
        rect = profile_hover_row_rect(option.rect)
        is_active = bool(index.data(ProfileStrategyListWidget._ROLE_IS_ACTIVE))
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)

        paint_profile_hover_row(
            painter,
            rect,
            active=is_active,
            hovered=hovered,
            selected=selected,
        )

        left = rect.left() + (24 if is_active else 18)
        right = rect.right() - 16
        status = str(index.data(ProfileStrategyListWidget._ROLE_STATUS_TEXT) or "")
        icon_name = str(index.data(ProfileStrategyListWidget._ROLE_VISUAL_ICON_NAME) or "")
        visual_color = str(index.data(ProfileStrategyListWidget._ROLE_VISUAL_COLOR) or "")
        visual_label = str(index.data(ProfileStrategyListWidget._ROLE_VISUAL_LABEL_TEXT) or "")
        status_rect = QRect()

        font = painter.font()
        font.setBold(False)
        painter.setFont(font)
        metrics = QFontMetrics(font)

        if status:
            status_width = min(metrics.horizontalAdvance(status) + 18, max(0, rect.width() // 2))
            status_rect = QRect(right - status_width, rect.center().y() - 10, status_width, 20)
            right = status_rect.left() - 12

        icon_size = 14
        if icon_name:
            icon_rect = QRect(left, rect.center().y() - icon_size // 2, icon_size, icon_size)
            pixmap = get_cached_qta_pixmap(icon_name, color=visual_color or tokens.fg_faint, size=icon_size)
            if not pixmap.isNull():
                painter.drawPixmap(icon_rect, pixmap)
            else:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(to_qcolor(visual_color or tokens.fg_faint, "#aeb5c1"))
                painter.drawEllipse(icon_rect)
            left = icon_rect.right() + 10

        visual_rect = QRect()
        if visual_label:
            visual_width = min(metrics.horizontalAdvance(visual_label) + 4, max(0, rect.width() // 3))
            visual_rect = QRect(max(left, right - visual_width), rect.top(), visual_width, rect.height())
            right = visual_rect.left() - 12

        name = str(index.data(ProfileStrategyListWidget._ROLE_NAME_TEXT) or "")
        name_rect = QRect(left, rect.top(), max(0, right - left), rect.height())
        painter.setPen(to_qcolor(tokens.fg, "#f5f5f5"))
        painter.drawText(
            name_rect,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            metrics.elidedText(name, Qt.TextElideMode.ElideRight, name_rect.width()),
        )

        if visual_rect.width() > 0:
            painter.setPen(to_qcolor(visual_color or tokens.fg_faint, "#aeb5c1"))
            painter.drawText(
                visual_rect,
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                metrics.elidedText(visual_label, Qt.TextElideMode.ElideRight, visual_rect.width()),
            )

        if status_rect.width() > 0:
            if is_active:
                badge_bg = to_qcolor(tokens.accent_soft_bg_hover, tokens.accent_hex)
                badge_fg = to_qcolor(tokens.accent_hex, "#5caee8")
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(badge_bg)
                painter.drawRoundedRect(status_rect, 9, 9)
                painter.setPen(badge_fg)
            else:
                painter.setPen(to_qcolor(tokens.fg_faint, "#aeb5c1"))
            painter.drawText(
                status_rect,
                int(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter),
                metrics.elidedText(status, Qt.TextElideMode.ElideRight, max(0, status_rect.width() - 10)),
            )

        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        _ = (option, index)
        return QSize(0, 31)

    def helpEvent(self, event, view, option, index: QModelIndex) -> bool:  # noqa: N802
        _ = (view, option)
        text = str(index.data(ProfileStrategyListWidget._ROLE_TOOLTIP_TEXT) or "").strip()
        if not text:
            self._tooltip.hide()
            return True
        self._tooltip.show_text(text, event.globalPos())
        return True


class CompactDisplayComboBox(ComboBox):
    """ComboBox с подробным меню и коротким выбранным значением."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._compact_text_by_data: dict[str, str] = {}

    def addItem(self, text: str, icon=None, userData=None, compactText: str | None = None):  # noqa: N802
        super().addItem(text, icon=icon, userData=userData)
        if compactText is not None:
            self._compact_text_by_data[str(userData)] = str(compactText)
            self._sync_compact_text()

    def setCurrentIndex(self, index: int):  # noqa: N802
        super().setCurrentIndex(index)
        self._sync_compact_text()

    def _sync_compact_text(self) -> None:
        index = self.currentIndex()
        if index < 0:
            return
        data = str(self.itemData(index))
        compact = self._compact_text_by_data.get(data)
        if compact:
            self.setText(compact)


class ProfileStrategyListWidget(QWidget):
    """Большой список готовых стратегий для profile."""

    strategy_activated = pyqtSignal(str)

    _ROLE_STRATEGY_ID = int(Qt.ItemDataRole.UserRole) + 1
    _ROLE_NAME_TEXT = int(Qt.ItemDataRole.UserRole) + 2
    _ROLE_STATUS_TEXT = int(Qt.ItemDataRole.UserRole) + 3
    _ROLE_IS_ACTIVE = int(Qt.ItemDataRole.UserRole) + 4
    _ROLE_VISUAL_ICON_NAME = int(Qt.ItemDataRole.UserRole) + 5
    _ROLE_VISUAL_COLOR = int(Qt.ItemDataRole.UserRole) + 6
    _ROLE_VISUAL_LABEL_TEXT = int(Qt.ItemDataRole.UserRole) + 7
    _ROLE_VISUAL_DESCRIPTION = int(Qt.ItemDataRole.UserRole) + 8
    _ROLE_TOOLTIP_TEXT = int(Qt.ItemDataRole.UserRole) + 9

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._current_strategy_id = "none"
        self._entries = {}
        self._states = {}
        self._item_by_strategy_id = {}
        self._rows_signature = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        top_row = QWidget(self)
        top_layout = QHBoxLayout(top_row)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(10)

        self._search = SearchLineEdit(self)
        self._search.setPlaceholderText("Поиск по готовым стратегиям")
        set_tooltip(
            self._search,
            "Поиск по названию, параметрам --lua-desync и описанию готовой стратегии.",
        )
        self._search.textChanged.connect(self._apply_filter)
        top_layout.addWidget(self._search, 1)

        self._summary = BodyLabel("")
        set_tooltip(
            self._summary,
            "Сколько готовых стратегий сейчас показано после фильтра поиска.",
        )
        top_layout.addWidget(self._summary)
        layout.addWidget(top_row)

        self._list = QListWidget(self)
        self._list.setItemDelegate(ProfileStrategyListDelegate(self._list))
        self._list.setUniformItemSizes(True)
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._list.setMouseTracking(True)
        self._list.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored)
        self._list.setMinimumHeight(520)
        self._list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._list.itemActivated.connect(self._on_item_activated)
        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.setStyleSheet(
            "QListWidget { background: rgba(255, 255, 255, 0.035); border: none; border-radius: 6px; outline: none; padding: 4px 0; }"
            "QListWidget::viewport { background: transparent; }"
            "QListWidget::item { border: none; padding: 0; }"
            "QListWidget::item:selected { background: transparent; }"
            "QListWidget::item:hover { background: transparent; }"
        )
        self._scrollbars = install_fluent_scrollbars(self._list, vertical=True, horizontal=False)
        layout.addWidget(self._list, 1)

    def set_rows(self, *, entries, states, current_strategy_id: str) -> None:
        next_entries = dict(entries or {})
        next_states = dict(states or {})
        next_current_id = str(current_strategy_id or "none").strip() or "none"
        next_signature = _strategy_rows_signature(next_entries, next_states)
        if self.__dict__.get("_rows_signature") == next_signature:
            self._entries = next_entries
            self._states = next_states
            if next_current_id != self._current_strategy_id:
                self.set_current_strategy_id(next_current_id)
            return
        if self._can_update_strategy_rows_in_place(next_entries, next_states):
            changed_strategy_ids = [
                strategy_id
                for strategy_id in next_entries
                if self._states.get(strategy_id) != next_states.get(strategy_id)
            ]
            self._entries = next_entries
            self._states = next_states
            self._current_strategy_id = next_current_id
            self._rows_signature = next_signature
            for strategy_id in changed_strategy_ids:
                item = self._item_by_strategy_id.get(strategy_id)
                self._refresh_strategy_item(item, strategy_id, is_current=strategy_id == self._current_strategy_id)
            return
        single_move = self._move_strategy_row_in_place(next_entries, next_states)
        if single_move is not None:
            changed_strategy_ids = [
                strategy_id
                for strategy_id in next_entries
                if self._states.get(strategy_id) != next_states.get(strategy_id)
            ]
            self._entries = next_entries
            self._states = next_states
            self._current_strategy_id = next_current_id
            self._rows_signature = next_signature
            item = self._item_by_strategy_id.get(single_move)
            self._refresh_strategy_item(item, single_move, is_current=single_move == self._current_strategy_id)
            for strategy_id in changed_strategy_ids:
                if strategy_id == single_move:
                    continue
                item = self._item_by_strategy_id.get(strategy_id)
                self._refresh_strategy_item(item, strategy_id, is_current=strategy_id == self._current_strategy_id)
            return
        self._entries = next_entries
        self._states = next_states
        self._current_strategy_id = next_current_id
        self._rows_signature = next_signature
        self._rebuild_tree()

    def _can_update_strategy_rows_in_place(self, next_entries: dict, next_states: dict) -> bool:
        if set(self._entries.keys()) != set(next_entries.keys()):
            return False
        if not self._item_by_strategy_id:
            return False
        return _strategy_visible_order(self._entries, self._states) == _strategy_visible_order(next_entries, next_states)

    def _move_strategy_row_in_place(self, next_entries: dict, next_states: dict) -> str | None:
        if set(self._entries.keys()) != set(next_entries.keys()):
            return None
        if set(self._item_by_strategy_id.keys()) != set(self._entries.keys()):
            return None
        if _strategy_entry_signature(self._entries) != _strategy_entry_signature(next_entries):
            return None
        current_order = _strategy_visible_order(self._entries, self._states)
        next_order = _strategy_visible_order(next_entries, next_states)
        changed_strategy_ids = {
            strategy_id
            for strategy_id in next_entries
            if self._states.get(strategy_id) != next_states.get(strategy_id)
        }
        move = _single_strategy_order_move(current_order, next_order, preferred_strategy_ids=changed_strategy_ids)
        if move is None:
            return None
        source_index, insert_index = move
        strategy_id = current_order[source_index]
        item = self._item_by_strategy_id.get(strategy_id)
        if item is None:
            return None
        list_row = self._list.row(item)
        if list_row != source_index:
            return None
        moved_item = self._list.takeItem(list_row)
        self._list.insertItem(insert_index, moved_item)
        return strategy_id

    def set_current_strategy_id(self, strategy_id: str) -> None:
        next_id = str(strategy_id or "none").strip() or "none"
        if next_id == self._current_strategy_id:
            return
        previous_id = self._current_strategy_id
        self._current_strategy_id = next_id
        previous_item = self._item_by_strategy_id.get(previous_id)
        next_item = self._item_by_strategy_id.get(next_id)
        self._refresh_strategy_item(previous_item, previous_id, is_current=False)
        if next_item is not previous_item:
            self._refresh_strategy_item(next_item, next_id, is_current=True)

    def _rebuild_tree(self) -> None:
        search_text = self._search.text().strip().lower()
        self._item_by_strategy_id.clear()
        self._list.clear()
        visible = 0
        current_item = None

        rows = list(self._entries.items())
        rows.sort(key=lambda pair: (
            not bool(getattr(self._states.get(pair[0]), "favorite", False)),
            str(getattr(pair[1], "name", "") or "").lower(),
        ))

        for strategy_id, entry in rows:
            name = str(getattr(entry, "name", "") or strategy_id)
            args = str(getattr(entry, "args", "") or "")
            visual = getattr(entry, "visual", None) or describe_strategy_visual(args)
            visual_label = str(visual.label or "")
            visual_description = str(visual.description or "")
            visual_search = f"{visual_label} {visual_description}".lower()
            if search_text and search_text not in name.lower() and search_text not in args.lower() and search_text not in visual_search:
                continue

            item = QListWidgetItem()
            state = self._states.get(strategy_id)
            is_current = strategy_id == self._current_strategy_id
            status_parts = []
            if is_current:
                status_parts.append("Выбрана")
            if bool(getattr(state, "favorite", False)):
                status_parts.append("В избранном")
            rating = str(getattr(state, "rating", "") or "")
            if rating == "work":
                status_parts.append("Работает")
            elif rating == "notwork":
                status_parts.append("Не работает")

            item.setText(name)
            item.setData(self._ROLE_STRATEGY_ID, strategy_id)
            item.setData(self._ROLE_NAME_TEXT, name)
            item.setData(self._ROLE_STATUS_TEXT, " • ".join(status_parts))
            item.setData(self._ROLE_IS_ACTIVE, is_current)
            item.setData(self._ROLE_VISUAL_ICON_NAME, str(visual.icon_name or ""))
            item.setData(self._ROLE_VISUAL_COLOR, str(visual.color or ""))
            item.setData(self._ROLE_VISUAL_LABEL_TEXT, visual_label)
            item.setData(self._ROLE_VISUAL_DESCRIPTION, visual_description)
            tooltip_parts = [visual_description.strip(), args]
            item.setData(self._ROLE_TOOLTIP_TEXT, "\n\n".join(part for part in tooltip_parts if part))
            item.setSizeHint(QSize(0, 31))
            if is_current:
                current_item = item
            self._item_by_strategy_id[strategy_id] = item
            self._list.addItem(item)
            visible += 1

        self._summary.setText(f"{visible} из {len(self._entries)}")
        if current_item is not None:
            self._list.setCurrentItem(current_item)
            current_item.setSelected(True)

    def _refresh_strategy_item(self, item, strategy_id: str, *, is_current: bool) -> None:
        if item is None:
            return
        state = self._states.get(strategy_id)
        status_parts = []
        if is_current:
            status_parts.append("Выбрана")
        if bool(getattr(state, "favorite", False)):
            status_parts.append("В избранном")
        rating = str(getattr(state, "rating", "") or "")
        if rating == "work":
            status_parts.append("Работает")
        elif rating == "notwork":
            status_parts.append("Не работает")
        item.setData(self._ROLE_STATUS_TEXT, " • ".join(status_parts))
        item.setData(self._ROLE_IS_ACTIVE, is_current)
        if is_current:
            self._list.setCurrentItem(item)
            item.setSelected(True)
        else:
            item.setSelected(False)
        self._list.viewport().update(self._list.visualItemRect(item))

    def _apply_filter(self) -> None:
        self._rebuild_tree()

    def _strategy_id_for_item(self, item) -> str:
        return str(item.data(self._ROLE_STRATEGY_ID) or "").strip() if item is not None else ""

    def _on_item_clicked(self, item) -> None:
        strategy_id = self._strategy_id_for_item(item)
        if strategy_id:
            self.strategy_activated.emit(strategy_id)

    def _on_item_activated(self, item) -> None:
        strategy_id = self._strategy_id_for_item(item)
        if strategy_id:
            self.strategy_activated.emit(strategy_id)


def _strategy_rows_signature(entries, states) -> tuple[tuple, tuple]:
    entry_rows = []
    for strategy_id, entry in dict(entries or {}).items():
        visual = getattr(entry, "visual", None)
        entry_rows.append((
            str(strategy_id),
            str(getattr(entry, "name", "") or ""),
            str(getattr(entry, "args", "") or ""),
            str(getattr(visual, "icon_name", "") or ""),
            str(getattr(visual, "color", "") or ""),
            str(getattr(visual, "label", "") or ""),
            str(getattr(visual, "description", "") or ""),
        ))
    state_rows = []
    for strategy_id, state in dict(states or {}).items():
        state_rows.append((
            str(strategy_id),
            str(getattr(state, "rating", "") or ""),
            bool(getattr(state, "favorite", False)),
        ))
    return tuple(sorted(entry_rows)), tuple(sorted(state_rows))


def _strategy_entry_signature(entries) -> tuple:
    return _strategy_rows_signature(entries, {})[0]


def _strategy_visible_order(entries, states) -> tuple[str, ...]:
    return tuple(
        strategy_id
        for strategy_id, _entry in sorted(
            dict(entries or {}).items(),
            key=lambda pair: (
                not bool(getattr(dict(states or {}).get(pair[0]), "favorite", False)),
                str(getattr(pair[1], "name", "") or "").lower(),
            ),
        )
    )


def _single_strategy_order_move(
    current_order: tuple[str, ...],
    next_order: tuple[str, ...],
    *,
    preferred_strategy_ids: set[str] | None = None,
) -> tuple[int, int] | None:
    if len(current_order) != len(next_order):
        return None
    if current_order == next_order:
        return None
    if len(set(current_order)) != len(current_order):
        return None
    if set(current_order) != set(next_order):
        return None

    current_positions = {strategy_id: index for index, strategy_id in enumerate(current_order)}
    first_changed = next(
        (
            index
            for index, strategy_id in enumerate(next_order)
            if current_positions.get(strategy_id) != index
        ),
        -1,
    )
    if first_changed < 0:
        return None

    last_changed = len(next_order) - 1
    while last_changed > first_changed and current_order[last_changed] == next_order[last_changed]:
        last_changed -= 1

    candidates = []
    if current_order[first_changed] == next_order[last_changed]:
        candidates.append((first_changed, last_changed))
    if current_order[last_changed] == next_order[first_changed]:
        candidates.append((last_changed, first_changed))
    if not candidates:
        return None

    preferred = set(preferred_strategy_ids or ())
    for source_index, insert_index in candidates:
        if current_order[source_index] in preferred:
            return source_index, insert_index
    return candidates[0]


def _match_tab_text(payload) -> str:
    item = getattr(payload, "item", None)
    strategy_id = str(getattr(item, "strategy_id", "") or "").strip()
    strategy_name = str(getattr(item, "strategy_name", "") or "").strip()
    strategy_entries = getattr(payload, "strategy_entries", {}) or {}
    entry = strategy_entries.get(strategy_id)
    strategy_args = str(getattr(entry, "args", "") or getattr(payload, "raw_strategy_text", "") or "").strip()

    if not strategy_name or strategy_id in {"", "none"}:
        strategy_name = "Стратегия не выбрана"
    elif strategy_id == "custom":
        strategy_name = "Своя стратегия"

    blocks = [
        ("Когда profile применяется", str(getattr(payload, "match_summary", "") or "без явных условий").strip()),
        ("Текущая готовая стратегия", strategy_name),
        ("Аргументы готовой стратегии", strategy_args or "Стратегия не выбрана"),
    ]

    lines: list[str] = []
    for title, text in blocks:
        lines.append(title)
        lines.append("=" * len(title))
        lines.append(text)
        lines.append("")
    return "\n".join(lines).strip()


def _profile_editor_tab_title(payload) -> str:
    item = getattr(payload, "item", None)
    match_lines = tuple(str(line or "").strip().lower() for line in getattr(item, "match_lines", ()) or ())
    if any(line.startswith(("--hostlist-exclude", "--ipset-exclude")) for line in match_lines):
        return "Исключения"

    display_name = str(getattr(item, "display_name", "") or "").casefold()
    if "исключения" in display_name:
        return "Исключения"

    return "Редактор"


def _profile_has_list_file_editor(payload) -> bool:
    item = getattr(payload, "item", None)
    match_lines = tuple(str(line or "").strip().lower() for line in getattr(item, "match_lines", ()) or ())
    return any(
        line.startswith(("--hostlist=", "--ipset=", "--hostlist-exclude=", "--ipset-exclude="))
        for line in match_lines
    )


def _list_file_entries_count(text: str) -> int:
    return len([
        line
        for line in str(text or "").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ])


class ProfileSetupPageBase(BasePage):
    profile_ui_mode_override: str | None = None
    launch_method = ZAPRET2_MODE
    title_key_name = "page.winws2_profile_setup.title"
    control_key = "page.winws2_profile_setup.breadcrumb.control"
    profiles_key = "page.winws2_pages.title"
    profiles_default = "Настройка пресета"

    def __init__(self, parent=None, *, profile_feature, open_profiles, open_root, on_profile_changed):
        super().__init__(
            title="",
            parent=parent,
            title_key=self.title_key_name,
        )
        self._controller = ProfileSetupController(
            profile_feature=profile_feature,
            launch_method=self.launch_method,
        )
        self._open_profiles = open_profiles
        self._open_root = open_root
        self._on_profile_changed_callback = on_profile_changed
        self._profile_key = ""
        self._loading = False
        self._setup_load_request_id = 0
        self._setup_load_worker = None
        self._list_file_load_request_id = 0
        self._list_file_load_worker = None
        self._list_file_save_request_id = 0
        self._list_file_save_worker = None
        self._list_file_validation_request_id = 0
        self._list_file_validation_worker = None
        self._pending_list_file_validation = None
        self._settings_save_request_id = 0
        self._settings_save_worker = None
        self._pending_settings_save = None
        self._raw_profile_save_request_id = 0
        self._raw_profile_save_worker = None
        self._enabled_save_request_id = 0
        self._enabled_save_worker = None
        self._user_profile_update_request_id = 0
        self._user_profile_update_worker = None
        self._user_profile_delete_request_id = 0
        self._user_profile_delete_worker = None
        self._strategy_apply_request_id = 0
        self._strategy_apply_worker = None
        self._strategy_apply_worker_strategy_id = ""
        self._pending_strategy_apply = None
        self._strategy_feedback_save_request_id = 0
        self._strategy_feedback_save_worker = None
        self._pending_strategy_feedback_save = None
        self._payload = None
        self._strategy_stack = None
        self._strategy_tabs = None
        self._strategy_list = None
        self._strategy_tab = None
        self._list_file_editor_placeholder = None
        self._match_tab_placeholder = None
        self._editor_tab_available = True
        self._editor_tab_built = False
        self._match_tab_built = False
        self._list_file_dirty = True
        self._match_text = None
        self._settings_container = None
        self._work_button = None
        self._notwork_button = None
        self._favorite_button = None
        self._clear_feedback_button = None
        self._update_user_profile_button = None
        self._delete_user_profile_button = None
        self._raw_profile_text = None
        self._raw_profile_save_button = None
        self._list_file_title = None
        self._list_file_base_title = None
        self._list_file_base_text = None
        self._list_file_user_title = None
        self._list_file_text = None
        self._list_file_editor_tab = None
        self._list_file_error_label = None
        self._list_file_status_label = None
        self._list_file_save_button = None
        self._list_file_kind = ""
        self._list_file_normal_style = ""
        self._list_file_error_style = ""
        self._settings_save_timer = QTimer(self)
        self._settings_save_timer.setSingleShot(True)
        self._settings_save_timer.setInterval(350)
        self._settings_save_timer.timeout.connect(self._autosave_editable_settings)
        self._build_content()

    def _build_content(self) -> None:
        if self.title_label is not None:
            self.title_label.hide()
        if self.subtitle_label is not None:
            self.subtitle_label.hide()

        self._breadcrumb = BreadcrumbBar()
        self._breadcrumb.currentItemChanged.connect(self._on_breadcrumb_item_changed)
        self.layout.addWidget(self._breadcrumb)

        header = QWidget(self)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(12)
        self._summary = BodyLabel("")
        self._summary.setWordWrap(True)
        header_layout.addWidget(self._summary, 1)

        self._enabled_checkbox = CheckBox("Включён")
        self._enabled_checkbox.stateChanged.connect(self._on_enabled_changed)
        header_layout.addWidget(self._enabled_checkbox, 0, Qt.AlignmentFlag.AlignRight)
        self._update_user_profile_button = PushButton("Изменить", icon=FluentIcon.EDIT)
        self._update_user_profile_button.clicked.connect(self._on_update_user_profile_clicked)
        self._update_user_profile_button.hide()
        header_layout.addWidget(self._update_user_profile_button, 0, Qt.AlignmentFlag.AlignRight)
        self._delete_user_profile_button = PushButton("Удалить", icon=FluentIcon.DELETE)
        self._delete_user_profile_button.clicked.connect(self._on_delete_user_profile_clicked)
        self._delete_user_profile_button.hide()
        header_layout.addWidget(self._delete_user_profile_button, 0, Qt.AlignmentFlag.AlignRight)
        self.layout.addWidget(header)

        self._settings_container = QWidget(self)
        self._settings_container.setMinimumWidth(0)
        self._settings_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        settings_layout = QHBoxLayout(self._settings_container)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.setSpacing(10)

        self._filter_combo = ComboBox()
        self._filter_combo.setMinimumWidth(120)
        self._filter_combo.addItem(tr_catalog("page.winws2_profile_setup.filter.hostlist", language=self._ui_language, default="Hostlist"), userData="hostlist")
        self._filter_combo.addItem(tr_catalog("page.winws2_profile_setup.filter.ipset", language=self._ui_language, default="IPset"), userData="ipset")
        settings_layout.addWidget(self._filter_combo)

        self._filter_value = LineEdit()
        self._filter_value.setMinimumWidth(0)
        self._filter_value.setPlaceholderText("lists/example.txt")
        settings_layout.addWidget(self._filter_value, 1)

        self._in_range_mode = CompactDisplayComboBox()
        self._in_range_mode.setMinimumWidth(82)
        self._fill_range_combo(self._in_range_mode)
        self._in_range_label = BodyLabel("--in-range")
        settings_layout.addWidget(self._in_range_label)
        settings_layout.addWidget(self._in_range_mode)

        self._in_range_value = LineEdit()
        self._in_range_value.setMinimumWidth(72)
        self._in_range_value.setPlaceholderText("8")
        settings_layout.addWidget(self._in_range_value)

        self._out_range_mode = CompactDisplayComboBox()
        self._out_range_mode.setMinimumWidth(82)
        self._fill_range_combo(self._out_range_mode)
        self._out_range_label = BodyLabel("--out-range")
        settings_layout.addWidget(self._out_range_label)
        settings_layout.addWidget(self._out_range_mode)

        self._out_range_value = LineEdit()
        self._out_range_value.setMinimumWidth(72)
        self._out_range_value.setPlaceholderText("8")
        settings_layout.addWidget(self._out_range_value)

        self._in_range_mode.currentIndexChanged.connect(
            lambda _index: self._on_range_mode_changed(self._in_range_mode, self._in_range_value)
        )
        self._out_range_mode.currentIndexChanged.connect(
            lambda _index: self._on_range_mode_changed(self._out_range_mode, self._out_range_value)
        )
        self._filter_combo.currentIndexChanged.connect(lambda _index: self._on_filter_kind_changed())
        self._filter_value.textEdited.connect(lambda _text: self._schedule_settings_autosave())
        self._in_range_value.textEdited.connect(lambda _text: self._schedule_settings_autosave())
        self._out_range_value.textEdited.connect(lambda _text: self._schedule_settings_autosave())

        self.layout.addWidget(self._settings_container)
        self._install_profile_tooltips()

        self._strategy_stack = QStackedWidget(self)
        self._strategy_tabs = SegmentedWidget()
        self._strategy_tabs.addItem("strategies", "Готовые стратегии", lambda: self._switch_strategy_tab(0))
        self._strategy_tabs.addItem("editor", "Редактор", lambda: self._switch_strategy_tab(1))
        self._strategy_tabs.addItem("match", "Когда применяется", lambda: self._switch_strategy_tab(2))
        self._strategy_tabs.setCurrentItem("strategies")
        self._sync_editor_tab_label(None)
        self.layout.addWidget(self._strategy_tabs)

        self._strategy_list = ProfileStrategyListWidget(self)
        self._strategy_list.strategy_activated.connect(self._on_strategy_list_activated)
        self._strategy_stack.addWidget(self._strategy_list)

        self._list_file_editor_placeholder = QWidget(self)
        self._strategy_stack.addWidget(self._list_file_editor_placeholder)

        self._match_tab_placeholder = QWidget(self)
        self._strategy_stack.addWidget(self._match_tab_placeholder)

        self.layout.addWidget(self._strategy_stack, 1)

    def _switch_strategy_tab(self, index: int) -> None:
        if index == 1 and not self._editor_tab_available:
            index = 0
            if self._strategy_tabs is not None:
                self._strategy_tabs.setCurrentItem("strategies")
        if index == 1:
            self._ensure_editor_tab_built()
            self._request_list_file_editor_state()
        elif index == 2:
            self._ensure_match_tab_built()
            self._apply_match_tab_payload()
        self._strategy_stack.setCurrentIndex(index)

    def _ensure_editor_tab_built(self) -> None:
        if self._editor_tab_built:
            return
        self._editor_tab_built = True
        editor_tab = self._list_file_editor_placeholder
        self._list_file_editor_tab = editor_tab
        editor_layout = QVBoxLayout(editor_tab)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(10)

        self._list_file_title = BodyLabel("Файл списка")
        editor_layout.addWidget(self._list_file_title)

        self._list_file_base_title = CaptionLabel("База")
        self._list_file_base_title.setWordWrap(True)
        editor_layout.addWidget(self._list_file_base_title)

        self._list_file_base_text = PlainTextEdit()
        self._list_file_base_text.setReadOnly(True)
        self._list_file_base_text.setMinimumHeight(180)
        self._list_file_base_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
        set_tooltip(
            self._list_file_base_text,
            "Системная часть списка. Она обновляется программой и показана только для просмотра.",
        )
        editor_layout.addWidget(self._list_file_base_text, 1)

        self._list_file_user_title = CaptionLabel("Ваши записи")
        self._list_file_user_title.setWordWrap(True)
        editor_layout.addWidget(self._list_file_user_title)

        self._list_file_text = PlainTextEdit()
        self._list_file_text.setMinimumHeight(320)
        self._list_file_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._list_file_text.textChanged.connect(self._on_list_file_text_changed)
        set_tooltip(
            self._list_file_text,
            "Пользовательская часть списка. Сохраняется в lists/user и добавляется к базе.",
        )
        editor_layout.addWidget(self._list_file_text, 1)

        self._list_file_error_label = CaptionLabel("")
        self._list_file_error_label.setWordWrap(True)
        self._list_file_error_label.hide()
        editor_layout.addWidget(self._list_file_error_label)

        editor_actions = QWidget(editor_tab)
        editor_actions_layout = QHBoxLayout(editor_actions)
        editor_actions_layout.setContentsMargins(0, 0, 0, 0)
        editor_actions_layout.setSpacing(12)
        self._list_file_save_button = PushButton("Сохранить список", icon=FluentIcon.SAVE)
        self._list_file_save_button.clicked.connect(self._on_list_file_save_clicked)
        editor_actions_layout.addWidget(self._list_file_save_button)
        self._list_file_status_label = CaptionLabel("Загрузка файла списка...")
        self._list_file_status_label.setWordWrap(True)
        editor_actions_layout.addWidget(self._list_file_status_label, 1)
        editor_layout.addWidget(editor_actions)
        self._refresh_list_file_editor_style(has_error=False)

    def _ensure_match_tab_built(self) -> None:
        if self._match_tab_built:
            return
        self._match_tab_built = True
        match_tab = self._match_tab_placeholder
        match_layout = QVBoxLayout(match_tab)
        match_layout.setContentsMargins(0, 0, 0, 0)
        match_layout.setSpacing(10)
        match_layout.addWidget(BodyLabel("Условия и готовая стратегия"))
        self._match_text = PlainTextEdit()
        self._match_text.setReadOnly(True)
        self._match_text.setMinimumHeight(280)
        set_tooltip(
            self._match_text,
            "Подробности текущего profile: условия применения и выбранная готовая стратегия.",
        )
        match_layout.addWidget(self._match_text, 1)

        match_layout.addWidget(BodyLabel("Текст profile в текущем preset"))
        self._raw_profile_text = PlainTextEdit()
        self._raw_profile_text.setMinimumHeight(150)
        self._raw_profile_text.setMaximumHeight(220)
        set_tooltip(
            self._raw_profile_text,
            "Сырой текст profile. Сохраняется только в текущий preset и не меняет пользовательский шаблон.",
        )
        match_layout.addWidget(self._raw_profile_text)

        raw_actions = QWidget(match_tab)
        raw_actions_layout = QHBoxLayout(raw_actions)
        raw_actions_layout.setContentsMargins(0, 0, 0, 0)
        raw_actions_layout.setSpacing(12)
        self._raw_profile_save_button = PushButton("Сохранить текст profile", icon=FluentIcon.SAVE)
        self._raw_profile_save_button.clicked.connect(self._on_raw_profile_save_clicked)
        set_tooltip(
            self._raw_profile_save_button,
            "Проверяет текст как один profile и записывает его в текущий preset.",
        )
        raw_actions_layout.addWidget(self._raw_profile_save_button)
        raw_actions_layout.addStretch(1)
        match_layout.addWidget(raw_actions)

        feedback_actions = QWidget(match_tab)
        feedback_actions_layout = QHBoxLayout(feedback_actions)
        feedback_actions_layout.setContentsMargins(0, 0, 0, 0)
        feedback_actions_layout.setSpacing(12)

        self._work_button = PushButton("Работает", icon=FluentIcon.ACCEPT)
        set_tooltip(self._work_button, "Пометить текущую готовую стратегию как рабочую для этого profile.")
        self._work_button.clicked.connect(lambda: self._set_current_strategy_feedback(rating="work"))
        feedback_actions_layout.addWidget(self._work_button)

        self._notwork_button = PushButton("Не работает", icon=FluentIcon.CLOSE)
        set_tooltip(self._notwork_button, "Пометить текущую готовую стратегию как нерабочую для этого profile.")
        self._notwork_button.clicked.connect(lambda: self._set_current_strategy_feedback(rating="notwork"))
        feedback_actions_layout.addWidget(self._notwork_button)

        self._favorite_button = PushButton("В избранное", icon=FluentIcon.HEART)
        set_tooltip(self._favorite_button, "Добавить текущую готовую стратегию в избранное или убрать её оттуда.")
        self._favorite_button.clicked.connect(self._toggle_current_strategy_favorite)
        feedback_actions_layout.addWidget(self._favorite_button)

        self._clear_feedback_button = PushButton("Убрать оценку", icon=FluentIcon.RETURN)
        set_tooltip(self._clear_feedback_button, "Очистить вашу оценку для текущей готовой стратегии.")
        self._clear_feedback_button.clicked.connect(lambda: self._set_current_strategy_feedback(rating=""))
        feedback_actions_layout.addWidget(self._clear_feedback_button)
        feedback_actions_layout.addStretch(1)
        match_layout.addWidget(feedback_actions)
        self._apply_match_tab_payload()

    def _apply_match_tab_payload(self) -> None:
        payload = self._payload
        if payload is None or not self._match_tab_built:
            return
        item = payload.item
        if self._match_text is not None:
            self._match_text.setPlainText(_match_tab_text(payload))
        if self._raw_profile_text is not None:
            self._raw_profile_text.setPlainText(str(getattr(payload, "raw_profile_text", "") or ""))
            raw_editable = bool(getattr(item, "in_preset", False))
            self._raw_profile_text.setReadOnly(not raw_editable)
        if self._raw_profile_save_button is not None:
            self._raw_profile_save_button.setEnabled(bool(getattr(item, "in_preset", False)))
        self._apply_feedback_buttons(payload)

    def _request_list_file_editor_state(self) -> None:
        if not self._editor_tab_built or not self._profile_key:
            return
        worker = self._list_file_load_worker
        if worker is not None:
            try:
                if worker.isRunning():
                    return
            except Exception:
                return
        if self._list_file_status_label is not None:
            self._list_file_status_label.setText("Загрузка файла списка...")
        self._list_file_load_request_id += 1
        request_id = self._list_file_load_request_id
        worker = self._controller.create_list_file_load_worker(
            request_id,
            self._profile_key,
            filter_kind=self._current_filter_kind(),
            filter_value=self._current_filter_value(),
            parent=self,
        )
        self._list_file_load_worker = worker
        worker.loaded.connect(self._on_list_file_editor_state_loaded)
        worker.failed.connect(self._on_list_file_editor_state_failed)
        worker.finished.connect(lambda w=worker: self._on_list_file_worker_finished(w))
        worker.start()

    def _on_list_file_editor_state_loaded(self, request_id: int, state) -> None:
        if request_id != self._list_file_load_request_id:
            return
        self._list_file_dirty = False
        self._apply_list_file_editor_state(state)

    def _on_list_file_editor_state_failed(self, request_id: int, error: str) -> None:
        if request_id != self._list_file_load_request_id:
            return
        if self._list_file_status_label is not None:
            self._list_file_status_label.setText(f"Ошибка загрузки файла списка: {error}")

    def _on_list_file_worker_finished(self, worker) -> None:
        if self._list_file_load_worker is worker:
            self._list_file_load_worker = None
        worker.deleteLater()

    def _fill_range_combo(self, combo: CompactDisplayComboBox) -> None:
        combo.addItem("a — всегда", userData="a", compactText="a")
        combo.addItem("x — никогда", userData="x", compactText="x")
        combo.addItem("n — номер пакета", userData="n", compactText="n")
        combo.addItem("d — пакет с данными", userData="d", compactText="d")
        combo.addItem("своё выражение", userData="custom", compactText="своё")

    def _range_mode_description(self, mode: str) -> str:
        descriptions = {
            "a": "a — всегда. Этот range не ограничивает пакеты.",
            "x": "x — никогда. Следующие --lua-desync не будут применяться для этого направления.",
            "n": "n — номер пакета в соединении. Например, n8 означает восьмой пакет.",
            "d": "d — номер пакета с данными. Служебные пакеты без данных не считаются.",
            "custom": "своё выражение — ручной range winws2, например s1<d1 или -d8.",
        }
        return descriptions.get(str(mode or "").strip(), "Неизвестный режим range.")

    def _update_range_tooltips(self, combo: ComboBox, value_edit: LineEdit, *, option_name: str, direction: str) -> None:
        mode = str(combo.itemData(combo.currentIndex()) or "").strip()
        mode_description = self._range_mode_description(mode)
        set_tooltip(
            combo,
            f"{option_name} для {direction} пакетов.\n{mode_description}",
        )
        set_tooltip(
            value_edit,
            f"Значение для {option_name}.\n{mode_description}\n"
            "Поле активно для n, d и своего выражения.",
        )

    def _update_all_range_tooltips(self) -> None:
        self._update_range_tooltips(
            self._in_range_mode,
            self._in_range_value,
            option_name="--in-range",
            direction="входящих",
        )
        self._update_range_tooltips(
            self._out_range_mode,
            self._out_range_value,
            option_name="--out-range",
            direction="исходящих",
        )

    def _install_profile_tooltips(self) -> None:
        range_hint = (
            "Диапазон задаёт, на каких пакетах будут работать следующие --lua-desync внутри этого profile.\n"
            "a — всегда, x — никогда, n — номер пакета, d — номер пакета с данными, своё — ручное выражение winws2."
        )
        set_tooltip(
            self._breadcrumb,
            "Хлебные крошки: показывают путь до текущего profile и позволяют вернуться к списку profile или управлению.",
        )
        set_tooltip(
            self._summary,
            "Краткое условие profile: протокол, порты и тип фильтра. По этой строке видно, когда этот profile применяется.",
        )
        set_tooltip(
            self._enabled_checkbox,
            "Включает или выключает этот profile в текущем preset. Если выключить, profile останется в preset, но не будет применяться.",
        )
        set_tooltip(
            self._update_user_profile_button,
            "Изменяет пользовательский profile и обновляет все preset-ы, где он найден по старому --name.",
        )
        set_tooltip(
            self._delete_user_profile_button,
            "Удаляет пользовательский profile, его файлы списков и связанные profile-ы из preset-ов.",
        )
        set_tooltip(
            self._filter_combo,
            "Тип фильтра profile. Hostlist — список доменов, ipset — список IP-адресов или подсетей.",
        )
        set_tooltip(
            self._filter_value,
            "Файл списка для текущего profile. Обычно это путь вида lists/youtube.txt или lists/ipset-youtube.txt.",
        )
        set_tooltip(
            self._in_range_label,
            "--in-range — диапазон для входящих пакетов. " + range_hint,
        )
        set_tooltip(
            self._in_range_mode,
            "Режим --in-range. Откройте меню, чтобы увидеть расшифровку a, x, n, d и своего выражения.",
        )
        set_tooltip(
            self._in_range_value,
            "Число или ручная часть --in-range. Поле активно, когда выбран режим n, d или своё выражение.",
        )
        set_tooltip(
            self._out_range_label,
            "--out-range — диапазон для исходящих пакетов. " + range_hint,
        )
        set_tooltip(
            self._out_range_mode,
            "Режим --out-range. Откройте меню, чтобы увидеть расшифровку a, x, n, d и своего выражения.",
        )
        set_tooltip(
            self._out_range_value,
            "Число или ручная часть --out-range. Поле активно, когда выбран режим n, d или своё выражение.",
        )

    def _rebuild_breadcrumb(self) -> None:
        self._breadcrumb.blockSignals(True)
        try:
            self._breadcrumb.clear()
            self._breadcrumb.addItem("control", tr_catalog(self.control_key, language=self._ui_language, default="Управление"))
            self._breadcrumb.addItem("profiles", tr_catalog(self.profiles_key, language=self._ui_language, default=self.profiles_default))
            title = str(getattr(getattr(self._payload, "item", None), "display_name", "") or "Профиль")
            self._breadcrumb.addItem("profile", title)
        finally:
            self._breadcrumb.blockSignals(False)

    def _on_breadcrumb_item_changed(self, key: str) -> None:
        if key == "control":
            self._open_root()
        elif key == "profiles":
            self._open_profiles()
        elif key == "profile":
            self._rebuild_breadcrumb()

    def _on_update_user_profile_clicked(self) -> None:
        if self._payload is None:
            return
        profile_id = _user_profile_id_from_payload(self._profile_key, self._payload)
        if not profile_id:
            return
        item = self._payload.item
        protocol, ports = _protocol_and_ports_from_match_lines(tuple(getattr(item, "match_lines", ()) or ()))
        dialog = CreateUserProfileDialog(
            self,
            title="Изменить profile",
            subtitle="Изменяет пользовательский profile и обновляет все preset-ы, где есть старое --name.",
            button_text="Сохранить",
            name=str(getattr(item, "display_name", "") or ""),
            protocol=protocol,
            ports=ports,
        )
        if not dialog.exec():
            return
        name, protocol, ports = dialog.values()
        self._request_user_profile_update(
            profile_id,
            name=name,
            protocol=protocol,
            ports=ports,
        )

    def _on_delete_user_profile_clicked(self) -> None:
        profile_id = _user_profile_id_from_payload(self._profile_key, self._payload)
        if not profile_id:
            return
        dialog = MessageBox(
            "Удалить profile",
            "Пользовательский profile будет удалён из библиотеки, его файлы списков будут удалены, "
            "а profile-ы с таким же --name будут убраны из preset-ов.",
            self,
        )
        dialog.yesButton.setText("Удалить")
        dialog.cancelButton.setText("Отмена")
        if not dialog.exec():
            return
        self._request_user_profile_delete(profile_id)

    def _set_user_profile_buttons_enabled(self, enabled: bool) -> None:
        if self._update_user_profile_button is not None:
            self._update_user_profile_button.setEnabled(enabled)
        if self._delete_user_profile_button is not None:
            self._delete_user_profile_button.setEnabled(enabled)

    def _current_user_profile_id(self) -> str:
        return _user_profile_id_from_payload(self._profile_key, self._payload)

    def _request_user_profile_update(self, profile_id: str, *, name: str, protocol: str, ports: str) -> None:
        profile_id = str(profile_id or "").strip()
        if not profile_id:
            return
        worker = self.__dict__.get("_user_profile_update_worker")
        if worker is not None:
            try:
                if worker.isRunning():
                    return
            except Exception:
                return
        self._user_profile_update_request_id = int(getattr(self, "_user_profile_update_request_id", 0) or 0) + 1
        request_id = self._user_profile_update_request_id
        self._set_user_profile_buttons_enabled(False)
        worker = self._controller.create_user_profile_update_worker(
            request_id,
            profile_id=profile_id,
            name=name,
            protocol=protocol,
            ports=ports,
            parent=self,
        )
        self._user_profile_update_worker = worker
        worker.updated.connect(self._on_user_profile_update_finished)
        worker.failed.connect(self._on_user_profile_update_failed)
        worker.finished.connect(lambda w=worker: self._on_user_profile_update_worker_finished(w))
        worker.start()

    def _on_user_profile_update_finished(
        self,
        request_id: int,
        profile_id: str,
        changed: int,
        _profile_items=(),
    ) -> None:
        if request_id != int(getattr(self, "_user_profile_update_request_id", 0) or 0):
            return
        if str(profile_id or "").strip() != self._current_user_profile_id():
            return
        InfoBar.success(
            title="Profile изменён",
            content=f"Обновлено profile-ов в preset-ах: {int(changed or 0)}.",
            parent=self.window(),
        )
        updated_item = _updated_user_profile_item(profile_id, self._profile_key, _profile_items)
        if updated_item is not None:
            if not self._apply_user_profile_update_locally(updated_item):
                self.reload_current_profile()
                self._on_profile_changed_callback(self._profile_key, "user_profile_updated")
                return
            self._on_profile_changed_callback(self._profile_key, "user_profile_updated", updated_item)
            return
        self.reload_current_profile()
        self._on_profile_changed_callback(self._profile_key, "user_profile_updated")

    def _on_user_profile_update_failed(self, request_id: int, error: str) -> None:
        if request_id != int(getattr(self, "_user_profile_update_request_id", 0) or 0):
            return
        self._set_user_profile_buttons_enabled(True)
        log(f"{self.__class__.__name__}: не удалось изменить пользовательский profile: {error}", "ERROR")
        InfoBar.error(
            title="Ошибка",
            content=str(error),
            parent=self.window(),
        )

    def _on_user_profile_update_worker_finished(self, worker) -> None:
        if self.__dict__.get("_user_profile_update_worker") is worker:
            self._user_profile_update_worker = None
            self._set_user_profile_buttons_enabled(True)
        worker.deleteLater()

    def _apply_user_profile_update_locally(self, updated_item) -> bool:
        payload = self._payload
        if payload is None or updated_item is None:
            return False
        try:
            self._payload = replace(payload, item=updated_item)
        except Exception:
            return False
        self._apply_payload(self._payload)
        return True

    def _request_user_profile_delete(self, profile_id: str) -> None:
        profile_id = str(profile_id or "").strip()
        if not profile_id:
            return
        worker = self.__dict__.get("_user_profile_delete_worker")
        if worker is not None:
            try:
                if worker.isRunning():
                    return
            except Exception:
                return
        self._user_profile_delete_request_id = int(getattr(self, "_user_profile_delete_request_id", 0) or 0) + 1
        request_id = self._user_profile_delete_request_id
        self._set_user_profile_buttons_enabled(False)
        worker = self._controller.create_user_profile_delete_worker(
            request_id,
            profile_id=profile_id,
            parent=self,
        )
        self._user_profile_delete_worker = worker
        worker.deleted.connect(self._on_user_profile_delete_finished)
        worker.failed.connect(self._on_user_profile_delete_failed)
        worker.finished.connect(lambda w=worker: self._on_user_profile_delete_worker_finished(w))
        worker.start()

    def _on_user_profile_delete_finished(self, request_id: int, profile_id: str, changed: int) -> None:
        if request_id != int(getattr(self, "_user_profile_delete_request_id", 0) or 0):
            return
        if str(profile_id or "").strip() != self._current_user_profile_id():
            return
        InfoBar.success(
            title="Profile удалён",
            content=f"Удалено profile-ов из preset-ов: {int(changed or 0)}.",
            parent=self.window(),
        )
        self._on_profile_changed_callback(self._profile_key, "user_profile_deleted")
        self._open_profiles()

    def _on_user_profile_delete_failed(self, request_id: int, error: str) -> None:
        if request_id != int(getattr(self, "_user_profile_delete_request_id", 0) or 0):
            return
        self._set_user_profile_buttons_enabled(True)
        log(f"{self.__class__.__name__}: не удалось удалить пользовательский profile: {error}", "ERROR")
        InfoBar.error(
            title="Ошибка",
            content=str(error),
            parent=self.window(),
        )

    def _on_user_profile_delete_worker_finished(self, worker) -> None:
        if self.__dict__.get("_user_profile_delete_worker") is worker:
            self._user_profile_delete_worker = None
            self._set_user_profile_buttons_enabled(True)
        worker.deleteLater()

    def show_profile(self, profile_key: str) -> None:
        self._profile_key = str(profile_key or "").strip()
        self.reload_current_profile()

    def handle_page_command(self, command: str, payload: dict) -> bool:
        if command == "open_profile":
            self.show_profile(str((payload or {}).get("profile_key") or ""))
            return True
        return False

    def reload_current_profile(self) -> None:
        self._request_profile_setup_payload()

    def _request_profile_setup_payload(self) -> None:
        if not self._profile_key:
            return
        self._setup_load_request_id += 1
        request_id = self._setup_load_request_id
        self._summary.setText("Загрузка profile...")
        self._enabled_checkbox.setEnabled(False)
        worker = self._controller.create_load_worker(request_id, self._profile_key, self)
        self._setup_load_worker = worker
        worker.loaded.connect(self._on_profile_setup_payload_loaded)
        worker.failed.connect(self._on_profile_setup_payload_failed)
        worker.finished.connect(lambda w=worker: self._on_profile_setup_worker_finished(w))
        worker.start()

    def _on_profile_setup_payload_loaded(self, request_id: int, payload) -> None:
        if request_id != self._setup_load_request_id:
            return
        if payload is None:
            self._summary.setText("Профиль не найден. Вернитесь к списку и выберите profile заново.")
            self._enabled_checkbox.setEnabled(False)
            return
        self._payload = payload
        self._apply_payload(payload)

    def _on_profile_setup_payload_failed(self, request_id: int, error: str) -> None:
        if request_id != self._setup_load_request_id:
            return
        log(f"{self.__class__.__name__}: не удалось прочитать профиль {self._profile_key}: {error}", "ERROR")
        self._summary.setText("Профиль не найден. Вернитесь к списку и выберите profile заново.")
        self._enabled_checkbox.setEnabled(False)

    def _on_profile_setup_worker_finished(self, worker) -> None:
        if self._setup_load_worker is worker:
            self._setup_load_worker = None
        worker.deleteLater()

    def _apply_payload(self, payload) -> None:
        self._loading = True
        try:
            item = payload.item
            self._summary.setText(payload.match_summary)
            self._enabled_checkbox.setChecked(bool(item.enabled))
            self._enabled_checkbox.setEnabled(True)
            if self._update_user_profile_button is not None:
                self._update_user_profile_button.setVisible(bool(_user_profile_id_from_payload(self._profile_key, payload)))
            if self._delete_user_profile_button is not None:
                self._delete_user_profile_button.setVisible(bool(_user_profile_id_from_payload(self._profile_key, payload)))
            self._apply_editable_settings(payload)
            self._set_list_file_editor_available(_profile_has_list_file_editor(payload))
            self._sync_editor_tab_label(payload)

            self._strategy_list.set_rows(
                entries=payload.strategy_entries,
                states=payload.strategy_states,
                current_strategy_id=item.strategy_id or "none",
            )
            self._strategy_list.setEnabled(not (item.in_preset and not item.enabled))
            self._list_file_dirty = True
            if self._editor_tab_built and self._strategy_stack.currentIndex() == 1:
                self._request_list_file_editor_state()
            if self._match_tab_built:
                self._apply_match_tab_payload()
            self._rebuild_breadcrumb()
        finally:
            self._loading = False

    def _set_list_file_editor_available(self, available: bool) -> None:
        if self._strategy_tabs is None or self._strategy_stack is None:
            self._editor_tab_available = available
            return
        if available == self._editor_tab_available:
            return

        self._editor_tab_available = available
        if available:
            editor_title = _profile_editor_tab_title(self._payload)
            self._strategy_tabs.insertItem(1, "editor", editor_title, lambda: self._switch_strategy_tab(1))
            return

        if self._strategy_stack.currentIndex() == 1:
            self._strategy_stack.setCurrentIndex(0)
            self._strategy_tabs.setCurrentItem("strategies")
        self._strategy_tabs.removeWidget("editor")

    def _sync_editor_tab_label(self, payload) -> None:
        editor_title = _profile_editor_tab_title(payload)
        if self._strategy_tabs is not None and self._editor_tab_available:
            self._strategy_tabs.setItemText("editor", editor_title)
            set_tooltip(
                self._strategy_tabs,
                f"Готовые стратегии меняют строки --lua-desync. «{editor_title}» меняет файл hostlist/ipset. «Когда применяется» показывает условия profile и итоговый текст.",
            )

    def _apply_list_file_editor_state(self, state) -> None:
        kind = str(getattr(state, "kind", "") or "").strip().lower()
        display_path = str(getattr(state, "display_path", "") or "").strip()
        text = str(getattr(state, "text", "") or "")
        base_text = str(getattr(state, "base_text", "") or "")
        user_text = str(getattr(state, "user_text", text) or "")
        base_display_path = str(getattr(state, "base_display_path", "") or "").strip()
        user_display_path = str(getattr(state, "user_display_path", display_path) or "").strip()
        editable = bool(getattr(state, "editable", False))
        error_text = str(getattr(state, "error_text", "") or "").strip()
        invalid_lines = tuple(getattr(state, "invalid_lines", ()) or ())
        self._list_file_kind = kind

        title = "Файл списка"
        if display_path:
            title = f"{display_path} ({'IPset' if kind == 'ipset' else 'Hostlist'})"
        if self._list_file_title is not None:
            self._list_file_title.setText(title)
        if self._list_file_base_title is not None:
            self._list_file_base_title.setVisible(editable)
            self._list_file_base_title.setText(
                f"База: {base_display_path}" if base_display_path else "База"
            )
        if self._list_file_base_text is not None:
            self._list_file_base_text.setVisible(editable)
            self._list_file_base_text.blockSignals(True)
            try:
                self._list_file_base_text.setPlainText(base_text)
                if kind == "ipset":
                    self._list_file_base_text.setPlaceholderText("В базе пока нет IP или подсетей.")
                else:
                    self._list_file_base_text.setPlaceholderText("В базе пока нет доменов.")
            finally:
                self._list_file_base_text.blockSignals(False)
        if self._list_file_user_title is not None:
            self._list_file_user_title.setVisible(editable)
            self._list_file_user_title.setText(
                f"Ваши записи: {user_display_path}" if user_display_path else "Ваши записи"
            )
        if self._list_file_text is not None:
            self._list_file_text.blockSignals(True)
            try:
                self._list_file_text.setPlainText(user_text if editable else text)
                self._list_file_text.setReadOnly(not editable)
                if kind == "ipset":
                    self._list_file_text.setPlaceholderText("IP или подсети по одному на строку:\n1.2.3.4\n10.0.0.0/8")
                else:
                    self._list_file_text.setPlaceholderText("Домены по одному на строку:\nexample.com\nsub.example.org")
            finally:
                self._list_file_text.blockSignals(False)
        if self._list_file_save_button is not None:
            self._list_file_save_button.setEnabled(editable and not invalid_lines)
        if self._list_file_status_label is not None:
            if editable:
                base_count = _list_file_entries_count(base_text)
                user_count = _list_file_entries_count(user_text)
                self._list_file_status_label.setText(
                    f"Записей всего: {base_count + user_count} • ваших: {user_count}"
                )
            else:
                self._list_file_status_label.setText(error_text or "Файл списка недоступен для редактирования.")
        self._render_list_file_validation(invalid_lines, fallback_error=error_text if not editable else "")

    def _on_list_file_text_changed(self) -> None:
        if self._loading or self._list_file_text is None:
            return
        text = self._list_file_text.toPlainText()
        if self._list_file_status_label is not None:
            self._list_file_status_label.setText("Проверка списка...")
        self._request_list_file_validation({
            "kind": self._list_file_kind,
            "text": text,
        })

    def _request_list_file_validation(self, request: dict) -> None:
        worker = self.__dict__.get("_list_file_validation_worker")
        if worker is not None:
            try:
                if worker.isRunning():
                    self._pending_list_file_validation = dict(request)
                    return
            except Exception:
                pass
        self._start_list_file_validation_worker(request)

    def _start_list_file_validation_worker(self, request: dict) -> None:
        self._list_file_validation_request_id = int(getattr(self, "_list_file_validation_request_id", 0) or 0) + 1
        request_id = self._list_file_validation_request_id
        worker = self._controller.create_list_file_validation_worker(
            request_id,
            kind=str(request.get("kind") or ""),
            text=str(request.get("text") or ""),
            parent=self,
        )
        self._list_file_validation_worker = worker
        worker.validated.connect(self._on_list_file_validation_finished)
        worker.failed.connect(self._on_list_file_validation_failed)
        worker.finished.connect(lambda w=worker: self._on_list_file_validation_worker_finished(w))
        worker.start()

    def _on_list_file_validation_finished(
        self,
        request_id: int,
        kind: str,
        text: str,
        invalid_lines,
    ) -> None:
        if request_id != int(getattr(self, "_list_file_validation_request_id", 0) or 0):
            return
        if self.__dict__.get("_pending_list_file_validation"):
            return
        if str(kind or "").strip() != str(getattr(self, "_list_file_kind", "") or "").strip():
            return
        current_text = self._list_file_text.toPlainText() if self._list_file_text is not None else ""
        if str(text or "") != current_text:
            return
        invalid_lines = tuple(invalid_lines or ())
        self._render_list_file_validation(tuple(invalid_lines or ()))
        if self._list_file_save_button is not None:
            self._list_file_save_button.setEnabled(not invalid_lines and not self._list_file_text.isReadOnly())
        if self._list_file_status_label is not None:
            if invalid_lines:
                self._list_file_status_label.setText("Исправьте ошибки перед сохранением.")
            else:
                user_count = _list_file_entries_count(self._list_file_text.toPlainText())
                base_count = _list_file_entries_count(
                    self._list_file_base_text.toPlainText()
                    if self._list_file_base_text is not None
                    else ""
                )
                self._list_file_status_label.setText(
                    f"Записей всего: {base_count + user_count} • ваших: {user_count} • есть несохранённые изменения"
                )

    def _on_list_file_validation_failed(self, request_id: int, error: str) -> None:
        if request_id != int(getattr(self, "_list_file_validation_request_id", 0) or 0):
            return
        log(f"{self.__class__.__name__}: не удалось проверить файл списка profile: {error}", "ERROR")
        if self.__dict__.get("_pending_list_file_validation"):
            return
        self._render_list_file_validation((), fallback_error=str(error))
        if self._list_file_save_button is not None:
            self._list_file_save_button.setEnabled(False)
        if self._list_file_status_label is not None:
            self._list_file_status_label.setText("Ошибка проверки списка.")

    def _on_list_file_validation_worker_finished(self, worker) -> None:
        if self.__dict__.get("_list_file_validation_worker") is worker:
            self._list_file_validation_worker = None
        worker.deleteLater()
        pending = self.__dict__.get("_pending_list_file_validation")
        self._pending_list_file_validation = None
        if pending:
            self._start_list_file_validation_worker(pending)

    def _on_list_file_save_clicked(self) -> None:
        if self._loading or not self._profile_key or self._list_file_text is None:
            return
        worker = self._list_file_save_worker
        if worker is not None:
            try:
                if worker.isRunning():
                    return
            except Exception:
                return
        self._list_file_save_request_id += 1
        request_id = self._list_file_save_request_id
        if self._list_file_status_label is not None:
            self._list_file_status_label.setText("Сохранение списка...")
        if self._list_file_save_button is not None:
            self._list_file_save_button.setEnabled(False)
        worker = self._controller.create_list_file_save_worker(
            request_id,
            self._profile_key,
            self._list_file_text.toPlainText(),
            parent=self,
        )
        self._list_file_save_worker = worker
        worker.saved.connect(self._on_list_file_save_finished)
        worker.failed.connect(self._on_list_file_save_failed)
        worker.finished.connect(lambda w=worker: self._on_list_file_save_worker_finished(w))
        worker.start()

    def _on_list_file_save_finished(self, request_id: int, state, payload=None) -> None:
        if request_id != self._list_file_save_request_id:
            return
        if state is not None:
            self._apply_list_file_editor_state(state)
        if self._list_file_status_label is not None:
            self._list_file_status_label.setText("Список сохранён.")
        if payload is None:
            self.reload_current_profile()
            self._on_profile_changed_callback(self._profile_key, "list_file")
        else:
            self._payload = payload
            self._apply_payload(payload)
            self._on_profile_changed_callback(self._profile_key, "list_file", getattr(payload, "item", None))
        InfoBar.success(
            title="Список сохранён",
            content="Файл списка обновлён.",
            parent=self.window(),
        )

    def _on_list_file_save_failed(self, request_id: int, error: str) -> None:
        if request_id != self._list_file_save_request_id:
            return
        log(f"{self.__class__.__name__}: не удалось сохранить файл списка profile: {error}", "ERROR")
        self._render_list_file_validation((), fallback_error=str(error))
        if self._list_file_save_button is not None:
            self._list_file_save_button.setEnabled(True)
        InfoBar.error(title="Ошибка", content=str(error), parent=self.window())

    def _on_list_file_save_worker_finished(self, worker) -> None:
        if self._list_file_save_worker is worker:
            self._list_file_save_worker = None
        worker.deleteLater()

    def _render_list_file_validation(
        self,
        invalid_lines: tuple[tuple[int, str], ...],
        *,
        fallback_error: str = "",
    ) -> None:
        has_error = bool(invalid_lines or fallback_error)
        self._refresh_list_file_editor_style(has_error=has_error)
        if self._list_file_error_label is None:
            return
        if invalid_lines:
            lines = [
                f"Строка {line}: {value}"
                for line, value in invalid_lines[:5]
            ]
            if len(invalid_lines) > 5:
                lines.append(f"И ещё ошибок: {len(invalid_lines) - 5}")
            self._list_file_error_label.setText("Неверные строки:\n" + "\n".join(lines))
            self._list_file_error_label.show()
            return
        if fallback_error:
            self._list_file_error_label.setText(fallback_error)
            self._list_file_error_label.show()
            return
        self._list_file_error_label.clear()
        self._list_file_error_label.hide()

    def _refresh_list_file_editor_style(self, *, has_error: bool) -> None:
        if self._list_file_text is None:
            return
        tokens = get_theme_tokens()
        error_color = "#ff6b6b"
        normal_style = f"""
            QPlainTextEdit {{
                background: {tokens.surface_bg};
                border: 1px solid {tokens.surface_border};
                border-radius: 8px;
                padding: 12px;
                color: {tokens.fg};
                font-family: Consolas, 'Courier New', monospace;
                font-size: 13px;
            }}
            QPlainTextEdit:hover {{
                background: {tokens.surface_bg_hover};
                border: 1px solid {tokens.surface_border_hover};
            }}
            QPlainTextEdit:focus {{
                border: 1px solid {tokens.accent_hex};
            }}
        """
        error_style = f"""
            QPlainTextEdit {{
                background: rgba(255, 100, 100, 0.06);
                border: 1px solid {error_color};
                border-radius: 8px;
                padding: 12px;
                color: {tokens.fg};
                font-family: Consolas, 'Courier New', monospace;
                font-size: 13px;
            }}
            QPlainTextEdit:focus {{
                border: 1px solid {error_color};
            }}
        """
        if self._list_file_base_text is not None:
            self._list_file_base_text.setStyleSheet(normal_style)
        self._list_file_text.setStyleSheet(error_style if has_error else normal_style)
        if self._list_file_error_label is not None:
            self._list_file_error_label.setStyleSheet(f"color: {error_color}; background: transparent;")
        if self._list_file_status_label is not None:
            self._list_file_status_label.setStyleSheet(f"color: {tokens.fg_faint}; background: transparent;")

    def _apply_feedback_buttons(self, payload) -> None:
        item = payload.item
        state = payload.current_strategy_state
        editable = bool(
            item.in_preset
            and item.enabled
            and item.strategy_id not in {"", "none", "custom"}
        )
        for button in (self._work_button, self._notwork_button, self._favorite_button, self._clear_feedback_button):
            if button is not None:
                button.setEnabled(editable)
        if self._favorite_button is not None:
            self._favorite_button.setText("Убрать из избранного" if state.favorite else "В избранное")
        if self._work_button is not None:
            self._work_button.setProperty("selected", state.rating == "work")
        if self._notwork_button is not None:
            self._notwork_button.setProperty("selected", state.rating == "notwork")

    def _apply_editable_settings(self, payload) -> None:
        is_preset_mode = is_preset_launch_method(self.launch_method)
        is_winws2 = is_zapret2_launch_method(self.launch_method)
        if not is_preset_mode:
            if self._settings_container is not None:
                self._settings_container.setVisible(False)
            return

        filter_enabled = bool(getattr(payload, "editable_filter_enabled", True))
        available_kinds = tuple(getattr(payload, "editable_filter_kinds", ()) or ())
        filter_switchable = filter_enabled and len({kind for kind in available_kinds if kind in {"hostlist", "ipset"}}) > 1
        if self._settings_container is not None:
            self._settings_container.setVisible(is_winws2 or filter_switchable)
        self._rebuild_filter_kind_combo(
            available_kinds,
            str(getattr(payload, "editable_filter_kind", "") or "hostlist"),
        )
        set_combo_by_data(self._filter_combo, getattr(payload, "editable_filter_kind", "") or "hostlist")
        self._filter_value.setText(str(getattr(payload, "editable_filter_value", "") or ""))
        self._filter_combo.setVisible(filter_switchable)
        self._filter_value.setVisible(filter_switchable)
        for widget in (
            self._in_range_label,
            self._in_range_mode,
            self._in_range_value,
            self._out_range_label,
            self._out_range_mode,
            self._out_range_value,
        ):
            if widget is not None:
                widget.setVisible(is_winws2)
        set_range_controls(self._in_range_mode, self._in_range_value, getattr(payload, "in_range", "") or "x")
        set_range_controls(self._out_range_mode, self._out_range_value, getattr(payload, "out_range", "") or "a")
        self._update_all_range_tooltips()

    def _rebuild_filter_kind_combo(self, available_kinds: tuple[str, ...], current_kind: str) -> None:
        labels = {
            "hostlist": tr_catalog("page.winws2_profile_setup.filter.hostlist", language=self._ui_language, default="Hostlist"),
            "ipset": tr_catalog("page.winws2_profile_setup.filter.ipset", language=self._ui_language, default="IPset"),
        }
        kinds: list[str] = []
        for kind in (*available_kinds, current_kind):
            normalized = str(kind or "").strip().lower()
            if normalized in labels and normalized not in kinds:
                kinds.append(normalized)
        if not kinds:
            kinds = ["hostlist"]

        current_items = [
            str(self._filter_combo.itemData(index) or "").strip().lower()
            for index in range(self._filter_combo.count())
        ]
        if current_items == kinds:
            return

        self._filter_combo.blockSignals(True)
        try:
            self._filter_combo.clear()
            for kind in kinds:
                self._filter_combo.addItem(labels[kind], userData=kind)
        finally:
            self._filter_combo.blockSignals(False)

    def _on_range_mode_changed(self, combo: ComboBox, value_edit: LineEdit) -> None:
        sync_range_value_enabled(combo, value_edit)
        if combo is self._in_range_mode:
            self._update_range_tooltips(combo, value_edit, option_name="--in-range", direction="входящих")
        elif combo is self._out_range_mode:
            self._update_range_tooltips(combo, value_edit, option_name="--out-range", direction="исходящих")
        self._schedule_settings_autosave()

    def _on_filter_kind_changed(self) -> None:
        self._sync_filter_value_for_kind()
        if self._profile_is_only_template() and self._editor_tab_built and self._strategy_stack.currentIndex() == 1:
            self._request_list_file_editor_state()
        self._schedule_settings_autosave()

    def _current_filter_kind(self) -> str:
        return str(self._filter_combo.itemData(self._filter_combo.currentIndex()) or "hostlist")

    def _current_filter_value(self) -> str:
        return self._filter_value.text().strip()

    def _profile_is_only_template(self) -> bool:
        item = getattr(self._payload, "item", None)
        return item is not None and not bool(getattr(item, "in_preset", False))

    def _sync_filter_value_for_kind(self) -> None:
        if self._loading or not is_preset_launch_method(self.launch_method):
            return
        filter_kind = self._current_filter_kind()
        filter_role = str(getattr(self._payload, "editable_filter_role", "") or "primary")
        normalized = normalize_filter_value(self._filter_value.text(), filter_kind, filter_role=filter_role)
        if normalized and normalized != self._filter_value.text().strip():
            self._filter_value.setText(normalized)

    def _schedule_settings_autosave(self) -> None:
        if self._loading or not self._profile_key or not is_preset_launch_method(self.launch_method):
            return
        if self._profile_is_only_template():
            return
        self._settings_save_timer.start()

    def _autosave_editable_settings(self) -> None:
        if self._loading or not self._profile_key or not is_preset_launch_method(self.launch_method):
            return
        filter_value = self._filter_value.text().strip()
        filter_enabled = bool(getattr(self._payload, "editable_filter_enabled", True))
        if filter_enabled and not filter_value:
            return
        request = {
            "profile_key": self._profile_key,
            "filter_kind": self._current_filter_kind(),
            "filter_value": filter_value,
            "in_range": range_expression_from_controls(self._in_range_mode, self._in_range_value, default="x"),
            "out_range": range_expression_from_controls(self._out_range_mode, self._out_range_value, default="a"),
        }
        self._request_settings_save(request)

    def _request_settings_save(self, request: dict) -> None:
        worker = self._settings_save_worker
        if worker is not None:
            try:
                if worker.isRunning():
                    self._pending_settings_save = dict(request)
                    return
            except Exception:
                return
        self._start_settings_save_worker(request)

    def _start_settings_save_worker(self, request: dict) -> None:
        self._settings_save_request_id += 1
        request_id = self._settings_save_request_id
        worker = self._controller.create_settings_save_worker(
            request_id,
            profile_key=str(request.get("profile_key") or ""),
            filter_kind=str(request.get("filter_kind") or ""),
            filter_value=str(request.get("filter_value") or ""),
            in_range=str(request.get("in_range") or ""),
            out_range=str(request.get("out_range") or ""),
            parent=self,
        )
        self._settings_save_worker = worker
        worker.saved.connect(self._on_settings_save_finished)
        worker.failed.connect(self._on_settings_save_failed)
        worker.finished.connect(lambda w=worker: self._on_settings_save_worker_finished(w))
        worker.start()

    def _on_settings_save_finished(self, request_id: int, profile_key: str, payload=None) -> None:
        if request_id != self._settings_save_request_id:
            return
        if self._pending_settings_save:
            return
        new_key = str(profile_key or "").strip()
        if new_key:
            self._profile_key = new_key
        if payload is None:
            self.reload_current_profile()
            self._on_profile_changed_callback(self._profile_key, "settings")
            return
        self._payload = payload
        self._apply_payload(payload)
        self._on_profile_changed_callback(self._profile_key, "settings", getattr(payload, "item", None))

    def _on_settings_save_failed(self, request_id: int, error: str) -> None:
        if request_id != self._settings_save_request_id:
            return
        log(f"{self.__class__.__name__}: не удалось сохранить настройки профиля: {error}", "ERROR")

    def _on_settings_save_worker_finished(self, worker) -> None:
        if self._settings_save_worker is worker:
            self._settings_save_worker = None
        worker.deleteLater()
        pending = self._pending_settings_save
        self._pending_settings_save = None
        if pending:
            self._start_settings_save_worker(pending)

    def _on_raw_profile_save_clicked(self) -> None:
        if self._loading or not self._profile_key or self._raw_profile_text is None:
            return
        worker = self._raw_profile_save_worker
        if worker is not None:
            try:
                if worker.isRunning():
                    return
            except Exception:
                return
        self._raw_profile_save_request_id += 1
        request_id = self._raw_profile_save_request_id
        if self._raw_profile_save_button is not None:
            self._raw_profile_save_button.setEnabled(False)
        worker = self._controller.create_raw_profile_save_worker(
            request_id,
            self._profile_key,
            self._raw_profile_text.toPlainText(),
            parent=self,
        )
        self._raw_profile_save_worker = worker
        worker.saved.connect(self._on_raw_profile_save_finished)
        worker.failed.connect(self._on_raw_profile_save_failed)
        worker.finished.connect(lambda w=worker: self._on_raw_profile_save_worker_finished(w))
        worker.start()

    def _on_raw_profile_save_finished(self, request_id: int, profile_key: str, payload=None) -> None:
        if request_id != self._raw_profile_save_request_id:
            return
        new_key = str(profile_key or "").strip()
        if new_key:
            self._profile_key = new_key
        if payload is None:
            self.reload_current_profile()
            self._on_profile_changed_callback(self._profile_key, "raw_profile")
        else:
            self._payload = payload
            self._apply_payload(payload)
            self._on_profile_changed_callback(self._profile_key, "raw_profile", getattr(payload, "item", None))
        InfoBar.success(
            title="Profile сохранён",
            content="Текст profile обновлён только в текущем preset.",
            parent=self.window(),
        )

    def _on_raw_profile_save_failed(self, request_id: int, error: str) -> None:
        if request_id != self._raw_profile_save_request_id:
            return
        if self._raw_profile_save_button is not None:
            self._raw_profile_save_button.setEnabled(True)
        log(f"{self.__class__.__name__}: не удалось сохранить сырой текст profile: {error}", "ERROR")
        InfoBar.error(
            title="Ошибка",
            content=str(error),
            parent=self.window(),
        )

    def _on_raw_profile_save_worker_finished(self, worker) -> None:
        if self._raw_profile_save_worker is worker:
            self._raw_profile_save_worker = None
        worker.deleteLater()

    def _on_enabled_changed(self, state: int) -> None:
        if self._loading or not self._profile_key:
            return
        enabled = bool(state == Qt.CheckState.Checked.value or state == 2)
        worker = self._enabled_save_worker
        if worker is not None:
            try:
                if worker.isRunning():
                    return
            except Exception:
                return
        self._enabled_save_request_id += 1
        request_id = self._enabled_save_request_id
        if self._enabled_checkbox is not None:
            self._enabled_checkbox.setEnabled(False)
        worker = self._controller.create_enabled_save_worker(
            request_id,
            profile_key=self._profile_key,
            enabled=enabled,
            filter_kind=self._current_filter_kind(),
            filter_value=self._current_filter_value(),
            parent=self,
        )
        self._enabled_save_worker = worker
        worker.saved.connect(self._on_enabled_save_finished)
        worker.failed.connect(self._on_enabled_save_failed)
        worker.finished.connect(lambda w=worker: self._on_enabled_save_worker_finished(w))
        worker.start()

    def _on_enabled_save_finished(self, request_id: int, profile_key: str, enabled: bool, payload=None) -> None:
        if request_id != self._enabled_save_request_id:
            return
        old_key = str(self._profile_key or "").strip()
        new_key = str(profile_key or "").strip()
        if payload is not None:
            if new_key:
                self._profile_key = new_key
            self._payload = payload
            self._apply_payload(payload)
            self._on_profile_changed_callback(
                self._profile_key,
                "enabled" if enabled else "disabled",
                getattr(payload, "item", None),
            )
            return
        if new_key and new_key != old_key:
            self._profile_key = new_key
            self.reload_current_profile()
            self._on_profile_changed_callback(self._profile_key, "enabled" if enabled else "disabled")
            return
        updated_item = self._apply_enabled_locally(enabled)
        if updated_item is None:
            self.reload_current_profile()
            self._on_profile_changed_callback(self._profile_key, "enabled" if enabled else "disabled")
            return
        self._on_profile_changed_callback(self._profile_key, "enabled" if enabled else "disabled", updated_item)

    def _apply_enabled_locally(self, enabled: bool):
        payload = self._payload
        if payload is None:
            return None
        item = getattr(payload, "item", None)
        if item is None:
            return None
        updated_item = replace(item, enabled=bool(enabled))
        self._payload = replace(payload, item=updated_item)
        checkbox = self._enabled_checkbox
        if checkbox is not None:
            self._loading = True
            try:
                checkbox.setChecked(bool(enabled))
                checkbox.setEnabled(True)
            finally:
                self._loading = False
        return updated_item

    def _on_enabled_save_failed(self, request_id: int, error: str) -> None:
        if request_id != self._enabled_save_request_id:
            return
        if self._enabled_checkbox is not None:
            self._enabled_checkbox.setEnabled(True)
        log(f"{self.__class__.__name__}: не удалось изменить состояние профиля: {error}", "ERROR")

    def _on_enabled_save_worker_finished(self, worker) -> None:
        if self._enabled_save_worker is worker:
            self._enabled_save_worker = None
        worker.deleteLater()

    def _on_strategy_list_activated(self, strategy_id: str) -> None:
        if self._loading or not self._profile_key:
            return
        strategy_id = str(strategy_id or "").strip()
        if not strategy_id or strategy_id in {"none", "custom"}:
            return
        item = getattr(getattr(self, "_payload", None), "item", None)
        if bool(getattr(item, "in_preset", False)) and not bool(getattr(item, "enabled", False)):
            return
        if strategy_id == str(getattr(item, "strategy_id", "") or "").strip():
            return
        self._apply_strategy_locally(strategy_id)
        self._request_strategy_apply(strategy_id)

    def _request_strategy_apply(self, strategy_id: str) -> None:
        strategy_id = str(strategy_id or "").strip()
        worker = getattr(self, "_strategy_apply_worker", None)
        if worker is not None:
            try:
                if worker.isRunning():
                    if strategy_id != str(getattr(self, "_strategy_apply_worker_strategy_id", "") or "").strip():
                        self._pending_strategy_apply = strategy_id
                    return
            except Exception:
                pass
        self._start_strategy_apply_worker(strategy_id)

    def _start_strategy_apply_worker(self, strategy_id: str) -> None:
        strategy_id = str(strategy_id or "").strip()
        if not strategy_id or not self._profile_key:
            return
        self._strategy_apply_request_id = int(getattr(self, "_strategy_apply_request_id", 0) or 0) + 1
        request_id = self._strategy_apply_request_id
        worker = self._controller.create_strategy_apply_worker(
            request_id,
            profile_key=self._profile_key,
            strategy_id=strategy_id,
            parent=self,
        )
        self._strategy_apply_worker = worker
        self._strategy_apply_worker_strategy_id = strategy_id
        worker.applied.connect(self._on_strategy_apply_finished)
        worker.failed.connect(self._on_strategy_apply_failed)
        worker.finished.connect(lambda w=worker: self._on_strategy_apply_worker_finished(w))
        worker.start()

    def _on_strategy_apply_finished(
        self,
        request_id: int,
        requested_profile_key: str,
        profile_key: str,
        strategy_id: str,
        payload=None,
    ) -> None:
        if request_id != int(getattr(self, "_strategy_apply_request_id", 0) or 0):
            return
        if str(requested_profile_key or "").strip() != str(self._profile_key or "").strip():
            return
        pending = str(getattr(self, "_pending_strategy_apply", "") or "").strip()
        if pending and pending != str(strategy_id or "").strip():
            return
        previous_key = self._profile_key
        new_key = str(profile_key or "").strip()
        if new_key:
            self._profile_key = new_key
        if payload is not None:
            self._payload = payload
            self._apply_payload(payload)
            self._on_profile_changed_callback(
                self._profile_key,
                "strategy",
                getattr(payload, "item", None),
            )
            return
        applied_locally = self._apply_strategy_locally(strategy_id)
        if not applied_locally or self._profile_key != previous_key:
            self.reload_current_profile()
            self._on_profile_changed_callback(self._profile_key, "strategy")
            return
        item = getattr(getattr(self, "_payload", None), "item", None)
        self._on_profile_changed_callback(self._profile_key, "strategy", item)

    def _on_strategy_apply_failed(self, request_id: int, error: str) -> None:
        if request_id != int(getattr(self, "_strategy_apply_request_id", 0) or 0):
            return
        log(f"{self.__class__.__name__}: не удалось применить стратегию: {error}", "ERROR")
        self.reload_current_profile()

    def _on_strategy_apply_worker_finished(self, worker) -> None:
        if getattr(self, "_strategy_apply_worker", None) is worker:
            self._strategy_apply_worker = None
            self._strategy_apply_worker_strategy_id = ""
        worker.deleteLater()
        pending = str(getattr(self, "_pending_strategy_apply", "") or "").strip()
        self._pending_strategy_apply = None
        if pending:
            self._start_strategy_apply_worker(pending)

    def _apply_strategy_locally(self, strategy_id: str) -> bool:
        payload = self._payload
        if payload is None:
            return False
        item = getattr(payload, "item", None)
        if item is None or not bool(getattr(item, "in_preset", False)):
            return False
        entry = (getattr(payload, "strategy_entries", {}) or {}).get(strategy_id)
        if entry is None:
            return False

        state = (getattr(payload, "strategy_states", {}) or {}).get(strategy_id, ProfileStrategyState())
        updated_item = replace(
            item,
            strategy_id=strategy_id,
            strategy_name=str(getattr(entry, "name", "") or strategy_id),
            enabled=True,
            rating=str(getattr(state, "rating", "") or ""),
            favorite=bool(getattr(state, "favorite", False)),
        )
        self._payload = replace(
            payload,
            item=updated_item,
            raw_strategy_text=str(getattr(entry, "args", "") or ""),
            current_strategy_state=state,
        )
        self._strategy_list.set_current_strategy_id(strategy_id)
        self._apply_feedback_buttons(self._payload)
        if self._match_tab_built:
            self._apply_match_tab_payload()
        self._rebuild_breadcrumb()
        return True

    def _set_current_strategy_feedback(self, *, rating: str) -> None:
        if self._loading or not self._profile_key:
            return
        self._request_strategy_feedback_save({"rating": rating, "favorite": None})

    def _toggle_current_strategy_favorite(self) -> None:
        if self._loading or not self._profile_key or self._payload is None:
            return
        current = bool(self._payload.current_strategy_state.favorite)
        self._request_strategy_feedback_save({"rating": None, "favorite": not current})

    def _request_strategy_feedback_save(self, request: dict) -> None:
        worker = getattr(self, "_strategy_feedback_save_worker", None)
        if worker is not None:
            try:
                if worker.isRunning():
                    self._pending_strategy_feedback_save = dict(request)
                    return
            except Exception:
                pass
        self._start_strategy_feedback_save_worker(request)

    def _start_strategy_feedback_save_worker(self, request: dict) -> None:
        if not self._profile_key:
            return
        item = getattr(getattr(self, "_payload", None), "item", None)
        strategy_id = str(getattr(item, "strategy_id", "") or "").strip()
        if not strategy_id or strategy_id in {"none", "custom"}:
            return
        self._strategy_feedback_save_request_id = int(getattr(self, "_strategy_feedback_save_request_id", 0) or 0) + 1
        request_id = self._strategy_feedback_save_request_id
        worker = self._controller.create_strategy_feedback_save_worker(
            request_id,
            profile_key=self._profile_key,
            strategy_id=strategy_id,
            rating=request.get("rating"),
            favorite=request.get("favorite"),
            parent=self,
        )
        self._strategy_feedback_save_worker = worker
        worker.saved.connect(self._on_strategy_feedback_save_finished)
        worker.failed.connect(self._on_strategy_feedback_save_failed)
        worker.finished.connect(lambda w=worker: self._on_strategy_feedback_save_worker_finished(w))
        worker.start()

    def _on_strategy_feedback_save_finished(
        self,
        request_id: int,
        profile_key: str,
        strategy_id: str,
        state,
    ) -> None:
        if request_id != int(getattr(self, "_strategy_feedback_save_request_id", 0) or 0):
            return
        if self.__dict__.get("_pending_strategy_feedback_save"):
            return
        if str(profile_key or "").strip() != str(self._profile_key or "").strip():
            return
        item = getattr(getattr(self, "_payload", None), "item", None)
        current_strategy_id = str(getattr(item, "strategy_id", "") or "").strip()
        if str(strategy_id or "").strip() != current_strategy_id:
            return
        if not self._apply_strategy_feedback_locally(state):
            self.reload_current_profile()
            self._on_profile_changed_callback(self._profile_key, "feedback")
            return
        item = getattr(getattr(self, "_payload", None), "item", None)
        self._on_profile_changed_callback(self._profile_key, "feedback", item)

    def _on_strategy_feedback_save_failed(self, request_id: int, error: str) -> None:
        if request_id != int(getattr(self, "_strategy_feedback_save_request_id", 0) or 0):
            return
        log(f"{self.__class__.__name__}: не удалось обновить оценку стратегии: {error}", "ERROR")
        if not self.__dict__.get("_pending_strategy_feedback_save"):
            self.reload_current_profile()

    def _on_strategy_feedback_save_worker_finished(self, worker) -> None:
        if getattr(self, "_strategy_feedback_save_worker", None) is worker:
            self._strategy_feedback_save_worker = None
        worker.deleteLater()
        pending = self.__dict__.get("_pending_strategy_feedback_save")
        self._pending_strategy_feedback_save = None
        if pending:
            self._start_strategy_feedback_save_worker(pending)

    def cleanup(self) -> None:
        self._cleanup_in_progress = True
        timer = self.__dict__.get("_settings_save_timer")
        if timer is not None:
            try:
                timer.stop()
            except Exception:
                pass
        for attr in (
            "_pending_list_file_validation",
            "_pending_settings_save",
            "_pending_strategy_apply",
            "_pending_strategy_feedback_save",
        ):
            setattr(self, attr, None)
        for attr in (
            "_setup_load_request_id",
            "_list_file_load_request_id",
            "_list_file_save_request_id",
            "_list_file_validation_request_id",
            "_settings_save_request_id",
            "_raw_profile_save_request_id",
            "_enabled_save_request_id",
            "_user_profile_update_request_id",
            "_user_profile_delete_request_id",
            "_strategy_apply_request_id",
            "_strategy_feedback_save_request_id",
        ):
            setattr(self, attr, int(getattr(self, attr, 0) or 0) + 1)
        for attr in (
            "_setup_load_worker",
            "_list_file_load_worker",
            "_list_file_save_worker",
            "_list_file_validation_worker",
            "_settings_save_worker",
            "_raw_profile_save_worker",
            "_enabled_save_worker",
            "_user_profile_update_worker",
            "_user_profile_delete_worker",
            "_strategy_apply_worker",
            "_strategy_feedback_save_worker",
        ):
            worker = self.__dict__.get(attr)
            if worker is None:
                continue
            try:
                worker.quit()
            except Exception:
                pass
            setattr(self, attr, None)
        self._strategy_apply_worker_strategy_id = ""
        try:
            super().cleanup()
        except Exception:
            pass

    def _apply_strategy_feedback_locally(self, state) -> bool:
        if self._payload is None or state is None:
            return False
        item = getattr(self._payload, "item", None)
        if item is None:
            return False
        strategy_id = str(getattr(item, "strategy_id", "") or "").strip()
        if not strategy_id or strategy_id in {"none", "custom"}:
            return False
        next_state = state if isinstance(state, ProfileStrategyState) else ProfileStrategyState()
        strategy_states = dict(getattr(self._payload, "strategy_states", {}) or {})
        strategy_states[strategy_id] = next_state
        updated_item = replace(
            item,
            rating=str(getattr(next_state, "rating", "") or ""),
            favorite=bool(getattr(next_state, "favorite", False)),
        )
        self._payload = replace(
            self._payload,
            item=updated_item,
            strategy_states=strategy_states,
            current_strategy_state=next_state,
        )
        if self._strategy_list is not None:
            self._strategy_list.set_rows(
                entries=getattr(self._payload, "strategy_entries", {}) or {},
                states=strategy_states,
                current_strategy_id=strategy_id,
            )
        self._apply_feedback_buttons(self._payload)
        return True


class Zapret2ProfileSetupPage(ProfileSetupPageBase):
    launch_method = ZAPRET2_MODE
    title_key_name = "page.winws2_profile_setup.title"
    control_key = "page.winws2_profile_setup.breadcrumb.control"
    profiles_key = "page.winws2_pages.title"
    profiles_default = "Настройка пресета"


class Zapret1ProfileSetupPage(ProfileSetupPageBase):
    launch_method = ZAPRET1_MODE
    title_key_name = "page.winws1_profile_setup.title"
    control_key = "page.winws1_profile_setup.breadcrumb.control"
    profiles_key = "page.winws1_pages.title"
    profiles_default = "Настройка пресета"


def _protocol_and_ports_from_match_lines(match_lines: tuple[str, ...]) -> tuple[str, str]:
    for protocol, option_name in (("tcp", "--filter-tcp"), ("udp", "--filter-udp"), ("l7", "--filter-l7")):
        values = filter_values(match_lines, option_name)
        if values:
            return protocol, values[0]
    return "tcp", ""


def _user_profile_id_from_payload(profile_key: str, payload) -> str:
    item = getattr(payload, "item", None)
    profile_id = str(getattr(item, "user_profile_id", "") or "").strip()
    if profile_id:
        return profile_id
    key = str(profile_key or "").strip()
    if key.startswith("template:user:"):
        return key.split("template:user:", 1)[1].strip()
    return ""


def _updated_user_profile_item(profile_id: str, profile_key: str, profile_items):
    clean_profile_id = str(profile_id or "").strip()
    clean_profile_key = str(profile_key or "").strip()
    candidates = tuple(profile_items or ())
    for item in candidates:
        if clean_profile_key and str(getattr(item, "key", "") or "").strip() == clean_profile_key:
            return item
    for item in candidates:
        if clean_profile_id and str(getattr(item, "user_profile_id", "") or "").strip() == clean_profile_id:
            return item
    return None
