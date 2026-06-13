from __future__ import annotations

import os
import platform
import subprocess
from typing import Iterable

from log.log import log


WINDOWS_SERVER_WLANAPI_MARKER = "[WINDOWS_SERVER_WLANAPI]"
WIRELESS_NETWORKING_FEATURE_NAME = "Wireless-Networking"


def is_windows_server() -> bool:
    if os.name != "nt":
        return False

    try:
        edition = str(platform.win32_edition() or "").strip().lower()
        if "server" in edition:
            return True
    except Exception:
        pass

    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion") as key:
            for value_name in ("InstallationType", "ProductName", "EditionID"):
                try:
                    value, _kind = winreg.QueryValueEx(key, value_name)
                except OSError:
                    continue
                if "server" in str(value or "").strip().lower():
                    return True
    except Exception:
        pass

    return False


def has_wlanapi_missing(missing_dlls: Iterable[str]) -> bool:
    return any(str(name or "").strip().lower() == "wlanapi.dll" for name in missing_dlls)


def should_offer_windows_server_wlanapi_install(missing_dlls: Iterable[str]) -> bool:
    return has_wlanapi_missing(missing_dlls) and is_windows_server()


def mark_windows_server_wlanapi_message(message: str) -> str:
    text = str(message or "").strip()
    if text.startswith(WINDOWS_SERVER_WLANAPI_MARKER):
        return text
    return f"{WINDOWS_SERVER_WLANAPI_MARKER} {text}".strip()


def run_windows_server_wlanapi_install() -> tuple[bool, str]:
    if os.name != "nt":
        return False, "Команда установки доступна только в Windows Server."

    script = (
        "$ErrorActionPreference = 'Stop'; "
        "$p = Start-Process -FilePath 'powershell.exe' "
        "-ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-Command',"
        f"'Install-WindowsFeature -Name {WIRELESS_NETWORKING_FEATURE_NAME}') "
        "-Verb RunAs -Wait -PassThru; "
        "exit $p.ExitCode"
    )

    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1800,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, "Установка компонента Windows заняла слишком много времени."
    except Exception as exc:
        log(f"Не удалось запустить установку Wireless-Networking: {exc}", "ERROR")
        return False, f"Не удалось запустить PowerShell: {exc}"

    output = "\n".join(
        part.strip()
        for part in (result.stdout, result.stderr)
        if part and part.strip()
    ).strip()
    if result.returncode == 0:
        return True, (
            "Компонент Wireless-Networking установлен. "
            "Перезагрузите Windows Server и запустите DPI ещё раз."
        )

    message = output or "PowerShell завершился с ошибкой."
    return False, f"Компонент Wireless-Networking не установлен: {message}"
