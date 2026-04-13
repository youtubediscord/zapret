"""
Модуль для проверки здоровья процесса winws.exe после запуска
Мониторит процесс в течение первых секунд и определяет, не упал ли он
"""

import os
import time
import subprocess
from dataclasses import dataclass, field
from typing import Tuple, Optional, List, Dict
from log.log import log
from winws_runtime.runtime.system_ops import (
    aggressive_windivert_cleanup_runtime,
    force_kill_all_winws_processes,
    kill_process_by_pid_runtime,
)

from utils.windows_event_log import get_recent_application_error_messages
from utils.windows_process_probe import iter_process_records_winapi, iter_process_names_winapi, iter_uninstall_display_names

# Список конфликтующих программ
CONFLICTING_PROCESSES = {
    'ProcessHacker.exe': {
        'name': 'Process Hacker',
        'reason': 'Перехватывает системные вызовы и блокирует WinDivert драйвер',
        'solution': 'Закройте Process Hacker перед запуском DPI'
    },
    'procexp.exe': {
        'name': 'Process Explorer',
        'reason': 'Может конфликтовать с WinDivert драйвером',
        'solution': 'Закройте Process Explorer перед запуском DPI'
    },
    'procexp64.exe': {
        'name': 'Process Explorer (64-bit)',
        'reason': 'Может конфликтовать с WinDivert драйвером',
        'solution': 'Закройте Process Explorer перед запуском DPI'
    },
    'GoodbyeDPI.exe': {
        'name': 'GoodbyeDPI',
        'reason': 'Конфликт с другим DPI bypass инструментом',
        'solution': 'Используйте только один DPI bypass инструмент'
    },
    'SpoofDPI.exe': {
        'name': 'SpoofDPI',
        'reason': 'Конфликт с другим DPI bypass инструментом',
        'solution': 'Используйте только один DPI bypass инструмент'
    },
}

_CONFLICTING_PROCESS_BY_NAME = {
    str(exe_name or "").strip().lower(): dict(info or {})
    for exe_name, info in CONFLICTING_PROCESSES.items()
}

_ANTIVIRUS_PRODUCT_MARKERS = (
    ("kaspersky", "Kaspersky"),
    ("каспер", "Kaspersky"),
    ("dr.web", "Dr.Web"),
    ("eset", "ESET"),
    ("norton", "Norton"),
    ("avast", "Avast"),
    ("avg", "AVG"),
    ("bitdefender", "Bitdefender"),
    ("mcafee", "McAfee"),
    ("comodo", "Comodo"),
    ("malwarebytes", "Malwarebytes"),
    ("trend micro", "Trend Micro"),
    ("360 total security", "360 Total Security"),
)

_ANTIVIRUS_PROCESS_MARKERS = {
    "avp.exe": "Kaspersky",
    "ksde.exe": "Kaspersky",
    "klnagent.exe": "Kaspersky",
    "drweb32.exe": "Dr.Web",
    "spideragent.exe": "Dr.Web",
    "egui.exe": "ESET",
    "ekrn.exe": "ESET",
    "nortonsecurity.exe": "Norton",
    "navw32.exe": "Norton",
    "avastui.exe": "Avast",
    "avgui.exe": "AVG",
    "bdagent.exe": "Bitdefender",
    "vsserv.exe": "Bitdefender",
    "uihost.exe": "McAfee",
    "mfemms.exe": "McAfee",
    "cmdagent.exe": "Comodo",
    "mbam.exe": "Malwarebytes",
    "mbamtray.exe": "Malwarebytes",
    "pccntmon.exe": "Trend Micro",
    "360tray.exe": "360 Total Security",
    "360sd.exe": "360 Total Security",
}



def _find_process_pid_by_name_winapi(process_name: str) -> Optional[int]:
    """Ищет PID процесса по имени через единый WinAPI-путь."""
    expected = str(process_name or "").strip().lower()
    if not expected:
        return None

    for pid, name in iter_process_records_winapi():
        normalized = str(name or "").strip().lower()
        if normalized == expected:
            return int(pid)
    return None


def _find_known_antivirus_name() -> Optional[str]:
    """Возвращает имя обнаруженного антивируса по uninstall-реестру и WinAPI-процессам."""
    try:
        for display_name in iter_uninstall_display_names():
            normalized = str(display_name or "").strip().casefold()
            for marker, title in _ANTIVIRUS_PRODUCT_MARKERS:
                if marker in normalized:
                    return title
    except Exception:
        pass

    try:
        for process_name in iter_process_names_winapi():
            normalized = str(process_name or "").strip().casefold()
            match = _ANTIVIRUS_PROCESS_MARKERS.get(normalized)
            if match:
                return match
    except Exception:
        pass

    return None


def _is_windows_defender_active() -> bool:
    """Возвращает True, если Windows Defender выглядит активным по прямым Windows-признакам."""
    try:
        from startup.bfe_util import is_service_running

        if is_service_running("WinDefend"):
            return True
    except Exception:
        pass

    try:
        for process_name in iter_process_names_winapi():
            normalized = str(process_name or "").strip().casefold()
            if normalized in {"msmpeng.exe", "nisserv.exe", "securityhealthservice.exe"}:
                return True
    except Exception:
        pass

    try:
        from altmenu.defender_manager import WindowsDefenderManager

        return not bool(WindowsDefenderManager().is_defender_disabled())
    except Exception:
        return False

