from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path


PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))


class BlockcheckDomainActionWorkerTests(unittest.TestCase):
    def test_user_domain_actions_run_through_worker(self) -> None:
        import blockcheck.workers as blockcheck_workers
        from blockcheck.ui.page import BlockcheckPage

        self.assertTrue(hasattr(blockcheck_workers, "BlockcheckUserDomainActionWorker"))

        worker_source = inspect.getsource(blockcheck_workers.BlockcheckUserDomainActionWorker.run)
        add_source = inspect.getsource(BlockcheckPage._on_add_domain)
        remove_source = inspect.getsource(BlockcheckPage._on_remove_domain)

        self.assertIn("_run_user_domain_action", worker_source)
        self.assertNotIn("blockcheck_page_runtime.add_user_domain", worker_source)
        self.assertNotIn("blockcheck_page_runtime.remove_user_domain", worker_source)
        self.assertNotIn("blockcheck_commands.run_user_domain_action", worker_source)
        self.assertIn("_request_user_domain_action", add_source)
        self.assertIn("_request_user_domain_action", remove_source)
        self.assertNotIn("blockcheck_page_runtime.add_user_domain", add_source)
        self.assertNotIn("blockcheck_page_runtime.remove_user_domain", remove_source)


if __name__ == "__main__":
    unittest.main()
