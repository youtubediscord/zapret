"""Виджеты списка готовых стратегий profile и их free-функции.

Вынесено из profile_setup_page.py (этап 4, фаза B, чанк M1) без изменения
поведения: классы реэкспортируются из profile.ui.profile_setup_page.
"""

from __future__ import annotations

from dataclasses import replace

from PyQt6.QtCore import QEvent, QModelIndex, QPoint, QRect, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QFontMetrics, QKeySequence, QPainter, QShortcut
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
    QVBoxLayout,
    QWidget,
)

from log.log import log
from profile.strategy_list_filter import ProfileStrategyListFilterWorker, ProfileStrategyListPlan
from profile.strategy_state import ProfileStrategyState
from profile.strategy_visuals import describe_strategy_visual
from qfluentwidgets import (
    BodyLabel,
    ComboBox,
    FluentIcon,
    MenuAnimationType,
    SearchLineEdit,
    TransparentToolButton,
)
from ui.accessibility import (
    remove_line_edit_buttons_from_tab_order,
    set_control_accessibility,
    set_state_text,
)
from ui.fluent_widgets import set_tooltip
from ui.latest_value_worker_state import LatestValueWorkerState
from ui.one_shot_worker_runtime import OneShotWorkerRuntime
from ui.theme import get_cached_qta_pixmap, get_theme_tokens, to_qcolor
from ui.widgets.fluent_item_tooltip import FluentItemToolTipController
from ui.widgets.fluent_scrollbar import install_fluent_scrollbars
from ui.widgets.hover_row import paint_profile_hover_row, profile_hover_row_rect


def _set_widget_text_if_changed(widget, text: str) -> bool:
    """Ленивый мост к profile.ui.profile_setup_page.set_widget_text_if_changed.

    Widget-state сеттеры остаются в модуле страницы (патч-цель тестов по пути
    profile.ui.profile_setup_page.*); ленивый импорт разрывает циклический
    импорт страницы и этого модуля и сохраняет действие патчей."""
    from profile.ui import profile_setup_page

    return profile_setup_page.set_widget_text_if_changed(widget, text)


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
        selected = bool(option.state & QStyle.StateFlag.State_Selected) or bool(
            option.state & QStyle.StateFlag.State_HasFocus
        )

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

    def setItemAccessibleText(self, index: int, text: str) -> None:  # noqa: N802
        if 0 <= int(index) < len(self.items):
            setattr(self.items[int(index)], "accessibleText", str(text or "").strip())

    def _create_accessible_combo_menu(self):
        menu = self._createComboMenu()
        for index, item in enumerate(self.items):
            action = QAction(item.icon, item.text, triggered=lambda _checked=False, row=index: self._onItemClicked(row))
            action.setEnabled(item.isEnabled)
            menu.addAction(action)
            accessible_text = str(getattr(item, "accessibleText", "") or "").strip()
            menu_item = action.property("item")
            if accessible_text and menu_item is not None:
                menu_item.setData(Qt.ItemDataRole.AccessibleTextRole, accessible_text)
                menu_item.setData(Qt.ItemDataRole.AccessibleDescriptionRole, accessible_text)
        return menu

    def _showComboMenu(self) -> None:
        if not self.items:
            return

        menu = self._create_accessible_combo_menu()
        if menu.view.width() < self.width():
            menu.view.setMinimumWidth(self.width())
            menu.adjustSize()

        menu.setMaxVisibleItems(self.maxVisibleItems())
        menu.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        menu.closedSignal.connect(self._onDropMenuClosed)
        self.dropMenu = menu

        if self.currentIndex() >= 0 and self.items:
            menu.setDefaultAction(menu.actions()[self.currentIndex()])

        x = -menu.width() // 2 + menu.layout().contentsMargins().left() + self.width() // 2
        down_pos = self.mapToGlobal(QPoint(x, self.height()))
        down_height = menu.view.heightForAnimation(down_pos, MenuAnimationType.DROP_DOWN)

        up_pos = self.mapToGlobal(QPoint(x, 0))
        up_height = menu.view.heightForAnimation(up_pos, MenuAnimationType.PULL_UP)

        if down_height >= up_height:
            menu.view.adjustSize(down_pos, MenuAnimationType.DROP_DOWN)
            menu.exec(down_pos, aniType=MenuAnimationType.DROP_DOWN)
        else:
            menu.view.adjustSize(up_pos, MenuAnimationType.PULL_UP)
            menu.exec(up_pos, aniType=MenuAnimationType.PULL_UP)

    def _sync_compact_text(self) -> None:
        index = self.currentIndex()
        if index < 0:
            return
        data = str(self.itemData(index))
        compact = self._compact_text_by_data.get(data)
        if compact:
            _set_widget_text_if_changed(self, compact)


