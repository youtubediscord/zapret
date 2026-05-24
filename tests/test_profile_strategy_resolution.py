from __future__ import annotations

from pathlib import Path
import unittest

from core.paths import AppPaths
from profile.match_filters import strategy_catalog_from_match_lines
from profile.parser import parse_preset_text
from profile.service import _basic_strategy_entries, _normalize_lines, _resolve_strategy
from profile.strategy_catalog import load_strategy_catalogs


class ProfileStrategyResolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.paths = AppPaths(user_root=Path("src").resolve(), local_root=Path("src").resolve())
        cls.catalogs = load_strategy_catalogs(cls.paths, "winws2")
        cls.preset = parse_preset_text(
            Path("src/presets/builtin/winws2/Default v5 (game filter).txt").read_text(encoding="utf-8"),
            engine="winws2",
            source_name="Default v5 (game filter).txt",
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

    def test_duplicate_ready_strategy_args_are_still_detected_as_ready_strategy(self) -> None:
        preset = parse_preset_text(
            "\n".join(
                (
                    "--name=googlevideo.com (CDN сервера)",
                    "--filter-tcp=80,443",
                    "--hostlist=lists/googlevideo.txt",
                    "",
                    "--lua-desync=fake:blob=fake_default_tls:tls_mod=rnd,dupsid,sni=www.google.com:repeats=8:tcp_ts=-600000",
                    "--lua-desync=multisplit:pos=2:seqovl=681:seqovl_pattern=tls_google:repeats=8:tcp_ts=-600000",
                    "",
                )
            ),
            engine="winws2",
        )

        self.assertEqual(self._resolved_strategy_id(preset.profiles[0]), "stock_general_fake_tls_auto_alt3_game_filter_38")

    def test_strategy_catalogs_do_not_contain_duplicate_args(self) -> None:
        for engine in ("winws1", "winws2"):
            catalogs = load_strategy_catalogs(self.paths, engine)
            with self.subTest(engine=engine):
                duplicate_groups: list[str] = []
                for catalog_name, entries in catalogs.items():
                    seen: dict[tuple[str, ...], str] = {}
                    for strategy_id, entry in entries.items():
                        identity = _normalize_lines(entry.args.splitlines())
                        previous_id = seen.get(identity)
                        if previous_id is not None:
                            duplicate_groups.append(f"{catalog_name}: {previous_id} = {strategy_id}")
                            continue
                        seen[identity] = strategy_id
                self.assertEqual(duplicate_groups, [])

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
