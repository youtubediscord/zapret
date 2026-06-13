from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from core.paths import AppPaths
from profile.parser import parse_preset_text
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


class Winws2PayloadStrategyBranchTests(unittest.TestCase):
    def test_payload_scoped_lua_desync_lines_are_separate_strategy_branches(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            catalogs_dir = root / "profile" / "strategy_catalogs" / "winws2"
            catalogs_dir.mkdir(parents=True)
            (catalogs_dir / "tcp.txt").write_text(
                "\n".join(
                    (
                        "[tls_ozon]",
                        "name = TLS Ozon",
                        "--lua-desync=hostfakesplit:host=ozon.ru:tcp_ts=-1000:tcp_md5:repeats=4",
                        "",
                        "[http_ozon]",
                        "name = HTTP Ozon",
                        "--lua-desync=hostfakesplit:host=ozon.ru:tcp_ts=-2000:tcp_md5:repeats=4",
                        "",
                        "[http_vk]",
                        "name = HTTP VK",
                        "--lua-desync=hostfakesplit:host=vk.com:tcp_ts=-3000:tcp_md5:repeats=2",
                        "",
                    )
                ),
                encoding="utf-8",
            )
            store = _PresetStore(
                "\n".join(
                    (
                        "--name=youtube.com (интерфейс)",
                        "--filter-tcp=80,443",
                        "--hostlist=lists/youtube.txt",
                        "--out-range=-d8",
                        "--payload=tls_client_hello",
                        "--lua-desync=hostfakesplit:host=ozon.ru:tcp_ts=-1000:tcp_md5:repeats=4",
                        "--payload=http_req",
                        "--lua-desync=hostfakesplit:host=ozon.ru:tcp_ts=-2000:tcp_md5:repeats=4",
                        "",
                    )
                )
            )
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )
            service = ProfilePresetService(feature, "zapret2_mode")

            setup = service.get_profile_setup("profile:0")
            self.assertIsNotNone(setup)
            self.assertEqual(len(setup.strategy_branches), 2)
            self.assertEqual(
                [(branch.payload, branch.strategy_id) for branch in setup.strategy_branches],
                [("tls_client_hello", "tls_ozon"), ("http_req", "http_ozon")],
            )
            self.assertIn("TLS Ozon", setup.match_tab_text)
            self.assertIn("--payload=tls_client_hello", setup.match_tab_text)
            self.assertIn("HTTP Ozon", setup.strategy_branches[1].match_tab_text)
            self.assertIn("--payload=http_req", setup.strategy_branches[1].match_tab_text)

            result = service.apply_strategy("profile:0", "http_vk", strategy_branch_id="branch:1")

        self.assertEqual(result.status, "applied")
        self.assertEqual(result.profile_key, "profile:0")
        self.assertEqual(store.save_count, 1)
        self.assertIn("--payload=tls_client_hello", store.text)
        self.assertIn("--lua-desync=hostfakesplit:host=ozon.ru:tcp_ts=-1000:tcp_md5:repeats=4", store.text)
        self.assertIn("--payload=http_req", store.text)
        self.assertIn("--lua-desync=hostfakesplit:host=vk.com:tcp_ts=-3000:tcp_md5:repeats=2", store.text)
        self.assertNotIn("tcp_ts=-2000", store.text)

        reparsed = parse_preset_text(store.text, engine="winws2")
        self.assertEqual(len(reparsed.profiles), 1)
        self.assertEqual(
            [(action.payload, action.raw_line) for action in reparsed.profiles[0].strategy.actions],
            [
                (
                    "tls_client_hello",
                    "--lua-desync=hostfakesplit:host=ozon.ru:tcp_ts=-1000:tcp_md5:repeats=4",
                ),
                (
                    "http_req",
                    "--lua-desync=hostfakesplit:host=vk.com:tcp_ts=-3000:tcp_md5:repeats=2",
                ),
            ],
        )


if __name__ == "__main__":
    unittest.main()
