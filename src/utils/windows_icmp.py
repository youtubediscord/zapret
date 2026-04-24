from __future__ import annotations

import ctypes
import socket
import struct
from dataclasses import dataclass
from ctypes import wintypes


IP_SUCCESS = 0
IP_REQ_TIMED_OUT = 11010


@dataclass(frozen=True, slots=True)
class WindowsPingResult:
    ok: bool
    average_ms: float | None = None
    sent: int = 0
    received: int = 0
    resolved_ip: str | None = None
    error_code: str | None = None
    detail: str = ""


class IP_OPTION_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("Ttl", ctypes.c_ubyte),
        ("Tos", ctypes.c_ubyte),
        ("Flags", ctypes.c_ubyte),
        ("OptionsSize", ctypes.c_ubyte),
        ("OptionsData", ctypes.c_void_p),
    ]


class ICMP_ECHO_REPLY(ctypes.Structure):
    _fields_ = [
        ("Address", wintypes.DWORD),
        ("Status", wintypes.DWORD),
        ("RoundTripTime", wintypes.DWORD),
        ("DataSize", wintypes.WORD),
        ("Reserved", wintypes.WORD),
        ("Data", ctypes.c_void_p),
        ("Options", IP_OPTION_INFORMATION),
    ]


if hasattr(ctypes, "windll"):
    _kernel32 = ctypes.windll.kernel32

    _IcmpCreateFile = None
    _IcmpCloseHandle = None
    _IcmpSendEcho = None

    for _dll_name in ("iphlpapi", "icmp"):
        try:
            _icmp_dll = getattr(ctypes.windll, _dll_name)
            _IcmpCreateFile = _icmp_dll.IcmpCreateFile
            _IcmpCreateFile.argtypes = []
            _IcmpCreateFile.restype = wintypes.HANDLE

            _IcmpCloseHandle = _icmp_dll.IcmpCloseHandle
            _IcmpCloseHandle.argtypes = [wintypes.HANDLE]
            _IcmpCloseHandle.restype = wintypes.BOOL

            _IcmpSendEcho = _icmp_dll.IcmpSendEcho
            _IcmpSendEcho.argtypes = [
                wintypes.HANDLE,
                wintypes.DWORD,
                ctypes.c_void_p,
                wintypes.WORD,
                ctypes.c_void_p,
                ctypes.c_void_p,
                wintypes.DWORD,
                wintypes.DWORD,
            ]
            _IcmpSendEcho.restype = wintypes.DWORD
            break
        except Exception:
            _IcmpCreateFile = None
            _IcmpCloseHandle = None
            _IcmpSendEcho = None

    _GetLastError = _kernel32.GetLastError
    _GetLastError.argtypes = []
    _GetLastError.restype = wintypes.DWORD
else:  # pragma: no cover
    _IcmpCreateFile = None
    _IcmpCloseHandle = None
    _IcmpSendEcho = None
    _GetLastError = None


def _is_windows_icmp_available() -> bool:
    return all(
        fn is not None
        for fn in (_IcmpCreateFile, _IcmpCloseHandle, _IcmpSendEcho, _GetLastError)
    )


def _resolve_ipv4(host: str) -> tuple[str | None, str | None]:
    try:
        return socket.gethostbyname(str(host or "").strip()), None
    except socket.gaierror:
        return None, "DNS_ERR"
    except Exception:
        return None, "RESOLVE_ERR"


def _ipv4_to_dword(ip: str) -> int:
    return int(struct.unpack("!I", socket.inet_aton(ip))[0])


def ping_ipv4_host_winapi(host: str, *, count: int, timeout_ms: int) -> WindowsPingResult:
    """Пингует IPv4-хост через Windows ICMP API без вызова ping.exe."""
    sent = max(0, int(count))

    if not _is_windows_icmp_available():
        return WindowsPingResult(
            ok=False,
            sent=sent,
            received=0,
            error_code="UNSUPPORTED",
            detail="Windows ICMP API unavailable",
        )

    resolved_ip, resolve_error = _resolve_ipv4(host)
    if not resolved_ip:
        return WindowsPingResult(
            ok=False,
            sent=sent,
            received=0,
            error_code=resolve_error or "DNS_ERR",
            detail="DNS resolve failed",
        )

    handle = _IcmpCreateFile()
    invalid_handle = ctypes.c_void_p(-1).value
    if not handle or handle == invalid_handle:
        return WindowsPingResult(
            ok=False,
            sent=sent,
            received=0,
            resolved_ip=resolved_ip,
            error_code="ICMP_OPEN_FAILED",
            detail="IcmpCreateFile failed",
        )

    request_data = b"zapret"
    reply_size = ctypes.sizeof(ICMP_ECHO_REPLY) + len(request_data) + 8
    rtts: list[float] = []
    last_status: int | None = None

    try:
        destination_ip = _ipv4_to_dword(resolved_ip)
        for _attempt in range(sent):
            request_buffer = ctypes.create_string_buffer(request_data)
            reply_buffer = ctypes.create_string_buffer(reply_size)
            result = _IcmpSendEcho(
                handle,
                destination_ip,
                request_buffer,
                len(request_data),
                None,
                reply_buffer,
                reply_size,
                max(1, int(timeout_ms)),
            )
            if result:
                reply = ICMP_ECHO_REPLY.from_buffer(reply_buffer)
                last_status = int(reply.Status)
                if last_status == IP_SUCCESS:
                    rtts.append(float(reply.RoundTripTime))
            else:
                last_status = int(_GetLastError())
    finally:
        _IcmpCloseHandle(handle)

    received = len(rtts)
    if received > 0:
        average_ms = sum(rtts) / received
        return WindowsPingResult(
            ok=True,
            average_ms=average_ms,
            sent=sent,
            received=received,
            resolved_ip=resolved_ip,
            detail=f"{average_ms:.0f}ms",
        )

    if last_status == IP_REQ_TIMED_OUT:
        return WindowsPingResult(
            ok=False,
            sent=sent,
            received=0,
            resolved_ip=resolved_ip,
            error_code="TIMEOUT",
            detail="Timeout",
        )

    return WindowsPingResult(
        ok=False,
        sent=sent,
        received=0,
        resolved_ip=resolved_ip,
        error_code=f"ICMP_{int(last_status or 0)}",
        detail=f"ICMP status {int(last_status or 0)}",
    )
