from __future__ import annotations

import concurrent.futures
import socket
import ssl
import subprocess
import time
from base64 import b64encode
from collections.abc import Callable
from os import urandom

from log.log import log

from telegram_proxy.page_settings_controller import TelegramProxySettingsController


class TelegramProxyDiagnosticsController:
    DC_TARGETS = [
        ("149.154.167.220", "WSS relay", "—"),
        ("149.154.167.50", "DC2", "kws2"),
        ("149.154.167.41", "DC2", "kws2"),
        ("149.154.167.91", "DC4", "kws4"),
        ("149.154.175.53", "DC1", "—"),
        ("149.154.175.55", "DC1", "—"),
        ("149.154.175.100", "DC3 (→DC1)", "—"),
        ("91.108.56.134", "DC5", "—"),
        ("91.108.56.149", "DC5", "—"),
        ("91.105.192.100", "DC203 CDN", "—"),
        ("149.154.167.151", "DC2 media", "—"),
        ("149.154.167.222", "DC2 media", "—"),
        ("149.154.175.52", "DC1 media", "—"),
        ("91.108.56.102", "DC5 media", "—"),
        ("149.154.175.102", "DC3 media", "—"),
        ("149.154.164.250", "DC4 media", "—"),
    ]

    WSS_PROBE_TARGETS = [
        ("149.154.167.220", "kws1.web.telegram.org", 1),
        ("149.154.167.220", "kws2.web.telegram.org", 2),
        ("149.154.167.220", "kws3.web.telegram.org", 3),
        ("149.154.167.220", "kws4.web.telegram.org", 4),
        ("149.154.167.220", "kws5.web.telegram.org", 5),
        ("149.154.167.220", "zws2.web.telegram.org", 2),
        ("149.154.167.220", "zws4.web.telegram.org", 4),
    ]

    @classmethod
    def run_all(
        cls,
        proxy_port: int,
        *,
        progress_callback: Callable[[str], None] | None = None,
    ) -> str:
        from telegram_proxy.wss_proxy import check_relay_reachable

        t0 = time.time()
        results: list[str] = []

        def publish() -> None:
            if progress_callback is not None:
                try:
                    progress_callback("\n".join(results))
                except Exception:
                    pass

        with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
            dc_futures = {
                executor.submit(cls._test_single_ip, ip, dc, wss): (ip, dc)
                for ip, dc, wss in cls.DC_TARGETS
            }
            wss_futures = [
                executor.submit(cls._test_wss_relay, ip, domain, dc)
                for ip, domain, dc in cls.WSS_PROBE_TARGETS
            ]

            relay_future = executor.submit(check_relay_reachable, timeout=5.0)
            dns_relay_future = executor.submit(
                check_relay_reachable,
                relay_ip="149.154.167.99",
                timeout=5.0,
            )

            sni_future = executor.submit(cls._test_sni_vs_ip)
            http_future = executor.submit(cls._test_http_port80)
            proxy_future = executor.submit(cls._test_proxy_liveness, "127.0.0.1", proxy_port)
            winws_future = executor.submit(cls._check_winws2_running)

            upstream_future = None
            upstream_target = TelegramProxySettingsController.load_upstream_test_target()
            if upstream_target is not None:
                upstream_future = executor.submit(cls._test_upstream_proxy, *upstream_target)

            relay_result = relay_future.result()
            results.extend(
                [
                    "=" * 76,
                    "  ДОСТУПНОСТЬ WSS RELAY",
                    "=" * 76,
                    "  149.154.167.220:443 (web.telegram.org)",
                ]
            )
            if relay_result["reachable"]:
                results.append(f"  TCP+TLS: OK ({relay_result['ms']:.0f}ms)")
            else:
                results.append(f"  TCP+TLS: TIMEOUT ({relay_result['ms']:.0f}ms) <- ЗАБЛОКИРОВАН")
                results.append("  ! WSS relay недоступен — прокси не сможет проксировать через WSS.")
                try:
                    zapret_running = winws_future.result(timeout=0.1)
                except Exception:
                    zapret_running = None
                if zapret_running is not None:
                    results.append(f"  Zapret запущен: {'ДА' if zapret_running else 'НЕТ'}")
                if relay_result["error"]:
                    results.append(f"  Ошибка: {relay_result['error']}")
            publish()

            dns_relay_result = dns_relay_future.result()
            if dns_relay_result["reachable"]:
                results.append(f"  DNS relay (149.154.167.99): OK ({dns_relay_result['ms']:.0f}ms)")
            else:
                results.append(f"  DNS relay (149.154.167.99): TIMEOUT ({dns_relay_result['ms']:.0f}ms)")
            results.append("  (не используется — .220 стабильнее для медиа)")
            results.append("")

            results.extend(
                [
                    "=" * 76,
                    "  ПРЯМЫЕ ПОДКЛЮЧЕНИЯ К TELEGRAM DC",
                    "=" * 76,
                    f"{'IP':<20} {'DC':<12} {'TCP':>8}  {'TLS':>8}  {'Статус'}",
                    "-" * 76,
                ]
            )

            dc_lines: list[str] = []
            for future in concurrent.futures.as_completed(dc_futures):
                dc_lines.append(future.result())
                if progress_callback is not None:
                    try:
                        progress_callback("\n".join(results + dc_lines))
                    except Exception:
                        pass

            results.extend(dc_lines)
            results.append("")
            results.append("  Определение типа блокировки:")
            results.append(f"  {sni_future.result()}")
            results.append(f"  {http_future.result()}")
            publish()

            wss_results = [future.result() for future in wss_futures]
            results.extend(
                [
                    "",
                    "=" * 76,
                    "  WSS RELAY — ДОСТУПНОСТЬ ЭНДПОИНТОВ (149.154.167.220)",
                    "=" * 76,
                    f"{'DC':<6} {'Endpoint':<32} {'TCP':>6}  {'TLS':>6}  {'WS':>6}  {'Результат'}",
                    "-" * 76,
                ]
            )

            for result in sorted(wss_results, key=lambda item: item["dc"]):
                tcp = f"{result['tcp_ms']:.0f}ms" if result["tcp_ms"] is not None else "—"
                tls = f"{result['tls_ms']:.0f}ms" if result["tls_ms"] is not None else "—"
                ws = f"{result['ws_ms']:.0f}ms" if result["ws_ms"] is not None else "—"
                if result["status"] == "OK":
                    status = "OK (101)"
                elif result["status"] == "WS_REDIRECT":
                    status = f"{result['http_code']} (редирект)"
                elif result["status"] == "TLS_FAIL":
                    status = "TLS FAIL"
                elif result["status"] == "TCP_FAIL":
                    status = "TCP FAIL"
                elif result["status"] == "TIMEOUT":
                    status = "TIMEOUT"
                else:
                    status = result.get("error", result["status"])[:30]
                results.append(
                    f"DC{result['dc']:<4} {result['domain']:<32} {tcp:>6}  {tls:>6}  {ws:>6}  {status}"
                )
            publish()

            proxy_result = proxy_future.result()
            winws2_running = winws_future.result()

            results.extend(
                [
                    "",
                    "=" * 76,
                    f"  ПРОКСИ (127.0.0.1:{proxy_port})",
                    "=" * 76,
                ]
            )
            if proxy_result["status"] == "OK":
                results.append(
                    f"  SOCKS5: OK (tcp {proxy_result['tcp_ms']:.0f}ms, "
                    f"socks {proxy_result['socks_ms']:.0f}ms)"
                )
            elif proxy_result["status"] == "NOT_RUNNING":
                results.append("  SOCKS5: НЕ ЗАПУЩЕН (порт закрыт)")
            else:
                results.append(f"  SOCKS5: {proxy_result['status']} — {proxy_result.get('error', '')}")

            if upstream_future is not None:
                upstream_result = upstream_future.result()
                up_host = upstream_result.get("host", "?")
                up_port = upstream_result.get("port", 0)
                results.extend(
                    [
                        "",
                        "=" * 76,
                        f"  UPSTREAM PROXY ({up_host}:{up_port})",
                        "=" * 76,
                    ]
                )
                if upstream_result["status"] == "OK":
                    results.append(
                        f"  SOCKS5: OK (tcp {upstream_result['tcp_ms']:.0f}ms, "
                        f"handshake {upstream_result['handshake_ms']:.0f}ms)"
                    )
                elif upstream_result["status"] == "NOT_RUNNING":
                    results.append("  SOCKS5: НЕ ЗАПУЩЕН (порт закрыт)")
                elif upstream_result["status"] == "TIMEOUT":
                    results.append("  SOCKS5: TIMEOUT (не удалось подключиться)")
                else:
                    results.append(
                        f"  SOCKS5: {upstream_result['status']} — "
                        f"{upstream_result.get('error', '')}"
                    )

        elapsed = time.time() - t0
        results.extend(
            [
                "",
                "=" * 76,
                "  ИТОГ",
                "=" * 76,
                cls._build_summary(dc_lines, wss_results, proxy_result, winws2_running),
                f"\nВремя тестирования: {elapsed:.1f}s",
            ]
        )
        publish()
        return "\n".join(results)

    @staticmethod
    def _test_wss_relay(ip: str, domain: str, dc: int) -> dict:
        result = {
            "ip": ip,
            "domain": domain,
            "dc": dc,
            "tcp_ms": None,
            "tls_ms": None,
            "ws_ms": None,
            "status": "UNKNOWN",
            "http_code": None,
            "redirect_to": None,
            "error": None,
        }

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(4)
        t0 = time.time()
        try:
            sock.connect((ip, 443))
            result["tcp_ms"] = (time.time() - t0) * 1000
        except Exception as exc:
            sock.close()
            result["status"] = "TCP_FAIL"
            result["error"] = str(exc)
            return result

        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        t1 = time.time()
        try:
            secure_sock = context.wrap_socket(sock, server_hostname=domain)
            result["tls_ms"] = (time.time() - t1) * 1000
        except Exception as exc:
            sock.close()
            result["status"] = "TLS_FAIL"
            result["error"] = str(exc)
            return result

        ws_key = b64encode(urandom(16)).decode()
        request = (
            "GET /apiws HTTP/1.1\r\n"
            f"Host: {domain}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {ws_key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "Sec-WebSocket-Protocol: binary\r\n"
            "Origin: https://web.telegram.org\r\n"
            "\r\n"
        )
        secure_sock.settimeout(5)
        t2 = time.time()
        try:
            secure_sock.sendall(request.encode())
            response = b""
            while b"\r\n\r\n" not in response:
                chunk = secure_sock.recv(512)
                if not chunk:
                    break
                response += chunk
                if len(response) > 4096:
                    break
            result["ws_ms"] = (time.time() - t2) * 1000
            secure_sock.close()

            lines = response.split(b"\r\n")
            status_line = lines[0].decode("utf-8", errors="replace")
            parts = status_line.split(" ", 2)
            http_code = int(parts[1]) if len(parts) >= 2 else 0
            result["http_code"] = http_code

            for line in lines[1:]:
                decoded = line.decode("utf-8", errors="replace")
                if decoded.lower().startswith("location:"):
                    result["redirect_to"] = decoded.split(":", 1)[1].strip()
                    break

            if http_code == 101:
                result["status"] = "OK"
            elif http_code in (301, 302, 303, 307, 308):
                result["status"] = "WS_REDIRECT"
                result["error"] = status_line
            else:
                result["status"] = "WS_FAIL"
                result["error"] = status_line
            return result
        except socket.timeout:
            secure_sock.close()
            result["status"] = "TIMEOUT"
            result["error"] = "WS upgrade timeout"
            return result
        except Exception as exc:
            try:
                secure_sock.close()
            except Exception:
                pass
            result["status"] = "WS_FAIL"
            result["error"] = str(exc)
            return result

    @staticmethod
    def _test_proxy_liveness(host: str, port: int) -> dict:
        result = {"status": "UNKNOWN", "tcp_ms": None, "socks_ms": None, "error": None}
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        t0 = time.time()
        try:
            sock.connect((host, port))
            result["tcp_ms"] = (time.time() - t0) * 1000
        except ConnectionRefusedError:
            sock.close()
            result["status"] = "NOT_RUNNING"
            result["error"] = "порт закрыт (прокси не запущен)"
            return result
        except socket.timeout:
            sock.close()
            result["status"] = "TIMEOUT"
            result["error"] = "TCP timeout"
            return result
        except Exception as exc:
            sock.close()
            result["status"] = "REFUSED"
            result["error"] = str(exc)
            return result

        t1 = time.time()
        try:
            sock.sendall(b"\x05\x01\x00")
            reply = sock.recv(2)
            if len(reply) < 2 or reply[0] != 5 or reply[1] != 0:
                sock.close()
                result["status"] = "SOCKS_ERROR"
                result["error"] = f"unexpected greeting: {reply.hex()}"
                return result

            ip_bytes = bytes([149, 154, 167, 220])
            sock.sendall(b"\x05\x01\x00\x01" + ip_bytes + b"\x01\xbb")
            reply = sock.recv(10)
            result["socks_ms"] = (time.time() - t1) * 1000
            sock.close()

            if len(reply) >= 2 and reply[0] == 5 and reply[1] == 0:
                result["status"] = "OK"
            else:
                code = reply[1] if len(reply) >= 2 else -1
                errors = {
                    1: "general failure",
                    2: "not allowed",
                    3: "network unreachable",
                    4: "host unreachable",
                    5: "connection refused (relay unreachable)",
                }
                result["status"] = "SOCKS_ERROR"
                result["error"] = errors.get(code, f"code={code}")
            return result
        except socket.timeout:
            sock.close()
            result["status"] = "TIMEOUT"
            result["error"] = "SOCKS5 timeout"
            return result
        except Exception as exc:
            sock.close()
            result["status"] = "SOCKS_ERROR"
            result["error"] = str(exc)
            return result

    @staticmethod
    def _test_upstream_proxy(host: str, port: int) -> dict:
        result = {
            "host": host,
            "port": port,
            "status": "NOT_RUNNING",
            "tcp_ms": 0,
            "handshake_ms": 0,
        }
        try:
            t0 = time.monotonic()
            sock = socket.create_connection((host, port), timeout=5.0)
            result["tcp_ms"] = (time.monotonic() - t0) * 1000

            t1 = time.monotonic()
            sock.sendall(b"\x05\x01\x00")
            reply = sock.recv(2)
            if len(reply) == 2 and reply[0] == 5 and reply[1] == 0:
                result["handshake_ms"] = (time.monotonic() - t1) * 1000
                result["status"] = "OK"
            else:
                result["status"] = "SOCKS_ERROR"
                result["error"] = f"Bad reply: {reply.hex()}"
            sock.close()
        except socket.timeout:
            result["status"] = "TIMEOUT"
            result["error"] = "Connection timeout"
        except ConnectionRefusedError:
            result["status"] = "NOT_RUNNING"
            result["error"] = "Connection refused"
        except Exception as exc:
            result["status"] = "ERROR"
            result["error"] = str(exc)
        return result

    @staticmethod
    def _test_single_ip(ip: str, dc: str, wss: str) -> str:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        t0 = time.time()
        try:
            sock.connect((ip, 443))
            tcp_ms = (time.time() - t0) * 1000
        except Exception:
            sock.close()
            return f"{ip:<20} {dc:<12} {'FAIL':>8}  {'—':>8}  TCP не подключается"

        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        t1 = time.time()
        try:
            secure_sock = context.wrap_socket(sock, server_hostname="telegram.org")
            tls_ms = (time.time() - t1) * 1000
            secure_sock.close()
            return f"{ip:<20} {dc:<12} {tcp_ms:>6.0f}ms  {tls_ms:>6.0f}ms  OK"
        except ssl.SSLError as exc:
            tls_ms = (time.time() - t1) * 1000
            sock.close()
            return f"{ip:<20} {dc:<12} {tcp_ms:>6.0f}ms  {tls_ms:>6.0f}ms  BLOCKED ({exc.reason})"
        except socket.timeout:
            sock.close()
            return f"{ip:<20} {dc:<12} {tcp_ms:>6.0f}ms  {'5000':>6}ms  TIMEOUT"
        except Exception as exc:
            sock.close()
            return f"{ip:<20} {dc:<12} {tcp_ms:>6.0f}ms  {'—':>8}  {type(exc).__name__}"

    @staticmethod
    def _test_sni_vs_ip() -> str:
        ip = "149.154.167.50"
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        try:
            sock.connect((ip, 443))
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            t0 = time.time()
            secure_sock = context.wrap_socket(sock, server_hostname="example.com")
            ms = (time.time() - t0) * 1000
            secure_sock.close()
            return f"TLS с чужим SNI (example.com → {ip}): OK ({ms:.0f}ms) → блокировка по SNI"
        except ssl.SSLError:
            sock.close()
            return f"TLS с чужим SNI (example.com → {ip}): BLOCKED → блокировка по IP (не SNI)"
        except socket.timeout:
            sock.close()
            return f"TLS с чужим SNI (example.com → {ip}): TIMEOUT → блокировка по IP (не SNI)"
        except Exception as exc:
            sock.close()
            return f"TLS с чужим SNI: {type(exc).__name__}"

    @staticmethod
    def _test_http_port80() -> str:
        ip = "149.154.167.50"
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        try:
            t0 = time.time()
            sock.connect((ip, 80))
            sock.send(b"GET / HTTP/1.0\r\nHost: test\r\n\r\n")
            sock.settimeout(3)
            data = sock.recv(1024)
            ms = (time.time() - t0) * 1000
            sock.close()
            return f"HTTP {ip}:80 → {len(data)} байт ({ms:.0f}ms) — НЕ блокируется"
        except socket.timeout:
            sock.close()
            return f"HTTP {ip}:80 → TIMEOUT — блокируется"
        except Exception as exc:
            sock.close()
            return f"HTTP {ip}:80 → {type(exc).__name__}"

    @staticmethod
    def _check_winws2_running() -> bool:
        try:
            for exe in ("winws2.exe", "winws.exe"):
                result = subprocess.run(
                    ["tasklist", "/FI", f"IMAGENAME eq {exe}", "/NH"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if exe in result.stdout.lower():
                    return True
            return False
        except Exception:
            return False

    @staticmethod
    def _build_summary(
        dc_lines: list[str],
        wss_results: list[dict],
        proxy_result: dict,
        winws2_running: bool,
    ) -> str:
        def _dc_num(name: str):
            if not name.startswith("DC"):
                return None
            digits = ""
            for char in name[2:]:
                if char.isdigit():
                    digits += char
                else:
                    break
            return int(digits) if digits and len(digits) <= 2 else None

        dc_status: dict[str, str] = {}
        dc_names_ordered = (
            "DC203 CDN",
            "DC5 media",
            "DC5",
            "DC4 media",
            "DC4",
            "DC3 media",
            "DC3 (→DC1)",
            "DC2 media",
            "DC2",
            "DC1 media",
            "DC1",
        )
        for line in dc_lines:
            for dc_name in dc_names_ordered:
                if dc_name in line:
                    if line.strip().endswith("OK"):
                        dc_status.setdefault(dc_name, "OK")
                    elif "BLOCKED" in line or "TIMEOUT" in line or "FAIL" in line:
                        dc_status[dc_name] = "BLOCKED"
                    break

        blocked = sum(1 for value in dc_status.values() if value == "BLOCKED")
        ok_count = sum(1 for value in dc_status.values() if value == "OK")
        wss_ok_dcs = {result["dc"] for result in wss_results if result["status"] == "OK"}
        wss_redirect_dcs = {result["dc"] for result in wss_results if result["status"] == "WS_REDIRECT"}
        relay_ok = bool(wss_ok_dcs)
        proxy_running = proxy_result["status"] == "OK"
        proxy_not_running = proxy_result["status"] == "NOT_RUNNING"

        summary: list[str] = ["── Тип блокировки ──", f"  Доступно: {ok_count}  |  Заблокировано: {blocked}"]
        if blocked == 0 and ok_count > 0:
            summary.append("  Блокировки не обнаружено")
        elif blocked > 0:
            summary.append("  Тип: блокировка TLS к IP Telegram (DPI)")
            summary.append("  (подробности в секции 'Определение типа блокировки' выше)")

        summary.extend(["", "── Статус дата-центров ──"])
        for dc_name in (
            "DC1",
            "DC1 media",
            "DC2",
            "DC2 media",
            "DC3 (→DC1)",
            "DC3 media",
            "DC4",
            "DC4 media",
            "DC5",
            "DC5 media",
            "DC203 CDN",
        ):
            direct = dc_status.get(dc_name, "—")
            dc_num = _dc_num(dc_name)
            if dc_num and dc_num in wss_ok_dcs:
                wss_info = "WSS relay"
            elif dc_num and dc_num in wss_redirect_dcs:
                wss_info = "нет relay"
            elif dc_name == "DC203 CDN":
                wss_info = "TCP (CDN)"
            else:
                wss_info = "—"

            if direct == "OK":
                icon = "+"
            elif direct == "BLOCKED" and dc_num in wss_ok_dcs:
                icon = "~"
            else:
                icon = "x"
            summary.append(f"  [{icon}] {dc_name:<10} напрямую: {direct:<10} прокси: {wss_info}")

        summary.extend(["", "── WSS relay (149.154.167.220) ──"])
        if relay_ok:
            summary.append(f"  Доступен: {', '.join(f'kws{dc}' for dc in sorted(wss_ok_dcs))}")
        else:
            summary.append("  Недоступен")
        if wss_redirect_dcs:
            summary.append(f"  Редирект (нет relay): {', '.join(f'kws{dc}' for dc in sorted(wss_redirect_dcs))}")

        summary.extend(["", "── Сервисы ──"])
        if proxy_running:
            summary.append("  Прокси: запущен")
        elif proxy_not_running:
            summary.append("  Прокси: не запущен")
        else:
            summary.append(f"  Прокси: ошибка ({proxy_result.get('error', '?')})")
        summary.append(f"  winws2: {'запущен' if winws2_running else 'не запущен'}")

        summary.extend(["", "── Рекомендации ──"])
        if blocked == 0 and ok_count > 0:
            summary.append("  Telegram доступен напрямую, прокси не требуется.")
            return "\n".join(summary)

        bypassed_dcs = set()
        for dc_name, status in dc_status.items():
            if status == "BLOCKED":
                num = _dc_num(dc_name)
                if num is not None and num in wss_ok_dcs:
                    bypassed_dcs.add(dc_name)
        blocked_no_wss = {
            dc_name
            for dc_name, status in dc_status.items()
            if status == "BLOCKED" and dc_name not in bypassed_dcs
        }

        if bypassed_dcs and relay_ok:
            names = ", ".join(sorted(bypassed_dcs))
            if proxy_running:
                summary.append(f"  [+] {names}: заблокированы напрямую, обходятся через WSS прокси")
            else:
                summary.append(f"  [~] {names}: WSS relay доступен, но прокси не запущен")

        if blocked_no_wss:
            names = ", ".join(sorted(blocked_no_wss))
            summary.append(
                f"  [!] {names}: заблокированы, WSS relay нет — часть контента (эмодзи, стикеры) может не загружаться"
            )
            if winws2_running:
                summary.append(f"  [~] winws2 запущен — {names} могут работать через zapret")
            else:
                summary.append(f"  [!] Для {names} запустите winws2/zapret на главной странице")

        if proxy_not_running:
            summary.append("  [!] Прокси не запущен — запустите его на этой странице")

        if not relay_ok and blocked > 0:
            summary.append("  [x] WSS relay недоступен — прокси не будет работать")
            if not winws2_running:
                summary.append("  [!] Запустите winws2/zapret или используйте VPN")

        return "\n".join(summary)
