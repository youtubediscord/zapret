import queue
import unittest

from ui.log_limits import append_bounded_line, put_latest_bounded


class UiLogLimitsTests(unittest.TestCase):
    def test_append_bounded_line_keeps_latest_lines(self) -> None:
        lines: list[str] = []

        for index in range(5):
            append_bounded_line(lines, f"line-{index}", max_lines=3)

        self.assertEqual(lines, ["line-2", "line-3", "line-4"])

    def test_put_latest_bounded_drops_oldest_queue_items(self) -> None:
        log_queue: queue.Queue[str] = queue.Queue()

        for index in range(5):
            put_latest_bounded(log_queue, f"line-{index}", max_items=3)

        drained = []
        while not log_queue.empty():
            drained.append(log_queue.get_nowait())

        self.assertEqual(drained, ["line-2", "line-3", "line-4"])


if __name__ == "__main__":
    unittest.main()
