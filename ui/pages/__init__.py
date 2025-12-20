# ui/pages/__init__.py
"""Страницы контента для главного окна"""

from .home_page import HomePage
from .control_page import ControlPage
from .strategies_page import StrategiesPage
from .hostlist_page import HostlistPage
from .ipset_page import IpsetPage
from .blobs_page import BlobsPage
from .editor_page import EditorPage
from .dpi_settings_page import DpiSettingsPage
from .autostart_page import AutostartPage
from .network_page import NetworkPage
from .hosts_page import HostsPage
from .appearance_page import AppearancePage
from .about_page import AboutPage
from .logs_page import LogsPage
from .premium_page import PremiumPage
from .blockcheck_page import BlockcheckPage
from .servers_page import ServersPage  # ✅ НОВАЯ СТРАНИЦА
from .custom_domains_page import CustomDomainsPage  # Страница управления other2.txt
from .custom_ipset_page import CustomIpSetPage  # Страница управления my-ipset.txt
from .netrogat_page import NetrogatPage  # Страница управления netrogat.txt
from .connection_page import ConnectionTestPage
from .dns_check_page import DNSCheckPage
from .orchestra_page import OrchestraPage
from .orchestra_locked_page import OrchestraLockedPage
from .orchestra_blocked_page import OrchestraBlockedPage
from .orchestra_whitelist_page import OrchestraWhitelistPage
from .orchestra_ratings_page import OrchestraRatingsPage

__all__ = [
    'HomePage',
    'ControlPage', 
    'StrategiesPage',
    'HostlistPage',
    'IpsetPage',
    'BlobsPage',  # Управление блобами для Zapret 2
    'EditorPage',
    'DpiSettingsPage',
    'AutostartPage',
    'NetworkPage',
    'HostsPage',
    'AppearancePage',
    'AboutPage',
    'LogsPage',
    'PremiumPage',
    'BlockcheckPage',
    'ServersPage',  # ✅ НОВАЯ СТРАНИЦА
    'CustomDomainsPage',  # Страница управления other2.txt
    'CustomIpSetPage',  # Страница управления my-ipset.txt
    'NetrogatPage',  # Страница управления netrogat.txt
    'ConnectionTestPage',
    'DNSCheckPage',  # Страница проверки DNS подмены
    'OrchestraPage',  # Страница оркестратора автообучения
    'OrchestraLockedPage',  # Страница залоченных стратегий оркестратора
    'OrchestraBlockedPage',  # Страница заблокированных стратегий оркестратора
    'OrchestraWhitelistPage',  # Страница белого списка оркестратора
    'OrchestraRatingsPage',  # Страница истории стратегий с рейтингами
]

