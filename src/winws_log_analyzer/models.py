"""Модели результата разбора debug-лога winws2.

Лог состоит из преамбулы (профили, hostlist/ipset) и повторяющихся блоков
``packet: id=N len=... outbound|inbound ...`` … ``packet: id=N reinject ...|drop``.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# Вердикты пакета (терминатор блока).
VERDICT_UNMODIFIED = "unmodified"
VERDICT_MODIFIED = "modified"
VERDICT_DROP = "drop"
VERDICT_NONE = ""  # блок оборван (лог обрезан) либо терминатор не встретился


@dataclass(slots=True)
class ListCheckRecord:
    """Одна positive-проверка hostlist/ipset внутри пакетного блока."""

    list_path: str  # путь списка из лога либо "fixed"
    kind: str  # "hostlist" | "ipset"
    profile_id: int
    target: str  # hostname либо IP, для которого проверка дала positive


@dataclass(slots=True)
class PacketRecord:
    """Один пакетный блок лога."""

    packet_id: int
    line_no: int  # строка заголовка блока (1-based)
    direction: str  # "out" | "in"
    length: int
    ip_version: int  # 4 | 6
    src_ip: str = ""
    src_port: int = 0
    dst_ip: str = ""
    dst_port: int = 0
    proto: str = ""  # tcp | udp | ...
    ttl: int | None = None
    tcp_flags: str = ""
    l7proto: str = ""  # tls/quic/http/unknown
    hostname: str = ""
    payload_type: str = ""
    profile_id: int | None = None
    profile_name: str = ""
    profile_cached: bool = False
    verdict: str = VERDICT_NONE
    tls_details: tuple[str, ...] = ()
    positive_checks: tuple[ListCheckRecord, ...] = ()
    lua_applied: tuple[str, ...] = ()  # lua-функции, реально сделавшие desync
    delayed: bool = False  # DELAY desync / delayed-обработка внутри блока
    replay_count: int = 0


@dataclass(slots=True)
class ConnectionRecord:
    """Агрегат пакетов по удалённой стороне (proto, remote_ip, remote_port)."""

    proto: str
    remote_ip: str
    remote_port: int
    hostname: str = ""
    l7proto: str = ""
    profile_ids: tuple[int, ...] = ()
    profile_names: tuple[str, ...] = ()
    packets_total: int = 0
    packets_out: int = 0
    packets_in: int = 0
    verdict_counts: dict[str, int] = field(default_factory=dict)
    positive_lists: tuple[str, ...] = ()  # basename списков с positive-проверками
    lua_applied: tuple[str, ...] = ()
    packets: list[PacketRecord] = field(default_factory=list)
    packets_truncated: bool = False
    first_line_no: int = 0

    @property
    def key(self) -> tuple[str, str, int]:
        return (self.proto, self.remote_ip, self.remote_port)


@dataclass(slots=True)
class WinwsLogParseResult:
    """Итог разбора файла."""

    file_path: str = ""
    profiles: dict[int, str] = field(default_factory=dict)  # id -> "имя: func1, func2"
    hostlists: tuple[tuple[str, int], ...] = ()  # (путь, загружено hostов)
    ipsets: tuple[tuple[str, int], ...] = ()  # (путь, загружено подсетей)
    packets_total: int = 0
    connections: list[ConnectionRecord] = field(default_factory=list)
    positive_checks_total: int = 0
    unparsed_blocks: int = 0  # блоки без распознанной IP-строки
    # "packet: id=..." строки неизвестного формата (например, Linux nfqws —
    # намеренно не поддерживается, GUI только для Windows).
    unrecognized_packet_lines: int = 0
    cancelled: bool = False
