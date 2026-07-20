from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest


PUBLIC_ROOT = Path(__file__).resolve().parents[1]
PRIVATE_ROOT = PUBLIC_ROOT.parent / "private_zapretgui"


class BuildResourceLayoutTests(unittest.TestCase):
    def _read_inno_script(self) -> str:
        return (PRIVATE_ROOT / "build_zapret" / "zapret_universal.iss").read_text(encoding="utf-8")

    def test_profile_templates_are_private_resources(self) -> None:
        private_template = PRIVATE_ROOT / "resources" / "profile" / "templates" / "all_profiles.txt"
        public_template = PUBLIC_ROOT / "src" / "profile" / "templates" / "all_profiles.txt"

        self.assertTrue(private_template.exists(), private_template)
        self.assertFalse(public_template.exists(), public_template)

    def test_inno_installs_profile_templates_from_prepared_stage(self) -> None:
        iss = self._read_inno_script()

        self.assertIn(r'{#SOURCEPATH}\profile\templates\*.txt', iss)
        self.assertNotIn("PUBLICSRC", iss)
        self.assertNotIn("PRIVATERESOURCES", iss)
        self.assertNotIn("PROJECTPATH", iss)

    def test_inno_copies_lists_to_base_without_nested_base_or_user_dirs(self) -> None:
        iss = self._read_inno_script()
        list_lines = [
            line
            for line in iss.splitlines()
            if r'{#SOURCEPATH}\lists' in line and r'DestDir: "{app}\lists\base"' in line
        ]

        self.assertTrue(list_lines)
        for line in list_lines:
            self.assertNotIn("recursesubdirs", line)
            self.assertNotIn("createallsubdirs", line)

    def test_inno_does_not_install_local_help_folder(self) -> None:
        iss = self._read_inno_script()

        self.assertNotIn(r"{#SOURCEPATH}\help\*", iss)
        self.assertNotIn(r'DestDir: "{app}\help"', iss)

    def test_inno_shortcuts_are_versioned_and_recreated_by_single_channel_owner(self) -> None:
        iss = self._read_inno_script()

        self.assertIn("#define ShortcutName AppName", iss)

        expected_delete_patterns = [
            r'Type: files; Name: "{commondesktop}\{#AppName}.lnk"',
            r'Type: files; Name: "{commondesktop}\{#AppName} v*.lnk"',
            r'Type: files; Name: "{group}\{#AppName}.lnk"',
            r'Type: files; Name: "{group}\{#AppName} v*.lnk"',
            r'Type: files; Name: "{group}\Удалить {#AppName}.lnk"',
            r'Type: files; Name: "{group}\Удалить {#AppName} v*.lnk"',
        ]
        for pattern in expected_delete_patterns:
            self.assertIn(pattern, iss)

        self.assertIn("HadDesktopShortcut: Boolean;", iss)
        self.assertIn("function ChannelDesktopShortcutExists: Boolean;", iss)
        self.assertIn("function ShouldCreateDesktopIcon: Boolean;", iss)
        self.assertIn("HadDesktopShortcut := ChannelDesktopShortcutExists;", iss)
        self.assertIn(
            r'Name: "{commondesktop}\{#ShortcutName}"; Filename: "{app}\_internal\Zapret.exe"; WorkingDir: "{app}"; Check: ShouldCreateDesktopIcon',
            iss,
        )
        self.assertIn('Name: desktopicon; Description: "Создать ярлык на рабочем столе"; Flags: unchecked', iss)
        self.assertNotIn(
            r'Name: "{commondesktop}\{#ShortcutName}"; Filename: "{app}\_internal\Zapret.exe"; Tasks: desktopicon',
            iss,
        )
        self.assertIn("procedure RefreshPinnedTaskbarShortcutTarget;", iss)
        self.assertIn("RefreshPinnedTaskbarShortcutTarget;", iss)
        self.assertIn("CreateShellLink(", iss)
        self.assertIn("AppExe := ExpandConstant('{app}\\_internal\\Zapret.exe');", iss)

    def test_pyinstaller_icon_source_is_private_dist_ico_only(self) -> None:
        builder = (PRIVATE_ROOT / "build_zapret" / "pyinstaller_builder.py").read_text(encoding="utf-8")

        self.assertIn("PRIVATE_ROOT / 'dist' / 'ico' / icon_file", builder)
        self.assertNotIn("root_path / icon_file", builder)
        self.assertNotIn("root_path / 'ico' / icon_file", builder)
        self.assertNotIn("сборка без иконки", builder)

    def test_nuitka_uses_current_icons_and_source_driven_dynamic_modules(self) -> None:
        builder = (PRIVATE_ROOT / "build_zapret" / "nuitka_builder.py").read_text(encoding="utf-8")

        self.assertIn('"ZapretDevLogo4.ico" if channel == CHANNEL_DEV else "Zapret2.ico"', builder)
        self.assertNotIn("ZapretDevLogo3.ico", builder)
        self.assertNotIn("Zapret1.ico", builder)
        self.assertIn("iter_lazy_feature_facade_modules", builder)
        self.assertIn("iter_lazy_page_modules", builder)
        self.assertIn('nuitka_args.append(f"--include-module={module}")', builder)
        self.assertNotIn("packages_to_include = [", builder)

    def test_nuitka_dynamic_modules_cover_facades_and_lazy_pages(self) -> None:
        build_path = PRIVATE_ROOT / "build_zapret"
        old_path = list(sys.path)
        sys.path.insert(0, str(build_path))
        try:
            sys.modules.pop("nuitka_builder", None)
            import nuitka_builder

            modules = nuitka_builder._lazy_project_modules()
            nuitka_builder._validate_lazy_project_modules(modules)
        finally:
            sys.modules.pop("nuitka_builder", None)
            sys.path[:] = old_path

        self.assertIn("app.feature_facades.appearance", modules)
        self.assertIn("presets.ui.control.zapret2.page", modules)
        self.assertIn("presets.ui.control.zapret1.page", modules)

    def test_both_builders_cover_the_same_dynamic_application_modules(self) -> None:
        build_path = PRIVATE_ROOT / "build_zapret"
        old_path = list(sys.path)
        sys.path.insert(0, str(build_path))
        try:
            sys.modules.pop("nuitka_builder", None)
            sys.modules.pop("pyinstaller_builder", None)
            import nuitka_builder
            import pyinstaller_builder

            expected = set(nuitka_builder._lazy_project_modules())
            pyinstaller_hidden = set(pyinstaller_builder._hiddenimports_for_spec())

            self.assertTrue(expected)
            self.assertTrue(expected.issubset(pyinstaller_hidden))
            self.assertIn("app.feature_facades.appearance", expected)
            self.assertIn("presets.ui.control.zapret2.page", expected)
        finally:
            sys.modules.pop("nuitka_builder", None)
            sys.modules.pop("pyinstaller_builder", None)
            sys.path[:] = old_path

    def test_nuitka_does_not_bundle_builder_or_full_qt_dependencies(self) -> None:
        builder = (PRIVATE_ROOT / "build_zapret" / "nuitka_builder.py").read_text(encoding="utf-8")

        self.assertNotIn('"--include-qt-plugins=all"', builder)
        self.assertNotIn('            "paramiko",', builder)
        self.assertNotIn('            "pkg_resources",', builder)
        self.assertIn('"--nofollow-import-to=numpy"', builder)
        self.assertIn('"--nofollow-import-to=PIL"', builder)
        self.assertIn('"--noinclude-dlls=opengl32sw.dll"', builder)

    def test_nuitka_clears_stale_dist_but_preserves_compilation_cache(self) -> None:
        build_path = PRIVATE_ROOT / "build_zapret"
        old_path = list(sys.path)
        sys.path.insert(0, str(build_path))
        try:
            sys.modules.pop("nuitka_builder", None)
            import nuitka_builder

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                build_cache = temp_path / "main.build"
                stale_dist = temp_path / "main.dist"
                build_cache.mkdir()
                stale_dist.mkdir()
                (build_cache / "cache.bin").write_bytes(b"cache")
                (stale_dist / "unused.dll").write_bytes(b"old")

                nuitka_builder._clear_previous_dist_outputs(temp_path)

                self.assertTrue((build_cache / "cache.bin").is_file())
                self.assertFalse(stale_dist.exists())
        finally:
            sys.modules.pop("nuitka_builder", None)
            sys.path[:] = old_path

    def test_builders_do_not_delete_unrelated_runtime_or_nuitka_caches(self) -> None:
        pyinstaller = (PRIVATE_ROOT / "build_zapret" / "pyinstaller_builder.py").read_text(encoding="utf-8")

        self.assertNotIn("def cleanup_pyinstaller_temp", pyinstaller)
        self.assertNotIn("tempfile.gettempdir()", pyinstaller)
        self.assertIn("main.build Nuitka сохранён", pyinstaller)

    def test_release_builder_defaults_to_nuitka(self) -> None:
        gui = (PRIVATE_ROOT / "build_zapret" / "build_release_gui.py").read_text(encoding="utf-8")
        cli = (PRIVATE_ROOT / "build_zapret" / "build_release_cli.py").read_text(encoding="utf-8")

        self.assertIn('self.build_method_var = tk.StringVar(value="nuitka")', gui)
        self.assertIn('value="nuitka"', gui)
        self.assertIn('value="pyinstaller"', gui)
        self.assertIn('choices=["nuitka", "pyinstaller"]', cli)
        self.assertIn('default="nuitka"', cli)
        self.assertIn("Запуск из исходников запрещён", gui)
        self.assertIn("Запуск приложения из исходников запрещён", cli)

    def test_ci_and_builder_document_only_internal_exe_launch(self) -> None:
        ci = (PRIVATE_ROOT / "build_zapret" / "ci_build.py").read_text(encoding="utf-8")
        readme = (PRIVATE_ROOT / "build_zapret" / "README.md").read_text(encoding="utf-8")

        self.assertIn("out_dir = artifact_root / RUNTIME_DIR_NAME", ci)
        self.assertIn('choices=["nuitka", "pyinstaller"]', ci)
        self.assertIn('default="nuitka"', ci)
        self.assertIn("target_dir=out_dir", ci)
        self.assertIn("<корень установки>\\_internal\\Zapret.exe", readme)
        self.assertIn("Запуск самого приложения из Python-исходников запрещён", readme)

    def test_public_windows_workflow_uses_same_internal_layout_and_nuitka_default(self) -> None:
        workflow = (PUBLIC_ROOT / ".github" / "workflows" / "windows-release.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("default: nuitka", workflow)
        self.assertIn("- nuitka", workflow)
        self.assertIn("- pyinstaller", workflow)
        self.assertIn("ZAPRET_BUILD_METHOD: ${{ github.event.inputs.builder || 'nuitka' }}", workflow)
        self.assertIn('$runtimeTarget = Join-Path $artifactRoot "_internal"', workflow)
        self.assertIn('Join-Path $runtimeTarget "Zapret.exe"', workflow)
        self.assertIn("path: artifact/", workflow)
        self.assertNotIn("cd src", workflow)
        self.assertNotIn("src/dist/Zapret/", workflow)
        self.assertNotIn("--paths . main.py", workflow)

    def test_cli_uses_nuitka_by_default_and_normalizes_old_flat_target(self) -> None:
        build_path = PRIVATE_ROOT / "build_zapret"
        old_path = list(sys.path)
        sys.path.insert(0, str(build_path))
        try:
            sys.modules.pop("build_release_cli", None)
            import build_release_cli

            parsed = build_release_cli.parse_args(
                [
                    "--channel",
                    "dev",
                    "--version",
                    "21.1.5.4",
                    "--skip-github",
                    "--skip-ssh",
                ]
            )
            self.assertEqual(parsed.build_method, "nuitka")

            options = build_release_cli.BuildOptions(
                channel="dev",
                version="21.1.5.4",
                notes="test",
                build_method="nuitka",
                fast_exe=True,
                fast_exe_dest=r"C:\Zapret\Dev\Zapret.exe",
                publish_telegram=False,
                telegram_use_socks=False,
                skip_github=True,
                github_nonfatal=False,
                skip_ssh=True,
                run_installer=False,
            )
            builder = build_release_cli.ConsoleReleaseBuilder(options)
            self.assertEqual(
                builder._fast_dest_exe_path("dev"),
                Path(r"C:\Zapret\Dev\_internal\Zapret.exe"),
            )
        finally:
            sys.modules.pop("build_release_cli", None)
            sys.path[:] = old_path

    def test_both_builders_share_one_internal_runtime_layout(self) -> None:
        gui = (PRIVATE_ROOT / "build_zapret" / "build_release_gui.py").read_text(encoding="utf-8")
        nuitka = (PRIVATE_ROOT / "build_zapret" / "nuitka_builder.py").read_text(encoding="utf-8")
        pyinstaller = (PRIVATE_ROOT / "build_zapret" / "pyinstaller_builder.py").read_text(encoding="utf-8")
        paths = (PRIVATE_ROOT / "build_zapret" / "paths.py").read_text(encoding="utf-8")
        installer = self._read_inno_script()

        self.assertIn('RUNTIME_DIR_NAME = "_internal"', paths)
        self.assertIn("target_dir = DIST_RUNTIME_DIR", nuitka)
        self.assertIn("contents_directory='.'", pyinstaller)
        self.assertIn("replace_runtime_output(dist_dir, target_dir)", nuitka)
        self.assertIn("target_dir = Path(target_dir or DIST_RUNTIME_DIR).resolve()", pyinstaller)
        self.assertIn("replace_runtime_output(source_runtime_dir, target_dir)", pyinstaller)
        self.assertIn("runtime_stage = stage_root / RUNTIME_DIR_NAME", gui)
        self.assertNotIn("_nuitka_runtime", gui)
        self.assertNotIn("_nuitka_runtime", installer)
        self.assertNotIn(r'Source: "{#SOURCEPATH}\Zapret.exe"', installer)
        self.assertIn(
            r'Source: "{#SOURCEPATH}\_internal\*"; DestDir: "{app}\_internal"',
            installer,
        )
        self.assertIn('Type: filesandordirs; Name: "{app}\\_internal"', installer)
        self.assertIn('Type: files; Name: "{app}\\Zapret.exe"', installer)
        self.assertIn('Type: files; Name: "{app}\\*.dll"', installer)
        self.assertIn('Type: files; Name: "{app}\\*.pyd"', installer)
        self.assertIn('Type: filesandordirs; Name: "{app}\\src"', installer)

    def test_both_builders_use_strict_atomic_runtime_normalization(self) -> None:
        build_path = PRIVATE_ROOT / "build_zapret"
        old_path = list(sys.path)
        sys.path.insert(0, str(build_path))
        try:
            sys.modules.pop("runtime_output", None)
            import runtime_output

            with tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                source = root / "source"
                target = root / "_internal"
                source.mkdir()
                target.mkdir()
                (source / "Zapret.exe").write_bytes(b"new-exe")
                (source / "runtime.dll").write_bytes(b"new-dll")
                (target / "Zapret.exe").write_bytes(b"old-exe")
                (target / "old.dll").write_bytes(b"old-dll")

                produced = runtime_output.replace_runtime_output(source, target)

                self.assertEqual(produced, target / "Zapret.exe")
                self.assertEqual(produced.read_bytes(), b"new-exe")
                self.assertEqual((target / "runtime.dll").read_bytes(), b"new-dll")
                self.assertFalse((target / "old.dll").exists())
                self.assertFalse((root / "_internal.new").exists())
                self.assertFalse((root / "_internal.old").exists())

                invalid_source = root / "invalid"
                invalid_source.mkdir()
                with self.assertRaisesRegex(FileNotFoundError, "Zapret.exe"):
                    runtime_output.replace_runtime_output(invalid_source, target)

                self.assertEqual(produced.read_bytes(), b"new-exe")
        finally:
            sys.modules.pop("runtime_output", None)
            sys.path[:] = old_path

    def test_fast_deploy_replaces_complete_internal_runtime(self) -> None:
        gui = (PRIVATE_ROOT / "build_zapret" / "build_release_gui.py").read_text(encoding="utf-8")
        cli = (PRIVATE_ROOT / "build_zapret" / "build_release_cli.py").read_text(encoding="utf-8")

        self.assertIn("dst = replace_runtime_output(src_runtime, dst_runtime)", gui)
        self.assertNotIn("Синхронизация библиотек Nuitka рядом с Zapret.exe", gui)
        self.assertNotIn("def publish_exe_to_telegram", gui)
        self.assertIn("if fast_exe and publish_telegram:", gui)
        self.assertIn("if options.fast_exe and options.publish_telegram:", cli)

    def test_cli_rejects_publishing_internal_runtime_as_one_exe(self) -> None:
        build_path = PRIVATE_ROOT / "build_zapret"
        old_path = list(sys.path)
        sys.path.insert(0, str(build_path))
        try:
            sys.modules.pop("build_release_cli", None)
            import build_release_cli

            options = build_release_cli.BuildOptions(
                channel="dev",
                version="1.2.3.4",
                notes="test",
                build_method="nuitka",
                fast_exe=True,
                fast_exe_dest=None,
                publish_telegram=True,
                telegram_use_socks=False,
                skip_github=True,
                github_nonfatal=False,
                skip_ssh=True,
                run_installer=False,
            )
            builder = build_release_cli.ConsoleReleaseBuilder(options)

            with self.assertRaisesRegex(RuntimeError, "всю папку _internal"):
                builder._validate_options()
        finally:
            sys.modules.pop("build_release_cli", None)
            sys.path[:] = old_path

    def test_fast_deploy_cleanup_removes_only_old_flat_runtime(self) -> None:
        build_path = PRIVATE_ROOT / "build_zapret"
        old_path = list(sys.path)
        sys.path.insert(0, str(build_path))
        try:
            sys.modules.pop("build_release_cli", None)
            import build_release_cli

            options = build_release_cli.BuildOptions(
                channel="dev",
                version="1.2.3.4",
                notes="test",
                build_method="nuitka",
                fast_exe=True,
                fast_exe_dest=None,
                publish_telegram=False,
                telegram_use_socks=False,
                skip_github=True,
                github_nonfatal=False,
                skip_ssh=True,
                run_installer=False,
            )
            builder = build_release_cli.ConsoleReleaseBuilder(options)

            with tempfile.TemporaryDirectory() as temp_dir:
                app_root = Path(temp_dir) / "Zapret" / "Dev"
                internal = app_root / "_internal"
                settings = app_root / "settings"
                internal.mkdir(parents=True)
                settings.mkdir()
                (internal / "Zapret.exe").write_bytes(b"new")
                (settings / "settings.json").write_text("{}", encoding="utf-8")
                (app_root / "Zapret.exe").write_bytes(b"old")
                (app_root / "python314.dll").write_bytes(b"old")
                (app_root / "_socket.pyd").write_bytes(b"old")
                (app_root / "base_library.zip").write_bytes(b"old")
                (app_root / "PyQt6").mkdir()
                (app_root / "src").mkdir()

                removed = builder._cleanup_legacy_flat_runtime(app_root)

                self.assertEqual(removed, 6)
                self.assertTrue((internal / "Zapret.exe").is_file())
                self.assertTrue((settings / "settings.json").is_file())
                self.assertFalse((app_root / "Zapret.exe").exists())
                self.assertFalse((app_root / "python314.dll").exists())
                self.assertFalse((app_root / "_socket.pyd").exists())
                self.assertFalse((app_root / "base_library.zip").exists())
                self.assertFalse((app_root / "PyQt6").exists())
                self.assertFalse((app_root / "src").exists())
        finally:
            sys.modules.pop("build_release_cli", None)
            sys.path[:] = old_path

    def test_installer_stage_keeps_runtime_only_inside_internal(self) -> None:
        build_path = PRIVATE_ROOT / "build_zapret"
        old_path = list(sys.path)
        sys.path.insert(0, str(build_path))
        try:
            sys.modules.pop("build_release_cli", None)
            import build_release_cli

            options = build_release_cli.BuildOptions(
                channel="dev",
                version="1.2.3.4",
                notes="test",
                build_method="nuitka",
                fast_exe=False,
                fast_exe_dest=None,
                publish_telegram=False,
                telegram_use_socks=False,
                skip_github=True,
                github_nonfatal=False,
                skip_ssh=True,
                run_installer=False,
            )
            builder = build_release_cli.ConsoleReleaseBuilder(options)

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_root = Path(temp_dir)
                source_root = temp_root / "source"
                runtime_root = temp_root / "runtime"
                stage_root = temp_root / "stage"
                source_root.mkdir()
                runtime_root.mkdir()
                (runtime_root / "Zapret.exe").write_bytes(b"exe")
                (runtime_root / "python314.dll").write_bytes(b"dll")
                for dir_name in (
                    "bin",
                    "exe",
                    "json",
                    "lists",
                    "lua",
                    "sos",
                    "windivert.filter",
                    "themes",
                ):
                    directory = source_root / dir_name
                    directory.mkdir()
                    (directory / "required.dat").write_bytes(b"resource")
                generated_source_list = source_root / "lists" / "other.txt"
                generated_source_list.write_text("source must stay untouched", encoding="utf-8")

                builder._source_root = lambda: source_root
                builder._built_runtime_root = lambda: runtime_root
                builder._installer_stage_root = lambda: stage_root
                builder._copy_installer_icon_resources = lambda _stage: None
                builder._materialize_installer_managed_lists = lambda _stage: None

                prepared = builder._prepare_installer_source_root()

                self.assertEqual(prepared, stage_root)
                self.assertTrue((stage_root / "_internal" / "Zapret.exe").is_file())
                self.assertTrue((stage_root / "_internal" / "python314.dll").is_file())
                self.assertFalse((stage_root / "Zapret.exe").exists())
                self.assertFalse((stage_root / "python314.dll").exists())
                self.assertEqual(
                    generated_source_list.read_text(encoding="utf-8"),
                    "source must stay untouched",
                )
                self.assertTrue((stage_root / "presets" / "winws2_builtin").is_dir())
                self.assertTrue(any((stage_root / "presets" / "winws2_builtin").glob("*.txt")))
                self.assertTrue((stage_root / "presets" / "winws1_builtin").is_dir())
                self.assertTrue(any((stage_root / "presets" / "winws1_builtin").glob("*.txt")))
                self.assertTrue((stage_root / "profile" / "strategy_catalogs" / "winws2").is_dir())
                self.assertTrue((stage_root / "profile" / "templates").is_dir())
                self.assertTrue((stage_root / "json" / "hosts_catalog").is_dir())
                self.assertTrue((stage_root / "ico" / "windows11_fluent" / "sidebar").is_dir())
        finally:
            sys.modules.pop("build_release_cli", None)
            sys.path[:] = old_path

    def test_installer_stage_rejects_missing_required_resource_directory(self) -> None:
        build_path = PRIVATE_ROOT / "build_zapret"
        old_path = list(sys.path)
        sys.path.insert(0, str(build_path))
        try:
            sys.modules.pop("build_release_cli", None)
            import build_release_cli

            options = build_release_cli.BuildOptions(
                channel="dev",
                version="1.2.3.4",
                notes="test",
                build_method="nuitka",
                fast_exe=False,
                fast_exe_dest=None,
                publish_telegram=False,
                telegram_use_socks=False,
                skip_github=True,
                github_nonfatal=False,
                skip_ssh=True,
                run_installer=False,
            )
            builder = build_release_cli.ConsoleReleaseBuilder(options)

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_root = Path(temp_dir)
                source_root = temp_root / "source"
                runtime_root = temp_root / "runtime"
                stage_root = temp_root / "stage"
                source_root.mkdir()
                runtime_root.mkdir()
                (runtime_root / "Zapret.exe").write_bytes(b"exe")

                builder._source_root = lambda: source_root
                builder._built_runtime_root = lambda: runtime_root
                builder._installer_stage_root = lambda: stage_root

                with self.assertRaisesRegex(FileNotFoundError, "обязательный каталог"):
                    builder._prepare_installer_source_root()
        finally:
            sys.modules.pop("build_release_cli", None)
            sys.path[:] = old_path

    def test_inno_installs_only_required_ico_resources(self) -> None:
        iss = self._read_inno_script()

        self.assertNotIn(r'Source: "{#SOURCEPATH}\ico\*"', iss)
        self.assertIn(r'Source: "{#SOURCEPATH}\ico\Zapret2.ico"; DestDir: "{app}\ico"', iss)
        self.assertIn(r'Source: "{#SOURCEPATH}\ico\ZapretDevLogo4.ico"; DestDir: "{app}\ico"', iss)
        self.assertIn(
            r'Source: "{#SOURCEPATH}\ico\windows11_fluent\sidebar\*.svg"; DestDir: "{app}\ico\windows11_fluent\sidebar"',
            iss,
        )

    def test_inno_reads_all_required_resources_only_from_prepared_stage(self) -> None:
        iss = self._read_inno_script()

        expected_sources = (
            r'{#SOURCEPATH}\profile\strategy_catalogs\winws2\*.txt',
            r'{#SOURCEPATH}\profile\strategy_catalogs\winws1\*.txt',
            r'{#SOURCEPATH}\profile\templates\*.txt',
            r'{#SOURCEPATH}\presets\winws2_builtin\*.txt',
            r'{#SOURCEPATH}\presets\winws1_builtin\*.txt',
            r'{#SOURCEPATH}\json\hosts_catalog\*',
            r'{#SOURCEPATH}\ico\windows11_fluent\sidebar\*.svg',
        )
        for source in expected_sources:
            self.assertIn(source, iss)

        builder = (PRIVATE_ROOT / "build_zapret" / "build_release_gui.py").read_text(encoding="utf-8")
        self.assertIn("def _copy_installer_managed_resources", builder)
        self.assertIn("PUBLIC_SRC / \"presets\" / \"builtin\" / \"winws2\"", builder)
        self.assertIn("PRIVATE_ROOT / \"resources\" / \"profile\" / \"templates\"", builder)
        self.assertNotIn("f'/DPUBLICSRC=", builder)
        self.assertNotIn("f'/DPRIVATERESOURCES=", builder)

    def test_installer_stage_copies_only_required_ico_resources(self) -> None:
        builder = (PRIVATE_ROOT / "build_zapret" / "build_release_gui.py").read_text(encoding="utf-8")

        self.assertIn('REQUIRED_INSTALLER_ICO_FILES = ("Zapret2.ico", "ZapretDevLogo4.ico")', builder)
        self.assertIn("def _copy_installer_icon_resources", builder)
        self.assertIn("_copy_installer_icon_resources(stage_root)", builder)
        self.assertNotIn('"ico",\n            "lists",', builder)

    def test_installer_stage_does_not_copy_local_help_folder(self) -> None:
        builder = (PRIVATE_ROOT / "build_zapret" / "build_release_gui.py").read_text(encoding="utf-8")

        self.assertNotIn('"help"', builder)

    def test_pyinstaller_hiddenimports_include_lazy_feature_facades(self) -> None:
        build_path = PRIVATE_ROOT / "build_zapret"
        old_path = list(sys.path)
        sys.path.insert(0, str(build_path))
        try:
            sys.modules.pop("pyinstaller_builder", None)
            import pyinstaller_builder

            hiddenimports = pyinstaller_builder._hiddenimports_for_spec()
        finally:
            sys.modules.pop("pyinstaller_builder", None)
            sys.path[:] = old_path

        self.assertIn("app.feature_facades.blockcheck", hiddenimports)


if __name__ == "__main__":
    unittest.main()
