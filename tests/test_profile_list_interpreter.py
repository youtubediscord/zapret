from __future__ import annotations

import unittest

from profile.list_interpreter import build_profile_list_sources
from profile.parser import parse_preset_text


class ProfileListInterpreterTests(unittest.TestCase):
    def test_preset_profiles_with_same_match_are_kept_as_separate_rows(self) -> None:
        preset = parse_preset_text(
            """
--name=tr.rbxcdn.com
--filter-tcp=443-65535
--hostlist=lists/tr-rbxcdn-com.txt
--lua-desync=hostfakesplit

--new

--name=tr.rbxcdn.com копия 2
--filter-tcp=443-65535
--hostlist=lists/tr-rbxcdn-com.txt
--lua-desync=hostfakesplit

--new

--name=tr.rbxcdn.com копия
--filter-tcp=443-65535
--hostlist=lists/tr-rbxcdn-com.txt
--lua-desync=hostfakesplit
""",
            engine="winws2",
        )

        sources = build_profile_list_sources(tuple(preset.profiles), {})

        self.assertEqual(
            [source.profile.name for source in sources],
            ["tr.rbxcdn.com", "tr.rbxcdn.com копия 2", "tr.rbxcdn.com копия"],
        )


if __name__ == "__main__":
    unittest.main()
