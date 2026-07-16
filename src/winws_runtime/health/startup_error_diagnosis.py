# winws_runtime/health/startup_error_diagnosis.py
"""Диагностика исключений при запуске winws (диагноз + рекомендации)."""

import os
from typing import Optional

from settings.mode import EXE_NAME_WINWS1

from winws_runtime.health.antivirus_detection import _detect_active_antivirus
from winws_runtime.health.process_monitor import _find_process_pid_by_name_winapi


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

        # Проверка 2: конфликтующая программа помешала WinDivert
        try:
            from winws_runtime.health.launch_conflicts import build_launch_conflict_advice

            conflict_advice = build_launch_conflict_advice()
            if conflict_advice is not None:
                cause, solution = conflict_advice
                diagnostics.append(f"❌ Причина: {cause}")
                diagnostics.append(f"   Решение: {solution}")
                return "\n".join(diagnostics)
        except Exception:
            pass

        # Проверка 3: Антивирус блокирует
        av_blocking = _check_antivirus_blocking(exe_path)
        if av_blocking:
            diagnostics.append(f"❌ Причина: {av_blocking}")
            diagnostics.append("   Решение: Добавьте папку программы в исключения антивируса")
            return "\n".join(diagnostics)

        # Проверка 4: Файл заблокирован другим процессом
        if exe_path and os.path.exists(exe_path):
            locked_by = _check_file_locked(exe_path)
            if locked_by:
                diagnostics.append(f"❌ Причина: Файл заблокирован процессом: {locked_by}")
                diagnostics.append("   Решение: Закройте указанный процесс или перезагрузите компьютер")
                return "\n".join(diagnostics)

        # Проверка 5: Предыдущий winws ещё работает
        running_winws = _check_winws_already_running()
        if running_winws:
            diagnostics.append(f"❌ Причина: Уже запущен процесс winws (PID: {running_winws})")
            diagnostics.append("   Пытаемся автоматически завершить...")

            # Пробуем автоматически завершить
            try:
                from winws_runtime.runtime.system_ops import force_kill_all_winws_processes

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
            from winws_runtime.runtime.system_ops import aggressive_windivert_cleanup_runtime

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
                return f"Windows Defender может блокировать {EXE_NAME_WINWS1}"
            return f"Антивирус ({antivirus_name}) может блокировать {EXE_NAME_WINWS1}"
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
        from settings.mode import ALL_WINWS_EXE_NAMES

        for candidate in ALL_WINWS_EXE_NAMES:
            pid = _find_process_pid_by_name_winapi(candidate)
            if pid is not None:
                return pid
    except Exception:
        pass
    return None
