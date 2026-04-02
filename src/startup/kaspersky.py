# startup/kaspersky.py
from __future__ import annotations
import os
import sys

def _open_url(url: str):
    from PyQt6.QtCore import QUrl
    from PyQt6.QtGui import QDesktopServices
    QDesktopServices.openUrl(QUrl(url))


def _resolve_kaspersky_paths() -> tuple[str, str]:
    """Возвращает путь к exe и рабочую папку приложения."""
    if getattr(sys, "frozen", False):
        exe_path = os.path.abspath(sys.executable)
        base_dir = os.path.dirname(exe_path)
    else:
        exe_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "zapret.pyw")
        )
        base_dir = os.path.dirname(exe_path)
    return exe_path, base_dir

def _check_kaspersky_antivirus(self):
    """
    Проверяет наличие антивируса Касперского в системе.
    
    Returns:
        bool: True если Касперский обнаружен, False если нет
    """
    #return True # для тестирования
    try:
        import subprocess
        import os
        
        # Проверяем наличие процессов Касперского
        kaspersky_processes = [
            'avp.exe', 'kavfs.exe', 'klnagent.exe', 'ksde.exe',
            'kavfswp.exe', 'kavfswh.exe', 'kavfsslp.exe'
        ]
        
        # Получаем список запущенных процессов через psutil (быстрее и надежнее)
        try:
            import psutil
            for proc in psutil.process_iter(['name']):
                try:
                    proc_name = proc.info['name']
                    if proc_name and proc_name.lower() in kaspersky_processes:
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass
        
        # Проверяем папки установки Касперского
        kaspersky_paths = [
            r'C:\Program Files\Kaspersky Lab',
            r'C:\Program Files (x86)\Kaspersky Lab',
            r'C:\Program Files\Kaspersky Security',
            r'C:\Program Files (x86)\Kaspersky Security'
        ]
        
        for path in kaspersky_paths:
            if os.path.exists(path) and os.path.isdir(path):
                try:
                    # Проверяем, что папка не пустая
                    dir_contents = os.listdir(path)
                    if dir_contents:
                        # Дополнительно проверяем наличие исполняемых файлов или подпапок
                        for item in dir_contents:
                            item_path = os.path.join(path, item)
                            if os.path.isdir(item_path) or item.lower().endswith(('.exe', '.dll')):
                                return True
                except (PermissionError, OSError):
                    # Если нет доступа к папке, но она существует - считаем что Касперский есть
                    return True
        
        # Если ни один процесс не найден и папки пустые/не найдены, считаем что Касперского нет
        return False
        
    except Exception as e:
        # В случае ошибки считаем, что Касперского нет
        return False

def _check_kaspersky_warning_disabled():
    """
    Проверяет, отключено ли предупреждение о Kaspersky в реестре.
    
    Returns:
        bool: True если предупреждение отключено, False если нет
    """
    try:
        import winreg
        
        # Путь к ключу реестра
        key_path = r"Software\ZapretReg2"
        value_name = "DisableKasperskyWarning"
        
        # Пытаемся открыть ключ
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
                value, _ = winreg.QueryValueEx(key, value_name)
                return value == 1
        except (FileNotFoundError, OSError):
            return False
            
    except ImportError:
        # Если winreg недоступен (не Windows), возвращаем False
        return False

def _set_kaspersky_warning_disabled(disabled: bool):
    """
    Сохраняет в реестре настройку отключения предупреждения о Kaspersky.
    
    Args:
        disabled: True для отключения предупреждения, False для включения
    """
    try:
        import winreg
        
        # Путь к ключу реестра
        key_path = r"Software\ZapretReg2"
        value_name = "DisableKasperskyWarning"
        
        # Создаем или открываем ключ
        try:
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, value_name, 0, winreg.REG_DWORD, 1 if disabled else 0)
        except Exception as e:
            print(f"Ошибка при записи в реестр: {e}")
            
    except ImportError:
        # Если winreg недоступен (не Windows), ничего не делаем
        pass


def disable_kaspersky_warning_forever() -> None:
    """Отключает дальнейшие предупреждения о Kaspersky."""
    _set_kaspersky_warning_disabled(True)


