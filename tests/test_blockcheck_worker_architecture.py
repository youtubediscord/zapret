from __future__ import annotations

import inspect
import unittest

from app.feature_facades.blockcheck import BlockcheckFeature
import blockcheck.strategy_apply_worker as strategy_apply_worker
import blockcheck.workers as blockcheck_workers


class BlockcheckWorkerArchitectureTests(unittest.TestCase):
    def test_scan_resume_and_finalize_workers_receive_feature_action_callables(self) -> None:
        feature_source = "\n".join(
            (
                inspect.getsource(BlockcheckFeature.create_strategy_scan_resume_save_worker),
                inspect.getsource(BlockcheckFeature.create_strategy_scan_finalize_worker),
            )
        )
        worker_source = "\n".join(
            (
                inspect.getsource(blockcheck_workers.StrategyScanResumeSaveWorker),
                inspect.getsource(blockcheck_workers.StrategyScanFinalizeWorker),
            )
        )

        self.assertNotIn("blockcheck_feature=self", feature_source)
        self.assertNotIn("self._blockcheck", worker_source)
        self.assertIn("save_resume_state=self.save_resume_state", feature_source)
        self.assertIn("finalize_scan_report=self.finalize_scan_report", feature_source)
        self.assertIn("_save_resume_state", worker_source)
        self.assertIn("_finalize_scan_report", worker_source)
        self.assertNotIn("blockcheck_public.", worker_source)
        self.assertNotIn("import blockcheck.public", worker_source)

    def test_strategy_apply_worker_uses_apply_callable_not_feature_object(self) -> None:
        feature_source = inspect.getsource(BlockcheckFeature.create_strategy_apply_worker)
        worker_init_source = inspect.getsource(strategy_apply_worker.StrategyApplyWorker.__init__)
        worker_run_source = inspect.getsource(strategy_apply_worker.StrategyApplyWorker.run)

        self.assertNotIn("blockcheck_feature=self", feature_source)
        self.assertIn("apply_strategy", worker_init_source)
        self.assertIn("self._apply_strategy", worker_init_source)
        self.assertNotIn("self._blockcheck", worker_init_source)
        self.assertIn("self._apply_strategy(", worker_run_source)
        self.assertNotIn("self._blockcheck.apply_strategy", worker_run_source)


if __name__ == "__main__":
    unittest.main()