def check_process_health(process_name: str = "winws.exe", monitor_duration: int = 5, check_interval: float = 0.5) -> Tuple[bool, Optional[str]]:
    """
    Мониторит процесс в течение указанного времени и проверяет его стабильность
    
    Args:
        process_name: Имя процесса для проверки
        monitor_duration: Длительность мониторинга в секундах
        check_interval: Интервал между проверками в секундах
        
    Returns:
        Tuple[bool, Optional[str]]: (is_healthy, error_message)
            - is_healthy: True если процесс стабилен, False если упал
            - error_message: Описание проблемы если процесс упал, None если всё ок
    """
    log(f"🔍 Начало проверки здоровья процесса {process_name} (мониторинг {monitor_duration}с)", "INFO")
    
    start_time = time.time()
    checks_count = 0
    last_pid = None
    
    while time.time() - start_time < monitor_duration:
        is_running, current_pid = _check_process_running(process_name)
        checks_count += 1
        elapsed = time.time() - start_time
        
        if not is_running:
            error_details = _get_crash_details(process_name)
            error_msg = f"Процесс {process_name} завершился через {elapsed:.1f}с после запуска"
            
            if error_details:
                error_msg += f"\n{error_details}"  # ✅ Убрали "Детали:" для чистоты
            
            log(error_msg, "❌ ERROR")
            log(f"Падение обнаружено на проверке #{checks_count}/{int(monitor_duration/check_interval)}", "DEBUG")
            
            # ✅ НОВОЕ: Дополнительная диагностика
            common_causes = check_common_crash_causes(process_name)
            if common_causes:
                log(f"💡 Возможные причины падения:\n{common_causes}", "INFO")
            
            return False, error_msg
        
        # Проверяем, не изменился ли PID (рестарт процесса)
        if last_pid is not None and current_pid != last_pid:
            warning_msg = f"Процесс {process_name} был перезапущен (PID: {last_pid} → {current_pid})"
            log(warning_msg, "⚠ WARNING")
            # Сбрасываем таймер при рестарте
            start_time = time.time()
        
        last_pid = current_pid
        
        # Логируем прогресс каждую секунду
        if checks_count % int(1.0 / check_interval) == 0:
            log(f"Проверка здоровья: {elapsed:.1f}с, PID: {current_pid}, проверок: {checks_count}", "DEBUG")
        
        time.sleep(check_interval)
    
    log(f"✅ Проверка здоровья завершена: процесс стабилен (выполнено {checks_count} проверок, PID: {last_pid})", "SUCCESS")
    return True, None

def _check_process_running(process_name: str) -> Tuple[bool, Optional[int]]:
    """
    Проверяет, запущен ли процесс и возвращает его PID
    
    Returns:
        Tuple[bool, Optional[int]]: (is_running, pid)
    """
    try:
        pid = _find_process_pid_by_name_winapi(process_name)
        if pid is None:
            return False, None
        return True, pid
    except Exception as e:
        log(f"Ошибка WinAPI-проверки процесса {process_name}: {e}", "DEBUG")
    return False, None

def _get_crash_details(process_name: str) -> Optional[str]:
    """
    Пытается получить детали о падении процесса из журнала событий Windows
    
    Returns:
        Optional[str]: Описание ошибки или None
    """
    try:
        messages = get_recent_application_error_messages(
            process_name=process_name,
            minutes_back=1,
            max_events=1,
        )
    except Exception as e:
        log(f"Ошибка получения деталей падения из Event Log: {e}", "DEBUG")
        messages = []

    if messages:
        output = str(messages[0] or "").strip()
        if "Exception code:" in output or "код исключения:" in output.lower():
            lines = output.split('\n')
            for line in lines:
                if "exception code" in line.lower() or "код исключения" in line.lower():
                    return line.strip()

        first_line = output.split('\n')[0][:200]
        return first_line

    return None

def get_last_crash_info(process_name: str = "winws.exe", minutes_back: int = 5) -> Optional[str]:
    """
    Получает информацию о последних падениях процесса из журнала событий
    
    Args:
        process_name: Имя процесса
        minutes_back: Сколько минут назад искать
        
    Returns:
        Optional[str]: Информация о падениях или None
    """
    try:
        messages = get_recent_application_error_messages(
            process_name=process_name,
            minutes_back=minutes_back,
            max_events=5,
        )
    except Exception as e:
        log(f"Ошибка получения истории падений из Event Log: {e}", "DEBUG")
        messages = []

    if not messages:
        return None

    lines = []
    for message in messages:
        first_line = str(message or "").strip().splitlines()[0][:240]
        if first_line:
            lines.append(first_line)
    return "\n".join(lines) if lines else None

def check_conflicting_processes() -> List[Dict[str, str]]:
    """
    Проверяет наличие конфликтующих процессов
    
    Returns:
        List[Dict]: Список найденных конфликтующих процессов с информацией
    """
    found_conflicts = []
    try:
        for pid, proc_name in iter_process_records_winapi():
            normalized = str(proc_name or "").strip().lower()
            info = _CONFLICTING_PROCESS_BY_NAME.get(normalized)
            if not info:
                continue

            found_conflicts.append({
                'exe': normalized,
                'name': info.get('name', normalized),
                'reason': info.get('reason', ''),
                'solution': info.get('solution', ''),
                'pid': int(pid),
            })
            log(
                f"⚠ Обнаружен конфликтующий процесс: {info.get('name', normalized)} ({normalized}, PID: {pid})",
                "WARNING",
            )
    except Exception as e:
        log(f"Ошибка WinAPI-проверки конфликтующих процессов: {e}", "DEBUG")

    return found_conflicts

