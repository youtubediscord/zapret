# ui/pages/__init__.py
"""Страницы контента для главного окна"""

from .home_page import HomePage
from .control_page import ControlPage
from .strategies_page_base import StrategiesPageBase
from .zapret2_orchestra_strategies_page import Zapret2OrchestraStrategiesPage
from .zapret2 import (
    Zapret2DirectControlPage,
    Zapret2PresetDetailPage,
    Zapret2StrategiesPageNew,
    Zapret2UserPresetsPage,
    StrategyDetailPage,
)
from .zapret1 import (
    Zapret1DirectControlPage,
    Zapret1PresetDetailPage,
    Zapret1StrategiesPage,
    Zapret1UserPresetsPage,
)
from .hostlist_page import HostlistPage
from .ipset_page import IpsetPage
from .blobs_page import BlobsPage
from .dpi_settings_page import DpiSettingsPage
from .autostart_page import AutostartPage
from .network_page import NetworkPage
from .hosts_page import HostsPage
from .appearance_page import AppearancePage
from .about_page import AboutPage
from .support_page import SupportPage
from .logs_page import LogsPage
from .premium_page import PremiumPage
from .blockcheck_page import BlockcheckPage
from .servers_page import ServersPage  # ✅ НОВАЯ СТРАНИЦА
from .custom_domains_page import CustomDomainsPage  # Страница управления other.user.txt
from .custom_ipset_page import CustomIpSetPage  # Страница управления ipset-all.user.txt
from .netrogat_page import NetrogatPage  # Страница управления netrogat.txt
from .connection_page import ConnectionTestPage
from .dns_check_page import DNSCheckPage
from .orchestra_page import OrchestraPage
from .orchestra import (
    OrchestraSettingsPage,
    OrchestraLockedPage,
    OrchestraBlockedPage,
    OrchestraWhitelistPage,
    OrchestraRatingsPage,
)
__all__ = [
    'HomePage',
    'ControlPage',
    'Zapret2OrchestraStrategiesPage',
    'StrategiesPageBase',
    'Zapret2StrategiesPageNew',  # Новая страница Zapret2 из zapret2/
    'Zapret2DirectControlPage',  # Управление для direct_zapret2 (вкладка внутри "Стратегии")
    'Zapret2PresetDetailPage',  # Подстраница конкретного пресета Z2
    'Zapret2UserPresetsPage',  # Пользовательские пресеты (direct_zapret2)
    'StrategyDetailPage',  # Страница детального просмотра стратегии
    'Zapret1DirectControlPage',  # Управление для direct_zapret1
    'Zapret1PresetDetailPage',  # Подстраница конкретного пресета Z1
    'Zapret1StrategiesPage',  # Стратегии для direct_zapret1
    'Zapret1UserPresetsPage',  # Пользовательские пресеты для direct_zapret1
    'HostlistPage',
    'IpsetPage',
    'BlobsPage',  # Управление блобами для Zapret 2
    'DpiSettingsPage',
    'AutostartPage',
    'NetworkPage',
    'HostsPage',
    'AppearancePage',
    'AboutPage',
    'SupportPage',
    'LogsPage',
    'PremiumPage',
    'BlockcheckPage',
    'ServersPage',  # ✅ НОВАЯ СТРАНИЦА
    'CustomDomainsPage',  # Страница управления other.user.txt
    'CustomIpSetPage',  # Страница управления ipset-all.user.txt
    'NetrogatPage',  # Страница управления netrogat.txt
    'ConnectionTestPage',
    'DNSCheckPage',  # Страница проверки DNS подмены
    'OrchestraPage',  # Страница оркестратора автообучения
    'OrchestraSettingsPage',  # Объединённая страница настроек оркестратора (вкладки)
    'OrchestraLockedPage',  # Страница залоченных стратегий оркестратора
    'OrchestraBlockedPage',  # Страница заблокированных стратегий оркестратора
    'OrchestraWhitelistPage',  # Страница белого списка оркестратора
    'OrchestraRatingsPage',  # Страница истории стратегий с рейтингами
]
