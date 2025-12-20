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
from typing import List, Optional
from log import log


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
            from config import EXE_FOLDER
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


def create_service_with_nssm(
    service_name: str,
    display_name: str,
    exe_path: str,
    args: List[str],
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
        
        log(f"✅ Исполняемый файл: {exe_path}", "DEBUG")
        log(f"📊 Количество аргументов: {len(args)}", "DEBUG")
        
        # Проверяем длину командной строки
        full_command = f"{exe_path} " + " ".join(args)
        cmd_length = len(full_command)
        log(f"📏 Длина командной строки: {cmd_length} символов", "DEBUG")
        
        if cmd_length > 8191:  # Ограничение Windows для CreateProcess
            log(f"⚠️ Командная строка слишком длинная ({cmd_length} > 8191)", "WARNING")
        
        # 1. Удаляем старую службу если есть
        if service_exists_nssm(service_name):
            log(f"🔄 Служба '{service_name}' уже существует, удаляем...", "DEBUG")
            remove_service_with_nssm(service_name)
        
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
            stderr_text = result.stderr.strip() if result.stderr else "(пусто)"
            stdout_text = result.stdout.strip() if result.stdout else "(пусто)"
            
            log(f"📄 NSSM stderr ({len(result.stderr or '')} байт): {repr(stderr_text)}", "ERROR")
            log(f"📄 NSSM stdout ({len(result.stdout or '')} байт): {repr(stdout_text)}", "DEBUG")
            
            # Для ошибки 5 (Access Denied) проводим дополнительную диагностику
            if error_code == 5:
                log("🔍 ЗАПУСК ДИАГНОСТИКИ ошибки доступа (код 5):", "ERROR")
                
                # Проверяем доступ к SCM (Service Control Manager)
                try:
                    import ctypes
                    from ctypes import wintypes
                    
                    # Проверяем, что мы администратор
                    is_admin = ctypes.windll.shell32.IsUserAnAdmin()
                    log(f"  📋 IsUserAnAdmin: {is_admin}", "ERROR")
                    
                    advapi32 = ctypes.windll.advapi32
                    SC_MANAGER_ALL_ACCESS = 0xF003F
                    SC_MANAGER_CREATE_SERVICE = 0x0002
                    
                    # Пробуем открыть SCM с полным доступом
                    scm = advapi32.OpenSCManagerW(None, None, SC_MANAGER_ALL_ACCESS)
                    if scm:
                        advapi32.CloseServiceHandle(scm)
                        log("  ✅ SCM: полный доступ получен", "ERROR")
                    else:
                        scm_error = ctypes.get_last_error()
                        log(f"  ❌ SCM: нет полного доступа (код {scm_error})", "ERROR")
                    
                    # Пробуем открыть SCM с правом создания служб
                    scm2 = advapi32.OpenSCManagerW(None, None, SC_MANAGER_CREATE_SERVICE)
                    if scm2:
                        advapi32.CloseServiceHandle(scm2)
                        log("  ✅ SCM: право создания служб получено", "ERROR")
                    else:
                        scm_error2 = ctypes.get_last_error()
                        log(f"  ❌ SCM: нет права создания служб (код {scm_error2})", "ERROR")
                        
                        if scm_error2 == 5:
                            log("  ", "ERROR")
                            log("  💡 ВОЗМОЖНЫЕ ПРИЧИНЫ:", "ERROR")
                            log("     1️⃣ Антивирус блокирует создание служб (Kaspersky, Defender, etc)", "ERROR")
                            log("     2️⃣ Групповые политики (GPO) запрещают создание служб", "ERROR")
                            log("     3️⃣ NSSM.exe заблокирован антивирусом", "ERROR")
                            log("  ", "ERROR")
                            log("  🔧 РЕШЕНИЯ:", "ERROR")
                            log("     • Добавьте nssm.exe в исключения антивируса", "ERROR")
                            log("     • Проверьте групповые политики (gpedit.msc)", "ERROR")
                            log("     • Попробуйте временно отключить антивирус", "ERROR")
                except Exception as diag_error:
                    log(f"  ⚠️ Ошибка диагностики SCM: {diag_error}", "ERROR")
                    import traceback
                    log(f"  Traceback: {traceback.format_exc()}", "DEBUG")
                
                # Проверяем существующую службу
                try:
                    from autostart.service_api import get_service_status
                    status = get_service_status(service_name)
                    if status is not None:
                        log(f"  ⚠️ Служба '{service_name}' еще существует (статус: {status})", "ERROR")
                        log("  💡 Служба не была полностью удалена перед созданием", "ERROR")
                except Exception:
                    pass
                
                # Проверяем реестр службы
                try:
                    import winreg
                    service_key = rf"SYSTEM\CurrentControlSet\Services\{service_name}"
                    try:
                        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, service_key, 0, winreg.KEY_READ)
                        winreg.CloseKey(key)
                        log(f"  ⚠️ Служба '{service_name}' найдена в реестре!", "ERROR")
                        log(f"     Путь: HKLM\\{service_key}", "ERROR")
                        log("  💡 Попробуйте удалить службу через: sc delete " + service_name, "ERROR")
                    except FileNotFoundError:
                        log(f"  ✅ Служба '{service_name}' не найдена в реестре", "ERROR")
                except Exception as reg_error:
                    log(f"  ⚠️ Ошибка проверки реестра: {reg_error}", "DEBUG")
            
            return False
        
        log(f"✅ Служба '{service_name}' установлена (базовая)", "DEBUG")
        
        # 3. Устанавливаем параметры приложения (аргументы)
        if args:
            # Объединяем аргументы в одну строку
            args_string = " ".join(args)
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
            ("AppDirectory", os.path.dirname(exe_path)),
        ]
        
        if description:
            configs.append(("Description", description))
        
        # Настройка логирования
        from config import LOGS_FOLDER
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
            stderr_text = result.stderr.strip() if result.stderr else "(пусто)"
            stdout_text = result.stdout.strip() if result.stdout else "(пусто)"
            
            # Пытаемся декодировать UTF-16 (NSSM иногда отдает в UTF-16)
            try:
                if '\x00' in stderr_text:
                    stderr_decoded = stderr_text.encode('latin-1').decode('utf-16-le').strip()
                    stderr_text = stderr_decoded
            except Exception:
                pass
            
            log(f"❌ Не удалось запустить службу '{service_name}' (код {error_code})", "ERROR")
            log(f"📄 NSSM: {stderr_text}", "ERROR")
            
            # Дополнительная диагностика по тексту
            if "SERVICE_PAUSED" in stderr_text or "already running" in stderr_text:
                log("💡 SERVICE_PAUSED / already running:", "ERROR")
                log("   • Уже работает другой winws2.exe с тем же фильтром", "ERROR")
                log("   • Остановите предыдущий экземпляр: nssm stop ZapretDirectService или taskkill /IM winws2.exe /F", "ERROR")
                log("   • После остановки запустите службу снова", "ERROR")
            
            # Дополнительная диагностика
            if error_code == 2:
                log("💡 Код 2: Служба не запустилась. Возможные причины:", "ERROR")
                log("   • winws2.exe не запускается (неверные аргументы)", "ERROR")
                log("   • Порт уже занят другим процессом", "ERROR")
                log("   • Путь к файлу lua или списку некорректен", "ERROR")
            
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
            stderr_text = result.stderr.strip() if result.stderr else "(пусто)"
            log(f"⚠️ Предупреждение остановки службы: {repr(stderr_text)}", "WARNING")
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

