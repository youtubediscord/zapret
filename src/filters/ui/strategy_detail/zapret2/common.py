from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QFontMetrics
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from log.log import log

from filters.advanced import TCP_EMBEDDED_FAKE_TECHNIQUES, TCP_PHASE_COMMAND_ORDER, TCP_PHASE_TAB_ORDER
from ui.text_catalog import tr as tr_catalog
from ui.theme import get_themed_qta_icon


def tr_text(language: str, key: str, default: str, **kwargs) -> str:
    text = tr_catalog(key, language=language, default=default)
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text


def log_z2_detail_metric(section: str, elapsed_ms: float, *, extra: str | None = None) -> None:
    try:
        rounded = int(round(float(elapsed_ms)))
    except Exception:
        rounded = 0
    suffix = f" ({extra})" if extra else ""
    log(f"⏱ Startup UI Section: ZAPRET2_DETAIL_FLOW {section} {rounded}ms{suffix}", "⏱ STARTUP")


def prepare_compact_setting_group(group) -> None:
    """Скрывает заголовок fluent-group, чтобы она работала как чистый settings-container."""
    try:
        title_label = getattr(group, "titleLabel", None)
        if title_label is not None:
            title_label.hide()
    except Exception:
        pass

    try:
        layout = getattr(group, "vBoxLayout", None)
        if layout is None:
            return
        spacer_item = layout.itemAt(1)
        if spacer_item is not None and spacer_item.spacerItem() is not None:
            spacer_item.spacerItem().changeSize(0, 0)
        layout.invalidate()
    except Exception:
        pass


def coerce_global_pos_to_qpoint(global_pos):
    try:
        return global_pos.toPoint()
    except Exception:
        return global_pos


def ensure_preview_dialog(
    existing_dialog,
    *,
    parent_win,
    on_closed,
    dialog_cls,
):
    dialog = existing_dialog
    if dialog is not None:
        try:
            dialog.isVisible()
            return dialog
        except RuntimeError:
            dialog = None
        except Exception:
            return dialog

    try:
        dialog = dialog_cls(parent_win)
        dialog.closed.connect(on_closed)
        return dialog
    except Exception:
        return None


def show_strategy_preview_dialog(
    dialog,
    *,
    strategy_data: dict,
    strategy_id: str,
    target_key: str,
    global_pos,
    rating_getter,
    rating_toggler,
    log_fn=log,
) -> None:
    try:
        dialog.set_strategy_data(
            strategy_data,
            strategy_id=strategy_id,
            target_key=target_key,
            rating_getter=rating_getter,
            rating_toggler=rating_toggler,
        )
        dialog.show_animated(coerce_global_pos_to_qpoint(global_pos))
    except Exception as exc:
        log_fn(f"Preview dialog failed: {exc}", "DEBUG")

STRATEGY_TECHNIQUE_FILTERS: list[tuple[str, str]] = [
    ("FAKE", "fake"),
    ("SPLIT", "split"),
    ("MULTISPLIT", "multisplit"),
    ("DISORDER", "disorder"),
    ("OOB", "oob"),
    ("SYNDATA", "syndata"),
]


@dataclass(slots=True)
class StrategyHeaderWidgets:
    header_widget: QWidget
    title_label: object
    summary_label: object


@dataclass(slots=True)
class StrategyBlockShellWidgets:
    block_widget: QWidget
    card_widget: object


@dataclass(slots=True)
class StrategyToolbarWidgets:
    toolbar_widget: QWidget
    search_input: object
    filter_combo: object
    sort_combo: object
    edit_args_btn: object


@dataclass(slots=True)
class TcpPhaseBarWidgets:
    container_widget: QWidget
    tabbar: object
    index_by_key: dict[str, int]
    key_by_index: dict[int, str]


@dataclass(slots=True)
class SelectedStrategyHeaderState:
    visible: bool
    text: str
    tooltip: str


