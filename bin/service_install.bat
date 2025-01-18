@echo off

:: Проверьте, что имя службы передано как аргумент
if "%~1"=="" (
    echo Пожалуйста, укажите имя службы.
    exit /b 1
)

:: Имя службы
set SERVICE_NAME=%1
set ARGS=%2

:: Остановка и удаление существующей службы (если есть)
net stop %SERVICE_NAME% >nul 2>&1
sc delete %SERVICE_NAME% >nul 2>&1

:: Создание новой службы
sc create %SERVICE_NAME% binPath= "\"%~dp0winws.exe\" %ARGS%" DisplayName= "zapret DPI bypass : %SERVICE_NAME%" start= auto
if %errorlevel% neq 0 (
    echo Ошибка при создании службы.
    exit /b 1
)

:: Установка описания службы
sc description %SERVICE_NAME% "zapret DPI bypass software"

:: Запуск службы
sc start %SERVICE_NAME%
if %errorlevel% neq 0 (
    echo Ошибка при запуске службы.
    exit /b 1
)

echo Служба %SERVICE_NAME% успешно создана и запущена.
