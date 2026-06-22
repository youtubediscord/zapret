from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


class OrchestraIpsetFileTests(unittest.TestCase):
    def test_current_ipset_files_ignore_root_only_sidecars(self) -> None:
        from orchestra.orchestra_runner import _current_ipset_final_files

        with TemporaryDirectory() as temp_dir:
            lists_root = Path(temp_dir) / "lists"
            (lists_root / "base").mkdir(parents=True)
            (lists_root / "user").mkdir()
            (lists_root / "base" / "ipset-current.txt").write_text("1.1.1.0/24\n", encoding="utf-8")
            (lists_root / "user" / "ipset-user-only.txt").write_text("2.2.2.0/24\n", encoding="utf-8")
            (lists_root / "ipset-current.txt").write_text("1.1.1.0/24\n", encoding="utf-8")
            (lists_root / "ipset-user-only.txt").write_text("2.2.2.0/24\n", encoding="utf-8")
            (lists_root / "ipset-current.user.txt").write_text("3.3.3.0/24\n", encoding="utf-8")
            (lists_root / "ipset-current.base.txt").write_text("4.4.4.0/24\n", encoding="utf-8")

            files = _current_ipset_final_files(str(lists_root))

        self.assertEqual(
            [Path(path).name for path in files],
            ["ipset-current.txt", "ipset-user-only.txt"],
        )


if __name__ == "__main__":
    unittest.main()
