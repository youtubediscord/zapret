function DownloadDLLFile {
    $WinDivertDll = "WinDivert.dll"
    $WinDivert64Sys = "WinDivert64.sys"
    $exeName = "winws.exe"
    $cygwin1 = "cygwin1.dll"

    $WinDivertDLLURL = "https://github.com/bol-van/zapret-win-bundle/raw/refs/heads/master/zapret-winws/WinDivert.dll"
    $WinDivert64SysURL = "https://github.com/bol-van/zapret-win-bundle/raw/refs/heads/master/zapret-winws/WinDivert64.sys"
    $exeRawUrl = "https://github.com/bol-van/zapret-win-bundle/raw/refs/heads/master/zapret-winws/winws.exe"
    $cygwin1Url = "https://github.com/bol-van/zapret-win-bundle/raw/refs/heads/master/zapret-winws/cygwin1.dll"

    # Проверяем наличие папки bin
    if (-not (Test-Path -Path $BIN)) {
        Write-Host "Папка bin не найдена. Создаю..."
        New-Item -ItemType Directory -Path $BIN | Out-Null
    }

    $WinDivertDllPATH = Join-Path -Path $BIN -ChildPath $WinDivertDll
    if (-not (Test-Path -Path $WinDivertDllPATH)) {
        Write-Host "Драйвер $WinDivertDll не найден. Скачиваю..."
        try {
            Start-Sleep -Seconds 3
            Invoke-WebRequest -Uri $WinDivertDLLURL -OutFile $WinDivertDllPATH
            Write-Host "Драйвер $WinDivertDll успешно скачан."
        } catch {
            Write-Error "Ошибка при скачивании драйвера: $_"
            return
        }
    } else {
    }

    $WinDivert64SysPATH = Join-Path -Path $BIN -ChildPath $WinDivert64Sys
    if (-not (Test-Path -Path $WinDivert64SysPATH)) {
        Write-Host "Драйвер $WinDivert64Sys не найден. Скачиваю..."
        try {
            Start-Sleep -Seconds 3
            Invoke-WebRequest -Uri $WinDivert64SysURL -OutFile $WinDivert64SysPATH
            Write-Host "Драйвер $WinDivert64Sys успешно скачан."
        } catch {
            Write-Error "Ошибка при скачивании драйвера: $_"
            return
        }
    } else {
    }

    $exePath = Join-Path -Path $BIN -ChildPath $exeName
    if (-not (Test-Path -Path $exePath)) {
        Write-Host "Исполняемый файл $exeName не найден. Скачиваю..."
        try {
            Start-Sleep -Seconds 3
            Invoke-WebRequest -Uri $exeRawUrl -OutFile $exePath
            Write-Host "Исполняемый файл $exeName успешно скачан."
        } catch {
            Write-Error "Ошибка при скачивании исполняемого файла: $_"
            return # Прерываем выполнение функции в случае ошибки
        }
    } else {
    }

    $cygwin1Path = Join-Path -Path $BIN -ChildPath $cygwin1
    if (-not (Test-Path -Path $cygwin1Path)) {
        Write-Host "Исполняемый файл $cygwin1 не найден. Скачиваю..."
        try {
            Start-Sleep -Seconds 3
            Invoke-WebRequest -Uri $cygwin1Url -OutFile $cygwin1Path
            Write-Host "Исполняемый файл $cygwin1 успешно скачан."
        } catch {
            Write-Error "Ошибка при скачивании исполняемого файла: $_"
            return # Прерываем выполнение функции в случае ошибки
        }
    } else {
    }

}

# Устанавливаем кодовую страницу UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Устанавливаем синий цвет фона (не работает в PowerShell 7+)
if ($PSVersionTable.PSVersion.Major -lt 6) {
    $Host.UI.RawUI.BackgroundColor = "DarkBlue"
    Clear-Host
}

function ShowTitle {
    Write-Host "██████████████████████████████████████████████████████████████████"
    Write-Host ""
    Write-Host "███████      ██████      ██████     ██████       ███████    ███████"
    Write-Host "    ███     ██    ██     ██    ██   ██    ██     ██           ███"
    Write-Host "   ███      ████████     ██████     ██████       ███████      ███"
    Write-Host "  ███       ██    ██     ██         ██   ██      ██           ███"
    Write-Host " ██████     ██    ██     ██         ██    ██     ███████      ███"
    Write-Host ""
    Write-Host "██████████████████████████████████████████████████████████████████"
    Write-Host ""
}

$BIN = "$PSScriptRoot\bin\"
$LISTS = "$PSScriptRoot\lists\"

