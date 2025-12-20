# hosts/proxy_domains.py
# Домены разбиты по сервисам для удобного быстрого выбора

# ═══════════════════════════════════════════════════════════════
# СЕРВИСЫ - каждый сервис содержит список своих доменов с IP
# ═══════════════════════════════════════════════════════════════

SERVICES = {
    "ChatGPT": {
        "chatgpt.com": "138.124.72.139",
        "ab.chatgpt.com": "138.124.72.139",
        "auth.openai.com": "138.124.72.139",
        "auth0.openai.com": "138.124.72.139",
        "platform.openai.com": "138.124.72.139",
        "cdn.oaistatic.com": "138.124.72.139",
        "files.oaiusercontent.com": "138.124.72.139",
        "cdn.auth0.com": "138.124.72.139",
        "tcr9i.chat.openai.com": "138.124.72.139",
        "webrtc.chatgpt.com": "138.124.72.139",
        "android.chat.openai.com": "138.124.72.139",
        "api.openai.com": "138.124.72.139",
        "sora.com": "138.124.72.139",
        "sora.chatgpt.com": "138.124.72.139",
        "videos.openai.com": "138.124.72.139",
        "us.posthog.com": "138.124.72.139",
    },
    
    "Gemini": {
        "gemini.google.com": "138.124.72.139",
        "alkalimakersuite-pa.clients6.google.com": "138.124.72.139",
        "aisandbox-pa.googleapis.com": "138.124.72.139",
        "webchannel-alkalimakersuite-pa.clients6.google.com": "138.124.72.139",
        "proactivebackend-pa.googleapis.com": "138.124.72.139",
        "o.pki.goog": "138.124.72.139",
        "labs.google": "138.124.72.139",
        "notebooklm.google": "138.124.72.139",
        "notebooklm.google.com": "138.124.72.139",
    },
    
    "Claude": {
        "claude.ai": "138.124.72.139",
        "api.claude.ai": "138.124.72.139",
        "anthropic.com": "138.124.72.139",
        "www.anthropic.com": "138.124.72.139",
        "api.anthropic.com": "138.124.72.139",
    },
    
    "Copilot": {
        "copilot.microsoft.com": "138.124.72.139",
        "sydney.bing.com": "138.124.72.139",
        "edgeservices.bing.com": "138.124.72.139",
        "rewards.bing.com": "138.124.72.139",
        "xsts.auth.xboxlive.com": "138.124.72.139",
    },
    
    "Grok": {
        "grok.com": "138.124.72.139",
        "assets.grok.com": "138.124.72.139",
        "accounts.x.ai": "138.124.72.139",
    },
    
    "Instagram": {
        "www.instagram.com": "157.240.225.174",
        "instagram.com": "157.240.225.174",
        "scontent.cdninstagram.com": "157.240.224.63",
        "scontent-hel3-1.cdninstagram.com": "157.240.224.63",
        "static.cdninstagram.com": "31.13.72.53",
        "b.i.instagram.com": "157.240.245.174",
    },
    
    "Facebook": {
        "facebook.com": "31.13.72.36",
        "www.facebook.com": "31.13.72.36",
        "static.xx.fbcdn.net": "31.13.72.12",
        "external-hel3-1.xx.fbcdn.net": "31.13.72.12",
        "scontent-hel3-1.xx.fbcdn.net": "31.13.72.12",
        "z-p42-chat-e2ee-ig.facebook.com": "157.240.245.174",
    },
    
    "Threads": {
        "threads.com": "157.240.224.63",
        "www.threads.com": "157.240.224.63",
    },
    
    "Spotify": {
        "api.spotify.com": "138.124.72.139",
        "xpui.app.spotify.com": "138.124.72.139",
        "appresolve.spotify.com": "138.124.72.139",
        "login5.spotify.com": "138.124.72.139",
        "gew1-spclient.spotify.com": "138.124.72.139",
        "gew1-dealer.spotify.com": "138.124.72.139",
        "spclient.wg.spotify.com": "138.124.72.139",
        "api-partner.spotify.com": "138.124.72.139",
        "aet.spotify.com": "138.124.72.139",
        "www.spotify.com": "138.124.72.139",
        "accounts.spotify.com": "138.124.72.139",
        "spotifycdn.com": "138.124.72.139",
        "open-exp.spotifycdn.com": "138.124.72.139",
        "www-growth.scdn.co": "138.124.72.139",
        "login.app.spotify.com": "138.124.72.139",
        "accounts.scdn.co": "138.124.72.139",
        "ap-gew1.spotify.com": "138.124.72.139",
    },
    
    "Notion": {
        "www.notion.so": "138.124.72.139",
        "notion.so": "138.124.72.139",
        "calendar.notion.so": "138.124.72.139",
    },
    
    "Twitch": {
        "usher.ttvnw.net": "138.124.72.139",
        "gql.twitch.tv": "138.124.72.139",
    },
    
    "DeepL": {
        "deepl.com": "138.124.72.139",
        "www.deepl.com": "138.124.72.139",
        "s.deepl.com": "138.124.72.139",
        "ita-free.www.deepl.com": "138.124.72.139",
        "experimentation.deepl.com": "138.124.72.139",
        "w.deepl.com": "138.124.72.139",
        "login-wall.deepl.com": "138.124.72.139",
        "gtm.deepl.com": "138.124.72.139",
        "checkout.www.deepl.com": "138.124.72.139",
    },
    
    "TikTok": {
        "www.tiktok.com": "138.124.72.139",
        "mcs-sg.tiktok.com": "138.124.72.139",
        "mon.tiktokv.com": "138.124.72.139",
    },
    
    "Netflix": {
        "www.netflix.com": "158.255.0.189",
        "netflix.com": "158.255.0.189",
    },
    
    "Canva": {
        "static.canva.com": "138.124.72.139",
        "content-management-files.canva.com": "138.124.72.139",
        "www.canva.com": "138.124.72.139",
    },
    
    "ProtonMail": {
        "protonmail.com": "3.66.189.153",
        "mail.proton.me": "3.66.189.153",
    },
    
    "ElevenLabs": {
        "elevenlabs.io": "138.124.72.139",
        "api.us.elevenlabs.io": "138.124.72.139",
        "elevenreader.io": "138.124.72.139",
    },
    
    "GitHub Copilot": {
        "api.individual.githubcopilot.com": "138.124.72.139",
        "proxy.individual.githubcopilot.com": "138.124.72.139",
    },
    
    "JetBrains": {
        "datalore.jetbrains.com": "50.7.85.221",
        "plugins.jetbrains.com": "107.150.34.100",
    },
    
    "Codeium": {
        "codeium.com": "138.124.72.139",
        "inference.codeium.com": "138.124.72.139",
    },
    
    "SoundCloud": {
        "soundcloud.com": "18.238.243.27",
        "style.sndcdn.com": "13.224.222.71",
        "a-v2.sndcdn.com": "3.164.206.34",
        "secure.sndcdn.com": "18.165.140.56",
    },
    
    "Manus": {
        "manus.im": "138.124.72.139",
        "api.manus.im": "138.124.72.139",
        "manuscdn.com": "138.124.72.139",
        "files.manuscdn.com": "138.124.72.139",
    },
    
    "Pixabay": {
        "pixabay.com": "138.124.72.139",
        "cdn.pixabay.com": "138.124.72.139",
    },
    
    "RuTracker": {
        "rutracker.org": "172.67.182.196",
        "static.rutracker.cc": "104.21.50.150",
    },
    
    "Rutor": {
        "rutor.info": "172.64.33.155",
        "d.rutor.info": "172.64.33.155",
        "rutor.is": "173.245.59.155",
        "rutor.org": "0.0.0.0",
    },
    
    "Другое": {
        "www.aomeitech.com": "0.0.0.0",
        "www.intel.com": "138.124.72.139",
        "www.dell.com": "138.124.72.139",
        "developer.nvidia.com": "138.124.72.139",
        "truthsocial.com": "204.12.192.221",
        "static-assets-1.truthsocial.com": "204.12.192.221",
        "autodesk.com": "94.131.119.85",
        "accounts.autodesk.com": "94.131.119.85",
        "www.hulu.com": "2.19.183.66",
        "hulu.com": "2.22.31.233",
        "anilib.me": "172.67.192.246",
        "ntc.party": "130.255.77.28",
        "pump.fun": "138.124.72.139",
        "frontend-api-v3.pump.fun": "138.124.72.139",
        "images.pump.fun": "138.124.72.139",
        "swap-api.pump.fun": "138.124.72.139",
        "www.elgato.com": "138.124.72.139",
        "info.dns.malw.link": "104.21.24.110",
        "only-fans.uk": "0.0.0.0",
        "only-fans.me": "0.0.0.0",
        "only-fans.wtf": "0.0.0.0",
    },
}

