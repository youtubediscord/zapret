import inspect
import unittest

from blockcheck.ui.page import BlockcheckPage


class BlockcheckUserDomainRuntimeArchitectureTests(unittest.TestCase):
    def test_user_domain_actions_use_runtime_not_manual_page_worker(self) -> None:
        page_source = inspect.getsource(BlockcheckPage)
        request_source = inspect.getsource(BlockcheckPage._request_user_domain_action)
        start_source = inspect.getsource(BlockcheckPage._start_user_domain_action_worker)
        finished_source = inspect.getsource(BlockcheckPage._on_user_domain_action_finished)
        failed_source = inspect.getsource(BlockcheckPage._on_user_domain_action_failed)
        cleanup_source = inspect.getsource(BlockcheckPage.cleanup)

        self.assertIn("_user_domain_action_runtime = OneShotWorkerRuntime()", page_source)
        self.assertIn("_user_domain_action_runtime.is_running()", request_source)
        self.assertIn("start_qthread_worker", start_source)
        self.assertIn("bind_worker", start_source)
        self.assertIn("_on_user_domain_action_runtime_finished", start_source)
        self.assertIn("_user_domain_action_runtime.is_current", finished_source)
        self.assertIn("_user_domain_action_runtime.is_current", failed_source)
        self.assertIn("_user_domain_action_runtime.stop", cleanup_source)
        self.assertIn("_user_domain_action_runtime.cancel", cleanup_source)
        self.assertNotIn("_user_domain_action_worker =", page_source)
        self.assertNotIn("_user_domain_action_request_id", page_source)
        self.assertNotIn("worker.start()", start_source)


if __name__ == "__main__":
    unittest.main()
