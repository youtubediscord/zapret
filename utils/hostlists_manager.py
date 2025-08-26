# utils/hostlists_manager.py

import json
import os
from typing import Set, List

from config import OTHER_PATH, OTHER2_PATH, reg
from log import log

# Ключи реестра для хостлистов
_HOSTLISTS_KEY = r"Software\Zapret"
_HOSTLISTS_SERVICES = "HostlistsServices"  # JSON строка с выбранными сервисами
_HOSTLISTS_CUSTOM = "HostlistsCustom"      # JSON строка с пользовательскими доменами

# Базовые домены (всегда включены)
BASE_DOMAINS_TEXT = """
1.1.1.1
4pda.ws
5sim.net
adtidy.org
amazon.com
amazonaws.com
animego.org
aol.com
archive.org
articles.sk
bbc.com
bellingcat.com
bigvideo.net
bravotube.tv
btdig.com
cdn.betterttv.net
cdn.frankerfacez.com
cdn.hsmedia.ru
cdn.strapsco.com
cdn.vigo.one
cdn77.com
cdnbunny.org
cdninstagram.com
cdnst.net
cloudflare-ech.com
cloudflare.com
codenames.game
coursera.org
cryptpad.fr
currenttime.tv
delfi.lv
dept.one
detectportal.firefox.com
donationalerts.com
doppiocdn.live
doppiocdn.media
downdetector.com
doxa.team
dpidetector.org
dtf.ru
dw.com
e621.net
element.io
erome.com
escapefromtarkov.com
etahub.com
exitgames.com
eyeofgod.bot
eyezgod.ru
facebook.com
fbcdn.net
fbsbx.com
fburl.com
flibusta.is
flibusta.site
fonts.googleapis.com
f95zone.to
gifer.com
glaznews.com
googleads.g.doubleclick.net
hd2.lordfilm-ru.net
hentai-img.com
hmvmania.com
holod.media
hrw.org
i.kym-cdn.com
idelreal.org
indigogobot.com
ingest.sentry.io
instagram.com
invizible.net
jut.su
krymr.com
lantern.io
link.usersbox.io
linkedin.com
lordfilm.llc
lordfilms.day
matrix.org
maven.neoforged.net
medium.com
meduza.io
minecraftrating.ru
moscowtimes.ru
mullvad.net
mytpn.net
news.google.com
nexusmods.com
nnmclub.to
nnmstatic.win
notion.so
novayagazeta.eu
ntc.party
onlinesim.io
ooklaserver.net
otzovik.com
oxu.az
papervpn.io
patreon.com
phncdn.com
phpmyadmin.net
play.google.com
prostovpn.org
proton.me
protonmail.com
protonvpn.com
psiphon.ca
quora.com
radiofrance.fr
rapidgator.net
re-russia.net
republic.ru
reutersagency.com
rferl.org
roskomsvoboda.org
rtmps.youtube.com
rule34.xxx
rumble.com
rutor.info
rutor.is
rutracker.cc
rutracker.org
rutracker.wiki
save4k.top
signal.org
singlelogin.cc
sms-activate.guru
sndcdn.com
soundcloud.cloud
soundcloud.com
spankbang.com
speedtest.net
static.doubleclick.net
store-steam.ru
streamable.com
svoboda.org
t-ru.org
t.co
te-st.org
thebell.io
theins.ru
tntracker.org
torproject.org
tuta.com
twimg.com
twitter.com
udemy.com
unian.net
vector.im
viber.com
vpngate.net
vpngen.org
vpnguild.org
web.archive.org
wixmp.com
x.com
xhamster.com
xnxx.com
xvideos-cdn.com
xvideos.com
yande.re
z-lib.gs
z-lib.id
z-lib.io
z-library.cc
z-library.sk
ziffstatic.com
zlibrary.to
znanija.com
"""

