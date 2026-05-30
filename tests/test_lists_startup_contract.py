from __future__ import annotations

import inspect
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class ListsStartupContractTests(unittest.TestCase):
    def test_fast_required_files_check_does_not_import_layered_rebuild_at_module_load(self) -> None:
        from lists import file_manager

        module_prefix = inspect.getsource(file_manager).split("def ensure_required_files_fast", 1)[0]

        self.assertNotIn("lists.core.layered_files", module_prefix)
        self.assertNotIn("rebuild_all_layered_list_files", module_prefix)
        self.assertNotIn("\nfrom log.log import log", module_prefix)

    def test_core_startup_uses_fast_required_files_check(self) -> None:
        from winws_runtime.runtime import startup

        with (
            patch("lists.file_manager.ensure_required_files", side_effect=AssertionError("full rebuild is deferred")),
            patch("lists.file_manager.ensure_required_files_fast", return_value=True) as ensure_fast,
        ):
            startup.init_core_startup()

        ensure_fast.assert_called_once_with()

    def test_fast_required_files_check_skips_rebuild_when_final_files_exist(self) -> None:
        from lists import file_manager

        with tempfile.TemporaryDirectory() as tmp:
            lists_root = Path(tmp)
            for name in ("other.txt", "ipset-all.txt", "ipset-ru.txt"):
                (lists_root / name).write_text("ready\n", encoding="utf-8")

            with (
                patch.object(file_manager, "LISTS_FOLDER", str(lists_root)),
                patch.object(file_manager, "ensure_required_files", side_effect=AssertionError("unexpected rebuild")),
            ):
                self.assertTrue(file_manager.ensure_required_files_fast())

    def test_fast_required_files_check_falls_back_when_final_file_missing(self) -> None:
        from lists import file_manager

        with tempfile.TemporaryDirectory() as tmp:
            lists_root = Path(tmp)
            (lists_root / "other.txt").write_text("ready\n", encoding="utf-8")
            (lists_root / "ipset-all.txt").write_text("ready\n", encoding="utf-8")

            with (
                patch.object(file_manager, "LISTS_FOLDER", str(lists_root)),
                patch.object(file_manager, "ensure_required_files", return_value=True) as ensure_full,
            ):
                self.assertTrue(file_manager.ensure_required_files_fast())

            ensure_full.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
