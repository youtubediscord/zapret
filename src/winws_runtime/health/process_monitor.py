# winws_runtime/health/process_monitor.py
"""
Модуль для проверки здоровья процесса winws.exe после запуска
Мониторит процесс в течение первых секунд и определяет, не упал ли он
"""

import subprocess
import time
from typing import Dict, Optional, Tuple

from log.log import log
from settings.mode import EXE_NAME_WINWS1

from utils.windows_event_log import get_recent_application_error_messages
from utils.windows_process_probe import iter_process_records_winapi

from winws_runtime.health.antivirus_detection import _detect_active_antivirus


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


def check_process_health(process_name: str = EXE_NAME_WINWS1, monitor_duration: int = 5, check_interval: float = 0.5) -> Tuple[bool, Optional[str]]:
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


def get_last_crash_info(process_name: str = EXE_NAME_WINWS1, minutes_back: int = 5) -> Optional[str]:
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


def check_common_crash_causes(process_name: str = EXE_NAME_WINWS1) -> Optional[str]:
    """
    Проверяет типичные причины падения winws.exe

    Returns:
        Optional[str]: Описание возможной причины или None
    """
    suggestions = []

    # Проверяем конфликтующие программы только после падения запуска.
    try:
        from winws_runtime.health.launch_conflicts import check_conflicting_processes

        conflicting = check_conflicting_processes()
        if conflicting:
            suggestions.append("ОБНАРУЖЕНЫ КОНФЛИКТУЮЩИЕ ПРОГРАММЫ:")
            for conflict in conflicting:
                pid_info = f" (PID: {conflict['pid']})" if conflict.get('pid') else ""
                suggestions.append(f"   • {conflict['name']} ({conflict['exe']}{pid_info})")
                suggestions.append(f"     Причина: {conflict['reason']}")
                suggestions.append(f"     Решение: {conflict['solution']}")
            suggestions.append("")
    except Exception:
        pass

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
        # Та же проверка, которую использует диагностика кода завершения.
        # Важно учитывать переименованный Monkey64.sys и не требовать сразу
        # все варианты имён драйвера.
        from winws_runtime.health.winws_exit_diagnosis import _check_windivert_files

        missing_files = _check_windivert_files()

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
            suggestions.append(f"     Добавьте {EXE_NAME_WINWS1} и WinDivert в исключения антивируса")
    except Exception:
        pass

    if suggestions:
        return "\n".join(suggestions)

    return None


# ✅ Проверка длины командной строки
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


# ✅ Подсчет аргументов по категориям
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
