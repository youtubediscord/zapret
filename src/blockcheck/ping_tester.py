"""ICMP ping tester — extracted from blockcheck2.py."""

from blockcheck.config import PING_COUNT, PING_TIMEOUT
from blockcheck.models import SingleTestResult, TestStatus, TestType
from utils.windows_icmp import ping_ipv4_host_winapi


def ping_host(
    host: str,
    count: int = PING_COUNT,
    timeout: int = PING_TIMEOUT,
) -> SingleTestResult:
    """Ping a host via Windows ICMP API."""
    try:
        ping_result = ping_ipv4_host_winapi(
            host,
            count=count,
            timeout_ms=int(timeout * 1000),
        )
        if ping_result.ok and ping_result.average_ms is not None:
            ms = float(ping_result.average_ms)
            return SingleTestResult(
                target_name=host, test_type=TestType.PING,
                status=TestStatus.OK, time_ms=ms,
                detail=f"{ms:.0f}ms",
            )

        error_code = str(ping_result.error_code or "").strip().upper()
        if error_code in {"TIMEOUT", "NO_REPLY"}:
            return SingleTestResult(
                target_name=host, test_type=TestType.PING,
                status=TestStatus.TIMEOUT, error_code=error_code or "TIMEOUT",
                detail="Timeout",
            )

        return SingleTestResult(
            target_name=host, test_type=TestType.PING,
            status=TestStatus.ERROR, error_code=error_code or "ERROR",
            detail=str(ping_result.detail or "Ping failed"),
        )
    except Exception as e:
        return SingleTestResult(
            target_name=host, test_type=TestType.PING,
            status=TestStatus.ERROR, error_code="ERROR",
            detail=str(e),
        )
