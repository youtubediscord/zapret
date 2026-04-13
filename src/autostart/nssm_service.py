"""
Модуль для создания Windows служб через NSSM (Non-Sucking Service Manager).
NSSM - профессиональное решение для запуска обычных приложений как служб Windows.

Преимущества NSSM:
- Автоматический перезапуск при крашах
- Правильная обработка сигналов Windows  
- Перенаправление stdout/stderr в логи
- Управление через стандартные команды Windows
"""

import os
import subprocess
import time
from typing import List, Optional
from log.log import log



def kill_winws_processes() -> bool:
    """
    ⚡ Завершает все запущенные процессы winws.exe и winws2.exe.
    Необходимо перед запуском службы, чтобы избежать конфликта фильтров WinDivert.
    """
    try:
        import psutil

        killed_count = 0
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                proc_name = proc.info['name'].lower() if proc.info['name'] else ""
                if proc_name in ('winws.exe', 'winws2.exe'):
                    log(f"🔪 Завершаем процесс {proc_name} (PID: {proc.info['pid']})", "DEBUG")
                    proc.kill()
                    killed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        if killed_count > 0:
            log(f"✅ Завершено {killed_count} процесс(ов) winws", "INFO")
            # Небольшая пауза для освобождения WinDivert
            import time
            time.sleep(0.5)

        return True
    except Exception as e:
        log(f"⚠️ Ошибка завершения процессов winws: {e}", "WARNING")
        return False


def get_nssm_path() -> Optional[str]:
    """⚡ Получает путь к nssm.exe"""
    try:
        # Пробуем несколько вариантов
        possible_paths = []
        
        # 1. Через config (работает в exe)
        try:
            from config.config import EXE_FOLDER

            possible_paths.append(os.path.join(EXE_FOLDER, "nssm.exe"))
        except:
            pass
        
        # 2. Относительно текущей директории (для разработки)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)  # autostart -> project root
        possible_paths.append(os.path.join(project_root, "exe", "nssm.exe"))
        
        # 3. В папке zapret (для разработки)
        zapret_path = os.path.join(os.path.dirname(project_root), "zapret", "exe", "nssm.exe")
        possible_paths.append(zapret_path)
        
        # Ищем первый существующий
        for nssm_path in possible_paths:
            if os.path.exists(nssm_path):
                log(f"✅ NSSM найден: {nssm_path}", "DEBUG")
                return nssm_path
        
        log(f"❌ NSSM не найден. Проверенные пути: {possible_paths}", "WARNING")
        return None
    except Exception as e:
        log(f"Ошибка поиска NSSM: {e}", "ERROR")
        return None


def _decode_nssm_output(raw_text: str) -> str:
    """Декодирует вывод NSSM, включая UTF-16 с NUL-байтами."""
    text = (raw_text or "").strip()
    if not text:
        return "(пусто)"

    if "\x00" not in text:
        return text

    # NSSM на некоторых системах возвращает UTF-16LE, который уже декодирован
    # как single-byte text и выглядит как "E\x00r\x00r\x00...".
    for encoding in ("utf-16-le", "utf-16", "cp866", "cp1251", "utf-8"):
        try:
            decoded = text.encode("latin-1", errors="ignore").decode(encoding, errors="ignore").strip()
            if decoded:
                return decoded
        except Exception:
            continue

    return text.replace("\x00", "").strip()


def _wait_service_removed(service_name: str, timeout_seconds: float = 12.0) -> bool:
    """Ожидает, пока служба реально исчезнет из SCM."""
    try:
        from autostart.service_api import service_exists, get_service_state
    except Exception:
        return True

    deadline = time.time() + timeout_seconds
    last_state = None

    while time.time() < deadline:
        try:
            if not service_exists(service_name):
                return True

            state = get_service_state(service_name)
            if state != last_state:
                log(f"⏳ Ожидание удаления службы '{service_name}' (state: {state})", "DEBUG")
                last_state = state
        except Exception:
            pass

        time.sleep(0.25)

    try:
        return not service_exists(service_name)
    except Exception:
        return False


