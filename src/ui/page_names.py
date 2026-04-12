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
    ZAPRET2_DIRECT_CONTROL = auto()  # Zapret 2 Direct: управление (главная вкладка в "Стратегии")
    ZAPRET2_DIRECT = auto()          # Zapret 2 Direct стратегии
    ZAPRET1_DIRECT_CONTROL = auto()  # Zapret 1 Direct: управление (главная вкладка)
    ZAPRET1_DIRECT = auto()          # Zapret 1 Direct стратегии
    ZAPRET1_USER_PRESETS = auto()    # Zapret 1 Direct: пользовательские пресеты
    ZAPRET1_STRATEGY_DETAIL = auto() # Zapret 1 Direct: детали стратегии для категории
    ZAPRET2_STRATEGY_DETAIL = auto()         # Детальный просмотр стратегии
    ZAPRET2_PRESET_DETAIL = auto()   # Zapret 2 Direct: подстраница пресета
    ZAPRET1_PRESET_DETAIL = auto()   # Zapret 1 Direct: подстраница пресета
    HOSTLIST = auto()                # Листы (Hostlist + IPset)
    BLOBS = auto()                   # Блобы
    DPI_SETTINGS = auto()            # Настройки DPI
    ZAPRET2_USER_PRESETS = auto()      # Zapret 2 Direct: пользовательские пресеты

    # === Мои списки ===
    NETROGAT = auto()                # Исключения (netrogat.txt)
    CUSTOM_DOMAINS = auto()          # Мои hostlist (other.user.txt)
    CUSTOM_IPSET = auto()            # Мои ipset (ipset-all.user.txt)

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
