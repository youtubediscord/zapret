# bfe_util.py

from typing import Optional
import time
import win32service
import win32serviceutil
import threading

from app_notifications import advisory_notification

SERVICE_RUNNING = win32service.SERVICE_RUNNING
ERROR_SERVICE_DOES_NOT_EXIST = 1060

def is_service_running(name: str) -> bool:
    """Быстрая проверка состояния службы через Win32 API."""
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


class ServiceCache:
    """Кэш для хранения состояний служб."""
    def __init__(self):
        self._cache = {}
        self._lock = threading.Lock()
        self._default_ttl = 300  # 5 минут по умолчанию
    
    def get(self, service_name: str) -> Optional[bool]:
        """Получить статус из кэша, если он ещё актуален."""
        with self._lock:
            if service_name in self._cache:
                timestamp, status, ttl = self._cache[service_name]
                if time.time() - timestamp < ttl:
                    return status
        return None
    
    def set(self, service_name: str, status: bool, ttl: Optional[int] = None):
        """Обновить статус в кэше."""
        if ttl is None:
            # Если служба работает, кэшируем на дольше
            ttl = 600 if status else 60
        
        with self._lock:
            self._cache[service_name] = (time.time(), status, ttl)
    
    def invalidate(self, service_name: str):
        """Инвалидировать кэш для службы."""
        with self._lock:
            self._cache.pop(service_name, None)


# Глобальные экземпляры
service_cache = ServiceCache()


def _check_service_once_async(service_name: str, callback=None) -> None:
    """Запускает одну фоновую проверку службы без постоянного worker-потока."""
    def _worker() -> None:
        try:
            result = is_service_running(service_name)
            service_cache.set(service_name, result)
            if callback:
                callback(service_name, result)
        except Exception as e:
            from log.log import log

            log(f"Ошибка при фоновой проверке {service_name}: {e}", "❌ ERROR")

    thread = threading.Thread(
        target=_worker,
        daemon=True,
        name=f"ServiceCheck:{service_name}",
    )
    thread.start()


def start_service(service_name: str, timeout: int = 10) -> bool:
    """Запустить службу Windows."""
    try:
        win32serviceutil.StartService(service_name)
        
        # Ждём запуска
        start_time = time.time()
        while time.time() - start_time < timeout:
            if is_service_running(service_name):
                return True
            time.sleep(0.5)
        
        return False
        
    except Exception as e:
        # Если служба уже запущена
        if "уже запущена" in str(e) or "already running" in str(e).lower():
            return True
        return False


def ensure_bfe_running() -> tuple[bool, dict | None]:
    """
    Проверяет и запускает службу BFE с асинхронной оптимизацией.

    Возвращает:
    - (is_running, notification)
    """
    notification: dict | None = None

    def _build_bfe_notification(message: str) -> dict:
        return advisory_notification(
            level="warning",
            title="Проблема со службой BFE",
            content=message,
            source="startup.bfe",
            queue="startup",
            duration=16000,
            dedupe_key="startup.bfe",
        )
    from log.log import log

    
    # 1. Сначала проверяем кэш службы
    cached_status = service_cache.get("BFE")
    if cached_status is not None:
        # Обновляем кэш одноразовой фоновой проверкой.
        _check_service_once_async("BFE")
        return cached_status, None
    
    log("Выполняется проверка службы Base Filtering Engine (BFE)", "🧹 bfe_util")
    
    try:
        # 3. Выполняем быструю проверку через Win32 API
        is_running = is_service_running("BFE")
        
        if not is_running:
            log("Служба BFE остановлена, пытаемся запустить", "⚠ WARNING")

            # Пытаемся запустить службу
            is_running = start_service("BFE", timeout=5)

            if not is_running:
                log("Не удалось запустить службу BFE", "❌ ERROR")
                notification = _build_bfe_notification(
                    "Не удалось запустить службу Base Filtering Engine.\n"
                    "Это не блокирует запуск программы, но сетевые компоненты Windows могут работать нестабильно."
                )
        
        # 4. Сохраняем результат в живой service-кэш
        service_cache.set("BFE", is_running)
        
        return is_running, notification
        
    except Exception as e:
        log(f"Ошибка при проверке службы BFE: {e}", "❌ ERROR")
        service_cache.set("BFE", False, ttl=30)  # кэшируем ошибку на 30 секунд
        return False, _build_bfe_notification(
            f"Не удалось проверить службу Base Filtering Engine.\n\nПодробности: {e}"
        )

# Функция для быстрой предварительной проверки при старте
def preload_service_status(service_name: str = "BFE"):
    """Предзагрузить состояние службы в фоне."""
    _check_service_once_async(service_name)


# Очистка при выходе
def cleanup():
    """Очистить ресурсы при завершении программы."""
    from log.log import log

    try:
        log("BFE cleanup завершен", "DEBUG")
    except Exception as e:
        log(f"Ошибка в BFE cleanup: {e}", "DEBUG")


# Регистрируем очистку
import atexit
atexit.register(cleanup)
