"""Changelog card for Servers page."""

from __future__ import annotations

import time

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget


from config.build_info import APP_VERSION

from app.ui_texts import tr as tr_catalog
from ui.accessibility import set_control_accessibility, set_state_text
from ui.theme import get_cached_qta_pixmap, get_theme_tokens, get_themed_qta_icon
from ui.theme_refresh import ThemeRefreshBinding
import updater.update_page_plans as update_page_plans
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CardWidget,
    FluentIcon,
    IndeterminateProgressBar,
    PrimaryPushButton,
    ProgressBar,
    PushButton,
    StrongBodyLabel,
    TransparentToolButton,
)


class ChangelogCard(CardWidget):
    """Карточка changelog обновления."""

    install_clicked = pyqtSignal()
    dismiss_clicked = pyqtSignal()

    def __init__(self, parent=None, *, language: str = "ru", open_url=None):
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
        self._open_url = open_url or (lambda _url: None)
        self._build_ui()
        self._theme_refresh = ThemeRefreshBinding(self, self._apply_theme)
        self.hide()

    def _tr(self, key: str, default: str) -> str:
        return tr_catalog(key, language=self._ui_language, default=default)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

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
        set_control_accessibility(
            self.close_btn,
            name="Закрыть уведомление об обновлении",
            description="Скрывает карточку обновления.",
        )
        set_state_text(self.close_btn, "Закрыть уведомление об обновлении")
        self.close_btn.clicked.connect(self._on_dismiss)
        header.addWidget(self.close_btn)

        layout.addLayout(header)

        self.version_label = BodyLabel()
        layout.addWidget(self.version_label)

        self.changelog_text = QLabel()
        self.changelog_text.setWordWrap(True)
        self.changelog_text.setTextFormat(Qt.TextFormat.RichText)
        self.changelog_text.setOpenExternalLinks(True)
        self.changelog_text.linkActivated.connect(self._open_url)
        layout.addWidget(self.changelog_text)

        self.progress_widget = QWidget()
        progress_layout = QVBoxLayout(self.progress_widget)
        progress_layout.setContentsMargins(0, 4, 0, 4)
        progress_layout.setSpacing(6)

        self._progress_indeterminate = IndeterminateProgressBar(start=False)
        progress_layout.addWidget(self._progress_indeterminate)

        self.progress_bar = ProgressBar(useAni=False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.hide()
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

        self.buttons_widget = QWidget()
        buttons_layout = QHBoxLayout(self.buttons_widget)
        buttons_layout.setContentsMargins(0, 4, 0, 0)
        buttons_layout.setSpacing(8)
        buttons_layout.addStretch()

        self.later_btn = PushButton()
        self.later_btn.setText(self._tr("page.servers.changelog.button.later", "Позже"))
        self.later_btn.setFixedHeight(32)
        set_control_accessibility(
            self.later_btn,
            name="Отложить обновление",
            description="Скрывает карточку обновления. Установку можно запустить позже.",
        )
        set_state_text(self.later_btn, "Отложить обновление")
        self.later_btn.clicked.connect(self._on_dismiss)
        buttons_layout.addWidget(self.later_btn)

        self.install_btn = PrimaryPushButton(
            self._tr("page.servers.changelog.button.install", "Установить"),
            icon=FluentIcon.DOWNLOAD,
        )
        set_control_accessibility(
            self.install_btn,
            name="Установить обновление",
            description="Запускает установку доступного обновления.",
        )
        set_state_text(self.install_btn, "Установить обновление")
        self.install_btn.clicked.connect(self._on_install)
        buttons_layout.addWidget(self.install_btn)

        layout.addWidget(self.buttons_widget)

        self._apply_theme(force=True)

    def _update_accessibility(self) -> None:
        version = (self._raw_version or "").strip()
        if version:
            card_name = f"{self.title_label.text()}: версия {version}"
            install_name = f"Установить обновление {version}"
        else:
            card_name = self.title_label.text()
            install_name = "Установить обновление"

        set_control_accessibility(
            self,
            name=card_name,
            description="Карточка обновления. Содержит версию, список изменений и кнопки действий.",
        )
        set_state_text(self, card_name)
        set_control_accessibility(
            self.install_btn,
            name=install_name,
            description="Запускает установку доступного обновления.",
        )
        set_state_text(self.install_btn, install_name)
        self._set_label_state(self.title_label, "Заголовок обновления")
        self._set_label_state(self.version_label, "Информация об обновлении")
        changelog_text = " ".join(str(self._raw_changelog or "").strip().split())
        changelog_name = "Список изменений обновления"
        if changelog_text:
            changelog_name = f"{changelog_name}: {changelog_text}"
        set_control_accessibility(
            self.changelog_text,
            name=changelog_name,
            description="Показывает, что изменилось в доступном обновлении.",
        )
        self._update_progress_accessibility()

    def _update_progress_accessibility(self) -> None:
        self._set_label_state(self.progress_label, "Ход скачивания обновления")
        self._set_label_state(self.speed_label, "Скорость скачивания обновления")
        self._set_label_state(self.eta_label, "Осталось до завершения обновления")
        set_state_text(self._progress_indeterminate, "Подготовка скачивания обновления")
        self._set_label_state(self.progress_bar, "Прогресс скачивания обновления")

    def _set_label_state(self, label, prefix: str) -> None:
        try:
            value = str(label.text() or "").strip()
        except Exception:
            value = ""
        set_state_text(label, f"{prefix}: {value or '—'}")

    def _apply_theme(self, tokens=None, force: bool = False) -> None:
        _ = force
        self._tokens = tokens or get_theme_tokens()
        tokens = self._tokens

        self.title_label.setStyleSheet(f"color: {tokens.accent_hex};")
        self.changelog_text.setStyleSheet(f"color: {tokens.fg_muted}; font-size: 12px; padding: 4px 0;")

        self.close_btn.setIcon(FluentIcon.CLOSE)
        self.install_btn.setIcon(FluentIcon.DOWNLOAD)

        icon_name = 'fa5s.arrow-circle-up' if self._icon_kind == "update" else 'fa5s.download'
        self.icon_label.setPixmap(get_cached_qta_pixmap(icon_name, color=tokens.accent_hex, size=24))

        if self._raw_changelog:
            try:
                self.changelog_text.setText(
                    update_page_plans.make_links_clickable(self._raw_changelog, tokens.accent_hex)
                )
            except Exception:
                pass

    def show_update(self, version: str, changelog: str):
        if self._is_downloading:
            return
        plan = update_page_plans.build_changelog_update_plan(
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
        self._update_accessibility()

    def start_download(self, version: str):
        plan = update_page_plans.build_changelog_download_start_plan(
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
        self._update_accessibility()

    def update_progress(self, percent: int, done_bytes: int, total_bytes: int):
        plan = update_page_plans.build_changelog_progress_plan(
            percent=percent,
            done_bytes=done_bytes,
            total_bytes=total_bytes,
            last_speed_time=self._last_speed_time,
            last_speed_bytes=self._last_speed_bytes,
            smoothed_speed=self._smoothed_speed,
            download_speed_kb=self._download_speed_kb,
            download_eta_seconds=self._download_eta_seconds,
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
        self._update_accessibility()

    def set_download_status_text(self, message: str) -> None:
        if not self._is_downloading:
            return
        text = str(message or "").strip()
        if text:
            self.version_label.setText(text)
            self._update_accessibility()

    def download_complete(self):
        plan = update_page_plans.build_changelog_terminal_plan(
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
        self._update_accessibility()

    def download_failed(self, error: str):
        plan = update_page_plans.build_changelog_terminal_plan(
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
        self.icon_label.setPixmap(get_cached_qta_pixmap('fa5s.exclamation-triangle', color='#ff6b6b', size=24))
        self.version_label.setText(plan.version_text)
        self.progress_widget.setVisible(plan.progress_visible)
        self.buttons_widget.setVisible(plan.buttons_visible)
        self.close_btn.setVisible(plan.close_visible)
        self.install_btn.setText(plan.install_text)
        self._update_accessibility()

    def set_ui_language(self, language: str) -> None:
        self._ui_language = language
        self.later_btn.setText(self._tr("page.servers.changelog.button.later", "Позже"))
        plan = update_page_plans.build_changelog_terminal_plan(
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
        self._update_accessibility()

    def _on_install(self):
        self.install_clicked.emit()

    def _on_dismiss(self):
        self.hide()
        self.dismiss_clicked.emit()
