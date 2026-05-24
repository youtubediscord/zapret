import tempfile
import unittest
from pathlib import Path

from log.commands import build_tail_start_plan, build_winws_output_plan


class _FakeDirectRunner:
    def __init__(self, process: object) -> None:
        self._process = process

    def is_running(self) -> bool:
        return True

    def get_process(self) -> object:
        return self._process

    def get_current_strategy_info(self) -> dict:
        return {"name": "Default v5"}


class LogPageRuntimeTests(unittest.TestCase):
    def test_winws_output_plan_uses_runtime_pid_and_direct_runner_process(self) -> None:
        process = object()
        runner = _FakeDirectRunner(process)

        plan = build_winws_output_plan(
            launch_method="zapret2_mode",
            orchestra_runner=None,
            direct_runner=runner,
            process_pid=24680,
            language="ru",
        )

        self.assertEqual(plan.action, "start_worker")
        self.assertEqual(plan.process, process)
        self.assertIn("24680", plan.status_text)
        self.assertIn("Default v5", plan.status_text)

    def test_tail_plan_does_not_reload_unchanged_log_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "zapret_log.txt"
            log_path.write_text("line 1\nline 2\n", encoding="utf-8")

            first_plan = build_tail_start_plan(current_log_file=str(log_path))
            second_plan = build_tail_start_plan(
                current_log_file=str(log_path),
                previous_signature=first_plan.file_signature,
            )

        self.assertTrue(first_plan.should_clear_view)
        self.assertEqual(first_plan.initial_max_bytes, 1024 * 1024)
        self.assertFalse(second_plan.should_clear_view)
        self.assertEqual(second_plan.initial_max_bytes, 0)


if __name__ == "__main__":
    unittest.main()
