from __future__ import annotations

import socket
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


class TelegramProxyRuntimeController:
    @staticmethod
    def build_page_init_plan(*, runtime_initialized: bool) -> TelegramProxyPageInitPlan:
        return TelegramProxyPageInitPlan(
            ensure_hosts_once=not bool(runtime_initialized),
        )

    @staticmethod
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

    @staticmethod
    def build_toggle_action_plan(*, running: bool, restarting: bool, starting: bool) -> TelegramProxyToggleActionPlan:
        if restarting:
            return TelegramProxyToggleActionPlan(action="cancel_restart", persist_enabled=False)
        if starting:
            return TelegramProxyToggleActionPlan(action="ignore", persist_enabled=None)
        if running:
            return TelegramProxyToggleActionPlan(action="stop", persist_enabled=False)
        return TelegramProxyToggleActionPlan(action="start", persist_enabled=None)

    @staticmethod
    def build_restart_plan(*, running: bool, restarting: bool) -> TelegramProxyRestartPlan:
        return TelegramProxyRestartPlan(
            should_restart=bool(running and not restarting),
            status_text="Перезапуск прокси...",
        )

    @staticmethod
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

    @staticmethod
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

    @staticmethod
    def build_relay_start_plan(*, current_generation: int, host: str, port: int) -> TelegramProxyRelayStartPlan:
        return TelegramProxyRelayStartPlan(
            generation=int(current_generation) + 1,
            status_text=f"Работает на {host}:{port} — проверка relay...",
        )

    @staticmethod
    def check_relay_http(relay_ip: str = "149.154.167.220", timeout: float = 5.0) -> bool:
        try:
            sock = socket.create_connection((relay_ip, 80), timeout=timeout)
            sock.close()
            return True
        except Exception:
            return False

    @staticmethod
    def build_relay_result_plan(
        *,
        host: str,
        port: int,
        status: str,
        ms: float | int = 0,
        http_ok: bool = False,
        zapret_running: bool = False,
    ) -> TelegramProxyRelayResultPlan:
        base = f"Работает на {host}:{port}"

        if status == "ok":
            return TelegramProxyRelayResultPlan(
                status_text=f"{base} — Relay OK ({float(ms):.0f}ms)",
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

    @staticmethod
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

        text = (
            f"Подключения: {getattr(stats, 'active_connections', 0)} акт. / "
            f"{getattr(stats, 'total_connections', 0)} всего  |  "
            f"↑ {_fmt_bytes(now_sent)} ({_fmt_speed(avg_sent, interval)})  "
            f"↓ {_fmt_bytes(now_recv)} ({_fmt_speed(avg_recv, interval)})  |  "
            f"Uptime: {uptime_str}{recv_zero_str}"
        )

        return TelegramProxyStatsPlan(
            stats_text=text,
            next_prev_sent=now_sent,
            next_prev_recv=now_recv,
            next_speed_hist_up=next_up,
            next_speed_hist_down=next_down,
        )
