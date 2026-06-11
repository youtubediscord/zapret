from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class TelegramProxyToggleActionPlan:
    action: str
    persist_enabled: bool | None


@dataclass(slots=True)
class TelegramProxyStatusPlan:
    status_text: str
    toggle_text: str
    dot_active: bool
    host_edit_enabled: bool
    port_spin_enabled: bool
    clear_stats: bool
    reset_speed_state: bool
    invalidate_relay_check: bool


@dataclass(slots=True)
class TelegramProxyRestartPlan:
    should_restart: bool
    status_text: str


@dataclass(slots=True)
class TelegramProxyStartPlan:
    should_start: bool
    status_text: str
    toggle_enabled: bool
    upstream_log_line: str


@dataclass(slots=True)
class TelegramProxyFinishStartPlan:
    toggle_enabled: bool
    persist_enabled: bool | None
    should_check_relay: bool
    fallback_to_stopped_status: bool


@dataclass(slots=True)
class TelegramProxyRelayStartPlan:
    generation: int
    status_text: str


@dataclass(slots=True)
class TelegramProxyRelayResultPlan:
    status_text: str
    show_warning: bool
    warning_title: str
    warning_content: str


@dataclass(slots=True)
class TelegramProxyStatsPlan:
    stats_text: str
    next_prev_sent: int
    next_prev_recv: int
    next_speed_hist_up: tuple[int, ...]
    next_speed_hist_down: tuple[int, ...]


@dataclass(slots=True)
class TelegramProxyPageInitPlan:
    ensure_hosts_once: bool


def is_zapret_runtime_running(runtime_feature) -> bool:
    return bool(runtime_feature.is_any_running(silent=True))


def build_page_init_plan(*, runtime_initialized: bool) -> TelegramProxyPageInitPlan:
    return TelegramProxyPageInitPlan(
        ensure_hosts_once=not bool(runtime_initialized),
    )

def build_status_plan(*, running: bool, restarting: bool, starting: bool, host: str, port: int) -> TelegramProxyStatusPlan:
    if restarting:
        return TelegramProxyStatusPlan(
            status_text="Перезапуск прокси...",
            toggle_text="Остановить",
            dot_active=False,
            host_edit_enabled=False,
            port_spin_enabled=False,
            clear_stats=False,
            reset_speed_state=False,
            invalidate_relay_check=False,
        )
    if starting:
        return TelegramProxyStatusPlan(
            status_text="Запуск прокси...",
            toggle_text="Запустить",
            dot_active=False,
            host_edit_enabled=False,
            port_spin_enabled=False,
            clear_stats=False,
            reset_speed_state=False,
            invalidate_relay_check=False,
        )
    if running:
        return TelegramProxyStatusPlan(
            status_text=f"Работает на {host}:{port}",
            toggle_text="Остановить",
            dot_active=True,
            host_edit_enabled=False,
            port_spin_enabled=False,
            clear_stats=False,
            reset_speed_state=True,
            invalidate_relay_check=False,
        )
    return TelegramProxyStatusPlan(
        status_text="Остановлен",
        toggle_text="Запустить",
        dot_active=False,
        host_edit_enabled=True,
        port_spin_enabled=True,
        clear_stats=True,
        reset_speed_state=False,
        invalidate_relay_check=True,
    )

def build_toggle_action_plan(*, running: bool, restarting: bool, starting: bool) -> TelegramProxyToggleActionPlan:
    if restarting:
        return TelegramProxyToggleActionPlan(action="cancel_restart", persist_enabled=False)
    if starting:
        return TelegramProxyToggleActionPlan(action="ignore", persist_enabled=None)
    if running:
        return TelegramProxyToggleActionPlan(action="stop", persist_enabled=False)
    return TelegramProxyToggleActionPlan(action="start", persist_enabled=None)

def build_restart_plan(*, running: bool, restarting: bool) -> TelegramProxyRestartPlan:
    return TelegramProxyRestartPlan(
        should_restart=bool(running and not restarting),
        status_text="Перезапуск прокси...",
    )

def build_start_plan(*, starting: bool, running: bool, host: str, port: int, upstream_config) -> TelegramProxyStartPlan:
    if starting or running:
        return TelegramProxyStartPlan(
            should_start=False,
            status_text="",
            toggle_enabled=False,
            upstream_log_line="",
        )

    upstream_log_line = ""
    if upstream_config:
        upstream_log_line = (
            f"Upstream: {upstream_config.host}:{upstream_config.port} "
            f"(mode={upstream_config.mode}, user={upstream_config.username})"
        )

    _ = host, port
    return TelegramProxyStartPlan(
        should_start=True,
        status_text="Запуск прокси...",
        toggle_enabled=False,
        upstream_log_line=upstream_log_line,
    )

