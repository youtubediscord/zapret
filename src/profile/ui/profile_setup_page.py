from __future__ import annotations

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
from profile.winws2_editable_settings import normalize_winws2_filter_value
from profile.ui.profile_setup_controls import (
    range_expression_from_controls,
    set_combo_by_data,
    set_range_controls,
    sync_range_value_enabled,
)
from profile.setup_controller import ProfileSetupController
from profile.strategy_visuals import describe_strategy_visual
from qfluentwidgets import (
    BodyLabel,
    BreadcrumbBar,
    CheckBox,
    ComboBox,
    LineEdit,
    PlainTextEdit,
    SearchLineEdit,
    SegmentedWidget,
    PushButton,
)
from settings.mode import ZAPRET1_MODE, ZAPRET2_MODE, is_zapret2_launch_method
from ui.pages.base_page import BasePage
from ui.fluent_widgets import set_tooltip
from app.text_catalog import tr as tr_catalog
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
        self._entries = dict(entries or {})
        self._states = dict(states or {})
        self._current_strategy_id = str(current_strategy_id or "none").strip() or "none"
        self._rebuild_tree()

    def _rebuild_tree(self) -> None:
        search_text = self._search.text().strip().lower()
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
            self._list.addItem(item)
            visible += 1

        self._summary.setText(f"{visible} из {len(self._entries)}")
        if current_item is not None:
            self._list.setCurrentItem(current_item)
            current_item.setSelected(True)

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
        ("Что записано в profile", str(getattr(payload, "raw_profile_text", "") or "").strip() or "Profile пустой"),
    ]

    lines: list[str] = []
    for title, text in blocks:
        lines.append(title)
        lines.append("=" * len(title))
        lines.append(text)
        lines.append("")
    return "\n".join(lines).strip()


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
        self._payload = None
        self._settings_container = None
        self._work_button = None
        self._notwork_button = None
        self._favorite_button = None
        self._clear_feedback_button = None
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
        self._strategy_tabs.addItem("strategies", "Готовые стратегии", lambda: self._strategy_stack.setCurrentIndex(0))
        self._strategy_tabs.addItem("match", "Когда применяется", lambda: self._strategy_stack.setCurrentIndex(1))
        self._strategy_tabs.setCurrentItem("strategies")
        set_tooltip(
            self._strategy_tabs,
            "Готовые стратегии меняют строки --lua-desync. Вкладка «Когда применяется» показывает условия profile и итоговый текст.",
        )
        self.layout.addWidget(self._strategy_tabs)

        self._strategy_list = ProfileStrategyListWidget(self)
        self._strategy_list.strategy_activated.connect(self._on_strategy_list_activated)
        self._strategy_stack.addWidget(self._strategy_list)

        match_tab = QWidget(self)
        match_layout = QVBoxLayout(match_tab)
        match_layout.setContentsMargins(0, 0, 0, 0)
        match_layout.setSpacing(10)
        self._match_text = PlainTextEdit()
        self._match_text.setReadOnly(True)
        self._match_text.setMinimumHeight(520)
        set_tooltip(
            self._match_text,
            "Подробности текущего profile: условия применения, выбранная готовая стратегия и строки, которые будут записаны в preset.",
        )
        match_layout.addWidget(self._match_text)

        feedback_actions = QWidget(match_tab)
        feedback_actions_layout = QHBoxLayout(feedback_actions)
        feedback_actions_layout.setContentsMargins(0, 0, 0, 0)
        feedback_actions_layout.setSpacing(12)

        self._work_button = PushButton("Работает")
        set_tooltip(
            self._work_button,
            "Пометить текущую готовую стратегию как рабочую для этого profile.",
        )
        self._work_button.clicked.connect(lambda: self._set_current_strategy_feedback(rating="work"))
        feedback_actions_layout.addWidget(self._work_button)

        self._notwork_button = PushButton("Не работает")
        set_tooltip(
            self._notwork_button,
            "Пометить текущую готовую стратегию как нерабочую для этого profile.",
        )
        self._notwork_button.clicked.connect(lambda: self._set_current_strategy_feedback(rating="notwork"))
        feedback_actions_layout.addWidget(self._notwork_button)

        self._favorite_button = PushButton("В избранное")
        set_tooltip(
            self._favorite_button,
            "Добавить текущую готовую стратегию в избранное или убрать её оттуда.",
        )
        self._favorite_button.clicked.connect(self._toggle_current_strategy_favorite)
        feedback_actions_layout.addWidget(self._favorite_button)

        self._clear_feedback_button = PushButton("Убрать оценку")
        set_tooltip(
            self._clear_feedback_button,
            "Очистить вашу оценку для текущей готовой стратегии.",
        )
        self._clear_feedback_button.clicked.connect(lambda: self._set_current_strategy_feedback(rating=""))
        feedback_actions_layout.addWidget(self._clear_feedback_button)
        feedback_actions_layout.addStretch(1)
        match_layout.addWidget(feedback_actions)

        self._strategy_stack.addWidget(match_tab)

        self.layout.addWidget(self._strategy_stack, 1)

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

    def show_profile(self, profile_key: str) -> None:
        self._profile_key = str(profile_key or "").strip()
        self.reload_current_profile()

    def handle_page_command(self, command: str, payload: dict) -> bool:
        if command == "open_profile":
            self.show_profile(str((payload or {}).get("profile_key") or ""))
            return True
        return False

    def reload_current_profile(self) -> None:
        if not self._profile_key:
            return
        try:
            payload = self._controller.load(self._profile_key)
        except Exception as exc:
            log(f"{self.__class__.__name__}: не удалось прочитать профиль {self._profile_key}: {exc}", "ERROR")
            payload = None
        if payload is None:
            self._summary.setText("Профиль не найден. Вернитесь к списку и нажмите «Обновить».")
            self._enabled_checkbox.setEnabled(False)
            return
        self._payload = payload
        self._apply_payload(payload)

    def _apply_payload(self, payload) -> None:
        self._loading = True
        try:
            item = payload.item
            self._summary.setText(payload.match_summary)
            self._enabled_checkbox.setChecked(bool(item.enabled))
            self._enabled_checkbox.setEnabled(True)
            self._apply_editable_settings(payload)

            self._match_text.setPlainText(_match_tab_text(payload))
            self._strategy_list.set_rows(
                entries=payload.strategy_entries,
                states=payload.strategy_states,
                current_strategy_id=item.strategy_id or "none",
            )
            self._apply_feedback_buttons(payload)
            self._rebuild_breadcrumb()
        finally:
            self._loading = False

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
        is_winws2 = is_zapret2_launch_method(self.launch_method)
        if self._settings_container is not None:
            self._settings_container.setVisible(is_winws2)
        if not is_winws2:
            return

        filter_enabled = bool(getattr(payload, "editable_filter_enabled", True))
        self._filter_combo.setVisible(filter_enabled)
        self._filter_value.setVisible(filter_enabled)
        set_combo_by_data(self._filter_combo, getattr(payload, "editable_filter_kind", "") or "hostlist")
        self._filter_value.setText(str(getattr(payload, "editable_filter_value", "") or ""))
        set_range_controls(self._in_range_mode, self._in_range_value, getattr(payload, "in_range", "") or "x")
        set_range_controls(self._out_range_mode, self._out_range_value, getattr(payload, "out_range", "") or "a")
        self._update_all_range_tooltips()

    def _on_range_mode_changed(self, combo: ComboBox, value_edit: LineEdit) -> None:
        sync_range_value_enabled(combo, value_edit)
        if combo is self._in_range_mode:
            self._update_range_tooltips(combo, value_edit, option_name="--in-range", direction="входящих")
        elif combo is self._out_range_mode:
            self._update_range_tooltips(combo, value_edit, option_name="--out-range", direction="исходящих")
        self._schedule_settings_autosave()

    def _on_filter_kind_changed(self) -> None:
        self._sync_filter_value_for_kind()
        self._schedule_settings_autosave()

    def _sync_filter_value_for_kind(self) -> None:
        if self._loading or not is_zapret2_launch_method(self.launch_method):
            return
        filter_kind = str(self._filter_combo.itemData(self._filter_combo.currentIndex()) or "hostlist")
        normalized = normalize_winws2_filter_value(self._filter_value.text(), filter_kind)
        if normalized and normalized != self._filter_value.text().strip():
            self._filter_value.setText(normalized)

    def _schedule_settings_autosave(self) -> None:
        if self._loading or not self._profile_key or not is_zapret2_launch_method(self.launch_method):
            return
        self._settings_save_timer.start()

    def _autosave_editable_settings(self) -> None:
        if self._loading or not self._profile_key or not is_zapret2_launch_method(self.launch_method):
            return
        filter_value = self._filter_value.text().strip()
        filter_enabled = bool(getattr(self._payload, "editable_filter_enabled", True))
        if filter_enabled and not filter_value:
            return
        try:
            new_key = self._controller.save_winws2_settings(
                profile_key=self._profile_key,
                filter_kind=str(self._filter_combo.itemData(self._filter_combo.currentIndex()) or "hostlist"),
                filter_value=filter_value,
                in_range=range_expression_from_controls(self._in_range_mode, self._in_range_value, default="x"),
                out_range=range_expression_from_controls(self._out_range_mode, self._out_range_value, default="a"),
            )
            if new_key:
                self._profile_key = new_key
            self.reload_current_profile()
            self._on_profile_changed_callback(self._profile_key, "settings")
        except Exception as exc:
            log(f"{self.__class__.__name__}: не удалось сохранить настройки профиля: {exc}", "ERROR")

    def _on_enabled_changed(self, state: int) -> None:
        if self._loading or not self._profile_key:
            return
        enabled = bool(state == Qt.CheckState.Checked.value or state == 2)
        try:
            new_key = self._controller.set_enabled(
                profile_key=self._profile_key,
                enabled=enabled,
            )
            if new_key:
                self._profile_key = new_key
            self.reload_current_profile()
            self._on_profile_changed_callback(self._profile_key, "enabled" if enabled else "disabled")
        except Exception as exc:
            log(f"{self.__class__.__name__}: не удалось изменить состояние профиля: {exc}", "ERROR")

    def _on_strategy_list_activated(self, strategy_id: str) -> None:
        if self._loading or not self._profile_key:
            return
        strategy_id = str(strategy_id or "").strip()
        if not strategy_id or strategy_id in {"none", "custom"}:
            return
        try:
            new_key = self._controller.apply_strategy(
                profile_key=self._profile_key,
                strategy_id=strategy_id,
            )
            if new_key:
                self._profile_key = new_key
            self.reload_current_profile()
            self._on_profile_changed_callback(self._profile_key, "strategy")
        except Exception as exc:
            log(f"{self.__class__.__name__}: не удалось применить стратегию: {exc}", "ERROR")

    def _set_current_strategy_feedback(self, *, rating: str) -> None:
        if self._loading or not self._profile_key:
            return
        try:
            self._controller.set_strategy_feedback(
                profile_key=self._profile_key,
                rating=rating,
            )
            self.reload_current_profile()
            self._on_profile_changed_callback(self._profile_key, "feedback")
        except Exception as exc:
            log(f"{self.__class__.__name__}: не удалось обновить оценку стратегии: {exc}", "ERROR")

    def _toggle_current_strategy_favorite(self) -> None:
        if self._loading or not self._profile_key or self._payload is None:
            return
        try:
            current = bool(self._payload.current_strategy_state.favorite)
            self._controller.set_strategy_feedback(
                profile_key=self._profile_key,
                favorite=not current,
            )
            self.reload_current_profile()
            self._on_profile_changed_callback(self._profile_key, "feedback")
        except Exception as exc:
            log(f"{self.__class__.__name__}: не удалось обновить избранную стратегию: {exc}", "ERROR")


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
