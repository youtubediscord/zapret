from __future__ import annotations

import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PyQt6.QtCore import QEvent

from app.page_names import PageName


class UiPerformanceMetricsTests(unittest.TestCase):
    def test_ui_metric_format_is_single_central_format(self) -> None:
        from ui.performance_metrics import UI_PERFORMANCE_LOG_LEVEL, log_ui_timing

        with patch("ui.performance_metrics.log") as logger:
            log_ui_timing(
                "page",
                PageName.ZAPRET2_PRESET_SETUP,
                "open.navigation.first",
                96.6,
                budget_ms=200,
                extra="from=Main,to=PresetSetup",
                important=True,
            )

        logger.assert_called_once()
        message, level = logger.call_args.args
        self.assertEqual(level, UI_PERFORMANCE_LOG_LEVEL)
        self.assertIn("UiMetric:", message)
        self.assertIn("scope=page", message)
        self.assertIn("name=ZAPRET2_PRESET_SETUP", message)
        self.assertIn("stage=open.navigation.first", message)
        self.assertIn("elapsed=97ms", message)
        self.assertIn("budget=200ms", message)
        self.assertIn("detail=from=Main,to=PresetSetup", message)
        self.assertNotIn("PageLifecycle", message)

    def test_page_host_uses_open_navigation_names_not_legacy_show_names(self) -> None:
        from ui.page_host import WindowPageHost

        source = inspect.getsource(WindowPageHost.show_page)
        switch_source = inspect.getsource(WindowPageHost.set_stacked_widget_current_page)

        self.assertIn("open.navigation.first", source)
        self.assertIn("open.navigation.repeat", source)
        self.assertIn("open.switch.set_current", switch_source)
        self.assertNotIn("show.first", source)
        self.assertNotIn("show.repeat", source)
        self.assertNotIn("show.switch", source + switch_source)

    def test_base_page_exposes_content_ready_metric(self) -> None:
        from ui.pages.base_page import BasePage

        page = BasePage.__new__(BasePage)
        page._page_registry_name = PageName.ZAPRET2_PRESET_SETUP
        page._page_open_metric_started_at = 10.0
        page._page_open_metric_first_show = True
        page._resolve_page_budget = Mock(return_value=200)

        with (
            patch("ui.pages.base_page._time.perf_counter", return_value=10.125),
            patch("ui.pages.base_page.log_page_timing") as metric,
        ):
            BasePage.mark_content_ready(page, extra="profiles=83")

        metric.assert_called_once_with(
            PageName.ZAPRET2_PRESET_SETUP,
            "content.ready.first",
            125.0,
            budget_ms=200,
            extra="profiles=83",
            important=True,
            threshold_ms=0,
        )

    def test_base_page_marks_content_ready_after_target_paint_event(self) -> None:
        from ui.pages.base_page import BasePage

        class Target:
            def __init__(self) -> None:
                self.installed = False
                self.removed = False
                self.updated = False

            def installEventFilter(self, _filter):  # noqa: N802
                self.installed = True

            def removeEventFilter(self, _filter):  # noqa: N802
                self.removed = True

            def update(self):
                self.updated = True

        target = Target()
        page = BasePage.__new__(BasePage)
        page._page_registry_name = PageName.ZAPRET2_PRESET_SETUP
        page._page_open_metric_started_at = 20.0
        page._page_open_metric_first_show = True
        page._content_paint_metric_targets = {}
        page._content_paint_metric_next_token = 0
        page._resolve_page_budget = Mock(return_value=200)

        with (
            patch("ui.pages.base_page.QTimer.singleShot") as single_shot,
            patch("ui.pages.base_page._time.perf_counter", return_value=20.333),
            patch("ui.pages.base_page.log_page_timing") as metric,
        ):
            BasePage.mark_content_ready_after_next_paint(
                page,
                target,
                stage="content.profiles_list.painted",
                extra="list=painted",
            )

            self.assertTrue(target.installed)
            self.assertTrue(target.updated)
            single_shot.assert_called_once()

            BasePage.eventFilter(
                page,
                target,
                SimpleNamespace(type=lambda: QEvent.Type.Paint),
            )

        self.assertTrue(target.removed)
        metric.assert_called_once()
        args, kwargs = metric.call_args
        self.assertEqual(args[:2], (PageName.ZAPRET2_PRESET_SETUP, "content.profiles_list.painted.first"))
        self.assertAlmostEqual(args[2], 333.0)
        self.assertEqual(
            kwargs,
            {
                "budget_ms": 200,
                "extra": "list=painted",
                "important": True,
                "threshold_ms": 0,
            },
        )


if __name__ == "__main__":
    unittest.main()
