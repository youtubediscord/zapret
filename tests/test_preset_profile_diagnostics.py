from __future__ import annotations

import inspect
import time
import unittest
from unittest.mock import patch

from app.page_names import PageName
from ui.page_host import WindowPageHost


class PresetProfileDiagnosticsTests(unittest.TestCase):
    def test_page_host_switch_metric_does_not_walk_target_widget_tree(self) -> None:
        class _FakePage:
            def findChildren(self, _kind):
                raise AssertionError("navigation must not scan the widget tree")

        class _FakeWindow:
            stackedWidget = object()

            def switchTo(self, page):  # noqa: N802
                _ = page
                time.sleep(0.02)

        host = WindowPageHost(window=_FakeWindow(), page_factory=None)
        page = _FakePage()
        events: list[tuple[str, str]] = []

        with patch(
            "ui.page_host.log_page_timing",
            side_effect=lambda _page, stage, *_args, **kwargs: events.append((stage, str(kwargs.get("extra") or ""))),
        ):
            self.assertTrue(
                host.set_stacked_widget_current_page(
                    page,
                    page_name=PageName.ZAPRET2_USER_PRESETS,
                )
            )

        qfluent_extra = next(extra for stage, extra in events if stage == "open.switch.qfluent")
        self.assertEqual(qfluent_extra, "")

    def test_profile_list_visible_timing_includes_internal_steps(self) -> None:
        from profile import service

        timing_source = inspect.getsource(service.ProfilePresetService._log_timing)

        self.assertIn("log_ui_timing_since", timing_source)
        self.assertIn('"feature"', timing_source)
        self.assertIn('"profile"', timing_source)
        self.assertIn("important=True", timing_source)

    def test_user_presets_metadata_read_is_visible_timing(self) -> None:
        import presets.user_presets_runtime_service as runtime_service

        timing_source = inspect.getsource(runtime_service._log_user_presets_timing)
        worker_source = inspect.getsource(runtime_service.UserPresetsMetadataLoadWorker.run)
        self.assertIn("log_ui_timing_since", timing_source)
        self.assertIn('"feature"', timing_source)
        self.assertIn('"user_presets"', timing_source)
        self.assertIn("_log_user_presets_timing", worker_source)
        self.assertIn("user_presets.metadata.read", worker_source)


if __name__ == "__main__":
    unittest.main()
