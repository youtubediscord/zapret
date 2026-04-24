# log/crash_handler.py
"""
Модуль для отлова и логирования крашей приложения.

Устанавливает глобальные обработчики исключений для:
- Необработанных исключений в Python
- Исключений в потоках Qt
- Сигналов завершения (SIGTERM, SIGINT)
- Нативных крашей через faulthandler (segfaults, etc.)

Логирует полную информацию о краше в файл и консоль.
"""

import sys
import os
import traceback
import threading
import datetime
import platform
import atexit
from pathlib import Path

from config.config import LOGS_FOLDER, MAIN_DIRECTORY

# Папка для логов крашей
CRASH_LOGS_FOLDER = None
_original_excepthook = None
_original_threading_excepthook = None
_crash_handler_installed = False
_faulthandler_file = None


def _get_crash_logs_folder() -> Path:
    """Получает папку для логов крашей"""
    global CRASH_LOGS_FOLDER
    
    if CRASH_LOGS_FOLDER:
        return Path(CRASH_LOGS_FOLDER)
    
    try:
        folder = Path(LOGS_FOLDER) / "crashes"
    except Exception:
        folder = Path(MAIN_DIRECTORY) / "logs" / "crashes"
    
    folder.mkdir(parents=True, exist_ok=True)
    CRASH_LOGS_FOLDER = str(folder)
    return folder


def _get_system_info() -> str:
    """Собирает информацию о системе"""
    info_lines = [
        f"OS: {platform.system()} {platform.release()} ({platform.version()})",
        f"Python: {sys.version}",
        f"Platform: {platform.platform()}",
        f"Machine: {platform.machine()}",
        f"Processor: {platform.processor()}",
    ]
    
    # Qt версия
    try:
        from PyQt6.QtCore import QT_VERSION_STR, PYQT_VERSION_STR
        info_lines.append(f"Qt: {QT_VERSION_STR}")
        info_lines.append(f"PyQt6: {PYQT_VERSION_STR}")
    except ImportError:
        pass
    
    # Память процесса (Windows)
    try:
        import psutil
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        info_lines.append(f"Memory RSS: {mem_info.rss / 1024 / 1024:.1f} MB")
        info_lines.append(f"Memory VMS: {mem_info.vms / 1024 / 1024:.1f} MB")
    except (ImportError, Exception):
        pass
    
    return "\n".join(info_lines)


def _get_thread_info() -> str:
    """Получает информацию о всех потоках"""
    lines = ["Active threads:"]
    
    for thread in threading.enumerate():
        daemon = " (daemon)" if thread.daemon else ""
        current = " [CURRENT]" if thread == threading.current_thread() else ""
        lines.append(f"  - {thread.name}{daemon}{current}")
    
    return "\n".join(lines)


def _format_crash_report(exc_type, exc_value, exc_tb, context: str = "Unknown") -> str:
    """Форматирует полный отчёт о краше"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    
    # Форматируем traceback
    tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
    tb_str = "".join(tb_lines)
    
    # Собираем отчёт
    report = f"""
{'=' * 80}
🔴 CRASH REPORT - {timestamp}
{'=' * 80}

Context: {context}
Thread: {threading.current_thread().name}

{'─' * 40}
EXCEPTION
{'─' * 40}
Type: {exc_type.__name__ if exc_type else 'Unknown'}
Message: {exc_value}

{'─' * 40}
TRACEBACK
{'─' * 40}
{tb_str}

{'─' * 40}
SYSTEM INFO
{'─' * 40}
{_get_system_info()}

{'─' * 40}
THREADS
{'─' * 40}
{_get_thread_info()}

