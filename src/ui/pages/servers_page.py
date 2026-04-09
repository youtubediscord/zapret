# ui/pages/servers_page.py
"""Страница мониторинга серверов обновлений"""

from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QStackedWidget, QTableWidgetItem, QHeaderView,
)
from PyQt6.QtGui import QColor
import qtawesome as qta
import time

from .base_page import BasePage
from ui.compat_widgets import SettingsCard, ActionButton, PrimaryActionButton
from ui.theme import get_theme_tokens
from ui.theme_refresh import ThemeRefreshController
from ui.text_catalog import tr as tr_catalog
from updater.update_page_controller import UpdatePageController
from updater.update_page_view_controller import UpdatePageViewController
from ui.widgets.win11_controls import Win11ToggleRow

try:
    from qfluentwidgets import (
        BodyLabel, CaptionLabel, StrongBodyLabel,
        PushButton, TransparentToolButton, TransparentPushButton,
        SwitchButton, CardWidget,
        TableWidget,
        ProgressBar, IndeterminateProgressBar, IndeterminateProgressRing,
        FluentIcon, PushSettingCard, SettingCardGroup,
    )
    _HAS_FLUENT = True
except ImportError:
    from PyQt6.QtWidgets import QPushButton, QCheckBox, QProgressBar, QTableWidget as TableWidget
    BodyLabel = QLabel
    CaptionLabel = QLabel
    StrongBodyLabel = QLabel
    PushButton = QPushButton
    TransparentToolButton = QPushButton
    TransparentPushButton = QPushButton
    SwitchButton = QCheckBox
    ProgressBar = QProgressBar
    IndeterminateProgressBar = QProgressBar
    IndeterminateProgressRing = None
    CardWidget = QFrame
    FluentIcon = None
    PushSettingCard = None  # type: ignore[assignment]
    SettingCardGroup = None  # type: ignore[assignment]
    _HAS_FLUENT = False

from config import APP_VERSION, CHANNEL


# ═══════════════════════════════════════════════════════════════════════════════
# ИНДЕТЕРМИНИРОВАННАЯ КНОПКА С ПРОГРЕСС-КОЛЬЦОМ (аналог IndeterminateProgressPushButton Pro)
# ═══════════════════════════════════════════════════════════════════════════════

