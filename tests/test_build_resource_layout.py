from __future__ import annotations

from pathlib import Path
import sys
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

    def test_inno_installs_profile_templates_from_private_resources(self) -> None:
        iss = self._read_inno_script()

        self.assertIn(r'{#PRIVATERESOURCES}\profile\templates\*.txt', iss)
        self.assertNotIn(r'{#PUBLICSRC}\profile\templates\*.txt', iss)

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
            r'Name: "{commondesktop}\{#ShortcutName}"; Filename: "{app}\Zapret.exe"; WorkingDir: "{app}"; Check: ShouldCreateDesktopIcon',
            iss,
        )
        self.assertIn('Name: desktopicon; Description: "Создать ярлык на рабочем столе"; Flags: unchecked', iss)
        self.assertNotIn(
            r'Name: "{commondesktop}\{#ShortcutName}"; Filename: "{app}\Zapret.exe"; Tasks: desktopicon',
            iss,
        )

    def test_pyinstaller_icon_source_is_private_dist_ico_only(self) -> None:
        builder = (PRIVATE_ROOT / "build_zapret" / "pyinstaller_builder.py").read_text(encoding="utf-8")

        self.assertIn("PRIVATE_ROOT / 'dist' / 'ico' / icon_file", builder)
        self.assertNotIn("root_path / icon_file", builder)
        self.assertNotIn("root_path / 'ico' / icon_file", builder)
        self.assertNotIn("сборка без иконки", builder)

    def test_nuitka_uses_current_icons_and_includes_dynamic_app_package(self) -> None:
        builder = (PRIVATE_ROOT / "build_zapret" / "nuitka_builder.py").read_text(encoding="utf-8")

        self.assertIn('"ZapretDevLogo4.ico" if channel == CHANNEL_DEV else "Zapret2.ico"', builder)
        self.assertNotIn("ZapretDevLogo3.ico", builder)
        self.assertNotIn("Zapret1.ico", builder)
        self.assertIn('packages_to_include = [\n            "app",', builder)
        self.assertIn('nuitka_args.append(f"--include-package={pkg}")', builder)

    def test_inno_installs_only_required_ico_resources(self) -> None:
        iss = self._read_inno_script()

        self.assertNotIn(r'Source: "{#SOURCEPATH}\ico\*"', iss)
        self.assertIn(r'Source: "{#SOURCEPATH}\ico\Zapret2.ico"; DestDir: "{app}\ico"', iss)
        self.assertIn(r'Source: "{#SOURCEPATH}\ico\ZapretDevLogo4.ico"; DestDir: "{app}\ico"', iss)
        self.assertIn(
            r'Source: "{#PUBLICSRC}\ico\windows11_fluent\sidebar\*.svg"; DestDir: "{app}\src\ico\windows11_fluent\sidebar"',
            iss,
        )

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
