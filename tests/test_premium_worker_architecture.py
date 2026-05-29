from __future__ import annotations

import inspect
import unittest

from app.feature_facades.premium import PremiumFeature
import donater.commands as premium_commands
import donater.open_bot_worker as open_bot_worker


class PremiumWorkerArchitectureTests(unittest.TestCase):
    def test_open_bot_worker_uses_commands_not_feature_object(self) -> None:
        feature_source = inspect.getsource(PremiumFeature.create_open_extend_bot_worker)
        worker_source = inspect.getsource(open_bot_worker.PremiumOpenBotWorker)

        self.assertNotIn("premium_feature=self", feature_source)
        self.assertNotIn("self._premium", worker_source)
        self.assertIn("premium_commands.open_extend_bot", worker_source)
        self.assertIn("open_extend_bot", inspect.getsource(premium_commands.open_extend_bot))


if __name__ == "__main__":
    unittest.main()
