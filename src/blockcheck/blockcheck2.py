"""
Zapret Configuration Tester
Тестирует HTTP, TLS 1.2, TLS 1.3 и UDP/STUN.
"""

import socket
import ssl
import time
import re
import sys
import struct
import secrets
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from utils.windows_icmp import ping_ipv4_host_winapi


class Colors:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    GRAY = "\033[90m"
    RESET = "\033[0m"


def cprint(text: str, color: str = Colors.RESET, end: str = "\n"):
    print(f"{color}{text}{Colors.RESET}", end=end)


# =============================================================================
# STUN Protocol Implementation
# =============================================================================

def build_stun_request() -> bytes:
    """
    Собирает STUN Binding Request по RFC 5389.

    Формат заголовка STUN (20 байт):
    - 2 байта: Message Type (0x0001 = Binding Request)
    - 2 байта: Message Length (0 для простого запроса)
    - 4 байта: Magic Cookie (0x2112A442)
    - 12 байт: Transaction ID (случайный)
    """
    msg_type = 0x0001  # Binding Request
    msg_length = 0
    magic_cookie = 0x2112A442
    transaction_id = secrets.token_bytes(12)  # 96 бит случайных данных

    header = struct.pack(
        '>HHI',  # big-endian: 2 bytes, 2 bytes, 4 bytes
        msg_type,
        msg_length,
        magic_cookie
    ) + transaction_id

    return header


def parse_stun_response(data: bytes) -> dict:
    """
    Парсит STUN Binding Response.

    Возвращает dict с публичным IP и портом, или None при ошибке.
    """
    if len(data) < 20:
        return None

    # Парсим заголовок
    msg_type, msg_length, magic_cookie = struct.unpack('>HHI', data[:8])

    # Проверяем, что это Binding Response (0x0101)
    if msg_type != 0x0101:
        return None

    # Ищем атрибут XOR-MAPPED-ADDRESS (0x0020) или MAPPED-ADDRESS (0x0001)
    offset = 20  # После заголовка

    while offset < len(data):
        if offset + 4 > len(data):
            break

        attr_type, attr_length = struct.unpack('>HH', data[offset:offset+4])
        offset += 4

        if attr_type == 0x0020:  # XOR-MAPPED-ADDRESS
            if attr_length >= 8:
                family = data[offset + 1]
                xor_port = struct.unpack('>H', data[offset+2:offset+4])[0]
                port = xor_port ^ (0x2112A442 >> 16)

                if family == 0x01:  # IPv4
                    xor_ip = struct.unpack('>I', data[offset+4:offset+8])[0]
                    ip_int = xor_ip ^ 0x2112A442
                    ip = socket.inet_ntoa(struct.pack('>I', ip_int))
                    return {"ip": ip, "port": port, "family": "IPv4"}

        elif attr_type == 0x0001:  # MAPPED-ADDRESS (fallback)
            if attr_length >= 8:
                family = data[offset + 1]
                port = struct.unpack('>H', data[offset+2:offset+4])[0]

                if family == 0x01:  # IPv4
                    ip = socket.inet_ntoa(data[offset+4:offset+8])
                    return {"ip": ip, "port": port, "family": "IPv4"}

        # Переходим к следующему атрибуту (выравнивание на 4 байта)
        offset += attr_length
        if attr_length % 4 != 0:
            offset += 4 - (attr_length % 4)

    return None


