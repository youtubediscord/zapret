"""
run_hidden – единый «тихий» запуск процессов (без всплывающего окна)
Работает даже если вызывают с shell=True или передают строку команды.
"""

from __future__ import annotations
import os, subprocess, sys, shlex, tempfile
from typing import Sequence, Union
from functools import lru_cache


import ctypes

# WinAPI функции для получения системных путей
_kernel32 = ctypes.windll.kernel32


@lru_cache(maxsize=1)
def get_system32_path() -> str:
    """
    Возвращает путь к System32 через WinAPI GetSystemDirectoryW.
    Работает на любом диске (C:, D:, и т.д.).
    """
    buf = ctypes.create_unicode_buffer(260)
    length = _kernel32.GetSystemDirectoryW(buf, 260)
    if length > 0:
        return buf.value
    # Fallback через переменные окружения
    system_root = os.environ.get("SystemRoot") or os.environ.get("WINDIR")
    if system_root:
        return os.path.join(system_root, "System32")
    return r"C:\Windows\System32"


@lru_cache(maxsize=1)
def get_windows_path() -> str:
    """
    Возвращает путь к Windows через WinAPI GetWindowsDirectoryW.
    """
    buf = ctypes.create_unicode_buffer(260)
    length = _kernel32.GetWindowsDirectoryW(buf, 260)
    if length > 0:
        return buf.value
    return os.environ.get("SystemRoot") or os.environ.get("WINDIR") or r"C:\Windows"


@lru_cache(maxsize=1)
def get_syswow64_path() -> str:
    """
    Возвращает путь к SysWOW64 (32-битные программы на 64-битной Windows).
    """
    return os.path.join(get_windows_path(), "SysWOW64")


def get_system_exe(exe_name: str) -> str:
    """
    Возвращает полный путь к системному исполняемому файлу.
    Пример: get_system_exe("tasklist.exe") -> "D:\\Windows\\System32\\tasklist.exe"
    """
    return os.path.join(get_system32_path(), exe_name)

# Максимальный набор флагов для полного скрытия окон
WIN_FLAGS = (subprocess.CREATE_NO_WINDOW | 
             subprocess.DETACHED_PROCESS | 
             subprocess.CREATE_NEW_PROCESS_GROUP |
             subprocess.CREATE_NEW_CONSOLE |
             0x00000008)   # CREATE_BREAKAWAY_FROM_JOB

WIN_OEM   = "cp866"
UTF8      = "utf-8"


def _default_encoding() -> str:
    return WIN_OEM if os.name == "nt" else UTF8


def _hidden_startupinfo() -> subprocess.STARTUPINFO:
    si = subprocess.STARTUPINFO()
    # Используем только существующие константы из subprocess
    si.dwFlags |= (subprocess.STARTF_USESHOWWINDOW | 
                   subprocess.STARTF_USESTDHANDLES)
    si.wShowWindow = subprocess.SW_HIDE
    return si


def _prepare_cmd(cmd, use_shell: bool):
    """
    Если caller хочет shell=True / передал строку,
    превращаем это в ['cmd','/Q','/C', ...] + shell=False,
    чтобы всё равно прятать окно.
    """
    if sys.platform != "win32":
        return cmd, use_shell      # на *nix не меняем

    cmd_exe = get_system_exe("cmd.exe")

    if use_shell:
        if isinstance(cmd, str):
            return [cmd_exe, '/Q', '/C', cmd], False
        else:               # список + shell=True
            return [cmd_exe, '/Q', '/C', *cmd], False

    if isinstance(cmd, str):       # shell=False, но строка → тоже оборачиваем
        return [cmd_exe, '/Q', '/C', cmd], False

    return cmd, use_shell


