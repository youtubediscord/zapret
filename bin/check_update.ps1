# Устанавливаем кодовую страницу UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Test-Administrator {
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object System.Security.Principal.WindowsPrincipal($identity)
    $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (!(Test-Administrator)) {
    Write-Host "Requesting administrator rights..."
    Start-Process powershell.exe -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$PSCommandPath`"" -Verb RunAs
    exit
}

# URL файла с актуальной версией
$versionUrl = "https://filedn.eu/lFS6h5cBEsru02lgr5VwkTJ/Zapret/version.txt"

# Загружаем актуальную версию с сервера
$latestVersion = (Invoke-WebRequest -Uri $versionUrl -UseBasicParsin).Content.Trim()
        
# URL для скачивания
$url = "https://filedn.eu/lFS6h5cBEsru02lgr5VwkTJ/Zapret/zapret$latestVersion.zip"

# Имя файла архива
$zipFileName = "zapret$latestVersion.zip"
# Папка, где находится скрипт
$scriptDirectory = Join-Path -Path $PSScriptRoot -ChildPath "..\.."
# Имя папки для распаковки
$destinationFolderName = "zapret"
# Полный путь к папке для распаковки
$destinationFolderPath = Join-Path -Path $scriptDirectory -ChildPath $destinationFolderName

# Полный путь к архиву
$zipFilePath = Join-Path -Path $scriptDirectory -ChildPath $zipFileName

# Создание папки для распаковки, если она не существует
if (!(Test-Path -Path $destinationFolderPath)) {
    Write-Host "Создание папки $destinationFolderPath..."
    try {
        New-Item -ItemType Directory -Path $destinationFolderPath
    }
    catch {
        Write-Error "Ошибка при создании папки: $($_.Exception.Message)"
        Exit 1
    }
}

# Скачивание архива
Write-Host "Скачивание $url в $scriptDirectory..."
try {
    Invoke-WebRequest -Uri $url -OutFile $zipFilePath -UseBasicParsing
}
catch {
    Write-Error "Ошибка при скачивании: $($_.Exception.Message)"
    Exit 1
}

# Распаковка архива
Write-Host "Распаковка архива в $destinationFolderPath..."
try {
    Expand-Archive -Path $zipFilePath -DestinationPath $destinationFolderPath -Force
}
catch {
    Write-Error "Ошибка при распаковке: $($_.Exception.Message)"
    Exit 1
}

# Очистка (удаление архива)
Write-Host "Удаление архива $zipFilePath..."
try {
    Remove-Item -Path $zipFilePath
}
catch {
    Write-Warning "Не удалось удалить архив: $($_.Exception.Message)"
}

Write-Host "Готово!"
pause