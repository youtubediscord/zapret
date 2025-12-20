# orchestra/log_parser.py
"""
Парсер логов winws2.exe для оркестратора.
Основано на документации WINWS2_LOG.md
"""

import re
from dataclasses import dataclass
from typing import Optional
from enum import Enum


# === Локальные IP диапазоны ===
LOCAL_IP_PREFIXES = (
    "127.", "10.", "192.168.",
    "172.16.", "172.17.", "172.18.", "172.19.",
    "172.20.", "172.21.", "172.22.", "172.23.",
    "172.24.", "172.25.", "172.26.", "172.27.",
    "172.28.", "172.29.", "172.30.", "172.31.",
    "169.254.", "0.",
    "::1", "fe80:", "fc00:", "fd00:",
)


# === Паттерны регулярных выражений ===

class Patterns:
    """Все паттерны для парсинга логов winws2"""

    # --- Пакеты ---
    # packet: id=2079 len=40 inbound IPv6=0 ...
    packet = re.compile(r"packet: id=(\d+) len=(\d+) (inbound|outbound)")

    # IP4: 64.233.162.198 => 192.168.1.100 proto=tcp ttl=116 sport=443 dport=55666 flags=R
    ip4_tcp = re.compile(r"IP4: ([\d.]+) => ([\d.]+) proto=tcp ttl=(\d+) sport=(\d+) dport=(\d+) flags=(\S+)")

    # IP4: 151.101.1.140 => 192.168.1.100 proto=udp ttl=55 sport=443 dport=64028
    ip4_udp = re.compile(r"IP4: ([\d.]+) => ([\d.]+) proto=udp")

    # --- Profile Search ---
    # desync profile search for tcp ip=142.250.74.206 port=443 l7proto=tls ssid='' hostname='youtube.com'
    tcp_profile_search = re.compile(
        r"desync profile search for tcp ip=([\d.:]+) port=(\d+) l7proto=(\S+) ssid='[^']*' hostname='([^']*)'"
    )

    # desync profile search for udp ip=108.177.122.95 port=443 l7proto=quic
    udp_profile_search = re.compile(
        r"desync profile search for udp ip=([\d.:a-fA-F]+) port=(\d+) l7proto=(\S+)"
    )

    # using cached desync profile 1 (noname)
    cached_profile = re.compile(r"using cached desync profile (\d+) \((\S+)\)")

    # desync profile 3 (noname) matches
    profile_matches = re.compile(r"desync profile (\d+) \(\S+\) matches")

    # --- Automate ---
    # LUA: automate: host record key 'autostate.circular_quality_1_1.youtube.com'
    # LUA: automate: host record key 'autostate.circular_quality_3_1.udp_other_108.177.0.0'
    automate_hostkey = re.compile(
        r"LUA: automate: host record key 'autostate\.circular_quality_(\d+)_\d+\.(?:udp_other_)?([^']+)'"
    )

    automate_success = re.compile(r"LUA: automate: success detected")
    automate_failure = re.compile(r"LUA: automate: failure detected")

    # --- Strategy Stats ---
    # LUA: strategy-stats: APPLIED youtube.com = strategy 2 [circular_quality_1_1]
    # LUA: strategy-stats: APPLIED youtube.com [tls] = strategy 2
    applied = re.compile(
        r"APPLIED (\S+)(?: \[([^\]]+)\])? = strategy (\d+)(?: \[([^\]]+)\])?"
    )

    # LUA: strategy-stats: PRELOADED youtube.com = strategy 15 [tls]
    preloaded = re.compile(r"PRELOADED (\S+) = strategy (\d+)(?: \[(\S+)\])?")

    # LUA: strategy_quality: LOCK youtube.com -> strat=2
    # Hostname может содержать пробелы, поэтому матчим до " -> strat="
    lock = re.compile(r"strategy_quality: LOCK (.+?) -> strat=(\d+)")

    # LUA: strategy_quality: UNLOCK youtube.com
    # Hostname до конца строки (может содержать пробелы для UDP)
    unlock = re.compile(r"strategy_quality: UNLOCK (.+?)$")

    # LUA: strategy_quality: RESET hostname
    reset = re.compile(r"strategy_quality: RESET (.+?)$")

    # LUA: strategy_quality: youtube.com strat=2 SUCCESS 3/5
    success = re.compile(r"strategy_quality: (.+?) strat=(\d+) SUCCESS (\d+)/(\d+)")

    # LUA: strategy_quality: youtube.com strat=2 FAIL 1/4
    fail = re.compile(r"strategy_quality: (.+?) strat=(\d+) FAIL (\d+)/(\d+)")

    # LUA: strategy-stats: HISTORY youtube.com s2 successes=10 failures=2 rate=83%
    history = re.compile(r"HISTORY (\S+) s(\d+) successes=(\d+) failures=(\d+) rate=(\d+)%")

    # --- Circular ---
    # LUA: circular: rotate strategy to 7
    rotate = re.compile(r"circular: rotate strategy to (\d+)")

    # LUA: circular: current strategy 7
    current_strategy = re.compile(r"circular: current strategy (\d+)")

    # --- Failure Detectors ---
    # LUA: standard_failure_detector: incoming RST s1 in range s4096
    std_rst = re.compile(r"standard_failure_detector: incoming RST")

    # LUA: standard_failure_detector: retransmission 1/3
    std_retrans = re.compile(r"standard_failure_detector: retransmission (\d+)/(\d+)")

    # LUA: udp_aggressive_failure_detector: FAIL out=2>=2 in=0<=0
    udp_fail = re.compile(r"udp_aggressive_failure_detector: FAIL")

    # --- Success Detectors ---
    # LUA: standard_success_detector: treating connection as successful
    std_success = re.compile(r"standard_success_detector:.*successful")

    # LUA: udp_protocol_success_detector: QUIC (QUIC_SHORT_HEADER) - SUCCESS
    udp_success = re.compile(r"udp_protocol_success_detector: (.+) - SUCCESS")

    # --- Protocol Detection (by packet content, NOT ports) ---
    # "packet contains stun payload" - STUN by Magic Cookie 0x2112A442
    stun_payload = re.compile(r"packet contains stun payload")
    # "packet contains QUIC initial" - QUIC by long header
    quic_initial = re.compile(r"packet contains QUIC initial")
    # "packet contains discord_ip_discovery payload"
    discord_payload = re.compile(r"packet contains discord_ip_discovery payload")
    # "packet contains wireguard_* payload"
    wireguard_payload = re.compile(r"packet contains wireguard_\w+ payload")
    # "packet contains dht payload"
    dht_payload = re.compile(r"packet contains dht payload")

    # --- DPI Desync ---
    # dpi desync src=192.168.1.100:55666 dst=64.233.162.198:443 ... connection_proto=tls
    dpi_desync = re.compile(
        r"dpi desync src=([\d.:a-fA-F]+):(\d+) dst=([\d.:a-fA-F]+):(\d+) .* connection_proto=(\S+)"
    )

    # --- Legacy patterns ---
    legacy_lock = re.compile(r"LOCKED (\S+) to strategy=(\d+)(?:\s+\[(TLS|HTTP|UDP)\])?")
    legacy_unlock = re.compile(r"UNLOCKING (\S+)(?:\s+\[(TLS|HTTP|UDP)\])?")
    unsticky = re.compile(r"strategy-stats: UNSTICKY (\S+)(?:\s+\[(TLS|HTTP|UDP)\])?")

    # circular_quality variants
    auto_unlock = re.compile(r"circular_quality: AUTO-UNLOCK (\S+) after")
    cq_current_strategy = re.compile(r"circular_quality: current strategy (\d+)")
    # LUA: circular_quality: rotate to strategy 7 [stats...]
    cq_rotate = re.compile(r"circular_quality: rotate to strategy (\d+)")


