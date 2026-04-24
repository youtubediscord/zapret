# ui/fluent_app_window.py
"""
Main app window using qfluentwidgets FluentWindow (WinUI 3 style).
Replaces the old QWidget + FramelessWindowMixin + CustomTitleBar stack.
"""
import os
from qfluentwidgets import (
    FluentWindow, NavigationItemPosition, FluentIcon,
    setTheme, Theme, setThemeColor, NavigationAvatarWidget,
)
from qfluentwidgets import NavigationWidget
from PyQt6.QtWidgets import QApplication, QWidget, QLabel
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
from PyQt6.QtCore import Qt

from config.build_info import APP_VERSION
from config.config import ICON_PATH, ICON_DEV_PATH, is_dev_build_channel

from log.log import log



class ZapretFluentWindow(FluentWindow):
    """Main app window using qfluentwidgets FluentWindow (WinUI 3 style)."""

    def __init__(self, parent=None):
        # Tint color painted as window background (below all content, above Mica).
        # QColor(0,0,0,0) = pure Mica (no tint), alpha 1-200 = visible tint.
        self._mica_tint_color = QColor(0, 0, 0, 0)

        super().__init__(parent)
        self.setWindowTitle(f"Zapret2 v{APP_VERSION}")
        self.setMinimumSize(900, 500)

        # Set app icon
        icon_path = ICON_DEV_PATH if is_dev_build_channel() else ICON_PATH
        self._app_icon = None
        if os.path.exists(icon_path):
            self._app_icon = QIcon(icon_path)
            self.setWindowIcon(self._app_icon)
            app = QApplication.instance()
            if app:
                app.setWindowIcon(self._app_icon)

        # Theme mode (DARK/LIGHT) is set in main.py via _sync_theme_mode_to_qfluent()
        # before the window is created, so no hardcoded setTheme(DARK) here.

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
