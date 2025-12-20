# dns/dns_core.py
"""
Базовые утилиты и DNSManager на Win32 API.
Быстрая работа без PowerShell/netsh.
"""
from __future__ import annotations

import ctypes, socket, struct, platform, sys, winreg
from ctypes import wintypes, windll, POINTER, Structure, c_ulong, c_wchar_p
from functools import lru_cache
from typing import List, Tuple, Dict, Optional
from log import log

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

# ──────────────────────────────────────────────────────────────────────
#  Константы исключений
# ──────────────────────────────────────────────────────────────────────
DEFAULT_EXCLUSIONS: list[str] = [
    "vmware", "outline-tap", "openvpn", "virtualbox", "hyper-v", "vmnet",
    "tap-windows", "tuntap", "wireguard", "protonvpn", "proton vpn",
    "radmin vpn", "hamachi", "nordvpn", "expressvpn", "surfshark",
    "pritunl", "zerotier", "tailscale", "loopback", "teredo", "isatap",
    "6to4", "bluetooth", "docker", "wsl", "vethernet"
]

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

def set_dns_via_registry(guid: str, dns_servers: List[str], is_ipv6: bool = False) -> bool:
    """Устанавливает DNS через реестр (быстрее чем netsh)"""
    try:
        if is_ipv6:
            reg_path = f"SYSTEM\\CurrentControlSet\\Services\\Tcpip6\\Parameters\\Interfaces\\{guid}"
        else:
            reg_path = f"SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters\\Interfaces\\{guid}"
        
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path, 0, 
                           winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY) as key:
            
            if dns_servers:
                # Устанавливаем DNS
                dns_string = ",".join(dns_servers)
                winreg.SetValueEx(key, "NameServer", 0, winreg.REG_SZ, dns_string)
                
                # Отключаем DHCP для DNS
                try:
                    winreg.SetValueEx(key, "RegisterAdapterName", 0, winreg.REG_DWORD, 0)
                except:
                    pass
            else:
                # Очищаем DNS (автоматический режим)
                try:
                    winreg.DeleteValue(key, "NameServer")
                except:
                    pass
        
        return True
        
    except Exception as e:
        log(f"Error setting DNS via registry: {e}", "ERROR")
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
}

# DoH настройки
DOH_AUTO = 0  # Автоматический выбор
DOH_DISABLED = 1  # Отключен
DOH_ENABLED_AUTO_FALLBACK = 2  # Включен с fallback на обычный DNS
DOH_ENABLED_ONLY = 3  # Только DoH, без fallback

# Добавим функции проверки DoH:

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
        
        # Windows 11 (build 22000+) или Windows 10 build 19628+
        if major == 10:
            if build >= 22000:  # Windows 11
                return True
            elif build >= 19628:  # Windows 10 Insider Preview с DoH
                return True
        
        return False
    except:
        return False

def get_doh_template_for_dns(dns_ip: str) -> Optional[str]:
    """Возвращает DoH template URL для DNS IP"""
    return DOH_TEMPLATES.get(dns_ip)

def get_doh_settings_for_adapter(guid: str) -> Dict[str, any]:
    """Получает настройки DoH для адаптера"""
    try:
        # Путь к настройкам DoH в реестре
        reg_path = f"SYSTEM\\CurrentControlSet\\Services\\Dnscache\\InterfaceSpecificParameters\\{guid}\\DohInterfaceSettings\\Doh"
        
        result = {
            'supported': is_doh_supported(),
            'enabled': False,
            'template': None,
            'auto_upgrade': False
        }
        
        if not result['supported']:
            return result
        
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path, 0,
                               winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
                
                # Проверяем DohFlags (0=авто, 1=выкл, 2=вкл с fallback, 3=только DoH)
                try:
                    flags, _ = winreg.QueryValueEx(key, "DohFlags")
                    result['enabled'] = (flags in [DOH_ENABLED_AUTO_FALLBACK, DOH_ENABLED_ONLY])
                except:
                    pass
                
                # Получаем template
                try:
                    template, _ = winreg.QueryValueEx(key, "DohTemplate")
                    result['template'] = template
                except:
                    pass
                
                # Auto upgrade (автоматическое обновление до DoH)
                try:
                    auto, _ = winreg.QueryValueEx(key, "DohAutoUpgrade")
                    result['auto_upgrade'] = bool(auto)
                except:
                    pass
                    
        except FileNotFoundError:
            # Настройки DoH не заданы для этого адаптера
            pass
        
        return result
        
    except Exception as e:
        log(f"Error getting DoH settings: {e}", "DEBUG")
        return {
            'supported': False,
            'enabled': False,
            'template': None,
            'auto_upgrade': False
        }

