"""
Модуль для проверки здоровья процесса winws.exe после запуска
Мониторит процесс в течение первых секунд и определяет, не упал ли он
"""

import time
import subprocess
import psutil  # ✅ ДОБАВИТЬ: pip install psutil
from typing import Tuple, Optional, List, Dict
from log import log

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
    'winws.exe': {  # ✅ НОВОЕ: Проверка дублей
        'name': 'Другой экземпляр winws.exe',
        'reason': 'Уже запущен другой экземпляр DPI обхода',
        'solution': 'Остановите старый экземпляр перед запуском нового'
    },
    'winws2.exe': {  # Проверка дублей для Zapret 2
        'name': 'Другой экземпляр winws2.exe',
        'reason': 'Уже запущен другой экземпляр DPI обхода (Zapret 2)',
        'solution': 'Остановите старый экземпляр перед запуском нового'
    }
}

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
    # ✅ ИСПРАВЛЕНИЕ: Используем psutil как основной метод (быстрее и надежнее WMI)
    try:
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name'].lower() == process_name.lower():
                    return True, proc.info['pid']
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False, None
    except Exception as e:
        log(f"Ошибка проверки процесса через psutil: {e}", "DEBUG")
    
    # ✅ Fallback 1: WMI (если psutil не установлен)
    try:
        import win32com.client
        wmi = win32com.client.GetObject("winmgmts:")
        # ✅ ИСПРАВЛЕНИЕ: Более безопасный запрос
        processes = wmi.ExecQuery(
            f"SELECT ProcessId FROM Win32_Process WHERE Name='{process_name}'",
            "WQL",
            0x30  # wbemFlagReturnImmediately + wbemFlagForwardOnly
        )
        
        for process in processes:
            try:
                return True, process.ProcessId
            except:
                pass
        
        return False, None
            
    except Exception as e:
        log(f"Ошибка проверки процесса через WMI: {e}", "DEBUG")

    # Если ни psutil, ни WMI не сработали - процесс не найден
    return False, None

def _get_crash_details(process_name: str) -> Optional[str]:
    """
    Пытается получить детали о падении процесса из журнала событий Windows
    
    Returns:
        Optional[str]: Описание ошибки или None
    """
    try:
        # Используем PowerShell для чтения журнала событий
        ps_script = f"""
        $events = Get-WinEvent -FilterHashtable @{{
            LogName='Application'
            ProviderName='Application Error','Windows Error Reporting'
            StartTime=(Get-Date).AddMinutes(-1)
        }} -MaxEvents 10 -ErrorAction SilentlyContinue | 
        Where-Object {{$_.Message -like '*{process_name}*'}} | 
        Select-Object -First 1

        if ($events) {{
            $events.Message
        }}
        """
        
        result = subprocess.run(
            ['powershell.exe', '-WindowStyle', 'Hidden', '-NoProfile', '-Command', ps_script],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=0x08000000  # CREATE_NO_WINDOW
        )
        
        if result.stdout.strip():
            output = result.stdout.strip()
            
            # Ищем код исключения
            if "Exception code:" in output or "код исключения:" in output.lower():
                lines = output.split('\n')
                for line in lines:
                    if "exception code" in line.lower() or "код исключения" in line.lower():
                        return line.strip()
            
            # Возвращаем первую строку сообщения
            first_line = output.split('\n')[0][:200]  # Ограничиваем длину
            return first_line
            
    except subprocess.TimeoutExpired:
        log("Timeout при получении деталей падения из Event Log", "DEBUG")
    except Exception as e:
        log(f"Ошибка получения деталей падения: {e}", "DEBUG")
    
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
        ps_script = f"""
        $events = Get-WinEvent -FilterHashtable @{{
            LogName='Application'
            ProviderName='Application Error','Windows Error Reporting'
            StartTime=(Get-Date).AddMinutes(-{minutes_back})
        }} -MaxEvents 20 -ErrorAction SilentlyContinue | 
        Where-Object {{$_.Message -like '*{process_name}*'}}

        if ($events) {{
            $events | ForEach-Object {{
                "[$($_.TimeCreated.ToString('HH:mm:ss'))] $($_.LevelDisplayName): $($_.Message.Split([Environment]::NewLine)[0])"
            }} | Select-Object -First 5
        }}
        """
        
        result = subprocess.run(
            ['powershell.exe', '-WindowStyle', 'Hidden', '-NoProfile', '-Command', ps_script],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=0x08000000
        )
        
        if result.stdout.strip():
            return result.stdout.strip()
            
    except Exception as e:
        log(f"Ошибка получения истории падений: {e}", "DEBUG")
    
    return None

