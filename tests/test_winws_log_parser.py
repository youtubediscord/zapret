from __future__ import annotations

import io
from pathlib import Path

import pytest

from winws_log_analyzer.models import (
    VERDICT_DROP,
    VERDICT_MODIFIED,
    VERDICT_UNMODIFIED,
)
from winws_log_analyzer.parser import (
    parse_winws_log_file,
    parse_winws_log_stream,
)

FIXTURE = Path(__file__).parent / "fixtures" / "winws2_debug_sample.log"


@pytest.fixture(scope="module")
def result():
    return parse_winws_log_file(str(FIXTURE))


def _conn(result, remote_ip):
    matches = [c for c in result.connections if c.remote_ip == remote_ip]
    assert len(matches) == 1, f"ожидалось одно соединение с {remote_ip}"
    return matches[0]


def test_counts(result):
    # 6 заголовков блоков в фикстуре; терминаторы и REPLAY-строки не считаются.
    assert result.packets_total == 6
    # 5 соединений: пакеты id=5 (out) и id=6 (in) сливаются в одно.
    assert len(result.connections) == 5
    assert result.unparsed_blocks == 0
    assert result.unrecognized_packet_lines == 0
    assert result.positive_checks_total == 1
    assert not result.cancelled


def test_verdict_terminator_not_treated_as_header(result):
    conn = _conn(result, "85.172.79.187")
    assert conn.packets_total == 1
    assert conn.verdict_counts == {VERDICT_UNMODIFIED: 1}


def test_connection_grouping_merges_directions(result):
    # id=5 (outbound → 128.116.31.3:443) и id=6 (inbound ← 128.116.31.3:443)
    conn = _conn(result, "128.116.31.3")
    assert conn.packets_total == 2
    assert conn.packets_out == 1
    assert conn.packets_in == 1
    assert conn.remote_port == 443
    assert conn.proto == "tcp"


def test_replay_lines_do_not_create_packets(result):
    conn = _conn(result, "185.26.182.94")
    assert conn.packets_total == 1
    pkt = conn.packets[0]
    assert pkt.packet_id == 59
    assert pkt.delayed
    assert pkt.replay_count == 2
    assert pkt.verdict == VERDICT_DROP


def test_hostname_l7_tls_extraction(result):
    conn = _conn(result, "185.26.182.94")
    assert conn.hostname == "merchandise.opera-api.com"
    assert conn.l7proto == "tls"
    pkt = conn.packets[0]
    assert pkt.payload_type == "tls_client_hello"
    assert "handshake version: TLS 1.2" in pkt.tls_details
    assert "ALPN: h2" in pkt.tls_details
    assert "ECH: present" in pkt.tls_details


def test_positive_list_checks(result):
    conn = _conn(result, "149.154.167.99")
    assert conn.positive_lists == ("ipset-discord.txt",)
    pkt = conn.packets[0]
    assert len(pkt.positive_checks) == 1
    check = pkt.positive_checks[0]
    assert check.kind == "ipset"
    assert check.profile_id == 3
    assert check.target == "149.154.167.99"
    assert conn.profile_ids == (3,)


def test_cached_profile(result):
    conn = _conn(result, "128.116.31.3")
    pkt = conn.packets[0]
    assert pkt.profile_cached
    assert pkt.profile_id == 0
    assert pkt.profile_name == "no_action"


def test_lua_applied_and_modified_verdict(result):
    conn = _conn(result, "13.107.246.53")
    assert conn.lua_applied == ("multisplit_11_1",)
    assert conn.verdict_counts == {VERDICT_MODIFIED: 1}
    assert conn.profile_ids == (11,)


def test_preamble_profiles_and_lists(result):
    assert result.profiles[3] == "noname: tls_multisplit_sni"
    assert result.profiles[17] == "noname: send, syndata"
    assert ("D:\\ZapretTwo\\lists\\russia-blacklist.txt", 117144) in result.hostlists
    assert ("D:\\ZapretTwo\\lists\\ipset-discord.txt", 62) in result.ipsets


def test_packet_fields(result):
    conn = _conn(result, "85.172.79.187")
    pkt = conn.packets[0]
    assert pkt.direction == "out"
    assert pkt.proto == "udp"
    assert pkt.src_port == 53445
    assert pkt.dst_port == 53579
    assert pkt.ttl == 128
    assert pkt.ip_version == 4


def test_empty_file():
    result = parse_winws_log_stream(io.StringIO(""))
    assert result.packets_total == 0
    assert result.connections == []


def test_garbage_lines_ignored():
    garbage = "\n".join(["мусор", ": : :", "packet: id=abc nonsense", ""] * 10)
    result = parse_winws_log_stream(io.StringIO(garbage))
    assert result.packets_total == 0


_HEADER = "packet: id={i} len=80 outbound IPv6=0 IPChecksum=1 TCPChecksum=1 UDPChecksum=1 IfIdx=8.0\n"
_IP_LINE = "IP4: 10.0.0.1 => 1.2.3.4 proto=tcp ttl=128 sport=1000 dport=443 flags=A seq=1 ack_seq=0\n"


