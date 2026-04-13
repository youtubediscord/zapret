"""Update status card for Servers page."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QLabel, QHBoxLayout, QVBoxLayout, QWidget

from config.build_info import APP_VERSION

from ui.text_catalog import tr as tr_catalog
from ui.theme import get_cached_qta_pixmap, get_theme_tokens
from ui.theme_refresh import ThemeRefreshController
from updater.update_page_view_controller import UpdatePageViewController

try:
    from qfluentwidgets import (
        CaptionLabel,
        CardWidget,
        IndeterminateProgressRing,
        PushButton,
        StrongBodyLabel,
    )
    HAS_FLUENT = True
except ImportError:
    from PyQt6.QtWidgets import QFrame as CardWidget, QPushButton

    CaptionLabel = QLabel
    StrongBodyLabel = QLabel
    IndeterminateProgressRing = None
    HAS_FLUENT = False


class IndeterminateProgressPushButton(PushButton):
    """PushButton с IndeterminateProgressRing внутри."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stored_text = ""
        self._ring = None
        if HAS_FLUENT and IndeterminateProgressRing is not None:
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


class UpdateStatusCard(CardWidget):
    """Карточка статуса обновлений."""

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
        self._build_ui()
        self._theme_refresh = ThemeRefreshController(self, self._apply_theme)

    def _tr(self, key: str, default: str) -> str:
        return tr_catalog(key, language=self._ui_language, default=default)

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(20, 16, 20, 16)
        content_layout.setSpacing(16)

        self._icon_label = QLabel()
        self._icon_label.setFixedSize(40, 40)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(self._icon_label)

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

        self.check_btn = IndeterminateProgressPushButton()
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
        pixmap = get_cached_qta_pixmap('fa5s.sync-alt', color=self._tokens.accent_hex, size=32)
        self._icon_label.setPixmap(pixmap)

    def _on_check_clicked(self):
        self.check_clicked.emit()

    def _set_error_icon(self) -> None:
        tokens = self._tokens
        error_hex = "#dc2626" if tokens.is_light else "#f87171"
        pixmap = get_cached_qta_pixmap('fa5s.exclamation-triangle', color=error_hex, size=32)
        self._icon_label.setPixmap(pixmap)

    def _apply_state_text(self) -> None:
        plan = UpdatePageViewController.build_update_status_card_plan(
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
        plan = UpdatePageViewController.build_update_status_transition_plan(
            target_state="checking",
            language=self._ui_language,
        )
        self._apply_transition_plan(plan)

    def stop_checking(self, found_update: bool = False, version: str = ""):
        plan = UpdatePageViewController.build_update_status_transition_plan(
            target_state="result",
            language=self._ui_language,
            version=version,
            found_update=found_update,
        )
        self._apply_transition_plan(plan)

    def set_error(self, message: str):
        plan = UpdatePageViewController.build_update_status_transition_plan(
            target_state="error",
            language=self._ui_language,
            message=message,
        )
        self._apply_transition_plan(plan)

    def show_found_update(self, version: str, source: str) -> None:
        plan = UpdatePageViewController.build_update_status_transition_plan(
            target_state="found",
            language=self._ui_language,
            version=version,
            source=source,
        )
        self._apply_transition_plan(plan)

    def show_download_error(self) -> None:
        plan = UpdatePageViewController.build_update_status_transition_plan(
            target_state="download_error",
            language=self._ui_language,
        )
        self._apply_transition_plan(plan)

    def show_deferred(self, version: str) -> None:
        plan = UpdatePageViewController.build_update_status_transition_plan(
            target_state="deferred",
            language=self._ui_language,
            version=version,
        )
        self._apply_transition_plan(plan)

    def show_checked_ago(self, elapsed: float) -> None:
        plan = UpdatePageViewController.build_update_status_transition_plan(
            target_state="checked_ago",
            language=self._ui_language,
            elapsed=elapsed,
        )
        self._apply_transition_plan(plan)

    def show_manual_hint(self) -> None:
        plan = UpdatePageViewController.build_update_status_transition_plan(
            target_state="manual",
            language=self._ui_language,
        )
        self._apply_transition_plan(plan)

    def show_auto_enabled_hint(self) -> None:
        plan = UpdatePageViewController.build_update_status_transition_plan(
            target_state="auto_on",
            language=self._ui_language,
        )
        self._apply_transition_plan(plan)

    def set_ui_language(self, language: str) -> None:
        self._ui_language = language
        self._apply_state_text()
