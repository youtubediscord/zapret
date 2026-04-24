from __future__ import annotations

import os
import sys

from PyQt6.QtCore import QCoreApplication, Qt
from PyQt6.QtWidgets import QApplication


_QT_RUNTIME_READY = False


def _set_attr_if_exists(name: str, on: bool = True) -> None:
    attr = getattr(Qt.ApplicationAttribute, name, None)
    if attr is None:
        attr = getattr(Qt, name, None)
    if attr is not None:
        QCoreApplication.setAttribute(attr, on)


def _install_animation_py314_compat() -> None:
    if sys.version_info < (3, 14):
        return
    try:
        from PyQt6.QtCore import (
            QAbstractAnimation,
            QVariantAnimation,
            QPropertyAnimation,
            QSequentialAnimationGroup,
            QParallelAnimationGroup,
        )
    except ImportError:
        return
    try:
        _c_start = QAbstractAnimation.start
        _c_stop = QAbstractAnimation.stop
        _c_pause = QAbstractAnimation.pause
        _c_resume = QAbstractAnimation.resume
    except AttributeError:
        return

    deletion_policy = QAbstractAnimation.DeletionPolicy

    def _start(self, policy: deletion_policy = deletion_policy.KeepWhenStopped) -> None:
        _c_start(self, policy)

    def _stop(self) -> None:
        _c_stop(self)

    def _pause(self) -> None:
        _c_pause(self)

    def _resume(self) -> None:
        _c_resume(self)

    patches = {"start": _start, "stop": _stop, "pause": _pause, "resume": _resume}
    classes = (
        QAbstractAnimation,
        QVariantAnimation,
        QPropertyAnimation,
        QSequentialAnimationGroup,
        QParallelAnimationGroup,
    )
    for cls in classes:
        for attr_name, fn in patches.items():
            try:
                if hasattr(cls, attr_name):
                    setattr(cls, attr_name, fn)
            except Exception:
                pass


def ensure_qt_runtime() -> QApplication:
    global _QT_RUNTIME_READY

    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    os.environ["QT_API"] = "pyqt6"
    _set_attr_if_exists("AA_EnableHighDpiScaling")
    _set_attr_if_exists("AA_UseHighDpiPixmaps")

    app = QApplication.instance() or QApplication(sys.argv)

    if _QT_RUNTIME_READY:
        return app

    from ui.combo_popup_guard import install_global_combo_popup_closer

    install_global_combo_popup_closer(app)
    _install_animation_py314_compat()

    from ui.theme import connect_qfluent_accent_signal

    connect_qfluent_accent_signal()

    _QT_RUNTIME_READY = True
    return app


def _install_non_transient_scrollbars_style(app: QApplication) -> None:
    from PyQt6.QtWidgets import QProxyStyle, QStyle

    class _NoTransientScrollbarsStyle(QProxyStyle):
        def styleHint(self, hint, option=None, widget=None, returnData=None):
            if hint == QStyle.StyleHint.SH_ScrollBar_Transient:
                return 0
            return super().styleHint(hint, option, widget, returnData)

    app.setStyle(_NoTransientScrollbarsStyle(app.style()))


def application_bootstrap() -> QApplication:
    import ctypes

    app = ensure_qt_runtime()
    try:
        try:
            _install_non_transient_scrollbars_style(app)
        except Exception:
            pass

        app.setQuitOnLastWindowClosed(False)

        from log.crash_handler import install_qt_crash_handler

        install_qt_crash_handler(app)
    except Exception as exc:
        ctypes.windll.user32.MessageBoxW(None, f"Ошибка инициализации Qt: {exc}", "Zapret", 0x10)

    from qfluentwidgets import Theme, setTheme
    from qfluentwidgets.common.config import qconfig
    from PyQt6.QtGui import QColor

    try:
        from settings.store import get_display_mode

        display_mode = get_display_mode()
    except Exception:
        display_mode = "dark"

    if display_mode == "light":
        setTheme(Theme.LIGHT)
    elif display_mode == "system":
        setTheme(Theme.AUTO)
    else:
        setTheme(Theme.DARK)

    try:
        from settings.store import (
            get_follow_windows_accent,
            get_windows_system_accent,
            get_accent_color,
            set_accent_color,
        )

        if get_follow_windows_accent():
            accent_hex = get_windows_system_accent()
        else:
            accent_hex = get_accent_color()
        if accent_hex:
            color = QColor(accent_hex)
            if color.isValid():
                qconfig.set(qconfig.themeColor, color)
                if get_follow_windows_accent():
                    set_accent_color(accent_hex)
    except Exception:
        pass

    return app
