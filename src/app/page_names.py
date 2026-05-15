"""
Именованные константы для страниц окна.
Используй этот Enum вместо числовых индексов.
"""

from enum import Enum, auto


class PageName(Enum):
    """Имена страниц в pages_stack (QStackedWidget)

    Порядок значений НЕ ВАЖЕН - это просто уникальные идентификаторы.
    Фактический индекс в стеке определяется порядком добавления виджетов.
    """

    # === Основные страницы ===
    # Zapret 2: управление -> мои пресеты/raw preset или настройка preset-а через profiles
    ZAPRET2_MODE_CONTROL = auto()
    ZAPRET2_USER_PRESETS = auto()
    ZAPRET2_PRESET_RAW_EDITOR = auto()
    ZAPRET2_PRESET_SETUP = auto()
    ZAPRET2_PROFILE_SETUP = auto()

    # Zapret 1: зеркальный путь, отличается только strategy внутри profile
    ZAPRET1_MODE_CONTROL = auto()
    ZAPRET1_USER_PRESETS = auto()
    ZAPRET1_PRESET_RAW_EDITOR = auto()
    ZAPRET1_PRESET_SETUP = auto()
    ZAPRET1_PROFILE_SETUP = auto()

    HOSTLIST = auto()                # Листы (Hostlist + IPset)
    BLOBS = auto()                   # Блобы
    DPI_SETTINGS = auto()            # Настройки DPI

    # === Мои списки ===
    NETROGAT = auto()                # Исключения (netrogat.txt)
    CUSTOM_DOMAINS = auto()          # Мои hostlist (lists/user/other.txt)
    CUSTOM_IPSET = auto()            # Мои ipset (lists/user/ipset-all.txt)

    # === Настройки системы ===
    AUTOSTART = auto()               # Автозапуск
    NETWORK = auto()                 # Сеть
    HOSTS = auto()                   # Разблокировка сервисов
    BLOCKCHECK = auto()              # BlockCheck
    APPEARANCE = auto()              # Оформление
    PREMIUM = auto()                 # Донат/Premium
    LOGS = auto()                    # Логи
    SERVERS = auto()                 # Серверы обновлений
    ABOUT = auto()                   # О программе
    SUPPORT = auto()                 # Поддержка (GitHub Discussions и каналы сообщества)

    # === Telegram Proxy ===
    TELEGRAM_PROXY = auto()          # Telegram WebSocket Proxy

    # === Оркестратор (автообучение) ===
    ORCHESTRA = auto()               # Оркестр - главная
    ORCHESTRA_SETTINGS = auto()      # Настройки оркестратора (вкладки: залоченные, заблокированные, белый список, рейтинги)
