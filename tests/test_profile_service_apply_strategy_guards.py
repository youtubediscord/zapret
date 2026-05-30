from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from core.paths import AppPaths
from profile.service import ProfilePresetService


class _PresetStore:
    def __init__(self, text: str) -> None:
        self.text = text
        self.save_count = 0

    def read_selected_preset_source(self, _launch_method: str):
        return self.text, SimpleNamespace(file_name="selected.txt", name="selected")

    def save_selected_preset_source(self, _launch_method: str, text: str) -> None:
        self.save_count += 1
        self.text = text


class ProfileServiceApplyStrategyGuardTests(unittest.TestCase):
    def test_apply_strategy_skips_save_when_profile_already_uses_strategy(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            catalogs_dir = root / "profile" / "strategy_catalogs" / "winws2"
            catalogs_dir.mkdir(parents=True)
            (catalogs_dir / "tcp.txt").write_text(
                "\n".join(
                    (
                        "[tcp_md5]",
                        "name = TCP MD5",
                        "--lua-desync=multidisorder:pos=4:repeats=10:tcp_md5",
                        "",
                    )
                ),
                encoding="utf-8",
            )
            store = _PresetStore(
                "\n".join(
                    (
                        "--name=Speedtest",
                        "--filter-tcp=443,8080",
                        "--hostlist=lists/speedtest.txt",
                        "--lua-desync=multidisorder:pos=4:repeats=10:tcp_md5",
                        "",
                    )
                )
            )
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )

            with patch("settings.store.MAIN_DIRECTORY", str(root)):
                service = ProfilePresetService(feature, "zapret2_mode")
                result = service.apply_strategy("profile:0", "tcp_md5")

        self.assertEqual(result, "profile:0")
        self.assertEqual(store.save_count, 0)


if __name__ == "__main__":
    unittest.main()
