from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest


PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))


class Winws2LaunchPresetValidationTests(unittest.TestCase):
    def test_launch_preparation_keeps_valid_preset_text_unchanged(self) -> None:
        from winws_runtime.preset_launch_text import prepare_winws2_preset_text_for_launch

        source = "\n".join(
            (
                "--wf-tcp-out=443",
                "--filter-tcp=443",
                "--hostlist=lists/youtube.txt",
                "--payload=tls_client_hello",
                "--lua-desync=fake:blob=tls_google",
                "",
            )
        )

        prepared = prepare_winws2_preset_text_for_launch(source, source_name="valid.txt")

        self.assertEqual(prepared.text, source)
        self.assertFalse(prepared.changed)
        self.assertNotIn("--out-range=-d8", prepared.text)

    def test_launch_filter_check_ignores_only_skipped_profiles(self) -> None:
        from presets.mode_coordinator import PresetModeCoordinator
        from settings.mode import ZAPRET2_MODE

        source = "\n".join(
            (
                "--wf-tcp-out=443",
                "--skip",
                "--filter-tcp=443",
                "--hostlist=lists/youtube.txt",
                "--lua-desync=fake:blob=tls_google",
                "",
            )
        )

        self.assertFalse(PresetModeCoordinator._has_required_filters(ZAPRET2_MODE, source))

    def test_launch_filter_check_allows_some_skipped_profiles_when_one_is_enabled(self) -> None:
        from presets.mode_coordinator import PresetModeCoordinator
        from settings.mode import ZAPRET2_MODE

        source = "\n".join(
            (
                "--wf-tcp-out=443",
                "--skip",
                "--filter-tcp=443",
                "--hostlist=lists/disabled.txt",
                "--lua-desync=fake:blob=tls_google",
                "",
                "--new",
                "--filter-tcp=443",
                "--hostlist=lists/enabled.txt",
                "--lua-desync=multisplit:pos=sniext+1",
                "",
            )
        )

        self.assertTrue(PresetModeCoordinator._has_required_filters(ZAPRET2_MODE, source))

    def test_winws1_launch_filter_check_ignores_only_skipped_profiles(self) -> None:
        from presets.mode_coordinator import PresetModeCoordinator
        from settings.mode import ZAPRET1_MODE

        source = "\n".join(
            (
                "--wf-tcp=80,443",
                "--skip",
                "--filter-tcp=443",
                "--hostlist=lists/youtube.txt",
                "--dpi-desync=fake,split2",
                "",
            )
        )

        self.assertFalse(PresetModeCoordinator._has_required_filters(ZAPRET1_MODE, source))

    def test_winws1_launch_filter_check_allows_some_skipped_profiles_when_one_is_enabled(self) -> None:
        from presets.mode_coordinator import PresetModeCoordinator
        from settings.mode import ZAPRET1_MODE

        source = "\n".join(
            (
                "--wf-tcp=80,443",
                "--skip",
                "--filter-tcp=443",
                "--hostlist=lists/disabled.txt",
                "--dpi-desync=fake",
                "",
                "--new",
                "--filter-tcp=443",
                "--hostlist=lists/enabled.txt",
                "--dpi-desync=fake,split2",
                "",
            )
        )

        self.assertTrue(PresetModeCoordinator._has_required_filters(ZAPRET1_MODE, source))

    def test_start_validation_rejects_preset_with_only_skipped_profiles(self) -> None:
        from winws_runtime.flow.start_preparation import validate_preset_selected_mode
        from settings.mode import ZAPRET2_MODE

        with tempfile.TemporaryDirectory() as tmp:
            preset_path = Path(tmp) / "only-skipped.txt"
            preset_path.write_text(
                "\n".join(
                    (
                        "--wf-tcp-out=443",
                        "--skip",
                        "--filter-tcp=443",
                        "--hostlist=lists/youtube.txt",
                        "--lua-desync=fake:blob=tls_google",
                        "",
                    )
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(RuntimeError, "включ"):
                validate_preset_selected_mode(
                    {"is_preset_file": True, "preset_path": str(preset_path)},
                    ZAPRET2_MODE,
                )

    def test_launch_preparation_allows_unknown_filename_when_syntax_is_valid(self) -> None:
        from winws_runtime.preset_launch_text import prepare_winws2_preset_text_for_launch

        source = "\n".join(
            (
                "--wf-tcp-out=443",
                "--filter-tcp=443",
                "--hostlist=unknown.txt",
                "--lua-desync=fake:blob=tls_google",
                "",
            )
        )

        prepared = prepare_winws2_preset_text_for_launch(source, source_name="placeholder.txt")

        self.assertEqual(prepared.text, source)

    def test_source_save_normalization_adds_required_lua_init_lines(self) -> None:
        from presets.preset_text_ops import normalize_preset_source_text_for_engine
        from settings.mode import ENGINE_WINWS2

        source = "\n".join(
            (
                "# Preset: Example",
                "--wf-tcp-out=443",
                "--filter-tcp=443",
                "--hostlist=lists/youtube.txt",
                "--lua-desync=hostfakesplit_multi:hosts=google.com",
                "",
            )
        )

        normalized = normalize_preset_source_text_for_engine(source, ENGINE_WINWS2)

        self.assertIn("--lua-init=@lua/zapret-lib.lua", normalized)
        self.assertIn("--lua-init=@lua/zapret-antidpi.lua", normalized)
        self.assertIn("--lua-init=@lua/zapret-auto.lua", normalized)
        self.assertIn("--lua-init=@lua/custom_funcs.lua", normalized)
        self.assertIn("--lua-init=@lua/custom_diag.lua", normalized)
        self.assertIn("--lua-init=@lua/zapret-multishake.lua", normalized)

    def test_launch_preparation_rejects_strategy_tags_in_non_circular_preset(self) -> None:
        from winws_runtime.preset_launch_text import prepare_winws2_preset_text_for_launch

        source = "\n".join(
            (
                "--wf-tcp-out=443",
                "--filter-tcp=443",
                "--hostlist=lists/youtube.txt",
                "--lua-desync=fake:blob=tls_google:strategy=1",
                "",
            )
        )

        with self.assertRaisesRegex(ValueError, "strategy"):
            prepare_winws2_preset_text_for_launch(source, source_name="not-circular.txt")

    def test_circular_detection_uses_official_lua_desync_line_not_name(self) -> None:
        from winws_runtime.preset_launch_text import is_winws2_circular_preset_text

        self.assertTrue(
            is_winws2_circular_preset_text(
                "\n".join(
                    (
                        "# Preset: anything",
                        "--in-range=-s5556 --lua-desync=circular:fails=4:retrans=2:maxseq=16384",
                        "--lua-desync=fake:strategy=1",
                        "",
                    )
                )
            )
        )
        self.assertFalse(
            is_winws2_circular_preset_text(
                "\n".join(
                    (
                        "# Preset: Default (circular)",
                        "--wf-tcp-out=443",
                        "--lua-desync=fake:blob=tls_google:strategy=1",
                        "",
                    )
                )
            )
        )
        self.assertFalse(
            is_winws2_circular_preset_text(
                "\n".join(
                    (
                        "--wf-tcp-out=443",
                        "--lua-desync=circular_quality:fails=4",
                        "--lua-desync=fake:strategy=1",
                        "",
                    )
                )
            )
        )

    def test_launch_preparation_allows_strategy_tags_in_circular_preset(self) -> None:
        from winws_runtime.preset_launch_text import prepare_winws2_preset_text_for_launch

        source = "\n".join(
            (
                "--wf-tcp-out=443",
                "--lua-desync=circular",
                "--lua-desync=fake:blob=tls_google:strategy=1",
                "",
            )
        )

        prepared = prepare_winws2_preset_text_for_launch(
            source,
            source_name="circular.txt",
            source_is_circular=True,
        )

        self.assertEqual(prepared.text, source)

    def test_launch_preparation_ignores_strategy_tags_in_comments(self) -> None:
        from winws_runtime.preset_launch_text import prepare_winws2_preset_text_for_launch

        source = "\n".join(
            (
                "# example: --lua-desync=fake:strategy=1",
                "--wf-tcp-out=443",
                "--filter-tcp=443",
                "--hostlist=lists/youtube.txt",
                "--lua-desync=fake:blob=tls_google",
                "",
            )
        )

        prepared = prepare_winws2_preset_text_for_launch(source, source_name="comment.txt")

        self.assertEqual(prepared.text, source)

    def test_runner_checks_unknown_filename_by_file_existence(self) -> None:
        from winws_runtime.runners.zapret2_runner import Winws2StrategyRunner

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lists_dir = root / "lists"
            lists_dir.mkdir()
            runner = object.__new__(Winws2StrategyRunner)
            runner.work_dir = str(root)
            runner.lists_dir = str(lists_dir)
            runner.bin_dir = str(root / "bin")

            source = "\n".join(
                (
                    "--wf-tcp-out=443",
                    "--filter-tcp=443",
                    "--hostlist=unknown.txt",
                    "--lua-desync=fake:blob=tls_google",
                    "",
                )
            )

            missing = runner._collect_missing_preset_references_from_text(source)
            self.assertEqual(len(missing), 1)
            self.assertIn("--hostlist=unknown.txt", missing[0][0])

            (lists_dir / "unknown.txt").write_text("example.com\n", encoding="utf-8")

            self.assertEqual(len(runner._collect_missing_preset_references_from_text(source)), 1)

            (root / "unknown.txt").write_text("example.com\n", encoding="utf-8")

            self.assertEqual(runner._collect_missing_preset_references_from_text(source), [])

    def test_winws2_validation_treats_bare_list_file_as_workdir_relative(self) -> None:
        from winws_runtime.runners.zapret2_runner import Winws2StrategyRunner

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lists_dir = root / "lists"
            lists_dir.mkdir()
            (lists_dir / "tankix.txt").write_text("example.com\n", encoding="utf-8")
            runner = object.__new__(Winws2StrategyRunner)
            runner.work_dir = str(root)
            runner.lists_dir = str(lists_dir)
            runner.bin_dir = str(root / "bin")

            source = "\n".join(
                (
                    "--wf-tcp-out=443",
                    "--filter-tcp=443",
                    "--hostlist=tankix.txt",
                    "--lua-desync=fake:blob=tls_google",
                    "",
                )
            )

            missing = runner._collect_missing_preset_references_from_text(source)

            self.assertEqual(len(missing), 1)
            self.assertIn(str(root / "tankix.txt"), missing[0][1])

    def test_winws2_compile_accepts_explicit_lists_paths_for_at_launch(self) -> None:
        from threading import RLock

        from winws_runtime.runners.zapret2_runner import Winws2StrategyRunner

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lists_dir = root / "lists"
            lists_dir.mkdir()
            (lists_dir / "tankix.txt").write_text("example.com\n", encoding="utf-8")
            (lists_dir / "ipset-tankix.txt").write_text("1.2.3.4\n", encoding="utf-8")
            preset_path = root / "selected.txt"
            preset_path.write_text(
                "\n".join(
                    (
                        "--wf-tcp-out=443",
                        "--filter-tcp=443",
                        "--hostlist=lists/tankix.txt",
                        "--ipset=lists/ipset-tankix.txt",
                        "--lua-desync=fake:blob=tls_google",
                        "",
                    )
                ),
                encoding="utf-8",
            )

            runner = object.__new__(Winws2StrategyRunner)
            runner._state_lock = RLock()
            runner._prepared_preset_cache = {}
            runner.work_dir = str(root)
            runner.lists_dir = str(lists_dir)
            runner.bin_dir = str(root / "bin")

            artifact = runner._compile_preset_artifact(str(preset_path))

            self.assertTrue(artifact.validation_ok, artifact.validation_report)
            self.assertEqual(len(artifact.launch_args), 1)
            self.assertTrue(artifact.launch_args[0].startswith("@"))
            at_config_path = Path(artifact.launch_args[0][1:])
            self.assertTrue(at_config_path.exists())
            self.assertEqual(at_config_path.parent, root / "tmp" / "winws2_at_config")
            self.assertIn("--hostlist=lists/tankix.txt", at_config_path.read_text(encoding="utf-8"))

    def test_winws2_compile_launches_safe_at_config_file(self) -> None:
        from threading import RLock

        from winws_runtime.runners.zapret2_runner import Winws2StrategyRunner

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lists_dir = root / "lists"
            lists_dir.mkdir()
            (lists_dir / "tankix.txt").write_text("example.com\n", encoding="utf-8")
            preset_path = root / "selected with spaces.txt"
            preset_path.write_text(
                "\n".join(
                    (
                        "# Preset: selected with spaces",
                        "--wf-tcp-out=443",
                        "--new",
                        "--name=youtube.com (QUIC)",
                        "--filter-tcp=443",
                        "--hostlist=lists/tankix.txt",
                        "--lua-desync=fake:blob=tls_google",
                        "",
                    )
                ),
                encoding="utf-8",
            )

            runner = object.__new__(Winws2StrategyRunner)
            runner._state_lock = RLock()
            runner._prepared_preset_cache = {}
            runner.work_dir = str(root)
            runner.lists_dir = str(lists_dir)
            runner.bin_dir = str(root / "bin")

            artifact = runner._compile_preset_artifact(str(preset_path))

            self.assertTrue(artifact.validation_ok, artifact.validation_report)
            self.assertEqual(len(artifact.launch_args), 1)
            self.assertTrue(artifact.launch_args[0].startswith("@"))
            at_config_path = Path(artifact.launch_args[0][1:])
            self.assertTrue(at_config_path.exists())
            at_config_text = at_config_path.read_text(encoding="utf-8")
            self.assertNotIn("# Preset:", at_config_text)
            self.assertIn("'--name=youtube.com (QUIC)'", at_config_text)
            self.assertIn("--hostlist=lists/tankix.txt", at_config_text)

            at_config_path.unlink()
            rebuilt = runner._compile_preset_artifact(str(preset_path))
            self.assertTrue(Path(rebuilt.launch_args[0][1:]).exists())

    def test_winws2_compile_resolves_windivert_filter_paths_without_duplicate_folder(self) -> None:
        from threading import RLock

        from winws_runtime.runners.zapret2_runner import Winws2StrategyRunner

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            filter_dir = root / "windivert.filter"
            filter_dir.mkdir()
            (filter_dir / "windivert_part.discord_media.txt").write_text(
                "true\n",
                encoding="utf-8",
            )
            preset_path = root / "selected.txt"
            preset_path.write_text(
                "\n".join(
                    (
                        "--wf-tcp-out=443",
                        "--wf-raw-part=@windivert.filter/windivert_part.discord_media.txt",
                        "--filter-tcp=443",
                        "--lua-desync=fake:blob=tls_google",
                        "",
                    )
                ),
                encoding="utf-8",
            )

            runner = object.__new__(Winws2StrategyRunner)
            runner._state_lock = RLock()
            runner._prepared_preset_cache = {}
            runner.work_dir = str(root)
            runner.lists_dir = str(root / "lists")
            runner.bin_dir = str(root / "bin")

            artifact = runner._compile_preset_artifact(str(preset_path))

            self.assertTrue(artifact.validation_ok, artifact.validation_report)
            self.assertEqual(len(artifact.launch_args), 1)
            self.assertTrue(artifact.launch_args[0].startswith("@"))
            self.assertNotIn("windivert.filter/windivert.filter", "/".join(artifact.launch_args))

    def test_runner_reads_stdout_when_winws_exits_immediately(self) -> None:
        from winws_runtime.runners.zapret2_runner import Winws2StrategyRunner

        class FakeProcess:
            def communicate(self, timeout=None):
                return b"winws stdout diagnostic\n", b""

        runner = object.__new__(Winws2StrategyRunner)

        output = runner._read_process_startup_output(FakeProcess())

        self.assertEqual(output, "winws stdout diagnostic")

    def test_winws1_compile_resolves_bare_list_paths_for_launch(self) -> None:
        from threading import RLock

        from winws_runtime.runners.zapret1_runner import Winws1StrategyRunner

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lists_dir = root / "lists"
            lists_dir.mkdir()
            (lists_dir / "tankix.txt").write_text("example.com\n", encoding="utf-8")
            preset_path = root / "selected.txt"
            preset_path.write_text(
                "\n".join(
                    (
                        "--wf-tcp=443",
                        "--filter-tcp=443",
                        "--hostlist=tankix.txt",
                        "--dpi-desync=fake",
                        "",
                    )
                ),
                encoding="utf-8",
            )

            runner = object.__new__(Winws1StrategyRunner)
            runner._state_lock = RLock()
            runner._prepared_preset_cache = {}
            runner.work_dir = str(root)
            runner.lists_dir = str(lists_dir)
            runner.bin_dir = str(root / "bin")

            artifact = runner._compile_preset_artifact(str(preset_path))

            self.assertTrue(artifact.validation_ok, artifact.validation_report)
            self.assertIn(f"--hostlist={lists_dir / 'tankix.txt'}", artifact.launch_args)
            self.assertNotIn("--hostlist=tankix.txt", artifact.launch_args)

    def test_launch_preparation_rejects_invalid_ranges_and_payload(self) -> None:
        from winws_runtime.preset_launch_text import prepare_winws2_preset_text_for_launch

        cases = (
            ("--out-range=8", "out-range"),
            ("--in-range=bad", "in-range"),
            ("--payload=not_a_payload", "payload"),
        )

        for line, expected in cases:
            with self.subTest(line=line):
                source = "\n".join(
                    (
                        "--wf-tcp-out=443",
                        "--filter-tcp=443",
                        "--hostlist=lists/youtube.txt",
                        line,
                        "--lua-desync=fake:blob=tls_google",
                        "",
                    )
                )
                with self.assertRaisesRegex(ValueError, expected):
                    prepare_winws2_preset_text_for_launch(source, source_name="bad.txt")

    def test_profile_editor_rejects_non_engine_range_value(self) -> None:
        from profile.parser import parse_preset_text
        from profile.editable_settings import EditableProfileSettings, with_editable_profile_settings
        from settings.mode import ENGINE_WINWS2

        preset = parse_preset_text(
            "\n".join(
                (
                    "--filter-tcp=443",
                    "--hostlist=lists/youtube.txt",
                    "--lua-desync=fake:blob=tls_google",
                    "",
                )
            ),
            engine=ENGINE_WINWS2,
            source_name="editable.txt",
        )

        with self.assertRaisesRegex(ValueError, "packet range"):
            with_editable_profile_settings(
                preset,
                0,
                EditableProfileSettings(
                    filter_kind="hostlist",
                    filter_value="lists/youtube.txt",
                    in_range="x",
                    out_range="d8",
                ),
            )


if __name__ == "__main__":
    unittest.main()
