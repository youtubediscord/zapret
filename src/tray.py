# tray.py

from __future__ import annotations

import ctypes
import os
import sys
import time
from ctypes import wintypes

from PyQt6.QtCore import QTimer, QPoint
from PyQt6.QtGui import QAction, QCursor, QFontMetrics
from PyQt6.QtWidgets import QApplication, QInputDialog, QLineEdit, QMenu, QWidget

from ui.theme import get_themed_qta_icon

try:
    import qtawesome as qta

    HAS_QTAWESOME = True
except Exception:
    qta = None
    HAS_QTAWESOME = False

try:
    from qfluentwidgets import RoundMenu, Action, FluentIcon

    _HAS_FLUENT_MENU = True
except Exception:
    RoundMenu = None
    Action = None
    FluentIcon = None
    _HAS_FLUENT_MENU = False

try:
    from log import log
except Exception:
    def log(*args, **kwargs):  # type: ignore[no-redef]
        return None

from ui.popup_menu import exec_popup_menu


def _toggle_github_api_removal(*, status_callback=None) -> bool:
    """Переключает флаг удаления api.github.com из hosts при запуске."""
    from config import get_remove_github_api, set_remove_github_api

    try:
        current_state = bool(get_remove_github_api())
        new_state = not current_state

        if set_remove_github_api(new_state):
            state_text = "включено" if new_state else "отключено"
            message = f"Удаление api.github.com из hosts {state_text}"
            log(message, "INFO")
            if status_callback:
                status_callback(message)
            return True

        error_message = "Ошибка при сохранении настройки удаления GitHub API"
        log(error_message, "❌ ERROR")
        if status_callback:
            status_callback(error_message)
        return False
    except Exception as exc:
        error_message = f"Ошибка при переключении удаления GitHub API: {exc}"
        log(error_message, "❌ ERROR")
        if status_callback:
            status_callback(error_message)
        return False


