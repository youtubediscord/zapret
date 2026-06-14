# dns/dns_core.py
"""
Базовые утилиты и DNSManager на Win32 API.
Быстрая работа без PowerShell/netsh.
"""
from __future__ import annotations

import ctypes, socket, struct, platform, sys, winreg
from ctypes import (
    Union,
    byref,
    c_ulong,
    c_ulonglong,
    c_ushort,
    c_void_p,
    c_wchar_p,
    wintypes,
    windll,
    POINTER,
    Structure,
)
from functools import lru_cache
from typing import List, Tuple, Dict, Optional
from log.log import log


# ──────────────────────────────────────────────────────────────────────
#  Win32 API структуры и константы
# ──────────────────────────────────────────────────────────────────────

# IP Helper API
iphlpapi = windll.iphlpapi

# Константы
MAX_ADAPTER_NAME_LENGTH = 256
MAX_ADAPTER_DESCRIPTION_LENGTH = 128
MAX_ADAPTER_ADDRESS_LENGTH = 8
ERROR_SUCCESS = 0
ERROR_BUFFER_OVERFLOW = 111
MIB_IF_TYPE_ETHERNET = 6
MIB_IF_TYPE_PPP = 23
MIB_IF_TYPE_LOOPBACK = 24
MIB_IF_TYPE_IEEE80211 = 71
DNS_INTERFACE_SETTINGS_VERSION1 = 0x0001
DNS_INTERFACE_SETTINGS_VERSION3 = 0x0003
DNS_SETTING_IPV6 = 0x0001
DNS_SETTING_NAMESERVER = 0x0002
DNS_SETTING_DOH = 0x1000
DNS_SERVER_PROPERTY_VERSION1 = 0x0001
DNS_DOH_SERVER_SETTINGS_ENABLE = 0x0002
DNS_DOH_SERVER_SETTINGS_FALLBACK_TO_UDP = 0x0004
DnsServerDohProperty = 1
_last_dns_winapi_error = ""

class IP_ADDR_STRING(Structure):
    pass

IP_ADDR_STRING._fields_ = [
    ('Next', POINTER(IP_ADDR_STRING)),
    ('IpAddress', c_wchar_p * 16),
    ('IpMask', c_wchar_p * 16),
    ('Context', wintypes.DWORD),
]

class IP_ADAPTER_INFO(Structure):
    pass

IP_ADAPTER_INFO._fields_ = [
    ('Next', POINTER(IP_ADAPTER_INFO)),
    ('ComboIndex', wintypes.DWORD),
    ('AdapterName', ctypes.c_char * (MAX_ADAPTER_NAME_LENGTH + 4)),
    ('Description', ctypes.c_char * (MAX_ADAPTER_DESCRIPTION_LENGTH + 4)),
    ('AddressLength', wintypes.UINT),
    ('Address', ctypes.c_byte * MAX_ADAPTER_ADDRESS_LENGTH),
    ('Index', wintypes.DWORD),
    ('Type', wintypes.UINT),
    ('DhcpEnabled', wintypes.UINT),
    ('CurrentIpAddress', POINTER(IP_ADDR_STRING)),
    ('IpAddressList', IP_ADDR_STRING),
    ('GatewayList', IP_ADDR_STRING),
    ('DhcpServer', IP_ADDR_STRING),
    ('HaveWins', wintypes.BOOL),
    ('PrimaryWinsServer', IP_ADDR_STRING),
    ('SecondaryWinsServer', IP_ADDR_STRING),
    ('LeaseObtained', ctypes.c_int64),
    ('LeaseExpires', ctypes.c_int64),
]

