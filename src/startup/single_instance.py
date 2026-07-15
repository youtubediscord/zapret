# single_instance.py
#
# Single-instance подсистема: именованный мьютекс определяет повторный запуск,
# именованное auto-reset событие доставляет команду «показать окно» уже
# запущенному экземпляру. Событие создаётся сразу после захвата мьютекса —
# до инициализации Qt, поэтому сигнал второго экземпляра не теряется, даже
# если первый ещё грузится (auto-reset событие остаётся сигнальным, пока его
# не потребит ожидание).

from __future__ import annotations

import threading
from typing import Callable

ERROR_ALREADY_EXISTS = 183
EVENT_MODIFY_STATE = 0x0002
WAIT_OBJECT_0 = 0
_INFINITE = 0xFFFFFFFF

SHOW_EVENT_NAME = "ZapretGUI_ShowWindowEvent"

_show_event_handle: int | None = None


def _kernel32():
    import ctypes

    return ctypes.windll.kernel32


def create_mutex(name: str):
    """
    Пытаемся создать именованный mutex.
    Возвращает (handle, already_running: bool)
    """
    kernel32 = _kernel32()
    kernel32.SetLastError(0)
    handle = kernel32.CreateMutexW(None, False, name)
    last_error = kernel32.GetLastError()
    already_running = last_error == ERROR_ALREADY_EXISTS

    if not handle:
        return None, False

    return handle, already_running


def release_mutex(handle):
    if handle:
        kernel32 = _kernel32()
        kernel32.ReleaseMutex(handle)
        kernel32.CloseHandle(handle)


def create_show_event(name: str = SHOW_EVENT_NAME) -> int | None:
    """Создаёт auto-reset событие «показать окно» для этого экземпляра.

    Хэндл живёт до конца процесса и закрывается ОС при выходе: явный
    CloseHandle при живом WaitForSingleObject в потоке-наблюдателе даёт
    undefined behavior, а поток-наблюдатель — daemon и умирает с процессом.
    """
    global _show_event_handle
    if _show_event_handle:
        return _show_event_handle
    handle = _kernel32().CreateEventW(None, False, False, name)
    _show_event_handle = int(handle) if handle else None
    return _show_event_handle


def signal_show_event(name: str = SHOW_EVENT_NAME) -> bool:
    """Сигналит событие уже запущенного экземпляра.

    False — событие не существует (первый экземпляр — старая версия без
    события) или SetEvent не прошёл.
    """
    kernel32 = _kernel32()
    handle = kernel32.OpenEventW(EVENT_MODIFY_STATE, False, name)
    if not handle:
        return False
    try:
        return bool(kernel32.SetEvent(handle))
    finally:
        kernel32.CloseHandle(handle)


def start_show_event_watcher(
    callback: Callable[[], None],
    *,
    wait_fn: Callable[[], int] | None = None,
) -> threading.Thread | None:
    """Запускает daemon-поток, вызывающий callback() на каждый сигнал события.

    Поток крутится, пока ожидание возвращает WAIT_OBJECT_0; любой другой
    результат завершает цикл. wait_fn — тестовый шов вместо
    WaitForSingleObject.
    """
    if wait_fn is None:
        handle = _show_event_handle
        if not handle:
            return None
        kernel32 = _kernel32()

        def wait_fn() -> int:
            return kernel32.WaitForSingleObject(handle, _INFINITE)

    def _watch() -> None:
        while wait_fn() == WAIT_OBJECT_0:
            callback()

    thread = threading.Thread(target=_watch, daemon=True, name="show-event-watcher")
    thread.start()
    return thread
