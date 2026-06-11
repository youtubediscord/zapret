from __future__ import annotations

import socket as _socket
import ssl
import time
from dataclasses import dataclass


@dataclass
class UpstreamProxyConfig:
    """Configuration for an external SOCKS5 proxy used as last-resort fallback.

    Modes:
      - "fallback": route through upstream only when WSS+TCP both fail
      - "always":   route all traffic through upstream proxy
    """

    enabled: bool = False
    host: str = ""
    port: int = 0
    mode: str = "always"
    username: str = ""
    password: str = ""
    tls: bool = False
    tls_server_name: str = ""
    tls_verify: bool = False


def check_relay_reachable(
    relay_ip: str = "149.154.167.220",
    timeout: float = 5.0,
) -> dict:
    """Synchronous TCP+TLS check of WSS relay reachability."""
    t0 = time.monotonic()
    try:
        sock = _socket.create_connection((relay_ip, 443), timeout=timeout)
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            tls_sock = ctx.wrap_socket(sock, server_hostname="kws2.web.telegram.org")
            tls_sock.close()
        except Exception:
            sock.close()
            raise
        ms = (time.monotonic() - t0) * 1000
        return {"reachable": True, "error": "", "ms": round(ms, 1)}
    except _socket.timeout:
        ms = (time.monotonic() - t0) * 1000
        return {"reachable": False, "error": f"TCP timeout ({timeout}s)", "ms": round(ms, 1)}
    except ConnectionRefusedError:
        ms = (time.monotonic() - t0) * 1000
        return {"reachable": False, "error": "Connection refused", "ms": round(ms, 1)}
    except OSError as e:
        ms = (time.monotonic() - t0) * 1000
        return {"reachable": False, "error": f"Network error: {e}", "ms": round(ms, 1)}
    except Exception as e:
        ms = (time.monotonic() - t0) * 1000
        return {"reachable": False, "error": str(e), "ms": round(ms, 1)}


def should_route_upstream(upstream: UpstreamProxyConfig, *, mode: str) -> bool:
    """Return True when traffic should go through the external proxy now."""
    return bool(upstream.enabled and upstream.mode == mode)


__all__ = ["UpstreamProxyConfig", "check_relay_reachable", "should_route_upstream"]
