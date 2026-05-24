"""Контроллер страницы рейтингов orchestra."""

from __future__ import annotations

from orchestra.ratings_workflow import load_orchestra_ratings_state


class OrchestraRatingsController:
    """Загружает состояние рейтингов без привязки к QWidget."""

    def __init__(self, orchestra) -> None:
        self._orchestra = orchestra

    def load_state(self):
        return load_orchestra_ratings_state(self._orchestra.runner)

    def create_state_load_worker(self, request_id: int, parent=None):
        from orchestra.ratings_worker import OrchestraRatingsStateLoadWorker

        return OrchestraRatingsStateLoadWorker(request_id, self, parent)
