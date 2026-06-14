from __future__ import annotations

import ctypes
import sys
from dataclasses import dataclass
from typing import Callable


MIN_WINDOWS_10_1809_BUILD = 17763
CONSOLE_VERSION_URL = "https://t.me/bypassblock/666"
WINDOWS_VERSION_ERROR_TITLE = "Zapret — неподдерживаемая Windows"


@dataclass(frozen=True, slots=True)
class WindowsSupportResult:
    supported: bool
    os_name: str = ""
    message: str = ""


def _version_part(version, name: str, default: int = 0) -> int:
    try:
        return int(getattr(version, name))
    except Exception:
        return default


def _old_windows_name(major: int, minor: int) -> str:
    if major == 6 and minor == 1:
        return "Windows 7"
    if major == 6 and minor == 2:
        return "Windows 8"
    if major == 6 and minor == 3:
        return "Windows 8.1"
    if major == 6 and minor == 0:
        return "Windows Vista"
    if major < 6:
        return "старая Windows"
    return f"Windows {major}.{minor}"


def _unsupported_message(os_name: str) -> str:
    return (
        f"Обнаружена неподдерживаемая система: {os_name}\n\n"
        "GUI-версия Zapret требует Windows 10 1809 или новее "
        f"(build {MIN_WINDOWS_10_1809_BUILD}+).\n\n"
        "Для вашей операционной системы доступна консольная версия:\n"
        f"{CONSOLE_VERSION_URL}\n\n"
        "Рекомендуем обновить Windows до Windows 10 1809, Windows 10 22H2 "
        "или Windows 11, чтобы пользоваться GUI-версией."
    )


def evaluate_windows_support(version, *, platform_name: str) -> WindowsSupportResult:
    if platform_name != "win32":
        return WindowsSupportResult(supported=True)

    major = _version_part(version, "major")
    minor = _version_part(version, "minor")
    build = _version_part(version, "build")

    if major > 10:
        return WindowsSupportResult(supported=True)

    if major == 10:
        if build >= MIN_WINDOWS_10_1809_BUILD:
            return WindowsSupportResult(supported=True)
        os_name = "Windows 10 до 1809"
        return WindowsSupportResult(
            supported=False,
            os_name=os_name,
            message=_unsupported_message(os_name),
        )

    os_name = _old_windows_name(major, minor)
    return WindowsSupportResult(
        supported=False,
        os_name=os_name,
        message=_unsupported_message(os_name),
    )


def current_windows_support(
    *,
    platform_name: str | None = None,
    version_getter: Callable[[], object] | None = None,
) -> WindowsSupportResult:
    platform_value = sys.platform if platform_name is None else platform_name
    if platform_value != "win32":
        return WindowsSupportResult(supported=True)

    getter = version_getter or sys.getwindowsversion
    try:
        version = getter()
    except Exception:
        return WindowsSupportResult(supported=True)

    return evaluate_windows_support(version, platform_name=platform_value)


def _show_plain_windows_message(title: str, message: str) -> None:
    try:
        ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)
    except Exception:
        print(f"{title}\n\n{message}", file=sys.stderr)


def enforce_early_windows_version_guard(
    *,
    version_getter: Callable[[], object] | None = None,
    platform_name: str | None = None,
    show_message: Callable[[str, str], None] | None = None,
    exit_app: Callable[[int], None] | None = None,
) -> None:
    result = current_windows_support(
        platform_name=platform_name,
        version_getter=version_getter,
    )
    if result.supported:
        return

    notify = show_message or _show_plain_windows_message
    notify(WINDOWS_VERSION_ERROR_TITLE, result.message)

    exit_fn = exit_app or sys.exit
    exit_fn(1)