if sys.platform == "win32":
    user32 = ctypes.windll.user32
    shell32 = ctypes.windll.shell32
    kernel32 = ctypes.windll.kernel32
    _PTR_IS_64 = ctypes.sizeof(ctypes.c_void_p) == 8
    WPARAM = ctypes.c_uint64 if _PTR_IS_64 else ctypes.c_uint
    LPARAM = ctypes.c_int64 if _PTR_IS_64 else ctypes.c_long
    LRESULT = getattr(
        ctypes,
        "c_ssize_t",
        ctypes.c_int64 if _PTR_IS_64 else ctypes.c_long,
    )

    IMAGE_ICON = 1
    LR_LOADFROMFILE = 0x0010
    LR_DEFAULTSIZE = 0x0040

    NIM_ADD = 0x00000000
    NIM_MODIFY = 0x00000001
    NIM_DELETE = 0x00000002
    NIM_SETFOCUS = 0x00000003
    NIM_SETVERSION = 0x00000004

    NIF_MESSAGE = 0x00000001
    NIF_ICON = 0x00000002
    NIF_TIP = 0x00000004
    NIF_INFO = 0x00000010
    NIF_SHOWTIP = 0x00000080

    NOTIFYICON_VERSION_4 = 4
    NIIF_NONE = 0x00000000
    NIIF_INFO = 0x00000001

    WM_APP = 0x8000
    WM_NULL = 0x0000
    WM_DESTROY = 0x0002
    WM_CLOSE = 0x0010
    WM_CONTEXTMENU = 0x007B
    WM_LBUTTONUP = 0x0202
    WM_RBUTTONUP = 0x0205
    WM_LBUTTONDBLCLK = 0x0203
    VK_LBUTTON = 0x01
    VK_RBUTTON = 0x02

    NIN_SELECT = WM_USER = 0x0400
    NIN_KEYSELECT = WM_USER + 1

    MF_STRING = 0x00000000
    MF_SEPARATOR = 0x00000800
    MF_POPUP = 0x00000010
    MF_GRAYED = 0x00000001

    TPM_LEFTALIGN = 0x0000
    TPM_BOTTOMALIGN = 0x0020
    TPM_RIGHTBUTTON = 0x0002
    TPM_RETURNCMD = 0x0100
    TPM_NONOTIFY = 0x0080

    IDI_APPLICATION = 32512
    CW_USEDEFAULT = 0x80000000

    TRAY_CALLBACK_MESSAGE = WM_APP + 100

    CMD_SHOW_WINDOW = 1001
    CMD_HIDE_TO_TRAY = 1002
    CMD_TG_PROXY_TOGGLE = 1003
    CMD_OPEN_CONSOLE = 1004
    CMD_EXIT_ONLY = 1005
    CMD_EXIT_AND_STOP = 1006
    CMD_OPACITY_BASE = 1100


    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", wintypes.DWORD),
            ("Data2", wintypes.WORD),
            ("Data3", wintypes.WORD),
            ("Data4", ctypes.c_ubyte * 8),
        ]


    class _NotifyIconTimeoutUnion(ctypes.Union):
        _fields_ = [
            ("uTimeout", wintypes.UINT),
            ("uVersion", wintypes.UINT),
        ]


    class NOTIFYICONDATAW(ctypes.Structure):
        _anonymous_ = ("timeout_version",)
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("hWnd", wintypes.HWND),
            ("uID", wintypes.UINT),
            ("uFlags", wintypes.UINT),
            ("uCallbackMessage", wintypes.UINT),
            ("hIcon", wintypes.HANDLE),
            ("szTip", wintypes.WCHAR * 128),
            ("dwState", wintypes.DWORD),
            ("dwStateMask", wintypes.DWORD),
            ("szInfo", wintypes.WCHAR * 256),
            ("timeout_version", _NotifyIconTimeoutUnion),
            ("szInfoTitle", wintypes.WCHAR * 64),
            ("dwInfoFlags", wintypes.DWORD),
            ("guidItem", GUID),
            ("hBalloonIcon", wintypes.HANDLE),
        ]


    WNDPROC = ctypes.WINFUNCTYPE(
        LRESULT,
        wintypes.HWND,
        wintypes.UINT,
        WPARAM,
        LPARAM,
    )


    class WNDCLASSEXW(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.UINT),
            ("style", wintypes.UINT),
            ("lpfnWndProc", WNDPROC),
            ("cbClsExtra", ctypes.c_int),
            ("cbWndExtra", ctypes.c_int),
            ("hInstance", wintypes.HINSTANCE),
            ("hIcon", wintypes.HICON),
            ("hCursor", wintypes.HCURSOR),
            ("hbrBackground", wintypes.HBRUSH),
            ("lpszMenuName", wintypes.LPCWSTR),
            ("lpszClassName", wintypes.LPCWSTR),
            ("hIconSm", wintypes.HICON),
        ]


    class POINT(ctypes.Structure):
        _fields_ = [
            ("x", ctypes.c_long),
            ("y", ctypes.c_long),
        ]


    user32.CreatePopupMenu.restype = wintypes.HMENU
    user32.TrackPopupMenu.restype = wintypes.UINT
    user32.RegisterWindowMessageW.restype = wintypes.UINT
    user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, WPARAM, LPARAM]
    user32.DefWindowProcW.restype = LRESULT
    user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
    user32.GetAsyncKeyState.restype = ctypes.c_short
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, WPARAM, LPARAM]
    user32.PostMessageW.restype = wintypes.BOOL


def _make_int_resource(identifier: int):
    if sys.platform != "win32":
        return None
    return ctypes.cast(ctypes.c_void_p(identifier), wintypes.LPCWSTR)


def _truncate_text(value: str, max_length: int) -> str:
    return str(value or "")[: max(0, max_length - 1)]


def _loword(value: int) -> int:
    return int(value) & 0xFFFF


def _hiword(value: int) -> int:
    return (int(value) >> 16) & 0xFFFF


def _signed_word(value: int) -> int:
    value = int(value) & 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def _get_x_lparam(value: int) -> int:
    return _signed_word(value)


def _get_y_lparam(value: int) -> int:
    return _signed_word(int(value) >> 16)


def _resolve_tg_proxy_manager():
    from telegram_proxy.manager import get_proxy_manager

    return get_proxy_manager()


def _fluent_icon(name: str):
    if FluentIcon is None:
        return None
    return getattr(FluentIcon, name, None)


def _make_menu_action(text: str, *, icon=None, parent=None):
    if Action is not None:
        if icon is not None:
            try:
                return Action(icon, text, parent)
            except TypeError:
                pass
        try:
            action = Action(text, parent)
        except TypeError:
            try:
                action = Action(text)
            except TypeError:
                action = None
        if action is not None:
            try:
                if icon is not None and hasattr(action, "setIcon"):
                    action.setIcon(icon)
            except Exception:
                pass
            return action

    action = QAction(text, parent)
    try:
        if icon is not None:
            action.setIcon(icon)
    except Exception:
        pass
    return action


