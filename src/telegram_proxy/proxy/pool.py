from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from telegram_proxy.proxy.dc_map import (
    WSS_DOMAINS,
    WSS_PATH,
    WSS_RELAY_IP,
    WSS_RELAY_IPS,
    ws_domains_for_dc,
)
from telegram_proxy.proxy.cloudflare import build_worker_path
from telegram_proxy.proxy.stats import ProxyStats
from telegram_proxy.proxy.transport import RawWebSocket, WsHandshakeError


log = logging.getLogger("tg_proxy")

WS_POOL_SIZE = 4
WS_POOL_MAX_AGE = 120.0
MAX_CONCURRENT_WSS = 4
_wss_semaphore: Optional[asyncio.Semaphore] = None


def get_wss_semaphore() -> asyncio.Semaphore:
    """Lazy-init semaphore inside the active event loop."""
    global _wss_semaphore
    if _wss_semaphore is None:
        _wss_semaphore = asyncio.Semaphore(MAX_CONCURRENT_WSS)
    return _wss_semaphore


def reset_wss_semaphore() -> None:
    """Reset WSS connection limit for a fresh event loop/session."""
    global _wss_semaphore
    _wss_semaphore = asyncio.Semaphore(MAX_CONCURRENT_WSS)


def relay_ip_for_domain(domain: str) -> str:
    """Get the relay IP for a WSS domain, with fallback."""
    return WSS_RELAY_IPS.get(domain, WSS_RELAY_IP)


def normalize_pool_size(value: object) -> int:
    try:
        number = int(value)
    except Exception:
        return WS_POOL_SIZE
    return max(0, min(32, number))


def _websocket_is_unusable(ws: RawWebSocket) -> bool:
    if getattr(ws, "_closed", False):
        return True
    transport = getattr(getattr(ws, "writer", None), "transport", None)
    is_closing = getattr(transport, "is_closing", None)
    if not callable(is_closing):
        return False
    try:
        return bool(is_closing())
    except Exception:
        return True


class WsPool:
    """Pre-opened WebSocket connection pool."""

    def __init__(self, stats: ProxyStats, pool_size: int = WS_POOL_SIZE, buffer_size: int = 256 * 1024):
        self._idle: dict[tuple[int, bool], list[tuple[RawWebSocket, float]]] = {}
        self._refilling: set[tuple[int, bool]] = set()
        self._stats = stats
        self._pool_size = normalize_pool_size(pool_size)
        self._buffer_size = int(buffer_size)

    async def get(
        self, dc: int, is_media: bool,
        target_ip: str, domains: list[str],
    ) -> Optional[RawWebSocket]:
        """Return a pooled WebSocket or None if pool is empty."""
        if not domains:
            return None
        key = (dc, is_media)
        now = time.monotonic()
        allowed_domains = {str(domain) for domain in domains}

        bucket = self._idle.get(key, [])
        while bucket:
            ws, created = bucket.pop(0)
            age = now - created
            domain = str(getattr(ws, "domain", "") or "")
            if domain and domain not in allowed_domains:
                asyncio.create_task(self._quiet_close(ws))
                continue
            if age > WS_POOL_MAX_AGE or _websocket_is_unusable(ws):
                asyncio.create_task(self._quiet_close(ws))
                continue
            self._stats.pool_hits += 1
            media_tag = "m" if is_media else ""
            log.debug(
                "WS pool hit for DC%d%s (age=%.1fs, left=%d)",
                dc,
                media_tag,
                age,
                len(bucket),
            )
            self._schedule_refill(key, target_ip, domains)
            return ws

        self._stats.pool_misses += 1
        self._schedule_refill(key, target_ip, domains)
        return None

    def _schedule_refill(
        self, key: tuple[int, bool],
        target_ip: str, domains: list[str],
    ) -> None:
        if key in self._refilling:
            return
        self._refilling.add(key)
        asyncio.create_task(self._refill(key, target_ip, domains))

    async def _refill(
        self, key: tuple[int, bool],
        target_ip: str, domains: list[str],
    ) -> None:
        dc, is_media = key
        try:
            bucket = self._idle.setdefault(key, [])
            needed = self._pool_size - len(bucket)
            if needed <= 0:
                return
            tasks = [
                asyncio.create_task(self._connect_one(target_ip, domains, self._buffer_size))
                for _ in range(needed)
            ]
            for task in tasks:
                try:
                    ws = await task
                    if ws is not None:
                        bucket.append((ws, time.monotonic()))
                except Exception:
                    pass
            media_tag = "m" if is_media else ""
            log.debug("WS pool refilled DC%d%s: %d ready", dc, media_tag, len(bucket))
        finally:
            self._refilling.discard(key)

    @staticmethod
    async def _connect_one(
        target_ip: str, domains: list[str], buffer_size: int = 256 * 1024,
    ) -> Optional[RawWebSocket]:
        sem = get_wss_semaphore()
        async with sem:
            for domain in domains:
                relay_ip = relay_ip_for_domain(domain)
                try:
                    ws = await RawWebSocket.connect(
                        relay_ip, domain, WSS_PATH, timeout=8.0, buffer_size=buffer_size,
                    )
                    return ws
                except WsHandshakeError as exc:
                    if exc.is_redirect:
                        continue
                    return None
                except Exception:
                    return None
        return None

    @staticmethod
    async def _quiet_close(ws: RawWebSocket) -> None:
        try:
            await ws.close()
        except Exception:
            pass

    async def warmup(self) -> None:
        for dc, _domain_list in WSS_DOMAINS.items():
            for is_media in (False, True):
                key = (dc, is_media)
                domains = ws_domains_for_dc(dc, is_media)
                self._schedule_refill(key, WSS_RELAY_IP, domains)
        log.info("WS pool warmup started for %d DC(s)", len(WSS_DOMAINS))

    async def close_all(self) -> None:
        for bucket in self._idle.values():
            for ws, _created in bucket:
                asyncio.create_task(self._quiet_close(ws))
        self._idle.clear()


