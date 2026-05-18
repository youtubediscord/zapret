from __future__ import annotations

from pathlib import Path
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

    def test_inno_shortcuts_are_versioned_and_recreated_by_single_channel_owner(self) -> None:
        iss = self._read_inno_script()

        self.assertIn('#define ShortcutName AppName + " v" + VERSION', iss)

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


if __name__ == "__main__":
    unittest.main()
