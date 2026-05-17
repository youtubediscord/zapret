from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest

from core.paths import AppPaths
from profile.parser import parse_preset_text
from profile.service import ProfilePresetService


class _PresetStore:
    def __init__(self, text: str) -> None:
        self.text = text

    def read_selected_preset_source(self, _launch_method: str):
        return self.text, SimpleNamespace(file_name="test.txt", name="test")

    def save_selected_preset_source(self, _launch_method: str, text: str) -> None:
        self.text = text


class ProfileFilterKindSwitchTests(unittest.TestCase):
    def _service(self, text: str) -> tuple[ProfilePresetService, _PresetStore]:
        store = _PresetStore(text)
        feature = SimpleNamespace(
            _presets_feature=store,
            _app_paths=AppPaths(user_root=Path("src").resolve(), local_root=Path("src").resolve()),
        )
        return ProfilePresetService(feature, "zapret2_mode"), store

    def test_switch_hostlist_profile_to_ipset_rewrites_same_profile_line(self) -> None:
        service, store = self._service(
            "\n".join(
                (
                    "--filter-tcp=80,443",
                    "--hostlist=lists/youtube.txt",
                    "--out-range=-d8",
                    "--lua-desync=fake:blob=tls_max:badsum:repeats=8",
                    "--lua-desync=multidisorder:pos=1:seqovl=681:seqovl_pattern=tls_max",
                    "",
                )
            )
        )

        new_key = service.set_profile_filter_kind("profile:0", "ipset")

        self.assertEqual(new_key, "profile:0")
        self.assertIn("--ipset=lists/ipset-youtube.txt", store.text)
        self.assertNotIn("--hostlist=lists/youtube.txt", store.text)
        self.assertIn("--out-range=-d8", store.text)
        self.assertIn("--lua-desync=fake:blob=tls_max:badsum:repeats=8", store.text)
        preset = parse_preset_text(store.text, engine="winws2")
        self.assertEqual(len(preset.profiles), 1)

    def test_switch_ipset_profile_to_hostlist_rewrites_same_profile_line(self) -> None:
        service, store = self._service(
            "\n".join(
                (
                    "--filter-tcp=80,443",
                    "--ipset=lists/ipset-youtube.txt",
                    "--out-range=-d8",
                    "--lua-desync=fake:repeats=6:blob=fake_default_quic",
                    "",
                )
            )
        )

        new_key = service.set_profile_filter_kind("profile:0", "hostlist")

        self.assertEqual(new_key, "profile:0")
        self.assertIn("--hostlist=lists/youtube.txt", store.text)
        self.assertNotIn("--ipset=lists/ipset-youtube.txt", store.text)
        self.assertIn("--out-range=-d8", store.text)
        preset = parse_preset_text(store.text, engine="winws2")
        self.assertEqual(len(preset.profiles), 1)

    def test_hostlist_and_ipset_variants_keep_same_gui_persistent_key(self) -> None:
        hostlist = parse_preset_text(
            "--filter-tcp=80,443\n--hostlist=lists/youtube.txt\n--lua-desync=pass\n",
            engine="winws2",
        ).profiles[0]
        ipset = parse_preset_text(
            "--filter-tcp=80,443\n--ipset=lists/ipset-youtube.txt\n--lua-desync=pass\n",
            engine="winws2",
        ).profiles[0]

        self.assertEqual(hostlist.persistent_key, ipset.persistent_key)

    def test_logical_key_does_not_strip_non_zapret_list_prefixes(self) -> None:
        hostlist = parse_preset_text(
            "--filter-tcp=80,443\n--hostlist=lists/list-youtube.txt\n--lua-desync=pass\n",
            engine="winws2",
        ).profiles[0]
        ipset = parse_preset_text(
            "--filter-tcp=80,443\n--ipset=lists/ipset-youtube.txt\n--lua-desync=pass\n",
            engine="winws2",
        ).profiles[0]

        self.assertNotEqual(hostlist.persistent_key, ipset.persistent_key)


if __name__ == "__main__":
    unittest.main()