def test_stun(host: str, port: int = 3478, timeout: int = 5) -> dict:
    """
    Тестирует STUN-сервер через UDP.

    Возвращает dict с результатами:
    - success: bool
    - time_ms: float
    - public_ip: str (если успешно)
    - public_port: int (если успешно)
    - error: str (если ошибка)
    """
    result = {
        "success": False,
        "time_ms": None,
        "public_ip": None,
        "public_port": None,
        "error": None,
    }

    start = time.time()

    try:
        # Резолвим хост
        try:
            ip = socket.gethostbyname(host)
        except socket.gaierror:
            result["error"] = "DNS_ERR"
            return result

        # Создаём UDP-сокет
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)

        # Отправляем STUN Binding Request
        request = build_stun_request()
        sock.sendto(request, (ip, port))

        # Ждём ответ
        response, addr = sock.recvfrom(1024)
        sock.close()

        elapsed = (time.time() - start) * 1000
        result["time_ms"] = round(elapsed, 2)

        # Парсим ответ
        parsed = parse_stun_response(response)
        if parsed:
            result["success"] = True
            result["public_ip"] = parsed["ip"]
            result["public_port"] = parsed["port"]
        else:
            result["error"] = "PARSE_ERR"

    except socket.timeout:
        result["time_ms"] = round((time.time() - start) * 1000, 2)
        result["error"] = "TIMEOUT"
    except ConnectionResetError:
        result["time_ms"] = round((time.time() - start) * 1000, 2)
        result["error"] = "RESET"
    except Exception as e:
        result["time_ms"] = round((time.time() - start) * 1000, 2)
        result["error"] = "ERROR"

    return result


def test_udp_port(host: str, port: int, timeout: int = 3) -> dict:
    """
    Простой тест UDP-порта (отправляем пакет, ждём ответ или ICMP unreachable).
    Менее надёжен чем STUN, но работает для любого UDP-сервиса.
    """
    result = {
        "success": False,
        "time_ms": None,
        "error": None,
    }

    start = time.time()

    try:
        ip = socket.gethostbyname(host)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)

        # Отправляем пустой пакет
        sock.sendto(b'\x00', (ip, port))

        # Пытаемся получить ответ
        try:
            data, addr = sock.recvfrom(1024)
            elapsed = (time.time() - start) * 1000
            result["success"] = True
            result["time_ms"] = round(elapsed, 2)
        except socket.timeout:
            # Таймаут может означать, что пакет дошёл, но ответа нет
            # Это нормально для многих UDP-сервисов
            elapsed = (time.time() - start) * 1000
            result["time_ms"] = round(elapsed, 2)
            result["error"] = "NO_REPLY"

        sock.close()

    except Exception as e:
        result["time_ms"] = round((time.time() - start) * 1000, 2)
        result["error"] = "ERROR"

    return result


# =============================================================================
# HTTPS Testing (existing code)
# =============================================================================

def test_https(host: str, port: int = 443, timeout: int = 10, tls_version: str = None) -> dict:
    """Тестирует HTTPS-соединение."""
    result = {
        "success": False,
        "status_code": None,
        "time_ms": None,
        "error": None,
        "tls_version": None,
    }

    start = time.time()

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)

        context = ssl.create_default_context()

        if tls_version == "1.2":
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.maximum_version = ssl.TLSVersion.TLSv1_2
        elif tls_version == "1.3":
            context.minimum_version = ssl.TLSVersion.TLSv1_3
            context.maximum_version = ssl.TLSVersion.TLSv1_3

        ssock = context.wrap_socket(sock, server_hostname=host)
        ssock.connect((host, port))

        result["tls_version"] = ssock.version()

        request = f"GET / HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\nUser-Agent: Mozilla/5.0\r\n\r\n"
        ssock.send(request.encode())

        response = b""
        while len(response) < 1024:
            chunk = ssock.recv(4096)
            if not chunk:
                break
            response += chunk

        ssock.close()

        elapsed = (time.time() - start) * 1000

        first_line = response.decode('utf-8', errors='ignore').split('\r\n')[0]
        match = re.search(r'HTTP/\d\.?\d?\s+(\d{3})', first_line)
        if match:
            result["status_code"] = int(match.group(1))

        result["success"] = True
        result["time_ms"] = round(elapsed, 2)

    except socket.timeout:
        result["time_ms"] = round((time.time() - start) * 1000, 2)
        result["error"] = "TIMEOUT"
    except ssl.SSLError as e:
        result["time_ms"] = round((time.time() - start) * 1000, 2)
        if "unsupported" in str(e).lower() or "version" in str(e).lower():
            result["error"] = "UNSUP"
        else:
            result["error"] = "TLS_ERR"
    except ConnectionResetError:
        result["time_ms"] = round((time.time() - start) * 1000, 2)
        result["error"] = "RESET"
    except ConnectionRefusedError:
        result["time_ms"] = round((time.time() - start) * 1000, 2)
        result["error"] = "REFUSED"
    except OSError:
        result["time_ms"] = round((time.time() - start) * 1000, 2)
        result["error"] = "ERROR"
    except Exception:
        result["time_ms"] = round((time.time() - start) * 1000, 2)
        result["error"] = "ERROR"

    return result


