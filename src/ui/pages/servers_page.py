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

try:
    from qfluentwidgets import (
        BodyLabel, CaptionLabel, StrongBodyLabel,
        PushButton, TransparentToolButton, TransparentPushButton,
        SwitchButton, CardWidget,
        TableWidget,
        ProgressBar, IndeterminateProgressBar, IndeterminateProgressRing,
        FluentIcon,
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
    _HAS_FLUENT = False

from config import APP_VERSION, CHANNEL
from config.telegram_links import open_telegram_link
from updater.channel_utils import is_test_update_channel


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

        self._apply_theme()

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

    def _format_checked_ago(self, elapsed: float) -> str:
        mins_ago = int(max(elapsed, 0.0) // 60)
        secs_ago = int(max(elapsed, 0.0) % 60)
        if mins_ago > 0:
            return self._tr(
                "page.servers.update.subtitle.checked_ago_min_sec_template",
                "Проверено {minutes}м {seconds}с назад",
            ).format(minutes=mins_ago, seconds=secs_ago)
        return self._tr(
            "page.servers.update.subtitle.checked_ago_sec_template",
            "Проверено {seconds}с назад",
        ).format(seconds=secs_ago)

    def _set_error_icon(self) -> None:
        tokens = self._tokens
        error_hex = "#dc2626" if tokens.is_light else "#f87171"
        pixmap = qta.icon('fa5s.exclamation-triangle', color=error_hex).pixmap(32, 32)
        self._icon_label.setPixmap(pixmap)

    def _apply_state_text(self) -> None:
        state = self._state

        if state == "checking":
            self.title_label.setText(self._tr("page.servers.update.title.checking", "Проверка обновлений..."))
            self.subtitle_label.setText(
                self._tr("page.servers.update.subtitle.checking", "Подождите, идёт проверка серверов")
            )
            return

        if state == "available":
            self.title_label.setText(
                self._tr("page.servers.update.title.available_template", "Доступно обновление v{version}").format(
                    version=self._state_version
                )
            )
            self.subtitle_label.setText(
                self._tr(
                    "page.servers.update.subtitle.available",
                    "Установите обновление ниже или проверьте ещё раз",
                )
            )
            self.check_btn.setText(self._tr("page.servers.update.button.recheck", "ПРОВЕРИТЬ СНОВА"))
            return

        if state == "up_to_date":
            self.title_label.setText(self._tr("page.servers.update.title.none", "Обновлений нет"))
            self.subtitle_label.setText(
                self._tr(
                    "page.servers.update.subtitle.latest_template",
                    "Установлена последняя версия {version}",
                ).format(version=APP_VERSION)
            )
            self.check_btn.setText(self._tr("page.servers.update.button.recheck", "ПРОВЕРИТЬ СНОВА"))
            return

        if state == "error":
            self.title_label.setText(self._tr("page.servers.update.title.error", "Ошибка проверки"))
            self.subtitle_label.setText((self._state_message or "")[:60])
            self.check_btn.setText(self._tr("page.servers.update.button.retry", "Повторить"))
            return

        if state == "found":
            self.title_label.setText(
                self._tr("page.servers.update.title.found_template", "Найдено обновление v{version}").format(
                    version=self._state_version
                )
            )
            self.subtitle_label.setText(
                self._tr("page.servers.update.subtitle.source_template", "Источник: {source}").format(
                    source=self._state_source
                )
            )
            self.check_btn.setText(self._tr("page.servers.update.button.recheck", "ПРОВЕРИТЬ СНОВА"))
            return

        if state == "download_error":
            self.title_label.setText(self._tr("page.servers.update.title.download_error", "Ошибка загрузки"))
            self.subtitle_label.setText(self._tr("page.servers.update.subtitle.try_again", "Попробуйте снова"))
            self.check_btn.setText(self._tr("page.servers.update.button.recheck", "ПРОВЕРИТЬ СНОВА"))
            return

        if state == "deferred":
            self.title_label.setText(
                self._tr("page.servers.update.title.deferred_template", "Обновление v{version} отложено").format(
                    version=self._state_version
                )
            )
            self.subtitle_label.setText(
                self._tr("page.servers.update.subtitle.recheck_hint", "Нажмите для повторной проверки")
            )
            self.check_btn.setText(self._tr("page.servers.update.button.recheck", "ПРОВЕРИТЬ СНОВА"))
            return

        if state == "checked_ago":
            self.title_label.setText(self._tr("page.servers.update.title.default", "Проверка обновлений"))
            self.subtitle_label.setText(self._format_checked_ago(self._state_elapsed))
            self.check_btn.setText(self._tr("page.servers.update.button.recheck", "ПРОВЕРИТЬ СНОВА"))
            return

        if state == "auto_on":
            self.title_label.setText(self._tr("page.servers.update.title.default", "Проверка обновлений"))
            self.subtitle_label.setText(self._tr("page.servers.update.subtitle.auto_on", "Автопроверка включена"))
            self.check_btn.setText(self._tr("page.servers.update.button.recheck", "ПРОВЕРИТЬ СНОВА"))
            return

        if state == "manual":
            self.title_label.setText(self._tr("page.servers.update.title.default", "Проверка обновлений"))
            self.subtitle_label.setText(
                self._tr("page.servers.update.subtitle.press_button", "Нажмите кнопку для проверки")
            )
            self.check_btn.setText(self._tr("page.servers.update.button.manual", "ПРОВЕРИТЬ ВРУЧНУЮ"))
            return

        # idle
        self.title_label.setText(self._tr("page.servers.update.title.default", "Проверка обновлений"))
        self.subtitle_label.setText(
            self._tr(
                "page.servers.update.subtitle.default",
                "Нажмите для проверки доступных обновлений",
            )
        )
        self.check_btn.setText(self._tr("page.servers.update.button.check", "Проверить обновления"))

    def start_checking(self):
        self._is_checking = True
        self._state = "checking"
        self._apply_state_text()
        self.check_btn.start_loading()

    def stop_checking(self, found_update: bool = False, version: str = ""):
        self._is_checking = False
        self._set_icon_idle()
        self._state_version = version or ""
        self._state = "available" if found_update else "up_to_date"
        self._apply_state_text()
        self.check_btn.stop_loading(self._tr("page.servers.update.button.recheck", "ПРОВЕРИТЬ СНОВА"))

    def set_error(self, message: str):
        self._is_checking = False
        self._state = "error"
        self._state_message = (message or "")[:60]
        self._set_error_icon()
        self._apply_state_text()
        self.check_btn.stop_loading(self._tr("page.servers.update.button.retry", "Повторить"))

    def show_found_update(self, version: str, source: str) -> None:
        self._is_checking = False
        self._set_icon_idle()
        self._state = "found"
        self._state_version = version or ""
        self._state_source = source or ""
        self._apply_state_text()
        self.check_btn.setEnabled(True)

    def show_download_error(self) -> None:
        self._is_checking = False
        self._set_error_icon()
        self._state = "download_error"
        self._apply_state_text()
        self.check_btn.setEnabled(True)

    def show_deferred(self, version: str) -> None:
        self._is_checking = False
        self._set_icon_idle()
        self._state = "deferred"
        self._state_version = version or ""
        self._apply_state_text()
        self.check_btn.setEnabled(True)

    def show_checked_ago(self, elapsed: float) -> None:
        self._is_checking = False
        self._set_icon_idle()
        self._state = "checked_ago"
        self._state_elapsed = max(0.0, float(elapsed or 0.0))
        self._apply_state_text()

    def show_manual_hint(self) -> None:
        self._is_checking = False
        self._set_icon_idle()
        self._state = "manual"
        self._apply_state_text()

    def show_auto_enabled_hint(self) -> None:
        self._is_checking = False
        self._set_icon_idle()
        self._state = "auto_on"
        self._apply_state_text()

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

        self._apply_theme()

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
                self.changelog_text.setText(self._make_links_clickable(self._raw_changelog, tokens.accent_hex))
            except Exception:
                pass

    def _make_links_clickable(self, text: str, accent_hex: str) -> str:
        import re
        url_pattern = r'(https?://[^\s<>"\']+)'

        def replace_url(match):
            url = match.group(1)
            while url and url[-1] in '.,;:!?)':
                url = url[:-1]
            return f'<a href="{url}" style="color: {accent_hex};">{url}</a>'

        return re.sub(url_pattern, replace_url, text)

    def show_update(self, version: str, changelog: str):
        if self._is_downloading:
            return
        self._mode = "update"
        self._is_downloading = False
        self._icon_kind = "update"
        self._raw_version = str(version or "")
        self._download_error_text = ""
        self.version_label.setText(
            self._tr(
                "page.servers.changelog.version.transition_template",
                "v{current}  →  v{target}",
            ).format(current=APP_VERSION, target=version)
        )
        self.title_label.setText(self._tr("page.servers.changelog.title.available", "Доступно обновление"))
        self.install_btn.setText(self._tr("page.servers.changelog.button.install", "Установить"))

        if changelog:
            if len(changelog) > 200:
                changelog = changelog[:200] + "..."
            self._raw_changelog = changelog
            self.changelog_text.setText(self._make_links_clickable(changelog, self._tokens.accent_hex))
            self.changelog_text.show()
        else:
            self._raw_changelog = ""
            self.changelog_text.hide()

        self.progress_widget.hide()
        self.buttons_widget.show()
        self.close_btn.show()
        self.show()
        self._apply_theme()

    def start_download(self, version: str):
        self._mode = "downloading"
        self._is_downloading = True
        self._icon_kind = "download"
        self._raw_version = str(version or "")
        self._download_start_time = time.time()
        self._last_bytes = 0
        self._last_speed_time = time.time()
        self._last_speed_bytes = 0
        self._smoothed_speed = 0.0  # Сглаженная скорость (bytes/sec)
        self._download_percent = 0
        self._download_done_bytes = 0
        self._download_total_bytes = 0
        self._download_speed_kb = None
        self._download_eta_seconds = None
        self._download_error_text = ""

        self.title_label.setText(
            self._tr("page.servers.changelog.title.downloading_template", "Загрузка v{version}").format(
                version=version
            )
        )
        self._apply_theme()

        self.version_label.setText(
            self._tr("page.servers.changelog.version.preparing", "Подготовка к загрузке...")
        )
        self.changelog_text.hide()
        self.buttons_widget.hide()
        self.close_btn.hide()

        self.progress_bar.setValue(0)
        self.progress_bar.hide()
        if self._progress_indeterminate is not None:
            self._progress_indeterminate.start()
            self._progress_indeterminate.show()
        self.progress_label.setText("0%")
        self.speed_label.setText(self._tr("page.servers.changelog.progress.speed_unknown", "Скорость: —"))
        self.eta_label.setText(self._tr("page.servers.changelog.progress.eta_unknown", "Осталось: —"))
        self.progress_widget.show()

    def update_progress(self, percent: int, done_bytes: int, total_bytes: int):
        self._mode = "downloading"
        self._download_percent = int(percent)
        self._download_done_bytes = int(done_bytes)
        self._download_total_bytes = int(total_bytes)

        # First bytes received — swap indeterminate → determinate bar
        if self._progress_indeterminate is not None and self._progress_indeterminate.isVisible():
            try:
                self._progress_indeterminate.stop()
                self._progress_indeterminate.hide()
            except Exception:
                pass
            self.progress_bar.show()
        self.progress_bar.setValue(percent)
        self.progress_label.setText(f"{percent}%")

        done_mb = done_bytes / (1024 * 1024)
        total_mb = total_bytes / (1024 * 1024)
        self.version_label.setText(
            self._tr(
                "page.servers.changelog.progress.downloaded_mb_template",
                "Загружено {done:.1f} / {total:.1f} МБ",
            ).format(done=done_mb, total=total_mb)
        )

        now = time.time()
        dt = now - self._last_speed_time
        if dt >= 1.0 and done_bytes > 0:
            # Мгновенная скорость за последний интервал
            delta_bytes = done_bytes - self._last_speed_bytes
            if delta_bytes <= 0:
                # Смена сервера или resume — сбрасываем EMA
                self._smoothed_speed = 0.0
                self._last_speed_time = now
                self._last_speed_bytes = done_bytes
                return
            instant_speed = delta_bytes / dt

            # Сглаживание: 40% старое + 60% новое (быстро реагирует на смену сервера)
            if self._smoothed_speed <= 0:
                self._smoothed_speed = instant_speed
            else:
                self._smoothed_speed = self._smoothed_speed * 0.4 + instant_speed * 0.6

            self._last_speed_time = now
            self._last_speed_bytes = done_bytes

            speed = self._smoothed_speed
            speed_kb = speed / 1024
            self._download_speed_kb = speed_kb

            if speed_kb > 1024:
                self.speed_label.setText(
                    self._tr(
                        "page.servers.changelog.progress.speed_mb_template",
                        "Скорость: {value:.1f} МБ/с",
                    ).format(value=speed_kb / 1024)
                )
            else:
                self.speed_label.setText(
                    self._tr(
                        "page.servers.changelog.progress.speed_kb_template",
                        "Скорость: {value:.0f} КБ/с",
                    ).format(value=speed_kb)
                )

            if speed > 0:
                remaining = (total_bytes - done_bytes) / speed
                self._download_eta_seconds = remaining
                if remaining < 60:
                    self.eta_label.setText(
                        self._tr(
                            "page.servers.changelog.progress.eta_sec_template",
                            "Осталось: {seconds} сек",
                        ).format(seconds=int(remaining))
                    )
                else:
                    self.eta_label.setText(
                        self._tr(
                            "page.servers.changelog.progress.eta_min_template",
                            "Осталось: {minutes} мин",
                        ).format(minutes=int(remaining / 60))
                    )

        self._last_bytes = done_bytes

    def download_complete(self):
        self._mode = "installing"
        if self._progress_indeterminate is not None:
            try:
                self._progress_indeterminate.stop()
                self._progress_indeterminate.hide()
            except Exception:
                pass
        self.progress_bar.show()
        self.title_label.setText(self._tr("page.servers.changelog.title.installing", "Установка..."))
        self.version_label.setText(
            self._tr(
                "page.servers.changelog.version.installer_starting",
                "Запуск установщика, приложение закроется",
            )
        )
        self.progress_bar.setValue(100)
        self.progress_label.setText("100%")
        self.speed_label.setText("")
        self.eta_label.setText("")

    def download_failed(self, error: str):
        self._mode = "failed"
        self._is_downloading = False
        self._download_error_text = error[:80] if len(error) > 80 else error
        if self._progress_indeterminate is not None:
            try:
                self._progress_indeterminate.stop()
                self._progress_indeterminate.hide()
            except Exception:
                pass

        self.title_label.setText(
            self._tr("page.servers.changelog.title.download_error", "Ошибка загрузки")
        )
        self.title_label.setStyleSheet("color: #ff6b6b;")
        self.icon_label.setPixmap(qta.icon('fa5s.exclamation-triangle', color='#ff6b6b').pixmap(24, 24))

        self.version_label.setText(self._download_error_text)
        self.progress_widget.hide()
        self.buttons_widget.show()
        self.close_btn.show()
        self.install_btn.setText(self._tr("page.servers.changelog.button.retry", "Повторить"))

    def set_ui_language(self, language: str) -> None:
        self._ui_language = language
        self.later_btn.setText(self._tr("page.servers.changelog.button.later", "Позже"))

        if self._mode == "update":
            self.title_label.setText(self._tr("page.servers.changelog.title.available", "Доступно обновление"))
            self.version_label.setText(
                self._tr(
                    "page.servers.changelog.version.transition_template",
                    "v{current}  →  v{target}",
                ).format(current=APP_VERSION, target=self._raw_version)
            )
            self.install_btn.setText(self._tr("page.servers.changelog.button.install", "Установить"))
        elif self._mode == "downloading":
            self.title_label.setText(
                self._tr("page.servers.changelog.title.downloading_template", "Загрузка v{version}").format(
                    version=self._raw_version
                )
            )
            if self._download_done_bytes > 0 and self._download_total_bytes > 0:
                done_mb = self._download_done_bytes / (1024 * 1024)
                total_mb = self._download_total_bytes / (1024 * 1024)
                self.version_label.setText(
                    self._tr(
                        "page.servers.changelog.progress.downloaded_mb_template",
                        "Загружено {done:.1f} / {total:.1f} МБ",
                    ).format(done=done_mb, total=total_mb)
                )
            else:
                self.version_label.setText(
                    self._tr("page.servers.changelog.version.preparing", "Подготовка к загрузке...")
                )

            self.progress_label.setText(f"{self._download_percent}%")
            if self._download_speed_kb is None:
                self.speed_label.setText(self._tr("page.servers.changelog.progress.speed_unknown", "Скорость: —"))
            elif self._download_speed_kb > 1024:
                self.speed_label.setText(
                    self._tr(
                        "page.servers.changelog.progress.speed_mb_template",
                        "Скорость: {value:.1f} МБ/с",
                    ).format(value=self._download_speed_kb / 1024)
                )
            else:
                self.speed_label.setText(
                    self._tr(
                        "page.servers.changelog.progress.speed_kb_template",
                        "Скорость: {value:.0f} КБ/с",
                    ).format(value=self._download_speed_kb)
                )

            if self._download_eta_seconds is None:
                self.eta_label.setText(self._tr("page.servers.changelog.progress.eta_unknown", "Осталось: —"))
            elif self._download_eta_seconds < 60:
                self.eta_label.setText(
                    self._tr(
                        "page.servers.changelog.progress.eta_sec_template",
                        "Осталось: {seconds} сек",
                    ).format(seconds=int(self._download_eta_seconds))
                )
            else:
                self.eta_label.setText(
                    self._tr(
                        "page.servers.changelog.progress.eta_min_template",
                        "Осталось: {minutes} мин",
                    ).format(minutes=int(self._download_eta_seconds / 60))
                )
        elif self._mode == "installing":
            self.title_label.setText(self._tr("page.servers.changelog.title.installing", "Установка..."))
            self.version_label.setText(
                self._tr(
                    "page.servers.changelog.version.installer_starting",
                    "Запуск установщика, приложение закроется",
                )
            )
        elif self._mode == "failed":
            self.title_label.setText(
                self._tr("page.servers.changelog.title.download_error", "Ошибка загрузки")
            )
            self.install_btn.setText(self._tr("page.servers.changelog.button.retry", "Повторить"))
            self.version_label.setText(self._download_error_text)

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
        name_item = QTableWidgetItem(server_name)
        if status.get('is_current'):
            name_item.setText(f"⭐ {server_name}")
            name_item.setForeground(QColor(self._tokens.accent_hex))
        self.servers_table.setItem(row, 0, name_item)

        status_item = QTableWidgetItem()
        if status.get('status') == 'online':
            status_item.setText(self._tr("page.servers.table.status.online", "● Онлайн"))
            status_item.setForeground(QColor(134, 194, 132))
        elif status.get('status') == 'blocked':
            status_item.setText(self._tr("page.servers.table.status.blocked", "● Блок"))
            status_item.setForeground(QColor(230, 180, 100))
        elif status.get('status') == 'skipped':
            status_item.setText(self._tr("page.servers.table.status.waiting", "● Ожидание"))
            status_item.setForeground(QColor(160, 160, 160))
        else:
            status_item.setText(self._tr("page.servers.table.status.offline", "● Офлайн"))
            status_item.setForeground(QColor(220, 130, 130))
        self.servers_table.setItem(row, 1, status_item)

        if status.get('response_time'):
            time_text = self._tr("page.servers.table.time.ms_template", "{ms}мс").format(
                ms=f"{status.get('response_time', 0) * 1000:.0f}"
            )
        else:
            time_text = self._tr("page.servers.table.time.empty", "—")
        self.servers_table.setItem(row, 2, QTableWidgetItem(time_text))

        if server_name == 'Telegram Bot':
            if status.get('status') == 'online':
                if is_test_update_channel(CHANNEL):
                    extra = self._tr("page.servers.table.versions.test_template", "T: {version}").format(
                        version=status.get('test_version', '—')
                    )
                else:
                    extra = self._tr("page.servers.table.versions.stable_template", "S: {version}").format(
                        version=status.get('stable_version', '—')
                    )
            else:
                extra = status.get('error', '')[:40]
        elif server_name == 'GitHub API':
            if status.get('rate_limit') is not None:
                extra = self._tr("page.servers.table.versions.rate_limit_template", "Лимит: {remaining}/{limit}").format(
                    remaining=status['rate_limit'],
                    limit=status.get('rate_limit_max', 60),
                )
            else:
                extra = status.get('error', '')[:40]
        elif status.get('status') == 'online':
            extra = self._tr("page.servers.table.versions.both_template", "S: {stable}, T: {test}").format(
                stable=status.get('stable_version', '—'),
                test=status.get('test_version', '—'),
            )
        else:
            extra = status.get('error', '')[:40]

        self.servers_table.setItem(row, 3, QTableWidgetItem(extra))

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
        self._toggle_label.setText(self._tr("page.servers.settings.auto_check", "Проверять обновления при запуске"))
        self._version_info_label.setText(
            self._tr("page.servers.settings.version_channel_template", "v{version} · {channel}").format(
                version=APP_VERSION,
                channel=CHANNEL,
            )
        )

        self._tg_card.set_title(self._tr("page.servers.telegram.title", "Проблемы с обновлением?"))
        self._tg_info_label.setText(
            self._tr(
                "page.servers.telegram.info",
                "Если возникают трудности с автоматическим обновлением, все версии программы выкладываются в Telegram канале.",
            )
        )
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

        self._apply_theme()

    def showEvent(self, event):
        super().showEvent(event)

        if event.spontaneous():
            return

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
        open_telegram_link("zapretguidev" if is_test_update_channel(CHANNEL) else "zapretnetdiscordyoutube")

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
