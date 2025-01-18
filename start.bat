@echo off
chcp 65001 > nul

set "currentDir=%~dp0"
set "tempDir=%TEMP%"
set "tempDir=%tempDir:~0,-1%"

echo "Проверка текущего пути..."
echo %currentDir%

echo %currentDir% | findstr /i /b "%tempDir%" >nul

if %errorlevel%==0 (
    echo "Скрипт запущен из временной папки: %tempDir%"
    echo "РАЗАРХИВИРУЙТЕ (ВЫТАЩИТЕ ИЗ ZIP АРХИВА) ВСЮ ПРОГРАММУ И СОЗДАЙТЕ НОВУЮ ПАПКУ!"
    pause
)

echo "Скрипт не находится в временной папке. Продолжаем выполнение..."

%WINDIR%\System32\WindowsPowerShell\v1.0\powershell.exe Set-ExecutionPolicy Unrestricted -Scope CurrentUser
%WINDIR%\System32\WindowsPowerShell\v1.0\powershell.exe -ExecutionPolicy Bypass -File "%~dp0core.ps1"