class GUID(Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", c_ushort),
        ("Data3", c_ushort),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class DNS_DOH_SERVER_SETTINGS(Structure):
    _fields_ = [
        ("Template", c_wchar_p),
        ("Flags", c_ulonglong),
    ]


class DNS_SERVER_PROPERTY_TYPES(Union):
    _fields_ = [
        ("DohSettings", POINTER(DNS_DOH_SERVER_SETTINGS)),
        ("DotSettings", c_void_p),
    ]


class DNS_SERVER_PROPERTY(Structure):
    _fields_ = [
        ("Version", wintypes.ULONG),
        ("ServerIndex", wintypes.ULONG),
        ("Type", wintypes.ULONG),
        ("Property", DNS_SERVER_PROPERTY_TYPES),
    ]


class DNS_INTERFACE_SETTINGS(Structure):
    _fields_ = [
        ("Version", wintypes.ULONG),
        ("Flags", c_ulonglong),
        ("Domain", c_wchar_p),
        ("NameServer", c_wchar_p),
        ("SearchList", c_wchar_p),
        ("RegistrationEnabled", wintypes.ULONG),
        ("RegisterAdapterName", wintypes.ULONG),
        ("EnableLLMNR", wintypes.ULONG),
        ("QueryAdapterName", wintypes.ULONG),
        ("ProfileNameServer", c_wchar_p),
    ]


class DNS_INTERFACE_SETTINGS3(Structure):
    _fields_ = [
        ("Version", wintypes.ULONG),
        ("Flags", c_ulonglong),
        ("Domain", c_wchar_p),
        ("NameServer", c_wchar_p),
        ("SearchList", c_wchar_p),
        ("RegistrationEnabled", wintypes.ULONG),
        ("RegisterAdapterName", wintypes.ULONG),
        ("EnableLLMNR", wintypes.ULONG),
        ("QueryAdapterName", wintypes.ULONG),
        ("ProfileNameServer", c_wchar_p),
        ("DisableUnconstrainedQueries", wintypes.ULONG),
        ("SupplementalSearchList", c_wchar_p),
        ("cServerProperties", wintypes.ULONG),
        ("ServerProperties", POINTER(DNS_SERVER_PROPERTY)),
        ("cProfileServerProperties", wintypes.ULONG),
        ("ProfileServerProperties", POINTER(DNS_SERVER_PROPERTY)),
    ]

# ──────────────────────────────────────────────────────────────────────
#  Константы исключений
# ──────────────────────────────────────────────────────────────────────
DEFAULT_EXCLUSIONS: list[str] = [
    "vmware", "outline-tap", "openvpn", "virtualbox", "hyper-v", "vmnet",
    "tap-windows", "tuntap", "wireguard", "protonvpn", "proton vpn",
    "radmin vpn", "hamachi", "nordvpn", "expressvpn", "surfshark",
    "pritunl", "zerotier", "tailscale", "loopback", "teredo", "isatap",
    "6to4", "bluetooth", "docker", "wsl", "vethernet", "wan miniport",
    "pppoe", "pptp", "l2tp", "sstp", "ndiswan", "raspppoe", "raspptp",
]

SOFTWARE_PNP_PREFIXES = (
    "ROOT\\",
    "SWD\\",
    "BTH\\",
    "HTREE\\",
)

PHYSICAL_NETWORK_PNP_PREFIXES = (
    "PCI\\",
    "USB\\",
    "PCMCIA\\",
)

WMI_DNS_ADAPTER_TYPE_IDS = {0, 9}
NATIVE_DNS_ADAPTER_TYPES = {MIB_IF_TYPE_ETHERNET, MIB_IF_TYPE_IEEE80211}

# ──────────────────────────────────────────────────────────────────────
#  Вспомогательные функции
# ──────────────────────────────────────────────────────────────────────

def _normalize_alias(alias: str) -> str:
    """Нормализация имени адаптера"""
    if not isinstance(alias, str):
        return alias
    repl = (
        ('\u00A0', ' '),
        ('\u200E', ''),
        ('\u200F', ''),
        ('\t', ' '),
    )
    for bad, good in repl:
        alias = alias.replace(bad, good)
    return alias.strip()

@lru_cache(maxsize=1)
def _get_dynamic_exclusions() -> list[str]:
    """Возвращает список исключений"""
    return [x.lower() for x in DEFAULT_EXCLUSIONS]

def refresh_exclusion_cache() -> None:
    """Сброс кэша исключений"""
    _get_dynamic_exclusions.cache_clear()

# ──────────────────────────────────────────────────────────────────────
#  Низкоуровневые Win32 функции
# ──────────────────────────────────────────────────────────────────────

def get_adapters_info_native() -> List[Dict]:
    """Получает информацию об адаптерах через IP Helper API"""
    adapters = []
    
    # Получаем размер буфера
    size = c_ulong(0)
    result = iphlpapi.GetAdaptersInfo(None, ctypes.byref(size))
    
    if result != ERROR_BUFFER_OVERFLOW:
        if result != ERROR_SUCCESS:
            log(f"GetAdaptersInfo failed: {result}", "ERROR")
            return []
    
    # Выделяем буфер
    buffer = ctypes.create_string_buffer(size.value)
    adapter_info = ctypes.cast(buffer, POINTER(IP_ADAPTER_INFO))
    
    # Получаем данные
    result = iphlpapi.GetAdaptersInfo(adapter_info, ctypes.byref(size))
    
    if result != ERROR_SUCCESS:
        log(f"GetAdaptersInfo failed: {result}", "ERROR")
        return []
    
    # Парсим адаптеры
    current = adapter_info
    while current:
        adapter = current.contents
        
        try:
            name = adapter.Description.decode('cp866', errors='ignore')
            adapter_name = adapter.AdapterName.decode('ascii', errors='ignore')
            
            # Пропускаем loopback
            if adapter.Type == MIB_IF_TYPE_LOOPBACK:
                current = adapter.Next
                continue
            
            adapter_dict = {
                'name': name,
                'adapter_name': adapter_name,
                'index': adapter.Index,
                'type': adapter.Type,
                'dhcp_enabled': bool(adapter.DhcpEnabled),
            }
            
            adapters.append(adapter_dict)
            
        except Exception as e:
            log(f"Error parsing adapter: {e}", "DEBUG")
        
        current = adapter.Next
    
    return adapters

def get_interface_guid_from_name(adapter_name: str) -> Optional[str]:
    """Получает GUID интерфейса по имени через реестр"""
    try:
        # Ищем в реестре
        reg_path = r"SYSTEM\CurrentControlSet\Control\Network\{4D36E972-E325-11CE-BFC1-08002BE10318}"
        
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path) as network_key:
            i = 0
            while True:
                try:
                    guid = winreg.EnumKey(network_key, i)
                    
                    # Пропускаем специальные ключи
                    if not guid.startswith('{'):
                        i += 1
                        continue
                    
                    try:
                        conn_path = f"{reg_path}\\{guid}\\Connection"
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, conn_path) as conn_key:
                            name, _ = winreg.QueryValueEx(conn_key, "Name")
                            
                            if _normalize_alias(name) == _normalize_alias(adapter_name):
                                return guid
                    except:
                        pass
                    
                    i += 1
                except OSError:
                    break
        
    except Exception as e:
        log(f"Error getting GUID for {adapter_name}: {e}", "DEBUG")
    
    return None


