from __future__ import annotations

import unittest
from unittest.mock import patch

from blockcheck.scan_models import StrategyScanReport
import blockcheck.strategy_scan_page_plans as page_plans


class StrategyScanFatalErrorPlanTests(unittest.TestCase):
    def _finalize(self, report: StrategyScanReport):
        with (
            patch.object(page_plans, "save_resume_state"),
            patch.object(page_plans, "clear_resume_state"),
        ):
            return page_plans.finalize_scan_report(
                report,
                scan_target="discord.com",
                scan_protocol="tcp_https",
                scan_udp_games_scope="all",
                scan_mode="quick",
                scan_cursor=3,
                result_rows=[],
            )

    def test_fatal_error_reaches_finish_plan(self) -> None:
        report = StrategyScanReport(
            target="discord.com",
            total_tested=3,
            total_available=10,
            cancelled=True,
            fatal_error="WinDivert не готов: служба WinDivert отключена в системе (код 1058)",
        )

        plan = self._finalize(report)

        self.assertEqual(plan.fatal_error, report.fatal_error)
        self.assertEqual(plan.support_status_code, "ready_after_error")
        self.assertIn("Остановлено из-за ошибки", plan.status_text)

    def test_plain_cancel_keeps_empty_fatal_error(self) -> None:
        report = StrategyScanReport(
            target="discord.com",
            total_tested=3,
            total_available=10,
            cancelled=True,
        )

        plan = self._finalize(report)

        self.assertEqual(plan.fatal_error, "")
        self.assertEqual(plan.support_status_code, "ready")
        self.assertIn("Отменено", plan.status_text)


if __name__ == "__main__":
    unittest.main()
