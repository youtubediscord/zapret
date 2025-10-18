# altmenu/defender_manager.py

import os
import subprocess
import winreg
from typing import Callable, Optional, List, Tuple
from log import log
REGISTRY_PATH = r"Software\ZapretReg2"

def set_defender_disabled(enabled: bool):
    """Сохраняет настройку отключения Windows Defender"""
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH) as key:
            winreg.SetValueEx(key, "DefenderDisabled", 0, winreg.REG_DWORD, int(enabled))
    except Exception as e:
        from log import log
        log(f"Ошибка при сохранении настройки Defender: {e}", "❌ ERROR")

class WindowsDefenderManager:
    """Менеджер для управления Windows Defender"""
    
    def __init__(self, status_callback: Optional[Callable] = None):
        self.status_callback = status_callback or (lambda x: None)
        
    def _set_status(self, message: str):
        """Обновляет статус в GUI"""
        self.status_callback(message)
        
    def _run_reg_command(self, command: str) -> bool:
        """Выполняет команду реестра с правами администратора"""
        try:
            # Проверяем, запущена ли программа с правами администратора
            import ctypes
            if not ctypes.windll.shell32.IsUserAnAdmin():
                log("Требуются права администратора для изменения Windows Defender", "⚠️ WARNING")
                return False
                
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                return True
            else:
                # Логируем только если есть реальная ошибка
                if result.stderr and result.stderr.strip():
                    log(f"Ошибка выполнения команды: {result.stderr}", "❌ ERROR")
                return False
        except Exception as e:
            log(f"Ошибка при выполнении команды реестра: {e}", "❌ ERROR")
            return False
    
    def is_defender_disabled(self) -> bool:
        """Проверяет, отключен ли Windows Defender"""
        try:
            # Проверяем несколько ключей для более точного определения
            keys_to_check = [
                (r"SOFTWARE\Policies\Microsoft\Windows Defender", "DisableAntiSpyware"),
                (r"SOFTWARE\Policies\Microsoft\Windows Defender\Real-Time Protection", "DisableRealtimeMonitoring"),
            ]
            
            disabled_count = 0
            for key_path, value_name in keys_to_check:
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_READ) as key:
                        value, _ = winreg.QueryValueEx(key, value_name)
                        if value == 1:
                            disabled_count += 1
                except:
                    pass
                    
            # Считаем отключенным, если хотя бы один ключ установлен
            return disabled_count > 0
            
        except Exception as e:
            log(f"Ошибка при проверке состояния Defender: {e}", "❌ ERROR")
            return False
    
    def disable_defender(self) -> Tuple[bool, int]:
        """
        Отключает Windows Defender
        Возвращает (успех, количество успешных команд)
        """
        commands = [
            # Основные настройки
            'reg add "HKEY_LOCAL_MACHINE\\SOFTWARE\\Policies\\Microsoft\\Windows Defender" /v DisableAntiSpyware /t REG_DWORD /d 1 /f',
            'reg add "HKEY_LOCAL_MACHINE\\SOFTWARE\\Policies\\Microsoft\\Windows Defender" /v DisableRealtimeMonitoring /t REG_DWORD /d 1 /f',
            'reg add "HKEY_LOCAL_MACHINE\\SOFTWARE\\Policies\\Microsoft\\Windows Defender" /v DisableAntiVirus /t REG_DWORD /d 1 /f',
            'reg add "HKEY_LOCAL_MACHINE\\SOFTWARE\\Policies\\Microsoft\\Windows Defender" /v DisableSpecialRunningModes /t REG_DWORD /d 1 /f',
            'reg add "HKEY_LOCAL_MACHINE\\SOFTWARE\\Policies\\Microsoft\\Windows Defender" /v DisableRoutinelyTakingAction /t REG_DWORD /d 1 /f',
            'reg add "HKEY_LOCAL_MACHINE\\SOFTWARE\\Policies\\Microsoft\\Windows Defender" /v ServiceKeepAlive /t REG_DWORD /d 0 /f',
            
            # Real-Time Protection
            'reg add "HKEY_LOCAL_MACHINE\\SOFTWARE\\Policies\\Microsoft\\Windows Defender\\Real-Time Protection" /v DisableRealtimeMonitoring /t REG_DWORD /d 1 /f',
            'reg add "HKEY_LOCAL_MACHINE\\SOFTWARE\\Policies\\Microsoft\\Windows Defender\\Real-Time Protection" /v DisableBehaviorMonitoring /t REG_DWORD /d 1 /f',
            'reg add "HKEY_LOCAL_MACHINE\\SOFTWARE\\Policies\\Microsoft\\Windows Defender\\Real-Time Protection" /v DisableOnAccessProtection /t REG_DWORD /d 1 /f',
            'reg add "HKEY_LOCAL_MACHINE\\SOFTWARE\\Policies\\Microsoft\\Windows Defender\\Real-Time Protection" /v DisableScanOnRealtimeEnable /t REG_DWORD /d 1 /f',
            'reg add "HKEY_LOCAL_MACHINE\\SOFTWARE\\Policies\\Microsoft\\Windows Defender\\Real-Time Protection" /v DisableIOAVProtection /t REG_DWORD /d 1 /f',
            
            # SmartScreen и обновления
            'reg add "HKEY_LOCAL_MACHINE\\SOFTWARE\\Policies\\Microsoft\\Windows Defender\\SmartScreen" /v ConfigureAppInstallControlEnabled /t REG_DWORD /d 0 /f',
            'reg add "HKEY_LOCAL_MACHINE\\SOFTWARE\\Policies\\Microsoft\\Windows Defender\\Signature Updates" /v ForceUpdateFromMU /t REG_DWORD /d 0 /f',
            
            # Spynet
            'reg add "HKEY_LOCAL_MACHINE\\SOFTWARE\\Policies\\Microsoft\\Windows Defender\\Spynet" /v DisableBlockAtFirstSeen /t REG_DWORD /d 1 /f',
            'reg add "HKEY_LOCAL_MACHINE\\SOFTWARE\\Policies\\Microsoft\\Windows Defender\\Spynet" /v SubmitSamplesConsent /t REG_DWORD /d 2 /f',
            'reg add "HKEY_LOCAL_MACHINE\\SOFTWARE\\Policies\\Microsoft\\Windows Defender\\Spynet" /v SpynetReporting /t REG_DWORD /d 0 /f',
            
            # Tamper Protection и дополнительные настройки
            'reg add "HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Windows Defender\\Features" /v TamperProtection /t REG_DWORD /d 0 /f',
            'reg add "HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Windows Defender" /v ServiceStartStates /t REG_DWORD /d 1 /f',
            'reg add "HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Windows Defender" /v DisableAntiSpyware /t REG_DWORD /d 1 /f',
            'reg add "HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Windows Defender" /v DisableAntiVirus /t REG_DWORD /d 1 /f',
        ]
        
        success_count = 0
        total = len(commands)
        
        self._set_status("Отключение Windows Defender...")
        log("Начинаем отключение Windows Defender", "INFO")
        
        for i, cmd in enumerate(commands):
            self._set_status(f"Применение настроек... ({i+1}/{total})")
            if self._run_reg_command(cmd):
                success_count += 1
                
        # Пытаемся остановить службу
        self._set_status("Остановка службы Windows Defender...")
        stop_result = subprocess.run('sc stop WinDefend', shell=True, capture_output=True, text=True)
        if stop_result.returncode == 0:
            log("✅ Служба WinDefend остановлена", "INFO")
        else:
            log(f"⚠️ Не удалось остановить службу WinDefend: {stop_result.stderr or 'Служба уже остановлена'}", "WARNING")
        
        # Отключаем автозапуск службы
        disable_result = subprocess.run('sc config WinDefend start=disabled', shell=True, capture_output=True, text=True)
        if disable_result.returncode == 0:
            log("✅ Автозапуск службы WinDefend отключен", "INFO")
        else:
            log(f"⚠️ Не удалось отключить автозапуск WinDefend: {disable_result.stderr}", "WARNING")
        
        success = success_count > 0
        if success:
            log(f"Windows Defender отключен: {success_count}/{total} команд выполнено успешно", "✅ INFO")
        else:
            log("Не удалось отключить Windows Defender", "❌ ERROR")
            
        return success, success_count
    
    def enable_defender(self) -> Tuple[bool, int]:
        """
        Включает Windows Defender обратно
        Возвращает (успех, количество успешных команд)
        """
        # Удаляем ключи реестра для включения Defender
        commands = [
            'reg delete "HKEY_LOCAL_MACHINE\\SOFTWARE\\Policies\\Microsoft\\Windows Defender" /f',
            'reg delete "HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Windows Defender" /v DisableAntiSpyware /f',
            'reg delete "HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Windows Defender" /v DisableAntiVirus /f',
            'reg delete "HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Windows Defender" /v ServiceStartStates /f',
        ]
        
        success_count = 0
        total = len(commands)
        
        self._set_status("Включение Windows Defender...")
        log("Начинаем включение Windows Defender", "INFO")
        
        for i, cmd in enumerate(commands):
            self._set_status(f"Восстановление настроек... ({i+1}/{total})")
            # Игнорируем ошибки удаления (ключ может не существовать)
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                success_count += 1
                
        # Включаем автозапуск службы
        enable_result = subprocess.run('sc config WinDefend start=auto', shell=True, capture_output=True, text=True)
        if enable_result.returncode == 0:
            success_count += 1
            log("✅ Автозапуск службы WinDefend включен", "INFO")
        else:
            log(f"⚠️ Не удалось включить автозапуск WinDefend: {enable_result.stderr}", "WARNING")
            
        # Запускаем службу
        self._set_status("Запуск службы Windows Defender...")
        start_result = subprocess.run('sc start WinDefend', shell=True, capture_output=True, text=True)
        if start_result.returncode == 0:
            success_count += 1
            log("✅ Служба WinDefend запущена", "INFO")
        else:
            log(f"⚠️ Не удалось запустить службу WinDefend: {start_result.stderr or 'Возможно, требуется перезагрузка'}", "WARNING")
            
        success = success_count > 0
        if success:
            log(f"Windows Defender включен: {success_count} операций выполнено", "✅ INFO")
        else:
            log("Не удалось включить Windows Defender", "❌ ERROR")
            
        return success, success_count
    
    def get_defender_status(self) -> str:
        """Получает текущий статус Windows Defender"""
        try:
            # Проверяем состояние службы
            result = subprocess.run('sc query WinDefend', shell=True, capture_output=True, text=True)
            if "RUNNING" in result.stdout:
                return "Служба запущена"
            elif "STOPPED" in result.stdout:
                return "Служба остановлена"
            else:
                return "Неизвестно"
        except Exception as e:
            log(f"Ошибка при проверке статуса службы: {e}", "❌ ERROR")
            return "Ошибка проверки"
