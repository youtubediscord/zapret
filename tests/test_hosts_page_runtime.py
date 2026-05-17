from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))


class HostsPageRuntimeTests(unittest.TestCase):
    def test_page_controller_passes_status_callback_to_hosts_runtime(self) -> None:
        from hosts.page_controller import HostsPageController
        from hosts.ui.page_runtime import create_page_hosts_runtime

        captured = {}

        class HostsFeature:
            def create_hosts_runtime(self, *, status_callback=None):
                captured["status_callback"] = status_callback
                return "runtime"

        controller = HostsPageController(HostsFeature())

        runtime = create_page_hosts_runtime(controller.create_hosts_runtime)

        self.assertEqual(runtime, "runtime")
        self.assertTrue(callable(captured["status_callback"]))


if __name__ == "__main__":
    unittest.main()