def test_modified_verdict_with_len_suffix():
    # Актуальные сборки winws2 (nfqws.c) пишут "reinject modified len 74 => 148".
    text = (
        _HEADER.replace("{i}", "1")
        + _IP_LINE
        + "packet: id=1 reinject modified len 74 => 148\n"
    )
    result = parse_winws_log_stream(io.StringIO(text))
    assert result.unrecognized_packet_lines == 0
    assert result.connections[0].verdict_counts == {VERDICT_MODIFIED: 1}


def test_profile_search_with_icmp_field():
    text = (
        _HEADER.replace("{i}", "1")
        + _IP_LINE
        + "desync profile search for tcp ip=1.2.3.4 port=443 icmp=0:0 "
        "l7proto=tls ssid='' hostname='example.com'\n"
        "packet: id=1 reinject unmodified\n"
    )
    result = parse_winws_log_stream(io.StringIO(text))
    conn = result.connections[0]
    assert conn.hostname == "example.com"
    assert conn.l7proto == "tls"


def test_profile_search_with_ip_pair():
    text = (
        _HEADER.replace("{i}", "1")
        + _IP_LINE
        + "desync profile search for tcp ip1=10.0.0.1 ip2=1.2.3.4 port=443 icmp=0:0 "
        "l7proto=quic ssid='' hostname='pair.example.com'\n"
        "packet: id=1 reinject unmodified\n"
    )
    result = parse_winws_log_stream(io.StringIO(text))
    conn = result.connections[0]
    assert conn.hostname == "pair.example.com"
    assert conn.l7proto == "quic"


def test_profile_from_conntrack_entry():
    text = (
        _HEADER.replace("{i}", "1")
        + _IP_LINE
        + "using desync profile 7 (myprofile) from conntrack entry\n"
        "packet: id=1 reinject unmodified\n"
    )
    result = parse_winws_log_stream(io.StringIO(text))
    pkt = result.connections[0].packets[0]
    assert pkt.profile_id == 7
    assert pkt.profile_name == "myprofile"
    assert pkt.profile_cached


def test_unrecognized_packet_lines_counted():
    # Linux-формат nfqws намеренно не поддерживается (GUI только для Windows),
    # но такие строки должны попадать в счётчик, а не теряться молча.
    text = (
        "packet: id=1 len=60 mark=00000000 ifin=eth0(2) ifout=(0)\n"
        "packet: id=1 pass unmodified\n"
        + _HEADER.replace("{i}", "2")
        + _IP_LINE
        + "packet: id=2 reinject unmodified\n"
    )
    result = parse_winws_log_stream(io.StringIO(text))
    assert result.unrecognized_packet_lines == 2
    assert result.packets_total == 1


def test_block_without_verdict_is_closed():
    text = (
        "packet: id=1 len=80 outbound IPv6=0 IPChecksum=1 TCPChecksum=1 UDPChecksum=1 IfIdx=8.0\n"
        "IP4: 10.0.0.1 => 1.2.3.4 proto=tcp ttl=128 sport=1000 dport=443 flags=S seq=1 ack_seq=0\n"
    )
    result = parse_winws_log_stream(io.StringIO(text))
    assert result.packets_total == 1
    assert result.connections[0].packets[0].verdict == ""


def test_truncation_limit():
    block = (
        "packet: id={i} len=80 outbound IPv6=0 IPChecksum=1 TCPChecksum=1 UDPChecksum=1 IfIdx=8.0\n"
        "IP4: 10.0.0.1 => 1.2.3.4 proto=tcp ttl=128 sport=1000 dport=443 flags=A seq=1 ack_seq=0\n"
        "packet: id={i} reinject unmodified\n\n"
    )
    text = "".join(block.replace("{i}", str(i)) for i in range(5))
    result = parse_winws_log_stream(io.StringIO(text), max_packets_per_connection=2)
    conn = result.connections[0]
    assert conn.packets_total == 5
    assert len(conn.packets) == 2
    assert conn.packets_truncated


def test_progress_and_cancel(tmp_path):
    block = (
        "packet: id=1 len=80 outbound IPv6=0 IPChecksum=1 TCPChecksum=1 UDPChecksum=1 IfIdx=8.0\n"
        "IP4: 10.0.0.1 => 1.2.3.4 proto=tcp ttl=128 sport=1000 dport=443 flags=A seq=1 ack_seq=0\n"
        "packet: id=1 reinject unmodified\n"
    )
    path = tmp_path / "big.log"
    path.write_text(block * 3000, encoding="utf-8")

    progress_calls = []
    result = parse_winws_log_file(
        str(path), progress_cb=lambda done, total: progress_calls.append((done, total))
    )
    assert progress_calls
    assert progress_calls[-1][0] == progress_calls[-1][1]
    assert result.packets_total == 3000

    cancelled = parse_winws_log_file(str(path), cancel_cb=lambda: True)
    assert cancelled.cancelled
    assert cancelled.packets_total < 3000