class ProfileStrategyListView(QListWidget):
    """Список стратегий, который выбирается клавиатурой так же, как DNS."""

    def keyPressEvent(self, event):  # noqa: N802
        if self._move_current_row_from_keyboard(event.key()):
            event.accept()
            return
        navigation_keys = (
            Qt.Key.Key_Down,
            Qt.Key.Key_Up,
            Qt.Key.Key_Home,
            Qt.Key.Key_End,
            Qt.Key.Key_PageDown,
            Qt.Key.Key_PageUp,
        )
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            item = self.currentItem()
            if item is None:
                item = self._first_selectable_item()
                if item is not None:
                    self.setCurrentItem(item)
            if item is not None:
                self.itemActivated.emit(item)
                event.accept()
                return
        super().keyPressEvent(event)
        if event.key() in navigation_keys:
            self.setFocus(Qt.FocusReason.OtherFocusReason)

    def focusInEvent(self, event):  # noqa: N802
        super().focusInEvent(event)
        if self.currentItem() is None:
            item = self._first_selectable_item()
            if item is not None:
                self.setCurrentItem(item)

    def _first_selectable_item(self):
        for row in range(self.count()):
            item = self.item(row)
            if item is not None and item.flags() & Qt.ItemFlag.ItemIsSelectable:
                return item
        return None

    def _move_current_row_from_keyboard(self, key: int) -> bool:
        if key not in (
            Qt.Key.Key_Down,
            Qt.Key.Key_Up,
            Qt.Key.Key_Home,
            Qt.Key.Key_End,
            Qt.Key.Key_PageDown,
            Qt.Key.Key_PageUp,
        ):
            return False
        count = self.count()
        if count <= 0:
            return False

        row = self.currentRow()
        if key == Qt.Key.Key_Home or row < 0:
            row = 0
        elif key == Qt.Key.Key_End:
            row = count - 1
        elif key == Qt.Key.Key_Down:
            row = min(count - 1, row + 1)
        elif key == Qt.Key.Key_Up:
            row = max(0, row - 1)
        elif key == Qt.Key.Key_PageDown:
            row = min(count - 1, row + 10)
        else:
            row = max(0, row - 10)

        self.setCurrentRow(row)
        item = self.currentItem()
        if item is not None:
            self.scrollToItem(item)
        return True


