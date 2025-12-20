# trusted_installer.py
import ctypes
import sys
import os
import subprocess
import time
import win32api
import win32con
import win32process
import win32security
import win32service
import psutil
from log import log
from utils import run_hidden

def is_trusted_installer():
    """Проверяет, запущен ли процесс от имени TrustedInstaller"""
    try:
        # Получаем токен текущего процесса
        token = win32security.OpenProcessToken(
            win32api.GetCurrentProcess(),
            win32con.TOKEN_QUERY
        )
        
        # Получаем SID пользователя
        user_sid = win32security.GetTokenInformation(
            token, win32security.TokenUser
        )[0]
        
        # SID TrustedInstaller: S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464
        trusted_installer_sid = "S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464"
        
        return win32security.ConvertSidToStringSid(user_sid) == trusted_installer_sid
    except:
        return False

def ensure_trustedinstaller_service():
    """Убеждается, что служба TrustedInstaller запущена"""
    try:
        # Проверяем статус службы
        status = win32service.QueryServiceStatus(
            win32service.OpenService(
                win32service.OpenSCManager(None, None, win32service.SC_MANAGER_ALL_ACCESS),
                "TrustedInstaller",
                win32service.SERVICE_ALL_ACCESS
            )
        )[1]
        
        if status != win32service.SERVICE_RUNNING:
            log("Запуск службы TrustedInstaller...", "INFO")
            run_hidden('sc start TrustedInstaller', shell=True, capture_output=True)
            time.sleep(3)  # Даем время на запуск
            
        return True
    except Exception as e:
        log(f"Ошибка при запуске TrustedInstaller: {e}", "ERROR")
        return False

def get_trustedinstaller_token():
    """Получает токен процесса TrustedInstaller"""
    # Ищем процесс TrustedInstaller
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'].lower() == 'trustedinstaller.exe':
            try:
                # Открываем процесс
                process_handle = win32api.OpenProcess(
                    win32con.PROCESS_QUERY_INFORMATION,
                    False,
                    proc.info['pid']
                )
                
                # Получаем токен
                token_handle = win32security.OpenProcessToken(
                    process_handle,
                    win32con.TOKEN_DUPLICATE | win32con.TOKEN_QUERY
                )
                
                # Дублируем токен для использования
                return win32security.DuplicateTokenEx(
                    token_handle,
                    win32security.SecurityImpersonation,
                    win32con.TOKEN_ALL_ACCESS,
                    win32security.TokenPrimary
                )
            except Exception as e:
                log(f"Ошибка получения токена: {e}", "ERROR")
                
    return None

def run_as_trustedinstaller():
    """Перезапускает приложение от имени TrustedInstaller"""
    if "--trustedinstaller" in sys.argv:
        return True  # Уже запущены от TrustedInstaller
        
    log("Попытка запуска от имени TrustedInstaller...", "INFO")
    
    # Способ 1: Через NSudo (если доступен)
    nsudo_paths = [
        "C:\\Program Files\\NSudo\\NSudo.exe",
        "C:\\Program Files (x86)\\NSudo\\NSudo.exe",
        os.path.join(os.path.dirname(sys.executable), "NSudo.exe")
    ]
    
    for nsudo_path in nsudo_paths:
        if os.path.exists(nsudo_path):
            log(f"Найден NSudo: {nsudo_path}", "INFO")
            exe_path = sys.executable
            args = sys.argv[1:] + ["--trustedinstaller"]
            
            # Запускаем через NSudo
            cmd = [nsudo_path, "-U:T", "-P:E", exe_path] + args
            run_hidden(cmd)
            return False  # Завершаем текущий процесс
    
    # Способ 2: Через создание службы
    log("NSudo не найден, используем метод через службу", "INFO")
    
    service_name = "ZapretTrustedInstaller"
    exe_path = sys.executable
    args = " ".join([f'"{arg}"' for arg in sys.argv[1:] + ["--trustedinstaller"]])
    
    # Создаем bat файл для запуска
    bat_content = f'''
@echo off
"{exe_path}" {args}
'''
    
    bat_path = os.path.join(os.environ['TEMP'], 'zapret_trusted.bat')
    with open(bat_path, 'w') as f:
        f.write(bat_content)
    
    try:
        # Создаем службу
        create_service_cmd = f'''
sc create {service_name} binPath= "cmd /c \\"{bat_path}\\"" type= own start= demand
sc config {service_name} obj= "NT SERVICE\\TrustedInstaller"
'''
        run_hidden(create_service_cmd, shell=True, capture_output=True)
        
        # Запускаем службу
        run_hidden(f'sc start {service_name}', shell=True)
        
        # Удаляем службу через некоторое время
        time.sleep(2)
        run_hidden(f'sc delete {service_name}', shell=True, capture_output=True)
        
        return False  # Завершаем текущий процесс
        
    except Exception as e:
        log(f"Ошибка создания службы: {e}", "ERROR")
        
    # Способ 3: Через планировщик задач
    log("Пробуем через планировщик задач", "INFO")
    
    task_name = "ZapretTrustedInstallerTask"
    task_xml = f'''<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Principals>
    <Principal id="Author">
      <UserId>NT SERVICE\\TrustedInstaller</UserId>
      <LogonType>ServiceAccount</LogonType>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{exe_path}</Command>
      <Arguments>{args}</Arguments>
    </Exec>
  </Actions>
</Task>'''
    
    xml_path = os.path.join(os.environ['TEMP'], 'zapret_task.xml')
    with open(xml_path, 'w', encoding='utf-16') as f:
        f.write(task_xml)
    
    try:
        # Создаем и запускаем задачу
        run_hidden(f'schtasks /create /tn "{task_name}" /xml "{xml_path}" /f', shell=True)
        run_hidden(f'schtasks /run /tn "{task_name}"', shell=True)
        run_hidden(f'schtasks /delete /tn "{task_name}" /f', shell=True)
        
        return False
        
    except Exception as e:
        log(f"Ошибка планировщика: {e}", "ERROR")
    
    # Если ничего не сработало
    ctypes.windll.user32.MessageBoxW(
        None,
        "Не удалось запустить от имени TrustedInstaller.\n"
        "Приложение будет запущено с обычными правами администратора.",
        "Zapret",
        0x30  # MB_ICONWARNING
    )
    
    return True  # Продолжаем с текущими правами