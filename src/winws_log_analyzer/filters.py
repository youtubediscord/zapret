"""Фильтрация списка соединений для таблицы (чистые функции, без Qt)."""

from __future__ import annotations

from .models import VERDICT_DROP, VERDICT_MODIFIED, ConnectionRecord


def filter_connections(
    connections: list[ConnectionRecord],
    *,
    text: str = "",
    only_with_hostname: bool = False,
    only_affected: bool = False,
) -> list[ConnectionRecord]:
    """Отбирает соединения по подстроке (hostname/IP) и флагам.

    only_affected — оставить только соединения, где были modified/drop.
    """
    needle = text.strip().lower()
    filtered = []
    for conn in connections:
        if only_with_hostname and not conn.hostname:
            continue
        if only_affected and not (
            conn.verdict_counts.get(VERDICT_MODIFIED) or conn.verdict_counts.get(VERDICT_DROP)
        ):
            continue
        if needle and needle not in conn.hostname.lower() and needle not in conn.remote_ip.lower():
            continue
        filtered.append(conn)
    return filtered


__all__ = ["filter_connections"]