def _guid_from_string(guid: str) -> GUID:
    """Преобразует строковый GUID интерфейса в структуру WinAPI."""
    clean_guid = (guid or "").strip()
    if not clean_guid.startswith("{"):
        clean_guid = "{" + clean_guid
    if not clean_guid.endswith("}"):
        clean_guid = clean_guid + "}"

    result = GUID()
    hr = windll.ole32.CLSIDFromString(c_wchar_p(clean_guid), byref(result))
    if hr != 0:
        raise OSError(f"Invalid interface GUID: {guid}")
    return result


def _normalize_dns_servers(dns_servers: List[str]) -> list[str]:
    normalized: list[str] = []
    for raw_dns in dns_servers:
        dns = (raw_dns or "").strip()
        if not dns or dns in normalized:
            continue
        normalized.append(dns)
    return normalized


def _format_dns_servers(dns_servers: list[str], is_ipv6: bool) -> str:
    if not dns_servers:
        return ""
    separator = " " if is_ipv6 else ","
    return separator.join(dns_servers)


def get_last_dns_winapi_error() -> str:
    return _last_dns_winapi_error


def _set_last_dns_winapi_error(message: str) -> None:
    global _last_dns_winapi_error
    _last_dns_winapi_error = (message or "").strip()


def _format_winapi_result(api_name: str, result: int) -> str:
    detail = ""
    formatter = getattr(ctypes, "FormatError", None)
    if formatter is not None:
        try:
            detail = str(formatter(int(result)) or "").strip()
        except Exception:
            detail = ""
    if detail:
        return f"{api_name} вернул ошибку Windows {result}: {detail}"
    return f"{api_name} вернул ошибку Windows {result}"


