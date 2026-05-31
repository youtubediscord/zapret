from __future__ import annotations

import importlib.util
import unittest


class LegacyAsyncWorkersArchitectureTests(unittest.TestCase):
    def test_legacy_async_workers_module_is_removed(self) -> None:
        self.assertIsNone(importlib.util.find_spec("async_workers"))


if __name__ == "__main__":
    unittest.main()
