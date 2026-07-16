"""Потоковый парсер debug-лога winws2.

Ключевая тонкость формата: строки ``packet: id=N ...`` встречаются в двух ролях —
заголовок блока (содержит ``len=`` и ``outbound|inbound``) и терминатор-вердикт
(``reinject unmodified|reinject modified|drop``). Внутри одного блока при
reassembly встречаются ``REPLAY IP4:`` / ``REPLAYING/SENDING delayed packet`` —
они не открывают новых пакетов.

Поддерживается только Windows-формат (winws2). Linux-формат nfqws (заголовок
``packet: id=N len=N mark=...`` без outbound/inbound, вердикты ``pass
modified/unmodified``) намеренно не поддерживается — GUI работает только под
Windows. Такие строки учитываются в ``unrecognized_packet_lines``, чтобы дрейф
формата был виден в сводке, а не выглядел как пустой лог.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from typing import TextIO

from .models import (
    VERDICT_DROP,
    VERDICT_MODIFIED,
    VERDICT_UNMODIFIED,
    ConnectionRecord,
    ListCheckRecord,
    PacketRecord,
    WinwsLogParseResult,
)

DEFAULT_MAX_PACKETS_PER_CONNECTION = 5000

# Как часто (в строках) дёргать progress_cb/cancel_cb.
_CALLBACK_LINE_INTERVAL = 2000

_RE_PACKET_HEADER = re.compile(
    r"^packet: id=(\d+) len=(\d+) (outbound|inbound) IPv6=(\d)"
)
# У "reinject modified" в новых сборках есть хвост "len 74 => 148" (nfqws.c).
_RE_PACKET_VERDICT = re.compile(
    r"^packet: id=(\d+) (reinject unmodified|reinject modified|drop)(?: len \d+ => \d+)?\s*$"
)
_RE_IP = re.compile(
    r"^IP([46]): (\S+) => (\S+) proto=(\w+) ttl=(\d+)"
    r"(?: sport=(\d+) dport=(\d+))?(?:.*? flags=(\S+))?"
)
# Между port= и l7proto= в разных сборках бывают доп. поля (icmp=0:0),
# а вместо ip= — пара ip1=/ip2= (desync.c), поэтому середина не фиксируется.
_RE_PROFILE_SEARCH = re.compile(
    r"^desync profile search for \w+ .*?l7proto=(\S+) ssid='[^']*' hostname='([^']*)'"
)
_RE_LIST_CHECK_CONTEXT = re.compile(r"^\* (hostlist|ipset) check for profile (\d+)")
_RE_LIST_CHECK_RESULT = re.compile(
    r"\[([^\]]+)\] (?:include|exclude) (?:hostlist|ipset) check for (\S+) : (positive|negative)"
)
_RE_PROFILE_MATCH = re.compile(r"^desync profile (\d+) \(([^)]*)\) matches")
_RE_PROFILE_CACHED = re.compile(r"^using cached desync profile (\d+) \(([^)]*)\)")
_RE_PROFILE_CONNTRACK = re.compile(
    r"^using desync profile (\d+) \(([^)]*)\) from conntrack entry"
)
_RE_DPI_DESYNC = re.compile(
    r"^dpi desync .*connection_proto=(\S+) payload_type=(\S*)"
)
_RE_TLS_DETAIL = re.compile(r"^TLS ([\w ]+?) (?:ext )?: (.+)$")
_RE_HOSTNAME_LINE = re.compile(r"^hostname: (\S+)")
_RE_LUA_APPLIED = re.compile(r"^\* lua '([^']+)' : desync\s*$")
_RE_DELAYED = re.compile(r"^(DELAY desync|REPLAYING delayed packet|SENDING delayed packet)")
_RE_REPLAY = re.compile(r"^REPLAYING delayed packet")
# Преамбула
_RE_PREAMBLE_PROFILE = re.compile(r"^profile (\d+) \(([^)]*)\) lua (\w+)\(")
_RE_PREAMBLE_LOADED = re.compile(r"^Loaded (\d+) (hosts|ip/subnets) from (.+)$")

_VERDICT_MAP = {
    "reinject unmodified": VERDICT_UNMODIFIED,
    "reinject modified": VERDICT_MODIFIED,
    "drop": VERDICT_DROP,
}


class WinwsLogParser:
    """Построчный конечный автомат: преамбула → пакетные блоки."""

    def __init__(self, *, max_packets_per_connection: int = DEFAULT_MAX_PACKETS_PER_CONNECTION):
        self._max_packets = max_packets_per_connection
        self._result = WinwsLogParseResult()
        self._profiles: dict[int, tuple[str, list[str]]] = {}
        self._hostlists: list[tuple[str, int]] = []
        self._ipsets: list[tuple[str, int]] = []
        self._connections: dict[tuple[str, str, int], ConnectionRecord] = {}
        self._current: PacketRecord | None = None
        # Изменяемые накопители текущего блока (в PacketRecord — кортежи).
        self._cur_tls: list[str] = []
        self._cur_checks: list[ListCheckRecord] = []
        self._cur_lua: list[str] = []
        self._cur_check_context: tuple[str, int] | None = None

    def feed_line(self, line: str, line_no: int) -> None:
        line = line.rstrip("\r\n")
        if line.startswith("packet: id="):
            m = _RE_PACKET_HEADER.match(line)
            if m is not None:
                self._close_current()
                self._current = PacketRecord(
                    packet_id=int(m.group(1)),
                    line_no=line_no,
                    direction="out" if m.group(3) == "outbound" else "in",
                    length=int(m.group(2)),
                    ip_version=6 if m.group(4) == "1" else 4,
                )
                return
            m = _RE_PACKET_VERDICT.match(line)
            if m is not None:
                if self._current is not None:
                    self._current.verdict = _VERDICT_MAP[m.group(2)]
                    self._close_current()
                return
            self._result.unrecognized_packet_lines += 1
            return
        if self._current is not None:
            self._feed_block_line(line)
        else:
            self._feed_preamble_line(line)

    def _feed_block_line(self, line: str) -> None:
        pkt = self._current
        assert pkt is not None
        if _RE_DELAYED.match(line):
            pkt.delayed = True
            if _RE_REPLAY.match(line):
                pkt.replay_count += 1
            return
        if not pkt.src_ip:
            m = _RE_IP.match(line)
            if m is not None:
                pkt.ip_version = int(m.group(1))
                pkt.src_ip = m.group(2)
                pkt.dst_ip = m.group(3)
                pkt.proto = m.group(4)
                pkt.ttl = int(m.group(5))
                pkt.src_port = int(m.group(6) or 0)
                pkt.dst_port = int(m.group(7) or 0)
                pkt.tcp_flags = m.group(8) or ""
                return
        m = _RE_PROFILE_SEARCH.match(line)
        if m is not None:
            if m.group(1) != "unknown":
                pkt.l7proto = m.group(1)
            if m.group(2):
                pkt.hostname = m.group(2)
            return
        m = _RE_LIST_CHECK_CONTEXT.match(line)
        if m is not None:
            self._cur_check_context = (m.group(1), int(m.group(2)))
            return
        m = _RE_LIST_CHECK_RESULT.search(line)
        if m is not None:
            if m.group(3) == "positive":
                kind, profile_id = self._cur_check_context or ("", -1)
                self._cur_checks.append(
                    ListCheckRecord(
                        list_path=m.group(1),
                        kind=kind,
                        profile_id=profile_id,
                        target=m.group(2),
                    )
                )
            return
        m = (
            _RE_PROFILE_MATCH.match(line)
            or _RE_PROFILE_CACHED.match(line)
            or _RE_PROFILE_CONNTRACK.match(line)
        )
        if m is not None:
            pkt.profile_id = int(m.group(1))
            pkt.profile_name = m.group(2)
            # "using cached ..." и "using ... from conntrack entry" — профиль из кэша.
            pkt.profile_cached = line.startswith("using")
            return
        m = _RE_DPI_DESYNC.match(line)
        if m is not None:
            if m.group(1) != "unknown":
                pkt.l7proto = pkt.l7proto or m.group(1)
            if m.group(2) and m.group(2) != "unknown":
                pkt.payload_type = m.group(2)
            return
        m = _RE_HOSTNAME_LINE.match(line)
        if m is not None:
            pkt.hostname = pkt.hostname or m.group(1)
            return
        m = _RE_TLS_DETAIL.match(line)
        if m is not None:
            detail = f"{m.group(1)}: {m.group(2)}"
            if detail not in self._cur_tls:
                self._cur_tls.append(detail)
            return
        m = _RE_LUA_APPLIED.match(line)
        if m is not None:
            if m.group(1) not in self._cur_lua:
                self._cur_lua.append(m.group(1))
            return

    def _feed_preamble_line(self, line: str) -> None:
        m = _RE_PREAMBLE_PROFILE.match(line)
        if m is not None:
            profile_id = int(m.group(1))
            name, funcs = self._profiles.setdefault(profile_id, (m.group(2), []))
            if m.group(3) not in funcs:
                funcs.append(m.group(3))
            return
        m = _RE_PREAMBLE_LOADED.match(line)
        if m is not None:
            entry = (m.group(3), int(m.group(1)))
            if m.group(2) == "hosts":
                self._hostlists.append(entry)
            else:
                self._ipsets.append(entry)

    def _close_current(self) -> None:
        pkt = self._current
        if pkt is None:
            return
        self._current = None
        pkt.tls_details = tuple(self._cur_tls)
        pkt.positive_checks = tuple(self._cur_checks)
        pkt.lua_applied = tuple(self._cur_lua)
        self._cur_tls = []
        self._cur_checks = []
        self._cur_lua = []
        self._cur_check_context = None

        self._result.packets_total += 1
        self._result.positive_checks_total += len(pkt.positive_checks)
        if not pkt.src_ip:
            self._result.unparsed_blocks += 1
            return
        if pkt.direction == "out":
            remote_ip, remote_port = pkt.dst_ip, pkt.dst_port
        else:
            remote_ip, remote_port = pkt.src_ip, pkt.src_port
        key = (pkt.proto, remote_ip, remote_port)
        conn = self._connections.get(key)
        if conn is None:
            conn = ConnectionRecord(
                proto=pkt.proto,
                remote_ip=remote_ip,
                remote_port=remote_port,
                first_line_no=pkt.line_no,
            )
            self._connections[key] = conn
            self._result.connections.append(conn)
        conn.packets_total += 1
        if pkt.direction == "out":
            conn.packets_out += 1
        else:
            conn.packets_in += 1
        conn.verdict_counts[pkt.verdict] = conn.verdict_counts.get(pkt.verdict, 0) + 1
        if pkt.hostname and not conn.hostname:
            conn.hostname = pkt.hostname
        if pkt.l7proto and not conn.l7proto:
            conn.l7proto = pkt.l7proto
        if pkt.profile_id is not None and pkt.profile_id not in conn.profile_ids:
            conn.profile_ids = conn.profile_ids + (pkt.profile_id,)
            conn.profile_names = conn.profile_names + (pkt.profile_name,)
        for check in pkt.positive_checks:
            name = os.path.basename(check.list_path.replace("\\", "/"))
            if name not in conn.positive_lists:
                conn.positive_lists = conn.positive_lists + (name,)
        for lua_name in pkt.lua_applied:
            if lua_name not in conn.lua_applied:
                conn.lua_applied = conn.lua_applied + (lua_name,)
        if len(conn.packets) < self._max_packets:
            conn.packets.append(pkt)
        else:
            conn.packets_truncated = True

    def finish(self) -> WinwsLogParseResult:
        self._close_current()
        self._result.profiles = {
            profile_id: f"{name or 'noname'}: {', '.join(funcs)}"
            for profile_id, (name, funcs) in sorted(self._profiles.items())
        }
        self._result.hostlists = tuple(self._hostlists)
        self._result.ipsets = tuple(self._ipsets)
        return self._result


def parse_winws_log_stream(
    stream: TextIO,
    *,
    total_bytes: int = 0,
    progress_cb: Callable[[int, int], None] | None = None,
    cancel_cb: Callable[[], bool] | None = None,
    max_packets_per_connection: int = DEFAULT_MAX_PACKETS_PER_CONNECTION,
) -> WinwsLogParseResult:
    parser = WinwsLogParser(max_packets_per_connection=max_packets_per_connection)
    bytes_read = 0
    for line_no, line in enumerate(stream, start=1):
        parser.feed_line(line, line_no)
        # Приближение (символы ≈ байты) — достаточно для прогресс-бара.
        bytes_read += len(line)
        if line_no % _CALLBACK_LINE_INTERVAL == 0:
            if cancel_cb is not None and cancel_cb():
                result = parser.finish()
                result.cancelled = True
                return result
            if progress_cb is not None:
                progress_cb(bytes_read, total_bytes)
    result = parser.finish()
    if progress_cb is not None:
        progress_cb(total_bytes or bytes_read, total_bytes or bytes_read)
    return result


def parse_winws_log_file(
    path: str,
    *,
    progress_cb: Callable[[int, int], None] | None = None,
    cancel_cb: Callable[[], bool] | None = None,
    max_packets_per_connection: int = DEFAULT_MAX_PACKETS_PER_CONNECTION,
) -> WinwsLogParseResult:
    total_bytes = os.path.getsize(path)
    with open(path, "r", encoding="utf-8", errors="replace") as stream:
        result = parse_winws_log_stream(
            stream,
            total_bytes=total_bytes,
            progress_cb=progress_cb,
            cancel_cb=cancel_cb,
            max_packets_per_connection=max_packets_per_connection,
        )
    result.file_path = path
    return result