def build_finish_start_plan(start_ok: bool) -> TelegramProxyFinishStartPlan:
    if start_ok:
        return TelegramProxyFinishStartPlan(
            toggle_enabled=True,
            persist_enabled=True,
            should_check_relay=True,
            fallback_to_stopped_status=False,
        )
    return TelegramProxyFinishStartPlan(
        toggle_enabled=True,
        persist_enabled=None,
        should_check_relay=False,
        fallback_to_stopped_status=True,
    )

def build_relay_start_plan(*, current_generation: int, host: str, port: int) -> TelegramProxyRelayStartPlan:
    return TelegramProxyRelayStartPlan(
        generation=int(current_generation) + 1,
        status_text=f"Работает на {host}:{port} — проверка relay...",
    )

def build_relay_result_plan(
    *,
    host: str,
    port: int,
    status: str,
    ms: float | int = 0,
    http_ok: bool = False,
    zapret_running: bool = False,
    traffic_seen: bool = False,
) -> TelegramProxyRelayResultPlan:
    base = f"Работает на {host}:{port}"

    if status == "ok":
        return TelegramProxyRelayResultPlan(
            status_text=f"{base} — Relay OK ({float(ms):.0f}ms)",
            show_warning=False,
            warning_title="",
            warning_content="",
        )

    if traffic_seen:
        return TelegramProxyRelayResultPlan(
            status_text=f"{base} — Relay: проверка не прошла, но трафик идёт",
            show_warning=False,
            warning_title="",
            warning_content="",
        )

    if http_ok and zapret_running:
        return TelegramProxyRelayResultPlan(
            status_text=f"{base} — Relay: стратегия Zapret ломает TLS",
            show_warning=True,
            warning_title="Стратегия Zapret ломает Telegram прокси",
            warning_content=(
                "Что происходит: IP relay (149.154.167.220) доступен, "
                "но текущая стратегия Zapret применяет desync к TLS "
                "и ломает подключение прокси.\n"
                "Что делать: смените стратегию Zapret на другую, "
                "или выключите Zapret и перезапустите прокси."
            ),
        )
    if http_ok and not zapret_running:
        return TelegramProxyRelayResultPlan(
            status_text=f"{base} — Relay: TLS не проходит",
            show_warning=True,
            warning_title="TLS к relay не проходит",
            warning_content=(
                "Что происходит: IP relay (149.154.167.220) доступен по HTTP, "
                "но TLS (порт 443) не проходит.\n"
                "Что делать: если Zapret только что выключен — "
                "перезапустите прокси (нажмите Остановить → Запустить).\n"
                "Если после перезапуска проблема осталась — "
                "ваш провайдер блокирует TLS к Telegram. "
                "Настройте 'Внешний прокси' ниже."
            ),
        )
    if zapret_running:
        return TelegramProxyRelayResultPlan(
            status_text=f"{base} — Relay: недоступен, Zapret запущен",
            show_warning=True,
            warning_title="Relay недоступен — возможно мешает Zapret",
            warning_content=(
                "Что происходит: relay (149.154.167.220) не отвечает "
                "ни по HTTP, ни по TLS. Zapret запущен.\n"
                "Что делать: выключите Zapret и перезапустите прокси.\n"
                "Если без Zapret relay тоже недоступен — "
                "ваш провайдер блокирует IP Telegram. "
                "Настройте 'Внешний прокси' ниже."
            ),
        )
    return TelegramProxyRelayResultPlan(
        status_text=f"{base} — Relay: заблокирован провайдером",
        show_warning=True,
        warning_title="Провайдер блокирует Telegram",
        warning_content=(
            "Что происходит: relay (149.154.167.220) полностью недоступен — "
            "ваш провайдер блокирует IP Telegram.\n"
            "Прокси не сможет работать напрямую.\n"
            "Что делать: включите 'Внешний прокси' в настройках ниже "
            "и выберите один из доступных прокси-серверов."
        ),
    )

