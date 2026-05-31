import inspect
import unittest

import log.log as log_module


class LegacyLogViewerRuntimeTest(unittest.TestCase):
    def test_log_core_does_not_keep_legacy_viewer_path(self) -> None:
        source = inspect.getsource(log_module)

        self.assertFalse(hasattr(log_module, "LogViewerDialog"))
        self.assertFalse(hasattr(log_module, "_build_log_viewer_dialog_class"))
        self.assertFalse(hasattr(log_module, "_LogViewerDialogClass"))
        self.assertNotIn("QDialog", source)
        self.assertNotIn("QThread", source)
        self.assertNotIn("moveToThread", source)
        self.assertNotIn("thread.start()", source)
        self.assertNotIn("subprocess.Popen", source)


if __name__ == "__main__":
    unittest.main()
