from __future__ import annotations

from dataclasses import replace

from PyQt6.QtCore import QModelIndex, QRect, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFontMetrics, QPainter, QTextCursor
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
from profile.setup_match_text import build_profile_setup_match_tab_text
from profile.ui.profile_setup_controls import (
    range_expression_from_controls,
    set_combo_by_data,
    set_range_controls,
    sync_range_value_enabled,
)
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
from ui.accessibility import set_control_accessibility, set_state_text
from ui.fluent_widgets import set_tooltip
from ui.latest_value_worker_state import LatestValueWorkerState
from ui.one_shot_worker_runtime import OneShotWorkerRuntime
from app.ui_texts import tr as tr_catalog
from ui.theme import get_cached_qta_pixmap, get_theme_tokens, to_qcolor
from ui.widgets.fluent_item_tooltip import FluentItemToolTipController
from ui.widgets.fluent_scrollbar import install_fluent_scrollbars
from ui.widgets.hover_row import paint_profile_hover_row, profile_hover_row_rect


_PROFILE_SETUP_CLEANUP_RUNTIMES = (
    ("_setup_load_runtime", "profile setup load worker", False),
    ("_list_file_load_runtime", "profile list file load worker", False),
    ("_list_file_validation_runtime", "profile list file validation worker", False),
    ("_list_file_save_runtime", "profile list file save worker", True),
    ("_settings_save_runtime", "profile settings save worker", True),
    ("_raw_profile_save_runtime", "profile raw text save worker", True),
    ("_enabled_save_runtime", "profile enabled save worker", True),
    ("_user_profile_update_runtime", "profile user update worker", True),
    ("_user_profile_delete_runtime", "profile user delete worker", True),
    ("_strategy_apply_runtime", "profile strategy apply worker", True),
    ("_strategy_feedback_save_runtime", "profile strategy feedback save worker", True),
)


def set_widget_text_if_changed(widget, text: str) -> bool:
    value = str(text or "")
    try:
        if str(widget.text()) == value:
            return False
    except Exception:
        pass
    widget.setText(value)
    return True


def set_widget_checked_if_changed(widget, checked: bool) -> bool:
    value = bool(checked)
    try:
        if bool(widget.isChecked()) == value:
            return False
    except Exception:
        pass
    widget.setChecked(value)
    return True


def set_widget_enabled_if_changed(widget, enabled: bool) -> bool:
    value = bool(enabled)
    try:
        if bool(widget.isEnabled()) == value:
            return False
    except Exception:
        pass
    widget.setEnabled(value)
    return True


def set_widget_visible_if_changed(widget, visible: bool) -> bool:
    value = bool(visible)
    try:
        if bool(widget.isVisible()) == value:
            return False
    except Exception:
        pass
    widget.setVisible(value)
    return True


def set_widget_property_if_changed(widget, name: str, value) -> bool:
    key = str(name or "")
    try:
        if widget.property(key) == value:
            return False
    except Exception:
        pass
    widget.setProperty(key, value)
    return True


def set_profile_list_status_text(label, text: str) -> bool:
    changed = set_widget_text_if_changed(label, text)
    set_state_text(label, f"Статус списка profile: {text}")
    return changed


def set_profile_list_error_text(label, text: str) -> bool:
    changed = set_widget_text_if_changed(label, text)
    value = " ".join(str(text or "").strip().split())
    if value:
        set_state_text(label, f"Ошибка списка profile: {value}")
    return changed


def set_widget_style_sheet_if_changed(widget, style: str) -> bool:
    value = str(style or "")
    try:
        if str(widget.styleSheet()) == value:
            return False
    except Exception:
        pass
    widget.setStyleSheet(value)
    return True


def set_read_only_if_changed(widget, read_only: bool) -> bool:
    value = bool(read_only)
    try:
        if bool(widget.isReadOnly()) == value:
            return False
    except Exception:
        pass
    widget.setReadOnly(value)
    return True


def set_placeholder_text_if_changed(widget, text: str) -> bool:
    value = str(text or "")
    try:
        if str(widget.placeholderText()) == value:
            return False
    except Exception:
        pass
    widget.setPlaceholderText(value)
    return True


def set_current_index_if_changed(widget, index: int) -> bool:
    value = int(index)
    try:
        if int(widget.currentIndex()) == value:
            return False
    except Exception:
        pass
    widget.setCurrentIndex(value)
    return True


def set_segmented_current_item_if_changed(widget, item_key: str) -> bool:
    value = str(item_key or "")
    try:
        if str(widget.currentItem()) == value:
            return False
    except Exception:
        pass
    widget.setCurrentItem(value)
    return True


def set_tab_item_text_if_changed(widget, item_key: str, text: str) -> bool:
    route_key = str(item_key or "")
    value = str(text or "")
    try:
        if str(widget.itemText(route_key)) == value:
            return False
    except Exception:
        pass
    widget.setItemText(route_key, value)
    return True


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
            set_widget_text_if_changed(self, compact)


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
        set_control_accessibility(self._search, name="Поиск готовых стратегий")
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
        self._list.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        set_control_accessibility(
            self._list,
            name="Список готовых стратегий",
            description="Выберите готовую стратегию стрелками вверх и вниз, затем нажмите Enter.",
        )
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
            status_parts = _strategy_status_parts(state, is_current=is_current, include_unselected=False)
            accessible_status_parts = _strategy_status_parts(state, is_current=is_current, include_unselected=True)
            status_text = " • ".join(status_parts)

            item.setText(name)
            item.setData(self._ROLE_STRATEGY_ID, strategy_id)
            item.setData(self._ROLE_NAME_TEXT, name)
            item.setData(self._ROLE_STATUS_TEXT, status_text)
            item.setData(self._ROLE_IS_ACTIVE, is_current)
            item.setData(self._ROLE_VISUAL_ICON_NAME, str(visual.icon_name or ""))
            item.setData(self._ROLE_VISUAL_COLOR, str(visual.color or ""))
            item.setData(self._ROLE_VISUAL_LABEL_TEXT, visual_label)
            item.setData(self._ROLE_VISUAL_DESCRIPTION, visual_description)
            item.setData(
                Qt.ItemDataRole.AccessibleTextRole,
                _strategy_screen_reader_text(
                    name=name,
                    status_parts=accessible_status_parts,
                    visual_label=visual_label,
                    visual_description=visual_description,
                ),
            )
            tooltip_parts = [visual_description.strip(), args]
            item.setData(self._ROLE_TOOLTIP_TEXT, "\n\n".join(part for part in tooltip_parts if part))
            item.setSizeHint(QSize(0, 31))
            if is_current:
                current_item = item
            self._item_by_strategy_id[strategy_id] = item
            self._list.addItem(item)
            visible += 1

        set_widget_text_if_changed(self._summary, f"{visible} из {len(self._entries)}")
        if current_item is not None:
            self._list.setCurrentItem(current_item)
            current_item.setSelected(True)

    def _refresh_strategy_item(self, item, strategy_id: str, *, is_current: bool) -> None:
        if item is None:
            return
        state = self._states.get(strategy_id)
        status_parts = _strategy_status_parts(state, is_current=is_current, include_unselected=False)
        accessible_status_parts = _strategy_status_parts(state, is_current=is_current, include_unselected=True)
        changed = False
        status_text = " • ".join(status_parts)
        if str(item.data(self._ROLE_STATUS_TEXT) or "") != status_text:
            item.setData(self._ROLE_STATUS_TEXT, status_text)
            changed = True
        if bool(item.data(self._ROLE_IS_ACTIVE)) != bool(is_current):
            item.setData(self._ROLE_IS_ACTIVE, is_current)
            changed = True
        if is_current:
            try:
                if self._list.currentItem() is not item:
                    self._list.setCurrentItem(item)
                    changed = True
            except Exception:
                self._list.setCurrentItem(item)
                changed = True
            try:
                selected = bool(item.isSelected())
            except Exception:
                selected = False
            if not selected:
                item.setSelected(True)
                changed = True
        else:
            try:
                selected = bool(item.isSelected())
            except Exception:
                selected = True
            if selected:
                item.setSelected(False)
                changed = True
        name = str(item.data(self._ROLE_NAME_TEXT) or "")
        if name:
            accessible_text = _strategy_screen_reader_text(
                name=name,
                status_parts=accessible_status_parts,
                visual_label=str(item.data(self._ROLE_VISUAL_LABEL_TEXT) or ""),
                visual_description=str(item.data(self._ROLE_VISUAL_DESCRIPTION) or ""),
            )
            if str(item.data(Qt.ItemDataRole.AccessibleTextRole) or "") != accessible_text:
                item.setData(Qt.ItemDataRole.AccessibleTextRole, accessible_text)
                changed = True
        if changed:
            self._list.viewport().update(self._list.visualItemRect(item))

    def _apply_filter(self) -> None:
        self._rebuild_tree()

    def _strategy_id_for_item(self, item) -> str:
        return str(item.data(self._ROLE_STRATEGY_ID) or "").strip() if item is not None else ""

    def _on_item_clicked(self, item) -> None:
        strategy_id = self._strategy_id_for_item(item)
        if strategy_id == self._current_strategy_id:
            return
        if strategy_id:
            self.strategy_activated.emit(strategy_id)

    def _on_item_activated(self, item) -> None:
        strategy_id = self._strategy_id_for_item(item)
        if strategy_id == self._current_strategy_id:
            return
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


def _strategy_status_parts(state, *, is_current: bool, include_unselected: bool) -> list[str]:
    status_parts = []
    if is_current:
        status_parts.append("Выбрана")
    elif include_unselected:
        status_parts.append("Не выбрана")
    if bool(getattr(state, "favorite", False)):
        status_parts.append("В избранном")
    rating = str(getattr(state, "rating", "") or "")
    if rating == "work":
        status_parts.append("Работает")
    elif rating == "notwork":
        status_parts.append("Не работает")
    return status_parts


def _set_strategy_feedback_button_state(button, *, action_name: str, selected: bool) -> None:
    state_text = "выбрана" if selected else "не выбрана"
    set_state_text(button, f"{action_name}. Оценка стратегии: {state_text}.")


def _set_strategy_favorite_button_state(button, *, action_name: str, favorite: bool) -> None:
    state_text = "включено" if favorite else "не включено"
    set_state_text(button, f"{action_name}. Избранное: {state_text}.")


def _set_strategy_clear_feedback_button_state(button, *, rating: str) -> None:
    rating_value = str(rating or "").strip()
    if rating_value == "work":
        rating_text = "работает"
    elif rating_value == "notwork":
        rating_text = "не работает"
    else:
        rating_text = "не задана"
    set_state_text(button, f"Убрать оценку стратегии. Текущая оценка: {rating_text}.")


def _strategy_screen_reader_text(
    *,
    name: str,
    status_parts: list[str],
    visual_label: str,
    visual_description: str,
) -> str:
    parts = [str(name or "").strip()]
    parts.extend(_lower_first(part) for part in status_parts if str(part or "").strip())
    parts.extend(
        str(part or "").strip()
        for part in (visual_label, visual_description)
        if str(part or "").strip()
    )
    return ", ".join(part for part in parts if part)


def _lower_first(text: str) -> str:
    value = str(text or "").strip()
    if not value:
        return ""
    return value[:1].lower() + value[1:]


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


def _current_strategy_branch(payload):
    branches = tuple(getattr(payload, "strategy_branches", ()) or ())
    if not branches:
        return None
    current_id = str(getattr(payload, "current_strategy_branch_id", "") or "").strip()
    for branch in branches:
        if str(getattr(branch, "branch_id", "") or "").strip() == current_id:
            return branch
    return branches[0]


def _current_strategy_id(payload) -> str:
    branch = _current_strategy_branch(payload)
    if branch is not None:
        return str(getattr(branch, "strategy_id", "") or "").strip()
    item = getattr(payload, "item", None)
    return str(getattr(item, "strategy_id", "") or "").strip()


def _current_strategy_branch_id(payload) -> str:
    branch = _current_strategy_branch(payload)
    return str(getattr(branch, "branch_id", "") or "").strip() if branch is not None else ""


def _payload_with_strategy_branch(payload, branch_id: str):
    clean_branch_id = str(branch_id or "").strip()
    branches = tuple(getattr(payload, "strategy_branches", ()) or ())
    branch = next(
        (
            item
            for item in branches
            if str(getattr(item, "branch_id", "") or "").strip() == clean_branch_id
        ),
        None,
    )
    if branch is None:
        return payload
    states = getattr(payload, "strategy_states", {}) or {}
    strategy_id = str(getattr(branch, "strategy_id", "") or "").strip()
    return replace(
        payload,
        current_strategy_branch_id=clean_branch_id,
        raw_strategy_text=str(getattr(branch, "raw_strategy_text", "") or ""),
        match_tab_text=str(getattr(branch, "match_tab_text", "") or ""),
        current_strategy_state=states.get(strategy_id, ProfileStrategyState()),
    )


def _strategy_branch_label(branch) -> str:
    payload = str(getattr(branch, "payload", "") or "all").strip() or "all"
    in_range = str(getattr(branch, "in_range", "") or "x").strip() or "x"
    out_range = str(getattr(branch, "out_range", "") or "a").strip() or "a"
    strategy_name = str(getattr(branch, "strategy_name", "") or "Своя стратегия").strip()
    parts = [f"payload: {payload}"]
    if in_range != "x":
        parts.append(f"in: {in_range}")
    if out_range != "a":
        parts.append(f"out: {out_range}")
    return f"{' · '.join(parts)} — {strategy_name}"


def _update_strategy_branch_combo_in_place(
    combo,
    rows: tuple[tuple[str, str], ...] | list[tuple[str, str]],
    selected_index: int,
) -> bool:
    try:
        if int(combo.count()) != len(rows):
            return False
        for index, (branch_id, _label) in enumerate(rows):
            if str(combo.itemData(index) or "").strip() != str(branch_id or "").strip():
                return False
        for index, (_branch_id, label) in enumerate(rows):
            if str(combo.itemText(index) or "") != str(label or ""):
                combo.setItemText(index, str(label or ""))
        if int(combo.currentIndex()) != int(selected_index):
            combo.setCurrentIndex(int(selected_index))
        return True
    except Exception:
        return False


def _branch_raw_strategy_text(branch, strategy_args: str) -> str:
    lines = []
    in_range = str(getattr(branch, "in_range", "") or "x").strip() or "x"
    out_range = str(getattr(branch, "out_range", "") or "a").strip() or "a"
    payload = str(getattr(branch, "payload", "") or "all").strip() or "all"
    if in_range != "x":
        lines.append(f"--in-range={in_range}")
    if out_range != "a":
        lines.append(f"--out-range={out_range}")
    if payload != "all":
        lines.append(f"--payload={payload}")
    clean_strategy_args = str(strategy_args or "").strip()
    if clean_strategy_args:
        lines.append(clean_strategy_args)
    return "\n".join(lines).strip()


