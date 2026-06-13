from __future__ import annotations

import unittest

from profile.normalizer import normalize_preset_profiles
from profile.parser import parse_preset_text


class ProfileNormalizerTests(unittest.TestCase):
    def test_splits_multiple_hostlists_and_drops_excludes_from_split_profiles(self) -> None:
        preset = parse_preset_text(
            "\n".join(
                (
                    "--filter-tcp=80,443",
                    "--hostlist=lists/discord.txt",
                    "--hostlist=lists/other.txt",
                    "--hostlist-exclude=lists/list-exclude.txt",
                    "--payload=tcp",
                    "--out-range=-d10",
                    "--lua-desync=hostfakesplit_multi:hosts=google.com",
                    "",
                )
            ),
            engine="winws2",
        )

        result = normalize_preset_profiles(preset)

        self.assertTrue(result.changed)
        self.assertEqual(result.split_profile_count, 1)
        self.assertEqual(result.created_profile_count, 1)
        self.assertEqual(len(result.preset.profiles), 2)
        self.assertEqual(result.preset.profiles[0].match.hostlist_lines, ["--hostlist=lists/discord.txt"])
        self.assertEqual(result.preset.profiles[1].match.hostlist_lines, ["--hostlist=lists/other.txt"])
        for profile in result.preset.profiles:
            self.assertEqual(profile.match.hostlist_exclude_lines, [])
            self.assertIn("--out-range=-d10", [segment.text for segment in profile.segments])
            self.assertIn("--payload=tcp", [segment.text for segment in profile.segments])
            self.assertIn("--lua-desync=hostfakesplit_multi:hosts=google.com", [segment.text for segment in profile.segments])

    def test_splits_mixed_hostlist_and_ipset_into_separate_profiles(self) -> None:
        preset = parse_preset_text(
            "\n".join(
                (
                    "--filter-tcp=443",
                    "--hostlist=lists/discord.txt",
                    "--ipset=lists/ipset-discord.txt",
                    "--lua-desync=pass",
                    "",
                )
            ),
            engine="winws2",
        )

        result = normalize_preset_profiles(preset)

        self.assertTrue(result.changed)
        self.assertEqual(len(result.preset.profiles), 2)
        self.assertEqual(result.preset.profiles[0].match.hostlist_lines, ["--hostlist=lists/discord.txt"])
        self.assertEqual(result.preset.profiles[1].match.ipset_lines, ["--ipset=lists/ipset-discord.txt"])

    def test_keeps_multi_ipset_profile_when_it_matches_all_profiles_template(self) -> None:
        preset = parse_preset_text(
            "\n".join(
                (
                    "--name=Исключения (RU сайты)",
                    "--filter-tcp=80,443-65535",
                    "--ipset=lists/ipset-ru.txt",
                    "--ipset=lists/ipset-dns.txt",
                    "--ipset=lists/ipset-exclude.txt",
                    "--payload=tls_client_hello",
                    "--out-range=-d8",
                    "--lua-desync=pass",
                    "",
                )
            ),
            engine="winws2",
        )

        result = normalize_preset_profiles(
            preset,
            preserved_match_signatures=(preset.profiles[0].match_signature,),
        )

        self.assertFalse(result.changed)
        self.assertEqual(len(result.preset.profiles), 1)
        self.assertEqual(
            result.preset.profiles[0].match.ipset_lines,
            [
                "--ipset=lists/ipset-ru.txt",
                "--ipset=lists/ipset-dns.txt",
                "--ipset=lists/ipset-exclude.txt",
            ],
        )

    def test_keeps_all_profile_with_only_excludes_unchanged(self) -> None:
        preset = parse_preset_text(
            "\n".join(
                (
                    "--filter-tcp=80,443",
                    "--hostlist-exclude=lists/list-exclude.txt",
                    "--ipset-exclude=lists/ipset-exclude.txt",
                    "--lua-desync=pass",
                    "",
                )
            ),
            engine="winws2",
        )

        result = normalize_preset_profiles(preset)

        self.assertFalse(result.changed)
        self.assertEqual(len(result.preset.profiles), 1)
        self.assertEqual(result.preset.profiles[0].match.hostlist_exclude_lines, ["--hostlist-exclude=lists/list-exclude.txt"])
        self.assertEqual(result.preset.profiles[0].match.ipset_exclude_lines, ["--ipset-exclude=lists/ipset-exclude.txt"])

    def test_splits_winws1_profiles_and_preserves_strategy_lines(self) -> None:
        preset = parse_preset_text(
            "\n".join(
                (
                    "--filter-tcp=80,443",
                    "--hostlist=lists/discord.txt",
                    "--hostlist=lists/other.txt",
                    "--dpi-desync=fake,split2",
                    "--dup=2",
                    "",
                )
            ),
            engine="winws1",
        )

        result = normalize_preset_profiles(preset)

        self.assertTrue(result.changed)
        self.assertEqual(len(result.preset.profiles), 2)
        for profile in result.preset.profiles:
            texts = [segment.text for segment in profile.segments]
            self.assertIn("--dpi-desync=fake,split2", texts)
            self.assertIn("--dup=2", texts)


if __name__ == "__main__":
    unittest.main()
