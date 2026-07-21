from __future__ import annotations

import base64
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch


SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from updater import update


class UpdaterInstallerLaunchTests(unittest.TestCase):
    def _installer_path(self, temp_dir: str) -> Path:
        installer = Path(temp_dir) / "O'Brien Setup.exe"
        installer.write_bytes(b"setup")
        return installer

    @patch.object(update, "log")
    @patch.object(update.subprocess, "Popen")
    def test_launch_keeps_dir_with_spaces_as_one_argument(
        self,
        popen: Mock,
        _log: Mock,
    ) -> None:
        process = popen.return_value
        process.communicate.return_value = (b"", b"")
        process.returncode = 0

        with tempfile.TemporaryDirectory() as temp_dir:
            installer = self._installer_path(temp_dir)
            launched = update.launch_installer_winapi(
                str(installer),
                ["/AUTOUPDATE", r"/DIR=C:\Program Files\Zapret Dev"],
            )

        self.assertTrue(launched)
        powershell_args = popen.call_args.args[0]
        self.assertIn("-EncodedCommand", powershell_args)
        encoded = powershell_args[powershell_args.index("-EncodedCommand") + 1]
        command = base64.b64decode(encoded).decode("utf-16le")
        self.assertIn("O''Brien Setup.exe", command)
        self.assertIn(r'"/DIR=C:\Program Files\Zapret Dev"', command)
        self.assertIn("-Verb RunAs -PassThru", command)
        process.communicate.assert_called_once_with(timeout=120)

    @patch.object(update, "log")
    @patch.object(update.subprocess, "Popen")
    def test_launch_reports_uac_cancellation_as_failure(
        self,
        popen: Mock,
        _log: Mock,
    ) -> None:
        process = popen.return_value
        process.communicate.return_value = (b"", b"cancelled")
        process.returncode = 1

        with tempfile.TemporaryDirectory() as temp_dir:
            installer = self._installer_path(temp_dir)
            launched = update.launch_installer_winapi(
                str(installer),
                ["/AUTOUPDATE", r"/DIR=C:\Zapret\Dev"],
            )

        self.assertFalse(launched)


if __name__ == "__main__":
    unittest.main()