def ping_host(host: str, count: int = 2, timeout: int = 3) -> str:
    """Пингует хост."""
    try:
        ping_result = ping_ipv4_host_winapi(
            host,
            count=count,
            timeout_ms=int(timeout * 1000),
        )
        if ping_result.ok and ping_result.average_ms is not None:
            return f"{ping_result.average_ms:.0f}ms"
        if str(ping_result.error_code or "").strip().upper() in {"TIMEOUT", "NO_REPLY"}:
            return "Timeout"
        return str(ping_result.detail or "Error")
    except Exception:
        return "Error"


def extract_host(url: str) -> str:
    """Извлекает hostname из URL."""
    host = re.sub(r'^https?://', '', url)
    host = re.sub(r'[:/].*$', '', host)
    return host


def load_targets(filepath: str = None) -> list:
    """Загружает цели."""
    default_targets = [
        # HTTPS targets
        {"name": "Discord", "value": "https://discord.com"},
        {"name": "Discord GW", "value": "https://gateway.discord.gg"},
        {"name": "Discord CDN", "value": "https://cdn.discordapp.com"},
        {"name": "YouTube", "value": "https://www.youtube.com"},
        {"name": "YouTube Short", "value": "https://youtu.be"},
        {"name": "YT Images", "value": "https://i.ytimg.com"},
        {"name": "Google", "value": "https://www.google.com"},
        {"name": "Cloudflare", "value": "https://www.cloudflare.com"},
        # STUN targets (UDP)
        {"name": "Google STUN", "value": "STUN:stun.l.google.com:19302"},
        {"name": "Google STUN2", "value": "STUN:stun1.l.google.com:19302"},
        {"name": "CF STUN", "value": "STUN:stun.cloudflare.com:3478"},
        # Ping targets
        {"name": "CF DNS", "value": "PING:1.1.1.1"},
        {"name": "Google DNS", "value": "PING:8.8.8.8"},
    ]

    if not filepath:
        return default_targets

    try:
        targets = []
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                match = re.match(r'^(\w+)\s*=\s*"(.+)"', line)
                if match:
                    targets.append({"name": match.group(1), "value": match.group(2)})
        if targets:
            return targets
    except FileNotFoundError:
        pass

    return default_targets


def format_result(res: dict) -> tuple:
    """Форматирует результат."""
    if res["success"]:
        return "OK", Colors.GREEN
    elif res.get("error") == "UNSUP":
        return "UNSUP", Colors.YELLOW
    elif res.get("error") == "NO_REPLY":
        return "NO_RPL", Colors.YELLOW
    else:
        return res.get("error", "ERROR"), Colors.RED


def test_target(target: dict, timeout: int = 10) -> dict:
    """Тестирует одну цель."""
    name = target["name"]
    value = target["value"]

    entry = {"name": name, "value": value}

    if value.startswith("PING:"):
        host = value.replace("PING:", "").strip()
        entry["type"] = "ping"
        entry["ping"] = ping_host(host)

    elif value.startswith("STUN:"):
        # Формат: STUN:host:port
        parts = value.replace("STUN:", "").strip()
        if ":" in parts:
            host, port = parts.rsplit(":", 1)
            port = int(port)
        else:
            host = parts
            port = 3478

        entry["type"] = "stun"
        entry["stun"] = test_stun(host, port, timeout=timeout)
        entry["ping"] = ping_host(host, count=2, timeout=2)

    else:
        host = extract_host(value)
        entry["type"] = "https"
        entry["http"] = test_https(host, timeout=timeout, tls_version=None)
        entry["tls12"] = test_https(host, timeout=timeout, tls_version="1.2")
        entry["tls13"] = test_https(host, timeout=timeout, tls_version="1.3")
        entry["ping"] = ping_host(host, count=2, timeout=2)

    return entry