class ElidedLabel(QLabel):
    """QLabel, который автоматически обрезает текст с троеточием по ширине."""

    def __init__(self, text: str = "", parent=None):
        super().__init__("", parent)
        self._full_text = text or ""
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        super().setText("")
        self.set_full_text(self._full_text)

    def set_full_text(self, text: str) -> None:
        self._full_text = text or ""
        self.update()

    def full_text(self) -> str:
        return self._full_text

    def paintEvent(self, event):  # noqa: N802
        super().paintEvent(event)
        text = self._full_text or ""
        if not text:
            return

        try:
            rect = self.contentsRect()
            width = max(0, int(rect.width()))
            if width <= 0:
                return

            metrics = QFontMetrics(self.font())
            elided = metrics.elidedText(text, Qt.TextElideMode.ElideRight, width)

            from PyQt6.QtGui import QPainter

            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
            painter.setFont(self.font())
            painter.setPen(self.palette().color(self.foregroundRole()))
            align = self.alignment() or (Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            painter.drawText(rect, int(align), elided)
        except Exception:
            return


def build_strategy_block_shell(*, settings_card_cls) -> StrategyBlockShellWidgets:
    block_widget = QWidget()
    block_widget.setObjectName("targetStrategiesBlock")
    block_widget.setProperty("targetDisabled", False)
    block_widget.setVisible(False)

    host_layout = QVBoxLayout(block_widget)
    host_layout.setContentsMargins(0, 0, 0, 0)
    host_layout.setSpacing(0)

    card_widget = settings_card_cls()
    card_widget.setObjectName("targetStrategiesCard")
    host_layout.addWidget(card_widget, 1)

    return StrategyBlockShellWidgets(
        block_widget=block_widget,
        card_widget=card_widget,
    )


def build_strategy_header_widgets(
    *,
    title_text: str,
    strong_label_cls,
    caption_label_cls,
) -> StrategyHeaderWidgets:
    header_widget = QWidget()
    header_row = QHBoxLayout(header_widget)
    header_row.setContentsMargins(0, 0, 0, 0)
    header_row.setSpacing(12)

    header_text_layout = QVBoxLayout()
    header_text_layout.setContentsMargins(0, 0, 0, 0)
    header_text_layout.setSpacing(2)

    title_label = strong_label_cls(title_text)
    header_text_layout.addWidget(title_label)

    summary_label = caption_label_cls("")
    try:
        summary_label.setWordWrap(True)
    except Exception:
        pass
    header_text_layout.addWidget(summary_label)

    header_row.addLayout(header_text_layout, 1)

    return StrategyHeaderWidgets(
        header_widget=header_widget,
        title_label=title_label,
        summary_label=summary_label,
    )


def build_strategy_toolbar_widgets(
    *,
    parent,
    tr,
    tokens,
    search_line_edit_cls,
    combo_cls,
    transparent_tool_button_cls,
    set_tooltip,
    build_filter_combo_fn,
    technique_filters: list[tuple[str, str]] | None,
    on_search_changed,
    on_filter_changed,
    on_sort_changed,
    on_edit_args_clicked,
):
    toolbar_widget = QWidget()
    search_layout = QHBoxLayout(toolbar_widget)
    search_layout.setContentsMargins(0, 0, 0, 0)
    search_layout.setSpacing(8)

    search_input = search_line_edit_cls()
    search_input.setPlaceholderText(
        tr("page.z2_strategy_detail.search.placeholder", "Поиск по имени или args...")
    )
    search_input.setFixedHeight(36)
    search_input.textChanged.connect(on_search_changed)
    search_layout.addWidget(search_input)

    filter_combo = combo_cls(parent=parent)
    filter_combo.setFixedHeight(36)
    filter_combo.setMinimumWidth(154)
    build_filter_combo_fn(filter_combo, tr, technique_filters=technique_filters)
    filter_combo.currentIndexChanged.connect(on_filter_changed)
    search_layout.addWidget(filter_combo)

    sort_combo = combo_cls(parent=parent)
    sort_combo.setFixedHeight(36)
    sort_combo.setMinimumWidth(168)
    sort_combo.currentIndexChanged.connect(on_sort_changed)
    search_layout.addWidget(sort_combo)

    try:
        from qfluentwidgets import FluentIcon as _FIF

        edit_args_btn = transparent_tool_button_cls(_FIF.EDIT, parent=parent)
    except Exception:
        edit_args_btn = transparent_tool_button_cls(parent=parent)
        edit_args_btn.setIcon(get_themed_qta_icon("fa5s.edit", color=tokens.fg_faint))

    edit_args_btn.setIconSize(QSize(16, 16))
    edit_args_btn.setFixedSize(36, 36)
    edit_args_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    set_tooltip(
        edit_args_btn,
        tr(
            "page.z2_strategy_detail.args.tooltip",
            "Аргументы стратегии для выбранного target'а",
        ),
    )
    edit_args_btn.setEnabled(False)
    edit_args_btn.clicked.connect(on_edit_args_clicked)
    search_layout.addWidget(edit_args_btn)

    return StrategyToolbarWidgets(
        toolbar_widget=toolbar_widget,
        search_input=search_input,
        filter_combo=filter_combo,
        sort_combo=sort_combo,
        edit_args_btn=edit_args_btn,
    )


def build_strategy_filter_combo(combo, tr, *, technique_filters: list[tuple[str, str]] | None = None) -> None:
    filters = technique_filters or STRATEGY_TECHNIQUE_FILTERS
    combo.addItem(tr("page.z2_strategy_detail.filter.technique.all", "Все техники"))
    for label, _key in filters:
        combo.addItem(label)
    combo.setCurrentIndex(0)


def refresh_strategy_filter_combo(
    combo,
    tr,
    *,
    current_index: int,
    technique_filters: list[tuple[str, str]] | None = None,
) -> None:
    filters = technique_filters or STRATEGY_TECHNIQUE_FILTERS
    combo.blockSignals(True)
    combo.clear()
    combo.addItem(tr("page.z2_strategy_detail.filter.technique.all", "Все техники"))
    for label, _key in filters:
        combo.addItem(label)
    combo.setCurrentIndex(max(0, current_index))
    combo.blockSignals(False)


def build_tcp_phase_tabs(tabbar, on_click, *, phase_tabs: list[tuple[str, str]] | None = None) -> tuple[dict[str, int], dict[int, str]]:
    tabs = phase_tabs or TCP_PHASE_TAB_ORDER
    index_by_key: dict[str, int] = {}
    key_by_index: dict[int, str] = {}
    for i, (phase_key, label) in enumerate(tabs):
        key = str(phase_key or "").strip().lower()
        index_by_key[key] = i
        key_by_index[i] = key
        try:
            tabbar.addItem(
                key,
                label,
                onClick=lambda k=key: on_click(k),
            )
        except Exception:
            pass
    return index_by_key, key_by_index


def build_tcp_phase_bar_widgets(
    *,
    parent,
    segmented_widget_cls,
    on_click,
    on_changed,
    phase_tabs: list[tuple[str, str]] | None = None,
) -> TcpPhaseBarWidgets:
    container_widget = QWidget()
    container_widget.setVisible(False)
    try:
        container_widget.setProperty("noDrag", True)
    except Exception:
        pass

    phases_layout = QHBoxLayout(container_widget)
    phases_layout.setContentsMargins(0, 0, 0, 8)
    phases_layout.setSpacing(0)

    tabbar = segmented_widget_cls(parent)
    try:
        tabbar.setProperty("noDrag", True)
    except Exception:
        pass

    index_by_key, key_by_index = build_tcp_phase_tabs(
        tabbar,
        on_click,
        phase_tabs=phase_tabs,
    )

    try:
        tabbar.currentItemChanged.connect(on_changed)
    except Exception:
        pass

    phases_layout.addWidget(tabbar, 1)
    return TcpPhaseBarWidgets(
        container_widget=container_widget,
        tabbar=tabbar,
        index_by_key=index_by_key,
        key_by_index=key_by_index,
    )


def build_selected_strategy_header_state(
    *,
    strategy_id: str,
    tcp_phase_mode: bool,
    tcp_hide_fake_phase: bool,
    tcp_phase_selected_ids: dict[str, str] | None,
    strategies_data_by_id: dict[str, dict] | None,
    custom_strategy_id: str,
    fake_disabled_strategy_id: str,
    phase_command_order: list[str] | None = None,
) -> SelectedStrategyHeaderState:
    sid = str(strategy_id or "none").strip()

    if tcp_phase_mode:
        if sid == "none":
            return SelectedStrategyHeaderState(visible=False, text="", tooltip="")

        parts: list[str] = []
        for phase in (phase_command_order or TCP_PHASE_COMMAND_ORDER):
            if phase == "fake" and tcp_hide_fake_phase:
                continue
            psid = str((tcp_phase_selected_ids or {}).get(phase) or "").strip()
            if not psid:
                continue
            if phase == "fake" and psid == fake_disabled_strategy_id:
                continue

            if psid == custom_strategy_id:
                name = custom_strategy_id
            else:
                try:
                    data = dict((strategies_data_by_id or {}).get(psid, {}) or {})
                except Exception:
                    data = {}
                name = str(data.get("name") or psid).strip() or psid
            parts.append(f"{phase}={name}")

        text = "; ".join(parts).strip()
        if not text:
            return SelectedStrategyHeaderState(visible=False, text="", tooltip="")
        return SelectedStrategyHeaderState(visible=True, text=text, tooltip=text)

    if sid == "none":
        return SelectedStrategyHeaderState(visible=False, text="", tooltip="")

    try:
        data = dict((strategies_data_by_id or {}).get(sid, {}) or {})
    except Exception:
        data = {}
    name = str(data.get("name") or sid).strip() or sid
    return SelectedStrategyHeaderState(
        visible=True,
        text=name,
        tooltip=f"{name}\nID: {sid}",
    )