# === Типы событий ===

class EventType(Enum):
    TCP_PROFILE_SEARCH = "tcp_profile_search"
    UDP_PROFILE_SEARCH = "udp_profile_search"
    CACHED_PROFILE = "cached_profile"
    UDP_PACKET = "udp_packet"
    APPLIED = "applied"
    LOCK = "lock"
    UNLOCK = "unlock"
    SUCCESS = "success"
    FAIL = "fail"
    ROTATE = "rotate"
    RST = "rst"
    AUTOMATE_SUCCESS = "automate_success"
    AUTOMATE_FAILURE = "automate_failure"
    HOSTKEY = "hostkey"
    HISTORY = "history"
    PRELOADED = "preloaded"


@dataclass
class ParsedEvent:
    """Результат парсинга строки лога"""
    event_type: EventType
    hostname: Optional[str] = None
    ip: Optional[str] = None
    port: Optional[int] = None
    strategy: Optional[int] = None
    l7proto: Optional[str] = None  # tls, http, quic, stun, discord, etc.
    profile: Optional[int] = None  # номер профиля (1=TLS, 2=HTTP, 3=UDP)
    successes: Optional[int] = None
    failures: Optional[int] = None
    total: Optional[int] = None
    rate: Optional[int] = None
    tag: Optional[str] = None  # circular_quality_1_1, etc.
    raw_line: str = ""


