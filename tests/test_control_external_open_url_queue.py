from __future__ import annotations

import unittest
from unittest.mock import Mock, patch


from presets.ui.control.control_page_shared import ControlPageActionMixin


class _Runtime:
    def __init__(self, *, running: bool) -> None:
        self.running = bool(running)
        self.started: list[object] = []

    def is_running(self) -> bool:
        return self.running

    def start_qthread_worker(self, *, worker_factory, **_kwargs):
        worker = worker_factory(0)
        self.started.append(worker)
        return 0, worker


class _Page(ControlPageActionMixin):
    create_external_open_url_worker = Mock()
    _on_external_open_url_finished = Mock()
    _on_external_open_url_failed = Mock()


class ControlExternalOpenUrlQueueTests(unittest.TestCase):
    def test_external_open_url_keeps_all_pending_requests(self) -> None:
        page = _Page()
        page._external_open_url_runtime = _Runtime(running=True)
        page._external_open_url_pending = []
        page.create_external_open_url_worker = Mock()

        _Page._request_external_open_url(
            page,
            "https://example.org/one",
            error_title="Ошибка",
            error_default="Не удалось открыть: {error}",
        )
        _Page._request_external_open_url(
            page,
            "https://example.org/two",
            error_title="Ошибка",
            error_default="Не удалось открыть: {error}",
        )

        page.create_external_open_url_worker.assert_not_called()
        self.assertEqual(
            page._external_open_url_pending,
            [
                ("https://example.org/one", "Ошибка", "Не удалось открыть: {error}"),
                ("https://example.org/two", "Ошибка", "Не удалось открыть: {error}"),
            ],
        )

    def test_duplicate_external_open_url_request_is_queued_once(self) -> None:
        page = _Page()
        page._external_open_url_runtime = _Runtime(running=True)
        page._external_open_url_pending = []
        page.create_external_open_url_worker = Mock()

        _Page._request_external_open_url(
            page,
            "https://example.org/help",
            error_title="Ошибка",
            error_default="Не удалось открыть: {error}",
        )
        _Page._request_external_open_url(
            page,
            "https://example.org/help",
            error_title="Ошибка",
            error_default="Не удалось открыть: {error}",
        )

        page.create_external_open_url_worker.assert_not_called()
        self.assertEqual(
            page._external_open_url_pending,
            [("https://example.org/help", "Ошибка", "Не удалось открыть: {error}")],
        )

    def test_external_open_url_finished_starts_next_pending_request(self) -> None:
        worker = object()
        page = _Page()
        page._cleanup_in_progress = False
        page._external_open_url_runtime = _Runtime(running=False)
        page._external_open_url_pending = [
            ("https://example.org/next", "Ошибка", "Не удалось открыть: {error}")
        ]
        page.create_external_open_url_worker = Mock(return_value=worker)

        callbacks = []
        with patch(
            "presets.ui.control.control_page_shared.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            _Page._on_external_open_url_worker_finished(page, object())

        page.create_external_open_url_worker.assert_not_called()
        self.assertEqual(page._external_open_url_runtime.started, [])
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page.create_external_open_url_worker.assert_called_once_with(0, url="https://example.org/next")
        self.assertEqual(page._external_open_url_runtime.started, [worker])
        self.assertEqual(page._external_open_url_pending, [])

    def test_external_open_url_request_waits_while_start_is_scheduled(self) -> None:
        old_worker = object()
        page = _Page()
        page._cleanup_in_progress = False
        page._external_open_url_runtime = _Runtime(running=False)
        page._external_open_url_pending = []
        page._external_open_url_start_scheduled = False
        page.create_external_open_url_worker = Mock(return_value=old_worker)

        callbacks = []
        with patch(
            "presets.ui.control.control_page_shared.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            _Page._schedule_external_open_url_worker_start(
                page,
                ("https://example.org/old", "Ошибка", "Не удалось открыть: {error}"),
            )
            _Page._request_external_open_url(
                page,
                "https://example.org/new",
                error_title="Ошибка",
                error_default="Не удалось открыть: {error}",
            )

        page.create_external_open_url_worker.assert_not_called()
        self.assertEqual(len(callbacks), 1)
        self.assertEqual(
            page._external_open_url_pending,
            [("https://example.org/new", "Ошибка", "Не удалось открыть: {error}")],
        )

        callbacks[0]()

        page.create_external_open_url_worker.assert_called_once_with(0, url="https://example.org/old")
        self.assertEqual(page._external_open_url_runtime.started, [old_worker])
        self.assertEqual(
            page._external_open_url_pending,
            [("https://example.org/new", "Ошибка", "Не удалось открыть: {error}")],
        )


if __name__ == "__main__":
    unittest.main()