def build_stats_plan(
    *,
    stats,
    prev_sent: int,
    prev_recv: int,
    speed_hist_up: tuple[int, ...],
    speed_hist_down: tuple[int, ...],
    interval: float = 2.0,
) -> TelegramProxyStatsPlan:
    def _fmt_bytes(n: int) -> str:
        if n < 1024:
            return f"{n} B"
        if n < 1024 * 1024:
            return f"{n / 1024:.1f} KB"
        if n < 1024 * 1024 * 1024:
            return f"{n / (1024 * 1024):.1f} MB"
        return f"{n / (1024 * 1024 * 1024):.2f} GB"

    def _fmt_speed(n: float, secs: float) -> str:
        if secs <= 0:
            return "0 B/s"
        rate = n / secs
        if rate < 1024:
            return f"{rate:.0f} B/s"
        if rate < 1024 * 1024:
            return f"{rate / 1024:.1f} KB/s"
        return f"{rate / (1024 * 1024):.1f} MB/s"

    uptime = getattr(stats, "uptime_seconds", 0)
    mins, secs = divmod(int(uptime), 60)
    hrs, mins = divmod(mins, 60)
    uptime_str = f"{hrs}:{mins:02d}:{secs:02d}" if hrs else f"{mins}:{secs:02d}"

    now_sent = int(getattr(stats, "bytes_sent", 0))
    now_recv = int(getattr(stats, "bytes_received", 0))
    delta_sent = now_sent - int(prev_sent)
    delta_recv = now_recv - int(prev_recv)

    next_up = tuple((list(speed_hist_up) + [delta_sent])[-5:])
    next_down = tuple((list(speed_hist_down) + [delta_recv])[-5:])
    avg_sent = sum(next_up) / max(len(next_up), 1)
    avg_recv = sum(next_down) / max(len(next_down), 1)

    recv_zero_per_dc = getattr(stats, "recv_zero_per_dc", {})
    if recv_zero_per_dc:
        parts = [f"DC{dc}:{cnt}" for dc, cnt in sorted(recv_zero_per_dc.items()) if cnt > 0]
        recv_zero_str = f"  |  recv=0: {' '.join(parts)}" if parts else ""
    else:
        recv_zero = getattr(stats, "recv_zero_count", 0)
        recv_zero_str = f"  |  recv=0: {recv_zero}" if recv_zero > 0 else ""

    route_parts: list[str] = []
    route_counters = (
        ("WSS", "wss_connections"),
        ("TCP", "tcp_fallback_connections"),
        ("CF", "cloudflare_connections"),
        ("Worker", "cloudflare_worker_connections"),
        ("внешний", "upstream_connections"),
        ("мимо", "passthrough_connections"),
        ("ошибки", "failed_connections"),
    )
    for label, attr in route_counters:
        value = int(getattr(stats, attr, 0) or 0)
        if value > 0:
            route_parts.append(f"{label} {value}")
    routes_str = f"  |  Пути: {', '.join(route_parts)}" if route_parts else ""

    pool_parts: list[str] = []
    pool_hits = int(getattr(stats, "pool_hits", 0) or 0)
    pool_misses = int(getattr(stats, "pool_misses", 0) or 0)
    if pool_hits > 0 or pool_misses > 0:
        pool_parts.append(f"WSS {pool_hits}/{pool_misses}")
    worker_pool_hits = int(getattr(stats, "cloudflare_worker_pool_hits", 0) or 0)
    worker_pool_misses = int(getattr(stats, "cloudflare_worker_pool_misses", 0) or 0)
    if worker_pool_hits > 0 or worker_pool_misses > 0:
        pool_parts.append(f"Worker {worker_pool_hits}/{worker_pool_misses}")
    pool_str = f"  |  Пул: {', '.join(pool_parts)}" if pool_parts else ""

    mtproxy_problem_parts: list[str] = []
    mtproxy_invalid_init_count = int(getattr(stats, "mtproxy_invalid_init_count", 0) or 0)
    mtproxy_bad_handshake_count = int(getattr(stats, "mtproxy_bad_handshake_count", 0) or 0)
    if mtproxy_invalid_init_count > 0:
        mtproxy_problem_parts.append(f"не MTProxy {mtproxy_invalid_init_count}")
    if mtproxy_bad_handshake_count > 0:
        mtproxy_problem_parts.append(f"secret {mtproxy_bad_handshake_count}")
    mtproxy_problem_str = ""
    if mtproxy_problem_parts:
        last_problem = str(getattr(stats, "mtproxy_last_problem", "") or "").strip()
        mtproxy_problem_str = (
            f"  |  MTProxy: {', '.join(mtproxy_problem_parts)} — "
            "проверьте тип прокси и secret"
        )
        if last_problem:
            mtproxy_problem_str = f"{mtproxy_problem_str}; последнее: {last_problem}"

    recent_route_parts: list[str] = []
    media_or_cdn_fallback_failed = False
    http_direct_failed = False
    cloudflare_failed = False
    tcp_fallback_failed = False
    upstream_used = int(getattr(stats, "upstream_connections", 0) or 0) > 0
    upstream_ipv6_rejected = False
    for event in list(getattr(stats, "route_events", ()) or ())[-3:]:
        dc = int(getattr(event, "dc", 0) or 0)
        is_media = bool(getattr(event, "is_media", False))
        media = "media" if is_media else "обычный"
        route = str(getattr(event, "route", "") or "?")
        status = str(getattr(event, "status", "") or "?")
        reason = str(getattr(event, "reason", "") or "")
        route_lower = route.lower()
        status_lower = status.lower()
        reason_lower = reason.lower()
        is_error = (
            "ошиб" in status_lower
            or "error" in status_lower
            or "fail" in status_lower
            or "exhaust" in status_lower
        )
        is_upstream = "внеш" in route_lower or "upstream" in route_lower
        if is_upstream and not is_error:
            upstream_used = True
        if is_upstream and is_error and "rep=0x04" in reason_lower:
            upstream_ipv6_rejected = True
        if is_error and route_lower.startswith("http"):
            http_direct_failed = True
        if is_error and "cloudflare" in route_lower:
            cloudflare_failed = True
        if is_error and route_lower in {"tcp", "tcp fallback"}:
            tcp_fallback_failed = True
        if (
            is_error
            and (is_media or dc == 203)
            and (
                "cloudflare" in route_lower
                or route_lower in {"tcp", "tcp fallback"}
            )
        ):
            media_or_cdn_fallback_failed = True
        text = f"DC{dc} {media} {route} {status}"
        if reason:
            text = f"{text}: {reason}"
        recent_route_parts.append(text)
    recent_routes_str = f"  |  Последнее: {'; '.join(recent_route_parts)}" if recent_route_parts else ""
    user_hint_str = ""
    if upstream_ipv6_rejected:
        user_hint_str = (
            "  |  Что происходит: IPv6 Telegram отклонён внешним SOCKS5; "
            "программа пробует IPv4 того же DC"
        )
    elif http_direct_failed and upstream_used:
        user_hint_str = (
            "  |  Что происходит: авто-резерв уже используется; "
            "прямой HTTP/80 Telegram не прошёл, часть трафика пошла через внешний SOCKS5"
        )
    elif media_or_cdn_fallback_failed and upstream_used:
        user_hint_str = (
            "  |  Что происходит: авто-резерв уже используется; "
            "смайлики/медиа ушли через внешний SOCKS5 после ошибки прямого пути"
        )
    elif http_direct_failed:
        user_hint_str = (
            "  |  Что сделать: HTTP/80 Telegram не проходит; "
            "включите внешний SOCKS5. WSS/Worker этот путь не спасают"
        )
    elif media_or_cdn_fallback_failed:
        user_hint_str = (
            "  |  Что сделать: смайлики/медиа упали на запасном пути; "
            "включите внешний SOCKS5 или настройте свой Worker/CF-домен"
        )
    elif cloudflare_failed and tcp_fallback_failed:
        user_hint_str = (
            "  |  Что сделать: встроенный Cloudflare и прямой TCP не проходят; "
            "включите внешний SOCKS5 или настройте свой Worker/CF-домен"
        )

    text = (
        f"Подключения: {getattr(stats, 'active_connections', 0)} акт. / "
        f"{getattr(stats, 'total_connections', 0)} всего  |  "
        f"↑ {_fmt_bytes(now_sent)} ({_fmt_speed(avg_sent, interval)})  "
        f"↓ {_fmt_bytes(now_recv)} ({_fmt_speed(avg_recv, interval)})  |  "
        f"Uptime: {uptime_str}{routes_str}{pool_str}{recv_zero_str}"
        f"{mtproxy_problem_str}{recent_routes_str}{user_hint_str}"
    )

    return TelegramProxyStatsPlan(
        stats_text=text,
        next_prev_sent=now_sent,
        next_prev_recv=now_recv,
        next_speed_hist_up=next_up,
        next_speed_hist_down=next_down,
    )