def is_local_ip(ip: str) -> bool:
    """Проверяет, является ли IP локальным"""
    if not ip:
        return False
    return ip.startswith(LOCAL_IP_PREFIXES)


def get_remote_ip(src_ip: str, dst_ip: str) -> Optional[str]:
    """Возвращает удалённый (не локальный) IP из пары src/dst"""
    if is_local_ip(src_ip) and not is_local_ip(dst_ip):
        return dst_ip
    elif is_local_ip(dst_ip) and not is_local_ip(src_ip):
        return src_ip
    elif not is_local_ip(src_ip):
        return src_ip  # оба не-локальные, берём src
    return None


# Multi-part TLDs для корректного NLD-cut
MULTI_PART_TLDS = {
    'co.uk', 'com.au', 'co.nz', 'co.jp', 'co.kr', 'co.in', 'co.za',
    'com.br', 'com.mx', 'com.ar', 'com.ru', 'com.ua', 'com.cn',
    'org.uk', 'org.au', 'net.au', 'gov.uk', 'ac.uk', 'edu.au',
}


def nld_cut(hostname: str, nld: int = 2) -> str:
    """
    Обрезает hostname до N-level domain.
    nld=2: "rr1---sn-xxx.googlevideo.com" -> "googlevideo.com"
    """
    if not hostname:
        return hostname
    # IP адреса не обрезаем
    if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', hostname):
        return hostname

    parts = hostname.lower().split('.')
    if len(parts) <= nld:
        return hostname

    # Проверяем multi-part TLD
    if len(parts) >= 2:
        last_two = '.'.join(parts[-2:])
        if last_two in MULTI_PART_TLDS:
            if len(parts) <= nld + 1:
                return hostname
            return '.'.join(parts[-(nld + 1):])

    return '.'.join(parts[-nld:])


def ip_to_subnet16(ip: str) -> str:
    """
    Конвертирует IP в /16 подсеть для группировки.
    103.142.5.10 -> 103.142.0.0
    """
    match = re.match(r'^(\d{1,3})\.(\d{1,3})\.\d{1,3}\.\d{1,3}$', ip)
    if match:
        return f"{match.group(1)}.{match.group(2)}.0.0"
    return ip