def _build_doh_server_properties(
    dns_servers: list[str],
    doh_templates: dict[str, str],
) -> tuple[
    list[DNS_DOH_SERVER_SETTINGS],
    ctypes.Array[DNS_SERVER_PROPERTY] | None,
]:
    doh_settings: list[DNS_DOH_SERVER_SETTINGS] = []
    server_properties: list[DNS_SERVER_PROPERTY] = []

    for server_index, dns_server in enumerate(dns_servers):
        template = (doh_templates.get(dns_server) or "").strip()
        if not template:
            continue

        doh_settings.append(
            DNS_DOH_SERVER_SETTINGS(
                template,
                DNS_DOH_SERVER_SETTINGS_ENABLE
                | DNS_DOH_SERVER_SETTINGS_FALLBACK_TO_UDP,
            )
        )
        property_value = DNS_SERVER_PROPERTY_TYPES()
        property_value.DohSettings = ctypes.pointer(doh_settings[-1])
        server_properties.append(
            DNS_SERVER_PROPERTY(
                DNS_SERVER_PROPERTY_VERSION1,
                server_index,
                DnsServerDohProperty,
                property_value,
            )
        )

    if not server_properties:
        return doh_settings, None

    return doh_settings, (DNS_SERVER_PROPERTY * len(server_properties))(*server_properties)


def set_dns_via_winapi(
    guid: str,
    dns_servers: List[str],
    is_ipv6: bool = False,
    doh_templates: Optional[dict[str, str]] = None,
) -> bool:
    """Устанавливает DNS через SetInterfaceDnsSettings."""
    try:
        _set_last_dns_winapi_error("")
        normalized_servers = _normalize_dns_servers(dns_servers)
        name_server = _format_dns_servers(normalized_servers, is_ipv6)
        flags = DNS_SETTING_NAMESERVER
        if is_ipv6:
            flags |= DNS_SETTING_IPV6

        use_doh_settings = (
            not is_ipv6
            and bool(normalized_servers)
            and doh_templates is not None
            and is_doh_supported()
        )

        if use_doh_settings:
            flags |= DNS_SETTING_DOH
            doh_settings, property_array = _build_doh_server_properties(
                normalized_servers,
                doh_templates,
            )
            settings = DNS_INTERFACE_SETTINGS3()
            settings.Version = DNS_INTERFACE_SETTINGS_VERSION3
            settings.Flags = flags
            settings.NameServer = name_server
            if property_array is not None:
                settings.cServerProperties = len(property_array)
                settings.ServerProperties = property_array
        else:
            settings = DNS_INTERFACE_SETTINGS()
            settings.Version = DNS_INTERFACE_SETTINGS_VERSION1
            settings.Flags = flags
            settings.NameServer = name_server

        result = iphlpapi.SetInterfaceDnsSettings(
            _guid_from_string(guid),
            byref(settings),
        )
        if result != ERROR_SUCCESS:
            message = _format_winapi_result("SetInterfaceDnsSettings", int(result))
            _set_last_dns_winapi_error(message)
            log(message, "ERROR")
            return False

        return True

    except Exception as e:
        message = f"SetInterfaceDnsSettings не выполнен: {e}"
        _set_last_dns_winapi_error(message)
        log(message, "ERROR")
        return False

def notify_dns_change():
    """Уведомляет систему об изменении DNS через Win32 API"""
    try:
        # Используем SendNotifyMessage для уведомления оболочки
        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        
        user32 = windll.user32
        user32.SendNotifyMessageW(
            HWND_BROADCAST,
            WM_SETTINGCHANGE,
            0,
            "Environment"
        )
        
        return True
    except Exception as e:
        log(f"Error notifying DNS change: {e}", "DEBUG")
        return False

def flush_dns_cache_native() -> bool:
    """Очищает DNS кэш через Win32 API"""
    try:
        dnsapi = windll.dnsapi
        result = dnsapi.DnsFlushResolverCache()
        return True
    except Exception as e:
        log(f"Error flushing DNS cache: {e}", "DEBUG")
        return False

