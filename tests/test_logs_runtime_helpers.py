from __future__ import annotations

import unittest


class LogsRuntimeHelpersTests(unittest.TestCase):
    def test_errors_text_height_checks_document_empty_without_reading_widget_text(self) -> None:
        from log.ui.runtime_helpers import compute_errors_text_height

        class _Size:
            def height(self) -> int:
                return 80

        class _Document:
            def isEmpty(self) -> bool:  # noqa: N802
                return False

            def size(self) -> _Size:
                return _Size()

        class _TextEdit:
            def toPlainText(self) -> str:  # noqa: N802
                raise AssertionError("GUI errors text should not be read to compute height")

            def document(self) -> _Document:
                return _Document()

            def frameWidth(self) -> int:  # noqa: N802
                return 2

        height = compute_errors_text_height(
            text_edit=_TextEdit(),
            min_height=20,
            max_height=200,
        )

        self.assertEqual(height, 100)


if __name__ == "__main__":
    unittest.main()