# Предустановленные домены сервисов
PREDEFINED_DOMAINS = {
    'steam': {
        'name': '🎮 Steam',
        'domains': [
            'store.steampowered.com',
            'steamcommunity.com',
            'steampowered.com',
            'steam-chat.com',
            'steamgames.com',
            'steamusercontent.com',
            'steamcontent.com',
            'steamstatic.com',
            'akamaihd.net',
            'steamcdn-a.akamaihd.net',
            'steam-api.com',
            'steamserver.net',
            'valve.net',
            'valvesoftware.com',
            'dota2.com',
            'csgo.com',
            'counter-strike.net',
            'steamcommunity-a.akamaihd.net',
            'cdn.cloudflare.steamstatic.com',
            'steamstore-a.akamaihd.net',
        ]
    },
    'telegram': {
        'name': '✈️ Telegram',
        'domains': [
            'telegram.org',
            'telegram.me',
            't.me',
            'telegra.ph',
            'telesco.pe',
            'telegram-cdn.org',
            'core.telegram.org',
            'desktop.telegram.org',
            'web.telegram.org',
            'updates.tdesktop.com',
            'venus.web.telegram.org',
            'flora.web.telegram.org',
            'vesta.web.telegram.org',
            'aurora.web.telegram.org',
            'tdesktop.com',
            'cdn.tlgr.org',
        ]
    },
    'whatsapp': {
        'name': '💬 WhatsApp', 
        'domains': [
            'whatsapp.com',
            'whatsapp.net',
            'wa.me',
            'web.whatsapp.com',
            'www.whatsapp.com',
            'api.whatsapp.com',
            'chat.whatsapp.com',
            'w1.web.whatsapp.com',
            'w2.web.whatsapp.com',
            'w3.web.whatsapp.com',
            'w4.web.whatsapp.com',
            'w5.web.whatsapp.com',
            'w6.web.whatsapp.com',
            'w7.web.whatsapp.com',
            'w8.web.whatsapp.com',
        ]
    },
    'twitch': {
        'name': '🎥 Twitch',
        'domains': [
            'twitch.tv',
            'twitch.com',
            'twitchcdn.net',
            'twitchsvc.net',
            'jtvnw.net',
            'ttvnw.net',
            'twitch-ext.rootonline.de',
            'ext-twitch.tv',
            'pubster.twitch.tv',
            'app.twitch.tv',
            'player.twitch.tv',
            'clips.twitch.tv',
            'gql.twitch.tv',
            'vod-secure.twitch.tv',
            'usher.ttvnw.net',
            'video-weaver.fra02.hls.ttvnw.net',
        ]
    }
}

def get_base_domains() -> List[str]:
    """Возвращает список базовых доменов"""
    return [
        domain.strip() 
        for domain in BASE_DOMAINS_TEXT.strip().split('\n') 
        if domain.strip() and not domain.strip().startswith('#')
    ]

def save_hostlists_settings(selected_services: Set[str], custom_domains: List[str]) -> bool:
    """Сохраняет настройки хостлистов в реестр"""
    try:
        # Сохраняем выбранные сервисы
        services_json = json.dumps(list(selected_services))
        if not reg(_HOSTLISTS_KEY, _HOSTLISTS_SERVICES, services_json):
            log("Ошибка сохранения сервисов в реестр", "❌ ERROR")
            return False
        
        # Сохраняем пользовательские домены
        custom_json = json.dumps(custom_domains)
        if not reg(_HOSTLISTS_KEY, _HOSTLISTS_CUSTOM, custom_json):
            log("Ошибка сохранения пользовательских доменов в реестр", "❌ ERROR")
            return False
        
        log(f"Сохранено в реестр: {len(selected_services)} сервисов, {len(custom_domains)} доменов", "INFO")
        return True
        
    except Exception as e:
        log(f"Ошибка сохранения настроек хостлистов: {e}", "❌ ERROR")
        return False

def load_hostlists_settings() -> tuple[Set[str], List[str]]:
    """Загружает настройки хостлистов из реестра"""
    selected_services = set()
    custom_domains = []
    
    try:
        # Загружаем выбранные сервисы
        services_json = reg(_HOSTLISTS_KEY, _HOSTLISTS_SERVICES)
        if services_json:
            services_list = json.loads(services_json)
            selected_services = set(services_list)
            log(f"Загружено из реестра: {len(selected_services)} сервисов", "DEBUG")
        
        # Загружаем пользовательские домены
        custom_json = reg(_HOSTLISTS_KEY, _HOSTLISTS_CUSTOM)
        if custom_json:
            custom_domains = json.loads(custom_json)
            log(f"Загружено из реестра: {len(custom_domains)} пользовательских доменов", "DEBUG")
            
    except Exception as e:
        log(f"Ошибка загрузки настроек хостлистов: {e}", "⚠ WARNING")
    
    return selected_services, custom_domains