# DoH Template URLs
DOH_TEMPLATES = {
    "1.1.1.1": "https://cloudflare-dns.com/dns-query",
    "1.0.0.1": "https://cloudflare-dns.com/dns-query",
    "8.8.8.8": "https://dns.google/dns-query",
    "8.8.4.4": "https://dns.google/dns-query",
    "9.9.9.9": "https://dns.quad9.net/dns-query",
    "149.112.112.112": "https://dns.quad9.net/dns-query",
    "94.140.14.14": "https://dns.adguard.com/dns-query",
    "94.140.15.15": "https://dns.adguard.com/dns-query",
    "185.222.222.222": "https://doh.sb/dns-query",
    "45.11.45.11": "https://doh.sb/dns-query",
    "208.67.222.222": "https://doh.opendns.com/dns-query",
    "208.67.220.220": "https://doh.opendns.com/dns-query",
    "84.21.189.133": "https://dns.malw.link/dns-query",
    "64.188.98.242": "https://dns.malw.link/dns-query",
    "194.180.189.33": "https://dnsdoh.art:444/dns-query",
    # Xbox DNS (xbox-dns.ru)
    "111.88.96.50": "https://xbox-dns.ru/dns-query",
    "111.88.96.51": "https://xbox-dns.ru/dns-query",
    "87.228.47.200": "https://xbox-dns.ru/dns-query",
    "87.228.47.201": "https://xbox-dns.ru/dns-query",
    "176.99.11.77": "https://xbox-dns.ru/dns-query",
    "80.78.247.254": "https://xbox-dns.ru/dns-query",
    # Comss DNS (dns.comss.one)
    "83.220.169.155": "https://dns.comss.one/dns-query",
    "212.109.195.93": "https://dns.comss.one/dns-query",
}

def get_windows_version() -> Tuple[int, int, int]:
    """Получает версию Windows"""
    try:
        version = sys.getwindowsversion()
        return (version.major, version.minor, version.build)
    except:
        return (0, 0, 0)

def is_doh_supported() -> bool:
    """Проверяет, поддерживает ли система DoH"""
    try:
        major, minor, build = get_windows_version()
        
        # DNS_INTERFACE_SETTINGS3 появился в Windows 10 build 19645.
        # Windows 11 начинается с build 22000.
        if major == 10:
            if build >= 22000:  # Windows 11
                return True
            elif build >= 19645:  # Windows 10 Insider Preview с DoH API
                return True
        
        return False
    except:
        return False

def get_doh_template_for_dns(dns_ip: str) -> Optional[str]:
    """Возвращает DoH template URL для DNS IP"""
    return DOH_TEMPLATES.get(dns_ip)

def get_doh_settings_for_adapter(guid: str) -> Dict[str, any]:
    """Возвращает базовый статус DoH без чтения старых реестровых ключей."""
    return {
        "supported": is_doh_supported(),
        "enabled": False,
        "template": None,
        "auto_upgrade": False,
    }

def set_doh_for_adapter(guid: str, dns_ip: str, enable: bool = True, 
                        auto_upgrade: bool = True) -> bool:
    """Устанавливает DoH для адаптера"""
    template = get_doh_template_for_dns(dns_ip) if enable else None
    if enable and not template:
        log(f"No DoH template for {dns_ip}", "WARNING")
        return False

    return set_dns_via_winapi(
        guid,
        [dns_ip],
        is_ipv6=False,
        doh_templates={dns_ip: template} if template else {},
    )

def clear_doh_for_adapter(guid: str) -> bool:
    """Очищает настройки DoH для адаптера"""
    return set_dns_via_winapi(guid, [], is_ipv6=False, doh_templates={})