def _branch_match_tab_text(payload, branch, raw_strategy_text: str) -> str:
    return build_profile_setup_match_tab_text(
        match_summary=str(getattr(payload, "match_summary", "") or ""),
        strategy_id=str(getattr(branch, "strategy_id", "") or ""),
        strategy_name=str(getattr(branch, "strategy_name", "") or ""),
        raw_strategy_text=raw_strategy_text,
    )


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


def _profile_setup_payload_from_worker_result(result):
    return getattr(result, "payload", result)


def _profile_setup_apply_signature_from_worker_result(result):
    apply_signature = getattr(result, "apply_signature", None)
    return tuple(apply_signature) if apply_signature is not None else None


def _profile_setup_payload_and_apply_signature(result):
    return (
        _profile_setup_payload_from_worker_result(result),
        _profile_setup_apply_signature_from_worker_result(result),
    )


def _non_negative_int(value, default: int = 0) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return max(0, int(default))


class ProfileSetupPageBase(BasePage):
    launch_method = ZAPRET2_MODE
    title_key_name = "page.winws2_profile_setup.title"
    control_key = "page.winws2_profile_setup.breadcrumb.control"
    profiles_key = "page.winws2_pages.title"
    profiles_default = "Настройка пресета"

    def __init__(
        self,
        parent=None,
        *,
        create_profile_setup_load_worker,
        create_profile_list_file_load_worker,
        create_profile_list_file_save_worker,
        create_profile_list_file_validation_worker,
        create_profile_settings_save_worker,
        create_profile_raw_text_save_worker,
        create_profile_enabled_save_worker,
        create_profile_user_update_worker,
        create_profile_user_delete_worker,
        create_profile_strategy_apply_worker,
        create_profile_strategy_feedback_save_worker,
        open_profiles,
        open_root,
        on_profile_changed,
    ):
        super().__init__(
            title="",
            parent=parent,
            title_key=self.title_key_name,
        )
        self._create_profile_setup_load_worker_fn = create_profile_setup_load_worker
        self._create_profile_list_file_load_worker_fn = create_profile_list_file_load_worker
        self._create_profile_list_file_save_worker_fn = create_profile_list_file_save_worker
        self._create_profile_list_file_validation_worker_fn = create_profile_list_file_validation_worker
        self._create_profile_settings_save_worker_fn = create_profile_settings_save_worker
        self._create_profile_raw_text_save_worker_fn = create_profile_raw_text_save_worker
        self._create_profile_enabled_save_worker_fn = create_profile_enabled_save_worker
        self._create_profile_user_update_worker_fn = create_profile_user_update_worker
        self._create_profile_user_delete_worker_fn = create_profile_user_delete_worker
        self._create_profile_strategy_apply_worker_fn = create_profile_strategy_apply_worker
        self._create_profile_strategy_feedback_save_worker_fn = create_profile_strategy_feedback_save_worker
        self._open_profiles = open_profiles
        self._open_root = open_root
        self._on_profile_changed_callback = on_profile_changed
        self._profile_key = ""
        self._loading = False
        self._setup_load_runtime = OneShotWorkerRuntime()
        self._setup_load_request_id = 0
        self._setup_load_runtime_worker = None
        self._setup_load_dirty = False
        self._setup_load_start_scheduled = False
        self._list_file_load_runtime = OneShotWorkerRuntime()
        self._list_file_load_request_id = 0
        self._list_file_load_runtime_worker = None
        self._list_file_load_state = LatestValueWorkerState(
            self._list_file_load_runtime,
            empty_value=False,
        )
        self._list_file_state_apply_scheduled = False
        self._pending_list_file_state_apply = None
        self._list_file_save_runtime = OneShotWorkerRuntime()
        self._list_file_save_request_id = 0
        self._list_file_save_runtime_worker = None
        self._list_file_save_state = LatestValueWorkerState(
            self._list_file_save_runtime,
            empty_value=None,
        )
        self._list_file_validation_runtime = OneShotWorkerRuntime()
        self._list_file_validation_request_id = 0
        self._list_file_validation_runtime_worker = None
        self._list_file_validation_state = LatestValueWorkerState(
            self._list_file_validation_runtime,
            empty_value=None,
        )
        self._settings_save_runtime = OneShotWorkerRuntime()
        self._settings_save_request_id = 0
        self._settings_save_runtime_worker = None
        self._pending_settings_save = None
        self._raw_profile_save_runtime = OneShotWorkerRuntime()
        self._raw_profile_save_request_id = 0
        self._raw_profile_save_runtime_worker = None
        self._raw_profile_save_state = LatestValueWorkerState(
            self._raw_profile_save_runtime,
            empty_value=None,
        )
        self._enabled_save_runtime = OneShotWorkerRuntime()
        self._enabled_save_request_id = 0
        self._enabled_save_runtime_worker = None
        self._enabled_save_runtime_enabled: bool | None = None
        self._enabled_save_state = LatestValueWorkerState(
            self._enabled_save_runtime,
            empty_value=None,
        )
        self._user_profile_update_runtime = OneShotWorkerRuntime()
        self._user_profile_update_request_id = 0
        self._user_profile_update_runtime_worker = None
        self._pending_user_profile_updates: list[dict[str, str]] = []
        self._user_profile_delete_runtime = OneShotWorkerRuntime()
        self._user_profile_delete_request_id = 0
        self._user_profile_delete_runtime_worker = None
        self._pending_user_profile_deletes: list[str] = []
        self._pending_user_profile_operations: list[dict[str, str]] = []
        self._user_profile_write_operation_start_scheduled = False
        self._strategy_apply_runtime = OneShotWorkerRuntime()
        self._strategy_apply_request_id = 0
        self._strategy_apply_runtime_worker = None
        self._strategy_apply_runtime_strategy_id = ""
        self._strategy_apply_runtime_branch_id = ""
        self._pending_strategy_apply = None
        self._scheduled_profile_setup_write_operation = None
        self._pending_profile_setup_write_operations: list[dict[str, object]] = []
        self._profile_setup_write_operation_start_scheduled = False
        self._strategy_feedback_save_runtime = OneShotWorkerRuntime()
        self._strategy_feedback_save_request_id = 0
        self._strategy_feedback_save_runtime_worker = None
        self._pending_strategy_feedback_save = None
        self._strategy_feedback_save_start_scheduled = False
        self._payload = None
        self._profile_setup_payload_apply_scheduled = False
        self._pending_profile_setup_payload_apply = None
        self._strategy_stack = None
        self._strategy_tabs = None
        self._strategy_list = None
        self._strategy_branch_bar = None
        self._strategy_branch_combo = None
        self._strategy_tab = None
        self._list_file_editor_placeholder = None
        self._match_tab_placeholder = None
        self._editor_tab_available = True
        self._editor_tab_built = False
        self._match_tab_built = False
        self._list_file_dirty = True
        self._match_text = None
        self._match_text_snapshot = ""
        self._settings_container = None
        self._work_button = None
        self._notwork_button = None
        self._favorite_button = None
        self._clear_feedback_button = None
        self._update_user_profile_button = None
        self._delete_user_profile_button = None
        self._raw_profile_text = None
        self._raw_profile_text_cache: str | None = None
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
        self._list_file_base_text_snapshot = ""
        self._list_file_text_snapshot = ""
        self._list_file_text_dirty = True
        self._list_file_text_cache_update_suspended = False
        self._list_file_user_entries_count = 0
        self._list_file_base_entries_count = 0
        self._list_file_normal_style = ""
        self._list_file_error_style = ""
        self._list_file_validation_timer = QTimer(self)
        self._list_file_validation_timer.setSingleShot(True)
        self._list_file_validation_timer.timeout.connect(self._run_scheduled_list_file_validation)
        self._settings_save_timer = QTimer(self)
        self._settings_save_timer.setSingleShot(True)
        self._settings_save_timer.setInterval(350)
        self._settings_save_timer.timeout.connect(self._autosave_editable_settings)
        self._build_content()

    def _worker_runtime(self, attr: str) -> OneShotWorkerRuntime:
        runtime = self.__dict__.get(attr)
        if runtime is None:
            runtime = OneShotWorkerRuntime()
            setattr(self, attr, runtime)
        return runtime

    def _accept_current_profile_setup_worker_finished(self, attr: str, worker) -> bool:
        missing = object()
        current_worker = self.__dict__.get(attr, missing)
        if current_worker is missing:
            setattr(self, attr, None)
            return True
        if worker is not current_worker:
            return False
        setattr(self, attr, None)
        return True

    def _profile_setup_write_is_running(self) -> bool:
        if self.__dict__.get("_profile_setup_write_operation_start_scheduled", False):
            return True
        for attr in (
            "_list_file_save_runtime",
            "_settings_save_runtime",
            "_raw_profile_save_runtime",
            "_enabled_save_runtime",
            "_strategy_apply_runtime",
        ):
            runtime = self.__dict__.get(attr)
            if runtime is not None and runtime.is_running():
                return True
        if self._enabled_save_state_obj().start_scheduled:
            return True
        if self._list_file_save_state_obj().start_scheduled:
            return True
        return False

    def _queue_profile_setup_write_operation(self, operation: dict[str, object]) -> None:
        queued = dict(operation)
        scheduled = self.__dict__.get("_scheduled_profile_setup_write_operation")
        if (
            self.__dict__.get("_profile_setup_write_operation_start_scheduled", False)
            and isinstance(scheduled, dict)
            and scheduled.get("kind") == queued.get("kind")
        ):
            self._scheduled_profile_setup_write_operation = queued
            return
        pending = self.__dict__.setdefault("_pending_profile_setup_write_operations", [])
        if pending and pending[-1] == queued:
            return
        if pending and pending[-1].get("kind") == queued.get("kind"):
            pending[-1] = queued
            return
        pending.append(queued)

    def _start_next_profile_setup_write_operation(self) -> bool:
        if self.__dict__.get("_cleanup_in_progress"):
            return False
        if self._profile_setup_write_is_running():
            return False
        pending = self.__dict__.setdefault("_pending_profile_setup_write_operations", [])
        if not pending:
            return False
        operation = dict(pending.pop(0))
        self._schedule_profile_setup_write_operation_start(operation)
        return True

    def _schedule_profile_setup_write_operation_start(self, operation: dict[str, object]) -> None:
        queued = dict(operation or {})
        if self.__dict__.get("_cleanup_in_progress"):
            return
        if self.__dict__.get("_profile_setup_write_operation_start_scheduled", False):
            self._queue_profile_setup_write_operation(queued)
            return
        self._scheduled_profile_setup_write_operation = queued
        self._profile_setup_write_operation_start_scheduled = True
        try:
            QTimer.singleShot(0, self._run_profile_setup_write_operation)
        except Exception:
            self._run_profile_setup_write_operation()

    def _run_profile_setup_write_operation(self, operation: dict[str, object] | None = None) -> bool:
        self._profile_setup_write_operation_start_scheduled = False
        if operation is None:
            operation = self.__dict__.get("_scheduled_profile_setup_write_operation")
        self._scheduled_profile_setup_write_operation = None
        operation = dict(operation or {})
        if self.__dict__.get("_cleanup_in_progress"):
            return False
        if self._profile_setup_write_is_running():
            self._queue_profile_setup_write_operation(operation)
            return False
        kind = str(operation.get("kind") or "")
        if kind == "list_file_save":
            self._pending_list_file_save = None
            self._start_list_file_save_worker(
                str(operation.get("profile_key") or ""),
                str(operation.get("text") or ""),
            )
            return True
        if kind == "settings_save":
            self._pending_settings_save = None
            request = operation.get("request")
            self._start_settings_save_worker(dict(request if isinstance(request, dict) else {}))
            return True
        if kind == "raw_profile_save":
            self._pending_raw_profile_save = None
            self._start_raw_profile_save_worker(
                str(operation.get("profile_key") or ""),
                operation.get("text"),
            )
            return True
        if kind == "enabled_save":
            self._pending_enabled_save = None
            self._start_enabled_save_worker(bool(operation.get("enabled")))
            return True
        if kind == "strategy_apply":
            self._pending_strategy_apply = None
            self._start_strategy_apply_worker(
                str(operation.get("strategy_id") or ""),
                strategy_branch_id=str(operation.get("branch_id") or ""),
            )
            return True
        return False

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
        self._enabled_checkbox.stateChanged.connect(self._update_profile_setup_accessibility)
        header_layout.addWidget(self._enabled_checkbox, 0, Qt.AlignmentFlag.AlignRight)
        self._update_user_profile_button = PushButton("Изменить", icon=FluentIcon.EDIT)
        set_control_accessibility(
            self._update_user_profile_button,
            name="Изменить пользовательский profile",
            description="Открывает изменение пользовательского profile и обновляет связанные preset-ы.",
        )
        self._update_user_profile_button.clicked.connect(self._on_update_user_profile_clicked)
        self._update_user_profile_button.hide()
        header_layout.addWidget(self._update_user_profile_button, 0, Qt.AlignmentFlag.AlignRight)
        self._delete_user_profile_button = PushButton("Удалить", icon=FluentIcon.DELETE)
        set_control_accessibility(
            self._delete_user_profile_button,
            name="Удалить пользовательский profile",
            description="Удаляет пользовательский profile, его списки и связанные записи из preset-ов.",
        )
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
        set_control_accessibility(
            self._filter_value,
            name="Файл списка profile",
            description="Путь к hostlist или ipset файлу для текущего profile.",
        )
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
        set_control_accessibility(
            self._in_range_value,
            name="Значение in-range",
            description="Число или выражение для --in-range.",
        )
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
        set_control_accessibility(
            self._out_range_value,
            name="Значение out-range",
            description="Число или выражение для --out-range.",
        )
        settings_layout.addWidget(self._out_range_value)

        self._in_range_mode.currentIndexChanged.connect(
            lambda _index: self._on_range_mode_changed(self._in_range_mode, self._in_range_value)
        )
        self._in_range_mode.currentIndexChanged.connect(self._update_profile_setup_accessibility)
        self._out_range_mode.currentIndexChanged.connect(
            lambda _index: self._on_range_mode_changed(self._out_range_mode, self._out_range_value)
        )
        self._out_range_mode.currentIndexChanged.connect(self._update_profile_setup_accessibility)
        self._filter_combo.currentIndexChanged.connect(lambda _index: self._on_filter_kind_changed())
        self._filter_combo.currentIndexChanged.connect(self._update_profile_setup_accessibility)
        self._filter_value.textEdited.connect(lambda _text: self._schedule_settings_autosave())
        self._in_range_value.textEdited.connect(lambda _text: self._schedule_settings_autosave())
        self._out_range_value.textEdited.connect(lambda _text: self._schedule_settings_autosave())

        self.layout.addWidget(self._settings_container)
        self._install_profile_tooltips()
        self._update_profile_setup_accessibility()

        self._strategy_stack = QStackedWidget(self)
        self._strategy_tabs = SegmentedWidget()
        self._strategy_tabs.addItem("strategies", "Готовые стратегии", lambda: self._switch_strategy_tab(0))
        self._strategy_tabs.addItem("editor", "Редактор", lambda: self._switch_strategy_tab(1))
        self._strategy_tabs.addItem("match", "Когда применяется", lambda: self._switch_strategy_tab(2))
        set_segmented_current_item_if_changed(self._strategy_tabs, "strategies")
        self._sync_editor_tab_label(None)
        self.layout.addWidget(self._strategy_tabs)

        self._strategy_branch_bar = QWidget(self)
        branch_layout = QHBoxLayout(self._strategy_branch_bar)
        branch_layout.setContentsMargins(0, 0, 0, 0)
        branch_layout.setSpacing(8)
        branch_layout.addWidget(BodyLabel("Ветка"))
        self._strategy_branch_combo = ComboBox()
        self._strategy_branch_combo.setMinimumWidth(260)
        self._strategy_branch_combo.currentIndexChanged.connect(self._on_strategy_branch_changed)
        self._strategy_branch_combo.currentIndexChanged.connect(self._update_profile_setup_accessibility)
        branch_layout.addWidget(self._strategy_branch_combo, 1)
        self._strategy_branch_bar.hide()
        self.layout.addWidget(self._strategy_branch_bar)

        self._strategy_list = ProfileStrategyListWidget(self)
        self._strategy_list.strategy_activated.connect(self._on_strategy_list_activated)
        self._strategy_stack.addWidget(self._strategy_list)

        self._list_file_editor_placeholder = QWidget(self)
        self._strategy_stack.addWidget(self._list_file_editor_placeholder)

        self._match_tab_placeholder = QWidget(self)
        self._strategy_stack.addWidget(self._match_tab_placeholder)

        self.layout.addWidget(self._strategy_stack, 1)
        self._update_profile_setup_accessibility()

    def _update_combo_accessibility(self, combo, *, name: str, description: str) -> None:
        if combo is None:
            return
        current_text = getattr(combo, "currentText", None)
        if not callable(current_text):
            return
        selected = str(current_text() or "").strip()
        if selected:
            accessible_name = f"{name}, выбрано: {selected}"
        else:
            accessible_name = f"{name}, не выбрано"
        set_control_accessibility(
            combo,
            name=accessible_name,
            description=description,
        )

    def _update_profile_setup_accessibility(self, *_args) -> None:
        checkbox = self.__dict__.get("_enabled_checkbox")
        if checkbox is not None:
            state = "включено" if checkbox.isChecked() else "выключено"
            state_text = f"Profile, {state}"
            set_control_accessibility(
                checkbox,
                name=state_text,
                description="Включает или отключает этот profile в текущем preset.",
            )
            set_state_text(checkbox, state_text)
        self._update_combo_accessibility(
            self.__dict__.get("_filter_combo"),
            name="Тип списка profile",
            description="Выберите hostlist для доменов или ipset для IP-адресов.",
        )
        self._update_combo_accessibility(
            self.__dict__.get("_in_range_mode"),
            name="Режим in-range",
            description="Выберите режим --in-range для входящих пакетов.",
        )
        self._update_combo_accessibility(
            self.__dict__.get("_out_range_mode"),
            name="Режим out-range",
            description="Выберите режим --out-range для исходящих пакетов.",
        )
        self._update_combo_accessibility(
            self.__dict__.get("_strategy_branch_combo"),
            name="Ветка готовой стратегии",
            description="Выберите ветку готовой стратегии для этого profile.",
        )

    def _switch_strategy_tab(self, index: int) -> None:
        if index == 1 and not self._editor_tab_available:
            index = 0
            if self._strategy_tabs is not None:
                set_segmented_current_item_if_changed(self._strategy_tabs, "strategies")
        if index == 1:
            self._ensure_editor_tab_built()
            self._request_list_file_editor_state()
        elif index == 2:
            self._ensure_match_tab_built()
            self._apply_match_tab_payload()
        set_current_index_if_changed(self._strategy_stack, index)

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
        set_control_accessibility(
            self._list_file_base_text,
            name="Базовая часть списка profile",
            description="Системная часть списка. Она обновляется программой и доступна только для чтения.",
        )
        editor_layout.addWidget(self._list_file_base_text, 1)

        self._list_file_user_title = CaptionLabel("Ваши записи")
        self._list_file_user_title.setWordWrap(True)
        editor_layout.addWidget(self._list_file_user_title)

        self._list_file_text = PlainTextEdit()
        self._list_file_text.setMinimumHeight(320)
        self._list_file_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._list_file_text.document().contentsChange.connect(self._on_list_file_text_contents_changed)
        self._list_file_text.textChanged.connect(self._on_list_file_text_changed)
        set_tooltip(
            self._list_file_text,
            "Пользовательская часть списка. Сохраняется в lists/user и добавляется к базе.",
        )
        set_control_accessibility(
            self._list_file_text,
            name="Ваши записи списка profile",
            description="Пользовательская часть списка. Эти строки можно редактировать и сохранить.",
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
        set_control_accessibility(
            self._list_file_save_button,
            name="Сохранить список profile",
            description="Проверяет и сохраняет пользовательскую часть списка profile.",
        )
        self._list_file_save_button.clicked.connect(self._on_list_file_save_clicked)
        editor_actions_layout.addWidget(self._list_file_save_button)
        self._list_file_status_label = CaptionLabel("Загрузка файла списка...")
        set_state_text(self._list_file_status_label, "Статус списка profile: Загрузка файла списка...")
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
        set_control_accessibility(
            self._match_text,
            name="Условия применения profile",
            description="Здесь показаны условия применения profile и выбранная готовая стратегия.",
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
        set_control_accessibility(
            self._raw_profile_text,
            name="Текст profile в текущем preset",
            description="Сырой текст profile. Сохраняется только в текущий preset.",
        )
        self._raw_profile_text.document().contentsChange.connect(self._on_raw_profile_text_contents_changed)
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
        set_control_accessibility(
            self._raw_profile_save_button,
            name="Сохранить текст profile",
            description="Проверяет текст как один profile и записывает его в текущий preset.",
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
        set_control_accessibility(
            self._work_button,
            name="Отметить стратегию как рабочую",
            description="Помечает текущую готовую стратегию как рабочую для этого profile.",
        )
        self._work_button.clicked.connect(lambda: self._set_current_strategy_feedback(rating="work"))
        feedback_actions_layout.addWidget(self._work_button)

        self._notwork_button = PushButton("Не работает", icon=FluentIcon.CLOSE)
        set_tooltip(self._notwork_button, "Пометить текущую готовую стратегию как нерабочую для этого profile.")
        set_control_accessibility(
            self._notwork_button,
            name="Отметить стратегию как нерабочую",
            description="Помечает текущую готовую стратегию как нерабочую для этого profile.",
        )
        self._notwork_button.clicked.connect(lambda: self._set_current_strategy_feedback(rating="notwork"))
        feedback_actions_layout.addWidget(self._notwork_button)

        self._favorite_button = PushButton("В избранное", icon=FluentIcon.HEART)
        set_tooltip(self._favorite_button, "Добавить текущую готовую стратегию в избранное или убрать её оттуда.")
        set_control_accessibility(
            self._favorite_button,
            name="Добавить стратегию в избранное",
            description="Добавляет текущую готовую стратегию в избранное или убирает её оттуда.",
        )
        self._favorite_button.clicked.connect(self._toggle_current_strategy_favorite)
        feedback_actions_layout.addWidget(self._favorite_button)

        self._clear_feedback_button = PushButton("Убрать оценку", icon=FluentIcon.RETURN)
        set_tooltip(self._clear_feedback_button, "Очистить вашу оценку для текущей готовой стратегии.")
        set_control_accessibility(
            self._clear_feedback_button,
            name="Убрать оценку стратегии",
            description="Очищает вашу оценку для текущей готовой стратегии.",
        )
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
            match_text = str(getattr(payload, "match_tab_text", "") or "")
            if self.__dict__.get("_match_text_snapshot") != match_text:
                self._match_text.setPlainText(match_text)
                self._match_text_snapshot = match_text
        if self._raw_profile_text is not None:
            self._set_raw_profile_text_from_payload(str(getattr(payload, "raw_profile_text", "") or ""))
            raw_editable = bool(getattr(item, "in_preset", False))
            set_read_only_if_changed(self._raw_profile_text, not raw_editable)
        if self._raw_profile_save_button is not None:
            set_widget_enabled_if_changed(self._raw_profile_save_button, bool(getattr(item, "in_preset", False)))
        self._apply_feedback_buttons(payload)

    def _set_raw_profile_text_from_payload(self, text: str) -> None:
        value = str(text or "")
        if self.__dict__.get("_raw_profile_text_cache") == value:
            return
        editor = self.__dict__.get("_raw_profile_text")
        if editor is None:
            self._raw_profile_text_cache = value
            return
        self._raw_profile_text_cache_update_suspended = True
        try:
            editor.setPlainText(value)
        finally:
            self._raw_profile_text_cache_update_suspended = False
        self._raw_profile_text_cache = value

    def _on_raw_profile_text_changed(self) -> None:
        self._raw_profile_text_cache = None

    def _on_raw_profile_text_contents_changed(self, position: int, chars_removed: int, chars_added: int) -> None:
        if self._loading or bool(self.__dict__.get("_raw_profile_text_cache_update_suspended", False)):
            return
        current = str(self.__dict__.get("_raw_profile_text_cache", "") or "")
        start = max(0, min(int(position or 0), len(current)))
        removed = max(0, int(chars_removed or 0))
        inserted = self._raw_profile_inserted_text(start, max(0, int(chars_added or 0)))
        self._raw_profile_text_cache = f"{current[:start]}{inserted}{current[start + removed:]}"

    def _raw_profile_inserted_text(self, position: int, chars_added: int) -> str:
        if chars_added <= 0:
            return ""
        editor = self.__dict__.get("_raw_profile_text")
        if editor is None:
            return ""
        try:
            document = editor.document()
            cursor = QTextCursor(document)
            cursor.setPosition(max(0, int(position or 0)))
            cursor.setPosition(max(0, int(position or 0)) + int(chars_added or 0), QTextCursor.MoveMode.KeepAnchor)
            return str(cursor.selectedText() or "").replace("\u2029", "\n")
        except Exception:
            return ""

    def _request_list_file_editor_state(self) -> None:
        if not self._editor_tab_built or not self._profile_key:
            return
        runtime = self._worker_runtime("_list_file_load_runtime")
        state = self._list_file_load_state_obj()
        if state.is_busy():
            self._list_file_load_request_id = int(self.__dict__.get("_list_file_load_request_id", 0) or 0) + 1
            state.pending = True
            return
        if self._list_file_status_label is not None:
            set_profile_list_status_text(self._list_file_status_label, "Загрузка файла списка...")
        self._list_file_load_request_id = int(self.__dict__.get("_list_file_load_request_id", 0) or 0) + 1
        request_id = self._list_file_load_request_id
        _request_id, worker = runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: self.create_profile_list_file_load_worker(
                request_id,
                self._profile_key,
                filter_kind=self._current_filter_kind(),
                filter_value=self._current_filter_value(),
                parent=self,
            ),
            on_loaded=self._on_list_file_editor_state_loaded,
            on_failed=self._on_list_file_editor_state_failed,
            on_finished=self._on_list_file_worker_finished,
        )
        self._list_file_load_runtime_worker = worker

    def _on_list_file_editor_state_loaded(self, request_id: int, state) -> None:
        if request_id != self._list_file_load_request_id:
            return
        if self._list_file_load_state_obj().has_pending():
            return
        self._list_file_dirty = False
        self._schedule_list_file_editor_state_apply(state)

    def _schedule_list_file_editor_state_apply(self, state) -> None:
        self._pending_list_file_state_apply = state
        if self.__dict__.get("_list_file_state_apply_scheduled", False):
            return
        self._list_file_state_apply_scheduled = True
        try:
            QTimer.singleShot(0, self._run_scheduled_list_file_editor_state_apply)
        except Exception:
            self._run_scheduled_list_file_editor_state_apply()

    def _run_scheduled_list_file_editor_state_apply(self) -> None:
        state = self.__dict__.get("_pending_list_file_state_apply")
        self._pending_list_file_state_apply = None
        self._list_file_state_apply_scheduled = False
        if state is None or self.__dict__.get("_cleanup_in_progress"):
            return
        if (
            self._list_file_load_state_obj().has_pending()
            or self._list_file_load_state_obj().start_scheduled
        ):
            return
        self._apply_list_file_editor_state(state)

    def _on_list_file_editor_state_failed(self, request_id: int, error: str) -> None:
        if request_id != self._list_file_load_request_id:
            return
        if (
            self._list_file_load_state_obj().has_pending()
            or self._list_file_load_state_obj().start_scheduled
        ):
            return
        if self._list_file_status_label is not None:
            set_profile_list_status_text(
                self._list_file_status_label,
                f"Ошибка загрузки файла списка: {error}",
            )

    def _on_list_file_worker_finished(self, _worker) -> None:
        if not self._accept_current_profile_setup_worker_finished("_list_file_load_runtime_worker", _worker):
            return
        if self._list_file_load_state_obj().has_pending():
            self._schedule_pending_list_file_load_start()

    def _schedule_pending_list_file_load_start(self) -> None:
        state = self._list_file_load_state_obj()
        state.pending = True

        def _single_shot(delay: int, callback) -> None:
            try:
                QTimer.singleShot(delay, callback)
            except Exception:
                callback()

        state.schedule_start(
            _single_shot,
            self._run_scheduled_list_file_load_start,
            pending_when_already_scheduled=True,
        )

    def _run_scheduled_list_file_load_start(self) -> None:
        pending = self._list_file_load_state_obj().take_pending_for_scheduled_start(
            cleanup_in_progress=self.__dict__.get("_cleanup_in_progress", False),
        )
        if not pending:
            return
        self._request_list_file_editor_state()

    def _list_file_load_state_obj(self) -> LatestValueWorkerState:
        state = self.__dict__.get("_list_file_load_state")
        runtime = self.__dict__.get("_list_file_load_runtime")
        if state is None:
            pending = bool(self.__dict__.pop("_pending_list_file_load", False))
            start_scheduled = bool(self.__dict__.pop("_list_file_load_start_scheduled", False))
            state = LatestValueWorkerState(
                runtime,
                empty_value=False,
                pending=pending,
                start_scheduled=start_scheduled,
            )
            self.__dict__["_list_file_load_state"] = state
        elif getattr(state, "runtime", None) is None and runtime is not None:
            state.runtime = runtime
        return state

    @property
    def _pending_list_file_load(self) -> bool:
        return bool(self._list_file_load_state_obj().pending)

    @_pending_list_file_load.setter
    def _pending_list_file_load(self, value: bool) -> None:
        self._list_file_load_state_obj().pending = bool(value)

    @property
    def _list_file_load_start_scheduled(self) -> bool:
        return bool(self._list_file_load_state_obj().start_scheduled)

    @_list_file_load_start_scheduled.setter
    def _list_file_load_start_scheduled(self, value: bool) -> None:
        self._list_file_load_state_obj().start_scheduled = bool(value)

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
            set_widget_enabled_if_changed(self._update_user_profile_button, enabled)
        if self._delete_user_profile_button is not None:
            set_widget_enabled_if_changed(self._delete_user_profile_button, enabled)

    def _current_user_profile_id(self) -> str:
        return _user_profile_id_from_payload(self._profile_key, self._payload)

    def _request_user_profile_update(self, profile_id: str, *, name: str, protocol: str, ports: str) -> None:
        profile_id = str(profile_id or "").strip()
        if not profile_id:
            return
        if self._user_profile_write_operation_running():
            self._queue_user_profile_write_operation(
                "update",
                profile_id=profile_id,
                name=name,
                protocol=protocol,
                ports=ports,
            )
            return
        self._start_user_profile_update_worker(
            profile_id,
            name=name,
            protocol=protocol,
            ports=ports,
        )

    def _user_profile_write_operation_running(self) -> bool:
        if self.__dict__.get("_user_profile_write_operation_start_scheduled", False):
            return True
        return self._worker_runtime("_user_profile_update_runtime").is_running() or self._worker_runtime(
            "_user_profile_delete_runtime"
        ).is_running()

    def _queue_user_profile_write_operation(
        self,
        action: str,
        *,
        profile_id: str,
        name: str = "",
        protocol: str = "",
        ports: str = "",
    ) -> None:
        operation = {
            "action": str(action or ""),
            "profile_id": str(profile_id or ""),
            "name": str(name or ""),
            "protocol": str(protocol or ""),
            "ports": str(ports or ""),
        }
        if operation["action"] == "update":
            profile_id_to_replace = str(operation["profile_id"] or "")
            pending_operations = self.__dict__.setdefault("_pending_user_profile_operations", [])
            pending_operations[:] = [
                pending
                for pending in pending_operations
                if not (
                    str(pending.get("action") or "") == "update"
                    and str(pending.get("profile_id") or "") == profile_id_to_replace
                )
            ]
            pending_updates = self.__dict__.setdefault("_pending_user_profile_updates", [])
            pending_updates[:] = [
                pending
                for pending in pending_updates
                if str(pending.get("profile_id") or "") != profile_id_to_replace
            ]
        self.__dict__.setdefault("_pending_user_profile_operations", []).append(operation)
        if operation["action"] == "update":
            self.__dict__.setdefault("_pending_user_profile_updates", []).append(
                {
                    "profile_id": operation["profile_id"],
                    "name": operation["name"],
                    "protocol": operation["protocol"],
                    "ports": operation["ports"],
                }
            )
        elif operation["action"] == "delete":
            self.__dict__.setdefault("_pending_user_profile_deletes", []).append(operation["profile_id"])

    def _pop_next_pending_user_profile_write_operation(self) -> dict[str, str] | None:
        pending_operations = self.__dict__.setdefault("_pending_user_profile_operations", [])
        if pending_operations:
            operation = dict(pending_operations.pop(0))
            if operation.get("action") == "update":
                pending_updates = self.__dict__.setdefault("_pending_user_profile_updates", [])
                if pending_updates:
                    pending_updates.pop(0)
            elif operation.get("action") == "delete":
                pending_deletes = self.__dict__.setdefault("_pending_user_profile_deletes", [])
                if pending_deletes:
                    pending_deletes.pop(0)
            return operation
        pending_updates = self.__dict__.setdefault("_pending_user_profile_updates", [])
        if pending_updates:
            pending = dict(pending_updates.pop(0))
            pending["action"] = "update"
            return pending
        pending_deletes = self.__dict__.setdefault("_pending_user_profile_deletes", [])
        if pending_deletes:
            return {
                "action": "delete",
                "profile_id": str(pending_deletes.pop(0) or ""),
                "name": "",
                "protocol": "",
                "ports": "",
            }
        return None

    def _has_pending_user_profile_write_operation(self) -> bool:
        return any(
            self.__dict__.get(attr)
            for attr in (
                "_pending_user_profile_operations",
                "_pending_user_profile_updates",
                "_pending_user_profile_deletes",
            )
        )

    def _schedule_next_pending_user_profile_write_operation_start(self) -> bool:
        if self._user_profile_write_operation_running():
            return True
        if not self._has_pending_user_profile_write_operation():
            return False
        if self.__dict__.get("_user_profile_write_operation_start_scheduled", False):
            return True
        self._user_profile_write_operation_start_scheduled = True
        try:
            QTimer.singleShot(0, self._run_scheduled_user_profile_write_operation_start)
        except Exception:
            self._run_scheduled_user_profile_write_operation_start()
        return True

    def _run_scheduled_user_profile_write_operation_start(self) -> None:
        self._user_profile_write_operation_start_scheduled = False
        self._start_next_pending_user_profile_write_operation()

    def _start_next_pending_user_profile_write_operation(self) -> bool:
        if self._user_profile_write_operation_running():
            return True
        pending = self._pop_next_pending_user_profile_write_operation()
        if not pending:
            return False
        if pending.get("action") == "update":
            self._start_user_profile_update_worker(
                str(pending.get("profile_id") or ""),
                name=str(pending.get("name") or ""),
                protocol=str(pending.get("protocol") or ""),
                ports=str(pending.get("ports") or ""),
            )
            return True
        if pending.get("action") == "delete":
            self._start_user_profile_delete_worker(str(pending.get("profile_id") or ""))
            return True
        return self._start_next_pending_user_profile_write_operation()

    def _start_user_profile_update_worker(self, profile_id: str, *, name: str, protocol: str, ports: str) -> None:
        runtime = self._worker_runtime("_user_profile_update_runtime")
        self._user_profile_update_request_id = int(getattr(self, "_user_profile_update_request_id", 0) or 0) + 1
        request_id = self._user_profile_update_request_id
        self._set_user_profile_buttons_enabled(False)
        started = runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: self.create_profile_user_update_worker(
                request_id,
                profile_id=profile_id,
                name=name,
                protocol=protocol,
                ports=ports,
                parent=self,
            ),
            on_loaded=self._on_user_profile_update_finished,
            on_failed=self._on_user_profile_update_failed,
            on_finished=self._on_user_profile_update_worker_finished,
            loaded_signal_name="updated",
        )
        worker = started[1] if isinstance(started, tuple) and len(started) > 1 else getattr(runtime, "worker", None)
        self._user_profile_update_runtime_worker = worker

    def _on_user_profile_update_finished(
        self,
        request_id: int,
        profile_id: str,
        changed: int,
        _profile_items=(),
    ) -> None:
        if request_id != int(getattr(self, "_user_profile_update_request_id", 0) or 0):
            return
        if self.__dict__.get("_pending_user_profile_operations") or self.__dict__.get("_pending_user_profile_updates"):
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
            current_item = getattr(self.__dict__.get("_payload"), "item", None)
            if current_item == updated_item:
                return
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
        if not self.__dict__.get("_pending_user_profile_operations") and not self.__dict__.get("_pending_user_profile_updates"):
            self._set_user_profile_buttons_enabled(True)
        log(f"{self.__class__.__name__}: не удалось изменить пользовательский profile: {error}", "ERROR")
        InfoBar.error(
            title="Ошибка",
            content=str(error),
            parent=self.window(),
        )

    def _on_user_profile_update_worker_finished(self, _worker) -> None:
        if not self._accept_current_profile_setup_worker_finished("_user_profile_update_runtime_worker", _worker):
            return
        if self._schedule_next_pending_user_profile_write_operation_start():
            return
        self._set_user_profile_buttons_enabled(True)

    def _apply_user_profile_update_locally(self, updated_item) -> bool:
        payload = self._payload
        if payload is None or updated_item is None:
            return False
        try:
            self._payload = replace(payload, item=updated_item)
        except Exception:
            return False
        self._schedule_profile_setup_payload_apply(self._payload)
        return True

    def _request_user_profile_delete(self, profile_id: str) -> None:
        profile_id = str(profile_id or "").strip()
        if not profile_id:
            return
        runtime = self._worker_runtime("_user_profile_delete_runtime")
        if self._user_profile_write_operation_running():
            self._queue_user_profile_write_operation("delete", profile_id=profile_id)
            return
        self._start_user_profile_delete_worker(profile_id)

    def _start_user_profile_delete_worker(self, profile_id: str) -> None:
        runtime = self._worker_runtime("_user_profile_delete_runtime")
        self._user_profile_delete_request_id = int(getattr(self, "_user_profile_delete_request_id", 0) or 0) + 1
        request_id = self._user_profile_delete_request_id
        self._set_user_profile_buttons_enabled(False)
        started = runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: self.create_profile_user_delete_worker(
                request_id,
                profile_id=profile_id,
                parent=self,
            ),
            on_loaded=self._on_user_profile_delete_finished,
            on_failed=self._on_user_profile_delete_failed,
            on_finished=self._on_user_profile_delete_worker_finished,
            loaded_signal_name="deleted",
        )
        worker = started[1] if isinstance(started, tuple) and len(started) > 1 else getattr(runtime, "worker", None)
        self._user_profile_delete_runtime_worker = worker

    def _on_user_profile_delete_finished(self, request_id: int, profile_id: str, changed: int) -> None:
        if request_id != int(getattr(self, "_user_profile_delete_request_id", 0) or 0):
            return
        if self.__dict__.get("_pending_user_profile_operations") or self.__dict__.get("_pending_user_profile_deletes"):
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
        if not self.__dict__.get("_pending_user_profile_operations") and not self.__dict__.get("_pending_user_profile_deletes"):
            self._set_user_profile_buttons_enabled(True)
        log(f"{self.__class__.__name__}: не удалось удалить пользовательский profile: {error}", "ERROR")
        InfoBar.error(
            title="Ошибка",
            content=str(error),
            parent=self.window(),
        )

    def _on_user_profile_delete_worker_finished(self, _worker) -> None:
        if not self._accept_current_profile_setup_worker_finished("_user_profile_delete_runtime_worker", _worker):
            return
        if self._schedule_next_pending_user_profile_write_operation_start():
            return
        self._set_user_profile_buttons_enabled(True)

    def show_profile(self, profile_key: str) -> None:
        next_key = str(profile_key or "").strip()
        if next_key and next_key == str(self._profile_key or "").strip() and self._payload is not None:
            return
        self._profile_key = next_key
        self.reload_current_profile()

    def handle_page_command(self, command: str, payload: dict) -> bool:
        if command == "open_profile":
            self.show_profile(str((payload or {}).get("profile_key") or ""))
            return True
        return False

    def reload_current_profile(self) -> None:
        self._request_profile_setup_payload()

    def create_profile_setup_load_worker(self, request_id: int, profile_key: str, parent=None):
        return self._create_profile_setup_load_worker_fn(
            request_id,
            self.launch_method,
            profile_key=profile_key,
            parent=parent,
        )

    def create_profile_list_file_load_worker(
        self,
        request_id: int,
        profile_key: str,
        *,
        filter_kind: str = "",
        filter_value: str = "",
        parent=None,
    ):
        return self._create_profile_list_file_load_worker_fn(
            request_id,
            self.launch_method,
            profile_key=profile_key,
            filter_kind=filter_kind,
            filter_value=filter_value,
            parent=parent,
        )

    def create_profile_list_file_save_worker(self, request_id: int, profile_key: str, text: str, parent=None):
        return self._create_profile_list_file_save_worker_fn(
            request_id,
            self.launch_method,
            profile_key=profile_key,
            text=text,
            parent=parent,
        )

    def create_profile_list_file_validation_worker(self, request_id: int, *, kind: str, text: str, parent=None):
        return self._create_profile_list_file_validation_worker_fn(
            request_id,
            self.launch_method,
            kind=kind,
            text=text,
            parent=parent,
        )

    def create_profile_settings_save_worker(
        self,
        request_id: int,
        *,
        profile_key: str,
        filter_kind: str,
        filter_value: str,
        in_range: str,
        out_range: str,
        parent=None,
    ):
        return self._create_profile_settings_save_worker_fn(
            request_id,
            self.launch_method,
            profile_key=profile_key,
            filter_kind=filter_kind,
            filter_value=filter_value,
            in_range=in_range,
            out_range=out_range,
            parent=parent,
        )

    def create_profile_raw_text_save_worker(self, request_id: int, profile_key: str, raw_text: str, parent=None):
        return self._create_profile_raw_text_save_worker_fn(
            request_id,
            self.launch_method,
            profile_key=profile_key,
            raw_text=raw_text,
            parent=parent,
        )

    def create_profile_enabled_save_worker(
        self,
        request_id: int,
        *,
        profile_key: str,
        enabled: bool,
        filter_kind: str = "",
        filter_value: str = "",
        parent=None,
    ):
        return self._create_profile_enabled_save_worker_fn(
            request_id,
            self.launch_method,
            profile_key=profile_key,
            enabled=enabled,
            filter_kind=filter_kind,
            filter_value=filter_value,
            parent=parent,
        )

    def create_profile_user_update_worker(
        self,
        request_id: int,
        *,
        profile_id: str,
        name: str,
        protocol: str,
        ports: str,
        parent=None,
    ):
        return self._create_profile_user_update_worker_fn(
            request_id,
            self.launch_method,
            profile_id=profile_id,
            name=name,
            protocol=protocol,
            ports=ports,
            parent=parent,
        )

    def create_profile_user_delete_worker(self, request_id: int, *, profile_id: str, parent=None):
        return self._create_profile_user_delete_worker_fn(
            request_id,
            self.launch_method,
            profile_id=profile_id,
            parent=parent,
        )

    def create_profile_strategy_apply_worker(
        self,
        request_id: int,
        *,
        profile_key: str,
        strategy_id: str,
        strategy_branch_id: str = "",
        parent=None,
    ):
        return self._create_profile_strategy_apply_worker_fn(
            request_id,
            self.launch_method,
            profile_key=profile_key,
            strategy_id=strategy_id,
            strategy_branch_id=strategy_branch_id,
            parent=parent,
        )

    def create_profile_strategy_feedback_save_worker(
        self,
        request_id: int,
        *,
        profile_key: str,
        strategy_id: str,
        rating: str | None = None,
        favorite: bool | None = None,
        parent=None,
    ):
        return self._create_profile_strategy_feedback_save_worker_fn(
            request_id,
            self.launch_method,
            profile_key=profile_key,
            strategy_id=strategy_id,
            rating=rating,
            favorite=favorite,
            parent=parent,
        )

    def _request_profile_setup_payload(self) -> None:
        if not self._profile_key:
            return
        runtime = self._worker_runtime("_setup_load_runtime")
        if runtime.is_running() or self.__dict__.get("_setup_load_start_scheduled", False):
            self._setup_load_request_id += 1
            self._setup_load_dirty = True
            return

        self._start_profile_setup_load_worker()

    def _start_profile_setup_load_worker(self) -> None:
        if not self._profile_key:
            return
        self._setup_load_request_id += 1
        request_id = self._setup_load_request_id
        set_widget_text_if_changed(self._summary, "Загрузка profile...")
        set_widget_enabled_if_changed(self._enabled_checkbox, False)
        runtime = self._worker_runtime("_setup_load_runtime")
        started = runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: self.create_profile_setup_load_worker(
                request_id,
                self._profile_key,
                self,
            ),
            on_loaded=self._on_profile_setup_payload_loaded,
            on_failed=self._on_profile_setup_payload_failed,
            on_finished=self._on_profile_setup_worker_finished,
        )
        worker = started[1] if isinstance(started, tuple) and len(started) > 1 else getattr(runtime, "worker", None)
        self._setup_load_runtime_worker = worker

    def _on_profile_setup_payload_loaded(self, request_id: int, payload) -> None:
        if request_id != self._setup_load_request_id:
            return
        if self.__dict__.get("_setup_load_dirty"):
            return
        payload, apply_signature = _profile_setup_payload_and_apply_signature(payload)
        if payload is None:
            set_widget_text_if_changed(
                self._summary,
                "Профиль не найден. Вернитесь к списку и выберите profile заново.",
            )
            set_widget_enabled_if_changed(self._enabled_checkbox, False)
            return
        if (
            apply_signature is not None
            and self.__dict__.get("_last_profile_setup_payload_apply_signature") == apply_signature
        ):
            self._restore_loaded_payload_header(payload)
            return
        if payload == self.__dict__.get("_payload"):
            self._restore_loaded_payload_header(payload)
            return
        self._payload = payload
        self._schedule_profile_setup_payload_apply(payload, apply_signature=apply_signature)

    def _schedule_profile_setup_payload_apply(self, payload, *, apply_signature=None) -> None:
        self._pending_profile_setup_payload_apply = (
            payload,
            tuple(apply_signature) if apply_signature is not None else None,
        )
        if self.__dict__.get("_profile_setup_payload_apply_scheduled", False):
            return
        self._profile_setup_payload_apply_scheduled = True
        try:
            QTimer.singleShot(0, self._run_scheduled_profile_setup_payload_apply)
        except Exception:
            self._run_scheduled_profile_setup_payload_apply()

    def _run_scheduled_profile_setup_payload_apply(self) -> None:
        pending = self.__dict__.get("_pending_profile_setup_payload_apply")
        self._pending_profile_setup_payload_apply = None
        self._profile_setup_payload_apply_scheduled = False
        if isinstance(pending, tuple) and len(pending) == 2:
            payload, apply_signature = pending
        else:
            payload = pending
            apply_signature = None
        if payload is None or self.__dict__.get("_cleanup_in_progress"):
            return
        if (
            self.__dict__.get("_setup_load_dirty")
            or self.__dict__.get("_setup_load_start_scheduled", False)
        ):
            return
        if (
            apply_signature is not None
            and self.__dict__.get("_last_profile_setup_payload_apply_signature") == apply_signature
        ):
            self._restore_loaded_payload_header(payload)
            return
        self._apply_payload(payload)
        if apply_signature is not None:
            self._last_profile_setup_payload_apply_signature = apply_signature

    def _on_profile_setup_payload_failed(self, request_id: int, error: str) -> None:
        if request_id != self._setup_load_request_id:
            return
        if (
            self.__dict__.get("_setup_load_dirty")
            or self.__dict__.get("_setup_load_start_scheduled", False)
        ):
            return
        log(f"{self.__class__.__name__}: не удалось прочитать профиль {self._profile_key}: {error}", "ERROR")
        set_widget_text_if_changed(
            self._summary,
            "Профиль не найден. Вернитесь к списку и выберите profile заново.",
        )
        set_widget_enabled_if_changed(self._enabled_checkbox, False)

    def _on_profile_setup_worker_finished(self, _worker) -> None:
        if not self._accept_current_profile_setup_worker_finished("_setup_load_runtime_worker", _worker):
            return
        if self.__dict__.get("_setup_load_dirty") and not self.__dict__.get("_cleanup_in_progress", False):
            self._schedule_profile_setup_load_start()

    def _schedule_profile_setup_load_start(self) -> None:
        if self.__dict__.get("_setup_load_start_scheduled", False):
            return
        self._setup_load_start_scheduled = True
        try:
            QTimer.singleShot(0, self._run_scheduled_profile_setup_load_start)
        except Exception:
            self._run_scheduled_profile_setup_load_start()

    def _run_scheduled_profile_setup_load_start(self) -> None:
        self._setup_load_start_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if not self.__dict__.get("_setup_load_dirty"):
            return
        self._setup_load_dirty = False
        self._request_profile_setup_payload()

    def _restore_loaded_payload_header(self, payload) -> None:
        item = getattr(payload, "item", None)
        set_widget_text_if_changed(self._summary, getattr(payload, "match_summary", "") or "")
        if item is not None:
            set_widget_checked_if_changed(self._enabled_checkbox, bool(getattr(item, "enabled", False)))
            set_widget_enabled_if_changed(self._enabled_checkbox, True)

    def _apply_payload(self, payload) -> None:
        self._loading = True
        try:
            item = payload.item
            set_widget_text_if_changed(self._summary, payload.match_summary)
            set_widget_checked_if_changed(self._enabled_checkbox, bool(item.enabled))
            set_widget_enabled_if_changed(self._enabled_checkbox, True)
            user_profile_visible = bool(_user_profile_id_from_payload(self._profile_key, payload))
            if self._update_user_profile_button is not None:
                set_widget_visible_if_changed(self._update_user_profile_button, user_profile_visible)
            if self._delete_user_profile_button is not None:
                set_widget_visible_if_changed(self._delete_user_profile_button, user_profile_visible)
            self._apply_editable_settings(payload)
            self._set_list_file_editor_available(_profile_has_list_file_editor(payload))
            self._sync_editor_tab_label(payload)
            self._apply_strategy_branch_selector(payload)

            self._strategy_list.set_rows(
                entries=payload.strategy_entries,
                states=payload.strategy_states,
                current_strategy_id=_current_strategy_id(payload) or "none",
            )
            set_widget_enabled_if_changed(self._strategy_list, not (item.in_preset and not item.enabled))
            self._list_file_dirty = True
            if self._editor_tab_built and self._strategy_stack.currentIndex() == 1:
                self._request_list_file_editor_state()
            if self._match_tab_built:
                self._apply_match_tab_payload()
            self._rebuild_breadcrumb()
        finally:
            self._loading = False

    def _apply_strategy_branch_selector(self, payload) -> None:
        combo = self._strategy_branch_combo
        bar = self._strategy_branch_bar
        if combo is None or bar is None:
            return
        branches = tuple(getattr(payload, "strategy_branches", ()) or ())
        visible = len(branches) > 1
        set_widget_visible_if_changed(bar, visible)
        if not visible:
            return

        current_id = _current_strategy_branch_id(payload) or str(getattr(branches[0], "branch_id", "") or "")
        branch_rows: list[tuple[str, str]] = []
        selected_index = 0
        for index, branch in enumerate(branches):
            branch_id = str(getattr(branch, "branch_id", "") or "").strip()
            branch_rows.append((branch_id, _strategy_branch_label(branch)))
            if branch_id == current_id:
                selected_index = index
        combo.blockSignals(True)
        try:
            if _update_strategy_branch_combo_in_place(combo, branch_rows, selected_index):
                return
            combo.clear()
            for branch_id, label in branch_rows:
                combo.addItem(label, userData=branch_id)
            combo.setCurrentIndex(selected_index)
        finally:
            combo.blockSignals(False)
        self._update_profile_setup_accessibility()

    def _on_strategy_branch_changed(self, _index: int) -> None:
        if self._loading or self._payload is None or self._strategy_branch_combo is None:
            return
        branch_id = str(self._strategy_branch_combo.itemData(self._strategy_branch_combo.currentIndex()) or "").strip()
        if not branch_id:
            return
        branches = tuple(getattr(self._payload, "strategy_branches", ()) or ())
        branch = next((item for item in branches if str(getattr(item, "branch_id", "") or "").strip() == branch_id), None)
        if branch is None:
            return
        state = (getattr(self._payload, "strategy_states", {}) or {}).get(
            str(getattr(branch, "strategy_id", "") or "").strip(),
            ProfileStrategyState(),
        )
        self._payload = replace(
            self._payload,
            current_strategy_branch_id=branch_id,
            raw_strategy_text=str(getattr(branch, "raw_strategy_text", "") or ""),
            match_tab_text=str(getattr(branch, "match_tab_text", "") or ""),
            current_strategy_state=state,
        )
        self._strategy_list.set_current_strategy_id(str(getattr(branch, "strategy_id", "") or "none").strip() or "none")
        self._apply_feedback_buttons(self._payload)
        if self._match_tab_built:
            self._apply_match_tab_payload()

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
            set_current_index_if_changed(self._strategy_stack, 0)
            set_segmented_current_item_if_changed(self._strategy_tabs, "strategies")
        self._strategy_tabs.removeWidget("editor")

    def _sync_editor_tab_label(self, payload) -> None:
        editor_title = _profile_editor_tab_title(payload)
        if self._strategy_tabs is not None and self._editor_tab_available:
            set_tab_item_text_if_changed(self._strategy_tabs, "editor", editor_title)
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
        visible_user_text = user_text if editable else text
        base_text_changed = self.__dict__.get("_list_file_base_text_snapshot", "") != base_text
        user_text_changed = self.__dict__.get("_list_file_text_snapshot", "") != visible_user_text
        self._list_file_base_entries_count = (
            _non_negative_int(getattr(state, "base_entries_count", 0))
            if editable
            else 0
        )
        self._list_file_user_entries_count = _non_negative_int(
            getattr(state, "user_entries_count", 0)
        )

        title = "Файл списка"
        if display_path:
            title = f"{display_path} ({'IPset' if kind == 'ipset' else 'Hostlist'})"
        if self._list_file_title is not None:
            set_widget_text_if_changed(self._list_file_title, title)
        if self._list_file_base_title is not None:
            set_widget_visible_if_changed(self._list_file_base_title, editable)
            set_widget_text_if_changed(
                self._list_file_base_title,
                f"База: {base_display_path}" if base_display_path else "База"
            )
        if self._list_file_base_text is not None:
            set_widget_visible_if_changed(self._list_file_base_text, editable)
            self._list_file_base_text.blockSignals(True)
            try:
                if base_text_changed:
                    self._list_file_base_text.setPlainText(base_text)
                if kind == "ipset":
                    set_placeholder_text_if_changed(self._list_file_base_text, "В базе пока нет IP или подсетей.")
                else:
                    set_placeholder_text_if_changed(self._list_file_base_text, "В базе пока нет доменов.")
            finally:
                self._list_file_base_text.blockSignals(False)
        self._list_file_base_text_snapshot = base_text
        if self._list_file_user_title is not None:
            set_widget_visible_if_changed(self._list_file_user_title, editable)
            set_widget_text_if_changed(
                self._list_file_user_title,
                f"Ваши записи: {user_display_path}" if user_display_path else "Ваши записи"
            )
        if self._list_file_text is not None:
            self._list_file_text.blockSignals(True)
            self._list_file_text_cache_update_suspended = True
            try:
                if user_text_changed:
                    self._list_file_text.setPlainText(visible_user_text)
                set_read_only_if_changed(self._list_file_text, not editable)
                if kind == "ipset":
                    set_placeholder_text_if_changed(self._list_file_text, "IP или подсети по одному на строку:\n1.2.3.4\n10.0.0.0/8")
                else:
                    set_placeholder_text_if_changed(self._list_file_text, "Домены по одному на строку:\nexample.com\nsub.example.org")
            finally:
                self._list_file_text_cache_update_suspended = False
                self._list_file_text.blockSignals(False)
        self._list_file_text_snapshot = visible_user_text
        self._list_file_text_dirty = False
        if self._list_file_save_button is not None:
            set_widget_enabled_if_changed(self._list_file_save_button, editable and not invalid_lines)
        if self._list_file_status_label is not None:
            if editable:
                base_count = self._list_file_base_entries_count
                user_count = self._list_file_user_entries_count
                set_profile_list_status_text(
                    self._list_file_status_label,
                    f"Записей всего: {base_count + user_count} • ваших: {user_count}"
                )
            else:
                set_profile_list_status_text(
                    self._list_file_status_label,
                    error_text or "Файл списка недоступен для редактирования.",
                )
        self._render_list_file_validation(invalid_lines, fallback_error=error_text if not editable else "")

    def _on_list_file_text_changed(self) -> None:
        if self._loading or self._list_file_text is None:
            return
        self._list_file_text_dirty = True
        save_button = self.__dict__.get("_list_file_save_button")
        if save_button is not None:
            set_widget_enabled_if_changed(save_button, False)
        timer = self.__dict__.get("_list_file_validation_timer")
        if timer is not None:
            try:
                timer.start(180)
            except TypeError:
                timer.start()
        if self._list_file_status_label is not None:
            set_profile_list_status_text(self._list_file_status_label, "Проверка списка...")
        if timer is not None:
            return
        self._run_scheduled_list_file_validation()

    def _on_list_file_text_contents_changed(self, position: int, chars_removed: int, chars_added: int) -> None:
        if self._loading or bool(self.__dict__.get("_list_file_text_cache_update_suspended", False)):
            return
        current = str(self.__dict__.get("_list_file_text_snapshot", "") or "")
        start = max(0, min(int(position or 0), len(current)))
        removed = max(0, int(chars_removed or 0))
        inserted = self._list_file_inserted_text(start, max(0, int(chars_added or 0)))
        self._list_file_text_snapshot = f"{current[:start]}{inserted}{current[start + removed:]}"
        self._list_file_text_dirty = True
        self._list_file_text_snapshot_from_change = True

    def _list_file_inserted_text(self, position: int, chars_added: int) -> str:
        if chars_added <= 0:
            return ""
        editor = self.__dict__.get("_list_file_text")
        if editor is None:
            return ""
        try:
            document = editor.document()
            cursor = QTextCursor(document)
            cursor.setPosition(max(0, int(position or 0)))
            cursor.setPosition(max(0, int(position or 0)) + int(chars_added or 0), QTextCursor.MoveMode.KeepAnchor)
            return str(cursor.selectedText() or "").replace("\u2029", "\n")
        except Exception:
            return ""

    def _run_scheduled_list_file_validation(self) -> None:
        if self._loading or self._list_file_text is None:
            return
        self._request_list_file_validation({
            "kind": self._list_file_kind,
            "text": None,
        })

    def _request_list_file_validation(self, request: dict) -> None:
        state = self._list_file_validation_state_obj()
        if state.is_busy():
            state.pending = dict(request)
            return
        self._start_list_file_validation_worker(request)

    def _resolve_list_file_validation_request(self, request: dict) -> dict[str, str]:
        request = dict(request or {})
        raw_text = request.get("text")
        if raw_text is None:
            if (
                bool(self.__dict__.get("_list_file_text_dirty", False))
                and not bool(self.__dict__.get("_list_file_text_snapshot_from_change", False))
            ):
                editor = self.__dict__.get("_list_file_text")
                try:
                    text = str(editor.toPlainText() or "") if editor is not None else ""
                except Exception:
                    text = str(self.__dict__.get("_list_file_text_snapshot", "") or "")
            else:
                text = str(self.__dict__.get("_list_file_text_snapshot", "") or "")
        else:
            text = str(raw_text or "")
        self._list_file_text_snapshot = text
        self._list_file_text_dirty = False
        self._list_file_text_snapshot_from_change = False
        return {
            "kind": str(request.get("kind") or ""),
            "text": text,
        }

    def _start_list_file_validation_worker(self, request: dict) -> None:
        request = self._resolve_list_file_validation_request(request)
        runtime = self._worker_runtime("_list_file_validation_runtime")
        self._list_file_validation_request_id = int(getattr(self, "_list_file_validation_request_id", 0) or 0) + 1
        request_id = self._list_file_validation_request_id
        _request_id, worker = runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: self.create_profile_list_file_validation_worker(
                request_id,
                kind=str(request.get("kind") or ""),
                text=str(request.get("text") or ""),
                parent=self,
            ),
            on_loaded=self._on_list_file_validation_finished,
            on_failed=self._on_list_file_validation_failed,
            on_finished=self._on_list_file_validation_worker_finished,
            loaded_signal_name="validated",
        )
        self._list_file_validation_runtime_worker = worker

    def _on_list_file_validation_finished(
        self,
        request_id: int,
        kind: str,
        text: str,
        invalid_lines,
    ) -> None:
        if request_id != int(getattr(self, "_list_file_validation_request_id", 0) or 0):
            return
        if self._list_file_validation_state_obj().has_pending():
            return
        if str(kind or "").strip() != str(getattr(self, "_list_file_kind", "") or "").strip():
            return
        current_text = str(self.__dict__.get("_list_file_text_snapshot", "") or "")
        if str(text or "") != current_text:
            return
        validation_result = invalid_lines
        if isinstance(validation_result, dict):
            invalid_lines = tuple(validation_result.get("invalid_lines") or ())
            try:
                self._list_file_user_entries_count = int(validation_result.get("entries_count") or 0)
            except (TypeError, ValueError):
                self._list_file_user_entries_count = 0
        else:
            invalid_lines = tuple(validation_result or ())
        self._render_list_file_validation(tuple(invalid_lines or ()))
        if self._list_file_save_button is not None:
            editable = self._list_file_text is not None and not self._list_file_text.isReadOnly()
            set_widget_enabled_if_changed(self._list_file_save_button, not invalid_lines and editable)
        if self._list_file_status_label is not None:
            if invalid_lines:
                set_profile_list_status_text(
                    self._list_file_status_label,
                    "Исправьте ошибки перед сохранением.",
                )
            else:
                user_count = int(self.__dict__.get("_list_file_user_entries_count", 0) or 0)
                base_count = int(self.__dict__.get("_list_file_base_entries_count", 0) or 0)
                set_profile_list_status_text(
                    self._list_file_status_label,
                    f"Записей всего: {base_count + user_count} • ваших: {user_count} • есть несохранённые изменения",
                )

    def _on_list_file_validation_failed(self, request_id: int, error: str) -> None:
        if request_id != int(getattr(self, "_list_file_validation_request_id", 0) or 0):
            return
        if self._list_file_validation_state_obj().has_pending():
            return
        log(f"{self.__class__.__name__}: не удалось проверить файл списка profile: {error}", "ERROR")
        self._render_list_file_validation((), fallback_error=str(error))
        if self._list_file_save_button is not None:
            set_widget_enabled_if_changed(self._list_file_save_button, False)
        if self._list_file_status_label is not None:
            set_profile_list_status_text(self._list_file_status_label, "Ошибка проверки списка.")

    def _on_list_file_validation_worker_finished(self, _worker) -> None:
        if not self._accept_current_profile_setup_worker_finished("_list_file_validation_runtime_worker", _worker):
            return
        if self._list_file_validation_state_obj().has_pending():
            self._schedule_pending_list_file_validation_start()

    def _schedule_pending_list_file_validation_start(self) -> None:
        state = self._list_file_validation_state_obj()

        def _single_shot(delay: int, callback) -> None:
            try:
                QTimer.singleShot(delay, callback)
            except Exception:
                callback()

        state.schedule_start(_single_shot, self._run_scheduled_list_file_validation_start)

    def _run_scheduled_list_file_validation_start(self) -> None:
        pending = self._list_file_validation_state_obj().take_pending_for_scheduled_start(
            cleanup_in_progress=self.__dict__.get("_cleanup_in_progress", False),
        )
        if not pending:
            return
        self._start_list_file_validation_worker(dict(pending or {}))

    def _list_file_validation_state_obj(self) -> LatestValueWorkerState:
        state = self.__dict__.get("_list_file_validation_state")
        runtime = self.__dict__.get("_list_file_validation_runtime")
        if state is None:
            pending = self.__dict__.pop("_pending_list_file_validation", None)
            start_scheduled = bool(self.__dict__.pop("_list_file_validation_start_scheduled", False))
            state = LatestValueWorkerState(
                runtime,
                empty_value=None,
                pending=pending,
                start_scheduled=start_scheduled,
            )
            self.__dict__["_list_file_validation_state"] = state
        elif getattr(state, "runtime", None) is None and runtime is not None:
            state.runtime = runtime
        return state

    @property
    def _pending_list_file_validation(self):
        return self._list_file_validation_state_obj().pending

    @_pending_list_file_validation.setter
    def _pending_list_file_validation(self, value) -> None:
        self._list_file_validation_state_obj().pending = value

    @property
    def _list_file_validation_start_scheduled(self) -> bool:
        return bool(self._list_file_validation_state_obj().start_scheduled)

    @_list_file_validation_start_scheduled.setter
    def _list_file_validation_start_scheduled(self, value: bool) -> None:
        self._list_file_validation_state_obj().start_scheduled = bool(value)

    def _on_list_file_save_clicked(self) -> None:
        if self._loading or not self._profile_key or self._list_file_text is None:
            return
        self._request_list_file_save(
            self._profile_key,
            str(self.__dict__.get("_list_file_text_snapshot", "") or ""),
        )

    def _request_list_file_save(self, profile_key: str, text: str) -> None:
        profile_key = str(profile_key or "").strip()
        if not profile_key:
            return
        text = str(text or "")
        if self._profile_setup_write_is_running():
            state = self._list_file_save_state_obj()
            if not (state.start_scheduled and state.has_pending()):
                state.pending = (profile_key, text)
            self._queue_profile_setup_write_operation(
                {"kind": "list_file_save", "profile_key": profile_key, "text": text}
            )
            return
        self._start_list_file_save_worker(profile_key, text)

    def _start_list_file_save_worker(self, profile_key: str, text: str) -> None:
        runtime = self._worker_runtime("_list_file_save_runtime")
        self._list_file_save_request_id += 1
        request_id = self._list_file_save_request_id
        if self._list_file_status_label is not None:
            set_profile_list_status_text(self._list_file_status_label, "Сохранение списка...")
        if self._list_file_save_button is not None:
            set_widget_enabled_if_changed(self._list_file_save_button, False)
        _request_id, worker = runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: self.create_profile_list_file_save_worker(
                request_id,
                profile_key,
                str(text or ""),
                parent=self,
            ),
            on_loaded=self._on_list_file_save_finished,
            on_failed=self._on_list_file_save_failed,
            on_finished=self._on_list_file_save_worker_finished,
            loaded_signal_name="saved",
        )
        self._list_file_save_runtime_worker = worker

    def _on_list_file_save_finished(self, request_id: int, state, payload=None) -> None:
        if request_id != self._list_file_save_request_id:
            return
        if self._list_file_save_state_obj().has_pending():
            return
        payload, apply_signature = _profile_setup_payload_and_apply_signature(payload)
        if state is not None:
            self._apply_list_file_editor_state(state)
        if self._list_file_status_label is not None:
            set_profile_list_status_text(self._list_file_status_label, "Список сохранён.")
        if payload is None:
            self.reload_current_profile()
            self._on_profile_changed_callback(self._profile_key, "list_file")
        elif self.__dict__.get("_payload") is payload:
            pass
        else:
            self._payload = payload
            self._schedule_profile_setup_payload_apply(payload, apply_signature=apply_signature)
            self._on_profile_changed_callback(self._profile_key, "list_file", getattr(payload, "item", None))
        InfoBar.success(
            title="Список сохранён",
            content="Файл списка обновлён.",
            parent=self.window(),
        )

    def _on_list_file_save_failed(self, request_id: int, error: str) -> None:
        if request_id != self._list_file_save_request_id:
            return
        if self._list_file_save_state_obj().has_pending():
            return
        log(f"{self.__class__.__name__}: не удалось сохранить файл списка profile: {error}", "ERROR")
        self._render_list_file_validation((), fallback_error=str(error))
        if self._list_file_save_button is not None:
            set_widget_enabled_if_changed(self._list_file_save_button, True)
        InfoBar.error(title="Ошибка", content=str(error), parent=self.window())

    def _on_list_file_save_worker_finished(self, worker) -> None:
        if not self._accept_current_profile_setup_worker_finished("_list_file_save_runtime_worker", worker):
            return
        if self._start_next_profile_setup_write_operation():
            return
        if self._list_file_save_state_obj().has_pending():
            self._schedule_pending_list_file_save_start()

    def _schedule_pending_list_file_save_start(self, profile_key: str | None = None, text: str | None = None) -> None:
        state = self._list_file_save_state_obj()
        if profile_key is not None or text is not None:
            state.pending = (str(profile_key or ""), str(text or ""))

        def _single_shot(delay: int, callback) -> None:
            try:
                QTimer.singleShot(delay, callback)
            except Exception:
                callback()

        state.schedule_start(_single_shot, self._run_scheduled_list_file_save_start)

    def _run_scheduled_list_file_save_start(self) -> None:
        pending = self._list_file_save_state_obj().take_pending_for_scheduled_start(
            cleanup_in_progress=self.__dict__.get("_cleanup_in_progress", False),
        )
        if not pending:
            return
        profile_key, text = pending
        if self._profile_setup_write_is_running():
            self._list_file_save_state_obj().pending = (str(profile_key or ""), str(text or ""))
            self._queue_profile_setup_write_operation(
                {
                    "kind": "list_file_save",
                    "profile_key": str(profile_key or ""),
                    "text": str(text or ""),
                }
            )
            return
        self._start_list_file_save_worker(str(profile_key or ""), str(text or ""))

    def _list_file_save_state_obj(self) -> LatestValueWorkerState:
        state = self.__dict__.get("_list_file_save_state")
        runtime = self.__dict__.get("_list_file_save_runtime")
        if state is None:
            pending = self.__dict__.pop("_pending_list_file_save", None)
            scheduled = self.__dict__.pop("_scheduled_list_file_save", None)
            start_scheduled = bool(self.__dict__.pop("_list_file_save_start_scheduled", False))
            state = LatestValueWorkerState(
                runtime,
                empty_value=None,
                pending=scheduled if scheduled is not None else pending,
                start_scheduled=start_scheduled,
            )
            self.__dict__["_list_file_save_state"] = state
        elif getattr(state, "runtime", None) is None and runtime is not None:
            state.runtime = runtime
        return state

    @property
    def _pending_list_file_save(self):
        return self._list_file_save_state_obj().pending

    @_pending_list_file_save.setter
    def _pending_list_file_save(self, value) -> None:
        self._list_file_save_state_obj().pending = value

    @property
    def _scheduled_list_file_save(self):
        return self._list_file_save_state_obj().pending

    @_scheduled_list_file_save.setter
    def _scheduled_list_file_save(self, value) -> None:
        self._list_file_save_state_obj().pending = value

    @property
    def _list_file_save_start_scheduled(self) -> bool:
        return bool(self._list_file_save_state_obj().start_scheduled)

    @_list_file_save_start_scheduled.setter
    def _list_file_save_start_scheduled(self, value: bool) -> None:
        self._list_file_save_state_obj().start_scheduled = bool(value)

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
            set_profile_list_error_text(self._list_file_error_label, "Неверные строки:\n" + "\n".join(lines))
            set_widget_visible_if_changed(self._list_file_error_label, True)
            return
        if fallback_error:
            set_profile_list_error_text(self._list_file_error_label, fallback_error)
            set_widget_visible_if_changed(self._list_file_error_label, True)
            return
        set_widget_text_if_changed(self._list_file_error_label, "")
        set_widget_visible_if_changed(self._list_file_error_label, False)

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
            set_widget_style_sheet_if_changed(self._list_file_base_text, normal_style)
        set_widget_style_sheet_if_changed(self._list_file_text, error_style if has_error else normal_style)
        if self._list_file_error_label is not None:
            set_widget_style_sheet_if_changed(
                self._list_file_error_label,
                f"color: {error_color}; background: transparent;",
            )
        if self._list_file_status_label is not None:
            set_widget_style_sheet_if_changed(
                self._list_file_status_label,
                f"color: {tokens.fg_faint}; background: transparent;",
            )

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
                set_widget_enabled_if_changed(button, editable)
        if self._favorite_button is not None:
            favorite_text = "Убрать из избранного" if state.favorite else "В избранное"
            favorite_action_name = (
                "Убрать стратегию из избранного"
                if state.favorite
                else "Добавить стратегию в избранное"
            )
            set_widget_text_if_changed(self._favorite_button, favorite_text)
            set_control_accessibility(
                self._favorite_button,
                name=favorite_action_name,
                description="Добавляет текущую готовую стратегию в избранное или убирает её оттуда.",
            )
            _set_strategy_favorite_button_state(
                self._favorite_button,
                action_name=favorite_action_name,
                favorite=state.favorite,
            )
        if self._work_button is not None:
            work_selected = state.rating == "work"
            set_widget_property_if_changed(self._work_button, "selected", work_selected)
            _set_strategy_feedback_button_state(
                self._work_button,
                action_name="Отметить стратегию как рабочую",
                selected=work_selected,
            )
        if self._notwork_button is not None:
            notwork_selected = state.rating == "notwork"
            set_widget_property_if_changed(self._notwork_button, "selected", notwork_selected)
            _set_strategy_feedback_button_state(
                self._notwork_button,
                action_name="Отметить стратегию как нерабочую",
                selected=notwork_selected,
            )
        if self._clear_feedback_button is not None:
            _set_strategy_clear_feedback_button_state(
                self._clear_feedback_button,
                rating=state.rating,
            )

    def _apply_editable_settings(self, payload) -> None:
        is_preset_mode = is_preset_launch_method(self.launch_method)
        is_winws2 = is_zapret2_launch_method(self.launch_method)
        if not is_preset_mode:
            if self._settings_container is not None:
                set_widget_visible_if_changed(self._settings_container, False)
            return

        filter_enabled = bool(getattr(payload, "editable_filter_enabled", True))
        available_kinds = tuple(getattr(payload, "editable_filter_kinds", ()) or ())
        filter_switchable = filter_enabled and len({kind for kind in available_kinds if kind in {"hostlist", "ipset"}}) > 1
        if self._settings_container is not None:
            set_widget_visible_if_changed(self._settings_container, is_winws2 or filter_switchable)
        self._rebuild_filter_kind_combo(
            available_kinds,
            str(getattr(payload, "editable_filter_kind", "") or "hostlist"),
        )
        set_combo_by_data(self._filter_combo, getattr(payload, "editable_filter_kind", "") or "hostlist")
        set_widget_text_if_changed(self._filter_value, str(getattr(payload, "editable_filter_value", "") or ""))
        set_widget_visible_if_changed(self._filter_combo, filter_switchable)
        set_widget_visible_if_changed(self._filter_value, filter_switchable)
        for widget in (
            self._in_range_label,
            self._in_range_mode,
            self._in_range_value,
            self._out_range_label,
            self._out_range_mode,
            self._out_range_value,
        ):
            if widget is not None:
                set_widget_visible_if_changed(widget, is_winws2)
        set_range_controls(self._in_range_mode, self._in_range_value, getattr(payload, "in_range", "") or "x")
        set_range_controls(self._out_range_mode, self._out_range_value, getattr(payload, "out_range", "") or "a")
        self._update_all_range_tooltips()
        self._update_profile_setup_accessibility()

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
        payload = self.__dict__.get("_payload")
        if payload is not None and (
            str(getattr(payload, "editable_filter_kind", "") or "hostlist") == request["filter_kind"]
            and str(getattr(payload, "editable_filter_value", "") or "") == request["filter_value"]
            and str(getattr(payload, "in_range", "") or "x") == request["in_range"]
            and str(getattr(payload, "out_range", "") or "a") == request["out_range"]
        ):
            return
        self._request_settings_save(request)

    def _request_settings_save(self, request: dict) -> None:
        request = dict(request)
        if self._profile_setup_write_is_running():
            if self.__dict__.get("_pending_settings_save") == dict(request):
                return
            self._pending_settings_save = request
            self._queue_profile_setup_write_operation({"kind": "settings_save", "request": request})
            return
        self._start_settings_save_worker(request)

    def _start_settings_save_worker(self, request: dict) -> None:
        runtime = self._worker_runtime("_settings_save_runtime")
        self._settings_save_request_id += 1
        request_id = self._settings_save_request_id
        _request_id, worker = runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: self.create_profile_settings_save_worker(
                request_id,
                profile_key=str(request.get("profile_key") or ""),
                filter_kind=str(request.get("filter_kind") or ""),
                filter_value=str(request.get("filter_value") or ""),
                in_range=str(request.get("in_range") or ""),
                out_range=str(request.get("out_range") or ""),
                parent=self,
            ),
            on_loaded=self._on_settings_save_finished,
            on_failed=self._on_settings_save_failed,
            on_finished=self._on_settings_save_worker_finished,
            loaded_signal_name="saved",
        )
        self._settings_save_runtime_worker = worker

    def _on_settings_save_finished(self, request_id: int, profile_key: str, payload=None) -> None:
        if request_id != self._settings_save_request_id:
            return
        if self._pending_settings_save:
            return
        payload, apply_signature = _profile_setup_payload_and_apply_signature(payload)
        new_key = str(profile_key or "").strip()
        old_key = str(self._profile_key or "").strip()
        if new_key:
            self._profile_key = new_key
        if payload is None:
            self.reload_current_profile()
            self._on_profile_changed_callback(self._profile_key, "settings")
            return
        if self.__dict__.get("_payload") is payload and (not new_key or new_key == old_key):
            return
        self._payload = payload
        self._schedule_profile_setup_payload_apply(payload, apply_signature=apply_signature)
        self._on_profile_changed_callback(self._profile_key, "settings", getattr(payload, "item", None))

    def _on_settings_save_failed(self, request_id: int, error: str) -> None:
        if request_id != self._settings_save_request_id:
            return
        if self._pending_settings_save:
            return
        log(f"{self.__class__.__name__}: не удалось сохранить настройки профиля: {error}", "ERROR")

    def _on_settings_save_worker_finished(self, worker) -> None:
        if not self._accept_current_profile_setup_worker_finished("_settings_save_runtime_worker", worker):
            return
        if self._start_next_profile_setup_write_operation():
            return
        pending = self._pending_settings_save
        self._pending_settings_save = None
        if pending:
            self._schedule_profile_setup_write_operation_start(
                {"kind": "settings_save", "request": dict(pending)}
            )

    def _on_raw_profile_save_clicked(self) -> None:
        if self._loading or not self._profile_key or self._raw_profile_text is None:
            return
        self._request_raw_profile_save(self._profile_key, None)

    def _resolve_raw_profile_save_text(self, raw_text) -> str:
        if raw_text is not None:
            return str(raw_text or "")
        cached = self.__dict__.get("_raw_profile_text_cache")
        if cached is not None:
            return str(cached or "")
        editor = self.__dict__.get("_raw_profile_text")
        if editor is None:
            return ""
        try:
            text = str(editor.toPlainText() or "")
        except Exception:
            text = ""
        self._raw_profile_text_cache = text
        return text

    def _request_raw_profile_save(self, profile_key: str, raw_text: str | None) -> None:
        profile_key = str(profile_key or "").strip()
        if not profile_key:
            return
        if self._profile_setup_write_is_running():
            self._raw_profile_save_state_obj().pending = (profile_key, raw_text)
            self._queue_profile_setup_write_operation(
                {"kind": "raw_profile_save", "profile_key": profile_key, "text": raw_text}
            )
            return
        self._start_raw_profile_save_worker(profile_key, raw_text)

    def _start_raw_profile_save_worker(self, profile_key: str, raw_text: str | None) -> None:
        runtime = self._worker_runtime("_raw_profile_save_runtime")
        self._raw_profile_save_request_id += 1
        request_id = self._raw_profile_save_request_id
        raw_text = self._resolve_raw_profile_save_text(raw_text)
        if self._raw_profile_save_button is not None:
            set_widget_enabled_if_changed(self._raw_profile_save_button, False)
        _request_id, worker = runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: self.create_profile_raw_text_save_worker(
                request_id,
                profile_key,
                str(raw_text or ""),
                parent=self,
            ),
            on_loaded=self._on_raw_profile_save_finished,
            on_failed=self._on_raw_profile_save_failed,
            on_finished=self._on_raw_profile_save_worker_finished,
            loaded_signal_name="saved",
        )
        self._raw_profile_save_runtime_worker = worker

    def _on_raw_profile_save_finished(self, request_id: int, profile_key: str, payload=None) -> None:
        if request_id != self._raw_profile_save_request_id:
            return
        if self._raw_profile_save_state_obj().has_pending():
            return
        payload, apply_signature = _profile_setup_payload_and_apply_signature(payload)
        old_key = str(self._profile_key or "").strip()
        new_key = str(profile_key or "").strip()
        if new_key:
            self._profile_key = new_key
        if payload is None:
            self.reload_current_profile()
            self._on_profile_changed_callback(self._profile_key, "raw_profile")
        elif self.__dict__.get("_payload") is payload and (not new_key or new_key == old_key):
            pass
        else:
            self._payload = payload
            self._schedule_profile_setup_payload_apply(payload, apply_signature=apply_signature)
            self._on_profile_changed_callback(self._profile_key, "raw_profile", getattr(payload, "item", None))
        InfoBar.success(
            title="Profile сохранён",
            content="Текст profile обновлён только в текущем preset.",
            parent=self.window(),
        )

    def _on_raw_profile_save_failed(self, request_id: int, error: str) -> None:
        if request_id != self._raw_profile_save_request_id:
            return
        if self._raw_profile_save_state_obj().has_pending():
            return
        if self._raw_profile_save_button is not None:
            set_widget_enabled_if_changed(self._raw_profile_save_button, True)
        log(f"{self.__class__.__name__}: не удалось сохранить сырой текст profile: {error}", "ERROR")
        InfoBar.error(
            title="Ошибка",
            content=str(error),
            parent=self.window(),
        )

    def _on_raw_profile_save_worker_finished(self, worker) -> None:
        if not self._accept_current_profile_setup_worker_finished("_raw_profile_save_runtime_worker", worker):
            return
        if self._start_next_profile_setup_write_operation():
            return
        pending = self._raw_profile_save_state_obj().pending
        self._raw_profile_save_state_obj().pending = None
        if pending:
            profile_key, raw_text = pending
            self._schedule_profile_setup_write_operation_start(
                {
                    "kind": "raw_profile_save",
                    "profile_key": str(profile_key or ""),
                    "text": raw_text,
                }
            )

    def _raw_profile_save_state_obj(self) -> LatestValueWorkerState:
        state = self.__dict__.get("_raw_profile_save_state")
        runtime = self.__dict__.get("_raw_profile_save_runtime")
        if state is None:
            pending = self.__dict__.pop("_pending_raw_profile_save", None)
            state = LatestValueWorkerState(
                runtime,
                empty_value=None,
                pending=pending,
            )
            self.__dict__["_raw_profile_save_state"] = state
        elif getattr(state, "runtime", None) is None and runtime is not None:
            state.runtime = runtime
        return state

    @property
    def _pending_raw_profile_save(self):
        return self._raw_profile_save_state_obj().pending

    @_pending_raw_profile_save.setter
    def _pending_raw_profile_save(self, value) -> None:
        self._raw_profile_save_state_obj().pending = value

    def _on_enabled_changed(self, state: int) -> None:
        if self._loading or not self._profile_key:
            return
        enabled = bool(state == Qt.CheckState.Checked.value or state == 2)
        runtime = self._worker_runtime("_enabled_save_runtime")
        worker_state = self._enabled_save_state_obj()
        item = getattr(self.__dict__.get("_payload"), "item", None)
        if not runtime.is_running() and item is not None and bool(getattr(item, "enabled", False)) == enabled:
            return
        if worker_state.is_busy():
            if self.__dict__.get("_enabled_save_runtime_enabled") != enabled:
                worker_state.pending = enabled
            return
        if self._profile_setup_write_is_running():
            if self.__dict__.get("_enabled_save_runtime_enabled") != enabled:
                worker_state.pending = enabled
                self._queue_profile_setup_write_operation({"kind": "enabled_save", "enabled": enabled})
            return
        self._start_enabled_save_worker(enabled)

    def _start_enabled_save_worker(self, enabled: bool) -> None:
        runtime = self._worker_runtime("_enabled_save_runtime")
        self._enabled_save_request_id += 1
        request_id = self._enabled_save_request_id
        if self._enabled_checkbox is not None:
            set_widget_enabled_if_changed(self._enabled_checkbox, False)
        self._enabled_save_runtime_enabled = bool(enabled)
        _request_id, worker = runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: self.create_profile_enabled_save_worker(
                request_id,
                profile_key=self._profile_key,
                enabled=enabled,
                filter_kind=self._current_filter_kind(),
                filter_value=self._current_filter_value(),
                parent=self,
            ),
            on_loaded=self._on_enabled_save_finished,
            on_failed=self._on_enabled_save_failed,
            on_finished=self._on_enabled_save_worker_finished,
            loaded_signal_name="saved",
        )
        self._enabled_save_runtime_worker = worker

    def _on_enabled_save_finished(self, request_id: int, profile_key: str, enabled: bool, payload=None) -> None:
        if request_id != self._enabled_save_request_id:
            return
        if self._enabled_save_state_obj().has_pending():
            return
        payload, apply_signature = _profile_setup_payload_and_apply_signature(payload)
        old_key = str(self._profile_key or "").strip()
        new_key = str(profile_key or "").strip()
        if payload is not None:
            if self.__dict__.get("_payload") is payload and (not new_key or new_key == old_key):
                return
            if new_key:
                self._profile_key = new_key
            self._payload = payload
            self._schedule_profile_setup_payload_apply(payload, apply_signature=apply_signature)
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
                set_widget_checked_if_changed(checkbox, bool(enabled))
                set_widget_enabled_if_changed(checkbox, True)
            finally:
                self._loading = False
        return updated_item

    def _on_enabled_save_failed(self, request_id: int, error: str) -> None:
        if request_id != self._enabled_save_request_id:
            return
        if self._enabled_save_state_obj().has_pending():
            return
        if self._enabled_checkbox is not None:
            set_widget_enabled_if_changed(self._enabled_checkbox, True)
        log(f"{self.__class__.__name__}: не удалось изменить состояние профиля: {error}", "ERROR")

    def _on_enabled_save_worker_finished(self, worker) -> None:
        if not self._accept_current_profile_setup_worker_finished("_enabled_save_runtime_worker", worker):
            return
        self._enabled_save_runtime_enabled = None
        if self._start_next_profile_setup_write_operation():
            return
        pending = self._enabled_save_state_obj().pending
        self._enabled_save_state_obj().pending = None
        if pending is None:
            return
        item = getattr(self.__dict__.get("_payload"), "item", None)
        if item is not None and bool(getattr(item, "enabled", False)) == bool(pending):
            if self._enabled_checkbox is not None:
                set_widget_enabled_if_changed(self._enabled_checkbox, True)
            return
        self._enabled_save_state_obj().pending = bool(pending)
        self._schedule_enabled_save_worker_start()

    def _schedule_enabled_save_worker_start(self) -> None:
        state = self._enabled_save_state_obj()

        def _single_shot(delay: int, callback) -> None:
            try:
                QTimer.singleShot(delay, callback)
            except Exception:
                callback()

        state.schedule_start(_single_shot, self._run_scheduled_enabled_save_worker_start)

    def _run_scheduled_enabled_save_worker_start(self) -> None:
        pending = self._enabled_save_state_obj().take_pending_for_scheduled_start(
            cleanup_in_progress=self.__dict__.get("_cleanup_in_progress", False),
        )
        if pending is None:
            return
        item = getattr(self.__dict__.get("_payload"), "item", None)
        if item is not None and bool(getattr(item, "enabled", False)) == bool(pending):
            if self._enabled_checkbox is not None:
                set_widget_enabled_if_changed(self._enabled_checkbox, True)
            return
        enabled = bool(pending)
        self._start_enabled_save_worker(bool(enabled))

    def _enabled_save_state_obj(self) -> LatestValueWorkerState:
        state = self.__dict__.get("_enabled_save_state")
        runtime = self.__dict__.get("_enabled_save_runtime")
        if state is None:
            pending = self.__dict__.pop("_pending_enabled_save", None)
            start_scheduled = bool(self.__dict__.pop("_enabled_save_start_scheduled", False))
            state = LatestValueWorkerState(
                runtime,
                empty_value=None,
                pending=pending,
                start_scheduled=start_scheduled,
            )
            self.__dict__["_enabled_save_state"] = state
        elif getattr(state, "runtime", None) is None and runtime is not None:
            state.runtime = runtime
        return state

    @property
    def _pending_enabled_save(self):
        return self._enabled_save_state_obj().pending

    @_pending_enabled_save.setter
    def _pending_enabled_save(self, value) -> None:
        self._enabled_save_state_obj().pending = value

    @property
    def _enabled_save_start_scheduled(self) -> bool:
        return bool(self._enabled_save_state_obj().start_scheduled)

    @_enabled_save_start_scheduled.setter
    def _enabled_save_start_scheduled(self, value: bool) -> None:
        self._enabled_save_state_obj().start_scheduled = bool(value)

    def _on_strategy_list_activated(self, strategy_id: str) -> None:
        if self._loading or not self._profile_key:
            return
        strategy_id = str(strategy_id or "").strip()
        if not strategy_id or strategy_id in {"none", "custom"}:
            return
        item = getattr(getattr(self, "_payload", None), "item", None)
        if bool(getattr(item, "in_preset", False)) and not bool(getattr(item, "enabled", False)):
            return
        if strategy_id == _current_strategy_id(self._payload):
            return
        self._apply_strategy_locally(strategy_id)
        self._request_strategy_apply(strategy_id)

    def _request_strategy_apply(self, strategy_id: str) -> None:
        strategy_id = str(strategy_id or "").strip()
        branch_id = _current_strategy_branch_id(self._payload)
        if self._profile_setup_write_is_running():
            if (
                strategy_id != str(getattr(self, "_strategy_apply_runtime_strategy_id", "") or "").strip()
                or branch_id != str(getattr(self, "_strategy_apply_runtime_branch_id", "") or "").strip()
            ):
                self._pending_strategy_apply = (strategy_id, branch_id) if branch_id else strategy_id
                self._queue_profile_setup_write_operation(
                    {
                        "kind": "strategy_apply",
                        "strategy_id": strategy_id,
                        "branch_id": branch_id,
                    }
                )
            return
        self._start_strategy_apply_worker(strategy_id, strategy_branch_id=branch_id)

    def _start_strategy_apply_worker(self, strategy_id: str, *, strategy_branch_id: str = "") -> None:
        strategy_id = str(strategy_id or "").strip()
        strategy_branch_id = str(strategy_branch_id or "").strip()
        if not strategy_id or not self._profile_key:
            return
        runtime = self._worker_runtime("_strategy_apply_runtime")
        self._strategy_apply_request_id = int(getattr(self, "_strategy_apply_request_id", 0) or 0) + 1
        request_id = self._strategy_apply_request_id
        self._strategy_apply_runtime_strategy_id = strategy_id
        self._strategy_apply_runtime_branch_id = strategy_branch_id
        worker_kwargs = {
            "profile_key": self._profile_key,
            "strategy_id": strategy_id,
            "parent": self,
        }
        if strategy_branch_id:
            worker_kwargs["strategy_branch_id"] = strategy_branch_id
        _request_id, worker = runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: self.create_profile_strategy_apply_worker(
                request_id,
                **worker_kwargs,
            ),
            on_loaded=self._on_strategy_apply_finished,
            on_failed=self._on_strategy_apply_failed,
            on_finished=self._on_strategy_apply_worker_finished,
            loaded_signal_name="applied",
        )
        self._strategy_apply_runtime_worker = worker

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
        pending = getattr(self, "_pending_strategy_apply", None)
        pending_strategy_id = ""
        if isinstance(pending, tuple):
            pending_strategy_id = str(pending[0] or "").strip()
        else:
            pending_strategy_id = str(pending or "").strip()
        if pending_strategy_id and pending_strategy_id != str(strategy_id or "").strip():
            return
        previous_key = self._profile_key
        new_key = str(profile_key or "").strip()
        if new_key:
            self._profile_key = new_key
        item = getattr(getattr(self, "_payload", None), "item", None)
        if self._profile_key == previous_key and strategy_id == _current_strategy_id(self._payload):
            self._on_profile_changed_callback(self._profile_key, "strategy", item)
            return
        if payload is not None:
            payload, apply_signature = _profile_setup_payload_and_apply_signature(payload)
            branch_id = str(getattr(self, "_strategy_apply_runtime_branch_id", "") or "").strip()
            if branch_id:
                payload = _payload_with_strategy_branch(payload, branch_id)
                apply_signature = None
            self._payload = payload
            self._schedule_profile_setup_payload_apply(payload, apply_signature=apply_signature)
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
        if getattr(self, "_pending_strategy_apply", None):
            return
        log(f"{self.__class__.__name__}: не удалось применить стратегию: {error}", "ERROR")
        self.reload_current_profile()

    def _on_strategy_apply_worker_finished(self, worker) -> None:
        if not self._accept_current_profile_setup_worker_finished("_strategy_apply_runtime_worker", worker):
            return
        self._strategy_apply_runtime_strategy_id = ""
        self._strategy_apply_runtime_branch_id = ""
        if self._start_next_profile_setup_write_operation():
            return
        pending = getattr(self, "_pending_strategy_apply", None)
        self._pending_strategy_apply = None
        if pending:
            if isinstance(pending, tuple):
                self._schedule_profile_setup_write_operation_start(
                    {
                        "kind": "strategy_apply",
                        "strategy_id": str(pending[0] or ""),
                        "branch_id": str(pending[1] or ""),
                    }
                )
            else:
                self._schedule_profile_setup_write_operation_start(
                    {
                        "kind": "strategy_apply",
                        "strategy_id": str(pending or ""),
                        "branch_id": "",
                    }
                )

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
        branches = tuple(getattr(payload, "strategy_branches", ()) or ())
        current_branch_id = _current_strategy_branch_id(payload)
        if branches and current_branch_id:
            entry_args = str(getattr(entry, "args", "") or "").strip()
            updated_branch_items = []
            for branch in branches:
                if str(getattr(branch, "branch_id", "") or "").strip() != current_branch_id:
                    updated_branch_items.append(branch)
                    continue
                raw_strategy_text = _branch_raw_strategy_text(branch, entry_args)
                updated_branch = replace(
                    branch,
                    strategy_id=strategy_id,
                    strategy_name=str(getattr(entry, "name", "") or strategy_id),
                    raw_strategy_text=raw_strategy_text,
                )
                updated_branch_items.append(
                    replace(
                        updated_branch,
                        match_tab_text=_branch_match_tab_text(payload, updated_branch, raw_strategy_text),
                    )
                )
            updated_branches = tuple(updated_branch_items)
            selected_branch = next(
                (
                    branch
                    for branch in updated_branches
                    if str(getattr(branch, "branch_id", "") or "").strip() == current_branch_id
                ),
                None,
            )
            next_raw_strategy_text = str(getattr(selected_branch, "raw_strategy_text", "") or entry_args)
            self._payload = replace(
                payload,
                strategy_branches=updated_branches,
                raw_strategy_text=next_raw_strategy_text,
                match_tab_text=str(getattr(selected_branch, "match_tab_text", "") or ""),
                current_strategy_state=state,
            )
            self._strategy_list.set_current_strategy_id(strategy_id)
            self._apply_strategy_branch_selector(self._payload)
            self._apply_feedback_buttons(self._payload)
            if self._match_tab_built:
                self._apply_match_tab_payload()
            return True

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
            match_tab_text=build_profile_setup_match_tab_text(
                match_summary=str(getattr(payload, "match_summary", "") or ""),
                strategy_id=strategy_id,
                strategy_name=str(getattr(entry, "name", "") or strategy_id),
                raw_strategy_text=str(getattr(entry, "args", "") or ""),
            ),
            current_strategy_state=state,
        )
        self._strategy_list.set_current_strategy_id(strategy_id)
        self._apply_feedback_buttons(self._payload)
        if self._match_tab_built:
            self._apply_match_tab_payload()
        return True

    def _set_current_strategy_feedback(self, *, rating: str) -> None:
        if self._loading or not self._profile_key:
            return
        next_rating = str(rating or "").strip()
        state = getattr(getattr(self, "_payload", None), "current_strategy_state", None)
        current_rating = str(getattr(state, "rating", "") or "").strip()
        if next_rating == current_rating:
            return
        self._request_strategy_feedback_save({"rating": next_rating, "favorite": None})

    def _toggle_current_strategy_favorite(self) -> None:
        if self._loading or not self._profile_key or self._payload is None:
            return
        current = bool(self._payload.current_strategy_state.favorite)
        self._request_strategy_feedback_save({"rating": None, "favorite": not current})

    def _request_strategy_feedback_save(self, request: dict) -> None:
        runtime = self._worker_runtime("_strategy_feedback_save_runtime")
        if runtime.is_running() or self.__dict__.get("_strategy_feedback_save_start_scheduled", False):
            self._merge_pending_strategy_feedback_save(request)
            return
        self._start_strategy_feedback_save_worker(request)

    def _merge_pending_strategy_feedback_save(self, request: dict) -> None:
        pending = dict(self.__dict__.get("_pending_strategy_feedback_save") or {})
        next_request = dict(request or {})
        for key in ("rating", "favorite"):
            if key in next_request and next_request.get(key) is not None:
                pending[key] = next_request.get(key)
            elif key not in pending:
                pending[key] = next_request.get(key)
        self._pending_strategy_feedback_save = pending

    def _start_strategy_feedback_save_worker(self, request: dict) -> None:
        if not self._profile_key:
            return
        item = getattr(getattr(self, "_payload", None), "item", None)
        strategy_id = _current_strategy_id(self._payload)
        if not strategy_id or strategy_id in {"none", "custom"}:
            return
        runtime = self._worker_runtime("_strategy_feedback_save_runtime")
        self._strategy_feedback_save_request_id = int(getattr(self, "_strategy_feedback_save_request_id", 0) or 0) + 1
        request_id = self._strategy_feedback_save_request_id
        _request_id, worker = runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: self.create_profile_strategy_feedback_save_worker(
                request_id,
                profile_key=self._profile_key,
                strategy_id=strategy_id,
                rating=request.get("rating"),
                favorite=request.get("favorite"),
                parent=self,
            ),
            on_loaded=self._on_strategy_feedback_save_finished,
            on_failed=self._on_strategy_feedback_save_failed,
            on_finished=self._on_strategy_feedback_save_worker_finished,
            loaded_signal_name="saved",
        )
        self._strategy_feedback_save_runtime_worker = worker

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
        current_strategy_id = _current_strategy_id(self._payload)
        if str(strategy_id or "").strip() != current_strategy_id:
            return
        next_state = state if isinstance(state, ProfileStrategyState) else ProfileStrategyState()
        current_state = getattr(getattr(self, "_payload", None), "current_strategy_state", None)
        if (
            current_state == next_state
            and str(getattr(item, "rating", "") or "") == str(getattr(next_state, "rating", "") or "")
            and bool(getattr(item, "favorite", False)) == bool(getattr(next_state, "favorite", False))
        ):
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
        if self.__dict__.get("_pending_strategy_feedback_save"):
            return
        log(f"{self.__class__.__name__}: не удалось обновить оценку стратегии: {error}", "ERROR")
        self.reload_current_profile()

    def _on_strategy_feedback_save_worker_finished(self, worker) -> None:
        if not self._accept_current_profile_setup_worker_finished("_strategy_feedback_save_runtime_worker", worker):
            return
        pending = self.__dict__.get("_pending_strategy_feedback_save")
        if pending:
            self._schedule_strategy_feedback_save_worker_start()

    def _schedule_strategy_feedback_save_worker_start(self) -> None:
        if self.__dict__.get("_strategy_feedback_save_start_scheduled", False):
            return
        self._strategy_feedback_save_start_scheduled = True
        try:
            QTimer.singleShot(0, self._run_scheduled_strategy_feedback_save_worker_start)
        except Exception:
            self._run_scheduled_strategy_feedback_save_worker_start()

    def _run_scheduled_strategy_feedback_save_worker_start(self) -> None:
        self._strategy_feedback_save_start_scheduled = False
        request = self.__dict__.get("_pending_strategy_feedback_save")
        self._pending_strategy_feedback_save = None
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if not request:
            return
        self._start_strategy_feedback_save_worker(dict(request or {}))

    def cleanup(self) -> None:
        self._cleanup_in_progress = True
        timer = self.__dict__.get("_settings_save_timer")
        if timer is not None:
            try:
                timer.stop()
            except Exception:
                pass
        timer = self.__dict__.get("_list_file_validation_timer")
        if timer is not None:
            try:
                timer.stop()
            except Exception:
                pass
        for attr in (
            "_pending_list_file_load",
            "_pending_list_file_state_apply",
            "_pending_list_file_save",
            "_scheduled_list_file_save",
            "_pending_list_file_validation",
            "_pending_settings_save",
            "_pending_raw_profile_save",
            "_pending_enabled_save",
            "_pending_strategy_apply",
            "_pending_strategy_feedback_save",
            "_scheduled_profile_setup_write_operation",
            "_pending_profile_setup_payload_apply",
        ):
            setattr(self, attr, None)
        self._list_file_state_apply_scheduled = False
        self._setup_load_dirty = False
        self._setup_load_start_scheduled = False
        self._list_file_load_state_obj().reset()
        self._list_file_validation_state_obj().reset()
        self._list_file_save_state_obj().reset()
        self._raw_profile_save_state_obj().reset()
        self._enabled_save_state_obj().reset()
        self._strategy_feedback_save_start_scheduled = False
        self._profile_setup_payload_apply_scheduled = False
        self._profile_setup_write_operation_start_scheduled = False
        self._user_profile_write_operation_start_scheduled = False
        self.__dict__.setdefault("_pending_profile_setup_write_operations", []).clear()
        self.__dict__.setdefault("_pending_user_profile_updates", []).clear()
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
        for attr, warning_prefix, blocking in _PROFILE_SETUP_CLEANUP_RUNTIMES:
            runtime = self.__dict__.get(attr)
            if runtime is None:
                continue
            runtime.stop(blocking=blocking, log_fn=log, warning_prefix=warning_prefix)
            runtime.cancel()
        self._strategy_apply_runtime_strategy_id = ""
        self._enabled_save_runtime_enabled = None
        self._list_file_load_runtime_worker = None
        self._list_file_save_runtime_worker = None
        self._list_file_validation_runtime_worker = None
        self._settings_save_runtime_worker = None
        self._raw_profile_save_runtime_worker = None
        self._enabled_save_runtime_worker = None
        self._strategy_apply_runtime_worker = None
        self._strategy_feedback_save_runtime_worker = None
        self.__dict__.setdefault("_pending_user_profile_operations", []).clear()
        self.__dict__.setdefault("_pending_user_profile_updates", []).clear()
        self.__dict__.setdefault("_pending_user_profile_deletes", []).clear()
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
        strategy_id = _current_strategy_id(self._payload)
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
