# bfe_util.py

from typing import Optional, Tuple
import time
import win32service
import win32serviceutil
import threading
from queue import Queue

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


class AsyncServiceChecker:
    """Асинхронный проверщик состояний служб."""
    def __init__(self):
        self._results = {}
        self._lock = threading.Lock()
        self._queue = Queue()
        self._running = True
        self._worker = threading.Thread(target=self._check_worker, daemon=True)
        self._worker.start()
    
    def _check_worker(self):
        """Фоновый поток для проверки служб."""
        while self._running:
            try:
                # Ждём задачу с таймаутом
                task = self._queue.get(timeout=1)
                if task is None:
                    break
                
                service_name, callback = task
                
                # Выполняем проверку
                try:
                    result = is_service_running(service_name)
                    with self._lock:
                        self._results[service_name] = (time.time(), result)
                    
                    # Обновляем кэш
                    service_cache.set(service_name, result)
                    
                    # Вызываем callback если предоставлен
                    if callback:
                        callback(service_name, result)
                        
                except Exception as e:
                    from log.log import log

                    log(f"Ошибка при асинхронной проверке {service_name}: {e}", "❌ ERROR")
                    
            except:
                # Timeout или другая ошибка - продолжаем работу
                pass
    
    def check_async(self, service_name: str, callback=None):
        """Запустить асинхронную проверку службы."""
        self._queue.put((service_name, callback))
    
    def get_last_result(self, service_name: str) -> Optional[Tuple[float, bool]]:
        """Получить последний результат проверки."""
        with self._lock:
            return self._results.get(service_name)
    
    def stop(self):
        """Остановить фоновый поток."""
        self._running = False
        self._queue.put(None)
        # Ждем завершения потока
        if self._worker.is_alive():
            self._worker.join(timeout=2.0)


# Глобальные экземпляры
service_cache = ServiceCache()
async_checker = AsyncServiceChecker()


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
        # Запускаем фоновую проверку для обновления кэша
        async_checker.check_async("BFE")
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
        
        # 5. Запускаем периодическую фоновую проверку
        if is_running:
            schedule_periodic_check("BFE", interval=300)  # каждые 5 минут

        return is_running, notification
        
    except Exception as e:
        log(f"Ошибка при проверке службы BFE: {e}", "❌ ERROR")
        service_cache.set("BFE", False, ttl=30)  # кэшируем ошибку на 30 секунд
        return False, _build_bfe_notification(
            f"Не удалось проверить службу Base Filtering Engine.\n\nПодробности: {e}"
        )

# Хранилище для периодических проверок
_periodic_checks = {}
_periodic_lock = threading.Lock()


def schedule_periodic_check(service_name: str, interval: int = 300):
    """Запланировать периодическую проверку службы."""
    def periodic_check():
        while True:
            with _periodic_lock:
                if service_name not in _periodic_checks:
                    break
                    
            time.sleep(interval)
            async_checker.check_async(service_name)
    
    with _periodic_lock:
        if service_name not in _periodic_checks:
            thread = threading.Thread(target=periodic_check, daemon=True)
            thread.start()
            _periodic_checks[service_name] = thread


def stop_periodic_check(service_name: str):
    """Остановить периодическую проверку службы."""
    with _periodic_lock:
        _periodic_checks.pop(service_name, None)


# Функция для быстрой предварительной проверки при старте
def preload_service_status(service_name: str = "BFE"):
    """Предзагрузить состояние службы в фоне."""
    async_checker.check_async(service_name)


# Очистка при выходе
def cleanup():
    """Очистить ресурсы при завершении программы."""
    from log.log import log

    try:
        # Останавливаем асинхронный чекер
        log("Останавливаем async_checker...", "DEBUG")
        async_checker.stop()
        
        # Останавливаем все периодические проверки
        with _periodic_lock:
            if _periodic_checks:
                log(f"Останавливаем {len(_periodic_checks)} периодических проверок...", "DEBUG")
                _periodic_checks.clear()
        
        # Даем потокам время завершиться
        time.sleep(0.1)
        log("BFE cleanup завершен", "DEBUG")
    except Exception as e:
        log(f"Ошибка в BFE cleanup: {e}", "DEBUG")


# Регистрируем очистку
import atexit
atexit.register(cleanup)