class _IndeterminateProgressPushButton(PushButton):
    """PushButton с IndeterminateProgressRing внутри — показывается при загрузке."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stored_text = ""
        self._ring = None
        if _HAS_FLUENT and IndeterminateProgressRing is not None:
            self._ring = IndeterminateProgressRing(start=False, parent=self)
            self._ring.setFixedSize(20, 20)
            self._ring.setStrokeWidth(2)
            self._ring.hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._ring is not None:
            x = (self.width() - 20) // 2
            y = (self.height() - 20) // 2
            self._ring.move(x, y)

    def start_loading(self):
        self._stored_text = self.text()
        self.setText("")
        if self._ring is not None:
            self._ring.show()
            self._ring.start()
        self.setEnabled(False)

    def stop_loading(self, text: str = ""):
        self.setText(text or self._stored_text)
        if self._ring is not None:
            self._ring.stop()
            self._ring.hide()
        self.setEnabled(True)


# ═══════════════════════════════════════════════════════════════════════════════
# КАРТОЧКА СТАТУСА ОБНОВЛЕНИЙ
# ═══════════════════════════════════════════════════════════════════════════════

class UpdateStatusCard(CardWidget):
    """Карточка статуса обновлений"""

    check_clicked = pyqtSignal()

    def __init__(self, parent=None, *, language: str = "ru"):
        super().__init__(parent)
        self.setObjectName("updateStatusCard")
        self._ui_language = language
        self._is_checking = False
        self._state = "idle"
        self._state_version = ""
        self._state_source = ""
        self._state_message = ""
        self._state_elapsed = 0.0
        self._tokens = get_theme_tokens()
        self._view_controller = UpdatePageViewController()
        self._build_ui()
        self._theme_refresh = ThemeRefreshController(self, self._apply_theme)

    def _tr(self, key: str, default: str) -> str:
        return tr_catalog(key, language=self._ui_language, default=default)

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Content row
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(20, 16, 20, 16)
        content_layout.setSpacing(16)

        # Static icon
        self._icon_label = QLabel()
        self._icon_label.setFixedSize(40, 40)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(self._icon_label)

        # Text
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)

        self.title_label = StrongBodyLabel(
            self._tr("page.servers.update.title.default", "Проверка обновлений")
        )
        text_layout.addWidget(self.title_label)

        self.subtitle_label = CaptionLabel(
            self._tr(
                "page.servers.update.subtitle.default",
                "Нажмите для проверки доступных обновлений",
            )
        )
        text_layout.addWidget(self.subtitle_label)

        content_layout.addLayout(text_layout, 1)

        # IndeterminateProgressPushButton — кнопка со спиннером при проверке
        self.check_btn = _IndeterminateProgressPushButton()
        self.check_btn.setText(
            self._tr("page.servers.update.button.check", "Проверить обновления")
        )
        self.check_btn.setFixedHeight(32)
        self.check_btn.setMinimumWidth(180)
        self.check_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.check_btn.clicked.connect(self._on_check_clicked)
        content_layout.addWidget(self.check_btn)

        main_layout.addWidget(content)

        self._apply_page_theme(force=True)

    def _apply_theme(self, theme_name: str | None = None) -> None:
        self._tokens = get_theme_tokens(theme_name)
        if not self._is_checking:
            try:
                self._set_icon_idle()
            except Exception:
                pass

    def _set_icon_idle(self):
        pixmap = qta.icon('fa5s.sync-alt', color=self._tokens.accent_hex).pixmap(32, 32)
        self._icon_label.setPixmap(pixmap)

    def _on_check_clicked(self):
        self.check_clicked.emit()

    def _set_error_icon(self) -> None:
        tokens = self._tokens
        error_hex = "#dc2626" if tokens.is_light else "#f87171"
        pixmap = qta.icon('fa5s.exclamation-triangle', color=error_hex).pixmap(32, 32)
        self._icon_label.setPixmap(pixmap)

    def _apply_state_text(self) -> None:
        plan = self._view_controller.build_update_status_card_plan(
            state=self._state,
            version=self._state_version,
            source=self._state_source,
            message=self._state_message,
            elapsed=self._state_elapsed,
            app_version=APP_VERSION,
            language=self._ui_language,
        )
        self.title_label.setText(plan.title)
        self.subtitle_label.setText(plan.subtitle)
        self.check_btn.setText(plan.button_text)

    def _apply_transition_plan(self, plan) -> None:
        self._is_checking = plan.is_checking
        self._state = plan.state
        self._state_version = plan.state_version
        self._state_source = plan.state_source
        self._state_message = plan.state_message
        self._state_elapsed = plan.state_elapsed

        if plan.icon_mode == "error":
            self._set_error_icon()
        elif plan.icon_mode == "idle":
            self._set_icon_idle()

        self._apply_state_text()

        if plan.loading_mode == "start":
            self.check_btn.start_loading()
        elif plan.loading_mode == "stop":
            self.check_btn.stop_loading(plan.stop_loading_text)

        if plan.check_enabled is not None:
            self.check_btn.setEnabled(plan.check_enabled)

    def start_checking(self):
        plan = self._view_controller.build_update_status_transition_plan(
            target_state="checking",
            language=self._ui_language,
        )
        self._apply_transition_plan(plan)

    def stop_checking(self, found_update: bool = False, version: str = ""):
        plan = self._view_controller.build_update_status_transition_plan(
            target_state="result",
            language=self._ui_language,
            version=version,
            found_update=found_update,
        )
        self._apply_transition_plan(plan)

    def set_error(self, message: str):
        plan = self._view_controller.build_update_status_transition_plan(
            target_state="error",
            language=self._ui_language,
            message=message,
        )
        self._apply_transition_plan(plan)

    def show_found_update(self, version: str, source: str) -> None:
        plan = self._view_controller.build_update_status_transition_plan(
            target_state="found",
            language=self._ui_language,
            version=version,
            source=source,
        )
        self._apply_transition_plan(plan)

    def show_download_error(self) -> None:
        plan = self._view_controller.build_update_status_transition_plan(
            target_state="download_error",
            language=self._ui_language,
        )
        self._apply_transition_plan(plan)

    def show_deferred(self, version: str) -> None:
        plan = self._view_controller.build_update_status_transition_plan(
            target_state="deferred",
            language=self._ui_language,
            version=version,
        )
        self._apply_transition_plan(plan)

    def show_checked_ago(self, elapsed: float) -> None:
        plan = self._view_controller.build_update_status_transition_plan(
            target_state="checked_ago",
            language=self._ui_language,
            elapsed=elapsed,
        )
        self._apply_transition_plan(plan)

    def show_manual_hint(self) -> None:
        plan = self._view_controller.build_update_status_transition_plan(
            target_state="manual",
            language=self._ui_language,
        )
        self._apply_transition_plan(plan)

    def show_auto_enabled_hint(self) -> None:
        plan = self._view_controller.build_update_status_transition_plan(
            target_state="auto_on",
            language=self._ui_language,
        )
        self._apply_transition_plan(plan)

    def set_ui_language(self, language: str) -> None:
        self._ui_language = language
        self._apply_state_text()


# ═══════════════════════════════════════════════════════════════════════════════
# КАРТОЧКА CHANGELOG
# ═══════════════════════════════════════════════════════════════════════════════

class ChangelogCard(CardWidget):
    """Карточка с changelog обновления и встроенным прогрессом скачивания"""

    install_clicked = pyqtSignal()
    dismiss_clicked = pyqtSignal()

    def __init__(self, parent=None, *, language: str = "ru"):
        super().__init__(parent)
        self.setObjectName("changelogCard")
        self._ui_language = language
        self._is_downloading = False
        self._download_start_time = 0
        self._last_bytes = 0
        self._last_speed_time = 0.0
        self._last_speed_bytes = 0
        self._smoothed_speed = 0.0
        self._download_percent = 0
        self._download_done_bytes = 0
        self._download_total_bytes = 0
        self._download_speed_kb: float | None = None
        self._download_eta_seconds: float | None = None
        self._download_error_text = ""
        self._tokens = get_theme_tokens()
        self._icon_kind = "update"
        self._raw_changelog = ""
        self._raw_version = ""
        self._mode = "idle"
        self._view_controller = UpdatePageViewController()
        self._build_ui()
        self._theme_refresh = ThemeRefreshController(self, self._apply_theme)
        self.hide()

    def _tr(self, key: str, default: str) -> str:
        return tr_catalog(key, language=self._ui_language, default=default)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # Header
        header = QHBoxLayout()

        self.icon_label = QLabel()
        header.addWidget(self.icon_label)

        self.title_label = StrongBodyLabel(
            self._tr("page.servers.changelog.title.available", "Доступно обновление")
        )
        header.addWidget(self.title_label)
        header.addStretch()

        self.close_btn = TransparentToolButton()
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self._on_dismiss)
        header.addWidget(self.close_btn)

        layout.addLayout(header)

        # Version / status
        self.version_label = BodyLabel()
        layout.addWidget(self.version_label)

        # Changelog text (clickable links)
        self.changelog_text = QLabel()
        self.changelog_text.setWordWrap(True)
        self.changelog_text.setTextFormat(Qt.TextFormat.RichText)
        self.changelog_text.setOpenExternalLinks(True)
        self.changelog_text.linkActivated.connect(lambda url: __import__('webbrowser').open(url))
        layout.addWidget(self.changelog_text)

        # ─── Progress section (hidden by default) ────────────────────────────
        self.progress_widget = QWidget()
        progress_layout = QVBoxLayout(self.progress_widget)
        progress_layout.setContentsMargins(0, 4, 0, 4)
        progress_layout.setSpacing(6)

        # Indeterminate bar: visible while "preparing" (0 bytes yet received).
        # ProgressBar at setValue(0) has zero-width fill and looks invisible.
        if _HAS_FLUENT:
            self._progress_indeterminate = IndeterminateProgressBar(start=False)
            progress_layout.addWidget(self._progress_indeterminate)
        else:
            self._progress_indeterminate = None

        # Determinate bar: shown once actual bytes start flowing.
        if _HAS_FLUENT and ProgressBar is not None:
            self.progress_bar = ProgressBar(useAni=False)
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
        else:
            from PyQt6.QtWidgets import QProgressBar as _QProgressBar
            self.progress_bar = _QProgressBar()
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setFixedHeight(4)
        self.progress_bar.hide()  # Hidden until bytes arrive

        progress_layout.addWidget(self.progress_bar)

        status_row = QHBoxLayout()
        status_row.setSpacing(16)

        self.speed_label = CaptionLabel(
            self._tr("page.servers.changelog.progress.speed_unknown", "Скорость: —")
        )
        status_row.addWidget(self.speed_label)

        self.progress_label = CaptionLabel("0%")
        status_row.addWidget(self.progress_label)

        self.eta_label = CaptionLabel(
            self._tr("page.servers.changelog.progress.eta_unknown", "Осталось: —")
        )
        status_row.addWidget(self.eta_label)

        status_row.addStretch()
        progress_layout.addLayout(status_row)

        self.progress_widget.hide()
        layout.addWidget(self.progress_widget)

        # ─── Buttons ─────────────────────────────────────────────────────────
        self.buttons_widget = QWidget()
        buttons_layout = QHBoxLayout(self.buttons_widget)
        buttons_layout.setContentsMargins(0, 4, 0, 0)
        buttons_layout.setSpacing(8)
        buttons_layout.addStretch()

        self.later_btn = PushButton()
        self.later_btn.setText(self._tr("page.servers.changelog.button.later", "Позже"))
        self.later_btn.setFixedHeight(32)
        self.later_btn.clicked.connect(self._on_dismiss)
        buttons_layout.addWidget(self.later_btn)

        self.install_btn = PrimaryActionButton(
            self._tr("page.servers.changelog.button.install", "Установить"),
            "fa5s.download",
        )
        self.install_btn.clicked.connect(self._on_install)
        buttons_layout.addWidget(self.install_btn)

        layout.addWidget(self.buttons_widget)

        self._apply_page_theme(force=True)

    def _apply_theme(self, theme_name: str | None = None) -> None:
        self._tokens = get_theme_tokens(theme_name)
        tokens = self._tokens

        self.title_label.setStyleSheet(f"color: {tokens.accent_hex};")
        self.changelog_text.setStyleSheet(f"color: {tokens.fg_muted}; font-size: 12px; padding: 4px 0;")

        self.close_btn.setIcon(qta.icon('fa5s.times', color=tokens.fg_faint))
        self.install_btn.setIcon(qta.icon('fa5s.download', color="#ffffff"))

        icon_name = 'fa5s.arrow-circle-up' if self._icon_kind == "update" else 'fa5s.download'
        self.icon_label.setPixmap(qta.icon(icon_name, color=tokens.accent_hex).pixmap(24, 24))

        if self._raw_changelog:
            try:
                self.changelog_text.setText(self._view_controller.make_links_clickable(self._raw_changelog, tokens.accent_hex))
            except Exception:
                pass

    def show_update(self, version: str, changelog: str):
        if self._is_downloading:
            return
        plan = self._view_controller.build_changelog_update_plan(
            version=version,
            changelog=changelog,
            app_version=APP_VERSION,
            accent_hex=self._tokens.accent_hex,
            language=self._ui_language,
        )
        self._mode = plan.mode
        self._is_downloading = plan.is_downloading
        self._icon_kind = plan.icon_kind
        self._raw_version = plan.raw_version
        self._download_error_text = plan.download_error_text
        self.version_label.setText(plan.version_text)
        self.title_label.setText(plan.title_text)
        self.install_btn.setText(plan.install_text)
        self._raw_changelog = plan.raw_changelog
        self.changelog_text.setText(plan.changelog_html)
        self.changelog_text.setVisible(plan.changelog_visible)
        self.progress_widget.setVisible(plan.progress_visible)
        self.buttons_widget.setVisible(plan.buttons_visible)
        self.close_btn.setVisible(plan.close_visible)
        self.show()
        self._apply_theme()

    def start_download(self, version: str):
        plan = self._view_controller.build_changelog_download_start_plan(
            version=version,
            language=self._ui_language,
            now=time.time(),
        )
        self._mode = plan.mode
        self._is_downloading = plan.is_downloading
        self._icon_kind = plan.icon_kind
        self._raw_version = plan.raw_version
        self._download_start_time = plan.download_start_time
        self._last_bytes = plan.last_bytes
        self._last_speed_time = plan.last_speed_time
        self._last_speed_bytes = plan.last_speed_bytes
        self._smoothed_speed = plan.smoothed_speed
        self._download_percent = plan.download_percent
        self._download_done_bytes = plan.download_done_bytes
        self._download_total_bytes = plan.download_total_bytes
        self._download_speed_kb = plan.download_speed_kb
        self._download_eta_seconds = plan.download_eta_seconds
        self._download_error_text = plan.download_error_text
        self.title_label.setText(plan.title_text)
        self._apply_theme()
        self.version_label.setText(plan.version_text)
        self.changelog_text.hide()
        self.buttons_widget.setVisible(plan.buttons_visible)
        self.close_btn.setVisible(plan.close_visible)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(plan.show_progress_bar)
        if self._progress_indeterminate is not None and plan.show_indeterminate:
            self._progress_indeterminate.start()
            self._progress_indeterminate.show()
        self.progress_label.setText(plan.progress_label_text)
        self.speed_label.setText(plan.speed_label_text)
        self.eta_label.setText(plan.eta_label_text)
        self.progress_widget.setVisible(plan.progress_visible)

    def update_progress(self, percent: int, done_bytes: int, total_bytes: int):
        plan = self._view_controller.build_changelog_progress_plan(
            percent=percent,
            done_bytes=done_bytes,
            total_bytes=total_bytes,
            last_speed_time=self._last_speed_time,
            last_speed_bytes=self._last_speed_bytes,
            smoothed_speed=self._smoothed_speed,
            language=self._ui_language,
            now=time.time(),
            progress_bar_visible=self.progress_bar.isVisible(),
        )
        self._mode = plan.mode
        self._download_percent = plan.download_percent
        self._download_done_bytes = plan.download_done_bytes
        self._download_total_bytes = plan.download_total_bytes
        self._last_bytes = plan.last_bytes
        self._last_speed_time = plan.last_speed_time
        self._last_speed_bytes = plan.last_speed_bytes
        self._smoothed_speed = plan.smoothed_speed
        self._download_speed_kb = plan.download_speed_kb
        self._download_eta_seconds = plan.download_eta_seconds

        if plan.hide_indeterminate and self._progress_indeterminate is not None and self._progress_indeterminate.isVisible():
            try:
                self._progress_indeterminate.stop()
                self._progress_indeterminate.hide()
            except Exception:
                pass
        self.progress_bar.setVisible(plan.show_progress_bar)
        self.progress_bar.setValue(plan.progress_value)
        self.progress_label.setText(plan.progress_label_text)
        self.version_label.setText(plan.version_text)
        self.speed_label.setText(plan.speed_label_text)
        self.eta_label.setText(plan.eta_label_text)

    def download_complete(self):
        plan = self._view_controller.build_changelog_terminal_plan(
            kind="installing",
            language=self._ui_language,
            app_version=APP_VERSION,
        )
        self._mode = plan.mode
        self._is_downloading = plan.is_downloading
        self._icon_kind = plan.icon_kind
        if self._progress_indeterminate is not None:
            try:
                self._progress_indeterminate.stop()
                self._progress_indeterminate.hide()
            except Exception:
                pass
        self.progress_bar.setVisible(plan.progress_visible)
        self.title_label.setText(plan.title_text)
        self.version_label.setText(plan.version_text)
        self.progress_bar.setValue(plan.progress_value)
        self.progress_label.setText(plan.progress_label_text)
        self.speed_label.setText(plan.speed_label_text)
        self.eta_label.setText(plan.eta_label_text)

    def download_failed(self, error: str):
        plan = self._view_controller.build_changelog_terminal_plan(
            kind="failed",
            language=self._ui_language,
            app_version=APP_VERSION,
            download_error_text=error,
        )
        self._mode = plan.mode
        self._is_downloading = plan.is_downloading
        self._download_error_text = plan.error_text
        self._icon_kind = plan.icon_kind
        if self._progress_indeterminate is not None:
            try:
                self._progress_indeterminate.stop()
                self._progress_indeterminate.hide()
            except Exception:
                pass

        self.title_label.setText(plan.title_text)
        if plan.title_color:
            self.title_label.setStyleSheet(f"color: {plan.title_color};")
        self.icon_label.setPixmap(qta.icon('fa5s.exclamation-triangle', color='#ff6b6b').pixmap(24, 24))
        self.version_label.setText(plan.version_text)
        self.progress_widget.setVisible(plan.progress_visible)
        self.buttons_widget.setVisible(plan.buttons_visible)
        self.close_btn.setVisible(plan.close_visible)
        self.install_btn.setText(plan.install_text)

    def set_ui_language(self, language: str) -> None:
        self._ui_language = language
        self.later_btn.setText(self._tr("page.servers.changelog.button.later", "Позже"))
        plan = self._view_controller.build_changelog_terminal_plan(
            kind=self._mode if self._mode in {"downloading", "installing", "failed"} else "update",
            language=self._ui_language,
            app_version=APP_VERSION,
            raw_version=self._raw_version,
            download_error_text=self._download_error_text,
            download_done_bytes=self._download_done_bytes,
            download_total_bytes=self._download_total_bytes,
            download_percent=self._download_percent,
            download_speed_kb=self._download_speed_kb,
            download_eta_seconds=self._download_eta_seconds,
        )
        self.title_label.setText(plan.title_text)
        self.version_label.setText(plan.version_text)
        self.progress_label.setText(plan.progress_label_text)
        self.speed_label.setText(plan.speed_label_text)
        self.eta_label.setText(plan.eta_label_text)
        self.install_btn.setText(plan.install_text)
        self._apply_theme()

    def _on_install(self):
        self.install_clicked.emit()

    def _on_dismiss(self):
        self.hide()
        self.dismiss_clicked.emit()


# ═══════════════════════════════════════════════════════════════════════════════
# ОСНОВНАЯ СТРАНИЦА
# ═══════════════════════════════════════════════════════════════════════════════

class ServersPage(BasePage):
    """Страница мониторинга серверов обновлений"""

    update_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(
            "Серверы",
            "Мониторинг серверов обновлений",
            parent,
            title_key="page.servers.title",
            subtitle_key="page.servers.subtitle",
        )

        self._tokens = get_theme_tokens()
        self._server_status_map: dict[str, dict] = {}
        self._server_row_map: dict[str, int] = {}
        self._update_controller = UpdatePageController(self)
        self._view_controller = UpdatePageViewController()

        self.enable_deferred_ui_build()

    def _tr(self, key: str, default: str) -> str:
        return tr_catalog(key, language=self._ui_language, default=default)

    def _apply_page_theme(self, tokens=None, force: bool = False) -> None:
        _ = force
        self._tokens = tokens or get_theme_tokens()
        tokens = self._tokens

        if hasattr(self, "servers_table"):
            try:
                accent_qcolor = QColor(tokens.accent_hex)
                for r in range(self.servers_table.rowCount()):
                    item = self.servers_table.item(r, 0)
                    if item and (item.text() or "").lstrip().startswith("⭐"):
                        item.setForeground(accent_qcolor)
            except Exception:
                pass

    def _render_server_row(self, row: int, server_name: str, status: dict) -> None:
        plan = self._view_controller.build_server_row_plan(
            row_server_name=server_name,
            status=status,
            channel=CHANNEL,
            language=self._ui_language,
        )
        name_item = QTableWidgetItem(plan.server_text)
        if plan.server_accent:
            name_item.setForeground(QColor(self._tokens.accent_hex))
        self.servers_table.setItem(row, 0, name_item)

        status_item = QTableWidgetItem(plan.status_text)
        status_item.setForeground(QColor(*plan.status_color))
        self.servers_table.setItem(row, 1, status_item)
        self.servers_table.setItem(row, 2, QTableWidgetItem(plan.time_text))
        self.servers_table.setItem(row, 3, QTableWidgetItem(plan.extra_text))

    def _refresh_server_rows(self) -> None:
        for server_name, row in self._server_row_map.items():
            if row < 0 or row >= self.servers_table.rowCount():
                continue
            status = self._server_status_map.get(server_name)
            if not status:
                continue
            self._render_server_row(row, server_name, status)

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)

        self.update_card.set_ui_language(self._ui_language)
        self.changelog_card.set_ui_language(self._ui_language)

        self._back_btn.setText(self._tr("page.servers.back.about", "О программе"))
        self._page_title_label.setText(self._tr("page.servers.title", "Серверы"))
        self._servers_title_label.setText(self._tr("page.servers.section.update_servers", "Серверы обновлений"))
        self._legend_active_label.setText(self._tr("page.servers.legend.active", "⭐ активный"))
        self.servers_table.setHorizontalHeaderLabels([
            self._tr("page.servers.table.header.server", "Сервер"),
            self._tr("page.servers.table.header.status", "Статус"),
            self._tr("page.servers.table.header.time", "Время"),
            self._tr("page.servers.table.header.versions", "Версии"),
        ])

        self._settings_card.set_title(self._tr("page.servers.settings.title", "Настройки"))
        title_label = getattr(self._settings_card, "titleLabel", None)
        if title_label is not None:
            title_label.setText(self._tr("page.servers.settings.title", "Настройки"))
        if self._toggle_label is not None:
            self._toggle_label.setText(self._tr("page.servers.settings.auto_check", "Проверять обновления при запуске"))
        if hasattr(self, "_auto_check_card") and self._auto_check_card is not None:
            self._auto_check_card.set_texts(
                self._tr("page.servers.settings.auto_check", "Проверять обновления при запуске"),
                self._tr(
                    "page.servers.settings.auto_check.description",
                    "Автоматически проверять наличие обновлений при старте приложения.",
                ),
            )
        self._version_info_label.setText(
            self._tr("page.servers.settings.version_channel_template", "v{version} · {channel}").format(
                version=APP_VERSION,
                channel=CHANNEL,
            )
        )

        self._tg_card.set_title(self._tr("page.servers.telegram.title", "Проблемы с обновлением?"))
        if self._tg_info_label is not None:
            self._tg_info_label.setText(
                self._tr(
                    "page.servers.telegram.info",
                    "Если возникают трудности с автоматическим обновлением, все версии программы выкладываются в Telegram канале.",
                )
            )
        else:
            try:
                self._tg_card.setContent(
                    self._tr(
                        "page.servers.telegram.info",
                        "Если возникают трудности с автоматическим обновлением, все версии программы выкладываются в Telegram канале.",
                    )
                )
            except Exception:
                pass
        self._tg_btn.setText(self._tr("page.servers.telegram.button.open_channel", "Открыть Telegram канал"))

        self._refresh_server_rows()

    def _build_ui(self):
        # ── Custom header (back link + title) ───────────────────────────
        # Hide base title/subtitle and prevent _retranslate_base_texts
        # from re-showing them (it calls setVisible(bool(text))).
        if self.title_label is not None:
            self._title_key = None
            self.title_label.setText("")
            self.title_label.hide()
        if self.subtitle_label is not None:
            self._subtitle_key = None
            self.subtitle_label.setText("")
            self.subtitle_label.hide()

        header = QWidget()
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 8)
        header_layout.setSpacing(4)

        back_row = QHBoxLayout()
        back_row.setContentsMargins(0, 0, 0, 0)
        back_row.setSpacing(0)

        self._back_btn = TransparentPushButton(parent=self)
        self._back_btn.setText(self._tr("page.servers.back.about", "О программе"))
        self._back_btn.setIcon(qta.icon("fa5s.chevron-left", color="#888"))
        self._back_btn.setIconSize(QSize(12, 12))
        self._back_btn.clicked.connect(self._on_back_to_about)
        back_row.addWidget(self._back_btn)
        back_row.addStretch()
        header_layout.addLayout(back_row)

        try:
            from qfluentwidgets import TitleLabel as _TitleLabel
            self._page_title_label = _TitleLabel(self._tr("page.servers.title", "Серверы"))
        except Exception:
            self._page_title_label = QLabel(self._tr("page.servers.title", "Серверы"))
        header_layout.addWidget(self._page_title_label)

        self.add_widget(header)

        # Update status card
        self.update_card = UpdateStatusCard(language=self._ui_language)
        self.update_card.check_clicked.connect(self._request_check_updates)
        self.add_widget(self.update_card)

        # Changelog card (hidden by default)
        self.changelog_card = ChangelogCard(language=self._ui_language)
        self.changelog_card.install_clicked.connect(self._request_install_update)
        self.changelog_card.dismiss_clicked.connect(self._request_dismiss_update)
        self.add_widget(self.changelog_card)

        # Table header row
        servers_header = QHBoxLayout()
        self._servers_title_label = StrongBodyLabel(
            self._tr("page.servers.section.update_servers", "Серверы обновлений")
        )
        servers_header.addWidget(self._servers_title_label)
        servers_header.addStretch()

        self._legend_active_label = CaptionLabel(self._tr("page.servers.legend.active", "⭐ активный"))
        servers_header.addWidget(self._legend_active_label)

        header_widget = QWidget()
        header_widget.setLayout(servers_header)
        self.add_widget(header_widget)

        # Servers table
        self.servers_table = TableWidget()
        self.servers_table.setColumnCount(4)
        self.servers_table.setRowCount(0)
        self.servers_table.setBorderVisible(True)
        self.servers_table.setBorderRadius(8)
        self.servers_table.setHorizontalHeaderLabels([
            self._tr("page.servers.table.header.server", "Сервер"),
            self._tr("page.servers.table.header.status", "Статус"),
            self._tr("page.servers.table.header.time", "Время"),
            self._tr("page.servers.table.header.versions", "Версии"),
        ])
        header = self.servers_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.servers_table.verticalHeader().setVisible(False)
        self.servers_table.verticalHeader().setDefaultSectionSize(36)
        self.servers_table.setEditTriggers(TableWidget.EditTrigger.NoEditTriggers)
        self.servers_table.setSelectionBehavior(TableWidget.SelectionBehavior.SelectRows)
        self.add_widget(self.servers_table, stretch=1)

        # Settings card
        if SettingCardGroup is not None and _HAS_FLUENT:
            self._settings_card = SettingCardGroup(self._tr("page.servers.settings.title", "Настройки"), self.content)

            self._auto_check_card = Win11ToggleRow(
                "fa5s.sync-alt",
                self._tr("page.servers.settings.auto_check", "Проверять обновления при запуске"),
                self._tr(
                    "page.servers.settings.auto_check.description",
                    "Автоматически проверять наличие обновлений при старте приложения.",
                ),
                get_theme_tokens().accent_hex,
            )
            self._auto_check_card.setChecked(self._update_controller.auto_check_enabled, block_signals=True)
            self._auto_check_card.toggled.connect(self._on_auto_check_toggled)
            self.auto_check_toggle = self._auto_check_card.toggle
            self._settings_card.addSettingCard(self._auto_check_card)

            version_card = SettingsCard()
            version_layout = QHBoxLayout()
            version_layout.setContentsMargins(10, 6, 12, 6)
            version_layout.setSpacing(8)
            self._toggle_label = None
            self._version_info_label = CaptionLabel(
                self._tr("page.servers.settings.version_channel_template", "v{version} · {channel}").format(
                    version=APP_VERSION,
                    channel=CHANNEL,
                )
            )
            version_layout.addWidget(self._version_info_label)
            version_layout.addStretch()
            version_card.add_layout(version_layout)
            self._settings_card.addSettingCard(version_card)
        else:
            self._settings_card = SettingsCard(self._tr("page.servers.settings.title", "Настройки"))
            settings_layout = QVBoxLayout()
            settings_layout.setSpacing(12)

            toggle_row = QHBoxLayout()
            toggle_row.setSpacing(12)

            self.auto_check_toggle = SwitchButton()
            self.auto_check_toggle.setChecked(self._update_controller.auto_check_enabled)
            if _HAS_FLUENT:
                self.auto_check_toggle.checkedChanged.connect(self._on_auto_check_toggled)
            else:
                self.auto_check_toggle.toggled.connect(self._on_auto_check_toggled)
            toggle_row.addWidget(self.auto_check_toggle)

            self._toggle_label = BodyLabel(
                self._tr("page.servers.settings.auto_check", "Проверять обновления при запуске")
            )
            toggle_row.addWidget(self._toggle_label)
            toggle_row.addStretch()

            self._version_info_label = CaptionLabel(
                self._tr("page.servers.settings.version_channel_template", "v{version} · {channel}").format(
                    version=APP_VERSION,
                    channel=CHANNEL,
                )
            )
            toggle_row.addWidget(self._version_info_label)

            settings_layout.addLayout(toggle_row)
            self._settings_card.add_layout(settings_layout)
        self.add_widget(self._settings_card)

        # Telegram card
        if PushSettingCard is not None and _HAS_FLUENT:
            self._tg_info_label = None
            self._tg_card = PushSettingCard(
                self._tr("page.servers.telegram.button.open_channel", "Открыть Telegram канал"),
                qta.icon("fa5b.telegram-plane", color=tokens.accent_hex),
                self._tr("page.servers.telegram.title", "Проблемы с обновлением?"),
                self._tr(
                    "page.servers.telegram.info",
                    "Если возникают трудности с автоматическим обновлением, все версии программы выкладываются в Telegram канале.",
                ),
            )
            self._tg_card.clicked.connect(self._open_telegram_channel)
            self._tg_btn = self._tg_card.button
        else:
            self._tg_card = SettingsCard(self._tr("page.servers.telegram.title", "Проблемы с обновлением?"))
            tg_layout = QVBoxLayout()
            tg_layout.setSpacing(12)

            self._tg_info_label = BodyLabel(
                self._tr(
                    "page.servers.telegram.info",
                    "Если возникают трудности с автоматическим обновлением, все версии программы выкладываются в Telegram канале.",
                )
            )
            self._tg_info_label.setWordWrap(True)
            tg_layout.addWidget(self._tg_info_label)

            tg_btn_row = QHBoxLayout()
            self._tg_btn = ActionButton(
                self._tr("page.servers.telegram.button.open_channel", "Открыть Telegram канал"),
                "fa5b.telegram-plane",
            )
            self._tg_btn.clicked.connect(self._open_telegram_channel)
            tg_btn_row.addWidget(self._tg_btn)
            tg_btn_row.addStretch()

            tg_layout.addLayout(tg_btn_row)
            self._tg_card.add_layout(tg_layout)
        self.add_widget(self._tg_card)

        self._apply_page_theme(force=True)

    def on_page_activated(self, first_show: bool) -> None:
        _ = first_show
        self._update_controller.on_page_shown()

    def get_ui_language(self) -> str:
        return self._ui_language

    def reset_server_rows(self) -> None:
        self.servers_table.setRowCount(0)
        self._server_row_map.clear()
        self._server_status_map.clear()

    def upsert_server_status(self, server_name: str, status: dict) -> None:
        row = self._server_row_map.get(server_name)
        if row is None:
            row = self.servers_table.rowCount()
            self.servers_table.insertRow(row)
            self._server_row_map[server_name] = row

        self._server_status_map[server_name] = dict(status or {})
        self._render_server_row(row, server_name, self._server_status_map[server_name])

    def start_checking(self) -> None:
        self.update_card.start_checking()

    def finish_checking(self, found_update: bool, version: str) -> None:
        self.update_card.stop_checking(found_update, version)

    def show_found_update_source(self, version: str, source: str) -> None:
        self.update_card.show_found_update(version, source)

    def show_update_offer(self, version: str, release_notes: str) -> None:
        self.changelog_card.show_update(version, release_notes)

    def hide_update_offer(self) -> None:
        self.changelog_card.hide()

    def is_update_download_in_progress(self) -> bool:
        return bool(getattr(self.changelog_card, "_is_downloading", False))

    def start_update_download(self, version: str) -> None:
        self.changelog_card.start_download(version)

    def update_download_progress(self, percent: int, done_bytes: int, total_bytes: int) -> None:
        self.changelog_card.update_progress(percent, done_bytes, total_bytes)

    def mark_update_download_complete(self) -> None:
        self.changelog_card.download_complete()

    def mark_update_download_failed(self, error: str) -> None:
        self.changelog_card.download_failed(error)

    def show_update_download_error(self) -> None:
        self.update_card.show_download_error()

    def show_update_deferred(self, version: str) -> None:
        self.update_card.show_deferred(version)

    def show_checked_ago(self, elapsed: float) -> None:
        self.update_card.show_checked_ago(elapsed)

    def show_manual_hint(self) -> None:
        self.update_card.show_manual_hint()

    def show_auto_enabled_hint(self) -> None:
        self.update_card.show_auto_enabled_hint()

    def hide_update_status_card(self) -> None:
        self.update_card.hide()

    def show_update_status_card(self) -> None:
        self.update_card.show()

    def set_update_check_enabled(self, enabled: bool) -> None:
        self.update_card.check_btn.setEnabled(bool(enabled))

    def present_startup_update(self, version: str, release_notes: str, *, install_after_show: bool = True) -> bool:
        return self._update_controller.present_startup_update(
            version,
            release_notes,
            install_after_show=install_after_show,
        )

    def _request_check_updates(self) -> None:
        self._update_controller.request_manual_check()

    def _request_install_update(self) -> None:
        self._update_controller.install_update()

    def _request_dismiss_update(self) -> None:
        self._update_controller.dismiss_update()

    def _open_telegram_channel(self):
        result = self._view_controller.open_update_channel(CHANNEL)
        if not result.ok:
            try:
                from qfluentwidgets import InfoBar
            except Exception:
                InfoBar = None
            if InfoBar is not None:
                InfoBar.warning(
                    title=self._tr("page.servers.telegram.error.title", "Ошибка"),
                    content=self._tr(
                        "page.servers.telegram.error.open_channel",
                        "Не удалось открыть Telegram канал:\n{error}",
                    ).format(error=result.message),
                    parent=self.window(),
                )

    def _on_back_to_about(self):
        try:
            from ui.page_names import PageName
            win = self.window()
            if hasattr(win, 'show_page'):
                win.show_page(PageName.ABOUT)
        except Exception:
            pass

    def _on_auto_check_toggled(self, enabled: bool):
        self._update_controller.set_auto_check_enabled(bool(enabled))

    def cleanup(self):
        self._update_controller.cleanup()
