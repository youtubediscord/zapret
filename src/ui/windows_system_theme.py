from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from typing import Callable

from PyQt6.QtCore import QAbstractNativeEventFilter, QTimer

from log.log import log


WM_SETTINGCHANGE = 0x001A
WM_DWMCOLORIZATIONCOLORCHANGED = 0x0320
WINDOWS_PERSONALIZE_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize"
APPS_USE_LIGHT_THEME = "AppsUseLightTheme"


class _POINT(ctypes.Structure):
    _fields_ = [
        ("x", wintypes.LONG),
        ("y", wintypes.LONG),
    ]


class _MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", _POINT),
    ]


def _read_registry_dword(root, key_path: str, value_name: str) -> int | None:
    import winreg

    try:
        with winreg.OpenKey(root, key_path, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, value_name)
            return int(value)
    except Exception:
        return None


def read_windows_apps_theme(
    *,
    read_dword: Callable[[object, str, str], int | None] | None = None,
) -> str | None:
    """Читает тему приложений Windows: light или dark."""
    if sys.platform != "win32":
        return None

    import winreg

    reader = read_dword or _read_registry_dword
    value = reader(winreg.HKEY_CURRENT_USER, WINDOWS_PERSONALIZE_KEY, APPS_USE_LIGHT_THEME)
    if value is None:
        return None
    return "light" if int(value) != 0 else "dark"


def _native_message_id_and_lparam(message) -> tuple[int | None, int | None]:
    try:
        address = int(message)
    except Exception:
        return None, None
    if not address:
        return None, None
    try:
        msg = _MSG.from_address(address)
        return int(msg.message), int(msg.lParam)
    except Exception:
        return None, None


def _read_lparam_text(lparam: int | None) -> str:
    if not lparam:
        return ""
    try:
        return ctypes.wstring_at(int(lparam))
    except Exception:
        return ""


def is_windows_theme_change_message(message_id: int | None, lparam: int | None = None) -> bool:
    if message_id == WM_DWMCOLORIZATIONCOLORCHANGED:
        return True
    if message_id != WM_SETTINGCHANGE:
        return False

    text = _read_lparam_text(lparam)
    if not text:
        return True
    return text in {
        "ImmersiveColorSet",
        "WindowsThemeElement",
        "UserPreferences",
    }


def apply_windows_system_theme_if_auto(
    window,
    *,
    display_mode_loader: Callable[[], str] | None = None,
    system_theme_reader: Callable[[], str | None] | None = None,
    set_theme_func=None,
    theme_enum=None,
    is_dark_theme_func: Callable[[], bool] | None = None,
    background_applier: Callable[[object], None] | None = None,
    refresh_flusher: Callable[[object], int] | None = None,
) -> bool:
    """Применяет системную тему Windows, если в настройках выбран режим Авто."""
    try:
        if display_mode_loader is None:
            from settings.appearance import load_display_mode

            display_mode_loader = load_display_mode
        if str(display_mode_loader() or "dark") != "system":
            return False

        reader = system_theme_reader or read_windows_apps_theme
        system_theme = reader()
        if system_theme not in {"dark", "light"}:
            return False

        if set_theme_func is None or theme_enum is None or is_dark_theme_func is None:
            from qfluentwidgets import Theme, isDarkTheme, setTheme

            set_theme_func = setTheme
            theme_enum = Theme
            is_dark_theme_func = isDarkTheme

        target_is_dark = system_theme == "dark"
        try:
            already_correct = bool(is_dark_theme_func()) == target_is_dark
        except Exception:
            already_correct = False
        if already_correct:
            return False

        set_theme_func(theme_enum.DARK if target_is_dark else theme_enum.LIGHT)

        from ui.theme import invalidate_theme_tokens_cache

        invalidate_theme_tokens_cache()

        if background_applier is None:
            from ui.theme import apply_window_background

            background_applier = apply_window_background
        if window is not None:
            background_applier(window)

        if refresh_flusher is None:
            from ui.theme_refresh import flush_pending_theme_refreshes

            refresh_flusher = flush_pending_theme_refreshes
        if window is not None:
            refresh_flusher(window)
            try:
                window.update()
            except Exception:
                pass

        return True
    except Exception as exc:
        log(f"Не удалось применить системную тему Windows: {exc}", "DEBUG")
        return False


class WindowsSystemThemeWatcher(QAbstractNativeEventFilter):
    """Следит за сообщениями Windows о смене темы приложений."""

    def __init__(
        self,
        *,
        window,
        apply_theme: Callable[[object], bool] = apply_windows_system_theme_if_auto,
        debounce_ms: int = 80,
    ) -> None:
        super().__init__()
        self._window = window
        self._apply_theme = apply_theme
        self._debounce_ms = max(0, int(debounce_ms))
        self._installed_app = None
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.refresh_now)

    def install(self, app) -> bool:
        if sys.platform != "win32" or app is None:
            return False
        try:
            app.installNativeEventFilter(self)
            self._installed_app = app
            return True
        except Exception as exc:
            log(f"Не удалось включить слежение за темой Windows: {exc}", "DEBUG")
            return False

    def cleanup(self) -> None:
        try:
            self._timer.stop()
        except Exception:
            pass
        app = self._installed_app
        self._installed_app = None
        if app is not None:
            try:
                app.removeNativeEventFilter(self)
            except Exception:
                pass

    def refresh_now(self) -> None:
        self._apply_theme(self._window)

    def nativeEventFilter(self, _event_type, message):  # noqa: N802 (Qt override)
        message_id, lparam = _native_message_id_and_lparam(message)
        if is_windows_theme_change_message(message_id, lparam):
            self._timer.start(self._debounce_ms)
        return False


def install_windows_system_theme_watcher(app, window) -> WindowsSystemThemeWatcher | None:
    watcher = WindowsSystemThemeWatcher(window=window)
    if not watcher.install(app):
        return None
    watcher.refresh_now()
    return watcher
