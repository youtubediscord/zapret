# bfe_util.py

from typing import Optional
import time, win32service, ctypes, win32serviceutil
from PyQt6.QtWidgets import QWidget
SERVICE_RUNNING = win32service.SERVICE_RUNNING
ERROR_SERVICE_DOES_NOT_EXIST = 1060

def _native_msg(title: str, text: str, icon: int = 0x40):
    # icon: 0x40 = MB_ICONINFORMATION, 0x10 = MB_ICONERROR
    ctypes.windll.user32.MessageBoxW(None, text, title, icon)

def is_service_running(name: str) -> bool:
    scm = win32service.OpenSCManager(None, None,
                                     win32service.SC_MANAGER_CONNECT)
    try:
        try:
            svc = win32service.OpenService(scm, name,
                                           win32service.SERVICE_QUERY_STATUS)
        except win32service.error as e:
            # Если службы нет – просто возвращаем False
            if e.winerror == ERROR_SERVICE_DOES_NOT_EXIST:
                return False
            raise                       # остальные ошибки пробрасываем
        try:
            status = win32service.QueryServiceStatus(svc)[1]
            return status == SERVICE_RUNNING
        finally:
            win32service.CloseServiceHandle(svc)
    finally:
        win32service.CloseServiceHandle(scm)
        


def ensure_bfe_running(parent: Optional["QWidget"] = None,
                       show_ui: bool = True) -> bool:
    if is_service_running("BFE"):
        return True                      # уже запущена

    try:
        # Делаем автозапуск
        win32serviceutil.ChangeServiceConfig(None, "BFE", startType=win32service.SERVICE_AUTO_START)
        # Пытаемся запустить
        win32serviceutil.StartService("BFE")
    except win32service.error as e:
        # Не хватило прав или другая ошибка
        if show_ui:
            _native_msg("Не удалось запустить BFE",
                        f"Ошибка Windows: {e.winerror}\n"
                        "Попробуйте запустить службу вручную:\n    sc start BFE",
                        icon=0x10)
        return False

    # Ждём, пока ОС действительно запустит службу
    for _ in range(10):                  # ~10 секунд
        if is_service_running("BFE"):
            if show_ui:
                _native_msg("BFE запущена",
                            "Служба Base Filtering Engine была успешно запущена.")
            return True
        time.sleep(1)

    # Не дождались
    if show_ui:
        _native_msg("Не удалось запустить BFE",
                    "Операционная система так и не запустила службу BFE.\n"
                    "Попробуйте команду:\n    sc start BFE",
                    icon=0x10)
    return False
