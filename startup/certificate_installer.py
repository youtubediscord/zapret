# startup/certificate_installer.py
"""
Автоматическая установка самоподписанного сертификата в доверенные.

При первом запуске приложения проверяет наличие сертификата,
и если его нет - устанавливает автоматически без участия пользователя.
"""

from __future__ import annotations
import subprocess
import tempfile
from pathlib import Path
import winreg


# ✅ Встроенный сертификат в BASE64 (будет заполнен при сборке)
EMBEDDED_CERTIFICATE = "MIIDODCCAiCgAwIBAgIQKO7yJghue4VLVPwCiOZQRTANBgkqhkiG9w0BAQsFADA0MRcwFQYDVQQKDA5aYXByZXQgUHJvamVjdDEZMBcGA1UEAwwQWmFwcmV0IERldmVsb3BlcjAeFw0yNTEyMDkxNDM3MjdaFw0zNTEyMDkxNDQ3MjdaMDQxFzAVBgNVBAoMDlphcHJldCBQcm9qZWN0MRkwFwYDVQQDDBBaYXByZXQgRGV2ZWxvcGVyMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAwcJg+5dJtIm1K1C8ejE0IL0h5CtunrAPaGldYzdgRLrISNb6a/mCzVJJcfh89HAnknQNJVcEbbx3K7d57cDjJRwa3l3eUufC1FaYjaysDx4Bw5sFV08onM2UGg2tMVnTNpmuxDcL2Kgn3S412AUhsAk7WMHE7n/s1SSJ7Bb7q3EbSG1NGvPRYcRCEA3F0JFYT0+dtUDmMN8jfuhSjKlQmdLygQSIQKEcjKRTYMn4xdfFbDYHYRRA0skNAmHufMkZoJwr8wK/RtaM9xgNJBYHw8BIbi4Y6EV4IBSpxsINzKUlB7Djz7O/5zSpkZbkmxkI5HZEW++x9Wx6HfvJbqPOBQIDAQABo0YwRDAOBgNVHQ8BAf8EBAMCB4AwEwYDVR0lBAwwCgYIKwYBBQUHAwMwHQYDVR0OBBYEFFOFnIoBnLcsiP1REc8xrpkg7AU4MA0GCSqGSIb3DQEBCwUAA4IBAQBm8r2HgCWa/MEbj8w2ZdEjFc9m+GSVVmdCMasykrwvRi2t9kEA7Po3VZSBrYtA3G3VFZSA5P3Xp8hRNmwKTrpRVtXe+VyWl47cZBMplBXVnCuIvsuGey125xcjSqztB5To6Lpn+0YtHq2zzzYEbpMsbl4fI8zSGEqjWNX7aydW83aZNzTQlkekaEcdbGdrd/aHf/uER4J0mz6nhPrzIkg0tggQmUej6o+gFGfPHFyvwfnvacLpz6xbWXXM9p6lY/NsUdRX01e565jj0icEslAY2/tGPLbpNhg7gXn8YuZ60jkACWGK85YY0KHpdDClPPfkyK+l2FLOxTeCmOsWW1kn"

# ✅ Константы для работы с реестром
REGISTRY_KEY = r"Software\Zapret"
CERTIFICATE_DECLINED_VALUE = "CertificateInstallDeclined"


def is_certificate_install_declined() -> bool:
    """
    Проверяет, отказался ли пользователь от установки сертификата ранее.

    Returns:
        bool: True если пользователь отказался от установки
    """
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_KEY, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, CERTIFICATE_DECLINED_VALUE)
            return bool(value)
    except (FileNotFoundError, OSError):
        # Ключ или значение не существует - значит пользователь еще не отказывался
        return False


def set_certificate_install_declined(declined: bool = True) -> bool:
    """
    Сохраняет в реестр флаг отказа от установки сертификата.

    Args:
        declined: True - пользователь отказался, False - сбросить флаг

    Returns:
        bool: True если успешно сохранено
    """
    try:
        key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, REGISTRY_KEY, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, CERTIFICATE_DECLINED_VALUE, 0, winreg.REG_DWORD, int(declined))
        winreg.CloseKey(key)
        return True
    except Exception:
        return False


