# ui/pages/zapret2/strategy_detail_page.py
"""
Страница детального просмотра стратегий для выбранной категории.
Открывается при клике на категорию в Zapret2StrategiesPageNew.
"""

import re
import json

from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer, QEvent
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QWidget,
    QFrame, QMenu,
    QSizePolicy, QGraphicsOpacityEffect
)
from PyQt6.QtGui import QFont, QFontMetrics, QColor
import qtawesome as qta

try:
    from qfluentwidgets import (
        BodyLabel, CaptionLabel, StrongBodyLabel, SubtitleLabel,
        ComboBox, CheckBox, SpinBox, LineEdit, TextEdit, HorizontalSeparator,
        ToolButton, TransparentToolButton, SwitchButton, SegmentedWidget, TogglePushButton,
        PixmapLabel,
        TitleLabel, TransparentPushButton, IndeterminateProgressRing, RoundMenu, Action,
        MessageBoxBase, InfoBar, FluentIcon,
    )
    _HAS_FLUENT = True
except ImportError:
    from PyQt6.QtWidgets import (
        QComboBox as ComboBox, QCheckBox as CheckBox, QSpinBox as SpinBox,
        QLineEdit as LineEdit, QTextEdit as TextEdit, QFrame as HorizontalSeparator, QPushButton,
        QDialog as MessageBoxBase,
    )
    BodyLabel = QLabel
    CaptionLabel = QLabel
    StrongBodyLabel = QLabel
    SubtitleLabel = QLabel
    TitleLabel = QLabel
    ToolButton = QPushButton
    TransparentToolButton = QPushButton
    SwitchButton = QPushButton
    TransparentPushButton = QPushButton
    SegmentedWidget = QWidget
    TogglePushButton = QPushButton
    TextEdit = QWidget
    PixmapLabel = QLabel
    IndeterminateProgressRing = QWidget
    RoundMenu = QMenu
    Action = lambda *a, **kw: None
    InfoBar = None
    FluentIcon = None
    _HAS_FLUENT = False

from ui.pages.base_page import BasePage
from ui.compat_widgets import ActionButton, PrimaryActionButton, SettingsRow, set_tooltip, SettingsCard
from ui.pages.dpi_settings_page import Win11ToggleRow, Win11ComboRow, Win11NumberRow
from ui.pages.strategies_page_base import ResetActionButton
from ui.widgets.direct_zapret2_strategies_tree import DirectZapret2StrategiesTree, StrategyTreeRow
from strategy_menu.args_preview_dialog import ArgsPreviewDialog
from launcher_common.blobs import get_blobs_info
from preset_zapret2 import PresetManager, SyndataSettings
from ui.zapret2_strategy_marks import DirectZapret2MarksStore, DirectZapret2FavoritesStore
from ui.theme import get_theme_tokens
from ui.text_catalog import tr as tr_catalog
from log import log


def _tr_text(language: str, key: str, default: str, **kwargs) -> str:
    text = tr_catalog(key, language=language, default=default)
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text


# ─────────────────────────────────────────────────────────────────────────────
# ДИАЛОГ РЕДАКТИРОВАНИЯ АРГУМЕНТОВ (MessageBoxBase)
# ─────────────────────────────────────────────────────────────────────────────

class _ArgsEditorDialog(MessageBoxBase):
    """Диалог редактирования аргументов стратегии на базе MessageBoxBase."""

    def __init__(self, initial_text: str = "", parent=None, language: str = "ru"):
        super().__init__(parent)
        self._ui_language = language
        if _HAS_FLUENT:
            from qfluentwidgets import SubtitleLabel as _SubLabel
            self._title_lbl = _SubLabel(
                _tr_text(self._ui_language, "page.z2_strategy_detail.args_dialog.title", "Аргументы стратегии")
            )
        else:
            self._title_lbl = QLabel(
                _tr_text(self._ui_language, "page.z2_strategy_detail.args_dialog.title", "Аргументы стратегии")
            )
        self.viewLayout.addWidget(self._title_lbl)

        if _HAS_FLUENT:
            from qfluentwidgets import CaptionLabel as _Cap
            hint = _Cap(
                _tr_text(
                    self._ui_language,
                    "page.z2_strategy_detail.args_dialog.hint",
                    "Один аргумент на строку. Изменяет только выбранную категорию.",
                )
            )
        else:
            hint = QLabel(
                _tr_text(self._ui_language, "page.z2_strategy_detail.args_dialog.hint.short", "Один аргумент на строку.")
            )
        self.viewLayout.addWidget(hint)

        self._text_edit = TextEdit()
        try:
            from config.reg import get_smooth_scroll_enabled
            from qfluentwidgets.common.smooth_scroll import SmoothMode

            smooth_enabled = get_smooth_scroll_enabled()
            mode = SmoothMode.COSINE if smooth_enabled else SmoothMode.NO_SMOOTH
            delegate = (
                getattr(self._text_edit, "scrollDelegate", None)
                or getattr(self._text_edit, "scrollDelagate", None)
                or getattr(self._text_edit, "delegate", None)
            )
            if delegate is not None:
                if hasattr(delegate, "useAni"):
                    if not hasattr(delegate, "_zapret_base_use_ani"):
                        delegate._zapret_base_use_ani = bool(delegate.useAni)
                    delegate.useAni = bool(delegate._zapret_base_use_ani) if smooth_enabled else False
                for smooth_attr in ("verticalSmoothScroll", "horizonSmoothScroll"):
                    smooth = getattr(delegate, smooth_attr, None)
                    smooth_setter = getattr(smooth, "setSmoothMode", None)
                    if callable(smooth_setter):
                        smooth_setter(mode)

            setter = getattr(self._text_edit, "setSmoothMode", None)
            if callable(setter):
                try:
                    setter(mode, Qt.Orientation.Vertical)
                except TypeError:
                    setter(mode)
        except Exception:
            pass
        self._text_edit.setPlaceholderText(
            _tr_text(
                self._ui_language,
                "page.z2_strategy_detail.args_dialog.placeholder",
                "Например:\n--dpi-desync=multisplit\n--dpi-desync-split-pos=1",
            )
        )
        self._text_edit.setMinimumWidth(420)
        self._text_edit.setMinimumHeight(120)
        self._text_edit.setMaximumHeight(220)
        if _HAS_FLUENT:
            from PyQt6.QtGui import QFont
            self._text_edit.setFont(QFont("Consolas", 10))
        self._text_edit.setText(initial_text)
        self.viewLayout.addWidget(self._text_edit)

        self.yesButton.setText(
            _tr_text(self._ui_language, "page.z2_strategy_detail.args_dialog.button.save", "Сохранить")
        )
        self.cancelButton.setText(
            _tr_text(self._ui_language, "page.z2_strategy_detail.args_dialog.button.cancel", "Отмена")
        )

    def validate(self) -> bool:
        return True

    def get_text(self) -> str:
        return self._text_edit.toPlainText()


TCP_PHASE_TAB_ORDER: list[tuple[str, str]] = [
    ("fake", "FAKE"),
    ("multisplit", "MULTISPLIT"),
    ("multidisorder", "MULTIDISORDER"),
    ("multidisorder_legacy", "LEGACY"),
    ("tcpseg", "TCPSEG"),
    ("oob", "OOB"),
    ("other", "OTHER"),
]

TCP_PHASE_COMMAND_ORDER: list[str] = [
    "fake",
    "multisplit",
    "multidisorder",
    "multidisorder_legacy",
    "tcpseg",
    "oob",
    "other",
]

TCP_EMBEDDED_FAKE_TECHNIQUES: set[str] = {
    "fakedsplit",
    "fakeddisorder",
    "hostfakesplit",
}


STRATEGY_TECHNIQUE_FILTERS: list[tuple[str, str]] = [
    ("FAKE", "fake"),
    ("SPLIT", "split"),
    ("MULTISPLIT", "multisplit"),
    ("DISORDER", "disorder"),
    ("OOB", "oob"),
    ("SYNDATA", "syndata"),
]

TCP_FAKE_DISABLED_STRATEGY_ID = "__phase_fake_disabled__"
CUSTOM_STRATEGY_ID = "custom"


def _extract_desync_technique_from_arg(line: str) -> str | None:
    """
    Extracts desync function name from a single arg line.

    Examples:
      --lua-desync=fake:blob=tls_google -> "fake"
      --lua-desync=pass -> "pass"
      --dpi-desync=multisplit -> "multisplit"
    """
    s = (line or "").strip()
    m = re.match(r"^--(?:lua-desync|dpi-desync)=([a-zA-Z0-9_-]+)", s)
    if not m:
        return None
    return m.group(1).strip().lower() or None


def _map_desync_technique_to_tcp_phase(technique: str) -> str | None:
    t = (technique or "").strip().lower()
    if not t:
        return None
    # "pass" is a no-op, but keeping it in the main phase ensures
    # categories can still be enabled for send/syndata/out-range-only setups.
    if t == "pass":
        return "multisplit"
    if t == "fake":
        return "fake"
    if t in ("multisplit", "fakedsplit", "hostfakesplit"):
        return "multisplit"
    if t in ("multidisorder", "fakeddisorder"):
        return "multidisorder"
    if t == "multidisorder_legacy":
        return "multidisorder_legacy"
    if t == "tcpseg":
        return "tcpseg"
    if t == "oob":
        return "oob"
    return "other"


def _normalize_args_text(text: str) -> str:
    """Normalizes args text for exact matching (keeps line order)."""
    if not text:
        return ""
    lines = [ln.strip() for ln in str(text).splitlines() if ln.strip()]
    return "\n".join(lines).strip()


class TTLButtonSelector(QWidget):
    """
    Универсальный селектор значения через ряд кнопок.
    Используется для send_ip_ttl, autottl_delta, autottl_min, autottl_max
    """
    value_changed = pyqtSignal(int)  # Эмитит выбранное значение

    def __init__(self, values: list, labels: list = None, parent=None):
        """
        Args:
            values: список int значений для кнопок, например [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
            labels: опциональные метки для кнопок, например ["off", "1", "2", ...]
                   Если None - используются str(value)
        """
        super().__init__(parent)
        self._values = values
        self._labels = labels or [str(v) for v in values]
        self._current_value = values[0]
        self._buttons = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        for i, (value, label) in enumerate(zip(self._values, self._labels)):
            btn = TogglePushButton(self)
            btn.setText(label)
            btn.setFixedSize(36, 24)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, v=value: self._select(v))
            self._buttons.append((btn, value))
            layout.addWidget(btn)

        layout.addStretch()
        self._sync_checked_states()

    def _select(self, value: int):
        if value != self._current_value:
            self._current_value = value
            self._sync_checked_states()
            self.value_changed.emit(value)

    def _sync_checked_states(self):
        for btn, value in self._buttons:
            btn.setChecked(value == self._current_value)

    def setValue(self, value: int, block_signals: bool = False):
        """Устанавливает значение программно"""
        if value in self._values:
            if block_signals:
                self.blockSignals(True)
            self._current_value = value
            self._sync_checked_states()
            if block_signals:
                self.blockSignals(False)

    def value(self) -> int:
        """Возвращает текущее значение"""
        return self._current_value


