from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))


class PostStartupUpdateContractTests(unittest.TestCase):
    def test_skipped_startup_update_check_clears_checking_status(self) -> None:
        from main import post_startup_update

        class UpdaterFeature:
            def is_auto_update_enabled(self) -> bool:
                return True

            def run_startup_update_check(self) -> dict:
                return {
                    "has_update": False,
                    "version": "1.2.3",
                    "release_notes": "",
                    "error": None,
                    "skipped": True,
                    "skip_reason": "Следующая автоматическая проверка возможна через 5 мин",
                }

        startup_host = SimpleNamespace(
            startup_post_init_ready=object(),
            startup_state=SimpleNamespace(post_init_ready=True),
            is_alive=Mock(return_value=True),
            confirm_update_install=Mock(),
            show_page=Mock(),
            get_loaded_page=Mock(),
        )
        statuses: list[str] = []

        with (
            patch.object(post_startup_update, "bind_startup_gate", side_effect=lambda _signal, callback, **_kwargs: callback()),
            patch.object(post_startup_update, "schedule_after", side_effect=lambda _delay_ms, callback: callback()),
            patch.object(post_startup_update, "enqueue_subsystem_task", side_effect=lambda _queue, _name, target: target()),
            patch.object(post_startup_update, "log"),
        ):
            post_startup_update.install_update_check(
                startup_host,
                updater_feature=UpdaterFeature(),
                notify=Mock(),
                set_status=statuses.append,
            )

        self.assertEqual(statuses[0], "Проверка обновлений...")
        self.assertNotEqual(statuses[-1], "Проверка обновлений...")
        self.assertIn("Следующая автоматическая проверка", statuses[-1])


if __name__ == "__main__":
    unittest.main()
