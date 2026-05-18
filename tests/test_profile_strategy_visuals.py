from __future__ import annotations

import unittest

from profile.strategy_visuals import describe_strategy_visual


class ProfileStrategyVisualTests(unittest.TestCase):
    def test_detects_multiple_lua_desync_techniques_in_order(self) -> None:
        visual = describe_strategy_visual(
            "--out-range=-d8\n"
            "--lua-desync=fake:blob=tls_max:badsum:repeats=8\n"
            "--lua-desync=multidisorder:pos=1:seqovl=681\n"
        )

        self.assertEqual(visual.technique_keys, ("fake", "multidisorder"))
        self.assertEqual(visual.label, "Fake + MultiDisorder")
        self.assertEqual(visual.icon_name, "ri.magic-line")
        self.assertEqual(visual.color, "#ff6b6b")
        self.assertIn("Fake", visual.description)
        self.assertIn("MultiDisorder", visual.description)

    def test_ignores_non_strategy_options_for_visual_identity(self) -> None:
        left = describe_strategy_visual("--out-range=-d8\n--lua-desync=multisplit:seqovl=652")
        right = describe_strategy_visual("--payload=all\n--in-range=-n8\n--lua-desync=multisplit:seqovl=652")

        self.assertEqual(left.technique_keys, right.technique_keys)
        self.assertEqual(left.label, "MultiSplit")

    def test_unknown_strategy_has_neutral_visual(self) -> None:
        visual = describe_strategy_visual("--payload=all")

        self.assertEqual(visual.technique_keys, ())
        self.assertEqual(visual.label, "Своя")
        self.assertEqual(visual.icon_name, "ri.question-line")

    def test_strategy_icons_use_modern_outline_style(self) -> None:
        samples = [
            "--lua-desync=fake",
            "--lua-desync=multisplit",
            "--lua-desync=multidisorder",
            "--lua-desync=syndata",
            "--lua-desync=udplen",
        ]

        for args in samples:
            with self.subTest(args=args):
                visual = describe_strategy_visual(args)
                self.assertTrue(visual.icon_name.startswith("ri."))


if __name__ == "__main__":
    unittest.main()
