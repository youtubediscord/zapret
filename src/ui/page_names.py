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
    CONTROL = auto()                 # Управление DPI
    ZAPRET2_MODE_CONTROL = auto()  # Zapret 2 mode: управление
    ZAPRET2_MODE = auto()          # Zapret 2 mode: profiles
    ZAPRET1_MODE_CONTROL = auto()  # Zapret 1 mode: управление (главная вкладка)
    ZAPRET1_MODE = auto()          # Zapret 1 mode: profiles
    ZAPRET1_USER_PRESETS = auto()    # Zapret 1 mode: пользовательские пресеты
    ZAPRET1_PROFILE_DETAIL = auto()  # Zapret 1 mode: детали profile
    ZAPRET2_PROFILE_DETAIL = auto()  # Zapret 2 mode: детали profile
    ZAPRET2_PRESET_DETAIL = auto()   # Zapret 2 mode: подстраница пресета
    ZAPRET1_PRESET_DETAIL = auto()   # Zapret 1 mode: подстраница пресета
    HOSTLIST = auto()                # Листы (Hostlist + IPset)
    BLOBS = auto()                   # Блобы
    DPI_SETTINGS = auto()            # Настройки DPI
    ZAPRET2_USER_PRESETS = auto()      # Zapret 2 mode: пользовательские пресеты

    # === Мои списки ===
    NETROGAT = auto()                # Исключения (netrogat.txt)
    CUSTOM_DOMAINS = auto()          # Мои hostlist (lists/user/other.txt)
    CUSTOM_IPSET = auto()            # Мои ipset (lists/user/ipset-all.txt)

    # === Настройки системы ===
    AUTOSTART = auto()               # Автозапуск
    NETWORK = auto()                 # Сеть
    DNS_CHECK = auto()               # DNS подмена
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
