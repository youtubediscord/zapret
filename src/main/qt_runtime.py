from __future__ import annotations

import os
import sys
import time as _time

from PyQt6.QtCore import QCoreApplication, Qt
from PyQt6.QtWidgets import QApplication

from main.runtime_state import log_startup_metric as emit_startup_metric


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


def _connect_qfluent_accent_signal_lazy() -> None:
    """Подписывает сброс кэша темы без раннего импорта всего ui.theme."""
    try:
        from qfluentwidgets.common.config import qconfig

        def _invalidate_theme_cache(_color) -> None:
            try:
                from ui.theme import invalidate_theme_tokens_cache

                invalidate_theme_tokens_cache()
            except Exception:
                pass

        qconfig.themeColorChanged.connect(_invalidate_theme_cache)
    except Exception:
        pass


def ensure_qt_runtime() -> QApplication:
    global _QT_RUNTIME_READY

    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    os.environ["QT_API"] = "pyqt6"
    _set_attr_if_exists("AA_EnableHighDpiScaling")
    _set_attr_if_exists("AA_UseHighDpiPixmaps")

    t_qapp = _time.perf_counter()
    app = QApplication.instance() or QApplication(sys.argv)
    emit_startup_metric(
        "StartupQtRuntimeQApplication",
        f"{(_time.perf_counter() - t_qapp) * 1000:.0f}ms",
    )

    if _QT_RUNTIME_READY:
        return app

    t_hooks = _time.perf_counter()
    t_combo_guard = _time.perf_counter()
    from ui.combo_popup_guard import install_global_combo_popup_closer

    install_global_combo_popup_closer(app)
    emit_startup_metric(
        "StartupQtComboPopupGuard",
        f"{(_time.perf_counter() - t_combo_guard) * 1000:.0f}ms",
    )
    t_animation = _time.perf_counter()
    _install_animation_py314_compat()
    emit_startup_metric(
        "StartupQtAnimationCompat",
        f"{(_time.perf_counter() - t_animation) * 1000:.0f}ms",
    )
    t_accent_signal = _time.perf_counter()
    _connect_qfluent_accent_signal_lazy()
    emit_startup_metric(
        "StartupQtAccentSignal",
        f"{(_time.perf_counter() - t_accent_signal) * 1000:.0f}ms",
    )
    emit_startup_metric(
        "StartupQtRuntimeReadyHooks",
        f"{(_time.perf_counter() - t_hooks) * 1000:.0f}ms",
    )

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

    t_runtime = _time.perf_counter()
    app = ensure_qt_runtime()
    emit_startup_metric(
        "StartupQtRuntimeEnsure",
        f"{(_time.perf_counter() - t_runtime) * 1000:.0f}ms",
    )
    try:
        app.setQuitOnLastWindowClosed(False)

        from log.crash_handler import install_qt_crash_handler

        t_crash = _time.perf_counter()
        install_qt_crash_handler(app)
        emit_startup_metric(
            "StartupQtCrashHandler",
            f"{(_time.perf_counter() - t_crash) * 1000:.0f}ms",
        )
    except Exception as exc:
        ctypes.windll.user32.MessageBoxW(None, f"Ошибка инициализации Qt: {exc}", "Zapret", 0x10)

    t_theme = _time.perf_counter()
    from qfluentwidgets import Theme, setTheme
    from qfluentwidgets.common.config import qconfig
    from PyQt6.QtGui import QColor

    try:
        from settings.appearance import load_display_mode

        display_mode = load_display_mode()
    except Exception:
        display_mode = "dark"

    if display_mode == "light":
        setTheme(Theme.LIGHT)
    elif display_mode == "system":
        setTheme(Theme.AUTO)
    else:
        setTheme(Theme.DARK)
    emit_startup_metric(
        "StartupQtThemeMode",
        f"{(_time.perf_counter() - t_theme) * 1000:.0f}ms",
    )

    t_accent = _time.perf_counter()
    try:
        from settings.appearance import (
            load_accent_color,
            load_tinted_settings,
            load_windows_system_accent,
            save_accent_color,
        )

        tinted_settings = load_tinted_settings()
        if tinted_settings.follow_windows_accent:
            accent_hex = load_windows_system_accent().hex_color
        else:
            accent_hex = load_accent_color().hex_color
        if accent_hex:
            color = QColor(accent_hex)
            if color.isValid():
                qconfig.set(qconfig.themeColor, color)
                if tinted_settings.follow_windows_accent:
                    save_accent_color(accent_hex)
    except Exception:
        pass
    emit_startup_metric(
        "StartupQtAccent",
        f"{(_time.perf_counter() - t_accent) * 1000:.0f}ms",
    )

    return app
