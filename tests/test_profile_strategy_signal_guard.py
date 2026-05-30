from __future__ import annotations

import unittest
from types import SimpleNamespace

from profile.ui.profile_setup_page import ProfileStrategyListWidget


class ProfileStrategySignalGuardTests(unittest.TestCase):
    def test_clicking_current_strategy_does_not_emit_activation_signal(self) -> None:
        emitted: list[str] = []
        widget = SimpleNamespace(
            _current_strategy_id="tls_fake",
            _strategy_id_for_item=lambda _item: "tls_fake",
            strategy_activated=SimpleNamespace(emit=emitted.append),
        )

        ProfileStrategyListWidget._on_item_clicked(widget, object())

        self.assertEqual(emitted, [])


if __name__ == "__main__":
    unittest.main()