def run_tests(targets: list, timeout: int = 10, parallel: int = 4) -> dict:
    """Запускает тесты."""
    results = []
    stats = {
        "http_ok": 0, "http_fail": 0,
        "tls12_ok": 0, "tls12_fail": 0, "tls12_unsup": 0,
        "tls13_ok": 0, "tls13_fail": 0, "tls13_unsup": 0,
        "stun_ok": 0, "stun_fail": 0,
        "ping_ok": 0, "ping_fail": 0
    }

    # Разделяем по типам для разных заголовков
    https_targets = [t for t in targets if not t["value"].startswith(("PING:", "STUN:"))]
    stun_targets = [t for t in targets if t["value"].startswith("STUN:")]
    ping_targets = [t for t in targets if t["value"].startswith("PING:")]

    max_name = max(len(t["name"]) for t in targets)

    with ThreadPoolExecutor(max_workers=parallel) as executor:
        futures = {executor.submit(test_target, t, timeout): t for t in targets}
        completed = {}
        for future in as_completed(futures):
            target = futures[future]
            completed[target["name"]] = future.result()

    # HTTPS секция
    if https_targets:
        print()
        cprint(f"  {'HTTPS Targets':<{max_name}}  {'HTTP':<8} {'TLS1.2':<8} {'TLS1.3':<8} {'Ping':<10}", Colors.CYAN)
        cprint("-" * (max_name + 45), Colors.GRAY)

        for target in https_targets:
            entry = completed[target["name"]]
            results.append(entry)

            name = entry["name"]
            http_res = entry["http"]
            tls12_res = entry["tls12"]
            tls13_res = entry["tls13"]
            ping = entry["ping"]

            # Stats
            if http_res["success"]: stats["http_ok"] += 1
            else: stats["http_fail"] += 1

            if tls12_res["success"]: stats["tls12_ok"] += 1
            elif tls12_res["error"] == "UNSUP": stats["tls12_unsup"] += 1
            else: stats["tls12_fail"] += 1

            if tls13_res["success"]: stats["tls13_ok"] += 1
            elif tls13_res["error"] == "UNSUP": stats["tls13_unsup"] += 1
            else: stats["tls13_fail"] += 1

            if "ms" in ping: stats["ping_ok"] += 1
            else: stats["ping_fail"] += 1

            # Output
            cprint(f"  {name:<{max_name}}  ", end="")

            http_txt, http_col = format_result(http_res)
            cprint(f"{http_txt:<8}", http_col, end=" ")

            tls12_txt, tls12_col = format_result(tls12_res)
            cprint(f"{tls12_txt:<8}", tls12_col, end=" ")

            tls13_txt, tls13_col = format_result(tls13_res)
            cprint(f"{tls13_txt:<8}", tls13_col, end=" ")

            ping_color = Colors.GREEN if "ms" in ping else Colors.YELLOW
            cprint(ping, ping_color)

    # STUN секция
    if stun_targets:
        print()
        cprint(f"  {'STUN Targets':<{max_name}}  {'UDP':<10} {'Public IP':<18} {'Ping':<10}", Colors.CYAN)
        cprint("-" * (max_name + 45), Colors.GRAY)

        for target in stun_targets:
            entry = completed[target["name"]]
            results.append(entry)

            name = entry["name"]
            stun_res = entry["stun"]
            ping = entry["ping"]

            if stun_res["success"]: stats["stun_ok"] += 1
            else: stats["stun_fail"] += 1

            if "ms" in ping: stats["ping_ok"] += 1
            else: stats["ping_fail"] += 1

            cprint(f"  {name:<{max_name}}  ", end="")

            if stun_res["success"]:
                time_str = f"{stun_res['time_ms']:.0f}ms"
                cprint(f"{'OK':<10}", Colors.GREEN, end=" ")
                cprint(f"{stun_res['public_ip']:<18}", Colors.GRAY, end=" ")
            else:
                cprint(f"{stun_res['error']:<10}", Colors.RED, end=" ")
                cprint(f"{'--':<18}", Colors.GRAY, end=" ")

            ping_color = Colors.GREEN if "ms" in ping else Colors.YELLOW
            cprint(ping, ping_color)

    # Ping секция
    if ping_targets:
        print()
        cprint(f"  {'Ping Targets':<{max_name}}  {'ICMP':<10}", Colors.CYAN)
        cprint("-" * (max_name + 15), Colors.GRAY)

        for target in ping_targets:
            entry = completed[target["name"]]
            results.append(entry)

            name = entry["name"]
            ping = entry["ping"]

            if "ms" in ping: stats["ping_ok"] += 1
            else: stats["ping_fail"] += 1

            cprint(f"  {name:<{max_name}}  ", end="")
            ping_color = Colors.GREEN if "ms" in ping else Colors.RED
            cprint(ping, ping_color)

    return {"results": results, "stats": stats}