class ElidedLabel(QLabel):
    """QLabel, который автоматически обрезает текст с троеточием по ширине."""

    def __init__(self, text: str = "", parent=None):
        # Do not rely on QLabel text layout: setting text can trigger relayout/resize loops.
        # We paint the elided text ourselves in paintEvent for stability.
        super().__init__("", parent)
        self._full_text = text or ""
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        super().setText("")  # keep QLabel's own text empty; we paint manually
        self.set_full_text(self._full_text)

    def set_full_text(self, text: str) -> None:
        self._full_text = text or ""
        self.update()

    def full_text(self) -> str:
        return self._full_text

    def paintEvent(self, event):  # noqa: N802 (Qt override)
        # Let QLabel paint its background/style (with empty text), then draw elided text.
        super().paintEvent(event)
        text = self._full_text or ""
        if not text:
            return

        try:
            r = self.contentsRect()
            w = max(0, int(r.width()))
            if w <= 0:
                return

            metrics = QFontMetrics(self.font())
            elided = metrics.elidedText(text, Qt.TextElideMode.ElideRight, w)

            from PyQt6.QtGui import QPainter

            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
            p.setFont(self.font())
            p.setPen(self.palette().color(self.foregroundRole()))
            align = self.alignment() or (Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            p.drawText(r, int(align), elided)
        except Exception:
            return


class ArgsPreview(CaptionLabel):
    """Превью args на 2-3 строки (лёгкий label вместо QTextEdit на каждой строке)."""

    def __init__(self, max_lines: int = 3, parent=None):
        super().__init__(parent)
        self._max_lines = max(1, int(max_lines or 1))
        self._full_text = ""

        self.setWordWrap(True)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.setFont(QFont("Consolas", 9))
        self.setContentsMargins(4, 0, 4, 0)
        self._sync_height()

    def set_full_text(self, text: str):
        self._full_text = text or ""
        set_tooltip(self, (self._full_text or "").replace("\n", "<br>"))
        self.setText(self._wrap_friendly(self._full_text))

    def full_text(self) -> str:
        return self._full_text

    def _sync_height(self):
        metrics = QFontMetrics(self.font())
        line_h = metrics.lineSpacing()
        # +2 чтобы не резало нижние пиксели глифов на некоторых шрифтах/рендерах.
        self.setMaximumHeight((line_h * self._max_lines) + 2)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # QLabel сам переформатирует переносы по ширине; высоту держим постоянной.

    @staticmethod
    def _wrap_friendly(text: str) -> str:
        if not text:
            return ""
        # Добавляем точки переноса внутри "длинных слов" аргументов.
        zws = "\u200b"
        return (
            text.replace(":", f":{zws}")
            .replace(",", f",{zws}")
            .replace("=", f"={zws}")
        )


class _PresetNameDialog(MessageBoxBase):
    """WinUI-style modal dialog for preset create / rename (uses qfluentwidgets MessageBoxBase)."""

    def __init__(self, mode: str, old_name: str = "", parent=None, language: str = "ru"):
        super().__init__(parent)
        self._mode = mode  # "create" | "rename"
        self._ui_language = language

        title_text = (
            _tr_text(self._ui_language, "page.z2_strategy_detail.preset_dialog.create.title", "Создать пресет")
            if mode == "create"
            else _tr_text(self._ui_language, "page.z2_strategy_detail.preset_dialog.rename.title", "Переименовать пресет")
        )
        self.titleLabel = SubtitleLabel(title_text, self.widget)

        if mode == "rename" and old_name:
            from_label = CaptionLabel(
                _tr_text(
                    self._ui_language,
                    "page.z2_strategy_detail.preset_dialog.rename.current_name",
                    "Текущее имя: {name}",
                    name=old_name,
                ),
                self.widget,
            )
            self.viewLayout.addWidget(self.titleLabel)
            self.viewLayout.addWidget(from_label)
        else:
            self.viewLayout.addWidget(self.titleLabel)

        name_label = BodyLabel(
            _tr_text(self._ui_language, "page.z2_strategy_detail.preset_dialog.name_label", "Название"),
            self.widget,
        )
        self.name_edit = LineEdit(self.widget)
        self.name_edit.setPlaceholderText(
            _tr_text(
                self._ui_language,
                "page.z2_strategy_detail.preset_dialog.name_placeholder",
                "Введите название пресета...",
            )
        )
        if mode == "rename" and old_name:
            self.name_edit.setText(old_name)
        self.name_edit.returnPressed.connect(self._validate_and_accept)

        self._error_label = CaptionLabel("", self.widget)
        try:
            from qfluentwidgets import isDarkTheme as _idt
            _err_clr = "#ff6b6b" if _idt() else "#dc2626"
        except Exception:
            _err_clr = "#dc2626"
        self._error_label.setStyleSheet(f"color: {_err_clr};")
        self._error_label.hide()

        self.viewLayout.addWidget(name_label)
        self.viewLayout.addWidget(self.name_edit)
        self.viewLayout.addWidget(self._error_label)

        self.yesButton.setText(
            _tr_text(self._ui_language, "page.z2_strategy_detail.preset_dialog.button.create", "Создать")
            if mode == "create"
            else _tr_text(self._ui_language, "page.z2_strategy_detail.preset_dialog.button.rename", "Переименовать")
        )
        self.cancelButton.setText(
            _tr_text(self._ui_language, "page.z2_strategy_detail.preset_dialog.button.cancel", "Отмена")
        )
        self.widget.setMinimumWidth(360)

    def _validate_and_accept(self):
        if self.validate():
            self.accept()

    def validate(self) -> bool:
        name = self.name_edit.text().strip()
        if not name:
            self._error_label.setText(
                _tr_text(self._ui_language, "page.z2_strategy_detail.preset_dialog.error.empty", "Введите название пресета")
            )
            self._error_label.show()
            return False
        self._error_label.hide()
        return True

    def get_name(self) -> str:
        return self.name_edit.text().strip()


class StrategyDetailPage(BasePage):
    """
    Страница детального выбора стратегии для категории.

    Signals:
        strategy_selected(str, str): Эмитится при выборе стратегии (category_key, strategy_id)
        args_changed(str, str, list): Эмитится при изменении аргументов (category_key, strategy_id, new_args)
        strategy_marked(str, str, object): Эмитится при пометке стратегии (category_key, strategy_id, is_working)
        back_clicked(): Эмитится при нажатии кнопки "Назад"
    """

    strategy_selected = pyqtSignal(str, str)  # category_key, strategy_id
    filter_mode_changed = pyqtSignal(str, str)  # category_key, "hostlist"|"ipset"
    args_changed = pyqtSignal(str, str, list)  # category_key, strategy_id, new_args
    strategy_marked = pyqtSignal(str, str, object)  # category_key, strategy_id, is_working (bool|None)
    back_clicked = pyqtSignal()
    navigate_to_root = pyqtSignal()  # → PageName.ZAPRET2_DIRECT_CONTROL (skip strategies list)

    def __init__(self, parent=None):
        super().__init__(
            title="",  # Заголовок будет установлен динамически
            subtitle="",
            title_key="page.z2_strategy_detail.title",
            subtitle_key="page.z2_strategy_detail.subtitle",
            parent=parent,
        )
        # BasePage uses `SetMaximumSize` to clamp the content widget to its layout's
        # sizeHint. With dynamic/lazy-loaded content (like strategies list), this can
        # leave the scroll range "stuck" and cut off the bottom. For this page, keep
        # the default constraint so height can grow freely.
        try:
            self.layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetDefaultConstraint)
        except Exception:
            pass
        # Reset the content widget maximum size too: `SetMaximumSize` may have already
        # applied a maxHeight during BasePage init, and switching the layout constraint
        # afterwards does not always clear that clamp.
        try:
            if hasattr(self, "content") and self.content is not None:
                self.content.setMaximumSize(16777215, 16777215)
        except Exception:
            pass
        self.parent_app = parent
        self._category_key = None
        self._category_info = None
        self._current_strategy_id = "none"
        self._selected_strategy_id = "none"
        self._strategies_tree = None
        self._sort_mode = "default"  # default, name_asc, name_desc
        self._active_filters = set()  # Активные фильтры по технике
        # TCP multi-phase UI state (direct_zapret2, tcp.txt + tcp_fake.txt)
        self._tcp_phase_mode = False
        self._phase_tabbar: SegmentedWidget | None = None
        self._phase_tab_index_by_key: dict[str, int] = {}
        self._phase_tab_key_by_index: dict[int, str] = {}
        self._active_phase_key = None
        self._last_active_phase_key_by_category: dict[str, str] = {}
        self._tcp_phase_selected_ids: dict[str, str] = {}  # phase_key -> strategy_id
        self._tcp_phase_custom_args: dict[str, str] = {}  # phase_key -> raw args chunk (if no matching strategy)
        self._tcp_hide_fake_phase = False
        self._tcp_last_enabled_args_by_category: dict[str, str] = {}
        self._waiting_for_process_start = False  # Флаг ожидания запуска DPI
        self._process_monitor_connected = False  # Флаг подключения к process_monitor
        self._fallback_timer = None  # Таймер защиты от бесконечного спиннера
        self._apply_feedback_timer = None  # Быстрый таймер: убрать спиннер после apply
        self._strategies_load_timer = None
        self._strategies_load_generation = 0
        self._pending_strategies_items = []
        self._pending_strategies_index = 0
        self._loaded_strategy_type = None
        self._loaded_strategy_set = None
        self._loaded_tcp_phase_mode = False
        self._default_strategy_order = []
        self._strategies_loaded_fully = False
        self._page_scroll_by_category: dict[str, int] = {}
        self._tree_scroll_by_category: dict[str, int] = {}

        # Direct preset facade for category settings storage
        from core.presets.direct_facade import DirectPresetFacade

        self._preset_manager = DirectPresetFacade.from_launch_method(
            "direct_zapret2",
            on_dpi_reload_needed=self._on_dpi_reload_needed,
        )
        self._marks_store = DirectZapret2MarksStore.default()
        self._favorites_store = DirectZapret2FavoritesStore.default()
        self._favorite_strategy_ids = set()
        self._preview_dialog = None
        self._preview_pinned = False
        self._main_window = None
        self._strategies_data_by_id = {}
        self._content_built = False
        self._theme_refresh_scheduled = False
        self._theme_refresh_in_progress = False
        self._last_theme_overrides_key = None
        self._last_parent_link_icon_color = None
        self._last_edit_args_icon_color = None
        self._last_sort_icon_color = None

    def _tr(self, key: str, default: str, **kwargs) -> str:
        return _tr_text(self._ui_language, key, default, **kwargs)

    def _ensure_content_built(self) -> None:
        if self._content_built:
            return
        self._build_content()
        self._content_built = True

        # Close hover/pinned preview when the main window hides/deactivates (e.g. tray).
        QTimer.singleShot(0, self._install_main_window_event_filter)

        # Подключаемся к process_monitor для отслеживания статуса DPI
        self._connect_process_monitor()

    def _install_main_window_event_filter(self) -> None:
        try:
            w = self.window()
        except Exception:
            w = None
        if not w or w is self._main_window:
            return
        self._main_window = w
        try:
            w.installEventFilter(self)
        except Exception:
            pass

    def eventFilter(self, obj, event):  # noqa: N802 (Qt override)
        try:
            if obj is self._main_window and event is not None:
                et = event.type()
                if et in (
                    QEvent.Type.Hide,
                    QEvent.Type.Close,
                    QEvent.Type.WindowDeactivate,
                    QEvent.Type.WindowStateChange,
                ):
                    # Don't close if focus went to the preview dialog itself.
                    if et == QEvent.Type.WindowDeactivate and self._preview_dialog is not None:
                        try:
                            from PyQt6.QtWidgets import QApplication as _QApp
                            active = _QApp.activeWindow()
                            if active is not None and active is self._preview_dialog:
                                return super().eventFilter(obj, event)
                        except Exception:
                            pass
                    self._close_preview_dialog(force=True)
                    self._close_filter_combo_popup()
        except Exception:
            pass
        return super().eventFilter(obj, event)

    def _close_filter_combo_popup(self) -> None:
        """Close the technique filter ComboBox dropdown if it is open."""
        try:
            combo = getattr(self, "_filter_combo", None)
            if combo is not None and hasattr(combo, "_closeComboMenu"):
                combo._closeComboMenu()
        except Exception:
            pass

    def changeEvent(self, event):  # noqa: N802 (Qt override)
        try:
            if event.type() in (QEvent.Type.StyleChange, QEvent.Type.PaletteChange):
                if self._theme_refresh_in_progress:
                    return super().changeEvent(event)
                if not self._theme_refresh_scheduled:
                    self._theme_refresh_scheduled = True
                    QTimer.singleShot(0, self._on_debounced_theme_change)
        except Exception:
            pass
        return super().changeEvent(event)

    def _on_debounced_theme_change(self) -> None:
        if self._theme_refresh_in_progress:
            return
        self._theme_refresh_in_progress = True
        try:
            self._apply_theme_overrides()
        finally:
            self._theme_refresh_in_progress = False
            self._theme_refresh_scheduled = False

    def _apply_theme_overrides(self) -> None:
        try:
            tokens = get_theme_tokens()
        except Exception:
            return

        key = (
            str(tokens.theme_name),
            str(tokens.fg),
            str(tokens.fg_muted),
            str(tokens.fg_faint),
            str(tokens.accent_hex),
        )
        if key == self._last_theme_overrides_key:
            return
        self._last_theme_overrides_key = key

        try:
            detail_text_color = tokens.fg_muted if tokens.is_light else tokens.fg
            if getattr(self, "_subtitle_strategy", None) is not None:
                subtitle_style = f"background: transparent; padding-left: 10px; color: {detail_text_color};"
                if self._subtitle_strategy.styleSheet() != subtitle_style:
                    self._subtitle_strategy.setStyleSheet(subtitle_style)
        except Exception:
            pass

        try:
            if getattr(self, "_parent_link", None) is not None:
                parent_color = str(tokens.fg_muted)
                if parent_color != self._last_parent_link_icon_color:
                    self._parent_link.setIcon(qta.icon('fa5s.chevron-left', color=parent_color))
                    self._last_parent_link_icon_color = parent_color
        except Exception:
            pass

        try:
            if not _HAS_FLUENT and getattr(self, "_edit_args_btn", None) is not None:
                edit_color = str(tokens.fg_faint)
                if edit_color != self._last_edit_args_icon_color:
                    self._edit_args_btn.setIcon(qta.icon('fa5s.edit', color=edit_color))
                    self._last_edit_args_icon_color = edit_color
        except Exception:
            pass

        try:
            self._update_sort_button_ui()
        except Exception:
            pass

    def hideEvent(self, event):  # noqa: N802 (Qt override)
        # Ensure floating preview/tool windows do not keep intercepting mouse events
        # after navigation away from this page.
        try:
            self._save_scroll_state()
        except Exception:
            pass
        try:
            self._close_preview_dialog(force=True)
        except Exception:
            pass
        try:
            self._close_filter_combo_popup()
        except Exception:
            pass
        try:
            self._stop_loading()
        except Exception:
            pass
        try:
            self._strategies_load_generation += 1
            if self._strategies_load_timer:
                self._strategies_load_timer.stop()
                self._strategies_load_timer = None
        except Exception:
            pass
        return super().hideEvent(event)

    def _refresh_scroll_range(self) -> None:
        # Ensure QScrollArea recomputes range after dynamic content growth.
        try:
            if self.layout is not None:
                self.layout.invalidate()
                self.layout.activate()
        except Exception:
            pass
        try:
            if hasattr(self, "content") and self.content is not None:
                self.content.updateGeometry()
                self.content.adjustSize()
        except Exception:
            pass
        try:
            self.updateGeometry()
            self.viewport().update()
        except Exception:
            pass

    def _save_scroll_state(self, category_key: str | None = None) -> None:
        key = str(category_key or self._category_key or "").strip()
        if not key:
            return

        try:
            bar = self.verticalScrollBar()
            self._page_scroll_by_category[key] = int(bar.value())
        except Exception:
            pass

        try:
            if self._strategies_tree:
                tree_bar = self._strategies_tree.verticalScrollBar()
                self._tree_scroll_by_category[key] = int(tree_bar.value())
        except Exception:
            pass

    def _restore_scroll_state(self, category_key: str | None = None, defer: bool = False) -> None:
        key = str(category_key or self._category_key or "").strip()
        if not key:
            return

        def _apply() -> None:
            try:
                page_bar = self.verticalScrollBar()
                saved_page = self._page_scroll_by_category.get(key)
                if saved_page is None:
                    page_bar.setValue(page_bar.minimum())
                else:
                    page_bar.setValue(max(page_bar.minimum(), min(int(saved_page), page_bar.maximum())))
            except Exception:
                pass

            try:
                if not self._strategies_tree:
                    return
                tree_bar = self._strategies_tree.verticalScrollBar()
                saved_tree = self._tree_scroll_by_category.get(key)
                if saved_tree is None:
                    return
                tree_bar.setValue(max(tree_bar.minimum(), min(int(saved_tree), tree_bar.maximum())))
            except Exception:
                pass

        if defer:
            QTimer.singleShot(0, _apply)
            QTimer.singleShot(40, _apply)
        else:
            _apply()

    def _on_dpi_reload_needed(self):
        """Callback for PresetManager when DPI reload is needed."""
        # Any preset sync may restart / hot-reload winws2 via the config watcher.
        # Flip the header indicator to spinner so UI matches the real behavior.
        try:
            self.show_loading()
        except Exception:
            pass
        from dpi.zapret2_core_restart import trigger_dpi_reload
        if self.parent_app:
            trigger_dpi_reload(
                self.parent_app,
                reason="preset_settings_changed",
                category_key=self._category_key
            )

    def _on_breadcrumb_item_changed(self, route_key: str) -> None:
        """Breadcrumb click handler: navigate up the hierarchy."""
        # BreadcrumbBar physically deletes trailing items on click —
        # restore the full path immediately so the widget is correct when we return.
        if self._breadcrumb is not None and self._category_key:
            cat_name = ""
            try:
                cat_name = self._category_info.full_name if self._category_info else ""
            except Exception:
                pass
            self._breadcrumb.blockSignals(True)
            try:
                self._breadcrumb.clear()
                self._breadcrumb.addItem("control", self._tr("page.z2_strategy_detail.breadcrumb.control", "Управление"))
                self._breadcrumb.addItem("strategies", self._tr("page.z2_strategy_detail.breadcrumb.strategies", "Стратегии DPI"))
                self._breadcrumb.addItem(
                    "detail",
                    cat_name or self._tr("page.z2_strategy_detail.header.category_fallback", "Категория"),
                )
            finally:
                self._breadcrumb.blockSignals(False)

        if route_key == "control":
            self.navigate_to_root.emit()
        elif route_key == "strategies":
            self.back_clicked.emit()
        # "detail" = current page, nothing to do

    def _build_content(self):
        """Строит содержимое страницы"""
        tokens = get_theme_tokens()
        detail_text_color = tokens.fg_muted if tokens.is_light else tokens.fg

        # Скрываем стандартный заголовок BasePage
        if self.title_label is not None:
            self.title_label.hide()
        if self.subtitle_label is not None:
            self.subtitle_label.hide()

        # Хедер с breadcrumb-навигацией в стиле Windows 11 Settings
        header = QFrame()
        header.setFrameShape(QFrame.Shape.NoFrame)
        header.setStyleSheet("background: transparent; border: none;")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 16)
        header_layout.setSpacing(4)

        # Breadcrumb navigation: Управление › Стратегии DPI › [Category]
        self._breadcrumb = None
        try:
            from qfluentwidgets import BreadcrumbBar as _BreadcrumbBar
            self._breadcrumb = _BreadcrumbBar(self)
            self._breadcrumb.blockSignals(True)
            self._breadcrumb.addItem("control", self._tr("page.z2_strategy_detail.breadcrumb.control", "Управление"))
            self._breadcrumb.addItem("strategies", self._tr("page.z2_strategy_detail.breadcrumb.strategies", "Стратегии DPI"))
            self._breadcrumb.addItem("detail", self._tr("page.z2_strategy_detail.header.category_fallback", "Категория"))
            self._breadcrumb.blockSignals(False)
            self._breadcrumb.currentItemChanged.connect(self._on_breadcrumb_item_changed)
            header_layout.addWidget(self._breadcrumb)
        except Exception:
            # Fallback: original back button
            back_row = QHBoxLayout()
            back_row.setContentsMargins(0, 0, 0, 0)
            back_row.setSpacing(4)
            self._parent_link = TransparentPushButton(parent=self)
            self._parent_link.setText(self._tr("page.z2_strategy_detail.back.strategies", "Стратегии DPI"))
            self._parent_link.setIcon(qta.icon('fa5s.chevron-left', color=tokens.fg_muted))
            self._parent_link.setIconSize(QSize(12, 12))
            self._parent_link.clicked.connect(self.back_clicked.emit)
            back_row.addWidget(self._parent_link)
            back_row.addStretch()
            header_layout.addLayout(back_row)

        # Current page title
        self._title = TitleLabel(self._tr("page.z2_strategy_detail.header.select_category", "Выберите категорию"))
        header_layout.addWidget(self._title)

        # Строка с галочкой и подзаголовком
        subtitle_row = QHBoxLayout()
        subtitle_row.setContentsMargins(0, 0, 0, 0)
        subtitle_row.setSpacing(6)

        # Спиннер загрузки
        self._spinner = IndeterminateProgressRing(start=False)
        self._spinner.setFixedSize(16, 16)
        self._spinner.setStrokeWidth(2)
        self._spinner.hide()
        subtitle_row.addWidget(self._spinner)

        # Галочка успеха (показывается после загрузки)
        self._success_icon = PixmapLabel()
        self._success_icon.setFixedSize(16, 16)
        self._success_icon.hide()
        subtitle_row.addWidget(self._success_icon)

        # Подзаголовок (протокол | порты)
        self._subtitle = BodyLabel("")
        subtitle_row.addWidget(self._subtitle)

        # Выбранная стратегия (мелким шрифтом, справа от портов)
        self._subtitle_strategy = ElidedLabel("")
        self._subtitle_strategy.setFont(QFont("Segoe UI", 11))
        try:
            self._subtitle_strategy.setProperty("tone", "muted")
        except Exception:
            pass
        self._subtitle_strategy.setStyleSheet(
            f"background: transparent; padding-left: 10px; color: {detail_text_color};"
        )
        self._subtitle_strategy.hide()
        subtitle_row.addWidget(self._subtitle_strategy, 1)

        header_layout.addLayout(subtitle_row)

        self.layout.addWidget(header)

        # ═══════════════════════════════════════════════════════════════
        # ВКЛЮЧЕНИЕ КАТЕГОРИИ + НАСТРОЙКИ
        # ═══════════════════════════════════════════════════════════════
        self._settings_host = QWidget()
        settings_host_layout = QVBoxLayout(self._settings_host)
        settings_host_layout.setContentsMargins(0, 0, 0, 0)
        settings_host_layout.setSpacing(6)

        # ═══════════════════════════════════════════════════════════════
        # ТУЛБАР НАСТРОЕК КАТЕГОРИИ (фоновой блок)
        # ═══════════════════════════════════════════════════════════════
        self._toolbar_frame = QFrame()
        # Убираем background: transparent; border: none; чтобы фон был как у карточек,
        # или оставляем его контейнером, а внутри будут SettingsCard
        toolbar_layout = QVBoxLayout(self._toolbar_frame)
        toolbar_layout.setContentsMargins(0, 4, 0, 4)
        toolbar_layout.setSpacing(12)

        # ═══════════════════════════════════════════════════════════════
        # REGULAR SETTINGS
        # ═══════════════════════════════════════════════════════════════
        self._general_card = SettingsCard()

        # Режим фильтрации row
        self._filter_mode_frame = SettingsRow(
            "fa5s.filter",
            self._tr("page.z2_strategy_detail.filter_mode.title", "Режим фильтрации"),
            self._tr("page.z2_strategy_detail.filter_mode.description", "Hostlist - по доменам, IPset - по IP"),
        )
        self._filter_mode_selector = SwitchButton(parent=self)
        self._filter_mode_selector.setOnText(self._tr("page.z2_strategy_detail.filter.ipset", "IPset"))
        self._filter_mode_selector.setOffText(self._tr("page.z2_strategy_detail.filter.hostlist", "Hostlist"))
        self._filter_mode_selector.checkedChanged.connect(
            lambda checked: self._on_filter_mode_changed("ipset" if checked else "hostlist")
        )
        self._filter_mode_frame.set_control(self._filter_mode_selector)
        self._general_card.add_widget(self._filter_mode_frame)

        # OUT RANGE
        self._out_range_frame = SettingsRow(
            "fa5s.sliders-h",
            self._tr("page.z2_strategy_detail.out_range.title", "Out Range"),
            self._tr("page.z2_strategy_detail.out_range.description", "Ограничение исходящих пакетов"),
        )
        self._out_range_mode_label = BodyLabel(self._tr("page.z2_strategy_detail.out_range.mode", "Режим:"))
        self._out_range_frame.control_container.addWidget(self._out_range_mode_label)

        self._out_range_seg = SegmentedWidget()
        self._out_range_seg.addItem("n", "n", lambda: self._select_out_range_mode("n"))
        self._out_range_seg.addItem("d", "d", lambda: self._select_out_range_mode("d"))
        set_tooltip(
            self._out_range_seg,
            self._tr(
                "page.z2_strategy_detail.out_range.mode.tooltip",
                "n = количество пакетов с самого первого, d = отсчитывать ТОЛЬКО количество пакетов с данными",
            ),
        )
        self._out_range_mode = "n"
        self._out_range_seg.setCurrentItem("n")
        self._out_range_frame.control_container.addWidget(self._out_range_seg)

        self._out_range_value_label = BodyLabel(self._tr("page.z2_strategy_detail.out_range.value", "Значение:"))
        self._out_range_frame.control_container.addWidget(self._out_range_value_label)

        self._out_range_spin = SpinBox()
        self._out_range_spin.setRange(1, 999)
        self._out_range_spin.setValue(8)
        self._out_range_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        set_tooltip(
            self._out_range_spin,
            self._tr(
                "page.z2_strategy_detail.out_range.value.tooltip",
                "--out-range: ограничение количества исходящих пакетов (n) или задержки (d)",
            ),
        )
        self._out_range_spin.valueChanged.connect(self._save_syndata_settings)
        self._out_range_frame.control_container.addWidget(self._out_range_spin)

        self._general_card.add_widget(self._out_range_frame)
        toolbar_layout.addWidget(self._general_card)

        # ═══════════════════════════════════════════════════════════════
        # SEND SETTINGS (collapsible)
        # ═══════════════════════════════════════════════════════════════
        self._send_frame = SettingsCard()

        self._send_toggle_row = Win11ToggleRow(
            "fa5s.paper-plane",
            self._tr("page.z2_strategy_detail.send.toggle.title", "Send параметры"),
            self._tr("page.z2_strategy_detail.send.toggle.description", "Отправка копий пакетов"),
        )
        self._send_toggle = self._send_toggle_row.toggle
        self._send_toggle_row.toggled.connect(self._on_send_toggled)
        self._send_frame.add_widget(self._send_toggle_row)

        # Settings panel (shown when enabled)
        self._send_settings = QWidget()
        self._send_settings.setVisible(False)
        send_settings_layout = QVBoxLayout(self._send_settings)
        send_settings_layout.setContentsMargins(12, 0, 0, 0)
        send_settings_layout.setSpacing(0)

        # send_repeats row
        self._send_repeats_row = Win11NumberRow(
            "fa5s.redo",
            self._tr("page.z2_strategy_detail.send.repeats.title", "repeats"),
            self._tr("page.z2_strategy_detail.send.repeats.description", "Количество повторных отправок"),
            min_val=0,
            max_val=10,
            default_val=2,
        )
        self._send_repeats_spin = self._send_repeats_row.spinbox
        self._send_repeats_row.valueChanged.connect(self._save_syndata_settings)
        send_settings_layout.addWidget(self._send_repeats_row)

        # send_ip_ttl row
        self._send_ip_ttl_frame = SettingsRow(
            "fa5s.stopwatch",
            self._tr("page.z2_strategy_detail.send.ip_ttl.title", "ip_ttl"),
            self._tr("page.z2_strategy_detail.send.ip_ttl.description", "TTL для IPv4 отправляемых пакетов"),
        )
        self._send_ip_ttl_selector = TTLButtonSelector(
            values=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
            labels=["off", "1", "2", "3", "4", "5", "6", "7", "8", "9"]
        )
        self._send_ip_ttl_selector.value_changed.connect(self._save_syndata_settings)
        self._send_ip_ttl_frame.set_control(self._send_ip_ttl_selector)
        send_settings_layout.addWidget(self._send_ip_ttl_frame)

        # send_ip6_ttl row
        self._send_ip6_ttl_frame = SettingsRow(
            "fa5s.stopwatch",
            self._tr("page.z2_strategy_detail.send.ip6_ttl.title", "ip6_ttl"),
            self._tr("page.z2_strategy_detail.send.ip6_ttl.description", "TTL для IPv6 отправляемых пакетов"),
        )
        self._send_ip6_ttl_selector = TTLButtonSelector(
            values=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
            labels=["off", "1", "2", "3", "4", "5", "6", "7", "8", "9"]
        )
        self._send_ip6_ttl_selector.value_changed.connect(self._save_syndata_settings)
        self._send_ip6_ttl_frame.set_control(self._send_ip6_ttl_selector)
        send_settings_layout.addWidget(self._send_ip6_ttl_frame)

        # send_ip_id row
        self._send_ip_id_row = Win11ComboRow(
            "fa5s.fingerprint",
            self._tr("page.z2_strategy_detail.send.ip_id.title", "ip_id"),
            self._tr("page.z2_strategy_detail.send.ip_id.description", "Режим IP ID для отправляемых пакетов"),
            items=[("none", None), ("seq", None), ("rnd", None), ("zero", None)],
        )
        self._send_ip_id_combo = self._send_ip_id_row.combo
        self._send_ip_id_row.currentTextChanged.connect(self._save_syndata_settings)
        send_settings_layout.addWidget(self._send_ip_id_row)

        # send_badsum row
        self._send_badsum_frame = SettingsRow(
            "fa5s.exclamation-triangle",
            self._tr("page.z2_strategy_detail.send.badsum.title", "badsum"),
            self._tr(
                "page.z2_strategy_detail.send.badsum.description",
                "Отправлять пакеты с неправильной контрольной суммой",
            ),
        )
        self._send_badsum_check = SwitchButton()
        self._send_badsum_check.checkedChanged.connect(self._save_syndata_settings)
        self._send_badsum_frame.set_control(self._send_badsum_check)
        send_settings_layout.addWidget(self._send_badsum_frame)

        self._send_frame.add_widget(self._send_settings)
        toolbar_layout.addWidget(self._send_frame)

        # ═══════════════════════════════════════════════════════════════
        # SYNDATA SETTINGS (collapsible)
        # ═══════════════════════════════════════════════════════════════
        self._syndata_frame = SettingsCard()

        self._syndata_toggle_row = Win11ToggleRow(
            "fa5s.cog",
            self._tr("page.z2_strategy_detail.syndata.toggle.title", "Syndata параметры"),
            self._tr(
                "page.z2_strategy_detail.syndata.toggle.description",
                "Дополнительные параметры обхода DPI",
            ),
        )
        self._syndata_toggle = self._syndata_toggle_row.toggle
        self._syndata_toggle_row.toggled.connect(self._on_syndata_toggled)
        self._syndata_frame.add_widget(self._syndata_toggle_row)

        # Settings panel (shown when enabled)
        self._syndata_settings = QWidget()
        self._syndata_settings.setVisible(False)
        settings_layout = QVBoxLayout(self._syndata_settings)
        settings_layout.setContentsMargins(12, 0, 0, 0)
        settings_layout.setSpacing(0)

        # Blob selector row
        blob_names = ["none"]
        try:
            all_blobs = get_blobs_info()
            blob_names = ["none"] + sorted(all_blobs.keys())
        except Exception:
            blob_names = ["none", "tls_google", "tls7"]
        blob_items = [(n, None) for n in blob_names]

        self._blob_row = Win11ComboRow(
            "fa5s.file-code",
            self._tr("page.z2_strategy_detail.syndata.blob.title", "blob"),
            self._tr("page.z2_strategy_detail.syndata.blob.description", "Полезная нагрузка пакета"),
            items=blob_items,
        )
        self._blob_combo = self._blob_row.combo
        self._blob_row.currentTextChanged.connect(self._save_syndata_settings)
        settings_layout.addWidget(self._blob_row)

        # tls_mod selector row
        self._tls_mod_row = Win11ComboRow(
            "fa5s.shield-alt",
            self._tr("page.z2_strategy_detail.syndata.tls_mod.title", "tls_mod"),
            self._tr("page.z2_strategy_detail.syndata.tls_mod.description", "Модификация полезной нагрузки TLS"),
            items=[("none", None), ("rnd", None), ("rndsni", None), ("sni=google.com", None)],
        )
        self._tls_mod_combo = self._tls_mod_row.combo
        self._tls_mod_row.currentTextChanged.connect(self._save_syndata_settings)
        settings_layout.addWidget(self._tls_mod_row)

        # ═══════════════════════════════════════════════════════════════
        # AUTOTTL SETTINGS (три строки с кнопками)
        # ═══════════════════════════════════════════════════════════════
        # --- Delta row ---
        self._autottl_delta_frame = SettingsRow(
            "fa5s.clock",
            self._tr("page.z2_strategy_detail.syndata.autottl_delta.title", "AutoTTL Delta"),
            self._tr(
                "page.z2_strategy_detail.syndata.autottl_delta.description",
                "Смещение от измеренного TTL (OFF = убрать ip_autottl)",
            ),
        )
        self._autottl_delta_selector = TTLButtonSelector(
            values=[0, -1, -2, -3, -4, -5, -6, -7, -8, -9],
            labels=["OFF", "-1", "-2", "-3", "-4", "-5", "-6", "-7", "-8", "-9"]
        )
        self._autottl_delta_selector.value_changed.connect(self._save_syndata_settings)
        self._autottl_delta_frame.set_control(self._autottl_delta_selector)
        settings_layout.addWidget(self._autottl_delta_frame)

        # --- Min row ---
        self._autottl_min_frame = SettingsRow(
            "fa5s.angle-down",
            self._tr("page.z2_strategy_detail.syndata.autottl_min.title", "AutoTTL Min"),
            self._tr("page.z2_strategy_detail.syndata.autottl_min.description", "Минимальный TTL"),
        )
        self._autottl_min_selector = TTLButtonSelector(
            values=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            labels=["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]
        )
        self._autottl_min_selector.value_changed.connect(self._save_syndata_settings)
        self._autottl_min_frame.set_control(self._autottl_min_selector)
        settings_layout.addWidget(self._autottl_min_frame)

        # --- Max row ---
        self._autottl_max_frame = SettingsRow(
            "fa5s.angle-up",
            self._tr("page.z2_strategy_detail.syndata.autottl_max.title", "AutoTTL Max"),
            self._tr("page.z2_strategy_detail.syndata.autottl_max.description", "Максимальный TTL"),
        )
        self._autottl_max_selector = TTLButtonSelector(
            values=[15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25],
            labels=["15", "16", "17", "18", "19", "20", "21", "22", "23", "24", "25"]
        )
        self._autottl_max_selector.value_changed.connect(self._save_syndata_settings)
        self._autottl_max_frame.set_control(self._autottl_max_selector)
        settings_layout.addWidget(self._autottl_max_frame)

        # TCP flags row
        self._tcp_flags_row = Win11ComboRow(
            "fa5s.flag",
            self._tr("page.z2_strategy_detail.syndata.tcp_flags.title", "tcp_flags_unset"),
            self._tr("page.z2_strategy_detail.syndata.tcp_flags.description", "Сбросить TCP флаги"),
            items=[("none", None), ("ack", None), ("psh", None), ("ack,psh", None)],
        )
        self._tcp_flags_combo = self._tcp_flags_row.combo
        self._tcp_flags_row.currentTextChanged.connect(self._save_syndata_settings)
        settings_layout.addWidget(self._tcp_flags_row)

        self._syndata_frame.add_widget(self._syndata_settings)
        toolbar_layout.addWidget(self._syndata_frame)

        # ═══════════════════════════════════════════════════════════════
        # PRESET ACTIONS + RESET SETTINGS BUTTON
        # ═══════════════════════════════════════════════════════════════
        self._reset_row_widget = QWidget()
        reset_row = QHBoxLayout(self._reset_row_widget)
        reset_row.setContentsMargins(0, 8, 0, 0)
        reset_row.setSpacing(8)

        self._create_preset_btn = ActionButton(
            self._tr("page.z2_strategy_detail.button.create_preset", "Создать пресет"),
            "fa5s.plus",
        )
        set_tooltip(
            self._create_preset_btn,
            self._tr(
                "page.z2_strategy_detail.button.create_preset.tooltip",
                "Создать новый пресет на основе текущих настроек",
            ),
        )
        self._create_preset_btn.clicked.connect(self._on_create_preset_clicked)
        reset_row.addWidget(self._create_preset_btn)

        self._rename_preset_btn = ActionButton(
            self._tr("page.z2_strategy_detail.button.rename_preset", "Переименовать"),
            "fa5s.pen",
        )
        set_tooltip(
            self._rename_preset_btn,
            self._tr(
                "page.z2_strategy_detail.button.rename_preset.tooltip",
                "Переименовать текущий активный пресет",
            ),
        )
        self._rename_preset_btn.clicked.connect(self._on_rename_preset_clicked)
        reset_row.addWidget(self._rename_preset_btn)

        reset_row.addStretch()

        self._reset_settings_btn = ResetActionButton(
            self._tr("page.z2_strategy_detail.button.reset_settings", "Сбросить настройки"),
            confirm_text=self._tr("page.z2_strategy_detail.button.reset_settings.confirm", "Сбросить все?"),
        )
        self._reset_settings_btn.reset_confirmed.connect(self._on_reset_settings_confirmed)
        reset_row.addWidget(self._reset_settings_btn)

        toolbar_layout.addWidget(self._reset_row_widget)

        settings_host_layout.addWidget(self._toolbar_frame)
        self.layout.addWidget(self._settings_host)

        # Strategy controls stay visible even for disabled categories.
        self._strategies_block = QWidget()
        self._strategies_block.setObjectName("categoryStrategiesBlock")
        self._strategies_block.setProperty("categoryDisabled", False)
        self._strategies_block.setVisible(False)
        strategies_layout = QVBoxLayout(self._strategies_block)
        strategies_layout.setContentsMargins(0, 0, 0, 0)
        strategies_layout.setSpacing(0)

        # Поиск по стратегиям
        self._search_bar_widget = QWidget()
        search_layout = QHBoxLayout(self._search_bar_widget)
        search_layout.setContentsMargins(0, 0, 0, 8)
        # Add explicit spacing between the search input and icon buttons.
        # Previously it was 0, which made icons stick together visually.
        search_layout.setSpacing(6)

        self._search_input = LineEdit()
        self._search_input.setPlaceholderText(
            self._tr("page.z2_strategy_detail.search.placeholder", "Поиск по имени или args...")
        )
        self._search_input.setFixedHeight(36)
        self._search_input.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self._search_input)

        # Кнопка сортировки
        self._sort_btn = TransparentToolButton(parent=self)
        self._sort_btn.setIconSize(QSize(16, 16))
        self._sort_btn.setFixedSize(36, 36)
        self._sort_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        set_tooltip(self._sort_btn, self._tr("page.z2_strategy_detail.sort.tooltip.short", "Сортировка"))
        self._sort_btn.clicked.connect(self._show_sort_menu)
        search_layout.addWidget(self._sort_btn)

        # ComboBox фильтра по технике (одиночный выбор)
        self._filter_combo = ComboBox(parent=self)
        self._filter_combo.setFixedHeight(36)
        self._filter_combo.setFixedWidth(130)
        self._filter_combo.addItem(self._tr("page.z2_strategy_detail.filter.technique.all", "Все техники"))
        for label, _key in STRATEGY_TECHNIQUE_FILTERS:
            self._filter_combo.addItem(label)
        self._filter_combo.setCurrentIndex(0)
        self._filter_combo.currentIndexChanged.connect(self._on_technique_filter_changed)
        search_layout.addWidget(self._filter_combo)

        # Кнопка редактирования args (лениво, отдельная панель)
        try:
            from qfluentwidgets import FluentIcon as _FIF
            self._edit_args_btn = TransparentToolButton(_FIF.EDIT, parent=self)
        except Exception:
            self._edit_args_btn = TransparentToolButton(parent=self)
            self._edit_args_btn.setIcon(qta.icon('fa5s.edit', color=tokens.fg_faint))
        self._edit_args_btn.setIconSize(QSize(16, 16))
        self._edit_args_btn.setFixedSize(36, 36)
        self._edit_args_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        set_tooltip(
            self._edit_args_btn,
            self._tr(
                "page.z2_strategy_detail.args.tooltip",
                "Аргументы стратегии (по выбранной категории)",
            ),
        )
        self._edit_args_btn.setEnabled(False)
        self._edit_args_btn.clicked.connect(self._toggle_args_editor)
        search_layout.addWidget(self._edit_args_btn)

        # Initialize dynamic visuals/tooltips (sort/filter buttons).
        self._apply_theme_overrides()
        self._update_technique_filter_ui()

        strategies_layout.addWidget(self._search_bar_widget)

        self._args_editor_dirty = False

        # TCP multi-phase "tabs" (shown only for tcp categories in direct_zapret2)
        self._phases_bar_widget = QWidget()
        self._phases_bar_widget.setVisible(False)
        try:
            # Prevent frameless window drag from stealing tab clicks.
            self._phases_bar_widget.setProperty("noDrag", True)
        except Exception:
            pass
        phases_layout = QHBoxLayout(self._phases_bar_widget)
        phases_layout.setContentsMargins(0, 0, 0, 8)
        phases_layout.setSpacing(0)

        # SegmentedWidget (qfluentwidgets) for TCP multi-phase tab selection.
        self._phase_tabbar = SegmentedWidget(self)
        try:
            self._phase_tabbar.setProperty("noDrag", True)
        except Exception:
            pass

        self._phase_tab_index_by_key = {}
        self._phase_tab_key_by_index = {}
        for i, (phase_key, label) in enumerate(TCP_PHASE_TAB_ORDER):
            key = str(phase_key or "").strip().lower()
            self._phase_tab_index_by_key[key] = i
            self._phase_tab_key_by_index[i] = key
            try:
                self._phase_tabbar.addItem(
                    key, label,
                    onClick=lambda k=key: self._on_phase_pivot_item_clicked(k)
                )
            except Exception:
                pass

        try:
            self._phase_tabbar.currentItemChanged.connect(self._on_phase_tab_changed)
        except Exception:
            pass

        phases_layout.addWidget(self._phase_tabbar, 1)
        strategies_layout.addWidget(self._phases_bar_widget)

        # Лёгкий список стратегий: item-based, без сотен QWidget в layout
        self._strategies_tree = DirectZapret2StrategiesTree(self)
        # Внутренний скролл у дерева (надёжнее, чем растягивать страницу по высоте)
        self._strategies_tree.setProperty("noDrag", True)
        self._strategies_tree.strategy_clicked.connect(self._on_row_clicked)
        self._strategies_tree.favorite_toggled.connect(self._on_favorite_toggled)
        self._strategies_tree.working_mark_requested.connect(self._on_tree_working_mark_requested)
        self._strategies_tree.preview_requested.connect(self._on_tree_preview_requested)
        self._strategies_tree.preview_pinned_requested.connect(self._on_tree_preview_pinned_requested)
        self._strategies_tree.preview_hide_requested.connect(self._on_tree_preview_hide_requested)
        strategies_layout.addWidget(self._strategies_tree, 1)

        self.layout.addWidget(self._strategies_block, 1)

    def _update_selected_strategy_header(self, strategy_id: str) -> None:
        """Обновляет подзаголовок: показывает выбранную стратегию рядом с портами."""
        sid = (strategy_id or "none").strip()

        # TCP multi-phase summary (fake + multi*)
        if self._tcp_phase_mode:
            if sid == "none":
                try:
                    self._subtitle_strategy.hide()
                except Exception:
                    pass
                return

            parts: list[str] = []
            for phase in TCP_PHASE_COMMAND_ORDER:
                if phase == "fake" and self._tcp_hide_fake_phase:
                    continue
                psid = (self._tcp_phase_selected_ids.get(phase) or "").strip()
                if not psid:
                    continue
                if phase == "fake" and psid == TCP_FAKE_DISABLED_STRATEGY_ID:
                    continue

                if psid == CUSTOM_STRATEGY_ID:
                    name = CUSTOM_STRATEGY_ID
                else:
                    try:
                        data = dict(self._strategies_data_by_id.get(psid, {}) or {})
                    except Exception:
                        data = {}
                    name = str(data.get("name") or psid).strip() or psid

                parts.append(f"{phase}={name}")

            text = "; ".join(parts).strip()
            if not text:
                try:
                    self._subtitle_strategy.hide()
                except Exception:
                    pass
                return

            try:
                self._subtitle_strategy.set_full_text(text)
                set_tooltip(self._subtitle_strategy, text)
                self._subtitle_strategy.show()
            except Exception:
                pass
            return

        if sid == "none":
            try:
                self._subtitle_strategy.hide()
            except Exception:
                pass
            return

        try:
            data = dict(self._strategies_data_by_id.get(sid, {}) or {})
        except Exception:
            data = {}
        name = str(data.get("name") or sid).strip() or sid

        try:
            self._subtitle_strategy.set_full_text(name)
            set_tooltip(self._subtitle_strategy, f"{name}\nID: {sid}")
            self._subtitle_strategy.show()
        except Exception:
            pass

    def show_category(self, category_key: str, category_info, current_strategy_id: str):
        """
        Показывает стратегии для выбранной категории.

        Args:
            category_key: Ключ категории (например, "youtube_https")
            category_info: Объект CategoryInfo с информацией о категории
            current_strategy_id: ID текущей выбранной стратегии
        """
        self._ensure_content_built()

        prev_key = str(self._category_key or "").strip()
        if prev_key:
            self._save_scroll_state(prev_key)

        log(f"StrategyDetailPage.show_category: {category_key}, current={current_strategy_id}", "DEBUG")
        self._category_key = category_key
        self._category_info = category_info
        self._current_strategy_id = current_strategy_id or "none"
        self._selected_strategy_id = self._current_strategy_id
        self._close_preview_dialog(force=True)
        try:
            self._favorite_strategy_ids = self._favorites_store.get_favorites(category_key)
        except Exception:
            self._favorite_strategy_ids = set()

        # Обновляем заголовок (только название категории в breadcrumb)
        self._title.setText(category_info.full_name)
        self._subtitle.setText(
            f"{category_info.protocol}  |  "
            f"{self._tr('page.z2_strategy_detail.subtitle.ports', 'порты: {ports}', ports=category_info.ports)}"
        )
        self._update_selected_strategy_header(self._selected_strategy_id)

        # Sync BreadcrumbBar with the new category
        if self._breadcrumb is not None:
            self._breadcrumb.blockSignals(True)
            try:
                self._breadcrumb.clear()
                self._breadcrumb.addItem("control", self._tr("page.z2_strategy_detail.breadcrumb.control", "Управление"))
                self._breadcrumb.addItem("strategies", self._tr("page.z2_strategy_detail.breadcrumb.strategies", "Стратегии DPI"))
                self._breadcrumb.addItem("detail", category_info.full_name)
            finally:
                self._breadcrumb.blockSignals(False)

        # Determine whether to use the TCP multi-phase UI:
        # - only for TCP strategies (tcp.txt)
        # - only for direct_zapret2 advanced set (no orchestra/zapret1/basic)
        new_strategy_type = str(getattr(category_info, "strategy_type", "") or "tcp").strip().lower()
        is_udp_like_now = self._is_udp_like_category()
        try:
            from strategy_menu.strategies_registry import get_current_strategy_set
            strategy_set = get_current_strategy_set()
        except Exception:
            strategy_set = None
        want_tcp_phase_mode = (
            (new_strategy_type == "tcp")
            and (not is_udp_like_now)
            and (strategy_set in (None, "advanced"))
        )

        self._tcp_phase_mode = bool(want_tcp_phase_mode)
        try:
            if hasattr(self, "_filter_btn") and self._filter_btn is not None:
                self._filter_btn.setVisible(not self._tcp_phase_mode)
        except Exception:
            pass
        try:
            if hasattr(self, "_phases_bar_widget") and self._phases_bar_widget is not None:
                self._phases_bar_widget.setVisible(self._tcp_phase_mode)
        except Exception:
            pass

        # Для категорий одного strategy_type (особенно tcp) список стратегий одинаковый,
        # поэтому не пересобираем виджеты каждый раз: это ускоряет повторные переходы.
        reuse_list = (
            bool(self._strategies_tree and self._strategies_tree.has_rows())
            and self._loaded_strategy_type == new_strategy_type
            and self._loaded_strategy_set == strategy_set
            and bool(self._loaded_tcp_phase_mode) == bool(want_tcp_phase_mode)
        )

        if not reuse_list:
            # Очищаем старые стратегии
            self._clear_strategies()
            # Загружаем новые
            self._load_strategies()
        else:
            # Обновляем избранное для новой категории
            for sid in (self._strategies_tree.get_strategy_ids() if self._strategies_tree else []):
                want_fav = sid in self._favorite_strategy_ids
                self._strategies_tree.set_favorite_state(sid, want_fav)

            # Обновляем отметки working/not working для новой категории
            self._refresh_working_marks_for_category()

            # Обновляем выделение текущей стратегии
            if self._strategies_tree:
                if self._strategies_tree.has_strategy(self._current_strategy_id):
                    self._strategies_tree.set_selected_strategy(self._current_strategy_id)
                elif self._strategies_tree.has_strategy("none"):
                    self._strategies_tree.set_selected_strategy("none")
                else:
                    self._strategies_tree.clearSelection()
            # Восстанавливаем последнюю позицию прокрутки для этой категории.
            self._restore_scroll_state(category_key, defer=True)

        # Обновляем галочку статуса
        is_enabled = self._current_strategy_id != "none"
        self._update_status_icon(is_enabled)

        # Показываем режим фильтрации только если категория поддерживает оба варианта
        has_ipset = hasattr(category_info, 'base_filter_ipset') and category_info.base_filter_ipset
        has_hostlist = hasattr(category_info, 'base_filter_hostlist') and category_info.base_filter_hostlist
        if has_ipset and has_hostlist:
            self._filter_mode_frame.setVisible(True)
            saved_filter_mode = self._load_category_filter_mode(category_key)
            self._filter_mode_selector.blockSignals(True)
            self._filter_mode_selector.setChecked(saved_filter_mode == "ipset")
            self._filter_mode_selector.blockSignals(False)
        else:
            self._filter_mode_frame.setVisible(False)

        # Очищаем поиск и загружаем сохранённую сортировку
        self._search_input.clear()
        self._sort_mode = self._load_category_sort(category_key)

        # Сбрасываем фильтры по технике
        self._active_filters.clear()
        self._update_technique_filter_ui()

        # TCP multi-phase state
        if self._tcp_phase_mode:
            self._load_tcp_phase_state_from_preset()
            self._apply_tcp_phase_tabs_visibility()
            preferred = None
            try:
                preferred = (self._last_active_phase_key_by_category or {}).get(category_key)
            except Exception:
                preferred = None
            if not preferred:
                preferred = self._load_category_last_tcp_phase_tab(category_key)
                if preferred:
                    try:
                        self._last_active_phase_key_by_category[category_key] = preferred
                    except Exception:
                        pass
            if preferred:
                self._set_active_phase_chip(preferred)
            else:
                self._select_default_tcp_phase_tab()

        # Применяем сохранённую сортировку (если не default)
        self._apply_sort()
        self._apply_filters()

        # Загружаем syndata настройки для категории
        syndata_settings = self._load_syndata_settings(category_key)
        self._apply_syndata_settings(syndata_settings)

        # direct_zapret2 Basic: hide advanced Send/Syndata UI without mutating stored settings.
        is_basic_direct = (strategy_set == "basic")

        # syndata/send are supported only for TCP SYN; for UDP/QUIC always hide.
        protocol_raw = str(getattr(category_info, "protocol", "") or "").upper()
        is_udp_like = ("UDP" in protocol_raw) or ("QUIC" in protocol_raw) or ("L7" in protocol_raw)

        if is_basic_direct:
            self._send_frame.setVisible(False)
            self._syndata_frame.setVisible(False)
            try:
                if hasattr(self, "_reset_row_widget") and self._reset_row_widget is not None:
                    self._reset_row_widget.setVisible(False)
            except Exception:
                pass
        elif is_udp_like:
            # Force-off without saving (only affects visual state and subsequent saves)
            # UDP/QUIC: remove send (same limitation as syndata)
            self._send_toggle.blockSignals(True)
            self._send_toggle.setChecked(False)
            self._send_toggle.blockSignals(False)
            self._send_frame.setVisible(False)

            self._syndata_toggle.blockSignals(True)
            self._syndata_toggle.setChecked(False)
            self._syndata_toggle.blockSignals(False)
            self._syndata_frame.setVisible(False)

            try:
                if hasattr(self, "_reset_row_widget") and self._reset_row_widget is not None:
                    self._reset_row_widget.setVisible(True)
            except Exception:
                pass
        else:
            self._send_frame.setVisible(True)
            self._syndata_frame.setVisible(True)
            try:
                if hasattr(self, "_reset_row_widget") and self._reset_row_widget is not None:
                    self._reset_row_widget.setVisible(True)
            except Exception:
                pass

        # Args editor availability depends on whether category is enabled (strategy != none)
        self._refresh_args_editor_state()
        self._set_category_enabled_ui(is_enabled)

        log(f"StrategyDetailPage: показана категория {self._category_key}, sort_mode={self._sort_mode}", "DEBUG")

    def refresh_from_preset_switch(self):
        """
        Асинхронно перечитывает активный пресет и обновляет текущую категорию (если открыта).
        Вызывается из MainWindow после активации пресета.
        """
        try:
            QTimer.singleShot(0, self._apply_preset_refresh)
        except Exception:
            try:
                self._apply_preset_refresh()
            except Exception:
                pass

    def _apply_preset_refresh(self):
        if not self._category_key:
            return

        try:
            from strategy_menu.strategies_registry import registry
            category_info = registry.get_category_info(self._category_key) or self._category_info
        except Exception:
            category_info = self._category_info

        if not category_info:
            return

        try:
            selections = self._preset_manager.get_strategy_selections() or {}
            current_strategy_id = selections.get(self._category_key, "none") or "none"
        except Exception:
            current_strategy_id = "none"

        try:
            self.show_category(self._category_key, category_info, current_strategy_id)
        except Exception:
            return

    def _scroll_to_current_strategy(self) -> None:
        """Прокручивает страницу к текущей стратегии (не меняя порядок списка)."""
        if not self._strategies_tree:
            return

        sid = self._current_strategy_id or "none"
        if sid == "none":
            try:
                bar = self.verticalScrollBar()
                bar.setValue(bar.minimum())
            except Exception:
                pass
            return

        rect = self._strategies_tree.get_strategy_item_rect(sid)
        if rect is None:
            return

        try:
            vp = self._strategies_tree.viewport()
            center = vp.mapTo(self.content, rect.center())
            # ymargin: немного контекста вокруг строки
            self.ensureVisible(center.x(), center.y(), 0, 64)
        except Exception:
            pass

    def _clear_strategies(self):
        """Очищает список стратегий"""
        # Останавливаем ленивую загрузку если она идёт
        self._strategies_load_generation += 1
        if self._strategies_load_timer:
            try:
                self._strategies_load_timer.stop()
                self._strategies_load_timer.deleteLater()
            except Exception:
                pass
            self._strategies_load_timer = None
        self._pending_strategies_items = []
        self._pending_strategies_index = 0

        if self._strategies_tree:
            self._strategies_tree.clear_strategies()
        self._strategies_data_by_id = {}
        self._loaded_strategy_type = None
        self._loaded_strategy_set = None
        self._loaded_tcp_phase_mode = False
        self._default_strategy_order = []
        self._strategies_loaded_fully = False

    def _is_dpi_running_now(self) -> bool:
        """Best-effort check: is any winws process currently running."""
        try:
            controller = getattr(self.parent_app, "dpi_controller", None)
            if controller is not None and hasattr(controller, "is_running"):
                return bool(controller.is_running())
        except Exception:
            pass

        try:
            starter = getattr(self.parent_app, "dpi_starter", None)
            if starter is not None and hasattr(starter, "check_process_running_wmi"):
                return bool(starter.check_process_running_wmi(silent=True))
        except Exception:
            pass

        return False

    def _load_strategies(self):
        """Загружает стратегии для текущей категории"""
        try:
            from strategy_menu.strategies_registry import registry

            # Получаем информацию о категории
            category_info = registry.get_category_info(self._category_key)
            if category_info:
                log(f"StrategyDetailPage: категория {self._category_key}, strategy_type={category_info.strategy_type}", "DEBUG")
            else:
                log(f"StrategyDetailPage: категория {self._category_key} не найдена в реестре!", "ERROR")
                return

            # Получаем стратегии для категории
            strategies = registry.get_category_strategies(self._category_key)
            log(f"StrategyDetailPage: загружено {len(strategies)} стратегий для {self._category_key}", "DEBUG")

            # TCP multi-phase: load additional pure-fake strategies from tcp_fake.txt
            if self._tcp_phase_mode:
                try:
                    from strategy_menu.strategies_registry import get_current_strategy_set
                    from strategy_menu.strategy_loader import load_strategies_as_dict
                    current_set = get_current_strategy_set()
                    fake_set = "advanced" if current_set == "advanced" else None
                    fake_strategies = load_strategies_as_dict("tcp_fake", fake_set)
                except Exception:
                    fake_strategies = {}

                combined = {}
                # Preserve source ordering: tcp_fake.txt first, then tcp.txt
                combined.update(fake_strategies or {})
                combined.update(strategies or {})
                strategies = combined

            self._strategies_data_by_id = dict(strategies or {})
            self._default_strategy_order = list(self._strategies_data_by_id.keys())
            self._loaded_strategy_type = category_info.strategy_type
            
            try:
                from strategy_menu.strategies_registry import get_current_strategy_set
                self._loaded_strategy_set = get_current_strategy_set()
            except Exception:
                self._loaded_strategy_set = None
                
            self._loaded_tcp_phase_mode = self._tcp_phase_mode

            if not strategies:
                try:
                    self._strategies_tree.clear_strategies()
                except Exception:
                    pass
                log(f"StrategyDetailPage: список стратегий пуст для {self._category_key}", "INFO")
                # Fallback display: usually handled by empty list state, but we can stop loading.
                self._stop_loading()
                
                # Попробуем ещё раз через секунду, вдруг стратегии ещё грузятся
                if not hasattr(self, "_retry_count"):
                    self._retry_count = 0
                if self._retry_count < 3:
                    self._retry_count += 1
                    QTimer.singleShot(1000, self._load_strategies)
                else:
                    self._retry_count = 0
                    # Если DPI остановлен, не показываем шумное предупреждение "Нет стратегий".
                    # В этот момент чаще всего идёт смена режима/перезапуск.
                    if (not self._is_dpi_running_now()) or (not self.isVisible()):
                        log(
                            f"StrategyDetailPage: suppress 'no strategies' warning while DPI is stopped ({self._category_key})",
                            "DEBUG",
                        )
                        return

                    if InfoBar:
                        InfoBar.warning(
                            title=self._tr("page.z2_strategy_detail.infobar.no_strategies.title", "Нет стратегий"),
                            content=self._tr(
                                "page.z2_strategy_detail.infobar.no_strategies.content",
                                "Для категории '{category}' не найдено стратегий.",
                                category=self._category_key,
                            ),
                            parent=self.window(),
                        )
                return

            self._retry_count = 0

            # Подготавливаем элементы для ленивой загрузки
            self._pending_strategies_items = []
            
            # --- TCP phase mode ---
            if self._tcp_phase_mode:
                # В этом режиме всегда есть пункт "(без изменений)"
                self._pending_strategies_items.append({
                    'id': "none",
                    'name': self._tr("page.z2_strategy_detail.tree.phase.none.name", "(без изменений)"),
                    'desc': self._tr(
                        "page.z2_strategy_detail.tree.phase.none.desc",
                        "Снять отметку со стратегии (фаза будет пропущена)",
                    ),
                    'arg_str': "--new",
                    'is_custom': False
                })
                # И пункт "(custom_args...)"
                self._pending_strategies_items.append({
                    'id': CUSTOM_STRATEGY_ID,
                    'name': self._tr("page.z2_strategy_detail.tree.phase.custom.name", "Пользовательские аргументы (custom)"),
                    'desc': self._tr(
                        "page.z2_strategy_detail.tree.phase.custom.desc",
                        "Неизвестные аргументы, загруженные из профиля",
                    ),
                    'arg_str': "...",
                    'is_custom': True
                })

                for sid, data in strategies.items():
                    name = str(data.get("name", sid)).strip() or sid
                    desc = str(data.get("desc", ""))
                    arg_str = str(data.get("arg_str", ""))
                    # TCP auto-assign phase logic could go here; tree applies it
                    self._pending_strategies_items.append({
                        'id': sid,
                        'name': name,
                        'desc': desc,
                        'arg_str': arg_str,
                        'is_custom': False
                    })
                    
            # --- Звичайна загрузка ---
            else:
                self._pending_strategies_items.append({
                    'id': "none",
                    'name': self._tr("page.z2_strategy_detail.tree.disabled.name", "Выключено (без DPI-обхода)"),
                    'desc': self._tr(
                        "page.z2_strategy_detail.tree.disabled.desc",
                        "Трафик пускается напрямую без модификаций",
                    ),
                    'arg_str': ""
                })

                for sid, data in strategies.items():
                    name = data.get("name", sid)
                    desc = data.get("desc", "")
                    arg_str = data.get("arg_str", "")
                    self._pending_strategies_items.append({
                        'id': sid,
                        'name': name,
                        'desc': desc,
                        'arg_str': arg_str
                    })

            self._pending_strategies_index = 0
            self._strategies_loaded_fully = False

            # Запускаем пакетную загрузку
            self._strategies_load_generation += 1
            if self._strategies_load_timer is None:
                self._strategies_load_timer = QTimer(self)
                self._strategies_load_timer.timeout.connect(self._load_next_strategies_batch)
            self._strategies_load_timer.start(5) # Быстрая подгрузка батчами
            
        except Exception as e:
            log(f"StrategyDetailPage.error loading strategies: {e}", "ERROR")
            self._stop_loading()

    def _extract_args_lines_for_pending_item(self, strategy_id: str, item_data: dict) -> list[str]:
        """Builds args list for a row from cached strategy data or pending item payload."""
        source = None

        try:
            data = dict(self._strategies_data_by_id.get(strategy_id, {}) or {})
        except Exception:
            data = {}

        if data:
            source = data.get("args")
            if source in (None, "", []):
                source = data.get("arg_str")

        if source in (None, "", []):
            try:
                source = (item_data or {}).get("arg_str")
            except Exception:
                source = None

        if isinstance(source, (list, tuple)):
            return [str(v).strip() for v in source if str(v).strip()]

        text = str(source or "").strip()
        if not text:
            return []
        if "\n" in text:
            return [ln.strip() for ln in text.splitlines() if ln.strip()]
        if text.startswith("--"):
            return [part.strip() for part in text.split() if part.strip()]
        return [text]

    def _add_strategy_row(self, strategy_id: str, name: str, args: list[str] | None = None) -> None:
        if not self._strategies_tree:
            return

        args_list = [str(a).strip() for a in (args or []) if str(a).strip()]
        is_favorite = (strategy_id != "none") and (strategy_id in self._favorite_strategy_ids)
        is_working = None
        if self._category_key and strategy_id not in ("none", CUSTOM_STRATEGY_ID):
            try:
                is_working = self._marks_store.get_mark(self._category_key, strategy_id)
            except Exception:
                is_working = None

        try:
            self._strategies_tree.add_strategy(
                StrategyTreeRow(
                    strategy_id=strategy_id,
                    name=name,
                    args=args_list,
                    is_favorite=is_favorite,
                    is_working=is_working,
                )
            )
        except Exception as e:
            log(f"Strategy row add failed for {strategy_id}: {e}", "DEBUG")

    def _load_next_strategies_batch(self) -> None:
        """Lazily appends strategies to the tree in small UI-friendly chunks."""
        if not self._strategies_tree:
            return

        total = len(self._pending_strategies_items or [])
        if total <= 0:
            if self._strategies_load_timer:
                self._strategies_load_timer.stop()
            self._strategies_loaded_fully = True
            return

        start = int(self._pending_strategies_index or 0)
        if start >= total:
            if self._strategies_load_timer:
                self._strategies_load_timer.stop()
            self._strategies_loaded_fully = True
            return

        chunk_size = 32
        end = min(start + chunk_size, total)

        try:
            self._strategies_tree.setUpdatesEnabled(False)
            for i in range(start, end):
                item = self._pending_strategies_items[i]
                strategy_id = str((item or {}).get("id") or "").strip()
                if not strategy_id:
                    continue
                name = str((item or {}).get("name") or strategy_id).strip() or strategy_id
                args_list = self._extract_args_lines_for_pending_item(strategy_id, item)
                self._add_strategy_row(strategy_id, name, args_list)
        finally:
            try:
                self._strategies_tree.setUpdatesEnabled(True)
            except Exception:
                pass

        self._pending_strategies_index = end

        try:
            search_active = bool(self._search_input and self._search_input.text().strip())
        except Exception:
            search_active = False
        if search_active or self._active_filters or self._tcp_phase_mode:
            self._apply_filters()

        if end < total:
            return

        # Finished loading all rows.
        if self._strategies_load_timer:
            try:
                self._strategies_load_timer.stop()
            except Exception:
                pass

        self._strategies_loaded_fully = True
        self._refresh_working_marks_for_category()
        self._apply_sort()

        if self._tcp_phase_mode:
            self._sync_tree_selection_to_active_phase()
        else:
            if self._strategies_tree.has_strategy(self._current_strategy_id):
                self._strategies_tree.set_selected_strategy(self._current_strategy_id)
            elif self._strategies_tree.has_strategy("none"):
                self._strategies_tree.set_selected_strategy("none")

        self._refresh_scroll_range()
        self._restore_scroll_state(self._category_key, defer=True)

    def _refresh_working_marks_for_category(self) -> None:
        if not (self._category_key and self._strategies_tree):
            return
        for strategy_id in self._strategies_tree.get_strategy_ids():
            if strategy_id in ("none", CUSTOM_STRATEGY_ID):
                continue
            try:
                self._strategies_tree.set_working_state(
                    strategy_id, self._marks_store.get_mark(self._category_key, strategy_id)
                )
            except Exception:
                pass

    def _get_preview_strategy_data(self, strategy_id: str) -> dict:
        data = dict(self._strategies_data_by_id.get(strategy_id, {}) or {})
        if "name" not in data:
            data["name"] = strategy_id

        args = data.get("args", [])
        if isinstance(args, str):
            args_text = args
        elif isinstance(args, (list, tuple)):
            args_text = "\n".join([str(a) for a in args if a is not None]).strip()
        else:
            args_text = ""
        data["args"] = args_text
        return data

    def _get_preview_rating(self, strategy_id: str, category_key: str):
        if not (category_key and strategy_id and strategy_id != "none"):
            return None
        try:
            mark = self._marks_store.get_mark(category_key, strategy_id)
        except Exception:
            return None
        if mark is True:
            return "working"
        if mark is False:
            return "broken"
        return None

    def _toggle_preview_rating(self, strategy_id: str, rating: str, category_key: str):
        if not (category_key and strategy_id and strategy_id != "none"):
            return None
        current = None
        try:
            current = self._marks_store.get_mark(category_key, strategy_id)
        except Exception:
            current = None

        if rating == "working":
            new_state = None if current is True else True
        elif rating == "broken":
            new_state = None if current is False else False
        else:
            new_state = None

        try:
            self._marks_store.set_mark(category_key, strategy_id, new_state)
        except Exception as e:
            log(f"Error saving strategy mark (preview): {e}", "WARNING")
            return self._get_preview_rating(strategy_id, category_key)

        if self._strategies_tree:
            self._strategies_tree.set_working_state(strategy_id, new_state)

        if new_state is True:
            return "working"
        if new_state is False:
            return "broken"
        return None

    def _close_preview_dialog(self, force: bool = False):
        if self._preview_dialog is None:
            return
        if (not force) and self._preview_pinned:
            return
        try:
            self._preview_dialog.close_dialog()
        except Exception:
            try:
                self._preview_dialog.close()
            except Exception:
                pass
        self._preview_dialog = None
        self._preview_pinned = False

    def _on_preview_closed(self) -> None:
        self._preview_dialog = None
        self._preview_pinned = False

    def _ensure_preview_dialog(self):
        dlg = self._preview_dialog
        if dlg is not None:
            try:
                dlg.isVisible()
                return dlg
            except RuntimeError:
                self._preview_dialog = None
            except Exception:
                return dlg

        parent_win = self._main_window or self.window() or self
        try:
            dlg = ArgsPreviewDialog(parent_win)
            dlg.closed.connect(self._on_preview_closed)
            self._preview_dialog = dlg
            return dlg
        except Exception:
            self._preview_dialog = None
            return None

    @staticmethod
    def _to_qpoint(global_pos):
        try:
            return global_pos.toPoint()
        except Exception:
            return global_pos

    def _show_preview_dialog(self, strategy_id: str, global_pos) -> None:
        if not (self._category_key and strategy_id and strategy_id != "none"):
            return

        data = self._get_preview_strategy_data(strategy_id)

        try:
            dlg = self._ensure_preview_dialog()
            if dlg is None:
                return

            dlg.set_strategy_data(
                data,
                strategy_id=strategy_id,
                category_key=self._category_key,
                rating_getter=self._get_preview_rating,
                rating_toggler=self._toggle_preview_rating,
            )

            dlg.show_animated(self._to_qpoint(global_pos))
        except Exception as e:
            log(f"Preview dialog failed: {e}", "DEBUG")

    def _on_tree_preview_requested(self, strategy_id: str, global_pos):
        pass  # Hover preview is intentionally disabled.

    def _on_tree_preview_pinned_requested(self, strategy_id: str, global_pos):
        self._show_preview_dialog(strategy_id, global_pos)

    def _on_tree_preview_hide_requested(self) -> None:
        pass  # No hover preview instance to hide.

    def _on_tree_working_mark_requested(self, strategy_id: str, is_working):
        if not (self._category_key and strategy_id and strategy_id != "none"):
            return
        self._on_strategy_marked(strategy_id, is_working)
        if self._strategies_tree:
            self._strategies_tree.set_working_state(strategy_id, is_working)

    def _on_strategy_marked(self, strategy_id: str, is_working):
        if not self._category_key:
            return

        try:
            if strategy_id and strategy_id != "none":
                self._marks_store.set_mark(self._category_key, strategy_id, is_working)
        except Exception as e:
            log(f"Error saving strategy mark: {e}", "WARNING")

        self.strategy_marked.emit(self._category_key, strategy_id, is_working)

    def _apply_syndata_settings(self, settings: dict):
        """Applies persisted syndata settings to controls without re-saving."""
        data = dict(settings or {})
        try:
            self._syndata_toggle.blockSignals(True)
            self._blob_combo.blockSignals(True)
            self._tls_mod_combo.blockSignals(True)
            self._out_range_spin.blockSignals(True)
            self._tcp_flags_combo.blockSignals(True)
            self._send_toggle.blockSignals(True)
            self._send_repeats_spin.blockSignals(True)
            self._send_ip_id_combo.blockSignals(True)
            self._send_badsum_check.blockSignals(True)

            self._syndata_toggle.setChecked(bool(data.get("enabled", False)))
            self._syndata_settings.setVisible(bool(data.get("enabled", False)))

            blob_value = str(data.get("blob", "none") or "none")
            blob_index = self._blob_combo.findText(blob_value)
            if blob_index >= 0:
                self._blob_combo.setCurrentIndex(blob_index)

            tls_mod_value = str(data.get("tls_mod", "none") or "none")
            tls_mod_index = self._tls_mod_combo.findText(tls_mod_value)
            if tls_mod_index >= 0:
                self._tls_mod_combo.setCurrentIndex(tls_mod_index)

            self._autottl_delta_selector.setValue(int(data.get("autottl_delta", -2)), block_signals=True)
            self._autottl_min_selector.setValue(int(data.get("autottl_min", 3)), block_signals=True)
            self._autottl_max_selector.setValue(int(data.get("autottl_max", 20)), block_signals=True)
            self._out_range_spin.setValue(int(data.get("out_range", 8)))

            self._out_range_mode = str(data.get("out_range_mode", "n") or "n")
            try:
                self._out_range_seg.setCurrentItem(self._out_range_mode)
            except Exception:
                pass

            tcp_flags_value = str(data.get("tcp_flags_unset", "none") or "none")
            tcp_flags_index = self._tcp_flags_combo.findText(tcp_flags_value)
            if tcp_flags_index >= 0:
                self._tcp_flags_combo.setCurrentIndex(tcp_flags_index)

            self._send_toggle.setChecked(bool(data.get("send_enabled", False)))
            self._send_settings.setVisible(bool(data.get("send_enabled", False)))
            self._send_repeats_spin.setValue(int(data.get("send_repeats", 2)))
            self._send_ip_ttl_selector.setValue(int(data.get("send_ip_ttl", 0)), block_signals=True)
            self._send_ip6_ttl_selector.setValue(int(data.get("send_ip6_ttl", 0)), block_signals=True)

            send_ip_id = str(data.get("send_ip_id", "none") or "none")
            send_ip_id_index = self._send_ip_id_combo.findText(send_ip_id)
            if send_ip_id_index >= 0:
                self._send_ip_id_combo.setCurrentIndex(send_ip_id_index)

            self._send_badsum_check.setChecked(bool(data.get("send_badsum", False)))
        finally:
            try:
                self._syndata_toggle.blockSignals(False)
                self._blob_combo.blockSignals(False)
                self._tls_mod_combo.blockSignals(False)
                self._out_range_spin.blockSignals(False)
                self._tcp_flags_combo.blockSignals(False)
                self._send_toggle.blockSignals(False)
                self._send_repeats_spin.blockSignals(False)
                self._send_ip_id_combo.blockSignals(False)
                self._send_badsum_check.blockSignals(False)
            except Exception:
                pass

    def _schedule_full_repopulate(self) -> None:
        """Compatibility helper for old sort modes; keep list state consistent."""
        try:
            QTimer.singleShot(0, self._apply_sort)
            QTimer.singleShot(0, self._apply_filters)
        except Exception:
            pass


    def get_syndata_settings(self) -> dict:
        """Возвращает текущие syndata настройки для использования в командной строке"""
        return {
            "enabled": self._syndata_toggle.isChecked(),
            "blob": self._blob_combo.currentText(),
            "tls_mod": self._tls_mod_combo.currentText(),
        }

    # ======================================================================
    # PRESET CREATE / RENAME
    # ======================================================================

    def _on_create_preset_clicked(self):
        """Открывает WinUI-диалог создания нового пресета."""
        try:
            from core.presets.direct_facade import DirectPresetFacade
            from preset_zapret2.preset_store import get_preset_store

            facade = DirectPresetFacade.from_launch_method("direct_zapret2")
            store = get_preset_store()
        except Exception as e:
            if InfoBar:
                InfoBar.error(
                    title=self._tr("common.error.title", "Ошибка"),
                    content=str(e),
                    parent=self.window(),
                )
            return

        dialog = _PresetNameDialog("create", parent=self.window(), language=self._ui_language)
        if not dialog.exec():
            return
        name = dialog.get_name()
        if not name:
            return
        try:
            if facade.exists(name):
                if InfoBar:
                    InfoBar.warning(
                        title=self._tr("page.z2_strategy_detail.infobar.preset.exists.title", "Уже существует"),
                        content=self._tr(
                            "page.z2_strategy_detail.infobar.preset.exists.content",
                            "Пресет '{name}' уже существует.",
                            name=name,
                        ),
                        parent=self.window(),
                    )
                return
            facade.create(name, from_current=True)
            store.notify_presets_changed()
            log(f"Создан пресет '{name}'", "INFO")
            if InfoBar:
                InfoBar.success(
                    title=self._tr("page.z2_strategy_detail.infobar.preset.created.title", "Пресет создан"),
                    content=self._tr(
                        "page.z2_strategy_detail.infobar.preset.created.content",
                        "Пресет '{name}' создан на основе текущих настроек.",
                        name=name,
                    ),
                    parent=self.window(),
                )
        except Exception as e:
            log(f"Ошибка создания пресета: {e}", "ERROR")
            if InfoBar:
                InfoBar.error(
                    title=self._tr("common.error.title", "Ошибка"),
                    content=str(e),
                    parent=self.window(),
                )

    def _on_rename_preset_clicked(self):
        """Открывает WinUI-диалог переименования текущего активного пресета."""
        try:
            from core.presets.direct_facade import DirectPresetFacade
            from core.services import get_direct_flow_coordinator
            from preset_zapret2.preset_store import get_preset_store

            facade = DirectPresetFacade.from_launch_method("direct_zapret2")
            store = get_preset_store()

            old_name = (
                get_direct_flow_coordinator().get_selected_preset_name("direct_zapret2") or ""
            ).strip()
        except Exception as e:
            if InfoBar:
                InfoBar.error(
                    title=self._tr("common.error.title", "Ошибка"),
                    content=str(e),
                    parent=self.window(),
                )
            return

        if not old_name:
            if InfoBar:
                InfoBar.warning(
                    title=self._tr("page.z2_strategy_detail.infobar.preset.no_active.title", "Нет активного пресета"),
                    content=self._tr(
                        "page.z2_strategy_detail.infobar.preset.no_active.content",
                        "Активный пресет не найден.",
                    ),
                    parent=self.window(),
                )
            return

        dialog = _PresetNameDialog("rename", old_name=old_name, parent=self.window(), language=self._ui_language)
        if not dialog.exec():
            return
        new_name = dialog.get_name()
        if not new_name or new_name == old_name:
            return
        try:
            if facade.exists(new_name):
                if InfoBar:
                    InfoBar.warning(
                        title=self._tr("page.z2_strategy_detail.infobar.preset.exists.title", "Уже существует"),
                        content=self._tr(
                            "page.z2_strategy_detail.infobar.preset.exists.content",
                            "Пресет '{name}' уже существует.",
                            name=new_name,
                        ),
                        parent=self.window(),
                    )
                return
            facade.rename(old_name, new_name)
            store.notify_presets_changed()
            if facade.is_selected(new_name):
                store.notify_preset_switched(new_name)
            log(f"Пресет '{old_name}' переименован в '{new_name}'", "INFO")
            if InfoBar:
                InfoBar.success(
                    title=self._tr("page.z2_strategy_detail.infobar.preset.renamed.title", "Переименован"),
                    content=self._tr(
                        "page.z2_strategy_detail.infobar.preset.renamed.content",
                        "Пресет переименован: '{old}' -> '{new}'.",
                        old=old_name,
                        new=new_name,
                    ),
                    parent=self.window(),
                )
        except Exception as e:
            log(f"Ошибка переименования пресета: {e}", "ERROR")
            if InfoBar:
                InfoBar.error(
                    title=self._tr("common.error.title", "Ошибка"),
                    content=str(e),
                    parent=self.window(),
                )

    def _on_reset_settings_confirmed(self):
        """Сбрасывает настройки категории на значения по умолчанию (встроенный шаблон)"""
        if not self._category_key:
            return

        # 1. Reset via PresetManager (saves to preset file)
        if self._preset_manager.reset_category_settings(self._category_key):
            log(f"Настройки категории {self._category_key} сброшены", "INFO")

            # 2. Reload settings from PresetManager and apply to UI
            protocol_raw = str(getattr(self._category_info, "protocol", "") or "").upper()
            is_udp_like = ("UDP" in protocol_raw) or ("QUIC" in protocol_raw) or ("L7" in protocol_raw)
            protocol_key = "udp" if is_udp_like else "tcp"
            syndata = self._preset_manager.get_category_syndata(self._category_key, protocol=protocol_key)
            self._apply_syndata_settings(syndata.to_dict())

            # 3. Reset filter_mode selector to stored default
            if hasattr(self, '_filter_mode_frame') and self._filter_mode_frame.isVisible():
                current_mode = self._preset_manager.get_category_filter_mode(self._category_key)
                self._filter_mode_selector.blockSignals(True)
                self._filter_mode_selector.setChecked(current_mode == "ipset")
                self._filter_mode_selector.blockSignals(False)

            # 4. Update selected strategy highlight and enable toggle
            try:
                current_strategy_id = self._preset_manager.get_strategy_selections().get(self._category_key, "none")
            except Exception:
                current_strategy_id = "none"

            self._selected_strategy_id = current_strategy_id or "none"
            self._current_strategy_id = current_strategy_id or "none"

            if self._tcp_phase_mode:
                self._load_tcp_phase_state_from_preset()
                self._apply_tcp_phase_tabs_visibility()
                self._select_default_tcp_phase_tab()
                self._apply_filters()
            else:
                if self._strategies_tree:
                    if self._selected_strategy_id != "none":
                        self._strategies_tree.set_selected_strategy(self._selected_strategy_id)
                    elif self._strategies_tree.has_strategy("none"):
                        self._strategies_tree.set_selected_strategy("none")
                    else:
                        self._strategies_tree.clearSelection()

            # Reset writes the preset to disk and triggers the same hot-reload/restart
            # path as any other setting change, so show the spinner.
            self.show_loading()
            self._update_selected_strategy_header(self._selected_strategy_id)
            self._refresh_args_editor_state()
            self._set_category_enabled_ui((self._selected_strategy_id or "none") != "none")

    def _on_row_clicked(self, strategy_id: str):
        """Обработчик клика по строке стратегии - выбор активной"""
        if self._tcp_phase_mode:
            self._on_tcp_phase_row_clicked(strategy_id)
            return

        prev_strategy_id = self._selected_strategy_id

        # Remember last strategy before switching to "none"
        if strategy_id == "none" and prev_strategy_id and prev_strategy_id != "none":
            self._last_enabled_strategy_id = prev_strategy_id

        self._selected_strategy_id = strategy_id
        if self._strategies_tree:
            self._strategies_tree.set_selected_strategy(strategy_id)
        self._update_selected_strategy_header(self._selected_strategy_id)

        # При смене стратегии закрываем редактор args (чтобы не редактировать "не то")
        if prev_strategy_id != strategy_id:
            self._hide_args_editor(clear_text=False)

        if strategy_id != "none":
            # Показываем анимацию загрузки
            self.show_loading()
        else:
            self._stop_loading()
            self._success_icon.hide()

        self._refresh_args_editor_state()
        self._set_category_enabled_ui((strategy_id or "none") != "none")

        # Применяем стратегию (но остаёмся на странице)
        if self._category_key:
            self.strategy_selected.emit(self._category_key, strategy_id)

    def _update_status_icon(self, active: bool):
        """Обновляет галочку статуса в заголовке"""
        if active:
            self.show_success()
        else:
            self._stop_loading()
            self._success_icon.hide()

    def show_loading(self):
        """Показывает анимированный спиннер загрузки"""
        self._success_icon.hide()
        self._spinner.show()
        self._spinner.start()
        self._waiting_for_process_start = True  # Ждём запуска DPI
        # Убедимся, что мы подключены к process_monitor
        if not self._process_monitor_connected:
            self._connect_process_monitor()
        # В direct_zapret2 режимах "apply" часто не меняет состояние процесса (hot-reload),
        # поэтому даём быстрый таймаут, чтобы UI не зависал на спиннере.
        self._start_apply_feedback_timer()
        # Запускаем fallback таймер на случай если сигнал не придет
        self._start_fallback_timer()

    def _stop_loading(self):
        """Останавливает анимацию загрузки"""
        self._spinner.stop()
        self._spinner.hide()
        self._waiting_for_process_start = False  # Больше не ждём
        self._stop_apply_feedback_timer()
        self._stop_fallback_timer()

    def _start_apply_feedback_timer(self, timeout_ms: int = 1500):
        """Быстрый таймер, который завершает спиннер после apply/hot-reload."""
        self._stop_apply_feedback_timer()
        self._apply_feedback_timer = QTimer(self)
        self._apply_feedback_timer.setSingleShot(True)
        self._apply_feedback_timer.timeout.connect(self._on_apply_feedback_timeout)
        self._apply_feedback_timer.start(timeout_ms)

    def _stop_apply_feedback_timer(self):
        if self._apply_feedback_timer:
            self._apply_feedback_timer.stop()
            self._apply_feedback_timer = None

    def _on_apply_feedback_timeout(self):
        """
        В direct_zapret2 изменения часто применяются без смены процесса (winws2 остаётся запущен),
        поэтому ориентируемся на включенность категории, а не на processStatusChanged.
        """
        if not self._waiting_for_process_start:
            return
        if (self._selected_strategy_id or "none") != "none":
            self.show_success()
        else:
            self._stop_loading()
            self._success_icon.hide()

    def _start_fallback_timer(self):
        """Запускает fallback таймер для защиты от бесконечного спиннера"""
        self._stop_fallback_timer()  # Остановим предыдущий если был
        self._fallback_timer = QTimer(self)
        self._fallback_timer.setSingleShot(True)
        self._fallback_timer.timeout.connect(self._on_fallback_timeout)
        self._fallback_timer.start(10000)  # 10 секунд максимум

    def _stop_fallback_timer(self):
        """Останавливает fallback таймер"""
        if self._fallback_timer:
            self._fallback_timer.stop()
            self._fallback_timer = None

    def _on_fallback_timeout(self):
        """Вызывается если сигнал processStatusChanged не пришел за 10 секунд"""
        if self._waiting_for_process_start:
            log("StrategyDetailPage: fallback timeout - показываем галочку", "DEBUG")
            self.show_success()

    def show_success(self):
        """Показывает зелёную галочку успеха"""
        self._stop_loading()
        self._success_icon.setPixmap(qta.icon('fa5s.check-circle', color='#4ade80').pixmap(16, 16))
        self._success_icon.show()

    def _connect_process_monitor(self):
        """Подключается к сигналу processStatusChanged от ProcessMonitorThread"""
        if self._process_monitor_connected:
            return  # Уже подключены

        try:
            if self.parent_app and hasattr(self.parent_app, 'process_monitor'):
                process_monitor = self.parent_app.process_monitor
                if process_monitor is not None:
                    process_monitor.processStatusChanged.connect(self._on_process_status_changed)
                    self._process_monitor_connected = True
                    log("StrategyDetailPage: подключен к processStatusChanged", "DEBUG")
        except Exception as e:
            log(f"StrategyDetailPage: ошибка подключения к process_monitor: {e}", "DEBUG")

    def _on_process_status_changed(self, is_running: bool):
        """
        Обработчик изменения статуса процесса DPI.
        Вызывается когда winws.exe/winws2.exe запускается или останавливается.
        """
        try:
            if is_running and self._waiting_for_process_start:
                # DPI запустился и мы ждали этого - показываем галочку
                log("StrategyDetailPage: DPI запущен, показываем галочку", "DEBUG")
                self.show_success()
        except Exception as e:
            log(f"StrategyDetailPage._on_process_status_changed error: {e}", "DEBUG")

    def _on_args_changed(self, strategy_id: str, args: list):
        """Обработчик изменения аргументов стратегии"""
        if self._category_key:
            self.args_changed.emit(self._category_key, strategy_id, args)
            log(f"Args changed: {self._category_key}/{strategy_id} = {args}", "DEBUG")

    def _is_udp_like_category(self) -> bool:
        protocol_raw = str(getattr(self._category_info, "protocol", "") or "").upper()
        return ("UDP" in protocol_raw) or ("QUIC" in protocol_raw) or ("L7" in protocol_raw)

    # ======================================================================
    # TCP MULTI-PHASE (direct_zapret2)
    # ======================================================================

    def _get_category_strategy_args_text(self) -> str:
        """Returns the stored strategy args (tcp_args/udp_args) for the current category."""
        if not self._category_key:
            return ""
        try:
            preset = self._preset_manager.get_active_preset()
            cat = preset.categories.get(self._category_key) if preset else None
            if not cat:
                return ""
            return cat.udp_args if self._is_udp_like_category() else cat.tcp_args
        except Exception:
            return ""

    def _get_strategy_args_text_by_id(self, strategy_id: str) -> str:
        data = dict(self._strategies_data_by_id.get(strategy_id, {}) or {})
        args = data.get("args", "")
        if isinstance(args, (list, tuple)):
            args = "\n".join([str(a) for a in args if a is not None])
        return _normalize_args_text(str(args or ""))

    def _infer_strategy_id_from_args_exact(self, args_text: str) -> str:
        """
        Best-effort exact match against loaded strategies.

        Returns:
            - matching strategy_id if found
            - "custom" if args are non-empty but don't match a single known strategy
            - "none" if args are empty
        """
        normalized = _normalize_args_text(args_text)
        if not normalized:
            return "none"

        for sid, data in (self._strategies_data_by_id or {}).items():
            if not sid or sid in ("none", TCP_FAKE_DISABLED_STRATEGY_ID):
                continue
            args_val = (data or {}).get("args") if isinstance(data, dict) else ""
            if isinstance(args_val, (list, tuple)):
                args_val = "\n".join([str(a) for a in args_val if a is not None])
            candidate = _normalize_args_text(str(args_val or ""))
            if candidate and candidate == normalized:
                return sid

        return CUSTOM_STRATEGY_ID

    def _extract_desync_techniques_from_args(self, args_text: str) -> list[str]:
        out: list[str] = []
        for raw in (args_text or "").splitlines():
            line = raw.strip()
            if not line or not line.startswith("--"):
                continue
            tech = _extract_desync_technique_from_arg(line)
            if tech:
                out.append(tech)
        return out

    def _infer_tcp_phase_key_for_strategy_args(self, args_text: str) -> str | None:
        """
        Returns a single phase key if all desync lines belong to the same phase.
        Otherwise returns None (multi-phase/unknown).
        """
        phase_keys: set[str] = set()
        for tech in self._extract_desync_techniques_from_args(args_text):
            phase = _map_desync_technique_to_tcp_phase(tech)
            if phase:
                phase_keys.add(phase)
        if len(phase_keys) == 1:
            return next(iter(phase_keys))
        return None

    def _is_tcp_phase_active_for_ui(self, phase_key: str) -> bool:
        """
        Phase is considered "active" when it contributes something to the args chain.

        - fake=disabled is NOT active
        - custom is active only if it has non-empty args chunk
        """
        key = str(phase_key or "").strip().lower()
        if not key:
            return False

        sid = (self._tcp_phase_selected_ids.get(key) or "").strip()
        if not sid or sid == "none":
            return False

        if key == "fake" and sid == TCP_FAKE_DISABLED_STRATEGY_ID:
            return False

        if sid == CUSTOM_STRATEGY_ID:
            chunk = _normalize_args_text(self._tcp_phase_custom_args.get(key, ""))
            return bool(chunk)

        return True

    def _update_tcp_phase_chip_markers(self) -> None:
        """
        Highlights all active phases (even when not currently selected).

        In the tab UI, this is implemented by cyan tab text for active phases.
        """
        if not self._tcp_phase_mode:
            return

        tabbar = self._phase_tabbar
        if not tabbar:
            return

        # Update Pivot item text: prefix with "●" for active phases.
        _label_map = {pk: lbl for pk, lbl in TCP_PHASE_TAB_ORDER}
        for key in (self._phase_tab_index_by_key or {}).keys():
            try:
                is_active = bool(self._is_tcp_phase_active_for_ui(key))
            except Exception:
                is_active = False
            try:
                item = (tabbar.items or {}).get(key)
                if item is None:
                    continue
                orig = _label_map.get(key, key.upper())
                new_text = f"● {orig}" if is_active else orig
                if item.text() != new_text:
                    item.setText(new_text)
                    item.adjustSize()
            except Exception:
                pass

    def _load_tcp_phase_state_from_preset(self) -> None:
        """Parses current tcp_args into phase selections (best-effort)."""
        self._tcp_phase_selected_ids = {}
        self._tcp_phase_custom_args = {}
        self._tcp_hide_fake_phase = False

        if not (self._tcp_phase_mode and self._category_key):
            return

        args_text = self._get_category_strategy_args_text()
        args_norm = _normalize_args_text(args_text)
        if not args_norm:
            # Default: fake disabled, no other phases selected.
            self._tcp_phase_selected_ids["fake"] = TCP_FAKE_DISABLED_STRATEGY_ID
            self._update_selected_strategy_header(self._selected_strategy_id)
            self._update_tcp_phase_chip_markers()
            return

        # Split current args into phase chunks (keep line order).
        phase_lines: dict[str, list[str]] = {k: [] for k in TCP_PHASE_COMMAND_ORDER}
        for raw in args_norm.splitlines():
            line = raw.strip()
            if not line or line == "--new":
                continue
            tech = _extract_desync_technique_from_arg(line)
            if not tech:
                continue
            if tech in TCP_EMBEDDED_FAKE_TECHNIQUES:
                self._tcp_hide_fake_phase = True
            phase = _map_desync_technique_to_tcp_phase(tech)
            if not phase:
                continue
            phase_lines.setdefault(phase, []).append(line)

        phase_chunks = {k: _normalize_args_text("\n".join(v)) for k, v in phase_lines.items() if v}

        # Build reverse lookup: (phase_key, normalized_args) -> strategy_id
        lookup: dict[str, dict[str, str]] = {k: {} for k in TCP_PHASE_COMMAND_ORDER}
        for sid, data in (self._strategies_data_by_id or {}).items():
            if not sid or sid == TCP_FAKE_DISABLED_STRATEGY_ID:
                continue
            args_val = (data or {}).get("args") if isinstance(data, dict) else ""
            if isinstance(args_val, (list, tuple)):
                args_val = "\n".join([str(a) for a in args_val if a is not None])
            s_args = _normalize_args_text(str(args_val or ""))
            if not s_args:
                continue
            phase_key = self._infer_tcp_phase_key_for_strategy_args(s_args)
            if not phase_key:
                continue
            # Keep first occurrence if duplicates exist.
            if s_args not in lookup.get(phase_key, {}):
                lookup.setdefault(phase_key, {})[s_args] = sid

        # Fake defaults to disabled if there is no explicit fake chunk.
        if "fake" not in phase_chunks:
            self._tcp_phase_selected_ids["fake"] = TCP_FAKE_DISABLED_STRATEGY_ID

        for phase_key, chunk in phase_chunks.items():
            if phase_key not in TCP_PHASE_COMMAND_ORDER:
                continue
            found = lookup.get(phase_key, {}).get(chunk)
            if found:
                self._tcp_phase_selected_ids[phase_key] = found
            else:
                self._tcp_phase_selected_ids[phase_key] = CUSTOM_STRATEGY_ID
                self._tcp_phase_custom_args[phase_key] = chunk

        self._update_selected_strategy_header(self._selected_strategy_id)
        self._update_tcp_phase_chip_markers()

    def _apply_tcp_phase_tabs_visibility(self) -> None:
        """Shows/hides the FAKE phase tab depending on selected main techniques."""
        if not self._tcp_phase_mode:
            return

        hide_fake = bool(self._tcp_hide_fake_phase)
        try:
            pivot = self._phase_tabbar
            if pivot is not None:
                fake_item = (pivot.items or {}).get("fake")
                if fake_item is not None:
                    fake_item.setVisible(not hide_fake)
        except Exception:
            pass

        if hide_fake and (self._active_phase_key or "") == "fake":
            self._set_active_phase_chip("multisplit")
            try:
                self._apply_filters()
            except Exception:
                pass

    def _set_active_phase_chip(self, phase_key: str) -> None:
        """Selects a phase tab programmatically without firing user side effects twice."""
        key = str(phase_key or "").strip().lower()
        if not (self._tcp_phase_mode and key and key in (self._phase_tab_index_by_key or {})):
            return

        pivot = self._phase_tabbar
        if not pivot:
            return

        # If the item is hidden (fake tab), fall back to multisplit.
        try:
            item = (pivot.items or {}).get(key)
            if item is None or not item.isVisible():
                key = "multisplit"
        except Exception:
            key = "multisplit"

        if key not in (getattr(pivot, "items", {}) or {}):
            return

        try:
            pivot.blockSignals(True)
            pivot.setCurrentItem(key)
        except Exception:
            pass
        finally:
            try:
                pivot.blockSignals(False)
            except Exception:
                pass

        self._active_phase_key = key

    def _select_default_tcp_phase_tab(self) -> None:
        """Chooses the initial active tab for TCP phase UI."""
        if not self._tcp_phase_mode:
            return

        # Prefer a main phase that is currently selected.
        preferred = None
        for k in ("multisplit", "multidisorder", "multidisorder_legacy", "tcpseg", "oob", "other"):
            sid = (self._tcp_phase_selected_ids.get(k) or "").strip()
            if sid:
                preferred = k
                break

        if not preferred:
            preferred = "multisplit"

        if self._tcp_hide_fake_phase and preferred == "fake":
            preferred = "multisplit"

        self._set_active_phase_chip(preferred)

    def _strategy_has_embedded_fake(self, strategy_id: str) -> bool:
        """True if strategy uses a built-in fake technique (fakedsplit/fakeddisorder/hostfakesplit)."""
        if not strategy_id:
            return False
        args_text = self._get_strategy_args_text_by_id(strategy_id)
        for tech in self._extract_desync_techniques_from_args(args_text):
            if tech in TCP_EMBEDDED_FAKE_TECHNIQUES:
                return True
        return False

    def _build_tcp_args_from_phase_state(self) -> str:
        """Builds the ordered chain of --lua-desync lines for tcp_args."""
        if not self._tcp_phase_mode:
            return ""

        out_lines: list[str] = []
        for phase in TCP_PHASE_COMMAND_ORDER:
            if phase == "fake" and self._tcp_hide_fake_phase:
                continue

            sid = (self._tcp_phase_selected_ids.get(phase) or "").strip()
            if not sid:
                continue

            if phase == "fake" and sid == TCP_FAKE_DISABLED_STRATEGY_ID:
                continue

            if sid == CUSTOM_STRATEGY_ID:
                chunk = _normalize_args_text(self._tcp_phase_custom_args.get(phase, ""))
            else:
                chunk = self._get_strategy_args_text_by_id(sid)

            if not chunk:
                continue

            for raw in chunk.splitlines():
                line = raw.strip()
                if line:
                    out_lines.append(line)

        return "\n".join(out_lines).strip()

    def _save_tcp_phase_state_to_preset(self, *, show_loading: bool = True) -> None:
        """Persists current phase state into preset tcp_args and emits selection update."""
        if not (self._tcp_phase_mode and self._category_key):
            return

        new_args = self._build_tcp_args_from_phase_state()

        try:
            preset = self._preset_manager.get_active_preset()
            if not preset:
                return

            if self._category_key not in preset.categories:
                self._preset_manager.ensure_category(preset, self._category_key)

            cat = preset.categories[self._category_key]
            cat.tcp_args = new_args
            cat.strategy_id = self._infer_strategy_id_from_args_exact(new_args)
            preset.touch()
            self._preset_manager.save_preset_model(preset)

            # Update local state for UI.
            self._selected_strategy_id = cat.strategy_id or "none"
            self._current_strategy_id = cat.strategy_id or "none"
            self._set_category_enabled_ui(self._selected_strategy_id != "none")
            self._refresh_args_editor_state()

            # UI feedback
            if show_loading and self._selected_strategy_id != "none":
                self.show_loading()
            elif self._selected_strategy_id == "none":
                self._stop_loading()
                self._success_icon.hide()

            self._update_selected_strategy_header(self._selected_strategy_id)
            self._update_tcp_phase_chip_markers()

            # Notify main page (strategy id is "custom" for multi-phase)
            self.strategy_selected.emit(self._category_key, self._selected_strategy_id)

        except Exception as e:
            log(f"TCP phase save failed: {e}", "ERROR")

    def _on_tcp_phase_row_clicked(self, strategy_id: str) -> None:
        """TCP multi-phase: applies selection for the currently active phase."""
        if not (self._tcp_phase_mode and self._category_key and self._strategies_tree):
            return

        phase = (self._active_phase_key or "").strip().lower()
        if not phase:
            return

        sid = str(strategy_id or "").strip()
        if not sid:
            return

        # Clicking a hidden/filtered row should not happen, but be defensive.
        try:
            if not self._strategies_tree.is_strategy_visible(sid):
                return
        except Exception:
            pass

        # Fake phase: clicking the same strategy again toggles it off.
        if phase == "fake":
            current = (self._tcp_phase_selected_ids.get("fake") or "").strip()
            if current and current == sid:
                # Same click toggles fake off (no separate "disabled" row).
                self._tcp_phase_selected_ids["fake"] = TCP_FAKE_DISABLED_STRATEGY_ID
                self._tcp_phase_custom_args.pop("fake", None)
                try:
                    self._strategies_tree.clear_active_strategy()
                except Exception:
                    pass
            else:
                self._tcp_phase_selected_ids["fake"] = sid
                self._tcp_phase_custom_args.pop("fake", None)
                self._strategies_tree.set_selected_strategy(sid)

            self._save_tcp_phase_state_to_preset(show_loading=True)
            return

        # Other phases: toggle off when clicking the currently selected strategy.
        current = (self._tcp_phase_selected_ids.get(phase) or "").strip()
        if current == sid:
            self._tcp_phase_selected_ids.pop(phase, None)
            self._tcp_phase_custom_args.pop(phase, None)
            try:
                self._strategies_tree.clear_active_strategy()
            except Exception:
                pass
        else:
            self._tcp_phase_selected_ids[phase] = sid
            self._tcp_phase_custom_args.pop(phase, None)
            self._strategies_tree.set_selected_strategy(sid)

        # Embedded-fake techniques remove the FAKE phase tab and suppress separate --lua-desync=fake.
        hide_fake = any(
            self._strategy_has_embedded_fake(sel_id)
            for k, sel_id in self._tcp_phase_selected_ids.items()
            if k != "fake" and sel_id and sel_id not in (CUSTOM_STRATEGY_ID, TCP_FAKE_DISABLED_STRATEGY_ID)
        )
        if not hide_fake:
            # Also detect embedded-fake inside custom chunks.
            for k, chunk in (self._tcp_phase_custom_args or {}).items():
                if k == "fake":
                    continue
                for tech in self._extract_desync_techniques_from_args(chunk):
                    if tech in TCP_EMBEDDED_FAKE_TECHNIQUES:
                        hide_fake = True
                        break
                if hide_fake:
                    break
        self._tcp_hide_fake_phase = hide_fake
        self._apply_tcp_phase_tabs_visibility()

        self._save_tcp_phase_state_to_preset(show_loading=True)

    def _set_category_block_dimmed(self, widget: QWidget | None, dimmed: bool) -> None:
        if widget is None:
            return

        try:
            widget.setProperty("categoryDisabled", bool(dimmed))
            style = widget.style()
            if style is not None:
                style.unpolish(widget)
                style.polish(widget)
            widget.update()
        except Exception:
            pass

        try:
            if dimmed:
                effect = widget.graphicsEffect()
                if not isinstance(effect, QGraphicsOpacityEffect):
                    effect = QGraphicsOpacityEffect(widget)
                    widget.setGraphicsEffect(effect)
                effect.setOpacity(0.56)
            else:
                widget.setGraphicsEffect(None)
        except Exception:
            pass

    def _set_category_enabled_ui(self, enabled: bool) -> None:
        """Keeps controls visible and dims blocks for disabled categories."""
        is_enabled = bool(enabled)
        try:
            if hasattr(self, "_toolbar_frame") and self._toolbar_frame is not None:
                self._toolbar_frame.setVisible(True)
                self._set_category_block_dimmed(self._toolbar_frame, not is_enabled)
        except Exception:
            pass
        try:
            if hasattr(self, "_strategies_block") and self._strategies_block is not None:
                self._strategies_block.setVisible(True)
                self._set_category_block_dimmed(self._strategies_block, not is_enabled)
                if hasattr(self, "layout") and self.layout is not None:
                    self.layout.setStretchFactor(self._strategies_block, 1)
                self._strategies_block.setMaximumHeight(16777215)
        except Exception:
            pass
        try:
            self._refresh_scroll_range()
        except Exception:
            pass

    def _on_favorite_toggled(self, strategy_id: str, is_favorite: bool) -> None:
        """Called when user clicks the favorite star in the UI."""
        if not self._category_key:
            return
            
        try:
            self._favorites_store.set_favorite(self._category_key, strategy_id, is_favorite)
            
            # Update the cached set for the current category
            if is_favorite:
                self._favorite_strategy_ids.add(strategy_id)
            else:
                self._favorite_strategy_ids.discard(strategy_id)
                
            # Usually toggling a favorite just changes the icon color in place.
            # But if we are sorting by favorites, we might need to re-sort:
            if self._sort_mode == "favorites":
                self._schedule_full_repopulate()
        except Exception as e:
            try:
                log.error(f"Error saving favorite toggled: {e}")
            except:
                pass

    def _get_default_strategy(self) -> str:
        """╨Т╨╛╨╖╨▓╤А╨░╤Й╨░╨╡╤В ╤Б╤В╤А╨░╤В╨╡╨│╨╕╤О ╨┐╨╛ ╤Г╨╝╨╛╨╗╤З╨░╨╜╨╕╤О ╨┤╨╗╤П ╤В╨╡╨║╤Г╤Й╨╡╨╣ ╨║╨░╤В╨╡╨│╨╛╤А╨╕╨╕"""
        try:
            from strategy_menu.strategies_registry import registry

            # ╨Я╤А╨╛╨▒╤Г╨╡╨╝ ╨┐╨╛╨╗╤Г╤З╨╕╤В╤М ╨┤╨╡╤Д╨╛╨╗╤В╨╜╤Г╤О ╤Б╤В╤А╨░╤В╨╡╨│╨╕╤О ╨╕╨╖ ╤А╨╡╨╡╤Б╤В╤А╨░
            defaults = registry.get_default_selections()
            if self._category_key in defaults:
                default_id = defaults[self._category_key]
                if default_id and default_id != "none" and (default_id in (self._default_strategy_order or [])):
                    return default_id

            # ╨Ш╨╜╨░╤З╨╡ ╨▒╨╡╤А╤С╨╝ ╨┐╨╡╤А╨▓╤Г╤О ╤Б╤В╤А╨░╤В╨╡╨│╨╕╤О ╨╕╨╖ ╤Б╨┐╨╕╤Б╨║╨░ (╨╜╨╡ none)
            for sid in (self._default_strategy_order or []):
                if sid and sid != "none":
                    return sid

            return "none"
        except Exception as e:
            log(f"╨Ю╤И╨╕╨▒╨║╨░ ╨┐╨╛╨╗╤Г╤З╨╡╨╜╨╕╤П ╤Б╤В╤А╨░╤В╨╡╨│╨╕╨╕ ╨┐╨╛ ╤Г╨╝╨╛╨╗╤З╨░╨╜╨╕╤О: {e}", "DEBUG")
            # Fallback - ╨┐╨╡╤А╨▓╨░╤П ╨╜╨╡-none ╤Б╤В╤А╨░╤В╨╡╨│╨╕╤П
            for sid in (self._default_strategy_order or []):
                if sid and sid != "none":
                    return sid
            return "none"

    def _on_filter_mode_changed(self, new_mode: str):
        """╨Ю╨▒╤А╨░╨▒╨╛╤В╤З╨╕╨║ ╨╕╨╖╨╝╨╡╨╜╨╡╨╜╨╕╤П ╤А╨╡╨╢╨╕╨╝╨░ ╤Д╨╕╨╗╤М╤В╤А╨░╤Ж╨╕╨╕ ╨┤╨╗╤П ╨║╨░╤В╨╡╨│╨╛╤А╨╕╨╕"""
        if not self._category_key:
            return

        # Save via PresetManager (triggers DPI reload automatically)
        self._save_category_filter_mode(self._category_key, new_mode)
        self.filter_mode_changed.emit(self._category_key, new_mode)
        log(f"╨а╨╡╨╢╨╕╨╝ ╤Д╨╕╨╗╤М╤В╤А╨░╤Ж╨╕╨╕ ╨┤╨╗╤П {self._category_key}: {new_mode}", "INFO")

    def _save_category_filter_mode(self, category_key: str, mode: str):
        """╨б╨╛╤Е╤А╨░╨╜╤П╨╡╤В ╤А╨╡╨╢╨╕╨╝ ╤Д╨╕╨╗╤М╤В╤А╨░╤Ж╨╕╨╕ ╨┤╨╗╤П ╨║╨░╤В╨╡╨│╨╛╤А╨╕╨╕ ╤З╨╡╤А╨╡╨╖ PresetManager"""
        self._preset_manager.update_category_filter_mode(
            category_key, mode, save_and_sync=True
        )

    def _load_category_filter_mode(self, category_key: str) -> str:
        """╨Ч╨░╨│╤А╤Г╨╢╨░╨╡╤В ╤А╨╡╨╢╨╕╨╝ ╤Д╨╕╨╗╤М╤В╤А╨░╤Ж╨╕╨╕ ╨┤╨╗╤П ╨║╨░╤В╨╡╨│╨╛╤А╨╕╨╕ ╨╕╨╖ PresetManager"""
        return self._preset_manager.get_category_filter_mode(category_key)

    def _save_category_sort(self, category_key: str, sort_order: str):
        """╨б╨╛╤Е╤А╨░╨╜╤П╨╡╤В ╨┐╨╛╤А╤П╨┤╨╛╨║ ╤Б╨╛╤А╤В╨╕╤А╨╛╨▓╨║╨╕ ╨┤╨╗╤П ╨║╨░╤В╨╡╨│╨╛╤А╨╕╨╕ ╤З╨╡╤А╨╡╨╖ PresetManager"""
        # Sort order is UI-only parameter, doesn't affect DPI
        # But save_and_sync=True is needed to persist changes to disk
        # (hot-reload may trigger but sort_order has no effect on winws2)
        self._preset_manager.update_category_sort_order(
            category_key, sort_order, save_and_sync=True
        )

    def _load_category_sort(self, category_key: str) -> str:
        """╨Ч╨░╨│╤А╤Г╨╢╨░╨╡╤В ╨┐╨╛╤А╤П╨┤╨╛╨║ ╤Б╨╛╤А╤В╨╕╤А╨╛╨▓╨║╨╕ ╨┤╨╗╤П ╨║╨░╤В╨╡╨│╨╛╤А╨╕╨╕ ╨╕╨╖ PresetManager"""
        return self._preset_manager.get_category_sort_order(category_key)

    # ======================================================================
    # TCP PHASE TAB PERSISTENCE (UI-only)
    # ======================================================================

    _REG_TCP_PHASE_TABS_BY_CATEGORY = "TcpPhaseTabByCategory"

    def _load_category_last_tcp_phase_tab(self, category_key: str) -> str | None:
        """Loads the last selected TCP phase tab for a category (persisted in registry)."""
        try:
            from config.reg import reg
            from config import REGISTRY_PATH_GUI
        except Exception:
            return None

        key = str(category_key or "").strip().lower()
        if not key:
            return None

        try:
            raw = reg(REGISTRY_PATH_GUI, self._REG_TCP_PHASE_TABS_BY_CATEGORY)
            if not raw:
                return None
            data = json.loads(raw) if isinstance(raw, str) else {}
            phase = str((data or {}).get(key) or "").strip().lower()
            if phase and phase in (self._phase_tab_index_by_key or {}):
                return phase
        except Exception:
            return None

        return None

    def _save_category_last_tcp_phase_tab(self, category_key: str, phase_key: str) -> None:
        """Saves the last selected TCP phase tab for a category (best-effort)."""
        try:
            from config.reg import reg
            from config import REGISTRY_PATH_GUI
        except Exception:
            return

        cat_key = str(category_key or "").strip().lower()
        phase = str(phase_key or "").strip().lower()
        if not cat_key or not phase:
            return

        # Validate phase key early to avoid persisting garbage.
        if self._tcp_phase_mode and phase not in (self._phase_tab_index_by_key or {}):
            return

        try:
            raw = reg(REGISTRY_PATH_GUI, self._REG_TCP_PHASE_TABS_BY_CATEGORY)
            data = {}
            if isinstance(raw, str) and raw.strip():
                try:
                    data = json.loads(raw) or {}
                except Exception:
                    data = {}
            if not isinstance(data, dict):
                data = {}
            data[cat_key] = phase
            reg(REGISTRY_PATH_GUI, self._REG_TCP_PHASE_TABS_BY_CATEGORY, json.dumps(data, ensure_ascii=False))
        except Exception:
            return

    # тХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХР
    # OUT RANGE METHODS
    # тХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХР

    def _select_out_range_mode(self, mode: str):
        """╨Т╤Л╨▒╨╛╤А ╤А╨╡╨╢╨╕╨╝╨░ out_range (n ╨╕╨╗╨╕ d)"""
        if mode != self._out_range_mode:
            self._out_range_mode = mode
            try:
                self._out_range_seg.setCurrentItem(mode)
            except Exception:
                pass
            self._save_syndata_settings()

    # тХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХР
    # SYNDATA SETTINGS METHODS
    # тХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХР

    def _on_send_toggled(self, checked: bool):
        """╨Ю╨▒╤А╨░╨▒╨╛╤В╤З╨╕╨║ ╨▓╨║╨╗╤О╤З╨╡╨╜╨╕╤П/╨▓╤Л╨║╨╗╤О╤З╨╡╨╜╨╕╤П send ╨┐╨░╤А╨░╨╝╨╡╤В╤А╨╛╨▓"""
        self._send_settings.setVisible(checked)
        self._save_syndata_settings()

    def _on_syndata_toggled(self, checked: bool):
        """╨Ю╨▒╤А╨░╨▒╨╛╤В╤З╨╕╨║ ╨▓╨║╨╗╤О╤З╨╡╨╜╨╕╤П/╨▓╤Л╨║╨╗╤О╤З╨╡╨╜╨╕╤П syndata ╨┐╨░╤А╨░╨╝╨╡╤В╤А╨╛╨▓"""
        self._syndata_settings.setVisible(checked)
        self._save_syndata_settings()

    def _save_syndata_settings(self):
        """╨б╨╛╤Е╤А╨░╨╜╤П╨╡╤В syndata ╨╜╨░╤Б╤В╤А╨╛╨╣╨║╨╕ ╨┤╨╗╤П ╤В╨╡╨║╤Г╤Й╨╡╨╣ ╨║╨░╤В╨╡╨│╨╛╤А╨╕╨╕ ╤З╨╡╤А╨╡╨╖ PresetManager"""
        if not self._category_key:
            return

        # Build SyndataSettings from UI
        syndata = SyndataSettings(
            enabled=self._syndata_toggle.isChecked(),
            blob=self._blob_combo.currentText(),
            tls_mod=self._tls_mod_combo.currentText(),
            autottl_delta=self._autottl_delta_selector.value(),
            autottl_min=self._autottl_min_selector.value(),
            autottl_max=self._autottl_max_selector.value(),
            out_range=self._out_range_spin.value(),
            out_range_mode=self._out_range_mode,
            tcp_flags_unset=self._tcp_flags_combo.currentText(),
            send_enabled=self._send_toggle.isChecked(),
            send_repeats=self._send_repeats_spin.value(),
            send_ip_ttl=self._send_ip_ttl_selector.value(),
            send_ip6_ttl=self._send_ip6_ttl_selector.value(),
            send_ip_id=self._send_ip_id_combo.currentText(),
            send_badsum=self._send_badsum_check.isChecked(),
        )

        log(f"Syndata settings saved for {self._category_key}: {syndata.to_dict()}", "DEBUG")

        # Save with sync=True - ConfigFileWatcher will trigger hot-reload automatically
        # when it detects the preset file change
        protocol_raw = str(getattr(self._category_info, "protocol", "") or "").upper()
        is_udp_like = ("UDP" in protocol_raw) or ("QUIC" in protocol_raw) or ("L7" in protocol_raw)
        protocol_key = "udp" if is_udp_like else "tcp"
        self._preset_manager.update_category_syndata(
            self._category_key, syndata, protocol=protocol_key, save_and_sync=True
        )

    def _load_syndata_settings(self, category_key: str) -> dict:
        """╨Ч╨░╨│╤А╤Г╨╢╨░╨╡╤В syndata ╨╜╨░╤Б╤В╤А╨╛╨╣╨║╨╕ ╨┤╨╗╤П ╨║╨░╤В╨╡╨│╨╛╤А╨╕╨╕ ╨╕╨╖ PresetManager"""
        protocol_raw = str(getattr(self._category_info, "protocol", "") or "").upper()
        is_udp_like = ("UDP" in protocol_raw) or ("QUIC" in protocol_raw) or ("L7" in protocol_raw)
        protocol_key = "udp" if is_udp_like else "tcp"
        syndata = self._preset_manager.get_category_syndata(category_key, protocol=protocol_key)
        return syndata.to_dict()

    # ======================================================================
    # TCP PHASE TAB PERSISTENCE (UI-only)
    # ======================================================================

    _REG_TCP_PHASE_TABS_BY_CATEGORY = "TcpPhaseTabByCategory"

    def _load_category_last_tcp_phase_tab(self, category_key: str) -> str | None:
        """Loads the last selected TCP phase tab for a category (persisted in registry)."""
        try:
            from config.reg import reg
            from config import REGISTRY_PATH_GUI
        except Exception:
            return None

        key = str(category_key or "").strip().lower()
        if not key:
            return None

        try:
            raw = reg(REGISTRY_PATH_GUI, self._REG_TCP_PHASE_TABS_BY_CATEGORY)
            if not raw:
                return None
            data = json.loads(raw) if isinstance(raw, str) else {}
            phase = str((data or {}).get(key) or "").strip().lower()
            if phase and phase in (self._phase_tab_index_by_key or {}):
                return phase
        except Exception:
            return None

        return None

    def _save_category_last_tcp_phase_tab(self, category_key: str, phase_key: str) -> None:
        """Saves the last selected TCP phase tab for a category (best-effort)."""
        try:
            from config.reg import reg
            from config import REGISTRY_PATH_GUI
        except Exception:
            return

        cat_key = str(category_key or "").strip().lower()
        phase = str(phase_key or "").strip().lower()
        if not cat_key or not phase:
            return

        # Validate phase key early to avoid persisting garbage.
        if self._tcp_phase_mode and phase not in (self._phase_tab_index_by_key or {}):
            return

        try:
            raw = reg(REGISTRY_PATH_GUI, self._REG_TCP_PHASE_TABS_BY_CATEGORY)
            data = {}
            if isinstance(raw, str) and raw.strip():
                try:
                    data = json.loads(raw) or {}
                except Exception:
                    data = {}
            if not isinstance(data, dict):
                data = {}
            data[cat_key] = phase
            reg(REGISTRY_PATH_GUI, self._REG_TCP_PHASE_TABS_BY_CATEGORY, json.dumps(data, ensure_ascii=False))
        except Exception:
            return

    # тХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХР
    # OUT RANGE METHODS
    # тХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХР

    def _select_out_range_mode(self, mode: str):
        """╨Т╤Л╨▒╨╛╤А ╤А╨╡╨╢╨╕╨╝╨░ out_range (n ╨╕╨╗╨╕ d)"""
        if mode != self._out_range_mode:
            self._out_range_mode = mode
            try:
                self._out_range_seg.setCurrentItem(mode)
            except Exception:
                pass
            self._save_syndata_settings()

    # тХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХР
    # SYNDATA SETTINGS METHODS
    # тХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХР

    def _on_send_toggled(self, checked: bool):
        """╨Ю╨▒╤А╨░╨▒╨╛╤В╤З╨╕╨║ ╨▓╨║╨╗╤О╤З╨╡╨╜╨╕╤П/╨▓╤Л╨║╨╗╤О╤З╨╡╨╜╨╕╤П send ╨┐╨░╤А╨░╨╝╨╡╤В╤А╨╛╨▓"""
        self._send_settings.setVisible(checked)
        self._save_syndata_settings()

    def _on_syndata_toggled(self, checked: bool):
        """╨Ю╨▒╤А╨░╨▒╨╛╤В╤З╨╕╨║ ╨▓╨║╨╗╤О╤З╨╡╨╜╨╕╤П/╨▓╤Л╨║╨╗╤О╤З╨╡╨╜╨╕╤П syndata ╨┐╨░╤А╨░╨╝╨╡╤В╤А╨╛╨▓"""
        self._syndata_settings.setVisible(checked)
        self._save_syndata_settings()

    def _save_syndata_settings(self):
        """╨б╨╛╤Е╤А╨░╨╜╤П╨╡╤В syndata ╨╜╨░╤Б╤В╤А╨╛╨╣╨║╨╕ ╨┤╨╗╤П ╤В╨╡╨║╤Г╤Й╨╡╨╣ ╨║╨░╤В╨╡╨│╨╛╤А╨╕╨╕ ╤З╨╡╤А╨╡╨╖ PresetManager"""
        if not self._category_key:
            return

        # Build SyndataSettings from UI
        syndata = SyndataSettings(
            enabled=self._syndata_toggle.isChecked(),
            blob=self._blob_combo.currentText(),
            tls_mod=self._tls_mod_combo.currentText(),
            autottl_delta=self._autottl_delta_selector.value(),
            autottl_min=self._autottl_min_selector.value(),
            autottl_max=self._autottl_max_selector.value(),
            out_range=self._out_range_spin.value(),
            out_range_mode=self._out_range_mode,
            tcp_flags_unset=self._tcp_flags_combo.currentText(),
            send_enabled=self._send_toggle.isChecked(),
            send_repeats=self._send_repeats_spin.value(),
            send_ip_ttl=self._send_ip_ttl_selector.value(),
            send_ip6_ttl=self._send_ip6_ttl_selector.value(),
            send_ip_id=self._send_ip_id_combo.currentText(),
            send_badsum=self._send_badsum_check.isChecked(),
        )

        log(f"Syndata settings saved for {self._category_key}: {syndata.to_dict()}", "DEBUG")

        # Save with sync=True - ConfigFileWatcher will trigger hot-reload automatically
        # when it detects the preset file change
        protocol_raw = str(getattr(self._category_info, "protocol", "") or "").upper()
        is_udp_like = ("UDP" in protocol_raw) or ("QUIC" in protocol_raw) or ("L7" in protocol_raw)
        protocol_key = "udp" if is_udp_like else "tcp"
        self._preset_manager.update_category_syndata(
            self._category_key, syndata, protocol=protocol_key, save_and_sync=True
        )

    def _load_syndata_settings(self, category_key: str) -> dict:
        """╨Ч╨░╨│╤А╤Г╨╢╨░╨╡╤В syndata ╨╜╨░╤Б╤В╤А╨╛╨╣╨║╨╕ ╨┤╨╗╤П ╨║╨░╤В╨╡╨│╨╛╤А╨╕╨╕ ╨╕╨╖ PresetManager"""
        protocol_raw = str(getattr(self._category_info, "protocol", "") or "").upper()
        is_udp_like = ("UDP" in protocol_raw) or ("QUIC" in protocol_raw) or ("L7" in protocol_raw)
        protocol_key = "udp" if is_udp_like else "tcp"
        syndata = self._preset_manager.get_category_syndata(category_key, protocol=protocol_key)
        return syndata.to_dict()


    def _refresh_args_editor_state(self):
        enabled = bool(self._category_key) and (self._selected_strategy_id or "none") != "none"
        try:
            if hasattr(self, "_edit_args_btn"):
                self._edit_args_btn.setEnabled(enabled)
        except Exception:
            pass

        if not enabled:
            self._hide_args_editor(clear_text=True)

    def _toggle_args_editor(self):
        """Открывает MessageBoxBase диалог для редактирования args текущей категории."""
        if not self._category_key:
            return
        if (self._selected_strategy_id or "none") == "none":
            return

        initial = self._load_args_text()
        dlg = _ArgsEditorDialog(initial_text=initial, parent=self.window(), language=self._ui_language)
        if dlg.exec():
            self._apply_args_editor(dlg.get_text())

    def _hide_args_editor(self, clear_text: bool = False):
        """Стаб для обратной совместимости — редактор теперь диалог."""
        self._args_editor_dirty = False

    def _load_args_text(self) -> str:
        """Возвращает текущий args текст из пресета для открытия в диалоге."""
        if not self._category_key:
            return ""
        if (self._selected_strategy_id or "none") == "none":
            return ""
        try:
            preset = self._preset_manager.get_active_preset()
            cat = preset.categories.get(self._category_key) if preset else None
            if cat:
                return (cat.udp_args if self._is_udp_like_category() else cat.tcp_args) or ""
        except Exception as e:
            log(f"Args editor: failed to load preset args: {e}", "DEBUG")
        return ""

    def _load_args_into_editor(self):
        """Стаб для обратной совместимости."""
        pass

    def _on_args_editor_changed(self):
        """Стаб для обратной совместимости."""
        pass

    def _apply_args_editor(self, raw: str = ""):
        if not self._category_key:
            return
        if (self._selected_strategy_id or "none") == "none":
            return

        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        normalized = "\n".join(lines)

        try:
            preset = self._preset_manager.get_active_preset()
            if not preset:
                return

            if self._category_key not in preset.categories:
                self._preset_manager.ensure_category(preset, self._category_key)

            cat = preset.categories[self._category_key]

            if self._is_udp_like_category():
                cat.udp_args = normalized
            else:
                cat.tcp_args = normalized

            preset.touch()
            self._preset_manager.save_preset_model(preset)

            self._args_editor_dirty = False
            self.show_loading()
            self._on_args_changed(self._selected_strategy_id, lines)

        except Exception as e:
            log(f"Args editor: failed to save args: {e}", "ERROR")

    def _on_search_changed(self, text: str):
        """Фильтрует стратегии по поисковому запросу"""
        self._apply_filters()

    def _on_filter_toggled(self, technique: str, active: bool):
        """Обработчик переключения фильтра"""
        if active:
            self._active_filters.add(technique)
        else:
            self._active_filters.discard(technique)
        self._update_technique_filter_ui()
        self._apply_filters()

    def _build_sort_tooltip(self) -> str:
        mode = str(self._sort_mode or "default").strip().lower() or "default"
        if mode == "name_asc":
            label = self._tr("page.z2_strategy_detail.sort.name_asc", "По имени (А-Я)")
        elif mode == "name_desc":
            label = self._tr("page.z2_strategy_detail.sort.name_desc", "По имени (Я-А)")
        else:
            label = self._tr("page.z2_strategy_detail.sort.default", "По умолчанию")
        return self._tr("page.z2_strategy_detail.sort.tooltip", "Сортировка: {label}", label=label)

    def _update_sort_button_ui(self) -> None:
        btn = getattr(self, "_sort_btn", None)
        if not btn:
            return
        mode = str(self._sort_mode or "default").strip().lower() or "default"
        is_active = mode != "default"
        try:
            tokens = get_theme_tokens()
            color = tokens.accent_hex if is_active else tokens.fg_faint
            if color != self._last_sort_icon_color:
                btn.setIcon(qta.icon('fa5s.sort-alpha-down', color=color))
                self._last_sort_icon_color = color
        except Exception:
            pass
        try:
            set_tooltip(btn, self._build_sort_tooltip())
        except Exception:
            pass

    def _on_technique_filter_changed(self, index: int) -> None:
        """Обработчик выбора техники в ComboBox фильтра."""
        self._active_filters.clear()
        if index > 0 and index <= len(STRATEGY_TECHNIQUE_FILTERS):
            key = STRATEGY_TECHNIQUE_FILTERS[index - 1][1]
            self._active_filters.add(key)
        self._apply_filters()

    def _update_technique_filter_ui(self) -> None:
        """Синхронизирует ComboBox с текущим состоянием _active_filters."""
        combo = getattr(self, "_filter_combo", None)
        if combo is None:
            return
        active = {str(t or "").strip().lower() for t in (self._active_filters or set()) if str(t or "").strip()}
        if not active:
            target_idx = 0
        else:
            technique = next(iter(active))
            target_idx = 0
            for i, (_label, key) in enumerate(STRATEGY_TECHNIQUE_FILTERS, start=1):
                if key == technique:
                    target_idx = i
                    break
        combo.blockSignals(True)
        combo.setCurrentIndex(target_idx)
        combo.blockSignals(False)

    def _on_phase_tab_changed(self, route_key: str) -> None:
        """TCP multi-phase: handler for Pivot currentItemChanged signal."""
        if not self._tcp_phase_mode:
            return

        key = str(route_key or "").strip().lower()
        if not key:
            return

        self._active_phase_key = key
        try:
            if self._category_key:
                self._last_active_phase_key_by_category[self._category_key] = key
                self._save_category_last_tcp_phase_tab(self._category_key, key)
        except Exception:
            pass

        self._apply_filters()
        self._sync_tree_selection_to_active_phase()

    def _on_phase_pivot_item_clicked(self, key: str) -> None:
        """Called on every click on a phase pivot item (including re-click of current item)."""
        if not self._tcp_phase_mode:
            return
        k = str(key or "").strip().lower()
        if not k:
            return
        # If clicking the already-active tab, just refresh filters (Pivot won't emit currentItemChanged).
        if k == (self._active_phase_key or ""):
            self._apply_filters()
            self._sync_tree_selection_to_active_phase()

    def _apply_filters(self):
        """Применяет фильтры по технике к списку стратегий"""
        if not self._strategies_tree:
            return
        search_text = self._search_input.text() if self._search_input else ""
        if self._tcp_phase_mode:
            try:
                self._strategies_tree.set_all_strategies_phase(self._active_phase_key)
            except Exception:
                pass
            self._strategies_tree.apply_phase_filter(search_text, self._active_phase_key)
            self._sync_tree_selection_to_active_phase()
            return

        try:
            self._strategies_tree.set_all_strategies_phase(None)
        except Exception:
            pass
        self._strategies_tree.apply_filter(search_text, self._active_filters)
        # Filtering/hiding can drop visual selection; restore for the active strategy if visible.
        sid = self._selected_strategy_id or self._current_strategy_id or "none"
        if sid and self._strategies_tree.has_strategy(sid) and self._strategies_tree.is_strategy_visible(sid):
            self._strategies_tree.set_selected_strategy(sid)

    def _sync_tree_selection_to_active_phase(self) -> None:
        """TCP multi-phase: restores highlighted row for the currently active phase."""
        if not (self._tcp_phase_mode and self._strategies_tree):
            return

        phase = (self._active_phase_key or "").strip().lower()
        if not phase:
            try:
                self._strategies_tree.clear_active_strategy()
            except Exception:
                pass
            return

        sid = (self._tcp_phase_selected_ids.get(phase) or "").strip()
        if sid and sid != CUSTOM_STRATEGY_ID and self._strategies_tree.has_strategy(sid) and self._strategies_tree.is_strategy_visible(sid):
            self._strategies_tree.set_selected_strategy(sid)
            return

        try:
            self._strategies_tree.clear_active_strategy()
        except Exception:
            pass

    def _show_sort_menu(self):
        """Показывает RoundMenu сортировки с иконками."""
        menu = RoundMenu(parent=self)

        _sort_icon     = FluentIcon.SCROLL if _HAS_FLUENT else None
        _asc_icon      = FluentIcon.UP     if _HAS_FLUENT else None
        _desc_icon     = FluentIcon.DOWN   if _HAS_FLUENT else None

        def _set_sort(mode: str):
            self._sort_mode = mode
            if self._category_key:
                self._save_category_sort(self._category_key, self._sort_mode)
            self._apply_sort()

        entries = [
            (_sort_icon, self._tr("page.z2_strategy_detail.sort.default", "По умолчанию"), "default"),
            (_asc_icon, self._tr("page.z2_strategy_detail.sort.name_asc", "По имени (А-Я)"), "name_asc"),
            (_desc_icon, self._tr("page.z2_strategy_detail.sort.name_desc", "По имени (Я-А)"), "name_desc"),
        ]
        for icon, label, mode in entries:
            act = Action(icon, label, checkable=True) if _HAS_FLUENT else Action(label)
            act.setChecked(self._sort_mode == mode)
            act.triggered.connect(lambda _checked, m=mode: _set_sort(m))
            menu.addAction(act)

        try:
            pos = self._sort_btn.mapToGlobal(self._sort_btn.rect().bottomLeft())
        except Exception:
            return
        menu.exec(pos)

    def _apply_sort(self):
        """Применяет текущую сортировку"""
        if not self._strategies_tree:
            return
        self._strategies_tree.set_sort_mode(self._sort_mode)
        self._strategies_tree.apply_sort()
        self._update_sort_button_ui()
        # Sorting (takeChildren/addChild) may reset selection in Qt; restore it.
        sid = self._selected_strategy_id or self._current_strategy_id or "none"
        if sid and self._strategies_tree.has_strategy(sid):
            self._strategies_tree.set_selected_strategy(sid)

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)

        if not getattr(self, "_content_built", False):
            return

        if getattr(self, "_breadcrumb", None) is not None:
            self._breadcrumb.blockSignals(True)
            try:
                self._breadcrumb.clear()
                self._breadcrumb.addItem("control", self._tr("page.z2_strategy_detail.breadcrumb.control", "Управление"))
                self._breadcrumb.addItem(
                    "strategies", self._tr("page.z2_strategy_detail.breadcrumb.strategies", "Стратегии DPI")
                )
                detail = ""
                try:
                    detail = self._category_info.full_name if self._category_info else ""
                except Exception:
                    detail = ""
                self._breadcrumb.addItem(
                    "detail",
                    detail or self._tr("page.z2_strategy_detail.header.category_fallback", "Категория"),
                )
            finally:
                self._breadcrumb.blockSignals(False)

        if getattr(self, "_parent_link", None) is not None:
            self._parent_link.setText(self._tr("page.z2_strategy_detail.back.strategies", "Стратегии DPI"))

        if getattr(self, "_title", None) is not None:
            cat_name = ""
            protocol = ""
            ports = ""
            try:
                if self._category_info:
                    cat_name = str(getattr(self._category_info, "full_name", "") or "").strip()
                    protocol = str(getattr(self._category_info, "protocol", "") or "").strip()
                    ports = str(getattr(self._category_info, "ports", "") or "").strip()
            except Exception:
                pass
            self._title.setText(cat_name or self._tr("page.z2_strategy_detail.header.select_category", "Выберите категорию"))
            if getattr(self, "_subtitle", None) is not None:
                if protocol:
                    self._subtitle.setText(
                        f"{protocol}  |  "
                        f"{self._tr('page.z2_strategy_detail.subtitle.ports', 'порты: {ports}', ports=ports)}"
                    )
                else:
                    self._subtitle.setText("")

        if getattr(self, "_filter_mode_frame", None) is not None:
            self._filter_mode_frame.set_title(
                self._tr("page.z2_strategy_detail.filter_mode.title", "Режим фильтрации")
            )
            self._filter_mode_frame.set_description(
                self._tr("page.z2_strategy_detail.filter_mode.description", "Hostlist - по доменам, IPset - по IP")
            )
        if getattr(self, "_filter_mode_selector", None) is not None:
            if hasattr(self._filter_mode_selector, "setOnText"):
                self._filter_mode_selector.setOnText(self._tr("page.z2_strategy_detail.filter.ipset", "IPset"))
            if hasattr(self._filter_mode_selector, "setOffText"):
                self._filter_mode_selector.setOffText(self._tr("page.z2_strategy_detail.filter.hostlist", "Hostlist"))

        if getattr(self, "_out_range_mode_label", None) is not None:
            self._out_range_mode_label.setText(self._tr("page.z2_strategy_detail.out_range.mode", "Режим:"))
        if getattr(self, "_out_range_value_label", None) is not None:
            self._out_range_value_label.setText(self._tr("page.z2_strategy_detail.out_range.value", "Значение:"))
        if getattr(self, "_out_range_frame", None) is not None:
            self._out_range_frame.set_title(self._tr("page.z2_strategy_detail.out_range.title", "Out Range"))
            self._out_range_frame.set_description(
                self._tr("page.z2_strategy_detail.out_range.description", "Ограничение исходящих пакетов")
            )
        if getattr(self, "_out_range_seg", None) is not None:
            set_tooltip(
                self._out_range_seg,
                self._tr(
                    "page.z2_strategy_detail.out_range.mode.tooltip",
                    "n = количество пакетов с самого первого, d = отсчитывать ТОЛЬКО количество пакетов с данными",
                ),
            )
        if getattr(self, "_out_range_spin", None) is not None:
            set_tooltip(
                self._out_range_spin,
                self._tr(
                    "page.z2_strategy_detail.out_range.value.tooltip",
                    "--out-range: ограничение количества исходящих пакетов (n) или задержки (d)",
                ),
            )

        if getattr(self, "_search_input", None) is not None:
            self._search_input.setPlaceholderText(
                self._tr("page.z2_strategy_detail.search.placeholder", "Поиск по имени или args...")
            )

        if getattr(self, "_sort_btn", None) is not None:
            self._update_sort_button_ui()

        if getattr(self, "_filter_combo", None) is not None:
            idx = self._filter_combo.currentIndex()
            self._filter_combo.blockSignals(True)
            self._filter_combo.clear()
            self._filter_combo.addItem(self._tr("page.z2_strategy_detail.filter.technique.all", "Все техники"))
            for label, _key in STRATEGY_TECHNIQUE_FILTERS:
                self._filter_combo.addItem(label)
            self._filter_combo.setCurrentIndex(max(0, idx))
            self._filter_combo.blockSignals(False)

        if getattr(self, "_edit_args_btn", None) is not None:
            set_tooltip(
                self._edit_args_btn,
                self._tr(
                    "page.z2_strategy_detail.args.tooltip",
                    "Аргументы стратегии (по выбранной категории)",
                ),
            )

        if getattr(self, "_send_toggle_row", None) is not None:
            self._send_toggle_row.set_texts(
                self._tr("page.z2_strategy_detail.send.toggle.title", "Send параметры"),
                self._tr("page.z2_strategy_detail.send.toggle.description", "Отправка копий пакетов"),
            )
        if getattr(self, "_send_repeats_row", None) is not None:
            self._send_repeats_row.set_texts(
                self._tr("page.z2_strategy_detail.send.repeats.title", "repeats"),
                self._tr("page.z2_strategy_detail.send.repeats.description", "Количество повторных отправок"),
            )
        if getattr(self, "_send_ip_ttl_frame", None) is not None:
            self._send_ip_ttl_frame.set_title(self._tr("page.z2_strategy_detail.send.ip_ttl.title", "ip_ttl"))
            self._send_ip_ttl_frame.set_description(
                self._tr("page.z2_strategy_detail.send.ip_ttl.description", "TTL для IPv4 отправляемых пакетов")
            )
        if getattr(self, "_send_ip6_ttl_frame", None) is not None:
            self._send_ip6_ttl_frame.set_title(self._tr("page.z2_strategy_detail.send.ip6_ttl.title", "ip6_ttl"))
            self._send_ip6_ttl_frame.set_description(
                self._tr("page.z2_strategy_detail.send.ip6_ttl.description", "TTL для IPv6 отправляемых пакетов")
            )
        if getattr(self, "_send_ip_id_row", None) is not None:
            self._send_ip_id_row.set_texts(
                self._tr("page.z2_strategy_detail.send.ip_id.title", "ip_id"),
                self._tr("page.z2_strategy_detail.send.ip_id.description", "Режим IP ID для отправляемых пакетов"),
            )
        if getattr(self, "_send_badsum_frame", None) is not None:
            self._send_badsum_frame.set_title(self._tr("page.z2_strategy_detail.send.badsum.title", "badsum"))
            self._send_badsum_frame.set_description(
                self._tr(
                    "page.z2_strategy_detail.send.badsum.description",
                    "Отправлять пакеты с неправильной контрольной суммой",
                )
            )

        if getattr(self, "_syndata_toggle_row", None) is not None:
            self._syndata_toggle_row.set_texts(
                self._tr("page.z2_strategy_detail.syndata.toggle.title", "Syndata параметры"),
                self._tr(
                    "page.z2_strategy_detail.syndata.toggle.description",
                    "Дополнительные параметры обхода DPI",
                ),
            )
        if getattr(self, "_blob_row", None) is not None:
            self._blob_row.set_texts(
                self._tr("page.z2_strategy_detail.syndata.blob.title", "blob"),
                self._tr("page.z2_strategy_detail.syndata.blob.description", "Полезная нагрузка пакета"),
            )
        if getattr(self, "_tls_mod_row", None) is not None:
            self._tls_mod_row.set_texts(
                self._tr("page.z2_strategy_detail.syndata.tls_mod.title", "tls_mod"),
                self._tr("page.z2_strategy_detail.syndata.tls_mod.description", "Модификация полезной нагрузки TLS"),
            )
        if getattr(self, "_autottl_delta_frame", None) is not None:
            self._autottl_delta_frame.set_title(
                self._tr("page.z2_strategy_detail.syndata.autottl_delta.title", "AutoTTL Delta")
            )
            self._autottl_delta_frame.set_description(
                self._tr(
                    "page.z2_strategy_detail.syndata.autottl_delta.description",
                    "Смещение от измеренного TTL (OFF = убрать ip_autottl)",
                )
            )
        if getattr(self, "_autottl_min_frame", None) is not None:
            self._autottl_min_frame.set_title(
                self._tr("page.z2_strategy_detail.syndata.autottl_min.title", "AutoTTL Min")
            )
            self._autottl_min_frame.set_description(
                self._tr("page.z2_strategy_detail.syndata.autottl_min.description", "Минимальный TTL")
            )
        if getattr(self, "_autottl_max_frame", None) is not None:
            self._autottl_max_frame.set_title(
                self._tr("page.z2_strategy_detail.syndata.autottl_max.title", "AutoTTL Max")
            )
            self._autottl_max_frame.set_description(
                self._tr("page.z2_strategy_detail.syndata.autottl_max.description", "Максимальный TTL")
            )
        if getattr(self, "_tcp_flags_row", None) is not None:
            self._tcp_flags_row.set_texts(
                self._tr("page.z2_strategy_detail.syndata.tcp_flags.title", "tcp_flags_unset"),
                self._tr("page.z2_strategy_detail.syndata.tcp_flags.description", "Сбросить TCP флаги"),
            )

        if getattr(self, "_create_preset_btn", None) is not None:
            self._create_preset_btn.setText(
                self._tr("page.z2_strategy_detail.button.create_preset", "Создать пресет")
            )
            set_tooltip(
                self._create_preset_btn,
                self._tr(
                    "page.z2_strategy_detail.button.create_preset.tooltip",
                    "Создать новый пресет на основе текущих настроек",
                ),
            )
        if getattr(self, "_rename_preset_btn", None) is not None:
            self._rename_preset_btn.setText(
                self._tr("page.z2_strategy_detail.button.rename_preset", "Переименовать")
            )
            set_tooltip(
                self._rename_preset_btn,
                self._tr(
                    "page.z2_strategy_detail.button.rename_preset.tooltip",
                    "Переименовать текущий активный пресет",
                ),
            )
        if getattr(self, "_reset_settings_btn", None) is not None:
            self._reset_settings_btn.setText(
                self._tr("page.z2_strategy_detail.button.reset_settings", "Сбросить настройки")
            )
            try:
                self._reset_settings_btn._confirm_text = self._tr(
                    "page.z2_strategy_detail.button.reset_settings.confirm", "Сбросить все?"
                )
            except Exception:
                pass

        updater = getattr(self, "_update_header_labels", None)
        if callable(updater):
            try:
                updater()
            except Exception:
                pass
        self._update_selected_strategy_header(self._selected_strategy_id)