def check_common_crash_causes(process_name: str = "winws.exe") -> Optional[str]:
    """
    Проверяет типичные причины падения winws.exe
    
    Returns:
        Optional[str]: Описание возможной причины или None
    """
    suggestions = []
    
    # ✅ ПРОВЕРКА 0: Конфликтующие процессы (ПЕРВЫМ ДЕЛОМ!)
    conflicting = check_conflicting_processes()
    if conflicting:
        suggestions.append("🔴 ОБНАРУЖЕНЫ КОНФЛИКТУЮЩИЕ ПРОГРАММЫ:")
        for conflict in conflicting:
            pid_info = f" (PID: {conflict['pid']})" if conflict.get('pid') else ""
            suggestions.append(f"   • {conflict['name']} ({conflict['exe']}{pid_info})")
            suggestions.append(f"     Причина: {conflict['reason']}")
            suggestions.append(f"     Решение: {conflict['solution']}")
        suggestions.append("")
    
    # ✅ ПРОВЕРКА 1: Права администратора
    try:
        import ctypes
        if not ctypes.windll.shell32.IsUserAnAdmin():
            suggestions.append("  ⚠ Программа запущена БЕЗ прав администратора")
            suggestions.append("     Запустите программу от имени администратора")
    except:
        pass
    
    # ✅ ПРОВЕРКА 2: WinDivert драйвер
    try:
        result = subprocess.run(
            ['sc', 'query', 'WinDivert'],
            capture_output=True,
            text=True,
            creationflags=0x08000000,
            timeout=5
        )
        
        if "не удается найти" in result.stderr.lower() or "cannot find" in result.stderr.lower():
            suggestions.append("  Драйвер WinDivert не установлен")
            suggestions.append("     Переустановите программу")
        elif "STOPPED" in result.stdout:
            suggestions.append("  Драйвер WinDivert остановлен")
            suggestions.append("     Перезагрузите компьютер или переустановите программу")
    except:
        pass
    
    # ✅ ПРОВЕРКА 3: Целостность файлов WinDivert
    try:
        from config.config import WINDIVERT_FOLDER

        import os
        
        required_files = {
            'WinDivert.dll': 'Основная библиотека',
            'Monkey64.sys': 'Основная библиотека',
            'WinDivert64.sys': 'Драйвер для 64-bit систем',
            'WinDivert32.sys': 'Драйвер для 32-bit систем'
        }
        missing_files = []
        
        for file, description in required_files.items():
            file_path = os.path.join(WINDIVERT_FOLDER, file)
            if not os.path.exists(file_path):
                missing_files.append(f"{file} ({description})")
        
        if missing_files:
            suggestions.append("  Отсутствуют критические файлы WinDivert:")
            for file in missing_files:
                suggestions.append(f"     - {file}")
            suggestions.append("     Переустановите программу полностью")
    except:
        pass
    
    # ✅ ПРОВЕРКА 4: Антивирус
    try:
        active_av = _detect_active_antivirus()
        if active_av:
            suggestions.append(f"  Обнаружен антивирус: {active_av}")
            suggestions.append("     Добавьте winws.exe и WinDivert в исключения антивируса")
    except Exception:
        pass
    
    if suggestions:
        return "\n".join(suggestions)
    
    return None

def try_kill_conflicting_processes(auto_kill: bool = False) -> bool:
    """
    Пытается закрыть конфликтующие процессы
    
    Args:
        auto_kill: Если True, закрывает процессы автоматически. Если False, только проверяет
        
    Returns:
        bool: True если конфликтующих процессов не обнаружено или они успешно закрыты
    """
    conflicting = check_conflicting_processes()
    
    if not conflicting:
        return True
    
    if not auto_kill:
        log(f"Обнаружено конфликтующих процессов: {len(conflicting)}", "WARNING")
        return False
    
    log("Попытка закрыть конфликтующие процессы...", "INFO")

    success_count = 0
    for conflict in conflicting:
        try:
            pid = int(conflict.get('pid') or 0)
            if pid <= 0:
                log(f"❌ У конфликтующего процесса {conflict['name']} нет корректного PID", "ERROR")
                continue

            if kill_process_by_pid_runtime(pid, wait_timeout_ms=5000):
                log(f"✅ Процесс {conflict['name']} (PID {pid}) успешно закрыт через WinAPI", "SUCCESS")
                success_count += 1
            else:
                log(f"❌ Не удалось закрыть {conflict['name']} (PID {pid}) через WinAPI", "ERROR")
        except Exception as e:
            log(f"Ошибка при закрытии {conflict['name']}: {e}", "ERROR")
    
    if success_count == len(conflicting):
        log(f"Все конфликтующие процессы ({success_count}) успешно закрыты", "SUCCESS")
        time.sleep(1)  # Даем системе время на очистку
        return True
    else:
        log(f"Закрыто {success_count}/{len(conflicting)} конфликтующих процессов", "WARNING")
        return False

def get_conflicting_processes_report() -> str:
    """
    Генерирует отчет о конфликтующих процессах для отображения в UI
    
    Returns:
        str: Отформатированный отчет
    """
    conflicting = check_conflicting_processes()
    
    if not conflicting:
        return ""
    
    lines = ["⚠️ ОБНАРУЖЕНЫ КОНФЛИКТУЮЩИЕ ПРОГРАММЫ:", ""]
    
    for i, conflict in enumerate(conflicting, 1):
        pid_info = f" (PID: {conflict['pid']})" if conflict.get('pid') else ""
        lines.append(f"{i}. {conflict['name']}{pid_info}")
        lines.append(f"   Файл: {conflict['exe']}")
        lines.append(f"   Проблема: {conflict['reason']}")
        lines.append(f"   Решение: {conflict['solution']}")
        lines.append("")
    
    lines.append("Рекомендуется закрыть эти программы перед запуском DPI.")
    
    return "\n".join(lines)