function Test-Administrator {
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object System.Security.Principal.WindowsPrincipal($identity)
    $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Show-Telegram {
    $regKey = "HKCU:\Software\Zapret"
    $regValue = "TelegramOpened"

    if ((Get-ItemProperty -Path $regKey -Name $regValue -ErrorAction SilentlyContinue).$regValue -eq 1) {
        Write-Host "Присоединяйтесь к нашему каналу Telegram (для обновлений) https://t.me/bypassblock"
    } else {
        Write-Host "Присоединяйтесь к нашему каналу Telegram"
        Start-Process https://t.me/bypassblock
        New-Item -Path $regKey -Force | Out-Null
        New-ItemProperty -Path $regKey -Name $regValue -Value 1 -PropertyType DWORD -Force | Out-Null
    }
}

function ShowTelegram {
    Clear-Host
    ShowTitle
    Start-Process https://t.me/bypassblock
}

function StartZapret {
    param(
        [string]$StrategyName,
        [string]$Arguments
    )

    # Добавление проверки существования файла winws.exe
    if (-Not (Test-Path -Path "$BIN\winws.exe")) {
        Write-Error "Файл winws.exe не найден по пути: $BIN\winws.exe"
        return
    }

    # Попытка запуска процесса
    try {
        $process = Start-Process -FilePath "$BIN\winws.exe" -ArgumentList $Arguments -WindowStyle Hidden -PassThru -WorkingDirectory $PSScriptRoot
        # Проверка успешности запуска
        if ($process -eq $null) {
            Write-Error "Не удалось запустить winws.exe с аргументами: $Arguments"
            return
        }

        # Сохранение PID запущенного процесса
        "Process ID: $($process.Id) | $localVersion `nСтратегия: $($StrategyName) `nАргументы: $($Arguments -join ' ') `nВремя запуска: $($process.StartTime)" | Out-File -FilePath "$PSScriptRoot\log.txt" -Encoding UTF8 -Append
        Write-Host "Стратегия '$StrategyName' успешно загружена!" -ForegroundColor Green
    }
    catch {
        Write-Error "Ошибка при запуске winws.exe: $_"
    }
}

function StopZapret {
    $zapretProcess = Get-Process winws -ErrorAction SilentlyContinue
    if ($zapretProcess) {
        Stop-Process -Force -Name winws
        Stop-Service -Name "Zapret" -Force -ErrorAction SilentlyContinue
        sc.exe delete "Zapret" > $null 2>&1
    } else {
        Write-Host "Попытка запуска стратегии..."
    }

    $goodbyeDpiProcess = Get-Process goodbyedpi -ErrorAction SilentlyContinue
    if ($goodbyeDpiProcess) {
        Write-Host "ГУДБАЙДИПИАЙ НЕ РАБОТАЕТ С ZAPRET!!!"
        Stop-Process -Force -Name winws
        Stop-Service -Name "GoodbyeDPI" -Force -ErrorAction SilentlyContinue
        sc.exe delete "GoodbyeDPI" > $null 2>&1
        Remove-Item -Path "HKLM:\SYSTEM\CurrentControlSet\Services\GoodbyeDPI" -Recurse -Force -ErrorAction SilentlyContinue
    }

    try {
        Stop-Service -Name "WinDivert" -Force -ErrorAction SilentlyContinue
    } catch {
        Write-Host "Служба WinDivert была успешно остановлена."
    }

    try {
        sc.exe delete "WinDivert" > $null 2>&1
    } catch {
        Write-Host "Служба WinDivert была успешно удалена."
    }

    try {
        Stop-Service -Name "WinDivert14" -Force -ErrorAction SilentlyContinue
    } catch {
        Write-Host "Служба WinDivert была успешно остановлена."
    }

    try {
        sc.exe delete "WinDivert14" > $null 2>&1
    } catch {
        Write-Host "Служба WinDivert была успешно удалена."
    }

    Remove-Item -Path "HKLM:\SYSTEM\CurrentControlSet\Services\WinDivert" -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -Path "HKLM:\SYSTEM\CurrentControlSet\Services\WinDivert14" -Recurse -Force -ErrorAction SilentlyContinue
}

function OpenLogFile {
    Clear-Host
    ShowTitle
    $logFilePath = Join-Path -Path $PSScriptRoot -ChildPath "log.txt"
    if (Test-Path -Path $logFilePath) {
        Invoke-Item -Path $logFilePath
    } else {
        Write-Warning "Лог файл '$logFilePath' не найден."
    }
}

function Set-CustomDNS {
    param(
        [string]$DNSType = "default", # Тип DNS: Google, Zapret, Custom (по умолчанию)
        [string]$PrimaryDNS = "",      # Первичный DNS сервер (используется только если DNSType = "Custom")
        [string]$SecondaryDNS = ""    # Вторичный DNS сервер (используется только если DNSType = "Custom")
    )

    switch ($DNSType) {
        "Google" {
            $PrimaryDNS = "8.8.8.8"
            $SecondaryDNS = "8.8.4.4"
        }
        "DnsSB" {
            $PrimaryDNS = "185.222.222.222"
            $SecondaryDNS = "45.11.45.11"
        }
        "Custom" {
            if (-not $PrimaryDNS -or -not $SecondaryDNS) {
                Write-Warning "Для типа 'Custom' необходимо указать PrimaryDNS и SecondaryDNS параметры."
                return
            }
        }
        default {
            Write-Warning "Неизвестный тип DNS: '$DNSType'!"
        }
    }

    Write-Host "Изменение DNS на '$DNSType' DNS для активных интерфейсов..."

    # Получаем список активных сетевых интерфейсов
    try {
        $interfaces = Get-NetAdapter | Where-Object {$_.Status -eq "Up"} -ErrorAction Stop
    } catch {
        Write-Error "Ошибка при получении списка сетевых интерфейсов: $_"
        return
    }

    # Проверяем, найдены ли активные интерфейсы
    if ($interfaces.Count -eq 0) {
        Write-Warning "Не найдено активных сетевых интерфейсов."
        return
    }

    # Устанавливаем DNS-серверы для каждого интерфейса
    foreach ($interface in $interfaces) {
        try {
            Write-Host "Установка DNS для интерфейса $($interface.InterfaceAlias)..."
            Set-DnsClientServerAddress -InterfaceAlias $interface.InterfaceAlias -ServerAddresses ($primaryDNS, $secondaryDNS) -ErrorAction Stop
            Write-Host "DNS для интерфейса $($interface.InterfaceAlias) успешно установлен."
        } catch {
            Write-Error "Ошибка при установке DNS для интерфейса $($interface.InterfaceAlias): $_"
        }
    }

    # Очищаем кэш DNS
    Write-Host "Очистка кэша DNS..."
    ipconfig /flushdns | Out-Null
    Write-Host "Кэш DNS успешно очищен."
}

function Reset-DNS {
    Write-Host "Сброс DNS для активных интерфейсов на значения по умолчанию..."

    try {
        $interfaces = Get-NetAdapter | Where-Object {$_.Status -eq "Up"} -ErrorAction Stop
    } catch {
        Write-Error "Ошибка при получении списка сетевых интерфейсов: $_"
        return
    }

    if ($interfaces.Count -eq 0) {
        Write-Warning "Не найдено активных сетевых интерфейсов."
        return
    }

    foreach ($interface in $interfaces) {
        try {
            Write-Host "Сброс DNS для интерфейса $($interface.InterfaceAlias)..."
            Set-DnsClientServerAddress -InterfaceAlias $interface.InterfaceAlias -ResetServerAddresses -ErrorAction Stop
            Write-Host "DNS для интерфейса $($interface.InterfaceAlias) успешно сброшен."
        } catch {
            Write-Error "Ошибка при сбросе DNS для интерфейса $($interface.InterfaceAlias): $_"
        }
    }

    # Очищаем кэш DNS
    Write-Host "Очистка кэша DNS..."
    ipconfig /flushdns | Out-Null
    Write-Host "Кэш DNS успешно очищен."
}

function Edit-Hosts {
    param(
        [string]$ContentName = "Default" # Default value if no ContentName is provided
    )

    $hostsPath = "$env:SystemRoot\System32\drivers\etc\hosts"
    $tempHostsPath = "$env:TEMP\hosts_temp.txt"
    $addHostsContent = @() # Initialize as empty array

    switch ($ContentName) {
        "ChatGPT-Gemini" {
            $addHostsContent = @(
                "50.7.85.220 chatgpt.com"
                "50.7.85.220 ab.chatgpt.com"
                "50.7.85.220 auth.openai.com"
                "50.7.85.220 auth0.openai.com"
                "50.7.85.220 platform.openai.com"
                "50.7.85.220 cdn.oaistatic.com"
                "50.7.85.220 files.oaiusercontent.com"
                "50.7.85.220 cdn.auth0.com"
                "50.7.85.220 tcr9i.chat.openai.com"
                "50.7.85.220 webrtc.chatgpt.com"
                "50.7.85.220 android.chat.openai.com"
                "50.7.85.220 api.openai.com"
                "50.7.85.220 gemini.google.com"
                "50.7.85.220 aistudio.google.com"
                "50.7.85.220 generativelanguage.googleapis.com"
                "50.7.85.220 alkalimakersuite-pa.clients6.google.com"
                "50.7.85.220 copilot.microsoft.com"
                "50.7.85.220 www.bing.com"
                "50.7.85.220 sydney.bing.com"
                "50.7.85.220 edgeservices.bing.com"
                "50.7.85.220 claude.ai"
                "50.7.85.220 aitestkitchen.withgoogle.com"
                "50.7.85.220 aisandbox-pa.googleapis.com"
                "50.7.85.220 o.pki.goog"
                "50.7.85.220 labs.google"
                "50.7.85.220 notebooklm.google"
                "50.7.85.220 notebooklm.google.com"
                "50.7.85.220 webchannel-alkalimakersuite-pa.clients6.google.com"
                "50.7.85.220 api.spotify.com"
                "50.7.85.220 xpui.app.spotify.com"
                "50.7.85.220 appresolve.spotify.com"
                "50.7.85.220 login5.spotify.com"
                "50.7.85.220 gew1-spclient.spotify.com"
                "50.7.85.220 gew1-dealer.spotify.com"
                "50.7.85.220 spclient.wg.spotify.com"
                "50.7.85.220 api-partner.spotify.com"
                "50.7.85.220 aet.spotify.com"
                "50.7.85.220 www.spotify.com"
                "50.7.85.220 accounts.spotify.com"
                "50.7.85.220 www.notion.so"
                "50.7.85.222 www.canva.com"
                "204.12.192.222 www.intel.com"
                "204.12.192.219 www.dell.com"
                "50.7.87.85 codeium.com"
                "50.7.85.219 inference.codeium.com"
                "107.150.34.101 plugins.jetbrains.com"
                "50.7.85.219 www.tiktok.com"
                "50.7.87.84 api.github.com"
                "50.7.85.221 api.individual.githubcopilot.com"
                "50.7.87.83 proxy.individual.githubcopilot.com"
                "94.131.119.85 autodesk.com"
                "94.131.119.85 accounts.autodesk.com"
            )
        }
        "Facebook" {
            $addHostsContent = @(
                "0.0.0.0 www.aomeitech.com"
                #"185.15.211.203 bt.t-ru.org",
                #"185.15.211.203 bt2.t-ru.org",
                #"185.15.211.203 bt3.t-ru.org",
                #"185.15.211.203 bt4.t-ru.org",
                "3.66.189.153 mail.proton.me",
                "3.73.85.131 mail.proton.me",
                "31.13.72.36 facebook.com",
                "31.13.72.36 www.facebook.com",
                "31.13.72.12 static.xx.fbcdn.net",
                "31.13.72.12 external-hel3-1.xx.fbcdn.net",
                "157.240.225.174 www.instagram.com",
                "157.240.225.174 instagram.com",
                "157.240.247.63 scontent.cdninstagram.com",
                "157.240.247.63 scontent-hel3-1.cdninstagram.com"
            )
        }
        default {
            Write-Warning "Неизвестный тип контента для hosts!"
        }
    }

    # 1. Прочитать существующее содержимое файла (с обработкой отсутствия файла).
    try {
        $existingContent = Get-Content -Path $hostsPath -Raw -ErrorAction Stop
    }
    catch {
        if ($_.Exception -is [System.IO.FileNotFoundException]) {
            Write-Warning "Файл hosts не найден. Будет создан новый."
            $existingContent = ""
        }
        else {
            Write-Warning "Ошибка при чтении файла hosts: $($_.Exception.Message)"
            return
        }
    }

    # 2. Определить, какие строки нужно добавить.
    $linesToAdd = foreach ($line in $addHostsContent) {
        if ($existingContent -and $existingContent -notmatch [regex]::Escape($line)) {
            $line
        }
        elseif (-not $existingContent) {
            $line
        }
    }

    # 3. Если нет строк для добавления, выходим.
    if (-not $linesToAdd) {
        Write-Host "Все необходимые строки для '$ContentName' hosts уже присутствуют в файле hosts."
        return
    }

    # 4. Добавить только отсутствующие строки НАПРЯМУЮ в файл.
    try {
        # Остановка службы DNS-клиента - закомментировано, так как не всегда нужно и требует админских прав.
        # Write-Host "Остановка службы DNS-клиента..."
        # Stop-Service -Name "Dnscache" -Force -ErrorAction Stop

        # Очистка DNS-кэша
        Write-Host "Очистка кэша DNS..."
        ipconfig /flushdns | Out-Null

        # Добавление новых строк
        Write-Host "Добавление новых строк в файл hosts ('$ContentName')..."
        if ($existingContent) {
          Add-Content -Path $hostsPath -Value ("`n" + ($linesToAdd -join "`n")) -Encoding String -ErrorAction Stop
        } else {
          Add-Content -Path $hostsPath -Value ($linesToAdd -join "`n") -Encoding String -ErrorAction Stop
        }

        Write-Host "Файл hosts успешно обновлён (контент: '$ContentName')."
    }
    catch {
        Write-Warning "Ошибка при обновлении файла hosts: $($_.Exception.Message)"
    }
}

function Write-Log {
    param(
        [string]$LogMessage
    )
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $LogEntry = "[$Timestamp] $LogMessage"
    $LogPath = Join-Path -Path $PSScriptRoot -ChildPath "log.txt" # Прямое использование $PSScriptRoot
    Add-Content -Path $LogPath -Value $LogEntry -Encoding UTF8 -ErrorAction SilentlyContinue # Добавлено -Encoding UTF8
}

function Check-Availability {
    param(
        [string]$Url,
        [string[]]$IPAddresses
    )

    $logHeader = "Проверка доступности для URL: $Url"
    Write-Log $logHeader
    Write-Host $logHeader

    # Check main URL using ping
    $pingResults = Test-Connection -ComputerName $Url -Count 4
    $totalSent = $pingResults.Count
    $totalReceived = ($pingResults | Where-Object {$_.StatusCode -eq 0}).Count  # 0 means success
    $pingSummary = "${Url}: Отправлено: $totalSent, Получено: $totalReceived"
    Write-Log $pingSummary
    Write-Host $pingSummary
    foreach ($result in $pingResults) {
        if ($result.StatusCode -eq 0) {
            $statusMessage = "`tДоступен (Latency: $($result.ResponseTime)ms)"
            Write-Log $statusMessage
            Write-Host $statusMessage
        } else {
            $statusMessage = "`tНедоступен"
            Write-Log $statusMessage
            Write-Host $statusMessage
        }
    }

    # Check IP addresses using ping
    if ($IPAddresses) {
        foreach ($ip in $IPAddresses) {
            $logIPHeader = "Проверка доступности для IP: $ip"
            Write-Log $logIPHeader
            Write-Host $logIPHeader
            $pingResults = Test-Connection -ComputerName $ip -Count 4
            $totalSent = $pingResults.Count
            $totalReceived = ($pingResults | Where-Object {$_.StatusCode -eq 0}).Count
            $pingIPSummary = "IP ${ip}: Отправлено: $totalSent, Получено: $totalReceived"
            Write-Log $pingIPSummary
            Write-Host $pingIPSummary
            foreach ($result in $pingResults) {
                if ($result.StatusCode -eq 0) {
                    $statusMessage = "`tДоступен (Latency: $($result.ResponseTime)ms)"
                    Write-Log $statusMessage
                    Write-Host $statusMessage
                } else {
                    $statusMessage = "`tНедоступен"
                    Write-Log $statusMessage
                    Write-Host $statusMessage
                }
            }
        }
    }
}

function Check-Discord {
    $logDiscordHeader = "Запуск проверки доступности Discord:"
    Write-Log $logDiscordHeader
    Write-Host $logDiscordHeader
    Check-Availability -Url "discord.com"
    Write-Log "" # Empty line for separation in log
    Write-Host ""
    $logDiscordFinished = "Проверка доступности Discord завершена."
    Write-Log $logDiscordFinished
}

function Check-YouTube {
    $youtubeIPs = @(
        "212.188.49.81",
        "74.125.168.135",
        "173.194.140.136",
        "172.217.131.103"
    )

    $youtubeAddresses = @(
        "rr6.sn-jvhnu5g-n8v6.googlevideo.com",
        "rr4---sn-jvhnu5g-c35z.googlevideo.com",
        "rr4---sn-jvhnu5g-n8ve7.googlevideo.com",
        "rr2---sn-aigl6nze.googlevideo.com",
        "rr7---sn-jvhnu5g-c35e.googlevideo.com",
        "rr3---sn-jvhnu5g-c35d.googlevideo.com",
        "rr3---sn-q4fl6n6r.googlevideo.com"
    )

    $logYoutubeHeader = "Запуск проверки доступности YouTube:"
    Write-Log $logYoutubeHeader
    Write-Host $logYoutubeHeader
    Check-Availability -Url "www.youtube.com" -IPAddresses $youtubeIPs

    foreach ($address in $youtubeAddresses) {
        Check-Availability -Url $address
    }
    Write-Log "" # Empty line for separation in log
    Write-Host ""

    # Check https://jnn-pa.googleapis.com using Invoke-WebRequest
    try {
        $response = Invoke-WebRequest -Uri "https://jnn-pa.googleapis.com" -Method GET
        $youtubeApiSuccess = "Запрос https://jnn-pa.googleapis.com успешен: $($response.StatusCode)"
        Write-Log $youtubeApiSuccess
        Write-Output $youtubeApiSuccess
    } catch {
        if ($_.Exception.Response.StatusCode -eq 403) {
            $youtube403Error = "Ошибка 403: ВЫ НЕ СМОЖЕТЕ СМОТРЕТЬ ЮТУБ с помощью сайта youtube.com ЧЕРЕЗ ZAPRET! Вам следует запустить Zapret, а после скачать Freetube по ссылке freetubeapp.io и смотреть видео там. Или скачайте для своего браузера скрипт Tampermonkey по ссылке: https://zapret.now.sh/script.user.js"
            Write-Log $youtube403Error
            Write-Output $youtube403Error
            $choice = Read-Host "Узнать подробнее? (введите цифру 1 если да / введите цифру 0 если нужно выйти)"
            if ($choice -eq "1") {
                $youtubeLearnMore = "Пользователь выбрал 'Узнать подробнее' о разблокировке YouTube."
                Write-Log $youtubeLearnMore
                Write-Host "Пройдите по ссылке, выполните установки и перезайдите в Zapret"
                Start-Sleep -Seconds 5
                Start-Process https://github.com/youtubediscord/youtube_59second
            } elseif ($choice -eq "0") {
                $youtubeCancelScript = "Пользователь отменил установку скрипта для разблокировки YouTube."
                Write-Log $youtubeCancelScript
                Write-Host "Вы отменили установку скрипта, YouTube скорее всего не будет разблокирован"
            }
        } else {
            $youtubeOtherError = $($_.Exception.Message)
            Write-Log $youtubeOtherError
            Write-Output $youtubeOtherError
            $youtube404Success = "Если Вы видите ошибку 404, то Вы успешно сможете разблокировать YouTube через Zapret! Ничего дополнительно скачивать не требуется."
            Write-Log $youtube404Success
            Write-Output $youtube404Success
        }
    }
    $logYoutubeFinished = "Проверка доступности YouTube завершена."
    Write-Log $logYoutubeFinished
    Write-Host "Лог сохранён на сайте $PSScriptRoot\log.txt"
    
}

function Check-Update {
    # URL файла с актуальной версией
    $versionUrl = "https://gitflic.ru/project/main1234/main1234/blob/raw?file=version.txt"

    try {
        # Загружаем актуальную версию с сервера
        $global:latestVersion = (Invoke-WebRequest -Uri $versionUrl).Content.Trim()

        # Сравниваем версии
        if ([version]$localVersion -lt [version]$latestVersion) {
            $Title2 = "Доступно новое обновление! Текущая версия: $localVersion, Новая версия: $latestVersion"
            $Host.UI.RawUI.WindowTitle = $Title2
            return $true  # Возвращаем $true, если есть обновление
        } else {
            Write-Host "У вас установлена последняя версия ($localVersion)."
            return $false # Возвращаем $false, если обновлений нет
        }
    } catch {
        Write-Host "Ошибка при проверке обновлений: $_"
        return $false # Возвращаем $false, если обновлений нет
    }
}

# Функция для получения стратегии и аргументов из реестра
function Get-DefaultStrategy {
    $RegistryPath = "HKCU:\Software\Zapret"
    $DefaultStrategy = "06.01.2025" # Стратегия по умолчанию, если в реестре ничего нет
    $DefaultConfigArg = "--wf-tcp=80,443 --wf-udp=443,50000-50100 $YRTMP1 $YQ8 $YT10 $YGV3 $other4 $DISIP5 $DISTCP11 $DISUDP9 $UDP7 $YRTMP2 $faceinsta" # Аргументы по умолчанию

    if (Test-Path $RegistryPath) {
        $global:StrategyName = Get-ItemProperty -Path $RegistryPath -Name "DefaultStrategy" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty "DefaultStrategy"
        $global:ConfigArg = Get-ItemProperty -Path $RegistryPath -Name "DefaultConfigArg" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty "DefaultConfigArg"

        if ($StrategyName -and $ConfigArg) {
            return @{"StrategyName" = $StrategyName; "ConfigArg" = $ConfigArg}
        } else {
            # В реестре нет значений, устанавливаем значения по умолчанию и возвращаем их
            Set-ItemProperty -Path $RegistryPath -Name "DefaultStrategy" -Value $DefaultStrategy -Force
            Set-ItemProperty -Path $RegistryPath -Name "DefaultConfigArg" -Value $DefaultConfigArg -Force
            Write-Host "В реестре не найдены значения. Установлены значения по умолчанию."
            return @{"StrategyName" = $DefaultStrategy; "ConfigArg" = $DefaultConfigArg}
        }
    } else {
        New-Item -Path $RegistryPath -Force | Out-Null
        Set-ItemProperty -Path $RegistryPath -Name "DefaultStrategy" -Value $DefaultStrategy -Force
        Set-ItemProperty -Path $RegistryPath -Name "DefaultConfigArg" -Value $DefaultConfigArg -Force
        Write-Host "Раздел реестра HKCU:\Software\Zapret не найден. Создан новый раздел и установлены значения по умолчанию."
        return @{"StrategyName" = $DefaultStrategy; "ConfigArg" = $DefaultConfigArg}
    }
}

# Функция для сохранения состояния автозапуска в реестр
function Set-AutostartState {
    param(
        [int]$AutostartEnabled
    )

    $RegistryPath = "HKCU:\Software\Zapret"
    $Name = "AutostartEnabled"

    # Создаем раздел реестра, если он не существует
    if (!(Test-Path $RegistryPath)) {
        New-Item -Path $RegistryPath -Force | Out-Null
    }

    # Записываем состояние автозапуска в реестр
    Set-ItemProperty -Path $RegistryPath -Name $Name -Value $AutostartEnabled
}

# Функция для получения состояния автозапуска из реестра
function Get-AutostartState {
    $RegistryPath = "HKCU:\Software\Zapret"
    $Name = "AutostartEnabled"
    $DefaultValue = 0 # Автозапуск выключен по умолчанию

    if (Test-Path $RegistryPath) {
        $AutostartEnabled = Get-ItemProperty -Path $RegistryPath -Name $Name -ErrorAction SilentlyContinue | Select-Object -ExpandProperty $Name
        if ($AutostartEnabled -ne $null) {
            return $AutostartEnabled
        } else {
            return $DefaultValue
        }
    } else {
        return $DefaultValue
    }
}

# Функция для установки и включения службы
function Install-Service {
    # Путь к исполняемому файлу
    $ScriptPath = "$PSScriptRoot\bin\winws.exe"
    if (-not (Test-Path $ScriptPath)) {
        Write-Host "Исполняемый файл не найден по пути $ScriptPath!" -ForegroundColor Red
        return
    }

    # Формирование параметров для службы
    $BinPath = "`"$ScriptPath`" $ConfigArg"
    $DisplayName = "zapret DPI bypass: ZapretService"

    try {
        # Создание службы
        New-Service -Name ZapretService -BinaryPathName $BinPath -DisplayName $DisplayName -Description "zapret DPI bypass software" -StartupType Automatic
        Write-Host "Служба ZapretService установлена со стратегией $StrategyName и включена."
    } catch {
        Write-Host "Не удалось установить службу" -ForegroundColor Red
    }

    # Запуск службы
    try {
        Start-Service -Name ZapretService
        Write-Host "Служба ZapretService запущена."
    } catch {
        Write-Host "Не удалось запустить службу" -ForegroundColor Red
    }
}

# Функция для удаления и остановки службы
function Uninstall-Service {
    try {
        # Остановка службы
        Stop-Service -Name ZapretService -Force -ErrorAction Stop
        Write-Host "Служба ZapretService остановлена."
    } catch {
        Write-Host "Не удалось остановить службу" -ForegroundColor Red
        return
    }

    try {
        # Удаление службы
        sc.exe delete ZapretService
        Write-Host "Служба ZapretService удалена."
    } catch {
        Write-Host "Не удалось удалить службу" -ForegroundColor Red
    }
    StopZapret
}

# Функция для включения/выключения автозапуска
function Toggle-Autostart {
    Clear-Host
    $AutostartEnabled = Get-AutostartState

    if ((Get-Process winws -ErrorAction SilentlyContinue) -and ($AutostartEnabled -eq 0)) {
        Write-Host "Процесс winws.exe уже запущен! Остановите его через опцию 0 и только тогда запустите установку автозапуска!"
        return
    } elseif ($AutostartEnabled -eq 1) {
        Uninstall-Service
        Set-AutostartState -AutostartEnabled 0
    } else {
        Install-Service
        Set-AutostartState -AutostartEnabled 1
    }
}

# Функция для включения/выключения автообновлений
function Toggle-AutoUpdate {
    Clear-Host

    if ($global:AutoUpdate -eq 0) {
        $global:AutoUpdate = 1
        Set-ItemProperty -Path "HKCU:\SOFTWARE\Zapret" -Name "AutoUpdate" -Value 1 -Type DWord -Force
    } else {
        $global:AutoUpdate = 0
        Set-ItemProperty -Path "HKCU:\SOFTWARE\Zapret" -Name "AutoUpdate" -Value 0 -Type DWord -Force
    }
}

# Функция для сохранения стратегии в реестр
function Set-DefaultStrategy {
    param(
        [string]$StrategyName,
        [string]$ConfigArg
    )

    $RegistryPath = "HKCU:\Software\Zapret"

    # Создаем раздел реестра, если он не существует
    if (!(Test-Path $RegistryPath)) {
        New-Item -Path $RegistryPath -Force | Out-Null
    }

    # Записываем имя стратегии и аргументы в реестр
    Set-ItemProperty -Path $RegistryPath -Name "DefaultStrategy" -Value $StrategyName
    Set-ItemProperty -Path $RegistryPath -Name "DefaultConfigArg" -Value $ConfigArg
    Write-Host "Стратегия '$StrategyName' сохранена как стратегия по умолчанию в реестре."
    # TODO: ПЕРЕУСТАНОВИТЬ ЗДЕСЬ СЛУЖБУ!
}

# Функция для запуска стратегии по умолчанию при старте скрипта
function Start-DefaultStrategy {
    $AutostartEnabled = Get-AutostartState
    $DefaultStrategyInfo = Get-DefaultStrategy

    if ($AutostartEnabled) {
        Write-Host "Приложение находится в автозапуске! Стратегии не запускаются в ручном режиме."
    } else {
        Write-Host "Запуск стратегии по умолчанию из реестра: '$($DefaultStrategyInfo.StrategyName)'"
        StartZapret -StrategyName $DefaultStrategyInfo.StrategyName -Arguments $DefaultStrategyInfo.ConfigArg
    }
}

function Restart-Discord {
    $discordProcesses = Get-Process discord -ErrorAction SilentlyContinue

    if ($discordProcesses) {
        foreach ($process in $discordProcesses) {
            try {
                Write-Host "Убиваем процесс PID: $($process.Id)"
                Stop-Process -Force -Id $process.Id -ErrorAction Stop
            } catch {
                Write-Host "Процесс уже остановлен. PID: $($process.Id): $($_.Exception.Message)"
            }
        }
    } else {
        Write-Host "Не найдены процессоры Discord."
    }

    try {
        Start-Process -FilePath "$env:AppData\Microsoft\Windows\Start Menu\Programs\Discord Inc\Discord.lnk" -ErrorAction Stop
        Write-Host "Дискорд перезапущен. Для отключения введите опцию 41."
    } catch {
        Write-Host "Дискорд не установлен в системе."
    }
}

function Toggle-DiscordRestartSetting {
    
    Clear-Host
    $registryPath = "HKCU:\SOFTWARE\Zapret"
    $registryValueName = "DiscordRestart"

    if ($DiscordRestartEnabled -eq 1) {
        # Сейчас включено, будем отключать - показываем сообщение с подтверждением
        Write-Warning @"
Внимание! Чтобы изменения в настройках программы, касающиеся обхода блокировок, вступили в силу, вам нужно самостоятельно перезапускать Discord после каждой смены стратегии. Программа больше не будет делать это автоматически. Это значит, что вам нужно полностью закрыть Discord: не только само окно программы, но и найти значок Discord в правом нижнем углу экрана (в области уведомлений, рядом с часами), нажать на него правой кнопкой мыши и выбрать "Выйти из Discord". После этого запустите Discord заново. Если этого не сделать, Discord не сможет подключиться к интернету через новую стратегию. Напишите слово ркн если согласны с этим. Не стоит писать о проблемах с подключением, не попробовав перезапустить приложение. Вы всегда можете вернуть автоматический перезапуск в настройках. Пожалуйста, внимательно прочтите это сообщение от начала до конца.
"@

        $response = Read-Host "Внимательно прочитайте и подтвердите свои действия"
        if ($response -cmatch '^ркн$') { # Проверка на "ркн" (регистр не важен)
            try {
                Set-ItemProperty -Path $registryPath -Name $registryValueName -Value 0 -Type DWord -Force
                Write-Host "Автоматический перезапуск Discord ОТКЛЮЧЕН. Теперь вам нужно будет перезапускать Discord вручную после смены стратегий."
                return $true
            }
            catch {
                Write-Warning "Не удалось отключить автоматический перезапуск Discord: $($_.Exception.Message)"
                return $false
            }
        } else {
            Write-Host "Отмена. Автоматический перезапуск Discord остался включен."
            return $false
        }
    } else {
        # Сейчас выключено, будем включать - сообщение не нужно
        try {
            Set-ItemProperty -Path $registryPath -Name $registryValueName -Value 1 -Type DWord -Force
            Write-Host "Автоматический перезапуск Discord ВКЛЮЧЕН. Discord будет перезапускаться автоматически при смене стратегий."
            return $true
        }
        catch {
            Write-Warning "Не удалось включить автоматический перезапуск Discord: $($_.Exception.Message)"
            return $false
        }
    }
}

if (!(Test-Administrator)) {
    Write-Host "Requesting administrator rights..."
    Start-Process powershell.exe -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$PSCommandPath`"" -Verb RunAs
    exit
}

#####################################################################################################################
$localVersion = "7.0.1"
#####################################################################################################################
ShowTitle
DownloadDLLFile
Show-Telegram

Start-DefaultStrategy

$YT = "--filter-tcp=443 --hostlist=""$LISTS\youtube.txt"""
$YT_2 = "--filter-tcp=443 --hostlist=""$LISTS\youtube_v2.txt"""

$YT1 = "$YT --dpi-desync=fake,split2 --dpi-desync-split-seqovl=2 --dpi-desync-split-pos=3 --dpi-desync-fake-tls=""$BIN\tls_clienthello_www_google_com.bin"" --dpi-desync-ttl=3 --new"
$YT5 = "$YT --dpi-desync=fake,split2 --dpi-desync-split-seqovl=2 --dpi-desync-split-pos=3 --dpi-desync-fake-tls=""$BIN\tls_clienthello_2.bin"" --dpi-desync-autottl=2 --new"
$YT2 = "$YT --dpi-desync=fake,split2 --dpi-desync-split-seqovl=2 --dpi-desync-split-pos=3 --new"
$YT4 = "$YT --dpi-desync=split --dpi-desync-split-pos=1 --dpi-desync-fooling=badseq --dpi-desync-repeats=10 --dpi-desync-autottl=2 --new"
$YT8 = "$YT --dpi-desync=split --dpi-desync-split-pos=1 --dpi-desync-fooling=badseq --dpi-desync-repeats=10 --dpi-desync-cutoff=d2 --dpi-desync-ttl=3 --new"
$YT7 = "$YT --dpi-desync=split --dpi-desync-split-pos=3 --dpi-desync-repeats=4 --dpi-desync-autottl=1 --new"
$YT3 = "$YT --dpi-desync=split --dpi-desync-split-seqovl=1 --dpi-desync-split-tls=sniext --dpi-desync-fake-tls=""$BIN\tls_clienthello_www_google_com.bin"" --dpi-desync-ttl=1 --new"
$YT6 = "$YT --dpi-desync=fake,split2 --dpi-desync-split-seqovl=1 --dpi-desync-split-tls=sniext --dpi-desync-fake-tls=""$BIN\tls_clienthello_www_google_com.bin"" --dpi-desync-ttl=4 --new"
$YT9 = "$YT --dpi-desync=fake,multisplit --dpi-desync-split-seqovl=2 --dpi-desync-split-pos=3 --dpi-desync-fake-tls=""$BIN\tls_clienthello_2.bin"" --dpi-desync-ttl=3 --new"
$YT10 = "$YT_2 --dpi-desync=multisplit --dpi-desync-split-seqovl=1 --dpi-desync-split-pos=midsld+1 --new"
$YT11 = "$YT --dpi-desync=fake,multidisorder --dpi-desync-split-pos=1,midsld --dpi-desync-repeats=11 --dpi-desync-fooling=md5sig --dpi-desync-fake-tls=""$BIN\tls_clienthello_www_google_com.bin"" --new"
#YoutubeFix (ALT v10).bat
$Ankddev10_4 = "$YT --dpi-desync=syndata,multidisorder2 --dpi-desync-split-pos=4 --dpi-desync-repeats=10 --dpi-desync-fooling=md5sig --dpi-desync-fake-tls=""$BIN\tls_clienthello_vk_com_kyber.bin"" --new"

$YGV = "--filter-tcp=443 --hostlist=""$LISTS\youtubeGV.txt"""
$YGV1 = "$YGV --dpi-desync=split --dpi-desync-split-pos=1 --dpi-desync-fooling=badseq --dpi-desync-repeats=10 --dpi-desync-cutoff=d2 --dpi-desync-ttl=4 --new"
$YGV2 = "$YGV --dpi-desync=fakedsplit --dpi-desync-split-pos=1 --dpi-desync-fooling=badseq --dpi-desync-repeats=10 --dpi-desync-ttl=4 --new"
$YGV3 = "$YGV --dpi-desync=multisplit --dpi-desync-split-seqovl=1 --dpi-desync-split-pos=midsld-1 --new"

$YRTMP1 = "--filter-tcp=443 --ipset=""$LISTS\russia-youtube-rtmps.txt"" --dpi-desync=syndata --dpi-desync-fake-syndata=""$BIN\tls_clienthello_4.bin"" --dpi-desync-autottl --new"
$YRTMP2 = "--filter-tcp=443 --ipset-ip=XXX.XXX.XXX.XXX/XX,XXX.XXX.XXX.XXX/XX --wssize=1:6 --hostlist-domains=googlevideo.com --dpi-desync=multidisorder --dpi-desync-split-seqovl=1 --dpi-desync-split-pos=1,host+2,sld+2,sld+5,sniext+1,sniext+2,endhost-2 --new"

$DISTCP80 = "--filter-tcp=80"
$DISTCP = "--filter-tcp=443 --hostlist=""$LISTS\discord.txt"""

$DISTCP1 = "$DISTCP --dpi-desync=split --dpi-desync-split-pos=1 --dpi-desync-fooling=badseq --dpi-desync-repeats=10 --dpi-desync-ttl=4 --new"
$DISTCP2 = "$DISTCP --dpi-desync=split2 --dpi-desync-split-seqovl=652 --dpi-desync-split-pos=2 --dpi-desync-split-seqovl-pattern=""$BIN\tls_clienthello_4.bin"" --new"
$DISTCP3 = "$DISTCP --dpi-desync=fake,split --dpi-desync-repeats=6 --dpi-desync-fooling=badseq --dpi-desync-fake-tls=""$BIN\tls_clienthello_www_google_com.bin"" --new"
$DISTCP4 = "$DISTCP --dpi-desync=fake,split2 --dpi-desync-ttl=1 --dpi-desync-autottl=5 --dpi-desync-repeats=6 --dpi-desync-fake-tls=""$BIN\tls_clienthello_sberbank_ru.bin"" --new"
$DISTCP5 = "$DISTCP --dpi-desync=syndata --dpi-desync-fake-syndata=""$BIN\tls_clienthello_3.bin"" --dpi-desync-ttl=5 --new"
$DISTCP6 = "$DISTCP --dpi-desync=fake,split --dpi-desync-autottl=2 --dpi-desync-repeats=6 --dpi-desync-fooling=badseq --dpi-desync-fake-tls=""$BIN\tls_clienthello_www_google_com.bin"" --new"
$DISTCP7 = "$DISTCP --dpi-desync=fake,split2 --dpi-desync-split-seqovl=1 --dpi-desync-split-tls=sniext --dpi-desync-fake-tls=""$BIN\tls_clienthello_4.bin"" --dpi-desync-ttl=4 --new"
$DISTCP8 = "$DISTCP --dpi-desync=fake,split2 --dpi-desync-split-seqovl=1 --dpi-desync-split-tls=sniext --dpi-desync-fake-tls=""$BIN\tls_clienthello_www_google_com.bin"" --dpi-desync-ttl=2 --new"
$DISTCP9 = "$DISTCP --dpi-desync=split --dpi-desync-split-pos=1 --dpi-desync-fooling=badseq --dpi-desync-repeats=10 --dpi-desync-autottl --new"
$DISTCP10 = "$DISTCP --dpi-desync=split --dpi-desync-split-pos=1 --dpi-desync-fooling=badseq --dpi-desync-repeats=10 --dpi-desync-ttl=3 --new"
$DISTCP11 = "$DISTCP --dpi-desync=fakedsplit --dpi-desync-split-pos=1 --dpi-desync-fooling=badseq --dpi-desync-repeats=10 --dpi-desync-autottl --new"
$DISTCP12 = "$DISTCP --dpi-desync=multisplit --dpi-desync-split-seqovl=1 --dpi-desync-split-pos=midsld+1 --new"
$DISTCP13 = "$DISTCP80 $DISTCP --dpi-desync=fake,multidisorder --dpi-desync-split-pos=midsld --dpi-desync-repeats=6 --dpi-desync-fooling=badseq,md5sig --new"
#DiscordFix (ALT v10).bat
$Ankddev10_1 = "$DISTCP --dpi-desync=syndata,disorder2 --dpi-desync-split-pos=3 --dpi-desync-repeats=11 --dpi-desync-fooling=badseq --dpi-desync-fake-tls=""$BIN\tls_clienthello_www_google_com.bin"" --new"

$DISTCP80 = "--filter-tcp=80 --hostlist=""$LISTS\discord.txt"" --dpi-desync=fake,split2 --dpi-desync-autottl=2 --dpi-desync-fooling=md5sig --new"

$TCP80 = "--filter-tcp=80 --dpi-desync=fake,fakedsplit --dpi-desync-autottl=2 --dpi-desync-fooling=md5sig --new"

$UDP1 = "--filter-udp=50000-59000 --dpi-desync=fake,split2 --dpi-desync-any-protocol --dpi-desync-cutoff=d2 --dpi-desync-fake-quic=""$BIN\quic_test_00.bin"" --new"
#$UDP6 = "--filter-udp=50000-65535 --dpi-desync=fake,split2 --dpi-desync-any-protocol --dpi-desync-cutoff=d2 --dpi-desync-fake-quic=""$BIN\quic_test_00.bin"" --new"
$UDP2 = "--filter-udp=50000-59000 --dpi-desync=fake --dpi-desync-any-protocol --dpi-desync-cutoff=d3 --dpi-desync-repeats=6 --new"
$UDP3 = "--filter-udp=50000-59000 --dpi-desync=fake --dpi-desync-any-protocol --dpi-desync-cutoff=d3 --dpi-desync-repeats=6 --dpi-desync-fake-quic=""$BIN\quic_initial_www_google_com.bin"" --new"
$UDP4 = "--filter-udp=50000-59000 --dpi-desync=fake,tamper --dpi-desync-any-protocol --dpi-desync-cutoff=d3 --dpi-desync-repeats=6 --dpi-desync-fake-quic=""$BIN\quic_initial_www_google_com.bin"" --new"
$UDP5 = "--filter-udp=50000-59000 --dpi-desync=fake,tamper --dpi-desync-any-protocol --dpi-desync-cutoff=n5 --dpi-desync-repeats=10 --dpi-desync-fake-quic=""$BIN\quic_initial_www_google_com.bin"" --new"
$UDP7 = "--filter-udp=50000-50090 --dpi-desync=fake --dpi-desync-any-protocol --dpi-desync-cutoff=n3 --new"
$UDP8 = "--filter-udp=443 --dpi-desync=fake --dpi-desync-repeats=11 --new"

$YQ = "--filter-udp=443 --hostlist=""$LISTS\youtubeQ.txt"""

$YQ1 = "--dpi-desync=fake --dpi-desync-repeats=2 --dpi-desync-cutoff=n2 --dpi-desync-fake-quic=""$BIN\quic_test_00.bin"" --new"
$YQ2 = "$YQ --dpi-desync=fake --dpi-desync-repeats=4 --dpi-desync-fake-quic=""$BIN\quic_initial_www_google_com.bin"" --new"
$YQ3 = "$YQ --dpi-desync=fake --dpi-desync-repeats=4 --dpi-desync-fake-quic=""$BIN\quic_1.bin"" --new"
$YQ4 = "$YQ --dpi-desync=fake --dpi-desync-repeats=11 --dpi-desync-fake-quic=""$BIN\quic_initial_www_google_com.bin"" --new"
$YQ5 = "$YQ --dpi-desync=fake --dpi-desync-repeats=2 --dpi-desync-cutoff=n2 --dpi-desync-fake-quic=""$BIN\quic_initial_www_google_com.bin"" --new"
$YQ6 = "$YQ --dpi-desync=fake --dpi-desync-fake-quic=""$BIN\quic_1.bin"" --dpi-desync-repeats=4 --new"
$YQ7 = "$YQ --dpi-desync=fake,udplen --dpi-desync-udplen-increment=2 --dpi-desync-fake-quic=""$BIN\quic_3.bin"" --dpi-desync-cutoff=n3 --dpi-desync-repeats=2 --new"
$YQ8 = "$YQ --dpi-desync=fake,udplen --dpi-desync-udplen-increment=4 --dpi-desync-fake-quic=""$BIN\quic_3.bin"" --dpi-desync-cutoff=n3 --dpi-desync-repeats=2 --new"
$YQ9 = "$YQ --dpi-desync=fake --dpi-desync-repeats=11 --dpi-desync-fake-quic=""$BIN\quic_initial_www_google_com.bin"" --new"
$Ankddev10_5 = "$YQ --dpi-desync=fake,split2 --dpi-desync-repeats=10 --dpi-desync-udplen-increment=25 --dpi-desync-fake-quic=""$BIN\quic_initial_www_google_com.bin"" --new"

$DISUDP = "--filter-udp=443 --hostlist=""$LISTS\discord.txt"""

$DISUDP1 = "$DISUDP --dpi-desync=fake --dpi-desync-udplen-increment=10 --dpi-desync-repeats=7 --dpi-desync-udplen-pattern=0xDEADBEEF --dpi-desync-fake-quic=""$BIN\quic_test_00.bin"" --dpi-desync-cutoff=n2 --new"
$DISUDP2 = "$DISUDP --dpi-desync=fake --dpi-desync-repeats=6 --dpi-desync-fake-quic=""$BIN\quic_1.bin"" --new"
$DISUDP3 = "$DISUDP --dpi-desync=fake --dpi-desync-repeats=6 --dpi-desync-fake-quic=""$BIN\quic_initial_www_google_com.bin"" --new"
$DISUDP4 = "$DISUDP --dpi-desync=fake --dpi-desync-repeats=6 --dpi-desync-fake-quic=""$BIN\quic_initial_vk_com.bin"" --new"
$DISUDP5 = "$DISUDP --dpi-desync=fake --dpi-desync-udplen-increment=10 --dpi-desync-repeats=7 --dpi-desync-udplen-pattern=0xDEADBEEF --dpi-desync-fake-quic=""$BIN\quic_initial_www_google_com.bin"" --new"
$DISUDP6 = "$DISUDP --dpi-desync=fake,split2 --dpi-desync-udplen-increment=10 --dpi-desync-repeats=6 --dpi-desync-udplen-pattern=0xDEADBEEF --dpi-desync-fake-quic=""$BIN\quic_initial_www_google_com.bin"" --new"
$DISUDP7 = "$DISUDP --dpi-desync=fake --dpi-desync-udplen-increment=10 --dpi-desync-repeats=6 --dpi-desync-udplen-pattern=0xDEADBEEF --dpi-desync-fake-quic=""$BIN\quic_initial_www_google_com.bin"" --new"
$DISUDP8 = "$DISUDP --dpi-desync=fake --dpi-desync-udplen-increment=10 --dpi-desync-udplen-pattern=0xDEADBEEF --dpi-desync-fake-quic=""$BIN\quic_2.bin"" --dpi-desync-repeats=8 --dpi-desync-cutoff=n2 --new"
$DISUDP9 = "$DISUDP --dpi-desync=fake,udplen --dpi-desync-udplen-increment=5 --dpi-desync-udplen-pattern=0xDEADBEEF --dpi-desync-fake-quic=""$BIN\quic_2.bin"" --dpi-desync-repeats=7 --dpi-desync-cutoff=n2 --new"
$Ankddev10_2 = "$DISUDP --dpi-desync=fake,split2 --dpi-desync-repeats=11 --dpi-desync-udplen-increment=15 --dpi-desync-fake-quic=""$BIN\quic_initial_www_google_com.bin"" --new"

$DISIP1 = "--filter-udp=50000-50010 --ipset=""$LISTS\ipset-discord.txt"" --dpi-desync=fake --dpi-desync-any-protocol --dpi-desync-cutoff=d3 --dpi-desync-repeats=6 --new"
$DISIP2 = "--filter-udp=50000-65535 --ipset=""$LISTS\ipset-discord.txt"" --dpi-desync=fake --dpi-desync-any-protocol --dpi-desync-cutoff=d3 --dpi-desync-repeats=6 --new"
$DISIP3 = "--filter-udp=50000-59000 --dpi-desync=fake --dpi-desync-any-protocol --dpi-desync-cutoff=n2 --dpi-desync-fake-quic=""$BIN\quic_initial_www_google_com.bin"" --new"
$DISIP4 = "--filter-udp=50000-50099 --dpi-desync=fake --dpi-desync-any-protocol --dpi-desync-cutoff=d2 --dpi-desync-fake-quic=""$BIN\quic_1.bin"" --new"
$DISIP5 = "--filter-tcp=443 --ipset=""$LISTS\ipset-discord.txt"" --dpi-desync=syndata --dpi-desync-fake-syndata=""$BIN\tls_clienthello_3.bin"" --dpi-desync-autottl --new"
$DISIP6 = "--filter-udp=50000-50099 --ipset=""$LISTS\ipset-discord.txt"" --dpi-desync=fake --dpi-desync-repeats=6 --dpi-desync-any-protocol --dpi-desync-cutoff=n4 --new"
$Ankddev10_3 = "--filter-udp=50000-50099 --ipset=""$LISTS\ipset-discord.txt"" --dpi-desync=fake,tamper --dpi-desync-any-protocol --dpi-desync-cutoff=d5 --dpi-desync-repeats=11 --new"

$faceinsta = "--filter-tcp=443 --hostlist=""$LISTS\faceinsta.txt"" --dpi-desync=split2 --dpi-desync-split-seqovl=652 --dpi-desync-split-pos=2 --dpi-desync-split-seqovl-pattern=""$BIN\tls_clienthello_4.bin"" --new"

$other = "--filter-tcp=443 --hostlist=""$LISTS\other.txt"""
$other1 = "$other --dpi-desync=fake,split2 --dpi-desync-split-seqovl=1 --dpi-desync-split-tls=sniext --dpi-desync-fake-tls=""$BIN\tls_clienthello_3.bin"" --dpi-desync-ttl=2 --new"
$other2 = "$other --dpi-desync=fake,multisplit --dpi-desync-fooling=md5sig --dpi-desync-autottl --new"
$other3 = "$other --dpi-desync=fake,multisplit --dpi-desync-split-seqovl=1 --dpi-desync-split-pos=1 --dpi-desync-fake-tls=""$BIN\tls_clienthello_vk_com.bin"" --dpi-desync-ttl=5 --new"
$other4 = "$other --dpi-desync=fake,multisplit --dpi-desync-split-seqovl=1 --dpi-desync-split-pos=midsld-1 --dpi-desync-fooling=md5sig,badseq --dpi-desync-fake-tls=""$BIN\tls_clienthello_4.bin"" --dpi-desync-ttl=2 --new"
$other5 = "$other --dpi-desync=fake,multidisorder --dpi-desync-split-pos=midsld --dpi-desync-repeats=6 --dpi-desync-fooling=badseq,md5sig --new"
$wf = "--wf-tcp=80,443"

do {
    $AutostartEnabled = Get-AutostartState
    $DefaultStrategyInfo = Get-DefaultStrategy
    $StrategyName = $DefaultStrategyInfo.StrategyName # Получаем имя стратегии из объекта

    ######################## установление значений по умолчанию ###################################################
    try {
        $DiscordRestartEnabled = Get-ItemPropertyValue -Path "HKCU:\SOFTWARE\Zapret" -Name "DiscordRestart"
        Write-Log "[RESTARTDISCORD] $DiscordRestartEnabled"
    } catch {
        Set-ItemProperty -Path "HKCU:\SOFTWARE\Zapret" -Name "DiscordRestart" -Value 1 -Type DWord -Force
        $DiscordRestartEnabled = 1
        Write-Log "[RESTARTDISCORD] ЗНАЧЕНИЕ НЕ УСТАНОВЛЕНО! Устанавливаем $DiscordRestartEnabled"
    }
    try {
        $global:AutoUpdate = Get-ItemPropertyValue -Path "HKCU:\SOFTWARE\Zapret" -Name "AutoUpdate"
        Write-Log "[AUTOUPDATE] $global:AutoUpdate"
    } catch {
        Set-ItemProperty -Path "HKCU:\SOFTWARE\Zapret" -Name "AutoUpdate" -Value 1 -Type DWord -Force
        $global:AutoUpdate = 1
        Write-Log "[AUTOUPDATE] ЗНАЧЕНИЕ НЕ УСТАНОВЛЕНО! Устанавливаем $global:AutoUpdate"
    }

    $winwsProcess = Get-Process -Name winws -ErrorAction SilentlyContinue
    if ($winwsProcess) {
        $winwsStatus = "Запущен"
        $winwsColor = "Green" # Зеленый цвет для "Запущен"
    } else {
        $winwsStatus = "Не запущен"
        $winwsColor = "Red"   # Красный цвет для "Не запущен"
    }
    
    if ($global:AutoUpdate -eq 1) {
        if (Check-Update) {
            # Предлагаем пользователю скачать обновление
            Write-Warning "Доступно новое обновление! Текущая версия: $localVersion, Новая версия: $latestVersion"
            Start-Process -FilePath "powershell.exe" -ArgumentList "-File `"$BIN\check_update.ps1`""
            Exit 0
        }
    }

    $Host.UI.RawUI.WindowTitle = "Zapret $localVersion | https://t.me/bypassblock"
    Write-Host ""
    Write-Host "----------------------- ВЫБЕРИТЕ СТРАТЕГИЮ: -----------------------" -ForegroundColor Cyan
    Write-Host "0. Остановить Zapret"
    Write-Host ""

    # Стратегия 1
    if ($StrategyName -eq "06.01.2025") {
        Write-Host "1. Выбрана 06.01.2025 " -ForegroundColor Green -NoNewline
    }
    else {
        Write-Host "1. Запустить 06.01.2025 " -NoNewline
    }
    Write-Host "(разблокирует любые сайты)" -ForegroundColor DarkGray

    # Стратегия 2
    if ($StrategyName -eq "lite orig v1") {
        Write-Host "2. Выбрана лайт v1 " -ForegroundColor Green -NoNewline
    }
    else {
        Write-Host "2. Запустить лайт v1 " -NoNewline
    }
    Write-Host "(лёгкая и быстрая, минимальный детект для античитов игр, разблокирует любые сайты)" -ForegroundColor DarkGray

    # Стратегия 3
    if ($StrategyName -eq "Discord TCP 80") {
        Write-Host "3. Выбрана Discord TCP 80 " -ForegroundColor Green -NoNewline
    }
    else {
        Write-Host "3. Запустить Discord TCP 80 " -NoNewline
    }
    Write-Host "(предпочтительно Ростелеком)" -ForegroundColor DarkGray

    # Стратегия 4
    if ($StrategyName -eq "Discord fake") {
        Write-Host "4. Запустить Discord fake " -ForegroundColor Green -NoNewline
    }
    else {
        Write-Host "4. Запустить Discord fake " -NoNewline
    }
    Write-Host "(предпочтительно Ростелеком)" -ForegroundColor DarkGray

    # Стратегия 5
    if ($StrategyName -eq "Discord fake и split") {
        Write-Host "5. Выбрана Discord fake и split " -ForegroundColor Green -NoNewline
    }
    else {
        Write-Host "5. Запустить Discord fake и split " -NoNewline
    }
    Write-Host "(предпочтительно Уфанет)" -ForegroundColor DarkGray

    # Стратегия 6
    if ($StrategyName -eq "Ultimate Fix ALT Beeline-Rostelekom") {
        Write-Host "6. Выбрана Discord fake и split2 " -ForegroundColor Green -NoNewline
    }
    else {
        Write-Host "6. Запустить Discord fake и split2 " -NoNewline
    }
    Write-Host "(УльтиМейт фикс, предпочтительно Билайн и Ростелеком)" -ForegroundColor DarkGray
    Write-Host ""

    # Стратегия 7
    if ($StrategyName -eq "split с sniext") {
        Write-Host "7. Выбрана split с sniext " -ForegroundColor Green -NoNewline
    }
    else {
        Write-Host "7. Запустить split с sniext " -NoNewline
    }
    Write-Host "(предпочтительно ДомРу)" -ForegroundColor DarkGray

    # Стратегия 8
    if ($StrategyName -eq "split с badseq") {
        Write-Host "8. Выбрана split с badseq " -ForegroundColor Green -NoNewline
    }
    else {
        Write-Host "8. Запустить split с badseq " -NoNewline
    }
    Write-Host "(предпочтительно ДомРу)" -ForegroundColor DarkGray
    Write-Host ""

    # Стратегия 9
    if ($StrategyName -eq "Rostelecom & Megafon") {
        Write-Host "9. Выбрана split с badseq " -ForegroundColor Green -NoNewline
    }
    else {
        Write-Host "9. Запустить split с badseq " -NoNewline
    }
    Write-Host "(предпочтительно Ростелеком и Мегафон)" -ForegroundColor DarkGray

    # Стратегия 10
    if ($StrategyName -eq "Rostelecom v2") {
        Write-Host "10. Выбрана fake и split2, второй bin файл " -ForegroundColor Green -NoNewline
    }
    else {
        Write-Host "10. Запустить fake и split2, второй bin файл " -NoNewline
    }
    Write-Host "(предпочтительно Ростелеком)" -ForegroundColor DarkGray
    Write-Host ""

    # Стратегия 11
    if ($StrategyName -eq "Other v1") {
        Write-Host "11. Выбрана YouTube fake QUIC, bin файл google, больше размер пакетов, также YouTube fake" -ForegroundColor Green
    }
    else {
        Write-Host "11. Запустить YouTube fake QUIC, bin файл google, больше размер пакетов, также YouTube fake"
    }

    # Стратегия 12
    if ($StrategyName -eq "Other v2") {
        Write-Host "12. Выбрана YouTube fake QUIC, bin файл google, больше размер пакетов, также YouTube fake и split 2" -ForegroundColor Green
    }
    else {
        Write-Host "12. Запустить YouTube fake QUIC, bin файл google, больше размер пакетов, также YouTube fake и split 2"
    }

    # Стратегия 13
    if ($StrategyName -eq "Ankddev v10") { # Оригинальное имя стратегии из меню - "syndata", DefaultConfigName - "Ankddev v10"
        Write-Host "13. Выбрана syndata " -ForegroundColor Green -NoNewline
    }
    else {
        Write-Host "13. Запустить syndata " -NoNewline
    }
    Write-Host "(устаревшая стратегия)" -ForegroundColor DarkGray
    Write-Host ""

    # Стратегия 14
    if ($StrategyName -eq "MGTS v1") {
        Write-Host "14. Выбрана split с badseq " -ForegroundColor Green -NoNewline
    }
    else {
        Write-Host "14. Запустить split с badseq " -NoNewline
    }
    Write-Host "(предпочтительно МГТС)" -ForegroundColor DarkGray

    # Стратегия 15
    if ($StrategyName -eq "MGTS v2") {
        Write-Host "15. Выбрана split с badseq, дополнительно cutoff " -ForegroundColor Green -NoNewline
    }
    else {
        Write-Host "15. Запустить split с badseq, дополнительно cutoff " -NoNewline
    }
    Write-Host "(предпочтительно МГТС или ЯлтаТВ)" -ForegroundColor DarkGray

    # Стратегия 16
    if ($StrategyName -eq "MGTS v3") {
        Write-Host "16. Выбрана fake и split2, bin файл google " -ForegroundColor Green -NoNewline
    }
    else {
        Write-Host "16. Запустить fake и split2, bin файл google " -NoNewline
    }
    Write-Host "(предпочтительно МГТС)" -ForegroundColor DarkGray

    # Стратегия 17
    if ($StrategyName -eq "MGTS v4") {
        Write-Host "17. Выбрана fake и split2 bin файл quic_test_00 " -ForegroundColor Green -NoNewline
    }
    else {
        Write-Host "17. Запустить fake и split2 bin файл quic_test_00 " -NoNewline
    }
    Write-Host "(предпочтительно МГТС)" -ForegroundColor DarkGray
    Write-Host ""

    # Стратегия 30
    if ($StrategyName -eq "Ultimate Config ZL") {
        Write-Host "30. Выбрана ультимейт конфиг ZL " -ForegroundColor Green -NoNewline
    }
    else {
        Write-Host "30. Запустить ультимейт конфиг ZL " -NoNewline
    }
    Write-Host "(разблокирует любые сайты)" -ForegroundColor DarkGray

    # Стратегия 31
    if ($StrategyName -eq "Ultimate Config v2") {
        Write-Host "31. Выбрана ультимейт конфиг v2 " -ForegroundColor Green -NoNewline
    }
    else {
        Write-Host "31. Запустить ультимейт конфиг v2 " -NoNewline
    }
    Write-Host "(разблокирует любые сайты)" -ForegroundColor DarkGray

    Write-Host ""
    Write-Host "----------------------- ДРУГИЕ ОПЦИИ: -----------------------" -ForegroundColor Cyan
    if ($AutostartEnabled -eq 1) {
        Write-Host "40. Выключить автозапуск (" -NoNewline
        Write-Host "включён" -ForegroundColor DarkGreen -NoNewline
        Write-Host ")"
    } else {
        Write-Host "40. Включить автозапуск (" -NoNewline
        Write-Host "выключен" -ForegroundColor DarkRed -NoNewline
        Write-Host ")"
    }
    if ($discordRestartEnabled -eq 1) {
        Write-Host "41. Выключить автоматический перезапуск Discord при запуске Запрета (" -NoNewline
        Write-Host "включён" -ForegroundColor DarkGreen -NoNewline
        Write-Host ")"
    } else {
        Write-Host "41. Включить автоматический перезапуск Discord при запуске Запрета (" -NoNewline
        Write-Host "выключен" -ForegroundColor DarkRed -NoNewline
        Write-Host ")"
    }
    if ($global:AutoUpdate -eq 1) {
        Write-Host "42. Выключить автообновление программы Zapret (" -NoNewline
        Write-Host "включён" -ForegroundColor DarkGreen -NoNewline
        Write-Host ")"
    } else {
        Write-Host "41. Включить автообновление программы Zapret (" -NoNewline
        Write-Host "выключен" -ForegroundColor DarkRed -NoNewline
        Write-Host ")"
    }
    Write-Host ""
    Write-Host "50. Проверить работу YouTube и Discord глобально! (если никакие стратегии не помогают)"
    Write-Host "51. Открыть лог файл"
    Write-Host "52. Запросить помощь (открыть Telegram канал)"
    Write-Host ""
    Write-Host "60. Очистить DNS (установить дефолтные) (помогает если после смены DNS сломался интернет)"
    Write-Host "61. Сменить DNS на Google DNS (помогает если Вы этого ещё не сделали)"
    Write-Host "62. Сменить DNS на SB DNS"
    Write-Host "63. Сменить DNS на свои (кастомные)"
    Write-Host ""
    Write-Host "70. Отредактировать файл hosts (помогает разблокировать Instagram, Facebook, Twitter и т.д.)"
    Write-Host "71. Разблокировать ChatGPT, Gemini, Spotify, TikTok, Notion и другие ресурсы"
    Write-Host ""
    Write-Host "Статус программы: " -NoNewline
    Write-Host $winwsStatus -ForegroundColor $winwsColor
    $userInput = Read-Host "Введите цифру стратегии или необходимую опцию"

    switch ($userInput) {
        "0" {
            if ($AutostartEnabled) {
                Write-Host "Приложение находится в автозапуске! Запрет выключается ТОЛЬКО через выключение автозапуска, наберите 40 чтобы убрать его из автозапуска!"
                Write-Host "В будущих версиях эта ошибка исправится..."
            } else {
                Clear-Host
                ShowTitle
                StopZapret
            }
        }
        "1" {
            $DefaultConfigName = "06.01.2025"
            $DefaultConfigArg = "$wf --wf-udp=443,50000-50100 $YRTMP1 $YQ8 $YT10 $YGV3 $other1 $DISIP5 $DISTCP11 $DISUDP9 $UDP7 $YRTMP2 $faceinsta"
        }
        "2" {
            $DefaultConfigName = "lite orig v1"
            $DefaultConfigArg = "$wf --wf-udp=443,50000-50100 $faceinsta $TCP80 $YT11 $YQ9 $other3 $DISTCP13 $UDP8 $DISIP6"
        }
        "3" {
            $DefaultConfigName = "Discord TCP 80"
            $DefaultConfigArg = "$wf --wf-udp=443,50000-59000 $YQ1 $YGV1 $YT1 $DISTCP80 $DISUDP2 $UDP2 $DISTCP2 $other1 $faceinsta"
        }
        "4" {
            $DefaultConfigName = "Discord fake"
            $DefaultConfigArg = "$wf --wf-udp=443,50000-59000 $YQ1 $YGV1 $YT1 $DISUDP1 $UDP1 $DISTCP1 $other1 $faceinsta" 
        }
        "5" {
            $DefaultConfigName = "Discord fake и split"
            $DefaultConfigArg = "$wf --wf-udp=443,50000-50100 $DISUDP3 $DISIP1 $DISTCP80 $DISTCP3 $YQ1 $YGV1 $YT2 $other1 $faceinsta" 
        }
        "6" {
            $DefaultConfigName = "Ultimate Fix ALT Beeline-Rostelekom"
            $DefaultConfigArg = "$wf --wf-udp=443,50000-65535 $DISUDP4 $DISIP2 $DISTCP80 $DISTCP4 $YQ1 $YGV1 $YT2 $other1 $faceinsta"
        }
        "7" {
            $DefaultConfigName = "split с sniext"
            $DefaultConfigArg = "$wf --wf-udp=443,50000-59000 $YQ2 $YGV3 $YT3 $DISTCP5 $DISUDP5 $DISIP3 $other1 $faceinsta"
        }
        "8" {
            $DefaultConfigName = "split с badseq"
            $DefaultConfigArg = "$wf --wf-udp=443,50000-59000 $YQ2 $YGV1 $YT4 $DISTCP5 $DISUDP5 $DISIP3 $other1 $faceinsta"
        }
        "9" {
            $DefaultConfigName = "Rostelecom & Megafon"
            $DefaultConfigArg = "$wf --wf-udp=443,50000-59000 $YQ2 $YT4 $DISUDP3 $UDP3 $DISTCP6 $other1 $faceinsta"
        }
        "10" {
            $DefaultConfigName = "Rostelecom v2"
            $DefaultConfigArg = "$wf --wf-udp=443,50000-59000 $YQ3 $YT5 $DISUDP3 $UDP3 $DISTCP6 $other1 $faceinsta"
        }
        "11" {
            $DefaultConfigName = "Other v1"
            $DefaultConfigArg = "--wf-l3=ipv4,ipv6 --wf-tcp=443 --wf-udp=443,50000-65535 $YQ4 $YT3 $DISTCP7 $DISUDP6 $UDP4 $other1 $faceinsta"
        }
        "12" {
            $DefaultConfigName = "Other v2"
            $DefaultConfigArg = "--wf-l3=ipv4,ipv6 --wf-tcp=443 --wf-udp=443,50000-65535 $YQ4 $YT6 $DISUDP7 $UDP5 $DISTCP8 $other1 $faceinsta"
        }
        "13" {
            $DefaultConfigName = "Ankddev v10"
            $DefaultConfigArg = "--wf-l3=ipv4,ipv6 --wf-tcp=443 --wf-udp=443,50000-65535 $Ankddev10_1 $Ankddev10_2 $Ankddev10_3 $Ankddev10_4 $Ankddev10_5"           
        }
        "14" {
            $DefaultConfigName = "MGTS v1"
            $DefaultConfigArg = "$wf --wf-udp=443,50000-50010 $YGV1 $YT7 $DISIP1 $DISTCP9 $other1 $faceinsta"
        }
        "15" {
            $DefaultConfigName = "MGTS v2"
            $DefaultConfigArg = "$wf --wf-udp=443,50000-50900 $YT8 $DISTCP10 $YQ5 $DISUDP1 $other1 $faceinsta"
        }
        "16" {
            $DefaultConfigName = "MGTS v3"
            $DefaultConfigArg = "$wf --wf-udp=443,50000-50900 $YT7 $DISTCP10 $YQ5 $DISUDP1 $UDP1 $other1 $faceinsta"
        }
        "17" {
            $DefaultConfigName = "MGTS v4"
            $DefaultConfigArg = "$wf --wf-udp=443,50000-50900 $YQ1 $YGV3 $YT1 $DISUDP1 $UDP1 $DISTCP1 $other1 $faceinsta"
        }
        "30" {
            $DefaultConfigName = "Ultimate Config ZL"
            $DefaultConfigArg = "$wf --wf-udp=443,50000-50099 $YQ6 $YGV2 $YT9 $DISTCP11 $DISUDP8 $DISIP4 $other3 $faceinsta"
        }
        "31" {
            $DefaultConfigName = "Ultimate Config v2"
            $DefaultConfigArg = "$wf --wf-udp=443,50000-50090 $YRTMP1 $YQ7 $DISIP5 $DISTCP12 $DISUDP9 $UDP7 $YGV3 $other2 $other4 $faceinsta"
        }
        "40" {
            Toggle-Autostart
        }
        "41" {
            $result = Toggle-DiscordRestartSetting
            if ($result) {
                # Функция выполнилась успешно, сообщение уже выведено внутри Toggle-DiscordRestartSetting
            } else {
                Write-Error "Не удалось изменить настройку перезапуска Discord. Проверьте права доступа или журнал событий."
            }
        }
        "42" {
            Toggle-AutoUpdate
        }
        "50" {
            Check-Discord
            Check-YouTube
        }
        "51" {
            OpenLogFile
        }
        "52" {
            ShowTelegram
        }
        "60" {
            Reset-DNS
        }
        "61" {
            Set-CustomDNS -DNSType "Google"
        }
        "62" {
            Set-CustomDNS -DNSType "DnsSB"
        }
        "63" {
            $PrimaryCustomDNS = Read-Host "Введите первичный DNS сервер"
            $SecondaryCustomDNS = Read-Host "Введите вторичный DNS сервер"
            Set-CustomDNS -DNSType "Custom" -PrimaryDNS $PrimaryCustomDNS -SecondaryDNS $SecondaryCustomDNS
        }
        "70" {
            Edit-Hosts -ContentName "Facebook"
        }
        "71" {
            Edit-Hosts -ContentName "ChatGPT-Gemini"
        }
        default {
            Write-Host "Вы не выбрали правильную цифру!"
        }
    }

    if ($userInput -in @("1".."17"; "30"; "31")) {
        Set-DefaultStrategy -StrategyName $DefaultConfigName -ConfigArg $DefaultConfigArg
        if ($AutostartEnabled) {
            Write-Host "Важно: Запрет не применит новую выбранную стратегию пока Вы не перезапустите автозапуск через цифру 40!"
        } else {
            Clear-Host
            ShowTitle
            StopZapret
            StartZapret -StrategyName $DefaultConfigName -Arguments $DefaultConfigArg

            if ($discordRestartEnabled -eq 1) {
                Restart-Discord
            }
        }
    }
} while ($true)