def set_doh_for_adapter(guid: str, dns_ip: str, enable: bool = True, 
                        auto_upgrade: bool = True) -> bool:
    """Устанавливает DoH для адаптера"""
    try:
        if not is_doh_supported():
            log("DoH not supported on this Windows version", "WARNING")
            return False
        
        # Получаем DoH template для DNS
        template = get_doh_template_for_dns(dns_ip)
        if not template and enable:
            log(f"No DoH template for {dns_ip}", "WARNING")
            return False
        
        # Путь к настройкам DoH
        reg_path = f"SYSTEM\\CurrentControlSet\\Services\\Dnscache\\InterfaceSpecificParameters\\{guid}\\DohInterfaceSettings\\Doh"
        
        try:
            # Создаем/открываем ключ
            with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, reg_path, 0,
                                   winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY) as key:
                
                if enable:
                    # Включаем DoH
                    # DohFlags: 2 = включен с fallback на обычный DNS
                    winreg.SetValueEx(key, "DohFlags", 0, winreg.REG_DWORD, 
                                     DOH_ENABLED_AUTO_FALLBACK)
                    
                    # Устанавливаем template
                    winreg.SetValueEx(key, "DohTemplate", 0, winreg.REG_SZ, template)
                    
                    # Auto upgrade
                    if auto_upgrade:
                        winreg.SetValueEx(key, "DohAutoUpgrade", 0, winreg.REG_DWORD, 1)
                    
                    log(f"DoH enabled for GUID {guid}: {template}", "DNS")
                else:
                    # Отключаем DoH
                    winreg.SetValueEx(key, "DohFlags", 0, winreg.REG_DWORD, DOH_DISABLED)
                    log(f"DoH disabled for GUID {guid}", "DNS")
                
                # Уведомляем систему
                notify_dns_change()
                flush_dns_cache_native()
                
                return True
                
        except Exception as e:
            log(f"Error setting DoH registry values: {e}", "ERROR")
            return False
            
    except Exception as e:
        log(f"Error in set_doh_for_adapter: {e}", "ERROR")
        return False

def clear_doh_for_adapter(guid: str) -> bool:
    """Очищает настройки DoH для адаптера"""
    try:
        reg_path = f"SYSTEM\\CurrentControlSet\\Services\\Dnscache\\InterfaceSpecificParameters\\{guid}\\DohInterfaceSettings"
        
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path, 0,
                               winreg.KEY_ALL_ACCESS | winreg.KEY_WOW64_64KEY) as key:
                try:
                    winreg.DeleteKey(key, "Doh")
                    log(f"DoH settings cleared for GUID {guid}", "DNS")
                    notify_dns_change()
                    flush_dns_cache_native()
                    return True
                except:
                    pass
        except:
            pass
        
        return False
        
    except Exception as e:
        log(f"Error clearing DoH: {e}", "DEBUG")
        return False

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
                    
                    # Проверяем исключения
                    if not include_ignored and self.should_ignore_adapter(alias, desc):
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
                
                if not include_ignored and self.should_ignore_adapter(name, name):
                    continue
                
                adapters.append((name, name))
                
        except Exception as e:
            log(f"Native API error: {e}", "ERROR")
        
        return adapters
    
    @staticmethod
    def get_network_adapters(include_ignored=False, include_disconnected=True):
        """Обратная совместимость"""
        manager = DNSManager()
        return manager.get_network_adapters_fast(include_ignored, include_disconnected)
    
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
                        # DNS разделены запятыми или пробелами
                        dns_list = [ip.strip() for ip in dns_string.replace(' ', ',').split(',') if ip.strip()]
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
        """Устанавливает пользовательские DNS через реестр"""
        try:
            guid = self.get_adapter_guid(adapter_name)
            if not guid:
                return False, "GUID not found"
            
            dns_list = [primary_dns]
            if secondary_dns:
                dns_list.append(secondary_dns)
            
            is_ipv6 = (address_family.lower() == "ipv6")
            
            success = set_dns_via_registry(guid, dns_list, is_ipv6)
            
            if success:
                notify_dns_change()
                return True, "OK"
            else:
                return False, "Registry update failed"
            
        except Exception as e:
            return False, str(e)
    
    def set_auto_dns(self, adapter_name: str, address_family: Optional[str] = None) -> Tuple[bool, str]:
        """Сбрасывает DNS на автоматический режим"""
        try:
            guid = self.get_adapter_guid(adapter_name)
            if not guid:
                return False, "GUID not found"
            
            families = ["IPv4", "IPv6"] if address_family is None else [address_family]
            
            for family in families:
                is_ipv6 = (family.lower() == "ipv6")
                set_dns_via_registry(guid, [], is_ipv6)
            
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