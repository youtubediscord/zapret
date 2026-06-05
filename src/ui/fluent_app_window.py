# ui/fluent_app_window.py
"""
Main app window using qfluentwidgets FluentWindow (WinUI 3 style).
Replaces the old QWidget + FramelessWindowMixin + CustomTitleBar stack.
"""
import time as _time
from qfluentwidgets import (
    FluentWindow, NavigationItemPosition, FluentIcon,
    setTheme, Theme, setThemeColor, NavigationAvatarWidget,
)
from qfluentwidgets import NavigationWidget
from PyQt6.QtWidgets import QApplication, QWidget, QLabel
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
from PyQt6.QtCore import Qt, QTimer

from app.app_icon_resources import resolve_existing_app_icon_path
from config.build_info import APP_VERSION

from log.log import log
from main.runtime_state import log_startup_metric as emit_startup_metric



class ZapretFluentWindow(FluentWindow):
    """Main app window using qfluentwidgets FluentWindow (WinUI 3 style)."""

    def __init__(self, parent=None):
        # Tint color painted as window background (below all content, above Mica).
        # QColor(0,0,0,0) = pure Mica (no tint), alpha 1-200 = visible tint.
        self._mica_tint_color = QColor(0, 0, 0, 0)

        t_super = _time.perf_counter()
        super().__init__(parent)
        emit_startup_metric(
            "StartupFluentWindowSuper",
            f"{(_time.perf_counter() - t_super) * 1000:.0f}ms",
        )
        self.setWindowTitle(f"Zapret2 v{APP_VERSION}")

        self._app_icon = None
        self._app_icon_deferred_started = False
        self._schedule_app_icon_after_interactive()

        # Theme mode (DARK/LIGHT) is set in main.py via _sync_theme_mode_to_qfluent()
        # before the window is created, so no hardcoded setTheme(DARK) here.

    def _schedule_app_icon_after_interactive(self) -> None:
        try:
            self.startup_interactive_ready.connect(lambda *_args: QTimer.singleShot(0, self._apply_app_icon_deferred))
        except Exception:
            QTimer.singleShot(1500, self._apply_app_icon_deferred)

    def _apply_app_icon_deferred(self) -> None:
        """Ставит иконку после первого показа окна, чтобы не задерживать старт."""
        if self._app_icon_deferred_started:
            return
        self._app_icon_deferred_started = True

        t_icon = _time.perf_counter()
        icon_path = resolve_existing_app_icon_path()
        if icon_path:
            self._app_icon = QIcon(icon_path)
            self.setWindowIcon(self._app_icon)
            app = QApplication.instance()
            if app:
                app.setWindowIcon(self._app_icon)
        emit_startup_metric(
            "StartupFluentWindowIconDeferred",
            f"{(_time.perf_counter() - t_icon) * 1000:.0f}ms",
        )

    # ------------------------------------------------------------------
    # Background tint (Mica + semi-transparent Qt background layer)
    # ------------------------------------------------------------------

    def _normalBackgroundColor(self) -> QColor:  # noqa: N802
        """Override: inject semi-transparent tint when Mica is active.

        FluentWidget._normalBackgroundColor() returns QColor(0,0,0,0) when
        Mica is enabled, making the Qt surface fully transparent. By returning
        our _mica_tint_color instead, the background is painted as a
        semi-transparent fill BELOW all content widgets, so the tint blends
        with the DWM Mica backdrop without covering text or controls.
        """
        try:
            if self.isMicaEffectEnabled():
                return self._mica_tint_color
        except Exception:
            pass
        return super()._normalBackgroundColor()

    def set_tint_overlay(self, r: int, g: int, b: int, alpha: int) -> None:
        """Update the Mica tint color (painted below content, above Mica backdrop).

        alpha=0  → pure Mica (no tint)
        alpha=200 → strong tint but content still readable (drawn on top)
        """
        self._mica_tint_color = QColor(r, g, b, max(0, min(255, alpha)))
        try:
            self._updateBackgroundColor()
        except Exception:
            pass

    def clear_tint_overlay(self) -> None:
        """Reset tint to fully transparent (pure Mica or default background)."""
        self._mica_tint_color = QColor(0, 0, 0, 0)
        try:
            self._updateBackgroundColor()
        except Exception:
            pass

    def prepare_transparent_mica_background(self) -> None:
        """Готовит прозрачный фон перед отключением Mica на Windows 11."""
        self._darkBackgroundColor = QColor(0, 0, 0, 0)
        self._lightBackgroundColor = QColor(0, 0, 0, 0)

    # ------------------------------------------------------------------
    # Navigation helpers
    # ------------------------------------------------------------------

    def addPageToNav(self, page: QWidget, icon, text: str,
                     position=NavigationItemPosition.SCROLL,
                     parent=None, is_transparent=True):
        """Wrapper for addSubInterface that ensures objectName is set."""
        if not page.objectName():
            page.setObjectName(page.__class__.__name__)
        return self.addSubInterface(
            page, icon, text,
            position=position,
            parent=parent,
            isTransparent=is_transparent,
        )

    def addSeparatorToNav(self):
        """Add a separator line in the navigation."""
        self.navigationInterface.addSeparator()

    # ------------------------------------------------------------------
    # Background image support (for РКН Тян preset)
    # ------------------------------------------------------------------

    def set_background_image(self, path: str | None) -> None:
        """Set a full-window background image (dimmed). Pass None to hide."""
        if not hasattr(self, '_bg_label'):
            self._bg_label = QLabel(self)
            self._bg_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            self._bg_rawpath = None
        if path is None:
            self._bg_label.hide()
            self._bg_rawpath = None
            return
        self._bg_rawpath = path
        self._rescale_bg()
        self._bg_label.lower()
        self._bg_label.show()

    def _rescale_bg(self) -> None:
        """Rescale and dim the background image to current window size."""
        if not (hasattr(self, '_bg_label') and getattr(self, '_bg_rawpath', None)):
            return
        pm = QPixmap(self._bg_rawpath)
        if pm.isNull():
            return
        pm = pm.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        dimmed = QPixmap(pm.size())
        dimmed.fill(QColor(0, 0, 0, 0))
        p = QPainter(dimmed)
        p.drawPixmap(0, 0, pm)
        p.fillRect(dimmed.rect(), QColor(0, 0, 0, 155))
        p.end()
        self._bg_label.setPixmap(dimmed)
        self._bg_label.setGeometry(self.rect())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rescale_bg()