def _widget_contains_global_pos(widget: QWidget, global_pos: QPoint | None) -> bool:
    if global_pos is None:
        return False

    try:
        top_left = widget.mapToGlobal(widget.rect().topLeft())
        bottom_right = widget.mapToGlobal(widget.rect().bottomRight())
        return (
            top_left.x() <= global_pos.x() <= bottom_right.x()
            and top_left.y() <= global_pos.y() <= bottom_right.y()
        )
    except Exception:
        return False


def _global_mouse_button_down(vk_code: int) -> bool:
    if sys.platform != "win32":
        return False

    try:
        return bool(user32.GetAsyncKeyState(int(vk_code)) & 0x8000)
    except Exception:
        return False


def _exec_tray_popup_menu(menu: QWidget, pos: QPoint, *, owner: QWidget | None) -> None:
    """Tray uses the shared popup lifecycle plus Windows click-outside polling."""

    exec_popup_menu(
        menu,
        pos,
        owner=owner,
        monitor_global_mouse=True,
    )


class SystemTrayManager:
    """Windows-first менеджер системного трея.

    Production-путь для Windows теперь один:
    native tray icon через Shell_NotifyIcon без Qt-tray слоя.
    """

    def __init__(self, parent, icon_path, app_version):
        self.parent = parent
        self.icon_path = os.path.abspath(icon_path)
        self.app_version = str(app_version or "").strip()
        self._icon_visible = False
        self._tray_hint_shown_this_session = False
        self._menu = None
        self._show_window_action = None
        self._tg_proxy_action = None
        self._exit_stop_action = None
        self._tray_menu_min_width = 336
        self._tray_submenu_min_width = 252
        self._toggle_request_pending = False
        self._last_toggle_monotonic = 0.0
        self._icon_handle = None
        self._message_window = None
        self._taskbar_created_message = None
        self._class_name = f"Zapret2TrayWindow_{os.getpid()}"

        if sys.platform != "win32":
            log("Native Windows tray backend недоступен вне Windows", "DEBUG")
            return

        self._create_native_backend()

    def _create_native_backend(self) -> None:
        self._icon_handle = self._load_icon_handle(self.icon_path)
        self._message_window = _TrayMessageWindow(self)
        self._taskbar_created_message = self._message_window.taskbar_created_message
        self._add_icon()
        self._connect_proxy_status_signal()

    def _load_icon_handle(self, icon_path: str):
        if sys.platform != "win32":
            return None

        handle = None
        if os.path.exists(icon_path):
            try:
                handle = user32.LoadImageW(
                    None,
                    icon_path,
                    IMAGE_ICON,
                    0,
                    0,
                    LR_LOADFROMFILE | LR_DEFAULTSIZE,
                )
            except Exception:
                handle = None

        if handle:
            return handle

        try:
            return user32.LoadIconW(None, _make_int_resource(IDI_APPLICATION))
        except Exception:
            return None

    def _build_notify_icon_data(self, flags: int) -> NOTIFYICONDATAW:
        data = NOTIFYICONDATAW()
        data.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        data.hWnd = self._hwnd
        data.uID = 1
        data.uFlags = flags
        data.uCallbackMessage = TRAY_CALLBACK_MESSAGE
        data.hIcon = self._icon_handle
        data.szTip = _truncate_text(f"Zapret2 v{self.app_version}", 128)
        return data

    @property
    def _hwnd(self):
        window = self._message_window
        return 0 if window is None else int(window.hwnd or 0)

    def _add_icon(self) -> None:
        if sys.platform != "win32" or not self._hwnd:
            return

        data = self._build_notify_icon_data(NIF_MESSAGE | NIF_ICON | NIF_TIP | NIF_SHOWTIP)
        if bool(shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(data))):
            data.uVersion = NOTIFYICON_VERSION_4
            shell32.Shell_NotifyIconW(NIM_SETVERSION, ctypes.byref(data))
            self._icon_visible = True
            log("Native tray icon added", "DEBUG")
        else:
            log("Не удалось добавить native tray icon", "WARNING")

    def recreate_icon(self) -> None:
        self.hide_icon()
        self._add_icon()

    def hide_icon(self) -> None:
        if sys.platform != "win32" or not self._hwnd or not self._icon_visible:
            return

        data = self._build_notify_icon_data(0)
        shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(data))
        self._icon_visible = False

    def cleanup(self) -> None:
        self.hide_icon()

        window = self._message_window
        self._message_window = None
        if window is not None:
            window.destroy()

        icon_handle = self._icon_handle
        self._icon_handle = None
        if sys.platform == "win32" and icon_handle:
            try:
                user32.DestroyIcon(icon_handle)
            except Exception:
                pass

    def _handle_native_callback(self, callback_code: int, anchor_x: int | None = None, anchor_y: int | None = None) -> None:
        if callback_code == WM_CONTEXTMENU:
            QTimer.singleShot(0, lambda: self.show_context_menu(anchor_x=anchor_x, anchor_y=anchor_y))
            return

        if callback_code in (WM_LBUTTONUP, WM_LBUTTONDBLCLK, NIN_SELECT, NIN_KEYSELECT):
            self._schedule_visibility_toggle()

    def _handle_taskbar_recreated(self) -> None:
        QTimer.singleShot(0, self.recreate_icon)

    def _schedule_visibility_toggle(self) -> None:
        if self._toggle_request_pending:
            return
        self._toggle_request_pending = True
        QTimer.singleShot(0, self._run_scheduled_visibility_toggle)

    def _run_scheduled_visibility_toggle(self) -> None:
        self._toggle_request_pending = False
        now = time.monotonic()
        if now - self._last_toggle_monotonic < 0.30:
            return
        self._last_toggle_monotonic = now
        self.toggle_window_visibility()

    def toggle_window_visibility(self) -> None:
        try:
            is_visible = bool(self.parent.isVisible())
        except Exception:
            is_visible = False

        if is_visible:
            self.hide_to_tray(show_hint=False)
            return

        self.show_window()

    def _build_menu_state(self) -> dict:
        is_visible = False
        is_launch_running = self._is_launch_running()
        launch_phase = self._launch_phase()
        tg_label = "Telegram Proxy: выкл"

        try:
            is_visible = bool(self.parent.isVisible())
        except Exception:
            is_visible = False

        try:
            mgr = _resolve_tg_proxy_manager()
            if mgr.is_running:
                tg_label = f"Telegram Proxy: вкл ({mgr.port})"
        except Exception:
            pass

        return {
            "is_visible": is_visible,
            "is_launch_running": is_launch_running,
            "launch_phase": launch_phase,
            "tg_proxy_label": tg_label,
        }

    def show_context_menu(self, anchor_x: int | None = None, anchor_y: int | None = None) -> None:
        menu = self._ensure_qt_menu()
        state = self._build_menu_state()
        self._apply_menu_style(menu)
        self._sync_menu_state(state)
        self._update_menu_widths(menu)

        try:
            if menu.isVisible():
                return
        except Exception:
            pass

        position = self._resolve_menu_position(menu, anchor_x=anchor_x, anchor_y=anchor_y)
        try:
            _exec_tray_popup_menu(menu, position, owner=self.parent)
        except Exception as e:
            log(f"Не удалось показать tray menu: {e}", "WARNING")

    def _ensure_qt_menu(self) -> QMenu:
        menu = getattr(self, "_menu", None)
        if menu is not None:
            return menu

        menu = RoundMenu(parent=self.parent) if _HAS_FLUENT_MENU and RoundMenu is not None else QMenu(self.parent)
        self._menu = menu
        try:
            menu.setMinimumWidth(self._tray_menu_min_width)
        except Exception:
            pass

        show_window_action = _make_menu_action(
            "Показать",
            icon=_fluent_icon("PLAY") if _HAS_FLUENT_MENU else (get_themed_qta_icon("fa5s.window-restore", color="#60cdff") if HAS_QTAWESOME else None),
            parent=menu,
        )
        show_window_action.triggered.connect(self._toggle_primary_visibility_action)
        menu.addAction(show_window_action)
        self._show_window_action = show_window_action

        opacity_title = (
            "Эффект акрилика окна"
            if self._is_windows_11_or_newer()
            else "Прозрачность окна"
        )
        opacity_menu = RoundMenu(parent=menu) if _HAS_FLUENT_MENU and RoundMenu is not None else QMenu(menu)
        try:
            opacity_menu.setMinimumWidth(self._tray_submenu_min_width)
        except Exception:
            pass
        try:
            opacity_menu.setTitle(opacity_title)
        except Exception:
            pass
        try:
            if _HAS_FLUENT_MENU:
                opacity_menu.setIcon(_fluent_icon("PALETTE"))
            elif HAS_QTAWESOME:
                opacity_menu.setIcon(get_themed_qta_icon("fa5s.adjust", color="#60cdff"))
        except Exception:
            pass
        menu.addMenu(opacity_menu)
        for value, title in self._opacity_presets():
            action = _make_menu_action(title, parent=opacity_menu)
            action.triggered.connect(lambda checked=False, v=value: self._set_window_opacity(v))
            opacity_menu.addAction(action)

        menu.addSeparator()

        tg_proxy_action = _make_menu_action(
            "Telegram Proxy: выкл",
            icon=_fluent_icon("SEND") if _HAS_FLUENT_MENU else (get_themed_qta_icon("fa5s.paper-plane", color="#60cdff") if HAS_QTAWESOME else None),
            parent=menu,
        )
        tg_proxy_action.triggered.connect(self._toggle_tg_proxy)
        menu.addAction(tg_proxy_action)
        self._tg_proxy_action = tg_proxy_action

        menu.addSeparator()

        console_action = _make_menu_action(
            "Консоль",
            icon=_fluent_icon("COMMAND_PROMPT") if _HAS_FLUENT_MENU else (get_themed_qta_icon("fa5s.terminal", color="#888888") if HAS_QTAWESOME else None),
            parent=menu,
        )
        console_action.triggered.connect(self.show_console)
        menu.addAction(console_action)

        menu.addSeparator()

        exit_only_action = _make_menu_action(
            "Выход",
            icon=_fluent_icon("RETURN") if _HAS_FLUENT_MENU else (get_themed_qta_icon("fa5s.sign-out-alt", color="#aaaaaa") if HAS_QTAWESOME else None),
            parent=menu,
        )
        exit_only_action.triggered.connect(self.exit_only)
        menu.addAction(exit_only_action)

        exit_stop_action = _make_menu_action(
            "Выход и остановить DPI",
            icon=_fluent_icon("POWER_BUTTON") if _HAS_FLUENT_MENU else (get_themed_qta_icon("fa5s.power-off", color="#e81123") if HAS_QTAWESOME else None),
            parent=menu,
        )
        exit_stop_action.triggered.connect(self.exit_and_stop)
        menu.addAction(exit_stop_action)
        self._exit_stop_action = exit_stop_action

        return menu

    def _sync_menu_state(self, state: dict) -> None:
        if self._show_window_action is not None:
            self._show_window_action.setText("Скрыть в трей" if state["is_visible"] else "Показать")

        if self._tg_proxy_action is not None:
            self._tg_proxy_action.setText(state["tg_proxy_label"])

        if self._exit_stop_action is not None:
            active_phases = {"autostart_pending", "starting", "running", "stopping"}
            self._exit_stop_action.setEnabled(
                bool(state["is_launch_running"]) or str(state.get("launch_phase") or "").strip().lower() in active_phases
            )

    def _update_menu_widths(self, menu: QMenu) -> None:
        try:
            self._apply_menu_min_width(menu, base_width=self._tray_menu_min_width)
        except Exception:
            pass

        try:
            for action in menu.actions():
                submenu = action.menu()
                if submenu is not None:
                    self._apply_menu_min_width(submenu, base_width=self._tray_submenu_min_width)
        except Exception:
            pass

    def _apply_menu_min_width(self, menu: QMenu, *, base_width: int) -> None:
        metrics = QFontMetrics(menu.font())
        widest_text = 0

        for action in menu.actions():
            try:
                text = str(action.text() or "")
            except Exception:
                text = ""
            if not text:
                continue
            widest_text = max(widest_text, metrics.horizontalAdvance(text))

        # Запас под иконку, внутренние отступы, стрелку подменю и
        # особенности first-show layout у RoundMenu.
        calculated_width = int(widest_text + 170)
        min_width = max(int(base_width), calculated_width)

        try:
            menu.setMinimumWidth(min_width)
        except Exception:
            pass

        try:
            menu.adjustSize()
        except Exception:
            pass

    def _toggle_primary_visibility_action(self) -> None:
        try:
            if self.parent.isVisible():
                self.hide_to_tray(show_hint=False)
            else:
                self.show_window()
        except Exception:
            pass

    def _resolve_menu_position(self, menu: QMenu, anchor_x: int | None = None, anchor_y: int | None = None) -> QPoint:
        if anchor_x is None or anchor_y is None or anchor_x == -1 or anchor_y == -1:
            global_pos = QCursor.pos()
        else:
            global_pos = QPoint(int(anchor_x), int(anchor_y))

        screen = QApplication.screenAt(global_pos)
        if screen is None:
            screen = QApplication.primaryScreen()
        if screen is None:
            return global_pos

        available = screen.availableGeometry()
        size = menu.sizeHint()
        x = int(global_pos.x())
        y = int(global_pos.y())
        gap = 8

        # Для нижнего трея меню должно открываться над иконкой, а не прилипать
        # к самой панели задач. Это визуально естественнее и не создаёт ощущение,
        # что меню "тонет" в нижней границе экрана.
        open_upwards = y >= available.bottom() - max(48, size.height() // 3)
        if open_upwards:
            y = y - size.height() - gap
        else:
            y = y + gap

        if x + size.width() > available.right():
            x = max(available.left(), available.right() - size.width())

        if y + size.height() > available.bottom():
            y = max(available.top(), y - size.height())

        if y < available.top():
            y = available.top()

        if x < available.left():
            x = available.left()

        return QPoint(x, y)

    def _apply_menu_style(self, menu: QMenu):
        if _HAS_FLUENT_MENU and RoundMenu is not None and isinstance(menu, RoundMenu):
            return

        try:
            from qfluentwidgets import isDarkTheme, themeColor

            is_light = not isDarkTheme()
            accent = themeColor().name()
        except Exception:
            is_light = False
            accent = "#60cdff"

        if is_light:
            bg_color = "#f3f3f3"
            text_color = "#111111"
            hover_bg = "rgba(0, 0, 0, 0.08)"
            border_color = "rgba(0, 0, 0, 0.18)"
            separator_color = "rgba(0, 0, 0, 0.10)"
        else:
            bg_color = "#1e1e1e"
            text_color = "#f5f5f5"
            hover_bg = "rgba(255, 255, 255, 0.08)"
            border_color = "rgba(255, 255, 255, 0.16)"
            separator_color = "rgba(255, 255, 255, 0.10)"

        menu.setStyleSheet(
            f"""
            QMenu {{
                background-color: {bg_color};
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 8px;
                padding: 6px 0px;
            }}
            QMenu::item {{
                background-color: transparent;
                color: {text_color};
                padding: 7px 16px 7px 10px;
                margin: 2px 6px;
                border-radius: 6px;
            }}
            QMenu::item:selected {{
                background-color: {hover_bg};
                border-left: 2px solid {accent};
                padding-left: 8px;
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {separator_color};
                margin: 5px 10px;
            }}
            """
        )

    def _set_focus_to_tray(self) -> None:
        if sys.platform != "win32" or not self._hwnd:
            return

        data = self._build_notify_icon_data(0)
        shell32.Shell_NotifyIconW(NIM_SETFOCUS, ctypes.byref(data))

    def show_notification(self, title, message, msec=5000):
        if sys.platform != "win32" or not self._hwnd or not self._icon_visible:
            return

        data = self._build_notify_icon_data(NIF_INFO)
        data.szInfoTitle = _truncate_text(str(title or ""), 64)
        data.szInfo = _truncate_text(str(message or ""), 256)
        data.dwInfoFlags = NIIF_INFO if str(title or "").strip() else NIIF_NONE
        data.uTimeout = int(max(1000, msec))
        shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(data))

    def _connect_proxy_status_signal(self) -> None:
        try:
            mgr = _resolve_tg_proxy_manager()
            mgr.status_changed.connect(self._on_tg_proxy_status_changed)
        except Exception:
            pass

    def _toggle_tg_proxy(self):
        try:
            mgr = _resolve_tg_proxy_manager()
            if mgr.is_running:
                mgr.stop_proxy()
                try:
                    from config.reg import set_tg_proxy_enabled
                    set_tg_proxy_enabled(False)
                except Exception:
                    pass
                return

            from config.reg import (
                get_tg_proxy_host,
                get_tg_proxy_port,
                get_tg_proxy_upstream_enabled,
                get_tg_proxy_upstream_host,
                get_tg_proxy_upstream_mode,
                get_tg_proxy_upstream_pass,
                get_tg_proxy_upstream_port,
                get_tg_proxy_upstream_user,
            )

            port = get_tg_proxy_port()
            host = get_tg_proxy_host()
            upstream_config = None
            try:
                if get_tg_proxy_upstream_enabled():
                    up_host = get_tg_proxy_upstream_host()
                    up_port = get_tg_proxy_upstream_port()
                    if up_host and up_port > 0:
                        from telegram_proxy.wss_proxy import UpstreamProxyConfig

                        upstream_config = UpstreamProxyConfig(
                            enabled=True,
                            host=up_host,
                            port=up_port,
                            mode=get_tg_proxy_upstream_mode(),
                            username=get_tg_proxy_upstream_user(),
                            password=get_tg_proxy_upstream_pass(),
                        )
            except Exception:
                pass

            import threading

            threading.Thread(
                target=lambda: mgr.start_proxy(
                    port=port,
                    mode="socks5",
                    host=host,
                    upstream_config=upstream_config,
                ),
                daemon=True,
                name="TrayTelegramProxyStart",
            ).start()
        except Exception as e:
            log(f"Tray TG proxy toggle error: {e}", "WARNING")

    def _on_tg_proxy_status_changed(self, running: bool):
        try:
            from config.reg import set_tg_proxy_enabled
            set_tg_proxy_enabled(bool(running))
        except Exception:
            pass

    def _save_window_geometry(self):
        try:
            controller = getattr(self.parent, "window_geometry_controller", None)
            if controller is not None:
                controller.persist_now(force=True)
        except Exception as e:
            log(f"Ошибка сохранения геометрии окна: {e}", "ERROR")

    def _cleanup_loaded_detail_page_overlays(self) -> None:
        try:
            from ui.router import get_zapret2_strategy_detail_pages
            from ui.main_window_page_dispatch import call_loaded_page_method

            for page_name in get_zapret2_strategy_detail_pages():
                try:
                    call_loaded_page_method(self.parent, page_name, "close_transient_overlays")
                except Exception:
                    pass
        except Exception:
            pass

    def _cleanup_transient_overlays(self) -> None:
        try:
            from ui.widgets.strategies_tooltip import strategies_tooltip_manager
            strategies_tooltip_manager.hide_immediately()
        except Exception:
            pass

        try:
            from strategy_menu.hover_tooltip import tooltip_manager
            tooltip_manager.hide_immediately()
        except Exception:
            pass

        try:
            from strategy_menu.args_preview_dialog import preview_manager
            preview_manager.cleanup()
        except Exception:
            pass

        self._cleanup_loaded_detail_page_overlays()

    def hide_to_tray(self, show_hint: bool = True) -> bool:
        try:
            self._cleanup_transient_overlays()
        except Exception:
            pass

        try:
            self._save_window_geometry()
        except Exception:
            pass

        try:
            if hasattr(self.parent, "_release_input_interaction_states"):
                self.parent._release_input_interaction_states()
        except Exception:
            pass

        try:
            self.parent.hide()
        except Exception as e:
            log(f"Не удалось скрыть окно в трей: {e}", "WARNING")
            return False

        if not show_hint:
            return True

        if not self._tray_hint_shown_this_session:
            try:
                self.show_notification(
                    "Zapret продолжает работать",
                    "Свернуто в трей. Кликните по иконке, чтобы открыть окно.",
                )
                self._tray_hint_shown_this_session = True
            except Exception:
                pass

        return True

    def exit_only(self):
        if hasattr(self.parent, "request_exit"):
            self.parent.request_exit(stop_dpi=False)

    def exit_and_stop(self):
        if hasattr(self.parent, "request_exit"):
            self.parent.request_exit(stop_dpi=True)

    def show_console(self):
        from discord.discord_restart import toggle_discord_restart

        cmd, ok = QInputDialog.getText(
            self.parent,
            "Консоль",
            "Введите команду:",
            QLineEdit.EchoMode.Normal,
            "",
        )
        if not ok or not cmd:
            return

        if cmd.lower() == "ркн":
            toggle_discord_restart(
                self.parent,
                status_callback=lambda m: self.show_notification("Консоль", m),
            )
            return

        if cmd.lower() == "апигитхаб":
            _toggle_github_api_removal(
                status_callback=lambda m: self.show_notification("Консоль", m),
            )

    def show_window(self):
        try:
            self._cleanup_transient_overlays()
        except Exception:
            pass

        controller = getattr(self.parent, "window_geometry_controller", None)
        if controller is not None:
            try:
                self.parent.show()
                self.parent.showNormal()
                controller.request_zoom_state(controller.remembered_zoom_state())
            except Exception:
                pass
        else:
            try:
                self.parent.show()
                self.parent.showNormal()
            except Exception:
                pass

        try:
            self.parent.raise_()
        except Exception:
            pass

        try:
            self.parent.activateWindow()
        except Exception:
            pass

    def _set_window_opacity(self, value: int) -> None:
        try:
            from config.reg import set_window_opacity as _set_window_opacity
            _set_window_opacity(int(value))
        except Exception:
            pass

        try:
            if hasattr(self.parent, "set_window_opacity"):
                self.parent.set_window_opacity(int(value))
        except Exception:
            pass

    def _is_launch_running(self) -> bool:
        app_runtime_state = getattr(self.parent, "app_runtime_state", None)
        if app_runtime_state is None:
            return False
        try:
            return bool(app_runtime_state.is_launch_running())
        except Exception:
            return False

    def _launch_phase(self) -> str:
        app_runtime_state = getattr(self.parent, "app_runtime_state", None)
        if app_runtime_state is None:
            return "stopped"
        try:
            phase = str(app_runtime_state.current_launch_phase() or "").strip().lower()
            return phase or ("running" if app_runtime_state.is_launch_running() else "stopped")
        except Exception:
            return "running" if self._is_launch_running() else "stopped"

    def _is_windows_11_or_newer(self) -> bool:
        try:
            return sys.platform == "win32" and sys.getwindowsversion().build >= 22000
        except Exception:
            return False

    def _opacity_presets(self) -> list[tuple[int, str]]:
        if self._is_windows_11_or_newer():
            return [
                (100, "100% (максимальный эффект)"),
                (75, "75%"),
                (50, "50%"),
                (25, "25%"),
                (0, "0% (минимальный эффект)"),
            ]
        return [
            (100, "100% (непрозрачное)"),
            (75, "75%"),
            (50, "50%"),
            (25, "25%"),
            (0, "0% (прозрачный фон)"),
        ]