class CloudflareWorkerPool:
    """Pre-opened WebSocket connections to user Cloudflare Worker domains."""

    def __init__(self, stats: ProxyStats, pool_size: int = WS_POOL_SIZE, buffer_size: int = 256 * 1024):
        self._idle: dict[tuple[int, str, str], list[tuple[RawWebSocket, float]]] = {}
        self._refilling: set[tuple[int, str, str]] = set()
        self._stats = stats
        self._pool_size = normalize_pool_size(pool_size)
        self._buffer_size = int(buffer_size)

    async def get(self, dc: int, worker_domain: str, fallback_dst: str) -> Optional[RawWebSocket]:
        key = (int(dc), str(worker_domain), str(fallback_dst))
        now = time.monotonic()

        bucket = self._idle.get(key, [])
        while bucket:
            ws, created = bucket.pop(0)
            age = now - created
            if age > WS_POOL_MAX_AGE or _websocket_is_unusable(ws):
                asyncio.create_task(self._quiet_close(ws))
                continue
            self._stats.cloudflare_worker_pool_hits += 1
            self._schedule_refill(key)
            return ws

        self._stats.cloudflare_worker_pool_misses += 1
        self._schedule_refill(key)
        return None

    def _schedule_refill(self, key: tuple[int, str, str]) -> None:
        if key in self._refilling:
            return
        self._refilling.add(key)
        asyncio.create_task(self._refill(key))

    async def _refill(self, key: tuple[int, str, str]) -> None:
        dc, worker_domain, fallback_dst = key
        try:
            bucket = self._idle.setdefault(key, [])
            needed = self._pool_size - len(bucket)
            if needed <= 0:
                return
            tasks = [
                asyncio.create_task(self._connect_one(dc, worker_domain, fallback_dst, self._buffer_size))
                for _ in range(needed)
            ]
            for task in tasks:
                try:
                    ws = await task
                    if ws is not None:
                        bucket.append((ws, time.monotonic()))
                except Exception:
                    pass
            log.debug(
                "Cloudflare Worker pool refilled DC%d %s: %d ready",
                dc,
                worker_domain,
                len(bucket),
            )
        finally:
            self._refilling.discard(key)

    @staticmethod
    async def _connect_one(
        dc: int, worker_domain: str, fallback_dst: str, buffer_size: int = 256 * 1024
    ) -> Optional[RawWebSocket]:
        path = build_worker_path(fallback_dst, dc)
        sem = get_wss_semaphore()
        async with sem:
            try:
                return await RawWebSocket.connect(
                    worker_domain,
                    worker_domain,
                    path=path,
                    timeout=8.0,
                    buffer_size=buffer_size,
                )
            except Exception:
                return None

    @staticmethod
    async def _quiet_close(ws: RawWebSocket) -> None:
        try:
            await ws.close()
        except Exception:
            pass

    async def warmup(
        self,
        worker_domains: tuple[str, ...],
        fallback_targets: list[tuple[int, str]],
    ) -> None:
        scheduled: set[tuple[int, str, str]] = set()
        for worker_domain in worker_domains:
            worker = str(worker_domain or "").strip()
            if not worker:
                continue
            for dc, fallback_dst in fallback_targets:
                target = str(fallback_dst or "").strip()
                if not target:
                    continue
                key = (int(dc), worker, target)
                if key in scheduled:
                    continue
                scheduled.add(key)
                self._schedule_refill(key)
        if scheduled:
            log.info("Cloudflare Worker pool warmup started for %d target(s)", len(scheduled))

    async def close_all(self) -> None:
        for bucket in self._idle.values():
            for ws, _created in bucket:
                asyncio.create_task(self._quiet_close(ws))
        self._idle.clear()


__all__ = [
    "CloudflareWorkerPool",
    "WsPool",
    "get_wss_semaphore",
    "relay_ip_for_domain",
    "reset_wss_semaphore",
]