# ✅ НОВАЯ ФУНКЦИЯ: Проверка длины командной строки
def validate_command_line_length(args: str) -> Tuple[bool, Optional[str]]:
    """
    Проверяет, не превышает ли командная строка лимиты Windows
    
    Args:
        args: Строка с аргументами командной строки
        
    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    MAX_CMD_LINE = 8191  # Лимит Windows для командной строки
    MAX_SAFE = 7000  # Безопасный лимит с запасом
    
    length = len(args)
    
    if length > MAX_CMD_LINE:
        return False, f"Командная строка слишком длинная ({length} символов, лимит {MAX_CMD_LINE})"
    
    if length > MAX_SAFE:
        log(f"⚠ Командная строка близка к лимиту: {length}/{MAX_CMD_LINE} символов", "WARNING")
    
    return True, None

# ✅ НОВАЯ ФУНКЦИЯ: Подсчет аргументов по категориям
def analyze_strategy_complexity(args: str) -> Dict[str, any]:
    """
    Анализирует сложность стратегии
    
    Args:
        args: Строка с аргументами
        
    Returns:
        Dict с метриками сложности
    """
    analysis = {
        'total_length': len(args),
        'args_count': len(args.split()),
        'filter_count': args.count('--filter-'),
        'hostlist_count': args.count('.txt'),
        'ipset_count': args.count('ipset'),
        'complexity_score': 0
    }
    
    # Вычисляем балл сложности
    analysis['complexity_score'] = (
        analysis['args_count'] * 1 +
        analysis['filter_count'] * 5 +
        analysis['hostlist_count'] * 3 +
        analysis['ipset_count'] * 2
    )

    return analysis


def diagnose_startup_error(error: Exception, exe_path: str = None) -> str:
    """
    Диагностирует ошибку запуска и возвращает понятное сообщение с решением.

    Args:
        error: Исключение которое произошло
        exe_path: Путь к exe файлу (опционально)

    Returns:
        str: Понятное сообщение об ошибке с рекомендациями
    """
    import ctypes
    import os

    error_str = str(error)
    error_code = getattr(error, 'winerror', None) or getattr(error, 'errno', None)

    # Определяем тип ошибки
    diagnostics = []

    # ========== WinError 5: Отказано в доступе ==========
    if error_code == 5 or "WinError 5" in error_str or "отказано в доступе" in error_str.lower() or "access is denied" in error_str.lower():
        diagnostics.append("🚫 ОТКАЗАНО В ДОСТУПЕ")
        diagnostics.append("")

        # Проверка 1: Права администратора
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
            if not is_admin:
                diagnostics.append("❌ Причина: Программа запущена БЕЗ прав администратора")
                diagnostics.append("   Решение: Закройте программу и запустите от имени администратора")
                return "\n".join(diagnostics)
        except:
            pass

        # Проверка 2: Антивирус блокирует
        av_blocking = _check_antivirus_blocking(exe_path)
        if av_blocking:
            diagnostics.append(f"❌ Причина: {av_blocking}")
            diagnostics.append("   Решение: Добавьте папку программы в исключения антивируса")
            return "\n".join(diagnostics)

        # Проверка 3: Файл заблокирован другим процессом
        if exe_path and os.path.exists(exe_path):
            locked_by = _check_file_locked(exe_path)
            if locked_by:
                diagnostics.append(f"❌ Причина: Файл заблокирован процессом: {locked_by}")
                diagnostics.append("   Решение: Закройте указанный процесс или перезагрузите компьютер")
                return "\n".join(diagnostics)

        # Проверка 4: Предыдущий winws ещё работает
        running_winws = _check_winws_already_running()
        if running_winws:
            diagnostics.append(f"❌ Причина: Уже запущен процесс winws (PID: {running_winws})")
            diagnostics.append("   Пытаемся автоматически завершить...")

            # Пробуем автоматически завершить
            try:
                if force_kill_all_winws_processes():
                    diagnostics.append("   ✅ Процесс завершён. Попробуйте запустить снова")
                else:
                    diagnostics.append("   ❌ Не удалось завершить процесс")
                    diagnostics.append("   Решение: Перезагрузите компьютер")
            except Exception as kill_err:
                diagnostics.append(f"   ❌ Ошибка завершения: {kill_err}")
                diagnostics.append("   Решение: Перезагрузите компьютер")

            return "\n".join(diagnostics)

        # Не смогли определить точную причину - пробуем агрессивную очистку
        diagnostics.append("❌ Причина не определена, выполняем агрессивную очистку...")

        # Пробуем агрессивную очистку всего
        try:
            aggressive_windivert_cleanup_runtime()

            diagnostics.append("   ✅ Очистка выполнена. Попробуйте запустить снова")
        except Exception as cleanup_err:
            diagnostics.append(f"   ⚠ Ошибка очистки: {cleanup_err}")

        diagnostics.append("")
        diagnostics.append("   Если ошибка повторяется:")
        diagnostics.append("   1. Добавьте папку программы в исключения антивируса")
        diagnostics.append("   2. Перезагрузите компьютер")
        return "\n".join(diagnostics)

    # ========== WinError 2: Файл не найден ==========
    if error_code == 2 or "WinError 2" in error_str or "не удается найти" in error_str.lower() or "cannot find" in error_str.lower():
        diagnostics.append("📁 ФАЙЛ НЕ НАЙДЕН")
        diagnostics.append("")
        if exe_path:
            diagnostics.append(f"❌ Не найден файл: {exe_path}")
        diagnostics.append("   Решение: Переустановите программу или восстановите файлы")
        return "\n".join(diagnostics)

    # ========== WinError 740: Требуется повышение прав ==========
    if error_code == 740 or "WinError 740" in error_str:
        diagnostics.append("🔐 ТРЕБУЮТСЯ ПРАВА АДМИНИСТРАТОРА")
        diagnostics.append("")
        diagnostics.append("❌ Причина: Операция требует повышенных привилегий")
        diagnostics.append("   Решение: Запустите программу от имени администратора")
        return "\n".join(diagnostics)

    # ========== WinError 1314: Недостаточно привилегий ==========
    if error_code == 1314 or "WinError 1314" in error_str:
        diagnostics.append("🔐 НЕДОСТАТОЧНО ПРИВИЛЕГИЙ")
        diagnostics.append("")
        diagnostics.append("❌ Причина: У текущего пользователя нет необходимых прав")
        diagnostics.append("   Решение: Запустите программу от имени администратора")
        return "\n".join(diagnostics)

    # ========== WinError 1450: Недостаточно ресурсов ==========
    if error_code == 1450 or "WinError 1450" in error_str:
        diagnostics.append("💾 НЕДОСТАТОЧНО СИСТЕМНЫХ РЕСУРСОВ")
        diagnostics.append("")
        diagnostics.append("❌ Причина: Системе не хватает памяти или других ресурсов")
        diagnostics.append("   Решение: Закройте лишние программы и перезагрузите компьютер")
        return "\n".join(diagnostics)

    # ========== PermissionError ==========
    if isinstance(error, PermissionError):
        diagnostics.append("🚫 ОШИБКА ДОСТУПА")
        diagnostics.append("")
        diagnostics.append("❌ Причина: Нет прав на выполнение операции")
        diagnostics.append("   Решения:")
        diagnostics.append("   1. Запустите программу от имени администратора")
        diagnostics.append("   2. Проверьте антивирус на блокировки")
        return "\n".join(diagnostics)

    # ========== FileNotFoundError ==========
    if isinstance(error, FileNotFoundError):
        diagnostics.append("📁 ФАЙЛ ИЛИ ПАПКА НЕ НАЙДЕНЫ")
        diagnostics.append("")
        diagnostics.append(f"❌ {error_str}")
        diagnostics.append("   Решение: Переустановите программу")
        return "\n".join(diagnostics)

    # ========== OSError с кодом ==========
    if isinstance(error, OSError) and error_code:
        diagnostics.append(f"⚠️ СИСТЕМНАЯ ОШИБКА (код {error_code})")
        diagnostics.append("")
        diagnostics.append(f"❌ {error_str}")
        diagnostics.append("   Решение: Перезагрузите компьютер и попробуйте снова")
        return "\n".join(diagnostics)

    # ========== Неизвестная ошибка ==========
    diagnostics.append("⚠️ ОШИБКА ЗАПУСКА")
    diagnostics.append("")
    diagnostics.append(f"❌ {error_str}")
    diagnostics.append("")
    diagnostics.append("   Попробуйте:")
    diagnostics.append("   1. Перезапустить программу от имени администратора")
    diagnostics.append("   2. Проверить антивирус")
    diagnostics.append("   3. Перезагрузить компьютер")

    return "\n".join(diagnostics)


def _check_antivirus_blocking(exe_path: str = None) -> Optional[str]:
    """Проверяет, не блокирует ли антивирус файл"""
    try:
        _ = exe_path
        antivirus_name = _detect_active_antivirus()
        if antivirus_name:
            normalized = str(antivirus_name or "").casefold()
            if "defender" in normalized or "microsoft" in normalized:
                return "Windows Defender может блокировать winws.exe"
            return f"Антивирус ({antivirus_name}) может блокировать winws.exe"
    except Exception:
        pass

    return None


def _check_file_locked(file_path: str) -> Optional[str]:
    """Проверяет, заблокирован ли файл другим процессом"""
    try:
        fd = os.open(file_path, os.O_RDWR | os.O_EXCL)
        os.close(fd)
        return None
    except PermissionError:
        return "неизвестный процесс"
    except Exception:
        return None


def _check_winws_already_running() -> Optional[int]:
    """Проверяет, запущен ли уже winws"""
    try:
        for candidate in ('winws.exe', 'winws2.exe'):
            pid = _find_process_pid_by_name_winapi(candidate)
            if pid is not None:
                return pid
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
#  WinDivert exit-code diagnostics
# ---------------------------------------------------------------------------

@dataclass
class WinDivertDiagnosis:
    """Structured result of WinDivert error diagnosis."""
    cause: str                        # Human-readable cause
    solution: str                     # What the user should do
    auto_fix: Optional[str] = None   # Action ID: "enable_adapters", "enable_bfe", "enable_driver", None
    severity: str = "critical"        # "critical" | "warning"
    exit_code: int = 0                # Original exit code
    win32_error: Optional[int] = None # Mapped Win32 error (may differ from exit_code)


# --- Win32 error code constants ---
_ERROR_ACCESS_DENIED = 5
_ERROR_NOT_ENOUGH_MEMORY = 8
_ERROR_GEN_FAILURE = 31
_ERROR_INVALID_PARAMETER = 87
_ERROR_BAD_PATHNAME = 161
_ERROR_INVALID_IMAGE_HASH = 577
_ERROR_DRIVER_FAILED_PRIOR_UNLOAD = 654
_ERROR_SERVICE_DISABLED = 1058
_ERROR_SERVICE_DOES_NOT_EXIST = 1060
_ERROR_PROCESS_ABORTED = 1067
_ERROR_SERVICE_DEPENDENCY_FAIL = 1068
_ERROR_DRIVER_BLOCKED = 1275

# stderr patterns → Win32 error mapping (for when exit code is truncated)
_STDERR_TO_WIN32: List[Tuple[str, int]] = [
    ("the service cannot be started", _ERROR_SERVICE_DISABLED),
    ("service is disabled", _ERROR_SERVICE_DISABLED),
    ("no enabled devices", _ERROR_SERVICE_DISABLED),
    ("access is denied", _ERROR_ACCESS_DENIED),
    ("access denied", _ERROR_ACCESS_DENIED),
    ("hash for file is not valid", _ERROR_INVALID_IMAGE_HASH),
    ("invalid image hash", _ERROR_INVALID_IMAGE_HASH),
    ("disable secure boot", _ERROR_INVALID_IMAGE_HASH),
    ("driver blocked", _ERROR_DRIVER_BLOCKED),
    ("blocked from loading", _ERROR_DRIVER_BLOCKED),
    ("driver failed prior unload", _ERROR_DRIVER_FAILED_PRIOR_UNLOAD),
    ("bad pathname", _ERROR_BAD_PATHNAME),
    ("service does not exist", _ERROR_SERVICE_DOES_NOT_EXIST),
    ("dependency service", _ERROR_SERVICE_DEPENDENCY_FAIL),
    ("process terminated unexpectedly", _ERROR_PROCESS_ABORTED),
    ("not enough memory", _ERROR_NOT_ENOUGH_MEMORY),
    ("insufficient resources", _ERROR_NOT_ENOUGH_MEMORY),
    ("parameter is incorrect", _ERROR_INVALID_PARAMETER),
    ("a device attached to the system is not functioning", _ERROR_GEN_FAILURE),
]


def diagnose_winws_exit(exit_code: int, stderr: str = "") -> Optional[WinDivertDiagnosis]:
    """Diagnose winws2 exit code + stderr and return structured result.

    The exit code of winws2 equals the raw Win32 GetLastError() value after
    WinDivertOpen() fails.  However, the exit code may be truncated to 8 bits
    in some scenarios (e.g. 1058 → 34).  Therefore stderr text is parsed first
    as the primary signal, and exit_code is used as fallback.

    Returns None if exit_code is 0 (success) or diagnosis is not applicable.
    """
    if exit_code == 0:
        return None

    stderr_lower = (stderr or "").lower()

    # 1. Resolve the real Win32 error from stderr text (more reliable)
    win32_error = exit_code
    for pattern, code in _STDERR_TO_WIN32:
        if pattern in stderr_lower:
            win32_error = code
            break

    # 2. Dispatch to specific handlers
    handler = _EXIT_CODE_HANDLERS.get(win32_error)
    if handler:
        diag = handler(exit_code, stderr)
        diag.exit_code = exit_code
        diag.win32_error = win32_error
        return diag

    # 3. Fallback: generic WinDivert error
    if "windivert" in stderr_lower or "error opening filter" in stderr_lower:
        first_line = ""
        try:
            first_line = stderr.strip().splitlines()[0].strip()[:200]
        except Exception:
            first_line = stderr[:200]
        return WinDivertDiagnosis(
            cause=f"Ошибка WinDivert (код {exit_code})",
            solution=first_line or "Перезагрузите компьютер и попробуйте снова",
            severity="critical",
            exit_code=exit_code,
            win32_error=win32_error,
        )

    return None


# ---------------------------------------------------------------------------
#  Per-error-code handlers
# ---------------------------------------------------------------------------

def _handle_service_disabled(exit_code: int, stderr: str) -> WinDivertDiagnosis:
    """ERROR_SERVICE_DISABLED (1058) — the most common WinDivert error."""
    # Run sub-checks to narrow down the cause
    cause, solution, auto_fix = _probe_service_disabled_cause()
    return WinDivertDiagnosis(
        cause=cause, solution=solution, auto_fix=auto_fix, severity="critical",
    )


def _handle_invalid_image_hash(exit_code: int, stderr: str) -> WinDivertDiagnosis:
    secure_boot = _check_secure_boot()
    if secure_boot:
        return WinDivertDiagnosis(
            cause="Secure Boot блокирует загрузку драйвера WinDivert",
            solution="Отключите Secure Boot в BIOS/UEFI настройках",
            severity="critical",
        )
    return WinDivertDiagnosis(
        cause="Подпись драйвера WinDivert не прошла проверку",
        solution="Отключите Secure Boot или включите тестовый режим: bcdedit /set testsigning on",
        severity="critical",
    )


def _handle_access_denied(exit_code: int, stderr: str) -> WinDivertDiagnosis:
    try:
        import ctypes
        if not ctypes.windll.shell32.IsUserAnAdmin():
            return WinDivertDiagnosis(
                cause="Программа запущена без прав администратора",
                solution="Запустите программу от имени администратора",
                severity="critical",
            )
    except Exception:
        pass
    return WinDivertDiagnosis(
        cause="Отказано в доступе к WinDivert",
        solution="Проверьте антивирус и запустите от имени администратора",
        severity="critical",
    )


def _handle_driver_blocked(exit_code: int, stderr: str) -> WinDivertDiagnosis:
    return WinDivertDiagnosis(
        cause="Политика безопасности Windows блокирует загрузку драйвера",
        solution="Проверьте настройки Device Guard / WDAC или отключите Secure Boot",
        severity="critical",
    )


def _handle_driver_prior_unload(exit_code: int, stderr: str) -> WinDivertDiagnosis:
    return WinDivertDiagnosis(
        cause="Старая версия драйвера WinDivert всё ещё загружена в память",
        solution="Перезагрузите компьютер для выгрузки старого драйвера",
        severity="critical",
    )


def _handle_service_not_exist(exit_code: int, stderr: str) -> WinDivertDiagnosis:
    # Check if WinDivert files exist
    missing = _check_windivert_files()
    if missing:
        return WinDivertDiagnosis(
            cause=f"Отсутствуют файлы WinDivert: {', '.join(missing)}",
            solution="Переустановите программу или восстановите файлы из архива",
            severity="critical",
        )
    return WinDivertDiagnosis(
        cause="Служба WinDivert не найдена в системе",
        solution="Переустановите программу",
        severity="critical",
    )


def _handle_dependency_fail(exit_code: int, stderr: str) -> WinDivertDiagnosis:
    bfe_ok = _check_bfe_service()
    if not bfe_ok:
        return WinDivertDiagnosis(
            cause="Служба Base Filtering Engine (BFE) не запущена",
            solution="Включите BFE: sc config BFE start= auto && net start BFE",
            auto_fix="enable_bfe",
            severity="critical",
        )
    return WinDivertDiagnosis(
        cause="Зависимая служба Windows Filtering Platform не запущена",
        solution="Перезагрузите компьютер",
        severity="critical",
    )


def _handle_not_enough_memory(exit_code: int, stderr: str) -> WinDivertDiagnosis:
    return WinDivertDiagnosis(
        cause="Недостаточно системной памяти для WinDivert",
        solution="Закройте лишние программы и перезагрузите компьютер",
        severity="warning",
    )


def _handle_gen_failure(exit_code: int, stderr: str) -> WinDivertDiagnosis:
    adapters_ok = _check_network_adapters()
    if not adapters_ok:
        return WinDivertDiagnosis(
            cause="Все сетевые адаптеры отключены",
            solution="Включите хотя бы один сетевой адаптер",
            auto_fix="enable_adapters",
            severity="critical",
        )
    return WinDivertDiagnosis(
        cause="Общая ошибка устройства",
        solution="Перезагрузите компьютер и проверьте сетевые адаптеры",
        severity="critical",
    )


def _handle_invalid_parameter(exit_code: int, stderr: str) -> WinDivertDiagnosis:
    import re
    stderr_lower = (stderr or "").lower()

    # Lua desync function not found — lua-init auto-fix didn't help,
    # meaning the .lua file itself is missing from disk.
    m = re.search(r"desync function '([^']+)' does not exist", stderr or "")
    if m:
        func_name = m.group(1)
        return WinDivertDiagnosis(
            cause=f"Lua-функция '{func_name}' не найдена — файл .lua отсутствует на диске",
            solution="Переустановите программу — файлы в папке lua/ повреждены или удалены",
            severity="critical",
        )

    # Lua script syntax/runtime error
    if "lua" in stderr_lower and ("error" in stderr_lower or "syntax" in stderr_lower):
        return WinDivertDiagnosis(
            cause="Ошибка в Lua-скрипте",
            solution="Переустановите программу или проверьте файлы в папке lua/",
            severity="critical",
        )

    return WinDivertDiagnosis(
        cause="Ошибка в параметрах фильтра или Lua-скрипта",
        solution="Проверьте настройки стратегии — возможно повреждён пресет",
        severity="warning",
    )


def _handle_bad_pathname(exit_code: int, stderr: str) -> WinDivertDiagnosis:
    missing = _check_windivert_files()
    cause = "Не найден файл драйвера WinDivert"
    if missing:
        cause += f": {', '.join(missing)}"
    return WinDivertDiagnosis(
        cause=cause,
        solution="Переустановите программу или проверьте антивирус",
        severity="critical",
    )


def _handle_process_aborted(exit_code: int, stderr: str) -> WinDivertDiagnosis:
    return WinDivertDiagnosis(
        cause="Драйвер WinDivert аварийно завершился при запуске",
        solution="Переустановите программу и перезагрузите компьютер",
        severity="critical",
    )


# Handler dispatch table
_EXIT_CODE_HANDLERS = {
    _ERROR_SERVICE_DISABLED: _handle_service_disabled,
    _ERROR_INVALID_IMAGE_HASH: _handle_invalid_image_hash,
    _ERROR_ACCESS_DENIED: _handle_access_denied,
    _ERROR_DRIVER_BLOCKED: _handle_driver_blocked,
    _ERROR_DRIVER_FAILED_PRIOR_UNLOAD: _handle_driver_prior_unload,
    _ERROR_SERVICE_DOES_NOT_EXIST: _handle_service_not_exist,
    _ERROR_SERVICE_DEPENDENCY_FAIL: _handle_dependency_fail,
    _ERROR_NOT_ENOUGH_MEMORY: _handle_not_enough_memory,
    _ERROR_GEN_FAILURE: _handle_gen_failure,
    _ERROR_INVALID_PARAMETER: _handle_invalid_parameter,
    _ERROR_BAD_PATHNAME: _handle_bad_pathname,
    _ERROR_PROCESS_ABORTED: _handle_process_aborted,
}


# ---------------------------------------------------------------------------
#  System probe helpers
# ---------------------------------------------------------------------------

def _probe_service_disabled_cause() -> Tuple[str, str, Optional[str]]:
    """Narrow down why 'service cannot be started' (1058).

    Returns (cause, solution, auto_fix_action).
    """
    # Check 1: WinDivert files missing (AV quarantine)
    missing = _check_windivert_files()
    if missing:
        return (
            f"Файлы WinDivert отсутствуют (возможно удалены антивирусом): {', '.join(missing)}",
            "Добавьте папку программы в исключения антивируса и переустановите",
            None,
        )

    # Check 2: BFE service
    if not _check_bfe_service():
        return (
            "Служба Base Filtering Engine (BFE) отключена — WinDivert зависит от неё",
            "Включите BFE: sc config BFE start= auto && net start BFE",
            "enable_bfe",
        )

    # Check 3: Secure Boot
    if _check_secure_boot():
        return (
            "Secure Boot блокирует загрузку неподписанного драйвера WinDivert",
            "Отключите Secure Boot в BIOS/UEFI",
            None,
        )

    # Check 4: WinDivert service explicitly disabled
    driver_disabled = _check_windivert_driver_disabled()
    if driver_disabled:
        return (
            "Служба WinDivert отключена в системе",
            "Переключите тип запуска: sc config WinDivert start= demand",
            "enable_driver",
        )

    # Check 5: Driver installed but not yet ready after cleanup/restart.
    try:
        from winws_runtime.runtime.system_ops import probe_windivert_state_runtime

        probe = probe_windivert_state_runtime()
        if probe.installed and not probe.ready:
            return (
                "WinDivert ещё не готов после предыдущего запуска или очистки",
                "Подождите пару секунд и попробуйте снова. Если повторяется — перезапустите программу или ПК",
                None,
            )
    except Exception:
        pass

    # Check 6: Antivirus
    av = _detect_active_antivirus()
    if av:
        return (
            f"Антивирус ({av}) может блокировать загрузку драйвера WinDivert",
            "Добавьте папку программы в исключения антивируса",
            None,
        )

    # Check 7: Network adapters. This check must be late because Win32 1058
    # is a generic service-disabled error and otherwise easily turns into a
    # ложный диагноз про адаптеры.
    if not _check_network_adapters():
        return (
            "Не найден ни один активный сетевой адаптер — WinDivert не к чему привязаться",
            "Включите хотя бы один сетевой адаптер в системе и повторите запуск",
            "enable_adapters",
        )

    # Fallback
    return (
        "WinDivert не может запустить службу драйвера",
        "Перезагрузите компьютер. Если не помогает — проверьте Secure Boot и антивирус",
        None,
    )


def _check_network_adapters() -> bool:
    """Return True if at least one network adapter is enabled/up."""
    try:
        from dns.dns_core import get_adapters_info_native

        adapters = get_adapters_info_native()
        for adapter in adapters:
            adapter_type = int(adapter.get("type") or 0)
            if adapter_type == 24:  # MIB_IF_TYPE_LOOPBACK
                continue
            if adapter.get("index") or adapter.get("adapter_name") or adapter.get("name"):
                return True
        return False
    except Exception:
        return True  # assume OK on failure


def _check_windivert_files() -> List[str]:
    """Return list of missing critical WinDivert files."""
    import os
    try:
        from config.config import WINDIVERT_FOLDER

    except ImportError:
        return []

    required = ["WinDivert.dll", "WinDivert64.sys"]
    missing = []
    for f in required:
        if not os.path.exists(os.path.join(WINDIVERT_FOLDER, f)):
            missing.append(f)
    return missing


def _check_bfe_service() -> bool:
    """Return True if Base Filtering Engine service is running."""
    try:
        from startup.bfe_util import is_service_running

        return bool(is_service_running("BFE"))
    except Exception:
        return True  # assume OK


def _check_secure_boot() -> bool:
    """Return True if Secure Boot is ENABLED (via registry)."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\SecureBoot\State",
        )
        val, _ = winreg.QueryValueEx(key, "UEFISecureBootEnabled")
        winreg.CloseKey(key)
        return val == 1
    except Exception:
        return False  # key doesn't exist = Secure Boot not available


