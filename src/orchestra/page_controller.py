"""Контроллер основной страницы orchestra."""

from __future__ import annotations

import orchestra.page_runtime as orchestra_page_runtime


class OrchestraPageController:
    """Действия страницы логов orchestra без привязки к QWidget."""

    def __init__(self, *, orchestra_feature, runtime_feature) -> None:
        self._orchestra = orchestra_feature
        self._runtime = runtime_feature

    def runner(self):
        return self._orchestra.runner

    def is_runtime_running(self) -> bool:
        return orchestra_page_runtime.is_direct_runtime_running(self._runtime)

    def clear_learned_data(self) -> bool:
        if self.runner() is None:
            return False
        self._orchestra.clear_learned_data()
        return True

    def create_clear_learned_worker(self, request_id: int, parent=None):
        from orchestra.page_workers import OrchestraClearLearnedWorker

        return OrchestraClearLearnedWorker(request_id, self, parent)
