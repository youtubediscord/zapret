# remove_terminal.py

import os, subprocess, ctypes, sys
from pathlib import Path
from config import reg
from utils import run_hidden

# ---------------------------------------------------------------------------
# 1) Мини-хелперы
# ---------------------------------------------------------------------------
# ───────────── Удаление Windows Terminal ─────────────
_WT_KEY  = r"Software\ZapretReg2"
_WT_NAME = "RemoveWindowsTerminal"     # REG_DWORD (1/0)

def get_remove_windows_terminal() -> bool:
    """True – удалять Windows Terminal при запуске, False – не удалять."""
    val = reg(_WT_KEY, _WT_NAME)
    return bool(val) if val is not None else True   # дефолт = True (удалять)

def set_remove_windows_terminal(enabled: bool) -> bool:
    """Включает/выключает удаление Windows Terminal при запуске."""
    return reg(_WT_KEY, _WT_NAME, 1 if enabled else 0)

def _is_windows_11() -> bool:
    "Очень грубая проверка – номер сборки 22000+ ⇒ Windows 11."
    return sys.getwindowsversion().build >= 22000

def _wt_stub_exists() -> bool:
    """
    Быстрая проверка: у MS-Store-версии всегда присутствует stub
    %USERPROFILE%\\AppData\\Local\\Microsoft\\WindowsApps\\wt.exe.
    """
    stub = (
        Path(os.environ["USERPROFILE"])
        / "AppData" / "Local" / "Microsoft" / "WindowsApps" / "wt.exe"
    )
    return stub.exists()

# ---------------------------------------------------------------------------
# 2) Основная функция
# ---------------------------------------------------------------------------

def remove_windows_terminal_if_win11():
    """
    На Windows 11 удаляет MS-Store-версию Windows Terminal,
    но делает это ТОЛЬКО если:
    1. Терминал действительно установлен
    2. Пользователь включил эту опцию в настройках
    Если wt.exe-стаба нет или функция отключена – функция мгновенно возвращает управление.
    """
    from log import log   # импорт здесь, чтобы не тащить log в глобалы

    try:
        # 0. Проверяем настройку пользователя в реестре
        
        if not get_remove_windows_terminal():
            log("Удаление Windows Terminal отключено пользователем в настройках", level="INFO")
            return
        
        # 1. Требования к запуску
        if not _is_windows_11():
            return                  # не Win11 → ничего не делаем

        if not _wt_stub_exists():
            log("Windows Terminal не обнаружен – пропускаем удаление.")
            return                  # терминала нет → выходим

        log("Обнаружен Windows Terminal – выполняем удаление (согласно настройкам пользователя)…")

        # PowerShell-команды
        ps_remove_user = (
            'Get-AppxPackage -Name Microsoft.WindowsTerminal '
            '| Remove-AppxPackage -AllUsers'
        )
        ps_remove_prov = (
            'Get-AppxProvisionedPackage -Online '
            '| Where-Object {$_.PackageName -like "*WindowsTerminal*"} '
            '| Remove-AppxProvisionedPackage -Online'
        )

        for cmd in (ps_remove_user, ps_remove_prov):
            run_hidden(
                ["powershell", "-NoLogo", "-NoProfile", "-Command", cmd],
                wait=True  # ждём завершения, ошибки игнорируем
            )

        log("Windows Terminal удалён (или уже отсутствовал).")

    except Exception as e:
        log(f"remove_windows_terminal_if_win11: {e}")