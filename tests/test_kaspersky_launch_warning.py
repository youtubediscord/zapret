import inspect
import unittest
from unittest.mock import patch


class KasperskyLaunchWarningTests(unittest.TestCase):
    def test_startup_checks_do_not_show_kaspersky_just_because_it_is_running(self) -> None:
        from main import post_startup_check_workers

        source = inspect.getsource(post_startup_check_workers.collect_startup_checks_payload)

        self.assertNotIn("startup.kaspersky", source)
        self.assertNotIn("_check_kaspersky_antivirus", source)
        self.assertNotIn("build_kaspersky_notification", source)

    def test_kaspersky_launch_advice_lives_in_separate_module(self) -> None:
        from winws_runtime.health import kaspersky_launch_advice

        self.assertTrue(callable(kaspersky_launch_advice.detect_kaspersky_antivirus))
        self.assertTrue(callable(kaspersky_launch_advice.build_kaspersky_launch_advice))

    def test_windivert_access_denied_adds_kaspersky_advice_after_launch_failure(self) -> None:
        from winws_runtime.health import kaspersky_launch_advice
        from winws_runtime.health.process_health_check import diagnose_winws_exit

        with patch.object(kaspersky_launch_advice, "detect_kaspersky_antivirus", return_value=True):
            diagnosis = diagnose_winws_exit(5, "Error opening filter: Access is denied")

        self.assertIsNotNone(diagnosis)
        assert diagnosis is not None
        self.assertIn("Kaspersky", diagnosis.cause)
        self.assertIn("помешал запуску Zapret", diagnosis.cause)
        self.assertIn("исключения", diagnosis.solution)


if __name__ == "__main__":
    unittest.main()
