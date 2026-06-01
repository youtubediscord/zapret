from __future__ import annotations

import inspect
import unittest

from app.feature_facades.blockcheck import BlockcheckFeature
import blockcheck.commands as blockcheck_commands
import blockcheck.strategy_scan_worker as strategy_scan_worker
import blockcheck.worker as blockcheck_worker
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

    def test_blockcheck_run_worker_receives_log_actions_as_callables(self) -> None:
        feature_source = inspect.getsource(BlockcheckFeature.create_blockcheck_worker)
        command_factory_source = inspect.getsource(blockcheck_commands.create_blockcheck_worker)
        worker_source = inspect.getsource(blockcheck_worker.BlockcheckWorker)

        self.assertIn("start_run_log=self.start_blockcheck_run_log", feature_source)
        self.assertIn("append_run_log=self.append_blockcheck_run_log", feature_source)
        self.assertIn("start_run_log=start_blockcheck_run_log", command_factory_source)
        self.assertIn("append_run_log=append_blockcheck_run_log", command_factory_source)
        self.assertIn("_start_run_log", worker_source)
        self.assertIn("_append_run_log_action", worker_source)
        self.assertNotIn("blockcheck.commands", worker_source)

    def test_strategy_scan_worker_receives_log_actions_as_callables(self) -> None:
        feature_source = inspect.getsource(BlockcheckFeature.create_strategy_scan_worker)
        command_factory_source = inspect.getsource(blockcheck_commands.create_strategy_scan_worker)
        worker_source = inspect.getsource(strategy_scan_worker.StrategyScanWorker)

        self.assertIn("start_run_log=self.start_strategy_scan_run_log", feature_source)
        self.assertIn("append_run_log=self.append_strategy_scan_run_log", feature_source)
        self.assertIn("start_run_log=start_strategy_scan_run_log", command_factory_source)
        self.assertIn("append_run_log=append_strategy_scan_run_log", command_factory_source)
        self.assertIn("_start_run_log_action", worker_source)
        self.assertIn("_append_run_log_action", worker_source)
        self.assertNotIn("blockcheck.commands", worker_source)

    def test_strategy_scan_worker_exposes_finished_signal_for_shared_runtime(self) -> None:
        worker_source = inspect.getsource(strategy_scan_worker.StrategyScanWorker)

        self.assertTrue(hasattr(strategy_scan_worker.StrategyScanWorker, "finished"))
        self.assertIn("finished = pyqtSignal(object)", worker_source)
        self.assertIn("self.finished.emit(report)", worker_source)
        self.assertIn("self.finished.emit(None)", worker_source)

    def test_blockcheck_run_workers_leave_thread_ownership_to_shared_runtime(self) -> None:
        worker_sources = "\n".join(
            (
                inspect.getsource(blockcheck_worker.BlockcheckWorker),
                inspect.getsource(strategy_scan_worker.StrategyScanWorker),
            )
        )

        self.assertIn("def run(self)", worker_sources)
        self.assertNotIn("threading.Thread", worker_sources)
        self.assertNotIn("_bg_thread", worker_sources)
        self.assertNotIn("def start(self)", worker_sources)

    def test_strategy_scan_worker_receives_runtime_shutdown_callable_not_full_runtime_feature(self) -> None:
        from blockcheck.strategy_scanner import StrategyScanner

        feature_source = inspect.getsource(BlockcheckFeature.create_strategy_scan_worker)
        command_factory_source = inspect.getsource(blockcheck_commands.create_strategy_scan_worker)
        worker_signature = inspect.signature(strategy_scan_worker.StrategyScanWorker.__init__)
        scanner_signature = inspect.signature(StrategyScanner.__init__)
        worker_source = inspect.getsource(strategy_scan_worker.StrategyScanWorker)
        scanner_source = inspect.getsource(StrategyScanner)

        self.assertNotIn("runtime_feature", worker_signature.parameters)
        self.assertNotIn("runtime_feature", scanner_signature.parameters)
        self.assertNotIn("_runtime_feature", worker_source)
        self.assertNotIn("_runtime_feature", scanner_source)
        self.assertIn("shutdown_sync", worker_signature.parameters)
        self.assertIn("shutdown_sync", scanner_signature.parameters)
        self.assertIn("shutdown_sync=shutdown_sync", feature_source)
        self.assertIn("shutdown_sync=shutdown_sync", command_factory_source)


if __name__ == "__main__":
    unittest.main()
