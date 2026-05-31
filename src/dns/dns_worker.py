# dns/dns_worker.py
"""
Воркеры для DNS операций (упрощенная Win32 версия)
"""
from PyQt6.QtCore import QThread, pyqtSignal, QTimer
from log.log import log
from ui.one_shot_worker_runtime import OneShotWorkerRuntime

import time

# ══════════════════════════════════════════════════════════════════════
#  SafeDNSWorker - фоновый воркер для применения DNS
# ══════════════════════════════════════════════════════════════════════

class SafeDNSWorker(QThread):
    """Безопасный воркер для применения DNS в фоновом режиме"""
    
    status_update = pyqtSignal(str)
    finished_with_result = pyqtSignal(bool)
    
    def __init__(self, skip_on_startup=False, startup_mode=False):
        super().__init__()
        self.skip_on_startup = skip_on_startup
        self.startup_mode = startup_mode
        self._stop_requested = False

    def stop(self):
        self._stop_requested = True

    def is_stop_requested(self) -> bool:
        return self._stop_requested
    
    def run(self):
        """Выполнение DNS операций"""
        try:
            # Задержка при запуске для стабильности
            if self.skip_on_startup:
                log("DNS worker: задержка перед применением", "DEBUG")
                time.sleep(2)
                if self.is_stop_requested():
                    self.status_update.emit("⚪ DNS применение отменено")
                    self.finished_with_result.emit(False)
                    return
            
            from .dns_force import DNSForceManager, ensure_default_force_dns
            
            # Создаем ключ если нет
            ensure_default_force_dns()
            if self.is_stop_requested():
                self.status_update.emit("⚪ DNS применение отменено")
                self.finished_with_result.emit(False)
                return
            
            # Создаем менеджер
            manager = DNSForceManager(status_callback=self.status_update.emit)
            
            # Проверяем, включен ли принудительный DNS
            if not manager.is_force_dns_enabled():
                if self.startup_mode:
                    log("Принудительный DNS отключен в настройках", "INFO")
                self.status_update.emit("⚙️ Принудительный DNS отключен")
                self.finished_with_result.emit(False)
                return
            
            if self.is_stop_requested():
                self.status_update.emit("⚪ DNS применение отменено")
                self.finished_with_result.emit(False)
                return
            
            # Применяем DNS
            self.status_update.emit("⏳ Применение DNS настроек...")
            
            success, total = manager.force_dns_on_all_adapters(
                include_disconnected=False,
                enable_ipv6=True
            )
            
            # Результат
            if success > 0:
                if self.startup_mode:
                    msg = f"✅ DNS применен при запуске: {success}/{total}"
                else:
                    msg = f"✅ DNS применен: {success}/{total} адаптеров"
                self.status_update.emit(msg)
                log(msg, "DNS")
                self.finished_with_result.emit(True)
            else:
                if self.startup_mode:
                    msg = "⚠️ DNS не применен при запуске"
                else:
                    msg = "⚠️ DNS не применен ни к одному адаптеру"
                self.status_update.emit(msg)
                log(msg, "WARNING")
                self.finished_with_result.emit(False)
        
        except Exception as e:
            if self.startup_mode:
                error_msg = f"Ошибка применения DNS при запуске: {e}"
            else:
                error_msg = f"❌ Ошибка DNS worker: {e}"
            log(error_msg, "ERROR")
            self.status_update.emit("❌ Ошибка применения DNS")
            self.finished_with_result.emit(False)

# ══════════════════════════════════════════════════════════════════════
#  DNS при запуске приложения
# ══════════════════════════════════════════════════════════════════════

_dns_disabled_on_startup = False
_startup_runtime = OneShotWorkerRuntime()


def _cleanup_startup_worker():
    _startup_runtime.stop(
        blocking=False,
        log_fn=log,
        warning_prefix="DNS startup worker",
    )
    _startup_runtime.cancel()