class LogParser:
    """
    Парсер логов winws2 с отслеживанием состояния.

    Использование:
        parser = LogParser()
        for line in log_lines:
            event = parser.parse_line(line)
            if event:
                # обработать событие
    """

    def __init__(self):
        self.reset()

    def reset(self):
        """Сбрасывает состояние парсера"""
        # Текущий контекст пакета
        self.current_host: Optional[str] = None
        self.current_ip: Optional[str] = None
        self.current_port: Optional[int] = None
        self.current_proto: str = "tcp"  # tcp или udp
        self.current_l7proto: Optional[str] = None  # tls, http, quic, stun, etc.
        self.current_profile: int = 0  # 1=TLS, 2=HTTP, 3/4=UDP
        self.current_strategy: int = 1

        # Кэш IP → hostname для Keep-Alive
        self.ip_to_hostname: dict[str, str] = {}

        # Последняя применённая стратегия: (host, proto) -> strategy
        self.last_applied: dict[tuple[str, str], int] = {}
        # Последний хост по протоколу
        self.last_host_by_proto: dict[str, str] = {}

    def _cache_hostname(self, ip: str, hostname: str):
        """Сохраняет связку IP → hostname в кэш"""
        if ip and hostname and not is_local_ip(ip):
            self.ip_to_hostname[ip] = hostname
            # Ограничиваем размер кэша
            if len(self.ip_to_hostname) > 1000:
                keys = list(self.ip_to_hostname.keys())
                for k in keys[:500]:
                    del self.ip_to_hostname[k]

    def _get_proto_key(self) -> str:
        """Возвращает ключ протокола: udp, http, tls"""
        if self.current_proto == "udp":
            return "udp"
        if self.current_l7proto == "http" or self.current_port == 80:
            return "http"
        return "tls"

    def _is_udp_proto(self) -> bool:
        """Проверяет, является ли текущий протокол UDP (динамически по current_proto)"""
        if self.current_proto == "udp":
            return True
        if self.current_l7proto in ('discord', 'stun', 'quic', 'wireguard', 'dht'):
            return True
        return False

    def _get_proto_from_context(self) -> str:
        """
        Возвращает протокол на основе динамически определённого контекста.
        Использует current_proto и current_l7proto из 'desync profile search' строки.
        """
        # UDP протоколы
        if self.current_proto == "udp":
            # Используем конкретный l7proto если известен
            if self.current_l7proto in ('quic', 'stun', 'discord', 'wireguard', 'dht'):
                return self.current_l7proto
            return "udp"

        # TCP протоколы
        if self.current_proto == "tcp":
            if self.current_l7proto == "http":
                return "http"
            # Порт 80 = HTTP даже если l7proto=unknown
            if self.current_port == 80:
                return "http"
            # tls, unknown и др. -> tls
            return "tls"

        # Fallback по порту (если proto не определён)
        if self.current_port == 80:
            return "http"

        return "tls"

    def _is_udp_hostname(self, hostname: str) -> bool:
        """
        Проверяет, является ли hostname UDP-сервисом.
        Определяет по:
        - Известным сервисам из KNOWN_SERVICE_SUBNETS (Roblox, Discord, Telegram, etc.)
        - Generic UDP протоколам (QUIC, STUN, DHT, WireGuard)
        - Формату "UDP x.x.x.x" (подсеть)
        - IP адресу в начале hostname
        """
        if not hostname:
            return False

        hostname_upper = hostname.upper()

        # Известные UDP сервисы из KNOWN_SERVICE_SUBNETS в Lua
        # Эти имена возвращает udp_global_hostkey()
        known_udp_services = {
            "ROBLOX", "DISCORD", "TELEGRAM", "WHATSAPP",
            "GOOGLE", "CLOUDFLARE",
            # С суффиксами
            "DISCORD VOICE", "GOOGLE STUN",
        }

        # Generic UDP протоколы
        generic_udp_protos = {"QUIC", "STUN", "DHT", "WIREGUARD"}

        # Точное совпадение с известным сервисом
        if hostname_upper in known_udp_services:
            return True

        # Точное совпадение с generic протоколом
        if hostname_upper in generic_udp_protos:
            return True

        # Проверяем начало hostname на известные сервисы (для "Google STUN", "Discord Voice")
        for service in known_udp_services:
            if hostname_upper.startswith(service):
                return True

        # Формат "UDP x.x.x.x" - подсеть
        if hostname_upper.startswith("UDP "):
            return True

        # Hostname начинается с IP адреса
        if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', hostname):
            return True

        return False

    def parse_line(self, line: str) -> Optional[ParsedEvent]:
        """
        Парсит строку лога и возвращает событие или None.
        Обновляет внутреннее состояние парсера.
        """
        if not line:
            return None

        # === TCP Profile Search ===
        # desync profile search for tcp ip=... port=443 l7proto=tls hostname='youtube.com'
        m = Patterns.tcp_profile_search.search(line)
        if m:
            ip, port, l7proto, hostname = m.groups()
            self.current_ip = ip
            self.current_port = int(port)
            self.current_proto = "tcp"
            self.current_l7proto = l7proto

            if hostname and not hostname.replace('.', '').isdigit():
                self.current_host = nld_cut(hostname, 2)
                self._cache_hostname(ip, self.current_host)
            else:
                self.current_host = self.ip_to_hostname.get(ip)

            return ParsedEvent(
                event_type=EventType.TCP_PROFILE_SEARCH,
                hostname=self.current_host,
                ip=ip,
                port=int(port),
                l7proto=l7proto,
                raw_line=line
            )

        # === UDP Profile Search ===
        # desync profile search for udp ip=... port=443 l7proto=quic
        m = Patterns.udp_profile_search.search(line)
        if m:
            ip, port, l7proto = m.groups()
            self.current_ip = ip
            self.current_port = int(port)
            self.current_proto = "udp"
            self.current_l7proto = l7proto

            if not is_local_ip(ip):
                self.current_host = ip  # Для UDP используем полный IP
            else:
                self.current_host = None

            return ParsedEvent(
                event_type=EventType.UDP_PROFILE_SEARCH,
                ip=ip,
                port=int(port),
                l7proto=l7proto,
                raw_line=line
            )

        # === UDP Packet IP (fallback для cached profile) ===
        # IP4: 151.101.1.140 => 192.168.1.100 proto=udp
        m = Patterns.ip4_udp.search(line)
        if m:
            src_ip, dst_ip = m.groups()
            remote_ip = get_remote_ip(src_ip, dst_ip)
            if remote_ip:
                self.current_host = remote_ip
                self.current_ip = remote_ip
                self.current_proto = "udp"
                return ParsedEvent(
                    event_type=EventType.UDP_PACKET,
                    ip=remote_ip,
                    raw_line=line
                )

        # === Cached Profile ===
        m = Patterns.cached_profile.search(line)
        if m:
            profile_num = int(m.group(1))
            self.current_profile = profile_num
            if profile_num >= 3:
                self.current_proto = "udp"
            return ParsedEvent(
                event_type=EventType.CACHED_PROFILE,
                profile=profile_num,
                raw_line=line
            )

        # === Profile Matches ===
        m = Patterns.profile_matches.search(line)
        if m:
            self.current_profile = int(m.group(1))

        # === Protocol Detection by Packet Content (NOT ports) ===
        # Эти паттерны появляются ДО dpi desync строки и устанавливают протокол

        # STUN - определяется по Magic Cookie 0x2112A442, НЕ по портам
        # "packet contains stun payload"
        if Patterns.stun_payload.search(line):
            self.current_proto = "udp"
            self.current_l7proto = "stun"

        # QUIC - определяется по long header (первый байт 0xC0-0xFF)
        # "packet contains QUIC initial"
        if Patterns.quic_initial.search(line):
            self.current_proto = "udp"
            self.current_l7proto = "quic"

        # Discord IP Discovery
        if Patterns.discord_payload.search(line):
            self.current_proto = "udp"
            self.current_l7proto = "discord"

        # WireGuard
        if Patterns.wireguard_payload.search(line):
            self.current_proto = "udp"
            self.current_l7proto = "wireguard"

        # DHT (BitTorrent)
        if Patterns.dht_payload.search(line):
            self.current_proto = "udp"
            self.current_l7proto = "dht"

        # === DPI Desync (connection_proto) ===
        m = Patterns.dpi_desync.search(line)
        if m:
            src_ip, _, dst_ip, _, conn_proto = m.groups()
            self.current_l7proto = conn_proto
            if self.current_profile >= 3:
                remote_ip = get_remote_ip(src_ip, dst_ip)
                if remote_ip:
                    self.current_host = remote_ip
                    self.current_ip = remote_ip
                    self.current_proto = "udp"

        # === UDP Protocol Success Detector ===
        # LUA: udp_protocol_success_detector: QUIC (QUIC_SHORT_HEADER) - SUCCESS
        # Устанавливает UDP контекст для последующих событий (strategy_quality)
        m = Patterns.udp_success.search(line)
        if m:
            proto_detail = m.group(1)  # "QUIC (QUIC_SHORT_HEADER)" or just "QUIC"
            # Извлекаем базовый протокол
            base_proto = proto_detail.split()[0].lower() if proto_detail else "quic"
            self.current_proto = "udp"
            self.current_l7proto = base_proto
            # Не возвращаем событие - это информационная строка
            # Контекст будет использован следующим strategy_quality событием

        # === UDP Aggressive Failure Detector ===
        # LUA: udp_aggressive_failure_detector: FAIL out=2>=2 in=0<=0
        # Устанавливает UDP контекст для последующих событий
        if Patterns.udp_fail.search(line):
            self.current_proto = "udp"
            # Не возвращаем событие - это информационная строка

        # === Automate Hostkey ===
        # LUA: automate: host record key 'autostate.circular_quality_1_1.youtube.com'
        # Profile 1 = TLS, Profile 2 = HTTP, Profile 3+ = UDP
        m = Patterns.automate_hostkey.search(line)
        if m:
            profile_num, hostname = m.groups()
            profile = int(profile_num)
            is_ip = hostname.replace('.', '').replace(':', '').isdigit()

            # Для UDP (profile >= 3) используем IP как hostname
            # Для TCP/TLS/HTTP - только домены (не IP)
            if profile >= 3:
                # UDP: используем IP адрес как есть
                self.current_host = hostname
                self.current_proto = "udp"
            elif not is_ip:
                # TCP: используем домен с NLD-cut
                self.current_host = nld_cut(hostname, 2)
                if self.current_ip:
                    self._cache_hostname(self.current_ip, self.current_host)

            return ParsedEvent(
                event_type=EventType.HOSTKEY,
                hostname=self.current_host,
                profile=profile,
                raw_line=line
            )

        # === APPLIED ===
        # LUA: strategy-stats: APPLIED youtube.com [tls] = strategy 2
        m = Patterns.applied.search(line)
        if m:
            hostname = m.group(1)
            proto_tag = m.group(2)  # [tls] между hostname и =
            strategy = int(m.group(3))
            tag = m.group(4)  # [circular_quality_1_1] после strategy

            host_key = nld_cut(hostname, 2)

            # Определяем протокол из тега
            proto_key = None
            if tag:
                tag_m = re.match(r"circular_quality_(\d+)_", tag)
                if tag_m:
                    prof = int(tag_m.group(1))
                    proto_key = {1: "tls", 2: "http", 3: "udp", 4: "udp"}.get(prof, "tls")
            if not proto_key and proto_tag:
                proto_key = proto_tag.lower()
            if not proto_key:
                proto_key = self._get_proto_key()

            self.last_applied[(host_key, proto_key)] = strategy
            self.last_host_by_proto[proto_key] = host_key
            self.current_host = host_key

            return ParsedEvent(
                event_type=EventType.APPLIED,
                hostname=host_key,
                strategy=strategy,
                l7proto=proto_key,
                tag=tag,
                raw_line=line
            )

        # === LOCK ===
        m = Patterns.lock.search(line) or Patterns.legacy_lock.search(line)
        if m:
            hostname = m.group(1)
            strategy = int(m.group(2))
            proto_tag = m.group(3) if len(m.groups()) >= 3 else None

            # Определяем протокол динамически по контексту (tcp/udp + l7proto)
            proto = self._get_proto_from_context()
            is_udp = proto in ("udp", "quic", "stun", "discord", "wireguard", "dht")

            # Переопределяем из proto_tag если есть
            if proto_tag:
                proto_tag_upper = proto_tag.upper()
                if proto_tag_upper == "UDP":
                    is_udp = True
                    proto = "udp"
                elif proto_tag_upper == "HTTP":
                    is_udp = False
                    proto = "http"
                elif proto_tag_upper == "TLS":
                    is_udp = False
                    proto = "tls"

            # Fallback: проверяем hostname если контекст не определён
            if not self.current_proto and not is_udp:
                is_udp = self._is_udp_hostname(hostname)
                if is_udp:
                    proto = "udp"

            # Для UDP НЕ режем IP (используем полный)
            host_key = hostname if is_udp else nld_cut(hostname, 2)

            return ParsedEvent(
                event_type=EventType.LOCK,
                hostname=host_key,
                strategy=strategy,
                l7proto=proto,
                raw_line=line
            )

        # === UNLOCK ===
        m = Patterns.unlock.search(line) or Patterns.auto_unlock.search(line) or Patterns.legacy_unlock.search(line)
        if m:
            hostname = m.group(1)
            return ParsedEvent(
                event_type=EventType.UNLOCK,
                hostname=hostname,
                raw_line=line
            )

        # === SUCCESS ===
        m = Patterns.success.search(line)
        if m:
            hostname, strat, successes, total = m.groups()

            # Определяем протокол динамически по контексту (tcp/udp + l7proto)
            proto = self._get_proto_from_context()
            is_udp = proto in ("udp", "quic", "stun", "discord", "wireguard", "dht")

            # Fallback: проверяем hostname если контекст не определён
            if not self.current_proto and not is_udp:
                is_udp = self._is_udp_hostname(hostname)
                if is_udp:
                    proto = "udp"

            # Для UDP НЕ режем IP
            host_key = hostname if is_udp else nld_cut(hostname, 2)

            return ParsedEvent(
                event_type=EventType.SUCCESS,
                hostname=host_key,
                strategy=int(strat),
                successes=int(successes),
                total=int(total),
                l7proto=proto,
                raw_line=line
            )

        # === FAIL ===
        m = Patterns.fail.search(line)
        if m:
            hostname, strat, successes, total = m.groups()

            # Определяем протокол динамически по контексту (tcp/udp + l7proto)
            proto = self._get_proto_from_context()
            is_udp = proto in ("udp", "quic", "stun", "discord", "wireguard", "dht")

            # Fallback: проверяем hostname если контекст не определён
            if not self.current_proto and not is_udp:
                is_udp = self._is_udp_hostname(hostname)
                if is_udp:
                    proto = "udp"

            host_key = hostname if is_udp else nld_cut(hostname, 2)

            return ParsedEvent(
                event_type=EventType.FAIL,
                hostname=host_key,
                strategy=int(strat),
                successes=int(successes),
                total=int(total),
                l7proto=proto,
                raw_line=line
            )

        # === ROTATE ===
        m = Patterns.rotate.search(line) or Patterns.cq_rotate.search(line)
        if m:
            new_strat = int(m.group(1))
            # НЕ обновляем last_applied! Только APPLIED должен это делать
            return ParsedEvent(
                event_type=EventType.ROTATE,
                strategy=new_strat,
                hostname=self.current_host,
                raw_line=line
            )

        # === Current Strategy ===
        m = Patterns.current_strategy.search(line) or Patterns.cq_current_strategy.search(line)
        if m:
            self.current_strategy = int(m.group(1))

        # === RST ===
        if Patterns.std_rst.search(line):
            proto_key = self._get_proto_key()
            host_key = self.current_host
            if not host_key and self.current_ip:
                host_key = self.ip_to_hostname.get(self.current_ip)
            if not host_key:
                host_key = self.last_host_by_proto.get(proto_key)

            applied_strat = self.last_applied.get((host_key, proto_key)) if host_key else None

            return ParsedEvent(
                event_type=EventType.RST,
                hostname=host_key,
                strategy=applied_strat,
                l7proto=proto_key,
                raw_line=line
            )

        # === Automate Success ===
        if Patterns.automate_success.search(line):
            return ParsedEvent(
                event_type=EventType.AUTOMATE_SUCCESS,
                hostname=self.current_host,
                raw_line=line
            )

        # === Automate Failure ===
        if Patterns.automate_failure.search(line):
            return ParsedEvent(
                event_type=EventType.AUTOMATE_FAILURE,
                hostname=self.current_host,
                raw_line=line
            )

        # === Standard Success ===
        if Patterns.std_success.search(line):
            proto_key = self._get_proto_key()
            host_key = self.current_host
            if not host_key and self.current_ip:
                host_key = self.ip_to_hostname.get(self.current_ip)

            applied_strat = self.last_applied.get((host_key, proto_key)) if host_key else None

            return ParsedEvent(
                event_type=EventType.SUCCESS,
                hostname=host_key,
                strategy=applied_strat,
                l7proto=proto_key,
                raw_line=line
            )

        # === HISTORY ===
        # Format: HISTORY youtube.com s2 successes=10 failures=2 rate=83%
        m = Patterns.history.search(line)
        if m:
            hostname, strat, successes, failures, rate = m.groups()
            return ParsedEvent(
                event_type=EventType.HISTORY,
                hostname=nld_cut(hostname, 2),
                strategy=int(strat),
                successes=int(successes),
                failures=int(failures),
                rate=int(rate),
                raw_line=line
            )

        # === PRELOADED ===
        m = Patterns.preloaded.search(line)
        if m:
            hostname, strat, proto = m.groups()
            return ParsedEvent(
                event_type=EventType.PRELOADED,
                hostname=hostname,
                strategy=int(strat),
                l7proto=proto,
                raw_line=line
            )

        return None

    def get_applied_strategy(self, hostname: str, proto: str) -> Optional[int]:
        """Возвращает последнюю применённую стратегию для хоста и протокола"""
        return self.last_applied.get((hostname, proto))