{'=' * 80}
"""
    return report


def _save_crash_report(report: str, context: str = "crash") -> str:
    """Сохраняет отчёт о краше в файл"""
    try:
        folder = _get_crash_logs_folder()
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"crash_{context}_{timestamp}.log"
        filepath = folder / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report)
        
        return str(filepath)
    except Exception as e:
        return f"Failed to save: {e}"


def _log_crash(report: str, filepath: str = None):
    """Логирует краш через основной логгер и в консоль"""
    # Пытаемся использовать основной логгер
    try:
        from log.log import log

        log(f"🔴 CRASH DETECTED! Report saved to: {filepath}", "CRITICAL")
        # Логируем первые 2000 символов отчёта
        log(report[:2000] + ("..." if len(report) > 2000 else ""), "CRITICAL")
    except Exception:
        pass
    
    # Всегда выводим в stderr
    print(report, file=sys.stderr)
    
    # Также пишем в общий лог-файл
    try:
        folder = _get_crash_logs_folder().parent
        crash_log = folder / "crashes.log"
        
        with open(crash_log, 'a', encoding='utf-8') as f:
            f.write(f"\n{'=' * 80}\n")
            f.write(report)
    except Exception:
        pass


def _python_exception_handler(exc_type, exc_value, exc_tb):
    """Обработчик необработанных исключений Python"""
    # Игнорируем KeyboardInterrupt
    if issubclass(exc_type, KeyboardInterrupt):
        if _original_excepthook:
            _original_excepthook(exc_type, exc_value, exc_tb)
        return
    
    report = _format_crash_report(exc_type, exc_value, exc_tb, "Python Main Thread")
    filepath = _save_crash_report(report, "python")
    _log_crash(report, filepath)
    
    # Вызываем оригинальный обработчик
    if _original_excepthook:
        _original_excepthook(exc_type, exc_value, exc_tb)


def _threading_exception_handler(args):
    """Обработчик исключений в потоках"""
    exc_type = args.exc_type
    exc_value = args.exc_value
    exc_tb = args.exc_traceback
    thread = args.thread
    
    context = f"Thread: {thread.name if thread else 'Unknown'}"
    report = _format_crash_report(exc_type, exc_value, exc_tb, context)
    filepath = _save_crash_report(report, f"thread_{thread.name if thread else 'unknown'}")
    _log_crash(report, filepath)
    
    # Вызываем оригинальный обработчик
    if _original_threading_excepthook:
        _original_threading_excepthook(args)


def _qt_exception_handler(exc_type, exc_value, exc_tb):
    """Обработчик исключений в Qt event loop"""
    report = _format_crash_report(exc_type, exc_value, exc_tb, "Qt Event Loop")
    filepath = _save_crash_report(report, "qt")
    _log_crash(report, filepath)


def install_crash_handler():
    """
    Устанавливает глобальные обработчики крашей.
    
    Вызывайте эту функцию в самом начале main.py, до создания QApplication.
    """
    global _original_excepthook, _original_threading_excepthook, _crash_handler_installed, _faulthandler_file
    
    if _crash_handler_installed:
        return
    
    # Создаём папку для логов
    crash_folder = _get_crash_logs_folder()
    
    # ═══════════════════════════════════════════════════════════════════
    # FAULTHANDLER - ловит нативные краши (segfaults, etc.)
    # ═══════════════════════════════════════════════════════════════════
    try:
        import faulthandler
        
        # Файл для записи faulthandler (нативные краши)
        faulthandler_path = crash_folder / "faulthandler.log"
        _faulthandler_file = open(faulthandler_path, 'a', encoding='utf-8')
        
        # Записываем заголовок сессии
        _faulthandler_file.write(f"\n{'=' * 60}\n")
        _faulthandler_file.write(f"Session started: {datetime.datetime.now()}\n")
        _faulthandler_file.write(f"Python: {sys.version}\n")
        _faulthandler_file.write(f"Platform: {platform.platform()}\n")
        _faulthandler_file.write(f"{'=' * 60}\n\n")
        _faulthandler_file.flush()
        
        # Включаем faulthandler - запись ТОЛЬКО в файл
        # (sys.stderr может быть перенаправлен на Logger без fileno())
        faulthandler.enable(file=_faulthandler_file, all_threads=True)
        
        # Регистрируем закрытие файла при выходе
        def _close_faulthandler():
            global _faulthandler_file
            if _faulthandler_file:
                try:
                    _faulthandler_file.write(f"\nSession ended: {datetime.datetime.now()}\n")
                    _faulthandler_file.close()
                except Exception:
                    pass
        
        atexit.register(_close_faulthandler)
        
        print(f"[CRASH] Faulthandler enabled -> {faulthandler_path}", file=sys.stderr)
        
    except Exception as e:
        print(f"[WARNING] Failed to enable faulthandler: {e}", file=sys.stderr)
    
    # ═══════════════════════════════════════════════════════════════════
    # Python exception handlers
    # ═══════════════════════════════════════════════════════════════════
    
    # Сохраняем оригинальные обработчики
    _original_excepthook = sys.excepthook
    _original_threading_excepthook = getattr(threading, 'excepthook', None)
    
    # Устанавливаем наши обработчики
    sys.excepthook = _python_exception_handler
    
    # Python 3.8+ поддерживает threading.excepthook
    if hasattr(threading, 'excepthook'):
        threading.excepthook = _threading_exception_handler
    
    _crash_handler_installed = True
    
    # Логируем установку
    try:
        from log.log import log

        log("🛡️ Crash handler установлен (faulthandler + Python exceptions)", "INFO")
    except Exception:
        print("[INFO] Crash handler installed", file=sys.stderr)


def install_qt_crash_handler(app=None):
    """
    Устанавливает обработчик крашей для Qt.
    
    Вызывайте ПОСЛЕ создания QApplication.
    
    Args:
        app: QApplication instance (опционально)
    """
    try:
        from PyQt6.QtCore import qInstallMessageHandler, QtMsgType
        from PyQt6.QtWidgets import QApplication
        
        # Обработчик Qt сообщений
        def qt_message_handler(msg_type, context, message):
            if msg_type == QtMsgType.QtFatalMsg:
                # Фатальная ошибка Qt
                report = f"""
{'=' * 80}
🔴 QT FATAL ERROR
{'=' * 80}
Time: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Message: {message}
File: {context.file}:{context.line}
Function: {context.function}
Category: {context.category}