# ═══════════════════════════════════════════════════════════════
# PROXY_DOMAINS - объединённый словарь для совместимости
# ═══════════════════════════════════════════════════════════════

PROXY_DOMAINS = {}
for service_domains in SERVICES.values():
    PROXY_DOMAINS.update(service_domains)

# ═══════════════════════════════════════════════════════════════
# БЫСТРЫЙ ВЫБОР - ВСЕ сервисы для кнопок быстрого выбора
# Формат: (иконка_qtawesome, название, цвет_иконки)
# ═══════════════════════════════════════════════════════════════

QUICK_SERVICES = [
    # AI сервисы
    ("mdi.robot", "ChatGPT", "#10a37f"),
    ("mdi.google", "Gemini", "#4285f4"),
    ("fa5s.brain", "Claude", "#cc9b7a"),
    ("fa5b.microsoft", "Copilot", "#00bcf2"),
    ("fa5b.twitter", "Grok", "#1da1f2"),
    # Соцсети
    ("fa5b.instagram", "Instagram", "#e4405f"),
    ("fa5b.facebook-f", "Facebook", "#1877f2"),
    ("mdi.at", "Threads", "#ffffff"),
    ("mdi.music-note", "TikTok", "#ff0050"),
    # Медиа и развлечения
    ("fa5b.spotify", "Spotify", "#1db954"),
    ("fa5s.film", "Netflix", "#e50914"),
    ("fa5b.twitch", "Twitch", "#9146ff"),
    ("fa5b.soundcloud", "SoundCloud", "#ff5500"),
    # Продуктивность
    ("fa5s.sticky-note", "Notion", "#ffffff"),
    ("fa5s.language", "DeepL", "#0f2b46"),
    ("fa5s.palette", "Canva", "#00c4cc"),
    ("fa5s.envelope", "ProtonMail", "#6d4aff"),
    # Разработка
    ("fa5s.microphone-alt", "ElevenLabs", "#ffffff"),
    ("fa5b.github", "GitHub Copilot", "#ffffff"),
    ("fa5s.code", "JetBrains", "#fe315d"),
    ("fa5s.bolt", "Codeium", "#09b6a2"),
    # Торренты
    ("fa5s.magnet", "RuTracker", "#3498db"),
    ("fa5s.magnet", "Rutor", "#e74c3c"),
    # Другое
    ("fa5s.robot", "Manus", "#7c3aed"),
    ("fa5s.images", "Pixabay", "#00ab6c"),
    ("fa5s.box-open", "Другое", "#6c757d"),
]