def _check_windivert_driver_disabled() -> bool:
    """Return True if WinDivert service start type is DISABLED."""
    try:
        import winreg

        for service_name in ("WinDivert", "windivert", "WinDivert14", "WinDivert64"):
            try:
                with winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    fr"SYSTEM\CurrentControlSet\Services\{service_name}",
                    0,
                    winreg.KEY_READ,
                ) as key:
                    start_value, _ = winreg.QueryValueEx(key, "Start")
                    if int(start_value) == 4:
                        return True
            except FileNotFoundError:
                continue
        return False
    except Exception:
        return False


def _detect_active_antivirus() -> Optional[str]:
    """Return name of active antivirus or None."""
    try:
        antivirus_name = _find_known_antivirus_name()
        if antivirus_name:
            return antivirus_name
        if _is_windows_defender_active():
            return "Windows Defender"
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
#  Auto-fix actions
# ---------------------------------------------------------------------------

def execute_windivert_auto_fix(action: str) -> Tuple[bool, str]:
    """Execute an auto-fix action. Returns (success, message)."""
    if action == "enable_adapters":
        return _fix_enable_adapters()
    elif action == "enable_bfe":
        return _fix_enable_bfe()
    elif action == "enable_driver":
        return _fix_enable_driver()
    return False, f"Неизвестное действие: {action}"


