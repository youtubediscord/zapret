from __future__ import annotations

from pathlib import Path
import unittest

from core.paths import AppPaths
from profile.match_filters import strategy_catalog_from_match_lines
from profile.parser import parse_preset_text
from profile.service import _basic_strategy_entries, _resolve_strategy
from profile.strategy_catalog import load_strategy_catalogs


class ProfileStrategyResolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.paths = AppPaths(user_root=Path("src").resolve(), local_root=Path("src").resolve())
        cls.catalogs = load_strategy_catalogs(cls.paths, "winws2")
        cls.preset = parse_preset_text(
            Path("src/presets/builtin/winws2/Default v5.txt").read_text(encoding="utf-8"),
            engine="winws2",
            source_name="Default v5.txt",
        )

    def test_default_v5_youtube_tcp_strategy_is_detected_by_lua_desync_lines(self) -> None:
        profile = self.preset.profiles[1]

        self.assertIn("--out-range=-d8", profile.strategy.strategy_lines)
        self.assertEqual(self._resolved_strategy_id(profile), "stock_default_v5_11")

    def test_default_v5_udp_strategy_is_detected_when_payload_is_in_catalog(self) -> None:
        profile = self.preset.profiles[2]

        self.assertIn("--out-range=-n8", profile.strategy.strategy_lines)
        self.assertIn("--payload=all", profile.strategy.strategy_lines)
        self.assertEqual(self._resolved_strategy_id(profile), "fake_2_n2")

    def test_default_v5_discord_and_telegram_strategies_are_detected(self) -> None:
        self.assertEqual(self._resolved_strategy_id(self.preset.profiles[3]), "stock_default_v5_12")
        self.assertEqual(self._resolved_strategy_id(self.preset.profiles[8]), "stock_default_v5_13")

    def test_catalog_entry_contains_strategy_visual_description(self) -> None:
        entry = self.catalogs["tcp"]["stock_default_v5_11"]

        self.assertEqual(entry.visual.technique_keys, ("fake", "multidisorder"))
        self.assertEqual(entry.visual.label, "Fake + MultiDisorder")

    def _resolved_strategy_id(self, profile) -> str:
        catalog = strategy_catalog_from_match_lines(tuple(profile.match.all_lines()))
        self.assertIn(catalog, self.catalogs)
        strategy_id, _strategy_name = _resolve_strategy(profile, _basic_strategy_entries(profile, self.catalogs))
        return strategy_id


if __name__ == "__main__":
    unittest.main()
