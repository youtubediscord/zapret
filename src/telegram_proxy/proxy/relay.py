from __future__ import annotations

import asyncio
import time
from typing import Callable, Optional

from telegram_proxy.proxy.transport import RawWebSocket
from telegram_proxy.proxy.stats import ProxyStats


# Buffer size for relay (128 KB)
RELAY_BUFFER = 131072


async def relay_wss(
    *,
    client_reader: asyncio.StreamReader,
    client_writer: asyncio.StreamWriter,
    ws: RawWebSocket,
    splitter,
    stats: ProxyStats,
    log_fn: Callable[[str], None],
    label: str,
    dc: int = 0,
) -> tuple[int, int]:
    """Bidirectional relay between TCP client and WebSocket."""
    t0 = time.monotonic()
    sent_total = 0
    recv_total = 0

    async def tcp_to_ws():
        nonlocal sent_total
        try:
            while True:
                data = await client_reader.read(RELAY_BUFFER)
                if not data:
                    break
                sent_total += len(data)
                stats.bytes_sent += len(data)
                if splitter:
                    parts = splitter.split(data)
                    if not parts:
                        continue
                    if len(parts) > 1:
                        await ws.send_batch(parts)
                    else:
                        await ws.send(parts[0])
                else:
                    await ws.send(data)
        except (asyncio.CancelledError, ConnectionError, OSError):
            pass
        except Exception as e:
            log_fn(f"[{label}] tcp->ws error: {type(e).__name__}: {e}")

    async def ws_to_tcp():
        nonlocal recv_total
        try:
            while True:
                data = await ws.recv()
                if data is None:
                    log_fn(f"[{label}] WS closed by server (recv_total={recv_total})")
                    break
                recv_total += len(data)
                stats.bytes_received += len(data)
                client_writer.write(data)
                buf = client_writer.transport.get_write_buffer_size()
                if buf > RELAY_BUFFER:
                    await client_writer.drain()
        except (asyncio.CancelledError, ConnectionError, OSError):
            pass
        except Exception as e:
            log_fn(f"[{label}] ws->tcp error: {type(e).__name__}: {e}")

    tasks = [asyncio.create_task(tcp_to_ws()), asyncio.create_task(ws_to_tcp())]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except BaseException:
                pass
        try:
            await ws.close()
        except BaseException:
            pass
        elapsed = time.monotonic() - t0
        if recv_total == 0 and sent_total > 0:
            stats.recv_zero_count += 1
            if dc > 0:
                stats.recv_zero_per_dc[dc] = stats.recv_zero_per_dc.get(dc, 0) + 1
        log_fn(f"[{label}] relay done: sent={sent_total} recv={recv_total} ({elapsed:.1f}s)")
    return recv_total, sent_total


async def relay_tcp(
    *,
    client_reader: asyncio.StreamReader,
    client_writer: asyncio.StreamWriter,
    remote_reader: asyncio.StreamReader,
    remote_writer: asyncio.StreamWriter,
    stats: ProxyStats,
    log_fn: Callable[[str], None],
    label: str = "",
    dc: int = 0,
    recv_zero_timeout: float = 0,
    on_first_response: Optional[Callable[[], None]] = None,
) -> tuple[int, bool]:
    """Bidirectional TCP relay (fallback or passthrough)."""
    t0 = time.monotonic()
    sent_total = 0
    recv_total = 0
    watchdog_fired = False

    async def forward(src: asyncio.StreamReader, dst: asyncio.StreamWriter, is_upload: bool):
        nonlocal sent_total, recv_total
        try:
            while True:
                data = await src.read(RELAY_BUFFER)
                if not data:
                    break
                dst.write(data)
                await dst.drain()
                if is_upload:
                    sent_total += len(data)
                    stats.bytes_sent += len(data)
                else:
                    first_response = recv_total == 0
                    recv_total += len(data)
                    stats.bytes_received += len(data)
                    if first_response and on_first_response is not None:
                        try:
                            on_first_response()
                        except Exception:
                            pass
        except (asyncio.CancelledError, ConnectionError, OSError):
            pass

    task_c2r = asyncio.create_task(forward(client_reader, remote_writer, True))
    task_r2c = asyncio.create_task(forward(remote_reader, client_writer, False))
    all_tasks = {task_c2r, task_r2c}
    watchdog_task = None

    if recv_zero_timeout > 0:
        async def _recv_watchdog():
            await asyncio.sleep(recv_zero_timeout)
            if recv_total == 0:
                return
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                pass

        watchdog_task = asyncio.create_task(_recv_watchdog())
        all_tasks.add(watchdog_task)

    try:
        done, _pending = await asyncio.wait(all_tasks, return_when=asyncio.FIRST_COMPLETED)
        if watchdog_task is not None and watchdog_task in done:
            watchdog_fired = True
    finally:
        for task in all_tasks:
            task.cancel()
        for task in all_tasks:
            try:
                await task
            except BaseException:
                pass
        try:
            remote_writer.close()
            await remote_writer.wait_closed()
        except Exception:
            pass
        if label:
            elapsed = time.monotonic() - t0
            if recv_total == 0 and sent_total > 0:
                stats.recv_zero_count += 1
                if dc > 0:
                    stats.recv_zero_per_dc[dc] = stats.recv_zero_per_dc.get(dc, 0) + 1
            tag = " [watchdog]" if watchdog_fired else ""
            log_fn(f"[{label}] tcp relay done: sent={sent_total} recv={recv_total} ({elapsed:.1f}s){tag}")
    return recv_total, watchdog_fired


__all__ = ["RELAY_BUFFER", "relay_tcp", "relay_wss"]