class ProfileStrategySearchLineEdit(SearchLineEdit):
    """Поиск стратегий, где Enter выбирает текущий результат."""

    activate_current_result = pyqtSignal()
    navigate_results = pyqtSignal(int)
    close_requested = pyqtSignal()

    def keyPressEvent(self, event):  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.close_requested.emit()
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.activate_current_result.emit()
            event.accept()
            return
        if event.key() in (
            Qt.Key.Key_Down,
            Qt.Key.Key_Up,
            Qt.Key.Key_Home,
            Qt.Key.Key_End,
            Qt.Key.Key_PageDown,
            Qt.Key.Key_PageUp,
        ):
            self.navigate_results.emit(int(event.key()))
            event.accept()
            return
        super().keyPressEvent(event)


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
        self._strategy_filter_runtime = OneShotWorkerRuntime()
        self._strategy_filter_state = LatestValueWorkerState(
            self._strategy_filter_runtime,
            empty_value=None,
        )
        self._strategy_filter_timer = QTimer(self)
        self._strategy_filter_timer.setSingleShot(True)
        self._strategy_filter_timer.timeout.connect(self._run_debounced_tree_rebuild)
        self.destroyed.connect(self._cleanup_strategy_filter_worker)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        top_row = QWidget(self)
        top_layout = QHBoxLayout(top_row)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(10)

        self._search = ProfileStrategySearchLineEdit(self)
        self._search.setPlaceholderText("Поиск по готовым стратегиям")
        set_control_accessibility(self._search, name="Поиск готовых стратегий")
        set_tooltip(
            self._search,
            "Поиск по названию, параметрам --lua-desync и описанию готовой стратегии. "
            "Ctrl+F — открыть или закрыть поиск, Esc — закрыть.",
        )
        set_control_accessibility(
            self._search,
            name="Поиск готовых стратегий",
            description=(
                "Поиск по названию, параметрам --lua-desync и описанию готовой стратегии. "
                "После ввода перейдите в список клавишей Tab или нажмите Стрелка вниз, "
                "выберите стратегию стрелками вверх и вниз, "
                "затем нажмите Enter или Пробел. "
                "Esc закрывает поиск и сбрасывает фильтр."
            ),
        )
        remove_line_edit_buttons_from_tab_order(self._search)
        self._search.textChanged.connect(self._apply_filter)
        self._search.close_requested.connect(self.hide_search)
        top_layout.addWidget(self._search, 1)

        self._summary = BodyLabel("")
        set_tooltip(
            self._summary,
            "Сколько готовых стратегий сейчас показано после фильтра поиска.",
        )
        top_layout.addWidget(self._summary)

        self._search_close = TransparentToolButton(FluentIcon.CLOSE, top_row)
        set_tooltip(
            self._search_close,
            "Закрыть поиск и показать все стратегии (Esc).",
        )
        set_control_accessibility(
            self._search_close,
            name="Закрыть поиск стратегий",
            description="Скрывает строку поиска и сбрасывает фильтр списка стратегий.",
        )
        self._search_close.clicked.connect(self.hide_search)
        top_layout.addWidget(self._search_close)

        # Строка поиска скрыта по умолчанию и не занимает место: открывается по Ctrl+F.
        self._search_row = top_row
        self._search_row.hide()
        layout.addWidget(top_row)

        self._search_shortcut = QShortcut(QKeySequence(QKeySequence.StandardKey.Find), self)
        # WindowShortcut: Ctrl+F работает с любым фокусом в окне; защита от
        # срабатывания на других страницах — проверка isVisible() в обработчике.
        self._search_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self._search_shortcut.activated.connect(self._on_search_shortcut)
        self._search_shortcut.activatedAmbiguously.connect(self._on_search_shortcut)

        self._list = ProfileStrategyListView(self)
        self._list.setItemDelegate(ProfileStrategyListDelegate(self._list))
        self._list.setUniformItemSizes(True)
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._list.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._list.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocusProxy(self._list)
        set_control_accessibility(
            self._list,
            name="Список готовых стратегий",
            description="Выберите готовую стратегию стрелками вверх и вниз, затем нажмите Enter или Пробел. Ctrl+F открывает поиск по стратегиям.",
        )
        set_state_text(self._list, "Список готовых стратегий: список пока загружается")
        self._list.setMouseTracking(True)
        self._list.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored)
        self._list.setMinimumHeight(520)
        self._list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._list.currentItemChanged.connect(self._update_current_strategy_accessibility)
        self._list.itemActivated.connect(self._on_item_activated)
        self._list.itemClicked.connect(self._on_item_clicked)
        self._search.activate_current_result.connect(self._activate_current_search_result)
        self._search.navigate_results.connect(self._navigate_strategy_results_from_search)
        self._list.installEventFilter(self)
        self._list.setStyleSheet(
            "QListWidget { background: rgba(255, 255, 255, 0.035); border: none; border-radius: 6px; outline: none; padding: 4px 0; }"
            "QListWidget::viewport { background: transparent; }"
            "QListWidget::item { border: none; padding: 0; }"
            "QListWidget::item:selected { background: transparent; }"
            "QListWidget::item:hover { background: transparent; }"
        )
        self._scrollbars = install_fluent_scrollbars(self._list, vertical=True, horizontal=False)
        layout.addWidget(self._list, 1)
        QWidget.setTabOrder(self._search, self._list)

    def eventFilter(self, watched, event):  # noqa: N802
        if watched is self._list and event.type() == QEvent.Type.FocusIn:
            self._focus_first_strategy_row()
            self._update_current_strategy_accessibility(self._list.currentItem())
            return False
        if watched is self._list and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
                item = self._list.currentItem()
                if item is not None:
                    self._on_item_activated(item)
                    event.accept()
                    return True
        return super().eventFilter(watched, event)

    def _on_search_shortcut(self) -> None:
        if not self.isVisible() or not self.isEnabled():
            return
        # Ctrl+F работает как переключатель: повторное нажатие закрывает
        # поиск и сбрасывает фильтр, как Esc или кнопка закрытия.
        if self._search_row.isVisible():
            self.hide_search()
        else:
            self.show_search()

    def show_search(self) -> None:
        self._search_row.show()
        self._search.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self._search.selectAll()

    def hide_search(self) -> None:
        if self._search.text():
            self._search.clear()
        self._search_row.hide()
        self._list.setFocus(Qt.FocusReason.OtherFocusReason)

    def _activate_current_search_result(self) -> None:
        item = self._list.currentItem()
        if item is None:
            self._focus_first_strategy_row()
            item = self._list.currentItem()
        if item is None:
            return
        self._list.setFocus(Qt.FocusReason.OtherFocusReason)
        self._on_item_activated(item)

    def keyPressEvent(self, event):  # noqa: N802
        if self._handle_strategy_keyboard_event(event):
            return
        super().keyPressEvent(event)

    def _navigate_strategy_results_from_search(self, key: int) -> None:
        self._move_strategy_current_row(int(key))

    def _handle_strategy_keyboard_event(self, event) -> bool:
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            item = self._list.currentItem()
            if item is None:
                self._focus_first_strategy_row()
                item = self._list.currentItem()
            if item is not None:
                self._list.setFocus(Qt.FocusReason.OtherFocusReason)
                self._on_item_activated(item)
                event.accept()
                return True
            return False

        if int(key) not in {
            int(Qt.Key.Key_Down),
            int(Qt.Key.Key_Up),
            int(Qt.Key.Key_Home),
            int(Qt.Key.Key_End),
            int(Qt.Key.Key_PageDown),
            int(Qt.Key.Key_PageUp),
        }:
            return False

        if self._move_strategy_current_row(int(key)):
            event.accept()
            return True
        return False

    def _move_strategy_current_row(self, key: int) -> bool:
        if int(key) not in {
            int(Qt.Key.Key_Down),
            int(Qt.Key.Key_Up),
            int(Qt.Key.Key_Home),
            int(Qt.Key.Key_End),
            int(Qt.Key.Key_PageDown),
            int(Qt.Key.Key_PageUp),
        }:
            return False

        count = self._list.count()
        if count <= 0:
            return False

        row = self._list.currentRow()
        if row < 0:
            row = 0
        elif int(key) == int(Qt.Key.Key_Down):
            row = min(count - 1, row + 1)
        elif int(key) == int(Qt.Key.Key_Up):
            row = max(0, row - 1)
        elif int(key) == int(Qt.Key.Key_Home):
            row = 0
        elif int(key) == int(Qt.Key.Key_End):
            row = count - 1
        elif int(key) == int(Qt.Key.Key_PageDown):
            row = min(count - 1, row + 10)
        elif int(key) == int(Qt.Key.Key_PageUp):
            row = max(0, row - 10)

        self._list.setFocus(Qt.FocusReason.OtherFocusReason)
        self._list.setCurrentRow(row)
        item = self._list.currentItem()
        if item is not None:
            self._update_current_strategy_accessibility(item)
        return True

    def _focus_first_strategy_row(self) -> None:
        if self._list.currentItem() is not None:
            return
        for row in range(self._list.count()):
            item = self._list.item(row)
            if item is None:
                continue
            self._list.setCurrentItem(item)
            return

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
        self._request_tree_rebuild(immediate=True)

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
        first_item = None

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

            accessible_text = _strategy_screen_reader_text(
                name=name,
                status_parts=accessible_status_parts,
                visual_label=visual_label,
                visual_description=visual_description,
            )
            item.setText(accessible_text)
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
                accessible_text,
            )
            tooltip_parts = [visual_description.strip(), args]
            item.setData(self._ROLE_TOOLTIP_TEXT, "\n\n".join(part for part in tooltip_parts if part))
            item.setSizeHint(QSize(0, 31))
            if is_current:
                current_item = item
            if first_item is None:
                first_item = item
            self._item_by_strategy_id[strategy_id] = item
            self._list.addItem(item)
            visible += 1

        summary_text = f"{visible} из {len(self._entries)}"
        _set_widget_text_if_changed(self._summary, summary_text)
        set_state_text(self._summary, f"Показано готовых стратегий: {summary_text}")
        focus_item = current_item or first_item
        if focus_item is not None:
            self._list.setCurrentItem(focus_item)
        self._update_current_strategy_accessibility(self._list.currentItem())

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
            try:
                if str(item.text() or "") != accessible_text:
                    item.setText(accessible_text)
                    changed = True
            except Exception:
                pass
        if changed:
            self._list.viewport().update(self._list.visualItemRect(item))
            if self._list.currentItem() is item:
                self._update_current_strategy_accessibility(item)

    def _update_current_strategy_accessibility(self, item=None, _previous=None) -> None:
        accessible_text = ""
        if item is not None:
            accessible_text = str(item.data(Qt.ItemDataRole.AccessibleTextRole) or "").strip()
        if accessible_text:
            set_state_text(self._list, f"Готовая стратегия: {accessible_text}")
        else:
            set_state_text(self._list, self._empty_strategy_list_state_text())

    def _empty_strategy_list_state_text(self) -> str:
        search_text = ""
        try:
            search_text = str(self._search.text() or "").strip()
        except Exception:
            search_text = ""
        if search_text:
            return "Список готовых стратегий: по фильтру ничего не найдено"
        if not self._entries:
            return "Список готовых стратегий: список пуст"
        return "Список готовых стратегий"

    def _apply_filter(self) -> None:
        self._request_tree_rebuild()

    def _request_tree_rebuild(self, *, immediate: bool = False) -> None:
        runtime = self.__dict__.get("_strategy_filter_runtime")
        if runtime is None:
            self._rebuild_tree()
            return
        search = ""
        try:
            search = self._search.text().strip().lower()
        except Exception:
            search = ""
        self._strategy_filter_state_obj().pending = (
            dict(self._entries),
            dict(self._states),
            str(self._current_strategy_id or "none").strip() or "none",
            search,
        )
        if immediate:
            try:
                self._strategy_filter_timer.stop()
            except Exception:
                pass
            self._run_debounced_tree_rebuild()
            return
        try:
            self._strategy_filter_timer.start(120)
        except Exception:
            self._run_debounced_tree_rebuild()

    def _run_debounced_tree_rebuild(self) -> None:
        state = self._strategy_filter_state_obj()
        pending = state.pending
        if pending is None:
            return
        if state.is_busy():
            return
        state.pending = None
        entries, states, current_strategy_id, search_text = pending
        self._start_strategy_filter_worker(entries, states, current_strategy_id, search_text)

    def _start_strategy_filter_worker(self, entries, states, current_strategy_id: str, search_text: str) -> None:
        self._strategy_filter_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self.create_strategy_filter_worker(
                request_id,
                entries=entries,
                states=states,
                current_strategy_id=current_strategy_id,
                search_text=search_text,
            ),
            on_loaded=self._on_strategy_filter_loaded,
            on_failed=self._on_strategy_filter_failed,
            on_finished=self._on_strategy_filter_worker_finished,
        )

    def create_strategy_filter_worker(
        self,
        request_id: int,
        *,
        entries,
        states,
        current_strategy_id: str,
        search_text: str,
    ) -> ProfileStrategyListFilterWorker:
        return ProfileStrategyListFilterWorker(
            request_id,
            entries=entries,
            states=states,
            current_strategy_id=current_strategy_id,
            search_text=search_text,
            parent=self,
        )

    def _on_strategy_filter_loaded(self, request_id: int, plan: ProfileStrategyListPlan) -> None:
        runtime = self.__dict__.get("_strategy_filter_runtime")
        if runtime is None or not runtime.is_current(request_id):
            return
        if self._strategy_filter_state_obj().has_pending():
            return
        if str(getattr(plan, "current_strategy_id", "") or "") != str(self._current_strategy_id or ""):
            self._request_tree_rebuild()
            return
        self._apply_strategy_list_plan(plan)

    def _on_strategy_filter_failed(self, request_id: int, error: str) -> None:
        runtime = self.__dict__.get("_strategy_filter_runtime")
        if runtime is None or not runtime.is_current(request_id):
            return
        if self._strategy_filter_state_obj().has_pending():
            return
        log(f"Ошибка подготовки списка готовых стратегий profile: {error}", "DEBUG")

    def _on_strategy_filter_worker_finished(self, worker) -> None:
        self._strategy_filter_state_obj().schedule_pending_after_finish(
            worker,
            is_current_worker_finish=lambda _runtime, current_worker: self._is_current_strategy_filter_worker_finish(
                current_worker,
            ),
            single_shot=QTimer.singleShot,
            run_scheduled=self._run_scheduled_strategy_filter_worker_start,
            cleanup_in_progress=bool(getattr(self, "_cleanup_in_progress", False)),
        )

    def _schedule_strategy_filter_worker_start(self) -> None:
        self._strategy_filter_state_obj().schedule_start(
            QTimer.singleShot,
            self._run_scheduled_strategy_filter_worker_start,
            pending_when_already_scheduled=self._strategy_filter_state_obj().pending,
        )

    def _run_scheduled_strategy_filter_worker_start(self) -> None:
        pending = self._strategy_filter_state_obj().take_pending_for_scheduled_start()
        if pending is None:
            return
        entries, states, current_strategy_id, search_text = pending
        self._start_strategy_filter_worker(entries, states, current_strategy_id, search_text)

    def _is_current_strategy_filter_worker_finish(self, worker) -> bool:
        runtime = self.__dict__.get("_strategy_filter_runtime")
        if runtime is None:
            return False
        if getattr(runtime, "worker", None) is worker:
            return True
        request_id = getattr(worker, "_request_id", None)
        if request_id is None:
            return False
        return int(request_id) == int(getattr(runtime, "request_id", 0) or 0)

    def _strategy_filter_state_obj(self) -> LatestValueWorkerState:
        state = self.__dict__.get("_strategy_filter_state")
        runtime = self.__dict__.get("_strategy_filter_runtime")
        if state is None:
            pending = self.__dict__.pop("_strategy_filter_pending", None)
            start_scheduled = bool(self.__dict__.pop("_strategy_filter_start_scheduled", False))
            state = LatestValueWorkerState(
                runtime,
                empty_value=None,
                pending=pending,
                start_scheduled=start_scheduled,
            )
            self.__dict__["_strategy_filter_state"] = state
        elif getattr(state, "runtime", None) is None and runtime is not None:
            state.runtime = runtime
        return state

    def _apply_strategy_list_plan(self, plan: ProfileStrategyListPlan) -> None:
        self._item_by_strategy_id.clear()
        self._list.clear()
        current_item = None
        first_item = None

        for row in tuple(getattr(plan, "rows", ()) or ()):
            item = QListWidgetItem()
            item.setText(row.accessible_text or row.name)
            item.setData(self._ROLE_STRATEGY_ID, row.strategy_id)
            item.setData(self._ROLE_NAME_TEXT, row.name)
            item.setData(self._ROLE_STATUS_TEXT, row.status_text)
            item.setData(self._ROLE_IS_ACTIVE, row.is_current)
            item.setData(self._ROLE_VISUAL_ICON_NAME, row.visual_icon_name)
            item.setData(self._ROLE_VISUAL_COLOR, row.visual_color)
            item.setData(self._ROLE_VISUAL_LABEL_TEXT, row.visual_label)
            item.setData(self._ROLE_VISUAL_DESCRIPTION, row.visual_description)
            item.setData(Qt.ItemDataRole.AccessibleTextRole, row.accessible_text)
            item.setData(self._ROLE_TOOLTIP_TEXT, row.tooltip_text)
            item.setSizeHint(QSize(0, 31))
            if row.is_current:
                current_item = item
            if first_item is None:
                first_item = item
            self._item_by_strategy_id[row.strategy_id] = item
            self._list.addItem(item)

        summary_text = f"{int(getattr(plan, 'visible_count', 0) or 0)} из {int(getattr(plan, 'total_count', 0) or 0)}"
        _set_widget_text_if_changed(self._summary, summary_text)
        set_state_text(self._summary, f"Показано готовых стратегий: {summary_text}")
        focus_item = current_item or first_item
        if focus_item is not None:
            self._list.setCurrentItem(focus_item)
        self._update_current_strategy_accessibility(self._list.currentItem())

    def _cleanup_strategy_filter_worker(self, *_args) -> None:
        try:
            self._strategy_filter_timer.stop()
        except Exception:
            pass
        try:
            self._strategy_filter_state_obj().reset()
        except Exception:
            pass
        runtime = self.__dict__.get("_strategy_filter_runtime")
        if runtime is not None:
            runtime.stop(
                blocking=False,
                log_fn=log,
                warning_prefix="Profile strategy filter worker",
            )
            runtime.cancel()

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
    text = ", ".join(part for part in parts if part)
    return f"{text}. Нажмите Enter или Пробел, чтобы выбрать стратегию." if text else ""


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
    in_range = str(getattr(branch, "in_range", "") or "x").strip() or "x"
    out_range = str(getattr(branch, "out_range", "") or "a").strip() or "a"
    return replace(
        payload,
        current_strategy_branch_id=clean_branch_id,
        in_range=in_range,
        out_range=out_range,
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


def _strategy_branch_summary_name(branches) -> str:
    branch_items = tuple(branches or ())
    names = [
        str(getattr(branch, "strategy_name", "") or "").strip()
        for branch in branch_items
        if str(getattr(branch, "strategy_name", "") or "").strip()
    ]
    visible = names[:2]
    suffix = f" +{len(names) - len(visible)}" if len(names) > len(visible) else ""
    label = ", ".join(visible)
    if label:
        return f"{len(branch_items)} стратегии: {label}{suffix}"
    return f"{len(branch_items)} стратегии"


def _combo_item_accessible_text(
    *,
    name: str,
    label: str,
    selected: bool,
    selected_word: str = "выбран",
    unselected_word: str = "не выбран",
) -> str:
    state = selected_word if selected else unselected_word
    return f"{str(name or '').strip()}: {str(label or '').strip()}, {state}"


def _sync_combo_items_accessibility(
    combo,
    *,
    name: str,
    selected_word: str = "выбран",
    unselected_word: str = "не выбран",
) -> None:
    if combo is None:
        return
    try:
        current_index = int(combo.currentIndex())
        count = int(combo.count())
    except Exception:
        return
    set_item_accessible_text = getattr(combo, "setItemAccessibleText", None)
    if not callable(set_item_accessible_text):
        return
    for index in range(count):
        try:
            label = str(combo.itemText(index) or "").strip()
        except Exception:
            label = ""
        if not label:
            continue
        set_item_accessible_text(
            index,
            _combo_item_accessible_text(
                name=name,
                label=label,
                selected=index == current_index,
                selected_word=selected_word,
                unselected_word=unselected_word,
            ),
        )


def _strategy_branch_accessible_text(label: str, *, selected: bool) -> str:
    return _combo_item_accessible_text(
        name="Ветка готовой стратегии",
        label=label,
        selected=selected,
        selected_word="выбрана",
        unselected_word="не выбрана",
    )


def _sync_strategy_branch_combo_items_accessibility(combo) -> None:
    if combo is None:
        return
    try:
        current_index = int(combo.currentIndex())
        count = int(combo.count())
    except Exception:
        return
    set_item_accessible_text = getattr(combo, "setItemAccessibleText", None)
    if not callable(set_item_accessible_text):
        return
    for index in range(count):
        try:
            label = str(combo.itemText(index) or "").strip()
        except Exception:
            label = ""
        if not label:
            continue
        set_item_accessible_text(index, _strategy_branch_accessible_text(label, selected=index == current_index))


def _join_accessible_options(labels: list[str]) -> str:
    clean_labels = [str(label or "").strip() for label in labels if str(label or "").strip()]
    if not clean_labels:
        return ""
    if len(clean_labels) == 1:
        return clean_labels[0]
    return f"{', '.join(clean_labels[:-1])} или {clean_labels[-1]}"


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