def reset_certificate_declined_flag() -> bool:
    """
    Сбрасывает флаг отказа от установки сертификата.
    После вызова этой функции при следующем запуске приложение
    снова попытается установить сертификат.

    Returns:
        bool: True если флаг успешно сброшен
    """
    return set_certificate_install_declined(False)


def is_certificate_installed(thumbprint: str) -> bool:
    """
    Проверяет, установлен ли сертификат в доверенных.
    
    Args:
        thumbprint: Thumbprint сертификата для проверки
        
    Returns:
        bool: True если сертификат установлен
    """
    try:
        ps_script = f"""
$cert = Get-ChildItem -Path Cert:\\CurrentUser\\Root -Recurse | 
    Where-Object {{ $_.Thumbprint -eq '{thumbprint}' }}
if ($cert) {{ Write-Output 'INSTALLED' }} else {{ Write-Output 'NOT_FOUND' }}
"""
        
        result = subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        return "INSTALLED" in result.stdout
        
    except Exception:
        return False


def install_certificate_silently(cert_data: bytes) -> bool:
    """
    Устанавливает сертификат в доверенные автоматически БЕЗ ДИАЛОГОВ.
    
    Args:
        cert_data: Данные сертификата в формате DER/CER
        
    Returns:
        bool: True если успешно установлен
    """
    try:
        # Создаем временный файл
        with tempfile.NamedTemporaryFile(suffix='.cer', delete=False) as tmp:
            tmp.write(cert_data)
            tmp_path = tmp.name
        
        tmp_file = Path(tmp_path)
        
        try:
            # ✅ Метод 1: certutil - полностью тихая установка
            result = subprocess.run(
                ["certutil", "-user", "-addstore", "Root", str(tmp_file)],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if result.returncode == 0:
                return True
            
            # ✅ Метод 2: PowerShell с обходом диалога (через реестр)
            ps_script = f"""
# Временно отключаем предупреждение о сертификатах
$regPath = 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\WinTrust\\Trust Providers\\Software Publishing'
$oldValue = $null
try {{
    $oldValue = Get-ItemProperty -Path $regPath -Name 'State' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty State
    Set-ItemProperty -Path $regPath -Name 'State' -Value 0x23c00 -Force
}} catch {{}}

# Устанавливаем сертификат
$cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2("{tmp_file}")
$store = New-Object System.Security.Cryptography.X509Certificates.X509Store("Root","CurrentUser")
$store.Open("ReadWrite")
$store.Add($cert)
$store.Close()

# Восстанавливаем настройку
if ($oldValue -ne $null) {{
    Set-ItemProperty -Path $regPath -Name 'State' -Value $oldValue -Force
}}

Write-Output 'SUCCESS'
"""
            
            result = subprocess.run(
                ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            return "SUCCESS" in result.stdout
            
        finally:
            # Удаляем временный файл
            try:
                tmp_file.unlink()
            except:
                pass
                
    except Exception:
        return False


def get_embedded_certificate() -> bytes | None:
    """
    Получает встроенный сертификат из base64.
    
    Returns:
        bytes: Данные сертификата или None
    """
    if not EMBEDDED_CERTIFICATE:
        return None
    
    try:
        import base64
        return base64.b64decode(EMBEDDED_CERTIFICATE)
    except Exception:
        return None


def try_install_from_file(cert_file: Path) -> bool:
    """
    Пытается установить сертификат из файла рядом с exe.
    
    Args:
        cert_file: Путь к .cer файлу
        
    Returns:
        bool: True если успешно установлен
    """
    if not cert_file.exists():
        return False
    
    try:
        cert_data = cert_file.read_bytes()
        return install_certificate_silently(cert_data)
    except Exception:
        return False


def auto_install_certificate(
    thumbprint: str = "F507DDA6CB772F4332ECC2C5686623F39D9DA450",
    silent: bool = True
) -> tuple[bool, str]:
    """
    Автоматически устанавливает сертификат если его нет.
    
    Args:
        thumbprint: Thumbprint ожидаемого сертификата
        silent: Не показывать сообщения (работать тихо)
        
    Returns:
        tuple[bool, str]: (успешно, сообщение)
    """
    
    # Проверяем, уже установлен ли сертификат
    if is_certificate_installed(thumbprint):
        return True, "Сертификат уже установлен"
    
    # Вариант 1: Попробовать встроенный сертификат
    cert_data = get_embedded_certificate()
    if cert_data:
        if install_certificate_silently(cert_data):
            return True, "Сертификат автоматически установлен (встроенный)"
    
    # Вариант 2: Попробовать встроенный файл в PyInstaller (_MEIPASS)
    import sys
    import os
    
    # Проверяем _MEIPASS (временная папка PyInstaller)
    if hasattr(sys, '_MEIPASS'):
        cert_file = Path(sys._MEIPASS) / "zapret_certificate.cer"
        if try_install_from_file(cert_file):
            return True, "Сертификат автоматически установлен (встроенный файл)"
    
    # Проверяем рядом с exe
    if getattr(sys, 'frozen', False):
        app_dir = Path(os.path.dirname(sys.executable))
    else:
        app_dir = Path(__file__).parent.parent
    
    cert_file = app_dir / "zapret_certificate.cer"
    if try_install_from_file(cert_file):
        return True, "Сертификат автоматически установлен (из файла рядом с exe)"
    
    # Вариант 3: Проверить папку установки
    install_dirs = [
        Path(r"C:\ProgramData\ZapretTwo"),
        Path(r"C:\ProgramData\ZapretTwoDev"),
    ]
    
    for install_dir in install_dirs:
        cert_file = install_dir / "zapret_certificate.cer"
        if try_install_from_file(cert_file):
            return True, "Сертификат автоматически установлен (из папки установки)"
    
    # Не удалось установить
    return False, "Не удалось установить сертификат автоматически"


def check_and_install_on_startup() -> None:
    """
    Проверяет и устанавливает сертификат при старте приложения.
    Вызывается из main.py перед созданием GUI.

    Если пользователь ранее отказался от установки сертификата,
    проверка и установка не выполняются.
    """
    try:
        # ✅ Проверяем, отказался ли пользователь ранее от установки
        if is_certificate_install_declined():
            try:
                from log import log
                log("🔐 Установка сертификата пропущена (пользователь ранее отказался)", "CERT")
            except ImportError:
                pass
            return

        # Пытаемся установить сертификат
        success, message = auto_install_certificate(silent=True)

        # Логируем результат (если log модуль доступен)
        try:
            from log import log
            if success:
                log(f"✅ {message}", "CERT")
            else:
                # ✅ Если установка не удалась - сохраняем флаг отказа
                log(f"⚠️ {message}", "CERT")
                set_certificate_install_declined(True)
                log("🔐 Установка сертификата отключена. Для повторной попытки удалите ключ реестра HKCU\\Software\\Zapret\\CertificateInstallDeclined", "CERT")
        except ImportError:
            # Если логирование недоступно, все равно сохраняем флаг при неудаче
            if not success:
                set_certificate_install_declined(True)

    except Exception as e:
        try:
            from log import log
            log(f"Ошибка установки сертификата: {e}", "❌ CERT")
            # При ошибке также сохраняем флаг отказа
            set_certificate_install_declined(True)
        except ImportError:
            set_certificate_install_declined(True)


if __name__ == "__main__":
    # Тест установки сертификата
    print("🔐 Проверка и установка сертификата...\n")

    # Проверяем флаг отказа
    if is_certificate_install_declined():
        print("⚠️  Флаг отказа установлен в реестре!")
        print("   Для повторной попытки используйте: reset_certificate_declined_flag()")

        reset = input("\nСбросить флаг и попробовать снова? (y/n): ")
        if reset.lower() == 'y':
            reset_certificate_declined_flag()
            print("✅ Флаг сброшен!\n")
        else:
            print("Установка пропущена.")
            exit(0)

    success, message = auto_install_certificate(silent=False)

    print(f"\n{'✅' if success else '❌'} {message}")

    if success:
        print("\n🎉 Сертификат установлен! Windows будет доверять приложению.")
    else:
        print("\n⚠️ Установка не удалась.")
        print("   Флаг отказа будет сохранен в реестре.")
        print("   При следующих запусках приложение не будет пытаться установить сертификат.")
        print("\nДля повторной попытки:")
        print("   1. Удалите ключ реестра: HKCU\\Software\\Zapret\\CertificateInstallDeclined")
        print("   2. Или используйте функцию: reset_certificate_declined_flag()")