def check_conflicting_processes() -> List[Dict[str, str]]:
    """
    Проверяет наличие конфликтующих процессов
    
    Returns:
        List[Dict]: Список найденных конфликтующих процессов с информацией
    """
    found_conflicts = []
    
    # ✅ ИСПРАВЛЕНИЕ: Используем psutil вместо tasklist
    try:
        for proc in psutil.process_iter(['name', 'pid']):
            try:
                proc_name = proc.info['name']
                
                # Проверяем каждый конфликтующий процесс
                for conflict_exe, info in CONFLICTING_PROCESSES.items():
                    if proc_name.lower() == conflict_exe.lower():
                        # ✅ ОСОБАЯ ПРОВЕРКА для winws.exe (игнорируем "свой" процесс)
                        if conflict_exe.lower() == 'winws.exe':
                            # Пропускаем если это наш процесс (будет проверяться отдельно)
                            continue
                        
                        found_conflicts.append({
                            'exe': conflict_exe,
                            'name': info['name'],
                            'reason': info['reason'],
                            'solution': info['solution'],
                            'pid': proc.info['pid']
                        })
                        log(f"⚠ Обнаружен конфликтующий процесс: {info['name']} ({conflict_exe}, PID: {proc.info['pid']})", "WARNING")
                        break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    
    except Exception as e:
        log(f"Ошибка проверки конфликтующих процессов через psutil: {e}", "DEBUG")

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
        from config import WINDIVERT_FOLDER
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
        import win32com.client
        wmi = win32com.client.GetObject("winmgmts:")
        av_products = wmi.ExecQuery("SELECT * FROM AntiVirusProduct", "root\\SecurityCenter2")
        
        active_av = []
        for av in av_products:
            try:
                if hasattr(av, 'displayName'):
                    active_av.append(av.displayName)
            except:
                pass
        
        if active_av:
            suggestions.append(f"  Обнаружен антивирус: {', '.join(active_av)}")
            suggestions.append("     Добавьте winws.exe и WinDivert в исключения антивируса")
    except:
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
            # ✅ ИСПРАВЛЕНИЕ: Используем psutil для более надежного завершения
            pid = conflict.get('pid')
            if pid:
                try:
                    proc = psutil.Process(pid)
                    proc.terminate()
                    proc.wait(timeout=5)
                    log(f"✅ Процесс {conflict['name']} (PID {pid}) успешно закрыт", "SUCCESS")
                    success_count += 1
                    continue
                except psutil.NoSuchProcess:
                    log(f"Процесс {conflict['name']} уже завершен", "DEBUG")
                    success_count += 1
                    continue
                except psutil.TimeoutExpired:
                    log(f"Процесс {conflict['name']} не отвечает, принудительное завершение...", "WARNING")
                    proc.kill()
                    success_count += 1
                    continue
            
            # Fallback на Win API
            from utils.process_killer import kill_process_by_name
            killed = kill_process_by_name(conflict['exe'], kill_all=True)
            
            if killed > 0:
                log(f"✅ Процесс {conflict['name']} успешно закрыт через Win API", "SUCCESS")
                success_count += 1
            else:
                log(f"❌ Не удалось закрыть {conflict['name']}", "ERROR")
                
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
                from utils.process_killer import kill_winws_force
                if kill_winws_force():
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
            from utils.process_killer import kill_winws_force
            from utils.service_manager import cleanup_windivert_services, unload_driver

            # 1. Убиваем все процессы
            kill_winws_force()

            # 2. Очищаем WinDivert службы
            cleanup_windivert_services()

            # 3. Выгружаем драйверы WinDivert
            for driver in ["WinDivert", "WinDivert14", "WinDivert64", "Monkey"]:
                try:
                    unload_driver(driver)
                except:
                    pass

            import time
            time.sleep(0.5)

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
        import win32com.client
        wmi = win32com.client.GetObject("winmgmts:")

        # Проверяем активные антивирусы
        try:
            av_products = wmi.ExecQuery("SELECT * FROM AntiVirusProduct", "root\\SecurityCenter2")
            active_av = []
            for av in av_products:
                if hasattr(av, 'displayName'):
                    active_av.append(av.displayName)

            if active_av:
                # Проверяем Windows Defender отдельно
                if any('defender' in av.lower() or 'microsoft' in av.lower() for av in active_av):
                    return f"Windows Defender может блокировать winws.exe"
                return f"Антивирус ({', '.join(active_av[:2])}) может блокировать winws.exe"
        except:
            pass

        # Проверка журнала Windows Defender
        if exe_path:
            try:
                import subprocess
                result = subprocess.run(
                    ['powershell', '-Command',
                     f'Get-MpThreatDetection | Where-Object {{$_.Resources -like "*winws*"}} | Select-Object -First 1'],
                    capture_output=True, text=True, timeout=5,
                    creationflags=0x08000000
                )
                if result.stdout.strip():
                    return "Windows Defender заблокировал winws.exe (обнаружена угроза)"
            except:
                pass
    except:
        pass

    return None


def _check_file_locked(file_path: str) -> Optional[str]:
    """Проверяет, заблокирован ли файл другим процессом"""
    try:
        # Пробуем открыть файл эксклюзивно
        import os
        fd = os.open(file_path, os.O_RDWR | os.O_EXCL)
        os.close(fd)
        return None
    except PermissionError:
        # Файл заблокирован, пытаемся найти кем
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    for f in proc.open_files():
                        if file_path.lower() in f.path.lower():
                            return f"{proc.info['name']} (PID: {proc.info['pid']})"
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    continue
        except:
            pass
        return "неизвестный процесс"
    except:
        return None


def _check_winws_already_running() -> Optional[int]:
    """Проверяет, запущен ли уже winws"""
    try:
        for proc in psutil.process_iter(['pid', 'name']):
            name = proc.info['name'].lower()
            if name in ('winws.exe', 'winws2.exe'):
                return proc.info['pid']
    except:
        pass
    return None