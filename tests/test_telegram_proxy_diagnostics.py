from __future__ import annotations

import unittest
from types import SimpleNamespace

from telegram_proxy.diagnostics import _build_summary
from telegram_proxy.proxy.stats import ProxyStats
from telegram_proxy.ui.page_runtime import build_relay_result_plan, build_stats_plan


class TelegramProxyDiagnosticsTests(unittest.TestCase):
    def test_relay_failure_does_not_show_warning_when_proxy_has_traffic(self) -> None:
        plan = build_relay_result_plan(
            host="127.0.0.1",
            port=1353,
            status="fail",
            http_ok=True,
            zapret_running=False,
            traffic_seen=True,
        )

        self.assertFalse(plan.show_warning)
        self.assertIn("трафик идёт", plan.status_text)

    def test_summary_does_not_claim_proxy_dead_when_only_relay_probe_failed(self) -> None:
        summary = _build_summary(
            dc_lines=[
                "149.154.167.50       DC2              FAIL         —  TCP не подключается",
                "149.154.167.91       DC4              FAIL         —  TCP не подключается",
            ],
            wss_results=[
                {"dc": 2, "status": "TLS_FAIL"},
                {"dc": 4, "status": "TLS_FAIL"},
            ],
            proxy_result={"status": "OK"},
            winws2_running=True,
        )

        self.assertNotIn("прокси не будет работать", summary)
        self.assertIn("прямой WSS relay сейчас недоступен", summary)

    def test_stats_plan_shows_proxy_route_and_pool_counters(self) -> None:
        stats = SimpleNamespace(
            active_connections=2,
            total_connections=9,
            bytes_sent=4096,
            bytes_received=8192,
            uptime_seconds=12,
            wss_connections=3,
            tcp_fallback_connections=2,
            cloudflare_connections=4,
            cloudflare_worker_connections=1,
            upstream_connections=1,
            passthrough_connections=2,
            failed_connections=1,
            pool_hits=7,
            pool_misses=2,
            cloudflare_worker_pool_hits=5,
            cloudflare_worker_pool_misses=1,
            recv_zero_count=0,
            recv_zero_per_dc={},
        )

        plan = build_stats_plan(
            stats=stats,
            prev_sent=0,
            prev_recv=0,
            speed_hist_up=(),
            speed_hist_down=(),
            interval=2.0,
        )

        self.assertIn("Пути: WSS 3", plan.stats_text)
        self.assertIn("TCP 2", plan.stats_text)
        self.assertIn("CF 4", plan.stats_text)
        self.assertIn("Worker 1", plan.stats_text)
        self.assertIn("внешний 1", plan.stats_text)
        self.assertIn("мимо 2", plan.stats_text)
        self.assertIn("ошибки 1", plan.stats_text)
        self.assertIn("Пул: WSS 7/2", plan.stats_text)
        self.assertIn("Worker 5/1", plan.stats_text)

    def test_stats_plan_shows_recent_media_route_errors(self) -> None:
        stats = ProxyStats(
            active_connections=1,
            total_connections=2,
            bytes_sent=1024,
            bytes_received=2048,
        )
        stats.record_route_event(
            dc=4,
            is_media=True,
            route="WSS",
            status="ошибка",
            reason="TimeoutError",
        )
        stats.record_route_event(
            dc=4,
            is_media=True,
            route="TCP",
            status="ошибка",
            reason="recv=0 watchdog",
        )

        plan = build_stats_plan(
            stats=stats,
            prev_sent=0,
            prev_recv=0,
            speed_hist_up=(),
            speed_hist_down=(),
            interval=2.0,
        )

        self.assertIn("Последнее:", plan.stats_text)
        self.assertIn("DC4 media WSS ошибка: TimeoutError", plan.stats_text)
        self.assertIn("DC4 media TCP ошибка: recv=0 watchdog", plan.stats_text)


if __name__ == "__main__":
    unittest.main()