def print_summary(stats: dict):
    """Выводит итоги."""
    print()
    cprint("=" * 60, Colors.CYAN)
    cprint("SUMMARY", Colors.CYAN)
    cprint("=" * 60, Colors.CYAN)

    # HTTP
    http_total = stats["http_ok"] + stats["http_fail"]
    if http_total > 0:
        http_pct = stats["http_ok"] / http_total * 100
        cprint(f"  HTTP:    ", end="")
        cprint(f"{stats['http_ok']} OK", Colors.GREEN, end="")
        cprint(f" / {stats['http_fail']} FAIL  ({http_pct:.0f}%)")

    # TLS 1.2
    tls12_total = stats["tls12_ok"] + stats["tls12_fail"] + stats["tls12_unsup"]
    if tls12_total > 0:
        tls12_pct = stats["tls12_ok"] / tls12_total * 100
        cprint(f"  TLS1.2:  ", end="")
        cprint(f"{stats['tls12_ok']} OK", Colors.GREEN, end="")
        cprint(f" / {stats['tls12_fail']} FAIL", Colors.RED, end="")
        if stats["tls12_unsup"] > 0:
            cprint(f" / {stats['tls12_unsup']} UNSUP", Colors.YELLOW, end="")
        cprint(f"  ({tls12_pct:.0f}%)")

    # TLS 1.3
    tls13_total = stats["tls13_ok"] + stats["tls13_fail"] + stats["tls13_unsup"]
    if tls13_total > 0:
        tls13_pct = stats["tls13_ok"] / tls13_total * 100
        cprint(f"  TLS1.3:  ", end="")
        cprint(f"{stats['tls13_ok']} OK", Colors.GREEN, end="")
        cprint(f" / {stats['tls13_fail']} FAIL", Colors.RED, end="")
        if stats["tls13_unsup"] > 0:
            cprint(f" / {stats['tls13_unsup']} UNSUP", Colors.YELLOW, end="")
        cprint(f"  ({tls13_pct:.0f}%)")

    # STUN
    stun_total = stats["stun_ok"] + stats["stun_fail"]
    if stun_total > 0:
        stun_pct = stats["stun_ok"] / stun_total * 100
        cprint(f"  STUN:    ", end="")
        cprint(f"{stats['stun_ok']} OK", Colors.GREEN, end="")
        cprint(f" / {stats['stun_fail']} FAIL  ({stun_pct:.0f}%)")

    # Ping
    cprint(f"  Ping:    ", end="")
    cprint(f"{stats['ping_ok']} OK", Colors.GREEN, end="")
    cprint(f" / {stats['ping_fail']} FAIL", Colors.YELLOW)

    return stats["http_ok"] + stats["tls12_ok"] + stats["tls13_ok"] + stats["stun_ok"]


def main():
    if sys.platform == "win32":
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)

    print()
    cprint("=" * 60, Colors.CYAN)
    cprint("  ZAPRET CONFIGURATION TESTER", Colors.CYAN)
    cprint("  Testing HTTP, TLS 1.2, TLS 1.3, UDP/STUN", Colors.GRAY)
    cprint("=" * 60, Colors.CYAN)

    targets_file = None
    for arg in sys.argv[1:]:
        if not arg.startswith("-") and Path(arg).exists():
            targets_file = arg
            break

    targets = load_targets(targets_file)
    cprint(f"\nTargets: {len(targets)}", Colors.GRAY)

    start_time = time.time()
    data = run_tests(targets, timeout=10, parallel=4)
    elapsed = time.time() - start_time

    score = print_summary(data["stats"])
    cprint(f"\nCompleted in {elapsed:.1f}s", Colors.GRAY)

    return score


if __name__ == "__main__":
    main()