def get_kaspersky_warning_details() -> dict | None:
    """Возвращает данные предупреждения для неблокирующего показа на старте."""
    if _check_kaspersky_warning_disabled():
        return None

    exe_path, base_dir = _resolve_kaspersky_paths()
    content = (
        "Обнаружен антивирус Kaspersky.\n"
        "Чтобы Zapret работал стабильно, добавьте программу в исключения.\n"
        f"Папка: {base_dir}\n"
        f"Файл: {exe_path}\n"
        "Без исключения антивирус может мешать запуску и работе программы."
    )
    return {
        "title": "Обнаружен Kaspersky",
        "content": content,
        "base_dir": base_dir,
        "exe_path": exe_path,
    }

def show_kaspersky_warning(parent=None) -> None:
    """
    Показывает Qt-диалог с предупреждением, «кликабельными» путями и
    кнопками копирования.  Требует уже созданный QApplication.
    """
    # Проверяем, не отключено ли предупреждение
    if _check_kaspersky_warning_disabled():
        return

    exe_path, base_dir = _resolve_kaspersky_paths()

    # -- сам QMessageBox -----------------------------------------------------------
    from PyQt6.QtWidgets import QMessageBox, QPushButton, QApplication, QCheckBox
    from PyQt6.QtCore    import Qt, QUrl
    from PyQt6.QtGui     import QDesktopServices, QIcon

    mb = QMessageBox(parent)
    mb.setWindowTitle("Zapret – Обнаружен Kaspersky")
    mb.setIcon(QMessageBox.Icon.Warning)
    mb.setTextFormat(Qt.TextFormat.RichText)

    # ✨ HTML-текст со ссылками (file:// …) – Windows их открывает проводником
    mb.setText(
        "⚠️ <b>ВНИМАНИЕ: Обнаружен антивирус Kaspersky!</b><br><br>"
        "Для корректной работы Zapret необходимо добавить программу в исключения.<br><br>"
        "<b>ИНСТРУКЦИЯ</b>:<br>"
        "1. Откройте Kaspersky → Настройки<br>"
        "2. «Исключения» / «Доверенная зона»<br>"
        "3. Добавьте:<br>"
        f"&nbsp;&nbsp;• Папку:&nbsp;"
        f"<a href='file:///{base_dir.replace(os.sep, '/')}'>{base_dir}</a><br>"
        f"&nbsp;&nbsp;• Файл:&nbsp;"
        f"<a href='file:///{exe_path.replace(os.sep, '/')}'>{exe_path}</a><br>"
        "4. Сохраните и перезапустите Zapret.<br><br>"
        "Без добавления в исключения программа может работать некорректно."
    )

    # -- добавляем чекбокс "Больше не показывать" ---------------------------------
    dont_show_checkbox = QCheckBox("Больше никогда не показывать это предупреждение")
    mb.setCheckBox(dont_show_checkbox)

    # -- добавляем 2 кастомных «копирующих» кнопки --------------------------------
    copy_dir_btn  = QPushButton("📋 Копировать папку")
    copy_exe_btn  = QPushButton("📋 Копировать exe")
    mb.addButton(copy_dir_btn, QMessageBox.ButtonRole.ActionRole)
    mb.addButton(copy_exe_btn, QMessageBox.ButtonRole.ActionRole)

    # 2) отключаем «кнопка по умолчанию» – иначе клик интерпретируется
    #    как Accept и QMessageBox закрывается
    for btn in (copy_dir_btn, copy_exe_btn):
        btn.setAutoDefault(False)
        btn.setDefault(False)

    # стандартный OK, который действительно закрывает окно
    ok_btn = mb.addButton(QMessageBox.StandardButton.Ok)
    mb.setDefaultButton(ok_btn)

    # -- обработка копирования -----------------------------------------------------
    def copy_to_clipboard(text: str):
        QApplication.clipboard().setText(text)
    copy_dir_btn.clicked.connect(lambda: copy_to_clipboard(base_dir))
    copy_exe_btn.clicked.connect(lambda: copy_to_clipboard(exe_path))

    if hasattr(mb, "linkActivated"):
        mb.linkActivated.connect(_open_url)
    else:
        # fallback для старых/обрезанных сборок
        from PyQt6.QtWidgets import QLabel
        lbl = mb.findChild(QLabel, "qt_msgbox_label")
        if lbl is not None and hasattr(lbl, "linkActivated"):
            lbl.setOpenExternalLinks(False)
            lbl.linkActivated.connect(_open_url)

    # Показываем диалог
    mb.exec()
    
    # Сохраняем настройку в реестр, если пользователь поставил галочку
    if dont_show_checkbox.isChecked():
        _set_kaspersky_warning_disabled(True)
