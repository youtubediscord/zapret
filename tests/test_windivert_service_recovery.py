import unittest
from unittest.mock import Mock, patch


class WinDivertServiceRecoveryTests(unittest.TestCase):
    def test_stop_and_delete_waits_until_service_is_really_removed(self) -> None:
        from utils import service_manager

        with (
            patch.object(service_manager, "stop_service", return_value=True),
            patch.object(service_manager, "delete_service", return_value=True),
            patch.object(service_manager, "service_exists", return_value=True) as service_exists,
            patch.object(service_manager.time, "sleep"),
        ):
            removed = service_manager.stop_and_delete_service("Monkey", retry_count=1)

        self.assertFalse(removed)
        service_exists.assert_called_with("Monkey")

    def test_monkey_disabled_service_is_reported_as_windivert_driver_problem(self) -> None:
        from winws_runtime.health import process_health_check

        fake_winreg = Mock()
        fake_winreg.HKEY_LOCAL_MACHINE = object()
        fake_winreg.KEY_READ = 0
        fake_key = Mock()
        fake_key.__enter__ = Mock(return_value=fake_key)
        fake_key.__exit__ = Mock(return_value=False)

        def open_key(_root, path, *_args):
            if path.endswith("\\Monkey"):
                return fake_key
            raise FileNotFoundError(path)

        fake_winreg.OpenKey.side_effect = open_key
        fake_winreg.QueryValueEx.return_value = (4, None)

        with patch.dict("sys.modules", {"winreg": fake_winreg}):
            service_name = process_health_check._find_disabled_windivert_driver_service()

        self.assertEqual(service_name, "Monkey")

    def test_aggressive_cleanup_wait_treats_stopped_monkey_service_as_stale(self) -> None:
        from winws_runtime.runtime import system_ops

        with (
            patch.object(system_ops, "get_all_winws_process_pids", return_value=[]),
            patch.object(
                system_ops,
                "get_known_windivert_service_states_runtime",
                return_value={"Monkey": system_ops._SERVICE_STOPPED},
            ),
            patch.object(system_ops, "stop_and_delete_runtime_services") as stop_and_delete,
            patch.object(system_ops, "unload_known_windivert_drivers_runtime"),
            patch.object(system_ops, "log"),
            patch.object(system_ops.time, "sleep"),
        ):
            settled = system_ops.wait_for_windivert_cleanup_settle_runtime(
                max_wait_seconds=0.01,
                poll_interval=0.001,
                retry_cleanup=True,
            )

        self.assertFalse(settled)
        stop_and_delete.assert_called()


if __name__ == "__main__":
    unittest.main()
