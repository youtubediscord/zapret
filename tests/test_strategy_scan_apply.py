from types import SimpleNamespace
import unittest


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


if __name__ == "__main__":
    unittest.main()