def run_bat_through_vbs(bat_path: str, cwd: str = None) -> subprocess.Popen:
    """Запускает BAT файл через VBScript для максимального скрытия"""
    if not cwd:
        cwd = os.path.dirname(bat_path)
    
    # Создаем VBS скрипт для скрытого запуска
    vbs_content = f'''
Set objShell = CreateObject("Wscript.Shell")
objShell.CurrentDirectory = "{cwd}"
objShell.Run "cmd /c ""{bat_path}""", 0, False
'''
    
    # Создаем временный VBS файл
    with tempfile.NamedTemporaryFile(mode='w', suffix='.vbs', delete=False) as f:
        f.write(vbs_content)
        vbs_path = f.name
    
    try:
        # Запускаем VBS скрипт
        process = subprocess.Popen(
            ['wscript.exe', vbs_path],
            creationflags=WIN_FLAGS,
            startupinfo=_hidden_startupinfo(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return process
    finally:
        # Удаляем VBS файл через небольшую задержку
        import threading
        def cleanup():
            import time
            time.sleep(2)  # Даем время VBS файлу выполниться
            try:
                os.unlink(vbs_path)
            except:
                pass
        threading.Thread(target=cleanup, daemon=True).start()


def run_hidden(cmd: Union[str, Sequence[str]],
               *,
               wait: bool = False,
               capture_output: bool = False,
               timeout: int | None = None,
               text: bool | None = None,
               encoding: str | None = None,
               errors: str = "replace",
               shell: bool = False,
               cwd: str | None = None,
               env: dict | None = None,
               use_vbs_for_bat: bool = True,  # Новый параметр
               **kw):
    """
    Параметры совпадают с subprocess.run/Popen.
    На Windows shell=True игнорируется – команда оборачивается вручную.
    """

    # --- специальная обработка BAT файлов ---
    if (sys.platform == "win32" and use_vbs_for_bat and 
        isinstance(cmd, (str, list)) and not capture_output):
        
        # Определяем, это BAT файл или нет
        bat_path = None
        if isinstance(cmd, str) and cmd.strip().lower().endswith('.bat'):
            bat_path = cmd.strip()
        elif isinstance(cmd, list) and len(cmd) >= 3:
            # Проверяем команды вида ['cmd', '/Q', '/C', 'file.bat']
            if (cmd[0].lower() in ('cmd', 'cmd.exe') and 
                len(cmd) > 2 and cmd[-1].lower().endswith('.bat')):
                bat_path = cmd[-1]
        
        if bat_path and os.path.exists(bat_path):
            # Запускаем через VBS для максимального скрытия
            return run_bat_through_vbs(bat_path, cwd)

    # --- подготовка команды / shell ---
    cmd, shell = _prepare_cmd(cmd, shell)

    # --- Windows: прячем окно ---
    if sys.platform == "win32":
        kw.setdefault("creationflags", WIN_FLAGS)
        kw.setdefault("startupinfo", _hidden_startupinfo())
        
        # Если не захватываем вывод, перенаправляем в DEVNULL
        if not capture_output:
            kw.setdefault("stdin",  subprocess.DEVNULL)
            kw.setdefault("stdout", subprocess.DEVNULL)
            kw.setdefault("stderr", subprocess.DEVNULL)
        
        # Устанавливаем переменные окружения для скрытия окон дочерних процессов
        if env is None:
            env = os.environ.copy()
        else:
            env = env.copy()
        
        # Переменные для скрытия консолей
        env.update({
            '__COMPAT_LAYER': 'RunAsInvoker',
            'PYTHONWINDOWMODE': 'hide',
            'PROMPT': '$G',  # Минимальный prompt
            'COMSPEC': get_system_exe("cmd.exe"),  # Полный путь к cmd.exe
        })
        kw['env'] = env

    # --- добавляем cwd если указан ---
    if cwd:
        kw['cwd'] = cwd

    # --- нужно ли run() ---
    need_run = wait or capture_output
    if capture_output:
        need_run = True
        kw["stdout"] = subprocess.PIPE
        kw["stderr"] = subprocess.PIPE

    if need_run:
        kw["text"]     = text if text is not None else True
        kw["encoding"] = encoding or _default_encoding()
        kw["errors"]   = errors
        if timeout is not None:
            kw["timeout"] = timeout

    # --- запуск ---
    try:
        if need_run:
            return subprocess.run(cmd, shell=shell, **kw)
        else:
            return subprocess.Popen(cmd, shell=shell, **kw)
    except Exception as e:
        # Если не удалось с агрессивными флагами, пробуем с базовыми
        if sys.platform == "win32" and "creationflags" in kw:
            kw["creationflags"] = subprocess.CREATE_NO_WINDOW
            if need_run:
                return subprocess.run(cmd, shell=shell, **kw)
            else:
                return subprocess.Popen(cmd, shell=shell, **kw)
        raise