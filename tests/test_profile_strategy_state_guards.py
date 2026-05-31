from __future__ import annotations

import copy
import unittest
from unittest.mock import Mock, patch

from profile.strategy_state import ProfileStrategyState, ProfileStrategyStateStore


class ProfileStrategyStateGuardTests(unittest.TestCase):
    def test_clear_strategy_state_skips_write_when_strategy_is_already_absent(self) -> None:
        data = {
            "version": 1,
            "profiles": {
                "name:Speedtest": {
                    "strategies": {
                        "other_strategy": {
                            "favorite": False,
                            "rating": "work",
                            "updated_at": "2026-05-31T00:00:00Z",
                        },
                    },
                },
            },
        }

        with (
            patch(
                "profile.strategy_state.settings_store.get_profile_strategy_state_settings",
                side_effect=lambda: copy.deepcopy(data),
            ),
            patch(
                "profile.strategy_state.settings_store.set_profile_strategy_state_settings",
                Mock(side_effect=AssertionError("absent strategy state must not be written")),
            ),
        ):
            ProfileStrategyStateStore().clear_strategy_state("name:Speedtest", "tls_fake")

    def test_set_strategy_state_skips_write_when_state_is_unchanged(self) -> None:
        data = {
            "version": 1,
            "profiles": {
                "name:Speedtest": {
                    "strategies": {
                        "tls_fake": {
                            "favorite": True,
                            "rating": "work",
                            "updated_at": "2026-05-31T00:00:00Z",
                        },
                    },
                },
            },
        }

        with (
            patch(
                "profile.strategy_state.settings_store.get_profile_strategy_state_settings",
                side_effect=lambda: copy.deepcopy(data),
            ),
            patch(
                "profile.strategy_state.settings_store.set_profile_strategy_state_settings",
                Mock(side_effect=AssertionError("unchanged strategy state must not be written")),
            ),
        ):
            state = ProfileStrategyStateStore().set_strategy_state(
                "name:Speedtest",
                "tls_fake",
                rating="work",
                favorite=True,
            )

        self.assertEqual(state, ProfileStrategyState(rating="work", favorite=True))


if __name__ == "__main__":
    unittest.main()
