from types import SimpleNamespace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


class _PresetFeature:
    def __init__(self, text: str):
        self.text = text
        self.saved_text = ""
        self.saved_args = None

    def get_selected_source_preset_manifest(self, _mode):
        return SimpleNamespace(file_name="Selected.txt")

    def read_preset_source_by_file_name(self, _mode, _file_name):
        return self.text

    def save_preset_source_by_file_name(self, *args):
        self.saved_args = args
        self.saved_text = args[-1]


class StrategyScanApplyTests(unittest.TestCase):
    def test_apply_creates_profile_when_selected_preset_has_no_matching_profile(self) -> None:
        from blockcheck.strategy_scan_apply import apply_strategy
        from profile.parser import parse_preset_text
        from settings.mode import ENGINE_WINWS2

        feature = _PresetFeature(
            "\n".join(
                [
                    "--new",
                    "--name=Discord",
                    "--filter-tcp=443",
                    "--hostlist-domains=discord.com",
                    "--out-range=-d8",
                    "--lua-desync=pass",
                    "",
                ]
            )
        )

        result = apply_strategy(
            presets_feature=feature,
            profile_feature=None,
            strategy_args="--lua-desync=fake:blob=tls_google",
            strategy_name="found strategy",
            scan_target="www.youtube.com",
            scan_protocol="tcp_https",
            scan_udp_games_scope="all",
        )

        self.assertEqual(result.operation, "created")
        self.assertIn("--hostlist-domains=www.youtube.com", feature.saved_text)
        self.assertIn("--lua-desync=fake:blob=tls_google", feature.saved_text)
        self.assertNotIn("--blob=tls_google:", feature.saved_text)
        preset = parse_preset_text(feature.saved_text, engine=ENGINE_WINWS2, source_name="Selected.txt")
        self.assertEqual(len(preset.profiles), 2)
        self.assertIn("www.youtube.com", preset.profiles[0].match_signature)

    def test_apply_updates_existing_matching_profile(self) -> None:
        from blockcheck.strategy_scan_apply import apply_strategy
        from profile.parser import parse_preset_text
        from settings.mode import ENGINE_WINWS2

        feature = _PresetFeature(
            "\n".join(
                [
                    "--new",
                    "--filter-tcp=443",
                    "--hostlist-domains=www.youtube.com",
                    "--out-range=-d8",
                    "--lua-desync=pass",
                    "",
                ]
            )
        )

        result = apply_strategy(
            presets_feature=feature,
            profile_feature=None,
            strategy_args="--lua-desync=fake:blob=tls_google",
            strategy_name="found strategy",
            scan_target="www.youtube.com",
            scan_protocol="tcp_https",
            scan_udp_games_scope="all",
        )

        self.assertEqual(result.operation, "updated")
        preset = parse_preset_text(feature.saved_text, engine=ENGINE_WINWS2, source_name="Selected.txt")
        self.assertEqual(len(preset.profiles), 1)
        self.assertIn("--lua-desync=fake:blob=tls_google", feature.saved_text)
        self.assertNotIn("--lua-desync=pass", feature.saved_text)

    def test_apply_updates_existing_hostlist_profile_for_target_domain(self) -> None:
        from blockcheck import strategy_scan_apply
        from profile.parser import parse_preset_text
        from settings.mode import ENGINE_WINWS2

        with TemporaryDirectory() as temp_dir:
            lists_dir = Path(temp_dir) / "lists"
            lists_dir.mkdir()
            (lists_dir / "youtube.txt").write_text("youtube.com\n", encoding="utf-8")

            feature = _PresetFeature(
                "\n".join(
                    [
                        "--new",
                        "--name=youtube.com (интерфейс)",
                        "--filter-tcp=80,443",
                        "--hostlist=lists/youtube.txt",
                        "--out-range=-d8",
                        "--payload=tls_client_hello",
                        "--lua-desync=hostfakesplit:host=ozon.ru:tcp_ts=-1000:tcp_md5:repeats=4",
                        "",
                    ]
                )
            )

            with patch.object(strategy_scan_apply, "MAIN_DIRECTORY", temp_dir):
                result = strategy_scan_apply.apply_strategy(
                    presets_feature=feature,
                    profile_feature=None,
                    strategy_args="--lua-desync=fake:blob=tls_google",
                    strategy_name="found strategy",
                    scan_target="www.youtube.com",
                    scan_protocol="tcp_https",
                    scan_udp_games_scope="all",
                )

        self.assertEqual(result.operation, "updated")
        preset = parse_preset_text(feature.saved_text, engine=ENGINE_WINWS2, source_name="Selected.txt")
        self.assertEqual(len(preset.profiles), 1)
        self.assertIn("--name=youtube.com (интерфейс)", feature.saved_text)
        self.assertIn("--filter-tcp=80,443", feature.saved_text)
        self.assertIn("--hostlist=lists/youtube.txt", feature.saved_text)
        self.assertIn("--out-range=-d8", feature.saved_text)
        self.assertIn("--payload=tls_client_hello", feature.saved_text)
        self.assertIn("--lua-desync=fake:blob=tls_google", feature.saved_text)
        self.assertNotIn("--hostlist-domains=www.youtube.com", feature.saved_text)
        self.assertNotIn("hostfakesplit:host=ozon.ru", feature.saved_text)


if __name__ == "__main__":
    unittest.main()
