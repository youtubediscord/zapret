"""
Именованные константы для навигации по страницам.
Используй эти Enum вместо числовых индексов!

Пример использования:
    from ui.page_names import PageName, SectionName, SECTION_TO_PAGE

    # В main_window.py:
    self.show_page(PageName.LOGS)

    # В sidebar.py:
    page = SECTION_TO_PAGE[SectionName.LOGS]
"""

from enum import Enum, auto
from typing import Optional


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
    IPSET = auto()                   # Legacy alias -> Листы
    BLOBS = auto()                   # Блобы
    DPI_SETTINGS = auto()            # Настройки DPI
    ZAPRET2_USER_PRESETS = auto()      # Zapret 2 Direct: пользовательские пресеты

    # === Мои списки ===
    NETROGAT = auto()                # Исключения (netrogat.txt)
    CUSTOM_DOMAINS = auto()          # Мои hostlist (other.txt)
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


class SectionName(Enum):
    """Имена секций в sidebar (навигационные кнопки)

    Секции - это кнопки в боковой панели. Они могут быть:
    - Обычные (открывают страницу)
    - Collapsible (разворачивают подменю)
    - Header (заголовок группы, не кликабельный)
    """

    # === Главное меню ===
    CONTROL = auto()                 # Управление

    # === Стратегии (collapsible группа) ===
    STRATEGIES = auto()              # Заголовок группы (collapsible)
    HOSTLIST = auto()                # - Листы
    IPSET = auto()                   # - Legacy alias (скрыт в UI)
    BLOBS = auto()                   # - Блобы
    ORCHESTRA_SETTINGS = auto()      # - Настройки оркестратора (вкладки)
    DPI_SETTINGS = auto()            # - Настройки DPI
    DIRECT_RUN = auto()              # - Прямой запуск (только direct_zapret2)

    # === Мои списки (collapsible группа) ===
    MY_LISTS_HEADER = auto()         # Заголовок группы (header, не страница!)
    NETROGAT = auto()                # - Исключения
    CUSTOM_HOSTLIST = auto()         # - Мои hostlist
    CUSTOM_IPSET = auto()            # - Мои ipset

    # === Основные пункты ===
    AUTOSTART = auto()               # Автозапуск
    NETWORK = auto()                 # Сеть
    TELEGRAM_PROXY = auto()          # Telegram Proxy

    # === Диагностика (collapsible группа) ===
    DIAGNOSTICS = auto()             # Заголовок группы (collapsible)
    DNS_CHECK = auto()               # - DNS подмена

    # === Остальные пункты ===
    HOSTS = auto()                   # Hosts
    BLOCKCHECK = auto()              # BlockCheck
    APPEARANCE = auto()              # Оформление
    PREMIUM = auto()                 # Донат
    LOGS = auto()                    # Логи
    SERVERS = auto()                 # Обновления
    ABOUT = auto()                   # О программе
    SUPPORT = auto()                 # Поддержка (подпункт "О программе")


# Маппинг Section -> Page (какую страницу открывать при клике на секцию)
# None означает что секция collapsible - при клике определяется динамически в main_window
SECTION_TO_PAGE: dict[SectionName, Optional[PageName]] = {
    SectionName.CONTROL: PageName.CONTROL,
    SectionName.STRATEGIES: None,  # Collapsible группа, целевая страница определяется по методу запуска
    SectionName.HOSTLIST: PageName.HOSTLIST,
    SectionName.IPSET: PageName.HOSTLIST,
    SectionName.BLOBS: PageName.BLOBS,
    SectionName.ORCHESTRA_SETTINGS: PageName.ORCHESTRA_SETTINGS,
    SectionName.DPI_SETTINGS: PageName.DPI_SETTINGS,
    SectionName.DIRECT_RUN: PageName.ZAPRET2_DIRECT,
    SectionName.MY_LISTS_HEADER: None,  # Заголовок, нет страницы!
    SectionName.NETROGAT: PageName.NETROGAT,
    SectionName.CUSTOM_HOSTLIST: PageName.CUSTOM_DOMAINS,
    SectionName.CUSTOM_IPSET: PageName.CUSTOM_IPSET,
    SectionName.AUTOSTART: PageName.AUTOSTART,
    SectionName.NETWORK: PageName.NETWORK,
    SectionName.TELEGRAM_PROXY: PageName.TELEGRAM_PROXY,
    SectionName.DIAGNOSTICS: PageName.BLOCKCHECK,
    SectionName.DNS_CHECK: PageName.BLOCKCHECK,
    SectionName.HOSTS: PageName.HOSTS,
    SectionName.BLOCKCHECK: PageName.BLOCKCHECK,
    SectionName.APPEARANCE: PageName.APPEARANCE,
    SectionName.PREMIUM: PageName.PREMIUM,
    SectionName.LOGS: PageName.LOGS,
    SectionName.SERVERS: PageName.SERVERS,
    SectionName.ABOUT: PageName.ABOUT,
    SectionName.SUPPORT: PageName.SUPPORT,
}


# Collapsible секции (которые можно сворачивать)
COLLAPSIBLE_SECTIONS: set[SectionName] = {
    SectionName.STRATEGIES,
    SectionName.MY_LISTS_HEADER,
    SectionName.DIAGNOSTICS,
    SectionName.ABOUT,
}


# Подсекции для каждой collapsible группы
SECTION_CHILDREN: dict[SectionName, list[SectionName]] = {
    SectionName.STRATEGIES: [
        SectionName.DIRECT_RUN,
        SectionName.HOSTLIST,
        SectionName.BLOBS,
        SectionName.ORCHESTRA_SETTINGS,
        SectionName.DPI_SETTINGS,
    ],
    SectionName.MY_LISTS_HEADER: [
        SectionName.NETROGAT,
        SectionName.CUSTOM_HOSTLIST,
        SectionName.CUSTOM_IPSET,
    ],
    SectionName.DIAGNOSTICS: [],
    SectionName.ABOUT: [
        SectionName.SERVERS,
        SectionName.SUPPORT,
    ],
}


# Секции которые показываются только в режиме оркестратора
ORCHESTRA_ONLY_SECTIONS: set[SectionName] = {
    SectionName.ORCHESTRA_SETTINGS,
}


# Страницы стратегий (для переключения по режиму запуска)
STRATEGY_PAGES: set[PageName] = {
    PageName.ZAPRET2_DIRECT_CONTROL,
    PageName.ZAPRET2_DIRECT,
    PageName.ZAPRET2_USER_PRESETS,
    PageName.ZAPRET2_STRATEGY_DETAIL,
    PageName.ZAPRET2_PRESET_DETAIL,

    PageName.ZAPRET1_DIRECT_CONTROL,
    PageName.ZAPRET1_DIRECT,
    PageName.ZAPRET1_USER_PRESETS,
    PageName.ZAPRET1_STRATEGY_DETAIL,
    PageName.ZAPRET1_PRESET_DETAIL,
    PageName.ORCHESTRA,
}