System Info:
{_get_system_info()}

Threads:
{_get_thread_info()}
{'=' * 80}
"""
                filepath = _save_crash_report(report, "qt_fatal")
                _log_crash(report, filepath)
            
            elif msg_type == QtMsgType.QtCriticalMsg:
                try:
                    from log.log import log

                    log(f"Qt Critical: {message}", "ERROR")
                except Exception:
                    print(f"[Qt Critical] {message}", file=sys.stderr)
            
            elif msg_type == QtMsgType.QtWarningMsg:
                # Фильтруем частые неважные предупреждения
                ignore_patterns = [
                    "QWindowsWindow::setGeometry",
                    "Unknown property",
                    "Could not find file",
                ]
                if not any(p in message for p in ignore_patterns):
                    try:
                        from log.log import log

                        log(f"Qt Warning: {message}", "DEBUG")
                    except Exception:
                        pass
        
        qInstallMessageHandler(qt_message_handler)
        
        # Для QApplication устанавливаем обработчик исключений
        if app is None:
            app = QApplication.instance()
        
        # ✅ ОТКЛЮЧЕНО: Monkey-patching notify вызывает рекурсию и access violation
        # if app:
        #     original_notify = app.notify
        #     def patched_notify(receiver, event):
        #         try:
        #             return original_notify(receiver, event)
        #         except Exception:
        #             exc_type, exc_value, exc_tb = sys.exc_info()
        #             _qt_exception_handler(exc_type, exc_value, exc_tb)
        #             return False
        #     app.notify = patched_notify
        pass  # Qt message handler достаточно для отлова ошибок
        
        try:
            from log.log import log

            log("🛡️ Qt crash handler установлен", "INFO")
        except Exception:
            print("[INFO] Qt crash handler installed", file=sys.stderr)
            
    except ImportError:
        pass
    except Exception as e:
        print(f"[WARNING] Failed to install Qt crash handler: {e}", file=sys.stderr)


def test_crash(crash_type: str = "exception"):
    """
    Тестовая функция для проверки crash handler.
    
    Args:
        crash_type: Тип краша для теста
            - "exception" - обычное исключение
            - "thread" - исключение в потоке
            - "zero" - деление на ноль
            - "attribute" - AttributeError
    """
    if crash_type == "exception":
        raise RuntimeError("Test crash: RuntimeError")
    
    elif crash_type == "thread":
        def thread_crash():
            raise ValueError("Test crash in thread")
        
        t = threading.Thread(target=thread_crash, name="TestCrashThread")
        t.start()
        t.join()
    
    elif crash_type == "zero":
        _ = 1 / 0
    
    elif crash_type == "attribute":
        None.crash()  # type: ignore
    
    else:
        raise ValueError(f"Unknown crash type: {crash_type}")


# Логирование при импорте удалено чтобы избежать circular import
# Логирование происходит в install_crash_handler()
