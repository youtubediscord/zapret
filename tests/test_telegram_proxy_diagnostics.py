from __future__ import annotations

import unittest

from telegram_proxy.diagnostics import _build_summary
from telegram_proxy.ui.page_runtime import build_relay_result_plan


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


if __name__ == "__main__":
    unittest.main()
