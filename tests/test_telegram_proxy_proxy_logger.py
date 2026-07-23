from __future__ import annotations

import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from telegram_proxy import proxy_logger


class TelegramProxyLoggerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._file_logger = logging.getLogger("tg_proxy_file")
        self._original_handlers = list(self._file_logger.handlers)
        for handler in self._original_handlers:
            self._file_logger.removeHandler(handler)

    def tearDown(self) -> None:
        self._close_current_handlers()
        for handler in self._original_handlers:
            self._file_logger.addHandler(handler)

    def _close_current_handlers(self) -> None:
        for handler in list(self._file_logger.handlers):
            self._file_logger.removeHandler(handler)
            handler.close()

    def test_log_file_is_created_only_on_first_real_log_line(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.object(proxy_logger, "LOGS_FOLDER", temp_dir),
                patch.object(proxy_logger, "_instance", None),
            ):
                logger = proxy_logger.get_proxy_logger()
                log_path = Path(logger.log_file_path)

                self.assertFalse(log_path.exists())

                logger.log("первая строка Telegram Proxy")
                for handler in self._file_logger.handlers:
                    handler.flush()

                self.assertTrue(log_path.exists())
                self.assertIn(
                    "первая строка Telegram Proxy",
                    log_path.read_text(encoding="utf-8"),
                )

                self._close_current_handlers()


if __name__ == "__main__":
    unittest.main()
