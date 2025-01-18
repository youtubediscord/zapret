# Устанавливаем кодовую страницу UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Устанавливаем синий цвет фона (не работает в PowerShell 7+)
if ($PSVersionTable.PSVersion.Major -lt 6) {
    $Host.UI.RawUI.BackgroundColor = "DarkBlue"
    Clear-Host
}

<#
### 1.3. Настройки файла hosts
В файл `C:\Windows\System32\drivers\etc\hosts` пропишите следующее содержание (_рекомендуется использовать [`Notepad++`](https://github.com/notepad-plus-plus/notepad-plus-plus/releases), ссылка на оф. сайт была заблокирована_):

```
31.13.72.36 facebook.com
31.13.72.36 www.facebook.com
31.13.72.12 static.xx.fbcdn.net
31.13.72.18 fburl.com
157.240.227.174 www.instagram.com
157.240.227.174 instagram.com
31.13.72.53 static.cdninstagram.com
31.13.72.53 edge-chat.instagram.com
157.240.254.63 scontent.cdninstagram.com
157.240.205.63 scontent-hel3-1.cdninstagram.com
104.21.32.39 rutracker.org
172.67.182.196 rutracker.org
116.202.120.184 torproject.org
116.202.120.184 bridges.torproject.org
116.202.120.166 community.torproject.org
162.159.152.4 medium.com
172.67.182.196 rutracker.org
188.114.96.1 dept.one
142.250.185.238 youtube.com
142.250.186.110 www.youtube.com
130.255.77.28 ntc.party
```

Либо на какой-то из примеров ниже (_предыдущий вариант удалите_):
```
31.13.72.36 facebook.com
31.13.72.36 www.facebook.com
31.13.72.12 static.xx.fbcdn.net
31.13.72.18 fburl.com
157.240.229.174 www.instagram.com
157.240.229.174 instagram.com
31.13.72.53 static.cdninstagram.com
31.13.72.53 edge-chat.instagram.com
31.13.72.53 scontent-arn2-1.cdninstagram.com
157.240.247.63 scontent.cdninstagram.com
157.240.205.63 scontent-hel3-1.cdninstagram.com
104.21.32.39 rutracker.org
172.67.182.196 rutracker.org
116.202.120.184 torproject.org
116.202.120.184 bridges.torproject.org
116.202.120.166 community.torproject.org
162.159.152.4 medium.com
172.67.182.196 rutracker.org
188.114.96.1 dept.one
142.250.185.238 youtube.com
142.250.186.110 www.youtube.com
130.255.77.28 ntc.party
```

```
31.13.72.36 facebook.com
31.13.72.36 www.facebook.com
31.13.72.12 static.xx.fbcdn.net
31.13.72.18 fburl.com
157.240.225.174 instagram.com
157.240.225.174 www.instagram.com
157.240.225.174 i.instagram.com
31.13.72.53 edge-chat.instagram.com
31.13.72.53 scontent-arn2-1.cdninstagram.com
31.13.72.53 scontent.cdninstagram.com
31.13.72.53 static.cdninstagram.com 
157.240.205.63 scontent-hel3-1.cdninstagram.com
104.21.32.39 rutracker.org
172.67.182.196 rutracker.org
116.202.120.184 torproject.org
116.202.120.184 bridges.torproject.org
116.202.120.166 community.torproject.org
162.159.152.4 medium.com
172.67.182.196 rutracker.org
188.114.96.1 dept.one
142.250.185.238 youtube.com
142.250.186.110 www.youtube.com
130.255.77.28 ntc.party
```
#>

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

$BIN = "$PSScriptRoot\bin\"
$LISTS = "$PSScriptRoot\lists\"
$localVersion = "6.4.3"

$YT1 = "--filter-tcp=443 --hostlist=""$LISTS\youtube.txt"" --dpi-desync=fake,split2 --dpi-desync-split-seqovl=2 --dpi-desync-split-pos=3 --dpi-desync-fake-tls=""$BIN\tls_clienthello_www_google_com.bin"" --dpi-desync-ttl=3 --new"
$YT5 = "--filter-tcp=443 --hostlist=""$LISTS\youtube.txt"" --dpi-desync=fake,split2 --dpi-desync-split-seqovl=2 --dpi-desync-split-pos=3 --dpi-desync-fake-tls=""$BIN\tls_clienthello_2.bin"" --dpi-desync-autottl=2 --new"
$YT2 = "--filter-tcp=443 --hostlist=""$LISTS\youtube.txt"" --dpi-desync=fake,split2 --dpi-desync-split-seqovl=2 --dpi-desync-split-pos=3 --new"
$YT4 = "--filter-tcp=443 --hostlist=""$LISTS\youtube.txt"" --dpi-desync=split --dpi-desync-split-pos=1 --dpi-desync-fooling=badseq --dpi-desync-repeats=10 --dpi-desync-autottl=2 --new"
$YT8 = "--filter-tcp=443 --hostlist=""$LISTS\youtube.txt"" --dpi-desync=split --dpi-desync-split-pos=1 --dpi-desync-fooling=badseq --dpi-desync-repeats=10 --dpi-desync-cutoff=d2 --dpi-desync-ttl=3 --new"
$YT7 = "--filter-tcp=443 --hostlist=""$LISTS\youtube.txt"" --dpi-desync=split --dpi-desync-split-pos=1 --dpi-desync-fooling=badseq --dpi-desync-repeats=10 --dpi-desync-ttl=4 --new"
$YT3 = "--filter-tcp=443 --hostlist=""$LISTS\youtube.txt"" --dpi-desync=split --dpi-desync-split-seqovl=1 --dpi-desync-split-tls=sniext --dpi-desync-fake-tls=""$BIN\tls_clienthello_www_google_com.bin"" --dpi-desync-ttl=1 --new"
$YT6 = "--filter-tcp=443 --hostlist=""$LISTS\youtube.txt"" --dpi-desync=fake,split2 --dpi-desync-split-seqovl=1 --dpi-desync-split-tls=sniext --dpi-desync-fake-tls=""$BIN\tls_clienthello_www_google_com.bin"" --dpi-desync-ttl=4 --new"
$YT9 = "--filter-tcp=443 --hostlist=""$LISTS\youtube.txt"" --dpi-desync=fake,multisplit --dpi-desync-split-seqovl=2 --dpi-desync-split-pos=3 --dpi-desync-fake-tls=""$BIN\tls_clienthello_2.bin"" --dpi-desync-ttl=3 --new"
$YT10 = "--filter-tcp=443 --hostlist=""$LISTS\youtube_v2.txt"" --dpi-desync=multisplit --dpi-desync-split-seqovl=1 --dpi-desync-split-pos=midsld+1 --new"
$YT11 = "--filter-tcp=443 --hostlist=""$LISTS\youtube.txt"" --dpi-desync=fake,multidisorder --dpi-desync-split-pos=1,midsld --dpi-desync-repeats=11 --dpi-desync-fooling=md5sig --dpi-desync-fake-tls=""$BIN\tls_clienthello_www_google_com.bin"" --new"

$YGV1 = "--filter-tcp=443 --hostlist=""$LISTS\youtubeGV.txt"" --dpi-desync=split --dpi-desync-split-pos=1 --dpi-desync-fooling=badseq --dpi-desync-repeats=10 --dpi-desync-cutoff=d2 --dpi-desync-ttl=4 --new"
$YGV2 = "--filter-tcp=443 --hostlist=""$LISTS\youtubeGV.txt"" --dpi-desync=fakedsplit --dpi-desync-split-pos=1 --dpi-desync-fooling=badseq --dpi-desync-repeats=10 --dpi-desync-ttl=4 --new"
$YGV3 = "--filter-tcp=443 --hostlist=""$LISTS\youtubeGV.txt"" --dpi-desync=multisplit --dpi-desync-split-seqovl=1 --dpi-desync-split-pos=midsld-1 --new"

$YRTMP1 = "--filter-tcp=443 --ipset=""$LISTS\russia-youtube-rtmps.txt"" --dpi-desync=syndata --dpi-desync-fake-syndata=""$BIN\tls_clienthello_4.bin"" --dpi-desync-autottl --new"
$YRTMP2 = "--filter-tcp=443 --ipset-ip=XXX.XXX.XXX.XXX/XX,XXX.XXX.XXX.XXX/XX --wssize=1:6 --hostlist-domains=googlevideo.com --dpi-desync=multidisorder --dpi-desync-split-seqovl=1 --dpi-desync-split-pos=1,host+2,sld+2,sld+5,sniext+1,sniext+2,endhost-2 --new"

$DISTCP1 = "--filter-tcp=443 --hostlist=""$LISTS\discord.txt"" --dpi-desync=split --dpi-desync-split-pos=1 --dpi-desync-fooling=badseq --dpi-desync-repeats=10 --dpi-desync-ttl=4 --new"
$DISTCP2 = "--filter-tcp=443 --hostlist=""$LISTS\discord.txt"" --dpi-desync=split2 --dpi-desync-split-seqovl=652 --dpi-desync-split-pos=2 --dpi-desync-split-seqovl-pattern=""$BIN\tls_clienthello_4.bin"" --new"
$DISTCP3 = "--filter-tcp=443 --hostlist=""$LISTS\discord.txt"" --dpi-desync=fake,split --dpi-desync-repeats=6 --dpi-desync-fooling=badseq --dpi-desync-fake-tls=""$BIN\tls_clienthello_www_google_com.bin"" --new"
$DISTCP4 = "--filter-tcp=443 --hostlist=""$LISTS\discord.txt"" --dpi-desync=fake,split2 --dpi-desync-ttl=1 --dpi-desync-autottl=5 --dpi-desync-repeats=6 --dpi-desync-fake-tls=""$BIN\tls_clienthello_sberbank_ru.bin"" --new"
$DISTCP5 = "--filter-tcp=443 --hostlist=""$LISTS\discord.txt"" --dpi-desync=syndata --dpi-desync-fake-syndata=""$BIN\tls_clienthello_3.bin"" --dpi-desync-ttl=5 --new"
$DISTCP6 = "--filter-tcp=443 --hostlist=""$LISTS\discord.txt"" --dpi-desync=fake,split --dpi-desync-autottl=2 --dpi-desync-repeats=6 --dpi-desync-fooling=badseq --dpi-desync-fake-tls=""$BIN\tls_clienthello_www_google_com.bin"" --new"
$DISTCP7 = "--filter-tcp=443 --hostlist=""$LISTS\discord.txt"" --dpi-desync=fake,split2 --dpi-desync-split-seqovl=1 --dpi-desync-split-tls=sniext --dpi-desync-fake-tls=""$BIN\tls_clienthello_4.bin"" --dpi-desync-ttl=4 --new"
$DISTCP8 = "--filter-tcp=443 --hostlist=""$LISTS\discord.txt"" --dpi-desync=fake,split2 --dpi-desync-split-seqovl=1 --dpi-desync-split-tls=sniext --dpi-desync-fake-tls=""$BIN\tls_clienthello_www_google_com.bin"" --dpi-desync-ttl=2 --new"
$DISTCP9 = "--filter-tcp=443 --hostlist=""$LISTS\discord.txt"" --dpi-desync=split --dpi-desync-split-pos=1 --dpi-desync-fooling=badseq --dpi-desync-repeats=10 --dpi-desync-autottl --new"
$DISTCP10 = "--filter-tcp=443 --hostlist=""$LISTS\discord.txt"" --dpi-desync=split --dpi-desync-split-pos=1 --dpi-desync-fooling=badseq --dpi-desync-repeats=10 --dpi-desync-ttl=3 --new"
$DISTCP11 = "--filter-tcp=443 --hostlist=""$LISTS\discord.txt"" --dpi-desync=fakedsplit --dpi-desync-split-pos=1 --dpi-desync-fooling=badseq --dpi-desync-repeats=10 --dpi-desync-autottl --new"
$DISTCP12 = "--filter-tcp=443 --hostlist=""$LISTS\youtube.txt"" --dpi-desync=multisplit --dpi-desync-split-seqovl=1 --dpi-desync-split-pos=midsld+1 --new"
$DISTCP80 = "--filter-tcp=80 --hostlist=""$LISTS\discord.txt"" --dpi-desync=fake,split2 --dpi-desync-autottl=2 --dpi-desync-fooling=md5sig --new"

$TCP443 = "--filter-tcp=443 --hostlist=""$LISTS\discord.txt"" --hostlist=""$LISTS\other.txt"" --dpi-desync=fake,multidisorder --dpi-desync-split-pos=midsld --dpi-desync-repeats=6 --dpi-desync-fooling=badseq,md5sig --new"

$TCP80 = "--filter-tcp=80 --dpi-desync=fake,fakedsplit --dpi-desync-autottl=2 --dpi-desync-fooling=md5sig --new"

$UDP1 = "--filter-udp=50000-59000 --dpi-desync=fake,split2 --dpi-desync-any-protocol --dpi-desync-cutoff=d2 --dpi-desync-fake-quic=""$BIN\quic_test_00.bin"" --new"
#$UDP6 = "--filter-udp=50000-65535 --dpi-desync=fake,split2 --dpi-desync-any-protocol --dpi-desync-cutoff=d2 --dpi-desync-fake-quic=""$BIN\quic_test_00.bin"" --new"
$UDP2 = "--filter-udp=50000-59000 --dpi-desync=fake --dpi-desync-any-protocol --dpi-desync-cutoff=d3 --dpi-desync-repeats=6 --new"
$UDP3 = "--filter-udp=50000-59000 --dpi-desync=fake --dpi-desync-any-protocol --dpi-desync-cutoff=d3 --dpi-desync-repeats=6 --dpi-desync-fake-quic=""$BIN\quic_initial_www_google_com.bin"" --new"
$UDP4 = "--filter-udp=50000-59000 --dpi-desync=fake,tamper --dpi-desync-any-protocol --dpi-desync-cutoff=d3 --dpi-desync-repeats=6 --dpi-desync-fake-quic=""$BIN\quic_initial_www_google_com.bin"" --new"
$UDP5 = "--filter-udp=50000-59000 --dpi-desync=fake,tamper --dpi-desync-any-protocol --dpi-desync-cutoff=n5 --dpi-desync-repeats=10 --dpi-desync-fake-quic=""$BIN\quic_initial_www_google_com.bin"" --new"
$UDP7 = "--filter-udp=50000-50090 --dpi-desync=fake --dpi-desync-any-protocol --dpi-desync-cutoff=n3 --new"
$UDP8 = "--filter-udp=443 --dpi-desync=fake --dpi-desync-repeats=11 --new"

$YQ1 = "--filter-udp=443 --hostlist=""$LISTS\youtubeQ.txt"" --dpi-desync=fake --dpi-desync-repeats=2 --dpi-desync-cutoff=n2 --dpi-desync-fake-quic=""$BIN\quic_test_00.bin"" --new"
$YQ2 = "--filter-udp=443 --hostlist=""$LISTS\youtubeQ.txt"" --dpi-desync=fake --dpi-desync-repeats=4 --dpi-desync-fake-quic=""$BIN\quic_initial_www_google_com.bin"" --new"
$YQ3 = "--filter-udp=443 --hostlist=""$LISTS\youtubeQ.txt"" --dpi-desync=fake --dpi-desync-repeats=4 --dpi-desync-fake-quic=""$BIN\quic_1.bin"" --new"
$YQ4 = "--filter-udp=443 --hostlist=""$LISTS\youtubeQ.txt"" --dpi-desync=fake --dpi-desync-repeats=11 --dpi-desync-fake-quic=""$BIN\quic_initial_www_google_com.bin"" --new"
$YQ5 = "--filter-udp=443 --hostlist=""$LISTS\youtubeQ.txt"" --dpi-desync=fake --dpi-desync-repeats=2 --dpi-desync-cutoff=n2 --dpi-desync-fake-quic=""$BIN\quic_initial_www_google_com.bin"" --new"
$YQ6 = "--filter-udp=443 --hostlist=""$LISTS\youtubeQ.txt"" --dpi-desync=fake --dpi-desync-fake-quic=""$BIN\quic_1.bin"" --dpi-desync-repeats=4 --new"
$YQ7 = "--filter-udp=443 --hostlist=""$LISTS\youtubeQ.txt"" --dpi-desync=fake,udplen --dpi-desync-udplen-increment=2 --dpi-desync-fake-quic=""$BIN\quic_3.bin"" --dpi-desync-cutoff=n3 --dpi-desync-repeats=2 --new"
$YQ8 = "--filter-udp=443 --hostlist=""$LISTS\youtubeQ.txt"" --dpi-desync=fake,udplen --dpi-desync-udplen-increment=4 --dpi-desync-fake-quic=""$BIN\quic_3.bin"" --dpi-desync-cutoff=n3 --dpi-desync-repeats=2 --new"
$YQ9 = "--filter-udp=443 --hostlist=""$LISTS\youtubeQ.txt"" --dpi-desync=fake --dpi-desync-repeats=11 --dpi-desync-fake-quic=""$BIN\quic_initial_www_google_com.bin"" --new"

$DISUDP1 = "--filter-udp=443 --hostlist=""$LISTS\discord.txt"" --dpi-desync=fake --dpi-desync-udplen-increment=10 --dpi-desync-repeats=7 --dpi-desync-udplen-pattern=0xDEADBEEF --dpi-desync-fake-quic=""$BIN\quic_test_00.bin"" --dpi-desync-cutoff=n2 --new"
$DISUDP2 = "--filter-udp=443 --hostlist=""$LISTS\discord.txt"" --dpi-desync=fake --dpi-desync-repeats=6 --dpi-desync-fake-quic=""$BIN\quic_1.bin"" --new"
$DISUDP3 = "--filter-udp=443 --hostlist=""$LISTS\discord.txt"" --dpi-desync=fake --dpi-desync-repeats=6 --dpi-desync-fake-quic=""$BIN\quic_initial_www_google_com.bin"" --new"
$DISUDP4 = "--filter-udp=443 --hostlist=""$LISTS\discord.txt"" --dpi-desync=fake --dpi-desync-repeats=6 --dpi-desync-fake-quic=""$BIN\quic_initial_vk_com.bin"" --new"
$DISUDP5 = "--filter-udp=443 --hostlist=""$LISTS\discord.txt"" --dpi-desync=fake --dpi-desync-udplen-increment=10 --dpi-desync-repeats=7 --dpi-desync-udplen-pattern=0xDEADBEEF --dpi-desync-fake-quic=""$BIN\quic_initial_www_google_com.bin"" --new"
$DISUDP6 = "--filter-udp=443 --hostlist=""$LISTS\discord.txt"" --dpi-desync=fake,split2 --dpi-desync-udplen-increment=10 --dpi-desync-repeats=6 --dpi-desync-udplen-pattern=0xDEADBEEF --dpi-desync-fake-quic=""$BIN\quic_initial_www_google_com.bin"" --new"
$DISUDP7 = "--filter-udp=443 --hostlist=""$LISTS\discord.txt"" --dpi-desync=fake --dpi-desync-udplen-increment=10 --dpi-desync-repeats=6 --dpi-desync-udplen-pattern=0xDEADBEEF --dpi-desync-fake-quic=""$BIN\quic_initial_www_google_com.bin"" --new"
$DISUDP8 = "--filter-udp=443 --hostlist=""$LISTS\discord.txt"" --dpi-desync=fake --dpi-desync-udplen-increment=10 --dpi-desync-udplen-pattern=0xDEADBEEF --dpi-desync-fake-quic=""$BIN\quic_2.bin"" --dpi-desync-repeats=8 --dpi-desync-cutoff=n2 --new"
$DISUDP9 = "--filter-udp=443 --hostlist=""$LISTS\discord.txt"" --dpi-desync=fake,udplen --dpi-desync-udplen-increment=5 --dpi-desync-udplen-pattern=0xDEADBEEF --dpi-desync-fake-quic=""$BIN\quic_2.bin"" --dpi-desync-repeats=7 --dpi-desync-cutoff=n2 --new"

$DISIP1 = "--filter-udp=50000-50100 --ipset=""$LISTS\ipset-discord.txt"" --dpi-desync=fake --dpi-desync-any-protocol --dpi-desync-cutoff=d3 --dpi-desync-repeats=6 --new"
$DISIP2 = "--filter-udp=50000-65535 --ipset=""$LISTS\ipset-discord.txt"" --dpi-desync=fake --dpi-desync-any-protocol --dpi-desync-cutoff=d3 --dpi-desync-repeats=6 --new"
$DISIP3 = "--filter-udp=50000-59000 --dpi-desync=fake --dpi-desync-any-protocol --dpi-desync-cutoff=n2 --dpi-desync-fake-quic=""$BIN\quic_initial_www_google_com.bin"" --new"
$DISIP4 = "--filter-udp=50000-50099 --dpi-desync=fake --dpi-desync-any-protocol --dpi-desync-cutoff=d2 --dpi-desync-fake-quic=""$BIN\quic_1.bin"" --new"
$DISIP5 = "--filter-tcp=443 --ipset=""$LISTS\ipset-discord.txt"" --dpi-desync=syndata --dpi-desync-fake-syndata=""$BIN\tls_clienthello_3.bin"" --dpi-desync-autottl --new"
$DISIP6 = "--filter-udp=50000-50099 --ipset=""$LISTS\ipset-discord.txt"" --dpi-desync=fake --dpi-desync-repeats=6 --dpi-desync-any-protocol --dpi-desync-cutoff=n4 -- new"

$faceinsta = "--filter-tcp=443 --hostlist=""$LISTS\faceinsta.txt"" --dpi-desync=split2 --dpi-desync-split-seqovl=652 --dpi-desync-split-pos=2 --dpi-desync-split-seqovl-pattern=""$BIN\tls_clienthello_4.bin"" --new"

$other1 = "--filter-tcp=443 --hostlist=""$LISTS\other.txt"" --dpi-desync=fake,split2 --dpi-desync-split-seqovl=1 --dpi-desync-split-tls=sniext --dpi-desync-fake-tls=""$BIN\tls_clienthello_3.bin"" --dpi-desync-ttl=2 --new"
$other2 = "--filter-tcp=80 --hostlist=""$LISTS\other.txt"" --dpi-desync=fake,multisplit --dpi-desync-fooling=md5sig --dpi-desync-autottl --new"
$other3 = "--filter-tcp=443 --hostlist=""$LISTS\other.txt"" --dpi-desync=fake,multisplit --dpi-desync-split-seqovl=1 --dpi-desync-split-pos=1 --dpi-desync-fake-tls=""$BIN\tls_clienthello_vk_com.bin"" --dpi-desync-ttl=5 --new"
$other4 = "--filter-tcp=443 --hostlist=""$LISTS\other.txt"" --dpi-desync=fake,multisplit --dpi-desync-split-seqovl=1 --dpi-desync-split-pos=midsld-1 --dpi-desync-fooling=md5sig,badseq --dpi-desync-fake-tls=""$BIN\tls_clienthello_4.bin"" --dpi-desync-ttl=2 --new"

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

function Check-AndDownload-WinDivert {
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

function Invoke-ZapretStrategy {
    param(
        [string]$StrategyName,
        [string]$Arguments
    )

    Start-Sleep -Seconds 1
    $global:STRATEGY_STARTED = $true

    # Добавление проверки существования файла winws.exe
    if (-Not (Test-Path -Path "$BIN\winws.exe")) {
        Write-Error "Файл winws.exe не найден по пути: $BIN\winws.exe"
        return
    }

    # Попытка запуска процесса
    try {
        $process = Start-Process -FilePath "$BIN\winws.exe" -ArgumentList $Arguments -WindowStyle Minimized -PassThru -WorkingDirectory $PSScriptRoot
        # Проверка успешности запуска
        if ($process -eq $null) {
            Write-Error "Не удалось запустить winws.exe с аргументами: $Arguments"
            return
        }

        # Сохранение PID запущенного процесса
        #$process.Id | Out-File -FilePath "$PSScriptRoot\zapret_pid.txt" -Encoding UTF8
        Write-Host "Стратегия '$StrategyName' успешно загружена! PID: $($process.Id)"
    }
    catch {
        Write-Error "Ошибка при запуске winws.exe: $_"
    }
}

function Stop-Zapret {
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
    
    Start-Sleep -Seconds 1
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

function Restart-Discord {
    $discordProcesses = Get-Process discord -ErrorAction SilentlyContinue
    if ($discordProcesses) {
        foreach ($process in $discordProcesses) {
            Write-Host "Killing process with PID: $($process.Id)"
            Stop-Process -Force -Id $process.Id
        }
    } else {
        Write-Host "No Discord processes found."
    }

    Write-Host "Starting Discord..."
    try {
        Start-Process -FilePath "$env:AppData\Microsoft\Windows\Start Menu\Programs\Discord Inc\Discord.lnk"
    } catch {
        Write-Host "Дискорд не установлен."
    }
}

function Set-GoogleDNS {
    $PrimaryDNS = "8.8.8.8"
    $SecondaryDNS = "8.8.4.4"

    Write-Host "Изменение DNS для активных интерфейсов..."

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

function Set-ZapretDNS {
    $PrimaryDNS = "185.222.222.222"
    $SecondaryDNS = "45.11.45.11"

    Write-Host "Изменение DNS для активных интерфейсов..."

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
    $hostsPath = "$env:SystemRoot\System32\drivers\etc\hosts"

    $newHostsContent = @(
        "0.0.0.0 www.aomeitech.com",
        "185.15.211.203 bt.t-ru.org",
        "185.15.211.203 bt2.t-ru.org",
        "185.15.211.203 bt3.t-ru.org",
        "185.15.211.203 bt4.t-ru.org",
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

    $newHostsContent -join "`n" | Set-Content -Path $hostsPath -Encoding UTF8
    Write-Host "Файл hosts успешно обновлён."
}

function Check-Availability {
    param(
        [string]$Url,
        [string[]]$IPAddresses
    )

    # Check main URL using ping
    $pingResults = Test-Connection -ComputerName $Url -Count 4
    $totalSent = $pingResults.Count
    $totalReceived = ($pingResults | Where-Object {$_.StatusCode -eq 0}).Count  # 0 means success
    Write-Host "${Url}: Отправлено: $totalSent, Получено: $totalReceived" # Исправлено
    foreach ($result in $pingResults) {
        if ($result.StatusCode -eq 0) {
            Write-Host "`tДоступен (Latency: $($result.ResponseTime)ms)"
        } else {
            Write-Host "`tНедоступен"
        }
    }

    # Check IP addresses using ping
    if ($IPAddresses) {
        foreach ($ip in $IPAddresses) {
            $pingResults = Test-Connection -ComputerName $ip -Count 4
            $totalSent = $pingResults.Count
            $totalReceived = ($pingResults | Where-Object {$_.StatusCode -eq 0}).Count
            Write-Host "IP ${ip}: Отправлено: $totalSent, Получено: $totalReceived" # Исправлено
            foreach ($result in $pingResults) {
                if ($result.StatusCode -eq 0) {
                    Write-Host "`tДоступен (Latency: $($result.ResponseTime)ms)"
                } else {
                    Write-Host "`tНедоступен"
                }
            }
        }
    }
}

function Check-Discord {
    Write-Host "Проверка доступности Discord:"
    Check-Availability -Url "discord.com"
    Write-Host ""
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

    Write-Host "Проверка доступности YouTube:"
    Check-Availability -Url "www.youtube.com" -IPAddresses $youtubeIPs

    foreach ($address in $youtubeAddresses) {
        Check-Availability -Url $address
    }
    Write-Host ""

    # Check https://jnn-pa.googleapis.com using Invoke-WebRequest
    try {
        $response = Invoke-WebRequest -Uri "https://jnn-pa.googleapis.com" -Method GET
        Write-Output "Запрос https://jnn-pa.googleapis.com успешен: $($response.StatusCode)"
    } catch {
        if ($_.Exception.Response.StatusCode -eq 403) {
            Write-Output "Ошибка 403: ВЫ НЕ СМОЖЕТЕ СМОТРЕТЬ ЮТУБ с помощью сайта youtube.com ЧЕРЕЗ ZAPRET! Вам следует запустить Zapret, а после скачать Freetube по ссылке freetubeapp.io и смотреть видео там. Или скачайте для своего браузера скрипт Tampermonkey по ссылке: https://zapret.now.sh/script.user.js"
            $choice = Read-Host "Узнать подробнее? (введите цифру 1 если да / введите цифру 0 если нужно выйти)"
            if ($choice -eq "1") {
                Write-Host "Пройдите по ссылке, выполните установки и перезайдите в Zapret"
                Start-Sleep -Seconds 5
                Start-Process https://github.com/censorliber/youtube_unblock
            } elseif ($choice -eq "0") {
                Write-Host "Вы отменили установку скрипта, YouTube скорее всего не будет разблокирован"
            }
        } else {
            Write-Output $($_.Exception.Message)
            Write-Output "Если Вы видите ошибку 404, то Вы успешно сможете разблокировать YouTube через Zapret! Ничего дополнительно скачивать не требуется."
        }
    }
}

function Check-Update {
    # URL файла с актуальной версией
    $versionUrl = "https://filedn.eu/lFS6h5cBEsru02lgr5VwkTJ/Zapret/version.txt"

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
    Stop-Zapret
}

# Функция для включения/выключения автозапуска
function Toggle-Autostart {
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
        Invoke-ZapretStrategy -StrategyName $DefaultStrategyInfo.StrategyName -Arguments $DefaultStrategyInfo.ConfigArg
    }
}

if (!(Test-Administrator)) {
    Write-Host "Requesting administrator rights..."
    Start-Process powershell.exe -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$PSCommandPath`"" -Verb RunAs
    exit
}

Check-AndDownload-WinDivert
Show-Telegram
Start-DefaultStrategy

Write-Host "-----------------------"
Write-Host "ВЫБЕРИТЕ СТРАТЕГИЮ:"
Write-Host ""
Write-Host "0. Остановить Zapret"
Write-Host ""
Write-Host "1. Запустить стратегию от 06.01.2025 (разблокирует любые сайты)"
Write-Host "2. Запустить стратегию лайт v1 (лёгкая и быстрая, минимальный детект для античитов игр, разблокирует любые сайты)"
Write-Host "3. Запустить стратегию Discord TCP 80 (предпочтительно Ростелеком)"
Write-Host "4. Запустить стратегию Discord fake (предпочтительно Ростелеком)"
Write-Host "5. Запустить стратегию Discord fake и split (предпочтительно Уфанет)"
Write-Host "6. Запустить стратегию Discord fake и split2 (УльтиМейт фикс, предпочтительно Билайн и Ростелеком)"
Write-Host ""
Write-Host "7. Запустить стратегию split с sniext (предпочтительно ДомРу)"
Write-Host "8. Запустить стратегию split с badseq (предпочтительно ДомРу)"
Write-Host ""
Write-Host "9. Запустить стратегию split с badseq (предпочтительно Ростелеком и Мегафон)"
Write-Host "10. Запустить стратегию fake и split2, второй bin файл (предпочтительно Ростелеком)"
Write-Host ""
Write-Host "11. Запустить стратегию YouTube fake QUIC, bin файл google, больше размер пакетов, также YouTube fake"
Write-Host "12. Запустить стратегию YouTube fake QUIC, bin файл google, больше размер пакетов, также YouTube fake и split 2"
Write-Host ""
Write-Host "13. Запустить стратегию split с badseq (предпочтительно МГТС)"
Write-Host "14. Запустить стратегию split с badseq, дополнительно cutoff (предпочтительно МГТС или ЯлтаТВ)"
Write-Host "15. Запустить стратегию fake и split2, bin файл google (предпочтительно МГТС)"
Write-Host "16. Запустить стратегию fake и split2 bin файл quic_test_00 (предпочтительно МГТС)"
Write-Host ""
Write-Host "30. Запустить стратегию ультимейт конфиг ZL (разблокирует любые сайты)"
Write-Host "31. Запустить стратегию ультимейт конфиг v2 (разблокирует любые сайты)"
Write-Host ""
Write-Host ""
Write-Host "40. Включить / выключить автозапуск"
Write-Host ""
Write-Host "50 Проверить работу YouTube и Discord глобально! (если никакие стратегии не помогают)"
Write-Host ""
Write-Host "60. Очистить DNS (установить дефолтные) (помогает если после смены DNS сломался интернет)"
Write-Host "61. Сменить DNS на Google DNS (помогает если Вы этого ещё не сделали)"
Write-Host "62. Сменить DNS на SB DNS"
Write-Host ""
Write-Host "70. Отредактировать файл hosts (помогает разблокировать Instagram, Facebook, Twitter и т.д.)"
Write-Host ""

if (Check-Update) {
    # Предлагаем пользователю скачать обновление
    Write-Host "Доступно новое обновление! Текущая версия: $localVersion, Новая версия: $latestVersion"
    $choice = Read-Host "Вы можете скачать его прямо сейчас (введите цифру 1 если Вы согласны обновить программу / введите цифру 0 если против)"
    if ($choice -eq "1") {
        # Здесь код для скачивания и установки обновления
        Start-Process -FilePath "powershell.exe" -ArgumentList "-File `"$BIN\check_update.ps1`""
        Exit 0
    } elseif ($choice -eq "0") {
        Write-Host "ОБНОВЛЕНИЕ ОТМЕНЕНО! В БУДУЩЕМ ВЫ ДОЛЖНЫ СКАЧАТЬ НОВУЮ ВЕРСИЮ"
    } else {
        Exit 0
    }
}

do {
    $AutostartEnabled = Get-AutostartState
    $DefaultStrategyInfo = Get-DefaultStrategy
    $Host.UI.RawUI.WindowTitle = "Zapret $localVersion | Текущая стратегия - $StrategyName | Автозапуск - $AutostartEnabled | https://t.me/bypassblock"
    $userInput = Read-Host "Введите цифру (если Вы выбрали стратегию она автоматически станет стратегией по умолчанию)"

    if ($AutostartEnabled) {
            Write-Host "Важно: Запрет не применит новую выбранную стратегию пока Вы не перезапустите автозапуск через цифру 40!"
    } 

    switch ($userInput) {
        "0" {
            if ($AutostartEnabled) {
                    Write-Host "Приложение находится в автозапуске! Запрет выключается ТОЛЬКО через выключение автозапуска, наберите 40 чтобы убрать его из автозапуска!"
                    Write-Host "В будущих версиях эта ошибка исправится..."
            } else {
                    Stop-Zapret
                    Write-Host "ЗАПРЕТ ОСТАНОВЛЕН!"
            }
        }
        "1" {
              if ($AutostartEnabled) {
                    $DefaultConfigName = "06.01.2025"
                    $DefaultConfigArg = "--wf-tcp=80,443 --wf-udp=443,50000-50100 $YRTMP1 $YQ8 $YT10 $YGV3 $other1 $DISIP5 $DISTCP11 $DISUDP9 $UDP7 $YRTMP2 $faceinsta"
                    Set-DefaultStrategy -StrategyName $DefaultConfigName -ConfigArg $DefaultConfigArg
            } else {
                    Stop-Zapret
                    $DefaultConfigName = "06.01.2025"
                    $DefaultConfigArg = "--wf-tcp=80,443 --wf-udp=443,50000-50100 $YRTMP1 $YQ8 $YT10 $YGV3 $other1 $DISIP5 $DISTCP11 $DISUDP9 $UDP7 $YRTMP2 $faceinsta"
                    Invoke-ZapretStrategy -StrategyName $DefaultConfigName -Arguments $DefaultConfigArg
                    Set-DefaultStrategy -StrategyName $DefaultConfigName -ConfigArg $DefaultConfigArg
                    Restart-Discord
            }          
        }
        "2" {
               if ($AutostartEnabled) {
                    $DefaultConfigName = "lite orig v1"
                    $DefaultConfigArg = "--wf-tcp=80,443 --wf-udp=443,50000-50100 $faceinsta $TCP80 $YT11 $YQ9 $other3 $TCP443 $UDP8 $DISIP6"
                    Set-DefaultStrategy -StrategyName $DefaultConfigName -ConfigArg $DefaultConfigArg
            } else {
                    Stop-Zapret
                    $DefaultConfigName = "lite orig v1"
                    $DefaultConfigArg = "--wf-tcp=80,443 --wf-udp=443,50000-50100 $faceinsta $TCP80 $YT11 $YQ9 $other3 $TCP443 $UDP8 $DISIP6"
                    Invoke-ZapretStrategy -StrategyName $DefaultConfigName -Arguments $DefaultConfigArg
                    Set-DefaultStrategy -StrategyName $DefaultConfigName -ConfigArg $DefaultConfigArg
                    Restart-Discord
            }               
        }
        "3" {
            if ($AutostartEnabled) {
                    $DefaultConfigName = "Discord TCP 80"
                    $DefaultConfigArg = "--wf-tcp=80,443 --wf-udp=443,50000-59000 $YQ1 $YGV1 $YT1 $DISTCP80 $DISUDP2 $UDP2 $DISTCP2 $other1 $faceinsta"
                    Set-DefaultStrategy -StrategyName $DefaultConfigName -ConfigArg $DefaultConfigArg
            } else {
                    Stop-Zapret
                    $DefaultConfigName = "Discord TCP 80"
                    $DefaultConfigArg = "--wf-tcp=80,443 --wf-udp=443,50000-59000 $YQ1 $YGV1 $YT1 $DISTCP80 $DISUDP2 $UDP2 $DISTCP2 $other1 $faceinsta"
                    Invoke-ZapretStrategy -StrategyName $DefaultConfigName -Arguments $DefaultConfigArg
                    Set-DefaultStrategy -StrategyName $DefaultConfigName -ConfigArg $DefaultConfigArg
                    Restart-Discord
            }
        }
        "4" {
            if ($AutostartEnabled) {
                    $DefaultConfigName = "Discord fake"
                    $DefaultConfigArg = "--wf-tcp=80,443 --wf-udp=443,50000-59000 $YQ1 $YGV1 $YT1 $DISUDP1 $UDP1 $DISTCP1 $other1 $faceinsta"
                    Set-DefaultStrategy -StrategyName $DefaultConfigName -ConfigArg $DefaultConfigArg
            } else {
                    Stop-Zapret
                    $DefaultConfigName = "Discord fake"
                    $DefaultConfigArg = "--wf-tcp=80,443 --wf-udp=443,50000-59000 $YQ1 $YGV1 $YT1 $DISUDP1 $UDP1 $DISTCP1 $other1 $faceinsta"
                    Invoke-ZapretStrategy -StrategyName $DefaultConfigName -Arguments $DefaultConfigArg
                    Set-DefaultStrategy -StrategyName $DefaultConfigName -ConfigArg $DefaultConfigArg
                    Restart-Discord
            }
        }
        "5" {
            if ($AutostartEnabled) {
                    $DefaultConfigName = "Discord fake и split"
                    $DefaultConfigArg = "--wf-tcp=80,443 --wf-udp=443,50000-50100 $DISUDP3 $DISIP1 $DISTCP80 $DISTCP3 $YQ1 $YGV1 $YT2 $other1 $faceinsta"
                    Set-DefaultStrategy -StrategyName $DefaultConfigName -ConfigArg $DefaultConfigArg
            } else {
                    Stop-Zapret
                    $DefaultConfigName = "Discord fake и split"
                    $DefaultConfigArg = "--wf-tcp=80,443 --wf-udp=443,50000-50100 $DISUDP3 $DISIP1 $DISTCP80 $DISTCP3 $YQ1 $YGV1 $YT2 $other1 $faceinsta"
                    Invoke-ZapretStrategy -StrategyName $DefaultConfigName -Arguments $DefaultConfigArg
                    Set-DefaultStrategy -StrategyName $DefaultConfigName -ConfigArg $DefaultConfigArg
                    Restart-Discord
            }
        }
        "6" {
            if ($AutostartEnabled) {
                    $DefaultConfigName = "Ultimate Fix ALT Beeline-Rostelekom"
                    $DefaultConfigArg = "--wf-tcp=80,443 --wf-udp=443,50000-65535 $DISUDP4 $DISIP2 $DISTCP80 $DISTCP4 $YQ1 $YGV1 $YT2 $other1 $faceinsta"
                    Set-DefaultStrategy -StrategyName $DefaultConfigName -ConfigArg $DefaultConfigArg
            } else {
                    Stop-Zapret
                    $DefaultConfigName = "Ultimate Fix ALT Beeline-Rostelekom"
                    $DefaultConfigArg = "--wf-tcp=80,443 --wf-udp=443,50000-65535 $DISUDP4 $DISIP2 $DISTCP80 $DISTCP4 $YQ1 $YGV1 $YT2 $other1 $faceinsta"
                    Invoke-ZapretStrategy -StrategyName $DefaultConfigName -Arguments $DefaultConfigArg
                    Set-DefaultStrategy -StrategyName $DefaultConfigName -ConfigArg $DefaultConfigArg
                    Restart-Discord
            }
        }
        "7" {
            if ($AutostartEnabled) {
                    $DefaultConfigName = "split с sniext"
                    $DefaultConfigArg = "--wf-tcp=80,443 --wf-udp=443,50000-59000 $YQ2 $YGV3 $YT3 $DISTCP5 $DISUDP5 $DISIP3 $other1 $faceinsta"
                    Set-DefaultStrategy -StrategyName $DefaultConfigName -ConfigArg $DefaultConfigArg
            } else {
                    Stop-Zapret
                    $DefaultConfigName = "split с sniext"
                    $DefaultConfigArg = "--wf-tcp=80,443 --wf-udp=443,50000-59000 $YQ2 $YGV3 $YT3 $DISTCP5 $DISUDP5 $DISIP3 $other1 $faceinsta"
                    Invoke-ZapretStrategy -StrategyName $DefaultConfigName -Arguments $DefaultConfigArg
                    Set-DefaultStrategy -StrategyName $DefaultConfigName -ConfigArg $DefaultConfigArg
            }
        }
        "8" {
            if ($AutostartEnabled) {
                    $DefaultConfigName = "split с badseq"
                    $DefaultConfigArg = "--wf-tcp=80,443 --wf-udp=443,50000-59000 $YQ2 $YGV1 $YT4 $DISTCP5 $DISUDP5 $DISIP3 $other1 $faceinsta"
                    Set-DefaultStrategy -StrategyName $DefaultConfigName -ConfigArg $DefaultConfigArg
            } else {
                    Stop-Zapret
                    $DefaultConfigName = "split с badseq"
                    $DefaultConfigArg = "--wf-tcp=80,443 --wf-udp=443,50000-59000 $YQ2 $YGV1 $YT4 $DISTCP5 $DISUDP5 $DISIP3 $other1 $faceinsta"
                    Invoke-ZapretStrategy -StrategyName $DefaultConfigName -Arguments $DefaultConfigArg
                    Set-DefaultStrategy -StrategyName $DefaultConfigName -ConfigArg $DefaultConfigArg
            }
        }
        "9" {
            if ($AutostartEnabled) {
                    $DefaultConfigName = "Rostelecom & Megafon"
                    $DefaultConfigArg = "--wf-tcp=80,443 --wf-udp=443,50000-59000 $YQ2 $YT4 $DISUDP3 $UDP3 $DISTCP6 $other1 $faceinsta"
                    Set-DefaultStrategy -StrategyName $DefaultConfigName -ConfigArg $DefaultConfigArg
            } else {
                    Stop-Zapret
                    $DefaultConfigName = "Rostelecom & Megafon"
                    $DefaultConfigArg = "--wf-tcp=80,443 --wf-udp=443,50000-59000 $YQ2 $YT4 $DISUDP3 $UDP3 $DISTCP6 $other1 $faceinsta"
                    Invoke-ZapretStrategy -StrategyName $DefaultConfigName -Arguments $DefaultConfigArg
                    Set-DefaultStrategy -StrategyName $DefaultConfigName -ConfigArg $DefaultConfigArg
            }
        }
        "10" {
            if ($AutostartEnabled) {
                    $DefaultConfigName = "Rostelecom v2"
                    $DefaultConfigArg = "--wf-tcp=80,443 --wf-udp=443,50000-59000 $YQ3 $YT5 $DISUDP3 $UDP3 $DISTCP6 $other1 $faceinsta"
                    Set-DefaultStrategy -StrategyName $DefaultConfigName -ConfigArg $DefaultConfigArg
            } else {
                    Stop-Zapret
                    $DefaultConfigName = "Rostelecom v2"
                    $DefaultConfigArg = "--wf-tcp=80,443 --wf-udp=443,50000-59000 $YQ3 $YT5 $DISUDP3 $UDP3 $DISTCP6 $other1 $faceinsta"
                    Invoke-ZapretStrategy -StrategyName $DefaultConfigName -Arguments $DefaultConfigArg
                    Set-DefaultStrategy -StrategyName $DefaultConfigName -ConfigArg $DefaultConfigArg
            }
        }
        "11" {
            if ($AutostartEnabled) {
                    $DefaultConfigName = "Other v1"
                    $DefaultConfigArg = "--wf-l3=ipv4,ipv6 --wf-tcp=443 --wf-udp=443,50000-65535 $YQ4 $YT3 $DISTCP7 $DISUDP6 $UDP4 $other1 $faceinsta"
                    Set-DefaultStrategy -StrategyName $DefaultConfigName -ConfigArg $DefaultConfigArg
            } else {
                    Stop-Zapret
                    $DefaultConfigName = "Other v1"
                    $DefaultConfigArg = "--wf-l3=ipv4,ipv6 --wf-tcp=443 --wf-udp=443,50000-65535 $YQ4 $YT3 $DISTCP7 $DISUDP6 $UDP4 $other1 $faceinsta"
                    Invoke-ZapretStrategy -StrategyName $DefaultConfigName -Arguments $DefaultConfigArg
                    Set-DefaultStrategy -StrategyName $DefaultConfigName -ConfigArg $DefaultConfigArg
            }
        }
        "12" {
            if ($AutostartEnabled) {
                    $DefaultConfigName = "Other v2"
                    $DefaultConfigArg = "--wf-l3=ipv4,ipv6 --wf-tcp=443 --wf-udp=443,50000-65535 $YQ4 $YT6 $DISUDP7 $UDP5 $DISTCP8 $other1 $faceinsta"
                    Set-DefaultStrategy -StrategyName $DefaultConfigName -ConfigArg $DefaultConfigArg
            } else {
                    Stop-Zapret
                    $DefaultConfigName = "Other v2"
                    $DefaultConfigArg = "--wf-l3=ipv4,ipv6 --wf-tcp=443 --wf-udp=443,50000-65535 $YQ4 $YT6 $DISUDP7 $UDP5 $DISTCP8 $other1 $faceinsta"
                    Invoke-ZapretStrategy -StrategyName $DefaultConfigName -Arguments $DefaultConfigArg
                    Set-DefaultStrategy -StrategyName $DefaultConfigName -ConfigArg $DefaultConfigArg
            }
        }
        "13" {
            if ($AutostartEnabled) {
                    $DefaultConfigName = "MGTS v1"
                    $DefaultConfigArg = "--wf-tcp=80,443 --wf-udp=443,50000-50900 $YQ2 $YT7 $DISUDP5 $DISIP3 $DISTCP9 $other1 $faceinsta"
                    Set-DefaultStrategy -StrategyName $DefaultConfigName -ConfigArg $DefaultConfigArg
            } else {
                    Stop-Zapret
                    $DefaultConfigName = "MGTS v1"
                    $DefaultConfigArg = "--wf-tcp=80,443 --wf-udp=443,50000-50900 $YQ2 $YT7 $DISUDP5 $DISIP3 $DISTCP9 $other1 $faceinsta"
                    Invoke-ZapretStrategy -StrategyName $DefaultConfigName -Arguments $DefaultConfigArg
                    Set-DefaultStrategy -StrategyName $DefaultConfigName -ConfigArg $DefaultConfigArg
            }
        }
        "14" {
            if ($AutostartEnabled) {
                    $DefaultConfigName = "MGTS v2"
                    $DefaultConfigArg = "--wf-tcp=80,443 --wf-udp=443,50000-50900 $YT8 $DISTCP10 $YQ5 $DISUDP1 $UDP1 $other1 $faceinsta"
                    Set-DefaultStrategy -StrategyName $DefaultConfigName -ConfigArg $DefaultConfigArg
            } else {
                    Stop-Zapret
                    $DefaultConfigName = "MGTS v2"
                    $DefaultConfigArg = "--wf-tcp=80,443 --wf-udp=443,50000-50900 $YT8 $DISTCP10 $YQ5 $DISUDP1 $UDP1 $other1 $faceinsta"
                    Invoke-ZapretStrategy -StrategyName $DefaultConfigName -Arguments $DefaultConfigArg
                    Set-DefaultStrategy -StrategyName $DefaultConfigName -ConfigArg $DefaultConfigArg
            }
        }
        "15" {
            if ($AutostartEnabled) {
                    $DefaultConfigName = "MGTS v3"
                    $DefaultConfigArg = "--wf-tcp=80,443 --wf-udp=443,50000-50900 $YT1 $DISTCP10 $YQ5 $DISUDP1 $UDP1 $other1 $faceinsta"
                    Set-DefaultStrategy -StrategyName $DefaultConfigName -ConfigArg $DefaultConfigArg
            } else {
                    Stop-Zapret
                    $DefaultConfigName = "MGTS v3"
                    $DefaultConfigArg = "--wf-tcp=80,443 --wf-udp=443,50000-50900 $YT1 $DISTCP10 $YQ5 $DISUDP1 $UDP1 $other1 $faceinsta"
                    Invoke-ZapretStrategy -StrategyName $DefaultConfigName -Arguments $DefaultConfigArg
                    Set-DefaultStrategy -StrategyName $DefaultConfigName -ConfigArg $DefaultConfigArg
            }
        }
        "16" {
            if ($AutostartEnabled) {
                    $DefaultConfigName = "MGTS v4"
                    $DefaultConfigArg = "--wf-tcp=80,443 --wf-udp=443,50000-50900 $YQ1 $YGV3 $YT1 $DISUDP1 $UDP1 $DISTCP1 $other1 $faceinsta"
                    Set-DefaultStrategy -StrategyName $DefaultConfigName -ConfigArg $DefaultConfigArg
            } else {
                    Stop-Zapret
                    $DefaultConfigName = "MGTS v4"
                    $DefaultConfigArg = "--wf-tcp=80,443 --wf-udp=443,50000-50900 $YQ1 $YGV3 $YT1 $DISUDP1 $UDP1 $DISTCP1 $other1 $faceinsta"
                    Invoke-ZapretStrategy -StrategyName $DefaultConfigName -Arguments $DefaultConfigArg
                    Set-DefaultStrategy -StrategyName $DefaultConfigName -ConfigArg $DefaultConfigArg
            }
        }
        "30" {
            if ($AutostartEnabled) {
                    $DefaultConfigName = "Ultimate Config ZL"
                    $DefaultConfigArg = "--wf-tcp=80,443 --wf-udp=443,50000-50099 $YQ6 $YGV2 $YT9 $DISTCP11 $DISUDP8 $DISIP4 $other3 $faceinsta"
                    Set-DefaultStrategy -StrategyName $DefaultConfigName -ConfigArg $DefaultConfigArg
            } else {
                    Stop-Zapret
                    $DefaultConfigName = "Ultimate Config ZL"
                    $DefaultConfigArg = "--wf-tcp=80,443 --wf-udp=443,50000-50099 $YQ6 $YGV2 $YT9 $DISTCP11 $DISUDP8 $DISIP4 $other3 $faceinsta"
                    Invoke-ZapretStrategy -StrategyName $DefaultConfigName -Arguments $DefaultConfigArg
                    Set-DefaultStrategy -StrategyName $DefaultConfigName -ConfigArg $DefaultConfigArg
            }
        }
        "31" {
            if ($AutostartEnabled) {
                    $DefaultConfigName = "Ultimate Config v2"
                    $DefaultConfigArg = "--wf-tcp=80,443 --wf-udp=443,50000-50090 $YRTMP1 $YQ7 $DISIP5 $DISTCP12 $DISUDP9 $UDP7 $YGV3 $other2 $other4 $faceinsta"
                    Set-DefaultStrategy -StrategyName $DefaultConfigName -ConfigArg $DefaultConfigArg
            } else {
                    Stop-Zapret
                    $DefaultConfigName = "Ultimate Config v2"
                    $DefaultConfigArg = "--wf-tcp=80,443 --wf-udp=443,50000-50090 $YRTMP1 $YQ7 $DISIP5 $DISTCP12 $DISUDP9 $UDP7 $YGV3 $other2 $other4 $faceinsta"
                    Invoke-ZapretStrategy -StrategyName $DefaultConfigName -Arguments $DefaultConfigArg
                    Set-DefaultStrategy -StrategyName $DefaultConfigName -ConfigArg $DefaultConfigArg
            }
        }
        "40" {
            Toggle-Autostart
        }
        "50" {
            Check-Discord
            Check-YouTube
        }
        "60" {
            Reset-DNS
        }
        "61" {
            Set-GoogleDNS
        }
        "62" {
            Set-ZapretDNS
        }
        "70" {
            Edit-Hosts
        }
        default {
            Write-Host "Вы не выбрали правильную цифру!"
        }
    }
} while ($true)
