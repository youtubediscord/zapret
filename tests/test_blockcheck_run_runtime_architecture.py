import inspect
import unittest

from blockcheck import page_run_workflow
from blockcheck.ui.page import BlockcheckPage
from ui.one_shot_worker_runtime import OneShotWorkerRuntime


class BlockcheckRunRuntimeArchitectureTest(unittest.TestCase):
    def test_blockcheck_run_worker_starts_through_shared_runtime(self) -> None:
        page_source = inspect.getsource(BlockcheckPage)
        start_source = inspect.getsource(BlockcheckPage._on_start)
        cleanup_source = inspect.getsource(BlockcheckPage.cleanup)
        workflow_source = inspect.getsource(page_run_workflow.start_blockcheck_page_run)

        self.assertIn("_run_runtime = OneShotWorkerRuntime()", page_source)
        self.assertIn("run_runtime=self._run_runtime", start_source)
        self.assertIn("_run_runtime.stop", cleanup_source)
        self.assertIn("run_runtime.start_qthread_worker", workflow_source)
        self.assertNotIn("worker.start()", workflow_source)

    def test_shared_runtime_supports_workers_with_is_running_property(self) -> None:
        runtime_source = inspect.getsource(OneShotWorkerRuntime)
        qthread_start_source = inspect.getsource(OneShotWorkerRuntime.start_qthread_worker)
        is_running_source = inspect.getsource(OneShotWorkerRuntime.is_running)
        stop_source = inspect.getsource(OneShotWorkerRuntime.stop)

        self.assertIn("is_running", is_running_source)
        self.assertIn("is_running", stop_source)
        self.assertIn("callable", is_running_source)
        self.assertIn("callable", stop_source)
        self.assertIn("*_args", qthread_start_source)


if __name__ == "__main__":
    unittest.main()
