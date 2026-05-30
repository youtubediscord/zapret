from __future__ import annotations

import inspect
import unittest

from app.feature_facades.premium import PremiumFeature
import donater.commands as premium_commands
import donater.open_bot_worker as open_bot_worker
import donater.subscription_manager as subscription_manager
import donater.subscription_worker as subscription_worker


class PremiumWorkerArchitectureTests(unittest.TestCase):
    def test_open_bot_worker_receives_feature_action_not_feature_object(self) -> None:
        feature_source = inspect.getsource(PremiumFeature.create_open_extend_bot_worker)
        worker_source = inspect.getsource(open_bot_worker.PremiumOpenBotWorker)

        self.assertNotIn("premium_feature=self", feature_source)
        self.assertNotIn("self._premium", worker_source)
        self.assertIn("open_extend_bot=self.open_extend_bot", feature_source)
        self.assertIn("_open_extend_bot", worker_source)
        self.assertNotIn("premium_commands.open_extend_bot", worker_source)
        self.assertNotIn("import donater.commands", worker_source)
        self.assertIn("open_extend_bot", inspect.getsource(premium_commands.open_extend_bot))

    def test_subscription_worker_receives_command_actions_from_manager(self) -> None:
        command_source = inspect.getsource(premium_commands.create_subscription_manager)
        manager_init_source = inspect.getsource(subscription_manager.SubscriptionManager.__init__)
        manager_start_source = inspect.getsource(subscription_manager.SubscriptionManager.initialize_async)
        worker_source = inspect.getsource(subscription_worker.SubscriptionInitWorker)

        self.assertIn("get_premium_checker=get_premium_checker", command_source)
        self.assertIn("check_device_activation=check_device_activation", command_source)
        self.assertIn("_get_premium_checker", manager_init_source)
        self.assertIn("_check_device_activation", manager_init_source)
        self.assertIn("get_premium_checker=self._get_premium_checker", manager_start_source)
        self.assertIn("check_device_activation=self._check_device_activation", manager_start_source)
        self.assertIn("_get_premium_checker", worker_source)
        self.assertIn("_check_device_activation", worker_source)
        self.assertNotIn("import donater.commands", worker_source)


if __name__ == "__main__":
    unittest.main()