class _TrayMessageWindow:
    """Скрытое top-level окно для callback-сообщений notification area."""

    def __init__(self, owner: SystemTrayManager):
        self.owner = owner
        self.hwnd = None
        self.taskbar_created_message = None
        self._wndproc = None

        if sys.platform == "win32":
            self._create_window()

    def _create_window(self) -> None:
        self.taskbar_created_message = user32.RegisterWindowMessageW("TaskbarCreated")
        instance = kernel32.GetModuleHandleW(None)

        self._wndproc = WNDPROC(self._dispatch)
        window_class = WNDCLASSEXW()
        window_class.cbSize = ctypes.sizeof(WNDCLASSEXW)
        window_class.lpfnWndProc = self._wndproc
        window_class.hInstance = instance
        window_class.lpszClassName = self.owner._class_name

        atom = user32.RegisterClassExW(ctypes.byref(window_class))
        if not atom:
            last_error = ctypes.get_last_error()
            # 1410 = class already exists.
            if last_error != 1410:
                raise OSError(last_error, "Не удалось зарегистрировать класс tray window")

        hwnd = user32.CreateWindowExW(
            0,
            self.owner._class_name,
            self.owner._class_name,
            0,
            CW_USEDEFAULT,
            CW_USEDEFAULT,
            0,
            0,
            None,
            None,
            instance,
            None,
        )
        if not hwnd:
            raise OSError(ctypes.get_last_error(), "Не удалось создать native tray window")

        self.hwnd = hwnd

    def destroy(self) -> None:
        hwnd = self.hwnd
        self.hwnd = None
        if sys.platform != "win32" or not hwnd:
            return

        try:
            user32.DestroyWindow(hwnd)
        except Exception:
            pass

    def _dispatch(self, hwnd, message, w_param, l_param):
        try:
            if message == TRAY_CALLBACK_MESSAGE:
                callback_code = _loword(int(l_param))
                anchor_x = _get_x_lparam(int(w_param))
                anchor_y = _get_y_lparam(int(w_param))
                self.owner._handle_native_callback(callback_code, anchor_x=anchor_x, anchor_y=anchor_y)
                return 0

            if self.taskbar_created_message and message == self.taskbar_created_message:
                self.owner._handle_taskbar_recreated()
                return 0

            if message in (WM_CLOSE, WM_DESTROY):
                return 0
        except Exception as e:
            log(f"Ошибка обработки native tray message: {e}", "DEBUG")

        return user32.DefWindowProcW(hwnd, message, w_param, l_param)