def apply_dns_on_startup_async(status_callback=None):
    """
    Применяет DNS настройки при запуске приложения (отложенно).

    Args:
        status_callback: функция для обновления статуса

    Returns:
        bool: True если задача запланирована
    """
    try:
        if _dns_disabled_on_startup:
            log("⚠️ DNS при запуске отключен", "WARNING")
            if status_callback:
                status_callback("DNS при запуске отключен")
            return False

        log("Планирование применения DNS при запуске", "INFO")

        def delayed_apply():
            try:
                if _startup_runtime.is_running():
                    log("DNS startup worker уже запущен", "DEBUG")
                    return

                _startup_runtime.start_qthread_worker(
                    worker_factory=lambda _request_id: SafeDNSWorker(
                        skip_on_startup=False,
                        startup_mode=True,
                    ),
                    bind_worker=(
                        (lambda worker: worker.status_update.connect(status_callback))
                        if status_callback
                        else None
                    ),
                )
                log("DNS worker при старте приложения запущен в фоне", "DEBUG")
            except Exception as e:
                error_msg = f"Ошибка запуска DNS worker при старте: {e}"
                log(error_msg, "ERROR")
                if status_callback:
                    status_callback("❌ Ошибка DNS")

        QTimer.singleShot(3000, delayed_apply)
        return True

    except Exception as e:
        log(f"Ошибка планирования DNS при запуске: {e}", "ERROR")
        if status_callback:
            status_callback("❌ Ошибка планирования DNS")
        return False


def apply_dns_on_startup_sync(status_callback=None):
    """
    Синхронное применение DNS при запуске (блокирующее).

    Args:
        status_callback: функция для обновления статуса

    Returns:
        bool: True если применено успешно
    """
    try:
        if _dns_disabled_on_startup:
            log("DNS при запуске отключен", "WARNING")
            return False

        from .dns_force import DNSForceManager

        manager = DNSForceManager(status_callback=status_callback)

        if not manager.is_force_dns_enabled():
            log("Принудительный DNS отключен", "INFO")
            return False

        success, total = manager.force_dns_on_all_adapters(
            include_disconnected=False,
            enable_ipv6=True
        )

        return success > 0

    except Exception as e:
        log(f"Ошибка синхронного применения DNS: {e}", "ERROR")
        return False


def disable_dns_on_startup():
    """Отключает применение DNS при запуске."""
    global _dns_disabled_on_startup
    _dns_disabled_on_startup = True
    log("DNS при запуске отключен программно", "INFO")


def enable_dns_on_startup():
    """Включает применение DNS при запуске."""
    global _dns_disabled_on_startup
    _dns_disabled_on_startup = False
    log("DNS при запуске включен программно", "INFO")

# ══════════════════════════════════════════════════════════════════════
#  Утилиты
# ══════════════════════════════════════════════════════════════════════

def reset_crash_counter():
    """Сбрасывает счетчик крашей DNS в settings.json."""
    try:
        from settings.store import reset_dns_crash_count

        reset_dns_crash_count()
        log("Счетчик DNS крашей сброшен", "DEBUG")
    except Exception as e:
        log(f"Ошибка сброса счетчика крашей: {e}", "DEBUG")

def disable_dns_if_crashing():
    """
    Аварийное отключение DNS если обнаружены множественные краши
    
    Returns:
        bool: True если DNS был отключен из-за крашей
    """
    try:
        from settings.store import (
            get_dns_crash_count,
            increment_dns_crash_count,
            reset_dns_crash_count,
            set_force_dns_enabled,
        )

        crash_count = int(get_dns_crash_count())

        # Если больше 3 крашей - отключаем DNS
        if crash_count > 3:
            set_force_dns_enabled(False)
            reset_dns_crash_count()
            log("⚠️ DNS автоматически отключен после множественных крашей", "WARNING")
            return True
        
        # Увеличиваем счетчик
        increment_dns_crash_count()
        return False
        
    except Exception as e:
        log(f"Ошибка в disable_dns_if_crashing: {e}", "DEBUG")
        return False
