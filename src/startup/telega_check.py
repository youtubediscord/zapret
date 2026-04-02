# startup/telega_check.py
"""
Обнаружение поддельного клиента «Telega Desktop» —
неофициальная модификация Telegram, которая может перехватывать переписку.
"""
from __future__ import annotations
import os
import sys


def _check_telega_installed() -> str | None:
    """
    Проверяет наличие «Telega Desktop» в системе.

    Returns:
        Путь к обнаруженному файлу/папке, или None если не найдено.
    """
    try:
        appdata_roaming = os.environ.get("APPDATA", "")
        appdata_local = os.environ.get("LOCALAPPDATA", "")
        user_profile = os.environ.get("USERPROFILE", "")

        # Папки и exe, которые может создать Telega Desktop
        check_paths = []

        for base in (appdata_roaming, appdata_local):
            if not base:
                continue
            check_paths += [
                os.path.join(base, "Telega Desktop", "Telega.exe"),
                os.path.join(base, "Telega Desktop"),
                os.path.join(base, "TelegaDesktop", "Telega.exe"),
                os.path.join(base, "TelegaDesktop"),
            ]

        # Ярлыки в меню «Пуск»
        if appdata_roaming:
            start_menu = os.path.join(
                appdata_roaming, "Microsoft", "Windows", "Start Menu", "Programs"
            )
            check_paths += [
                os.path.join(start_menu, "Telega Desktop", "Telega.lnk"),
                os.path.join(start_menu, "Telega Desktop"),
                os.path.join(start_menu, "TelegaDesktop", "Telega.lnk"),
                os.path.join(start_menu, "TelegaDesktop"),
            ]

        # Ярлык на рабочем столе
        if user_profile:
            desktop = os.path.join(user_profile, "Desktop")
            check_paths += [
                os.path.join(desktop, "Telega.lnk"),
                os.path.join(desktop, "Telega Desktop.lnk"),
            ]

        # Program Files (на случай системной установки)
        for pf in (r"C:\Program Files", r"C:\Program Files (x86)"):
            check_paths += [
                os.path.join(pf, "Telega Desktop", "Telega.exe"),
                os.path.join(pf, "Telega Desktop"),
            ]

        for path in check_paths:
            if os.path.exists(path):
                return path

        # Дополнительно: проверяем запущенные процессы
        try:
            import psutil
            for proc in psutil.process_iter(["name"]):
                try:
                    name = proc.info["name"]
                    if name and name.lower() == "telega.exe":
                        return f"Процесс: {name}"
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass

        return None
    except Exception:
        return None


def _check_telega_warning_disabled() -> bool:
    """Проверяет, отключено ли предупреждение о Telega в реестре."""
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, r"Software\ZapretReg2", 0, winreg.KEY_READ
        ) as key:
            value, _ = winreg.QueryValueEx(key, "DisableTelegaWarning")
            return value == 1
    except Exception:
        return False


def _set_telega_warning_disabled(disabled: bool) -> None:
    """Сохраняет в реестре настройку отключения предупреждения о Telega."""
    try:
        import winreg
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER, r"Software\ZapretReg2", 0, winreg.KEY_WRITE
        ) as key:
            winreg.SetValueEx(key, "DisableTelegaWarning", 0, winreg.REG_DWORD, 1 if disabled else 0)
    except Exception:
        pass


def disable_telega_warning_forever() -> None:
    """Отключает дальнейшие предупреждения о Telega Desktop."""
    _set_telega_warning_disabled(True)


def get_telega_warning_details(found_path: str = "") -> dict | None:
    """Возвращает данные предупреждения для неблокирующего показа на старте."""
    if _check_telega_warning_disabled():
        return None

    path_line = f"\nОбнаружено: {found_path}" if found_path else ""
    content = (
        "Обнаружена программа Telega Desktop.\n"
        "Это неофициальная модификация Telegram, которая может читать переписку."
        f"{path_line}\n"
        "Рекомендуется удалить её, поставить официальный Telegram и завершить сторонние сессии."
    )
    return {
        "title": "Обнаружена Telega Desktop",
        "content": content,
        "found_path": found_path,
        "official_url": "https://desktop.telegram.org",
    }


def show_telega_warning(parent=None, found_path: str = "") -> None:
    """
    Показывает предупреждение о поддельном клиенте «Telega Desktop».
    """
    if _check_telega_warning_disabled():
        return

    from PyQt6.QtWidgets import QMessageBox, QCheckBox
    from PyQt6.QtCore import Qt

    mb = QMessageBox(parent)
    mb.setWindowTitle("Zapret – Обнаружена Telega Desktop")
    mb.setIcon(QMessageBox.Icon.Critical)
    mb.setTextFormat(Qt.TextFormat.RichText)

    path_line = ""
    if found_path:
        path_line = f"<br>Обнаружено: <code>{found_path}</code><br>"

    mb.setText(
        "🚨 <b>ВНИМАНИЕ: Обнаружена программа «Telega Desktop»!</b><br><br>"
        "«Telega Desktop» — это <b>не Telegram</b>. Это неофициальная модификация, "
        "которая может <b>перехватывать и читать ваши сообщения</b>."
        f"{path_line}<br>"
        "<b>Рекомендуется:</b><br>"
        "1. <b>Немедленно удалите</b> «Telega Desktop»<br>"
        "2. Установите официальный клиент Telegram с сайта "
        "<a href='https://desktop.telegram.org'>desktop.telegram.org</a><br>"
        "3. Смените пароль и завершите все сторонние сессии в настройках Telegram<br><br>"
        "⚠️ <b>Ваши сообщения могут быть скомпрометированы!</b>"
    )

    dont_show_checkbox = QCheckBox("Больше не показывать это предупреждение")
    mb.setCheckBox(dont_show_checkbox)

    mb.addButton(QMessageBox.StandardButton.Ok)
    mb.setDefaultButton(QMessageBox.StandardButton.Ok)

    mb.exec()

    if dont_show_checkbox.isChecked():
        _set_telega_warning_disabled(True)