def _fix_enable_adapters() -> Tuple[bool, str]:
    """Try to enable disabled network adapters."""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-NetAdapter -Physical | Where-Object {$_.Status -eq 'Disabled'} | Enable-NetAdapter -Confirm:$false"],
            capture_output=True, text=True, timeout=15,
            creationflags=0x08000000,
        )
        if result.returncode == 0:
            return True, "Сетевые адаптеры включены. Попробуйте запустить снова"
        return False, f"Не удалось включить адаптеры: {result.stderr[:200]}"
    except Exception as e:
        return False, f"Ошибка: {e}"


def _fix_enable_bfe() -> Tuple[bool, str]:
    """Enable and start Base Filtering Engine service."""
    try:
        subprocess.run(
            ["sc", "config", "BFE", "start=", "auto"],
            capture_output=True, timeout=5, creationflags=0x08000000,
        )
        result = subprocess.run(
            ["net", "start", "BFE"],
            capture_output=True, text=True, timeout=10, creationflags=0x08000000,
        )
        if result.returncode == 0 or "already been started" in (result.stderr or "").lower():
            return True, "Служба BFE запущена. Попробуйте запустить снова"
        return False, f"Не удалось запустить BFE: {result.stderr[:200]}"
    except Exception as e:
        return False, f"Ошибка: {e}"


def _fix_enable_driver() -> Tuple[bool, str]:
    """Set WinDivert service start type to demand."""
    try:
        result = subprocess.run(
            ["sc", "config", "WinDivert", "start=", "demand"],
            capture_output=True, text=True, timeout=5, creationflags=0x08000000,
        )
        if result.returncode == 0:
            return True, "Служба WinDivert переключена на ручной запуск. Попробуйте запустить снова"
        return False, f"Не удалось изменить настройки: {result.stderr[:200]}"
    except Exception as e:
        return False, f"Ошибка: {e}"