# ═══════════════════════════════════════════════════════════════
# ПРЕСЕТЫ - готовые наборы сервисов
# ═══════════════════════════════════════════════════════════════

# Пресеты: (иконка_qtawesome, цвет, список_сервисов)
PRESETS = {
    "Минимум": ("fa5s.check-circle", "#60cdff", ["ChatGPT", "Instagram", "Spotify"]),
    "Все AI": ("fa5s.robot", "#60cdff", ["ChatGPT", "Gemini", "Claude", "Copilot", "Grok", "ElevenLabs", "GitHub Copilot", "Codeium"]),
    "Соцсети": ("fa5s.users", "#60cdff", ["Instagram", "Facebook", "Threads", "TikTok"]),
    "Популярное": ("fa5s.star", "#60cdff", ["ChatGPT", "Claude", "Instagram", "Spotify", "Notion", "DeepL"]),
}


def get_service_domains(service_name: str) -> dict:
    """Возвращает домены сервиса"""
    return SERVICES.get(service_name, {})


def get_preset_domains(preset_name: str) -> dict:
    """Возвращает все домены для пресета"""
    domains = {}
    preset_data = PRESETS.get(preset_name)
    if preset_data:
        # Новый формат: (icon, color, services)
        services = preset_data[2] if len(preset_data) >= 3 else []
        for service in services:
            domains.update(get_service_domains(service))
    return domains


def get_all_services() -> list:
    """Возвращает список всех сервисов"""
    return list(SERVICES.keys())