def rebuild_hostlists_from_registry():
    """Перестраивает файлы other.txt и other2.txt из настроек в реестре"""
    try:
        log("Перестройка хостлистов из реестра...", "INFO")
        
        # Загружаем настройки из реестра
        selected_services, custom_domains = load_hostlists_settings()
        
        # Создаем папку lists если её нет
        os.makedirs(os.path.dirname(OTHER_PATH), exist_ok=True)
        
        # --- Перестраиваем other.txt ---
        all_domains = set(get_base_domains())  # Базовые домены
        
        # Добавляем домены выбранных сервисов
        for service_id in selected_services:
            if service_id in PREDEFINED_DOMAINS:
                service_domains = PREDEFINED_DOMAINS[service_id]['domains']
                all_domains.update(service_domains)
                log(f"Добавлены домены сервиса {service_id}: {len(service_domains)} шт.", "DEBUG")
        
        # Записываем other.txt
        with open(OTHER_PATH, 'w', encoding='utf-8') as f:
            for domain in sorted(all_domains):
                f.write(f"{domain}\n")
        
        log(f"Создан other.txt: {len(all_domains)} доменов", "✅ SUCCESS")
        
        # --- Перестраиваем other2.txt ---
        with open(OTHER2_PATH, 'w', encoding='utf-8') as f:
            for domain in sorted(custom_domains):
                f.write(f"{domain}\n")
        
        log(f"Создан other2.txt: {len(custom_domains)} доменов", "✅ SUCCESS")
        
        return True
        
    except Exception as e:
        log(f"Ошибка перестройки хостлистов: {e}", "❌ ERROR")
        return False

def ensure_hostlists_exist():
    """Проверяет существование файлов хостлистов и создает их если нужно"""
    try:
        # Создаем папку lists если её нет
        os.makedirs(os.path.dirname(OTHER_PATH), exist_ok=True)
        
        # Если файлы существуют и не пустые - не трогаем
        other_exists = os.path.exists(OTHER_PATH) and os.path.getsize(OTHER_PATH) > 0
        other2_exists = os.path.exists(OTHER2_PATH)  # other2.txt может быть пустым
        
        if other_exists and other2_exists:
            log("Файлы хостлистов существуют", "DEBUG")
            return True
        
        # Если файлов нет - создаем из реестра или с дефолтными значениями
        log("Создание отсутствующих файлов хостлистов...", "INFO")
        
        if not other_exists:
            # Пробуем загрузить из реестра
            selected_services, _ = load_hostlists_settings()
            
            # Если в реестре пусто - используем дефолтные значения
            if not selected_services:
                log("Настройки хостлистов не найдены в реестре, используем базовые", "INFO")
            
            # Создаем other.txt
            all_domains = set(get_base_domains())
            
            for service_id in selected_services:
                if service_id in PREDEFINED_DOMAINS:
                    all_domains.update(PREDEFINED_DOMAINS[service_id]['domains'])
            
            with open(OTHER_PATH, 'w', encoding='utf-8') as f:
                for domain in sorted(all_domains):
                    f.write(f"{domain}\n")
            
            log(f"Создан other.txt с {len(all_domains)} доменами", "✅ SUCCESS")
        
        if not other2_exists:
            # Создаем пустой other2.txt если его нет
            with open(OTHER2_PATH, 'w', encoding='utf-8') as f:
                # Загружаем пользовательские домены из реестра
                _, custom_domains = load_hostlists_settings()
                for domain in sorted(custom_domains):
                    f.write(f"{domain}\n")
            
            log(f"Создан other2.txt", "✅ SUCCESS")
        
        return True
        
    except Exception as e:
        log(f"Ошибка создания файлов хостлистов: {e}", "❌ ERROR")
        return False

def startup_hostlists_check():
    """Проверка и восстановление хостлистов при запуске программы"""
    try:
        log("=== Проверка хостлистов при запуске ===", "🔧 HOSTLISTS")
        
        # 1. Проверяем существование файлов
        ensure_hostlists_exist()
        
        # 2. Если есть настройки в реестре - применяем их
        selected_services, custom_domains = load_hostlists_settings()
        
        if selected_services or custom_domains:
            log(f"Найдены настройки в реестре: {len(selected_services)} сервисов, {len(custom_domains)} доменов", "INFO")
            # Перестраиваем файлы из реестра
            rebuild_hostlists_from_registry()
        else:
            log("Настройки хостлистов в реестре не найдены, используются существующие файлы", "INFO")
        
        return True
        
    except Exception as e:
        log(f"Ошибка при проверке хостлистов: {e}", "❌ ERROR")

        return False

