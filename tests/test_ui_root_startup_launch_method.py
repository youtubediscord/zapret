from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))


class UiRootStartupLaunchMethodTests(unittest.TestCase):
    def test_eager_page_uses_warmed_launch_method_without_window_settings_read(self) -> None:
        from ui import ui_root
        from ui.ui_root import WindowUiRoot

        page_host = SimpleNamespace(
            mark_stack_bootstrap_pending=Mock(),
            create_eager_pages=Mock(),
        )
        session = SimpleNamespace(
            page_host=page_host,
            preset_runtime_coordinator=None,
        )
        runtime_deps = SimpleNamespace(
            ui_state_store=SimpleNamespace(
                snapshot=Mock(return_value=SimpleNamespace(launch_method="zapret1_mode")),
            ),
        )
        window = SimpleNamespace(
            get_launch_method=Mock(side_effect=AssertionError("window settings read must stay out of UI build")),
            log_startup_metric=Mock(),
        )

        with (
            patch.object(ui_root, "initialize_build_ui_state"),
            patch.object(ui_root, "get_window_ui_session", return_value=session),
            patch.object(ui_root, "create_preset_runtime_coordinator", return_value=object()),
            patch.object(ui_root, "get_eager_page_names_for_method", return_value=("zapret1-entry",)) as eager_pages,
            patch.object(ui_root, "init_navigation"),
            patch.object(ui_root, "finalize_page_stack_bootstrap"),
            patch.object(ui_root, "ensure_session_memory_defaults"),
        ):
            WindowUiRoot(window, page_deps_sources=object(), runtime_bootstrap_deps=runtime_deps).build(
                width=100,
                height=100,
                nav_icons={},
                nav_labels={},
                default_nav_icon=object(),
                nav_scroll_position=object(),
                sidebar_search_widget_cls=object,
            )

        eager_pages.assert_called_once_with("zapret1_mode")
        page_host.create_eager_pages.assert_called_once_with(("zapret1-entry",))
        window.get_launch_method.assert_not_called()


if __name__ == "__main__":
    unittest.main()