class DNSManager:
    """Менеджер DNS на основе Win32 API"""
    
    def __init__(self):
        self._wmi_conn = None
        self._adapter_cache = {}
        self._guid_cache = {}
    
    @property
    def wmi_conn(self):
        """Ленивая инициализация WMI"""
        if self._wmi_conn is None:
            try:
                import wmi
                self._wmi_conn = wmi.WMI()
            except:
                self._wmi_conn = False
        return self._wmi_conn if self._wmi_conn else None
    
    @staticmethod
    def should_ignore_adapter(name: str, description: str) -> bool:
        """Проверяет, нужно ли игнорировать адаптер"""
        name = _normalize_alias(name)
        description = _normalize_alias(description)
        
        for pattern in _get_dynamic_exclusions():
            if pattern in name.lower() or pattern in description.lower():
                return True
        return False

    @staticmethod
    def is_supported_dns_adapter(
        name: str,
        description: str,
        *,
        pnp_device_id: str = "",
        service_name: str = "",
        adapter_type_id: int | None = None,
        native_type: int | None = None,
    ) -> bool:
        """Проверяет, можно ли менять DNS на этом адаптере."""
        if DNSManager.should_ignore_adapter(name, description):
            return False

        pnp_upper = _normalize_alias(pnp_device_id or "").upper()
        service_lower = _normalize_alias(service_name or "").lower()

        if service_lower and any(
            pattern in service_lower
            for pattern in _get_dynamic_exclusions()
        ):
            return False

        if native_type is not None:
            try:
                return int(native_type) in NATIVE_DNS_ADAPTER_TYPES
            except (TypeError, ValueError):
                return False

        if pnp_upper:
            if pnp_upper.startswith(SOFTWARE_PNP_PREFIXES):
                return False
            if pnp_upper.startswith(PHYSICAL_NETWORK_PNP_PREFIXES):
                return True

        if adapter_type_id is not None:
            try:
                return int(adapter_type_id) in WMI_DNS_ADAPTER_TYPE_IDS
            except (TypeError, ValueError):
                return False

        return False
    
    def get_network_adapters_fast(
        self,
        include_ignored: bool = False,
        include_disconnected: bool = True
    ) -> List[Tuple[str, str]]:
        """Быстрое получение списка адаптеров через WMI"""
        adapters = []
        
        # Пробуем WMI
        if self.wmi_conn:
            try:
                for adapter in self.wmi_conn.Win32_NetworkAdapter(PhysicalAdapter=True):
                    if not adapter.NetConnectionID or not adapter.Description:
                        continue
                    
                    # Проверяем статус подключения
                    if not include_disconnected and adapter.NetConnectionStatus != 2:
                        continue
                    
                    alias = _normalize_alias(adapter.NetConnectionID)
                    desc = adapter.Description
                    
                    pnp_device_id = str(getattr(adapter, "PNPDeviceID", "") or "")
                    service_name = str(getattr(adapter, "ServiceName", "") or "")
                    adapter_type_id = getattr(adapter, "AdapterTypeID", None)

                    # Проверяем исключения и оставляем только обычные Wi-Fi/Ethernet.
                    if not include_ignored and not self.is_supported_dns_adapter(
                        alias,
                        desc,
                        pnp_device_id=pnp_device_id,
                        service_name=service_name,
                        adapter_type_id=adapter_type_id,
                    ):
                        continue
                    
                    adapters.append((adapter.NetConnectionID, desc))
                    
                return adapters
                
            except Exception as e:
                log(f"WMI error: {e}", "DEBUG")
        
        # Fallback на нативный API
        try:
            native_adapters = get_adapters_info_native()
            
            for adapter in native_adapters:
                name = adapter['name']
                
                if not include_ignored and not self.is_supported_dns_adapter(
                    name,
                    name,
                    native_type=adapter.get("type"),
                ):
                    continue
                
                adapters.append((name, name))
                
        except Exception as e:
            log(f"Native API error: {e}", "ERROR")
        
        return adapters
    
    def get_adapter_guid(self, adapter_name: str) -> Optional[str]:
        """Получает GUID адаптера с кешированием"""
        norm_name = _normalize_alias(adapter_name)
        
        if norm_name in self._guid_cache:
            return self._guid_cache[norm_name]
        
        guid = get_interface_guid_from_name(adapter_name)
        
        if guid:
            self._guid_cache[norm_name] = guid
        
        return guid
    
    def get_current_dns(self, adapter_name: str, address_family: str = "IPv4") -> List[str]:
        """Получает текущие DNS серверы через реестр"""
        try:
            guid = self.get_adapter_guid(adapter_name)
            if not guid:
                log(f"GUID not found for {adapter_name}", "DEBUG")
                return []
            
            is_ipv6 = (address_family.lower() == "ipv6")
            
            if is_ipv6:
                reg_path = f"SYSTEM\\CurrentControlSet\\Services\\Tcpip6\\Parameters\\Interfaces\\{guid}"
            else:
                reg_path = f"SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters\\Interfaces\\{guid}"
            
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path, 0,
                               winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
                try:
                    dns_string, _ = winreg.QueryValueEx(key, "NameServer")
                    
                    if dns_string:
                        # DNS могут быть разделены запятыми/пробелами/точкой с запятой.
                        dns_list = [
                            ip.strip()
                            for ip in dns_string.replace(';', ',').replace(' ', ',').split(',')
                            if ip.strip()
                        ]
                        return dns_list
                    
                except FileNotFoundError:
                    pass
            
            return []
            
        except Exception as e:
            log(f"Error getting DNS for {adapter_name}: {e}", "DEBUG")
            return []
    
    def get_all_dns_info_fast(self, adapter_names: List[str]) -> Dict[str, Dict[str, List[str]]]:
        """Быстрое получение DNS для нескольких адаптеров"""
        result = {}
        
        for name in adapter_names:
            norm_name = _normalize_alias(name)
            result[norm_name] = {
                "ipv4": self.get_current_dns(name, "IPv4"),
                "ipv6": self.get_current_dns(name, "IPv6")
            }
        
        return result
    
    def set_custom_dns(
        self,
        adapter_name: str,
        primary_dns: str,
        secondary_dns: Optional[str] = None,
        address_family: str = "IPv4"
    ) -> Tuple[bool, str]:
        """Устанавливает пользовательские DNS через WinAPI"""
        try:
            guid = self.get_adapter_guid(adapter_name)
            if not guid:
                return False, "GUID not found"
            
            dns_list = [primary_dns]
            if secondary_dns:
                dns_list.append(secondary_dns)
            
            is_ipv6 = (address_family.lower() == "ipv6")

            doh_templates = None
            if not is_ipv6:
                doh_templates = {
                    dns: template
                    for dns in dns_list
                    if (template := get_doh_template_for_dns((dns or "").strip()))
                }

            success = set_dns_via_winapi(
                guid,
                dns_list,
                is_ipv6,
                doh_templates=doh_templates if not is_ipv6 else None,
            )
            
            if success:
                notify_dns_change()
                return True, "OK"
            else:
                return False, "WinAPI update failed"
            
        except Exception as e:
            return False, str(e)
    
    def set_auto_dns(self, adapter_name: str, address_family: Optional[str] = None) -> Tuple[bool, str]:
        """Сбрасывает DNS на автоматический режим"""
        try:
            guid = self.get_adapter_guid(adapter_name)
            if not guid:
                return False, "GUID not found"
            
            families = ["IPv4", "IPv6"] if address_family is None else [address_family]
            errors: list[str] = []
            
            for family in families:
                is_ipv6 = (family.lower() == "ipv6")
                success = set_dns_via_winapi(
                    guid,
                    [],
                    is_ipv6,
                    doh_templates={} if not is_ipv6 else None,
                )
                if not success:
                    detail = get_last_dns_winapi_error()
                    if detail:
                        errors.append(
                            "Не удалось вернуть DNS в автоматический режим "
                            f"для адаптера «{adapter_name}» ({family}). {detail}"
                        )
                    else:
                        errors.append(
                            "Не удалось вернуть DNS в автоматический режим "
                            f"для адаптера «{adapter_name}» ({family})."
                        )

            if errors:
                return False, " ".join(errors)
            
            notify_dns_change()
            return True, "OK"
            
        except Exception as e:
            return False, str(e)

    def get_doh_info(self, adapter_name: str) -> Dict[str, any]:
        """Получает информацию о DoH для адаптера"""
        guid = self.get_adapter_guid(adapter_name)
        if not guid:
            return {'supported': False, 'enabled': False}
        
        return get_doh_settings_for_adapter(guid)
    
    def set_doh(self, adapter_name: str, dns_ip: str, enable: bool = True) -> Tuple[bool, str]:
        """Включает/выключает DoH для адаптера"""
        try:
            guid = self.get_adapter_guid(adapter_name)
            if not guid:
                return False, "GUID not found"
            
            if not is_doh_supported():
                return False, "DoH not supported on this Windows version"
            
            success = set_doh_for_adapter(guid, dns_ip, enable)
            
            if success:
                return True, "OK"
            else:
                return False, "Failed to set DoH"
                
        except Exception as e:
            return False, str(e)
    
    def clear_doh(self, adapter_name: str) -> Tuple[bool, str]:
        """Очищает настройки DoH для адаптера"""
        try:
            guid = self.get_adapter_guid(adapter_name)
            if not guid:
                return False, "GUID not found"
            
            success = clear_doh_for_adapter(guid)
            return (True, "OK") if success else (False, "Failed")
            
        except Exception as e:
            return False, str(e)
            
    @staticmethod
    def flush_dns_cache() -> Tuple[bool, str]:
        """Очищает DNS кэш"""
        success = flush_dns_cache_native()
        return (success, "OK" if success else "Failed")