def create_service_with_nssm(
    service_name: str,
    display_name: str,
    exe_path: str,
    args: List[str],
    work_dir: Optional[str] = None,
    description: Optional[str] = None,
    auto_start: bool = True
) -> bool:
    """
    ⚡ Создает Windows службу через NSSM
    
    Args:
        service_name: Внутреннее имя службы
        display_name: Отображаемое имя
        exe_path: Путь к исполняемому файлу
        args: Список аргументов
        description: Описание службы
        auto_start: Автозапуск при загрузке системы
    
    Returns:
        True если служба создана успешно
    """
    nssm_path = get_nssm_path()
    if not nssm_path:
        return False
    
    try:
        log(f"⚡ Создание службы '{service_name}' через NSSM...", "INFO")
        
        # Проверяем существование exe файла
        if not os.path.exists(exe_path):
            log(f"❌ Исполняемый файл не найден: {exe_path}", "ERROR")
            return False
        
        exe_path = str(exe_path)
        args = [str(a) for a in (args or [])]

        log(f"✅ Исполняемый файл: {exe_path}", "DEBUG")
        log(f"📊 Количество аргументов: {len(args)}", "DEBUG")

        # Рабочая директория приложения (важно для winws2 @preset и относительных путей)
        app_directory = work_dir or os.path.dirname(exe_path)
        try:
            if app_directory and not os.path.isdir(app_directory):
                log(f"⚠️ AppDirectory не существует: {app_directory}", "WARNING")
        except Exception:
            pass
        
        # Проверяем длину командной строки
        # Используем windows-совместимое экранирование (важно для пробелов в путях)
        full_command = subprocess.list2cmdline([exe_path] + args)
        cmd_length = len(full_command)
        log(f"📏 Длина командной строки: {cmd_length} символов", "DEBUG")
        
        if cmd_length > 8191:  # Ограничение Windows для CreateProcess
            log(f"⚠️ Командная строка слишком длинная ({cmd_length} > 8191)", "WARNING")
        
        # 1. Удаляем старую службу если есть
        try:
            from autostart.service_api import service_exists, delete_service
            service_exists_fn = service_exists
            delete_service_fn = delete_service
        except Exception:
            service_exists_fn = service_exists_nssm
            delete_service_fn = None

        if service_exists_fn(service_name):
            log(f"🔄 Служба '{service_name}' уже существует, удаляем...", "DEBUG")
            remove_service_with_nssm(service_name)

            # Если NSSM remove пометил службу на удаление, но она ещё в SCM,
            # даём ей время исчезнуть и при необходимости пробуем WinAPI.
            if service_exists_fn(service_name) and delete_service_fn is not None:
                log(f"⚠️ Служба '{service_name}' ещё существует, пробуем удалить через WinAPI...", "WARNING")
                try:
                    delete_service_fn(service_name)
                except Exception:
                    pass

            if service_exists_fn(service_name) and not _wait_service_removed(service_name):
                log(f"⚠️ Служба '{service_name}' ещё удаляется. Повторите попытку через пару секунд.", "WARNING")
                return False
        
        # 2. Устанавливаем службу (БЕЗ аргументов - они добавляются отдельно!)
        #    Особенность NSSM: в окне services.msc будет отображаться путь до nssm.exe,
        #    а реальные бинарь и параметры хранятся в AppDirectory / AppParameters.
        #    Это нормальное поведение NSSM, код здесь рабочий.
        install_cmd = [nssm_path, "install", service_name, exe_path]
        log(f"📝 NSSM install: {service_name} -> {exe_path}", "DEBUG")
        
        try:
            result = subprocess.run(
                install_cmd,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=10
            )
        except subprocess.TimeoutExpired:
            log("❌ NSSM не ответил в течение 10 секунд (возможно заблокирован антивирусом)", "ERROR")
            return False
        except Exception as run_error:
            log(f"❌ Ошибка запуска NSSM install: {run_error}", "ERROR")
            return False
        
        if result.returncode != 0:
            error_code = result.returncode
            
            log(f"❌ NSSM install failed (код {error_code})", "ERROR")
            
            # Полный вывод stderr и stdout (без обрезки)
            stderr_text = _decode_nssm_output(result.stderr or "")
            stdout_text = _decode_nssm_output(result.stdout or "")
            
            log(f"📄 NSSM stderr ({len(result.stderr or '')} байт): {stderr_text}", "WARNING")
            log(f"📄 NSSM stdout ({len(result.stdout or '')} байт): {repr(stdout_text)}", "DEBUG")
            
            # Для ошибки 5 (Access Denied) проводим дополнительную диагностику
            if error_code == 5:
                log("🔍 ЗАПУСК ДИАГНОСТИКИ ошибки доступа (код 5):", "WARNING")
                
                # Проверяем доступ к SCM (Service Control Manager)
                try:
                    import ctypes
                    from ctypes import wintypes
                    
                    # Проверяем, что мы администратор
                    is_admin = ctypes.windll.shell32.IsUserAnAdmin()
                    log(f"  📋 IsUserAnAdmin: {is_admin}", "WARNING")
                    
                    advapi32 = ctypes.windll.advapi32
                    SC_MANAGER_ALL_ACCESS = 0xF003F
                    SC_MANAGER_CREATE_SERVICE = 0x0002
                    
                    # Пробуем открыть SCM с полным доступом
                    scm = advapi32.OpenSCManagerW(None, None, SC_MANAGER_ALL_ACCESS)
                    if scm:
                        advapi32.CloseServiceHandle(scm)
                        log("  ✅ SCM: полный доступ получен", "WARNING")
                    else:
                        scm_error = ctypes.get_last_error()
                        log(f"  ❌ SCM: нет полного доступа (код {scm_error})", "WARNING")
                    
                    # Пробуем открыть SCM с правом создания служб
                    scm2 = advapi32.OpenSCManagerW(None, None, SC_MANAGER_CREATE_SERVICE)
                    if scm2:
                        advapi32.CloseServiceHandle(scm2)
                        log("  ✅ SCM: право создания служб получено", "WARNING")
                    else:
                        scm_error2 = ctypes.get_last_error()
                        log(f"  ❌ SCM: нет права создания служб (код {scm_error2})", "WARNING")
                        
                        if scm_error2 == 5:
                            log("  ", "WARNING")
                            log("  💡 ВОЗМОЖНЫЕ ПРИЧИНЫ:", "WARNING")
                            log("     1️⃣ Антивирус блокирует создание служб (Kaspersky, Defender, etc)", "WARNING")
                            log("     2️⃣ Групповые политики (GPO) запрещают создание служб", "WARNING")
                            log("     3️⃣ NSSM.exe заблокирован антивирусом", "WARNING")
                            log("  ", "WARNING")
                            log("  🔧 РЕШЕНИЯ:", "WARNING")
                            log("     • Добавьте nssm.exe в исключения антивируса", "WARNING")
                            log("     • Проверьте групповые политики (gpedit.msc)", "WARNING")
                            log("     • Попробуйте временно отключить антивирус", "WARNING")
                except Exception as diag_error:
                    log(f"  ⚠️ Ошибка диагностики SCM: {diag_error}", "WARNING")
                    import traceback
                    log(f"  Traceback: {traceback.format_exc()}", "DEBUG")
                
                # Проверяем существующую службу
                try:
                    from autostart.service_api import get_service_state
                    state = get_service_state(service_name)
                    if state is not None:
                        log(f"  ⚠️ Служба '{service_name}' еще существует (state: {state})", "WARNING")
                        log("  💡 Служба не была полностью удалена перед созданием", "WARNING")
                except Exception:
                    pass
                
                # Проверяем реестр службы
                try:
                    import winreg
                    service_key = rf"SYSTEM\CurrentControlSet\Services\{service_name}"
                    try:
                        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, service_key, 0, winreg.KEY_READ)
                        winreg.CloseKey(key)
                        log(f"  ⚠️ Служба '{service_name}' найдена в реестре!", "WARNING")
                        log(f"     Путь: HKLM\\{service_key}", "WARNING")
                        log("  💡 Попробуйте удалить службу через: sc delete " + service_name, "WARNING")
                    except FileNotFoundError:
                        log(f"  ✅ Служба '{service_name}' не найдена в реестре", "WARNING")
                except Exception as reg_error:
                    log(f"  ⚠️ Ошибка проверки реестра: {reg_error}", "DEBUG")
            
            return False
        
        log(f"✅ Служба '{service_name}' установлена (базовая)", "DEBUG")
        
        # 3. Устанавливаем параметры приложения (аргументы)
        if args:
            # Объединяем аргументы в одну строку (с правильным quoting для Windows)
            args_string = subprocess.list2cmdline(args)
            log(f"📝 Устанавливаем параметры приложения ({len(args)} аргументов, {len(args_string)} символов)", "DEBUG")
            
            set_params_cmd = [nssm_path, "set", service_name, "AppParameters", args_string]
            
            try:
                params_result = subprocess.run(
                    set_params_cmd,
                    capture_output=True,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    timeout=10
                )
                
                if params_result.returncode != 0:
                    log(f"⚠️ Не удалось установить параметры приложения (код {params_result.returncode})", "WARNING")
                    stderr_text = params_result.stderr.strip() if params_result.stderr else "(пусто)"
                    log(f"   stderr: {repr(stderr_text)}", "WARNING")
                    # Не возвращаем False - служба создана, просто без параметров
                else:
                    log(f"✅ Параметры приложения установлены", "DEBUG")
                    
            except subprocess.TimeoutExpired:
                log("⚠️ Таймаут при установке параметров приложения", "WARNING")
            except Exception as params_error:
                log(f"⚠️ Ошибка установки параметров: {params_error}", "WARNING")
        
        log(f"✅ Служба '{service_name}' полностью установлена", "DEBUG")
        
        # 4. Настраиваем параметры службы
        configs = [
            ("DisplayName", display_name),
            ("Start", "SERVICE_AUTO_START" if auto_start else "SERVICE_DEMAND_START"),
            ("AppDirectory", app_directory),
        ]
        
        if description:
            configs.append(("Description", description))
        
        # Настройка логирования
        from config.config import LOGS_FOLDER

        os.makedirs(LOGS_FOLDER, exist_ok=True)
        
        log_file = os.path.join(LOGS_FOLDER, f"{service_name}.log")
        # Каждый раз пересоздаем лог: старый файл удаляем, чтобы не разрастался
        try:
            if os.path.exists(log_file):
                os.remove(log_file)
        except Exception:
            pass
        configs.extend([
            ("AppStdout", log_file),
            ("AppStderr", log_file),
            ("AppRotateFiles", "3"),      # Храним до 3 файлов
            ("AppRotateBytes", "2097152"),# Размер каждого до 2 МБ
        ])
        
        # Применяем все настройки
        for param, value in configs:
            set_cmd = [nssm_path, "set", service_name, param, value]
            subprocess.run(
                set_cmd,
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        
        # 5. Настраиваем автоперезапуск при крашах
        restart_cmd = [nssm_path, "set", service_name, "AppExit", "Default", "Restart"]
        subprocess.run(
            restart_cmd,
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        # 6. Проверяем применённые параметры (для отладки)
        try:
            check_params = [
                ("AppDirectory", "DEBUG"),
                ("AppParameters", "DEBUG"),
            ]
            for param, level in check_params:
                get_cmd = [nssm_path, "get", service_name, param]
                get_result = subprocess.run(
                    get_cmd,
                    capture_output=True,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    timeout=5
                )
                if get_result.returncode == 0:
                    value = (get_result.stdout or "").strip()
                    log(f"🔍 {param}: {value[:500]}", level)
                else:
                    log(f"⚠️ Не удалось прочитать {param} (код {get_result.returncode})", "WARNING")
        except Exception as check_err:
            log(f"⚠️ Ошибка проверки параметров службы: {check_err}", "WARNING")
        
        log(f"✅ Служба '{service_name}' настроена", "INFO")
        
        # Проверяем статус созданной службы
        try:
            status_cmd = [nssm_path, "status", service_name]
            status_result = subprocess.run(
                status_cmd,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=5
            )
            status_text = status_result.stdout.strip() if status_result.stdout else "Unknown"
            log(f"📊 Статус службы после создания: {status_text}", "DEBUG")
        except Exception:
            pass
        
        return True
        
    except Exception as e:
        log(f"Ошибка создания службы через NSSM: {e}", "ERROR")
        return False


def start_service_with_nssm(service_name: str) -> bool:
    """⚡ Запускает службу через NSSM"""
    # Примечание по NSSM:
    # - В services.msc всегда будет отображаться путь до nssm.exe — это нормально.
    #   Реальные бинарь и параметры лежат в AppDirectory/AppParameters.
    # - Статус SERVICE_PAUSED/Unexpected status обычно означает, что winws2.exe
    #   уже запущен где-то еще (ручной запуск или прежняя служба). Остановите
    #   старый winws2.exe перед стартом службы (nssm stop / taskkill).
    nssm_path = get_nssm_path()
    if not nssm_path:
        return False

    try:
        # Завершаем старые процессы winws перед запуском службы
        kill_winws_processes()

        cmd = [nssm_path, "start", service_name]
        log(f"Запуск службы '{service_name}' через NSSM...", "DEBUG")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=30
        )
        
        if result.returncode == 0:
            log(f"✅ Служба '{service_name}' запущена", "INFO")
            return True
        else:
            error_code = result.returncode
            stderr_text = _decode_nssm_output(result.stderr or "")
            
            log(f"❌ Не удалось запустить службу '{service_name}' (код {error_code})", "ERROR")
            log(f"📄 NSSM: {stderr_text}", "WARNING")
            
            # Дополнительная диагностика по тексту
            if "SERVICE_PAUSED" in stderr_text or "already running" in stderr_text:
                log("💡 SERVICE_PAUSED / already running:", "WARNING")
                log("   • Уже работает другой winws2.exe с тем же фильтром", "WARNING")
                log(f"   • Остановите предыдущий экземпляр: nssm stop {service_name} или taskkill /IM winws2.exe /F", "WARNING")
                log("   • После остановки запустите службу снова", "WARNING")
            
            # Дополнительная диагностика
            if error_code == 2:
                log("💡 Код 2: Служба не запустилась. Возможные причины:", "WARNING")
                log("   • winws2.exe не запускается (неверные аргументы)", "WARNING")
                log("   • Порт уже занят другим процессом", "WARNING")
                log("   • Путь к файлу lua или списку некорректен", "WARNING")
            
            return False
            
    except subprocess.TimeoutExpired:
        log(f"❌ Служба '{service_name}' не запустилась за 30 секунд (возможно зависла)", "ERROR")
        return False
    except Exception as e:
        log(f"❌ Ошибка запуска службы через NSSM: {e}", "ERROR")
        import traceback
        log(f"Traceback: {traceback.format_exc()}", "DEBUG")
        return False


def stop_service_with_nssm(service_name: str) -> bool:
    """⚡ Останавливает службу через NSSM"""
    nssm_path = get_nssm_path()
    if not nssm_path:
        return False
    
    try:
        cmd = [nssm_path, "stop", service_name]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        if result.returncode == 0:
            log(f"✅ Служба '{service_name}' остановлена", "INFO")
            return True
        else:
            stderr_text = _decode_nssm_output(result.stderr or "")
            log(f"⚠️ Предупреждение остановки службы: {stderr_text}", "WARNING")
            return False
            
    except subprocess.TimeoutExpired:
        log(f"Таймаут остановки службы '{service_name}'", "WARNING")
        return False
    except Exception as e:
        log(f"Ошибка остановки службы через NSSM: {e}", "ERROR")
        return False


def remove_service_with_nssm(service_name: str) -> bool:
    """⚡ Удаляет службу через NSSM"""
    nssm_path = get_nssm_path()
    if not nssm_path:
        return False
    
    try:
        # Сначала останавливаем
        stop_service_with_nssm(service_name)
        
        # Потом удаляем
        cmd = [nssm_path, "remove", service_name, "confirm"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        if result.returncode == 0:
            log(f"✅ Служба '{service_name}' удалена", "INFO")
            return True
        else:
            # Служба может не существовать - это OK
            log(f"Служба '{service_name}' не найдена или уже удалена", "DEBUG")
            return True
            
    except Exception as e:
        log(f"Ошибка удаления службы через NSSM: {e}", "ERROR")
        return False


def service_exists_nssm(service_name: str) -> bool:
    """⚡ Проверяет существование службы через NSSM"""
    nssm_path = get_nssm_path()
    if not nssm_path:
        return False
    
    try:
        cmd = [nssm_path, "status", service_name]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        # Если returncode == 0, служба существует
        return result.returncode == 0
        
    except Exception as e:
        log(f"Ошибка проверки службы через NSSM: {e}", "ERROR")
        return False
