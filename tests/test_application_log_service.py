from __future__ import annotations

import inspect
import tempfile
import threading
import unittest
from pathlib import Path

from log.file_reader_worker import LogFileReaderWorker
from log.live_stream import LiveLogBridge
from log.log import Logger, _AsyncLogStore
from log.run_log_sessions import RunLogSessionRegistry


class ApplicationLogServiceTests(unittest.TestCase):
    def test_logger_call_does_not_open_log_file_in_calling_thread(self) -> None:
        write_source = inspect.getsource(Logger.write)
        log_source = inspect.getsource(Logger.log)

        self.assertNotIn("open(", write_source)
        self.assertNotIn("open(", log_source)
        self.assertIn("self._store.publish", write_source)
        self.assertIn("self._store.publish", log_source)

    def test_writer_persists_in_order_and_live_subscription_receives_same_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "app.log"
            logger = Logger(str(path), redirect_stdio=False, run_cleanup=False)
            received: list[tuple[int, str]] = []
            received_event = threading.Event()

            def on_text(sequence: int, text: str) -> None:
                received.append((sequence, text))
                if "[INFO] first" in text and "[WARNING] second" in text:
                    received_event.set()

            token, snapshot = logger.open_live_subscription(on_text)
            logger.log("first", "INFO")
            logger.log("second", "WARNING")
            self.assertTrue(logger.flush_pending(timeout=2.0))
            self.assertTrue(received_event.wait(1.0))
            logger.close_live_subscription(token)
            logger.shutdown()

            content = path.read_text(encoding="utf-8-sig")

        self.assertTrue(snapshot.reset_required)
        self.assertIn("Zapret 2 GUI Log", snapshot.text)
        self.assertLess(content.index("[INFO] first"), content.index("[WARNING] second"))
        received_text = "".join(text for _, text in received)
        self.assertLess(received_text.index("[INFO] first"), received_text.index("[WARNING] second"))

    def test_redirected_print_is_buffered_until_complete_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "stdio.log"
            logger = Logger(str(path), redirect_stdio=False, run_cleanup=False)
            logger.orig_stdout = None
            logger.write("one partial")
            self.assertTrue(logger.flush_pending(timeout=2.0))
            before_newline = path.read_text(encoding="utf-8-sig")

            logger.write(" line\n")
            self.assertTrue(logger.flush_pending(timeout=2.0))
            logger.shutdown()
            after_newline = path.read_text(encoding="utf-8-sig")

        self.assertNotIn("one partial", before_newline)
        self.assertEqual(after_newline.count("one partial line"), 1)

    def test_pending_queue_and_live_history_are_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bounded.log"
            store = _AsyncLogStore(
                str(path),
                "header\n",
                max_pending_records=64,
                max_pending_chars=64 * 1024,
                max_history_chars=64 * 1024,
                batch_delay_seconds=0.0,
            )
            for index in range(500):
                store.publish(f"{index:04d} " + ("x" * 1024) + "\n")
            self.assertTrue(store.flush_pending(timeout=3.0))
            self.assertLessEqual(store.history_char_count, 64 * 1024)
            self.assertEqual(store.pending_record_count, 0)
            store.shutdown()

    def test_live_ui_bridge_and_old_file_reader_have_no_periodic_scanner(self) -> None:
        bridge_source = inspect.getsource(LiveLogBridge)
        reader_source = inspect.getsource(LogFileReaderWorker)

        self.assertNotIn("QTimer", bridge_source)
        self.assertNotIn("QThread", bridge_source)
        self.assertNotIn("time.sleep", reader_source)
        self.assertNotIn("poll_interval", reader_source)

    def test_diagnostic_run_log_keeps_one_handle_and_closes_it_explicitly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.log"
            registry = RunLogSessionRegistry()

            self.assertTrue(registry.start(path, "header\n"))
            self.assertEqual(registry.active_session_count, 1)
            registry.append(path, "first")
            registry.append(path, "second")
            registry.close(path)
            self.assertEqual(registry.active_session_count, 0)
            content = path.read_text(encoding="utf-8-sig")

        self.assertEqual(content.splitlines(), ["header", "first", "second"])


if __name__ == "__main__":
    unittest.main()
