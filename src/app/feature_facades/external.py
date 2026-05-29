from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True, slots=True, weakref_slot=True, init=False)
class ExternalActionsFeature:
    _open_url: Callable | None = field(default=None, repr=False, compare=False)

    def __init__(self, open_url: Callable | None = None) -> None:
        object.__setattr__(self, "_open_url", open_url)

    @staticmethod
    def _actions():
        from app import external_actions

        return external_actions

    def open_url(self, *args, **kwargs):
        open_url = self._open_url
        if open_url is None:
            open_url = self._actions().open_url
            object.__setattr__(self, "_open_url", open_url)
        return open_url(*args, **kwargs)

    def create_open_url_worker(self, request_id: int, *, url: str, parent=None):
        from app.external_workers import ExternalOpenUrlWorker

        return ExternalOpenUrlWorker(request_id, url=url, open_url_fn=self._open_url, parent=parent)


def build_external_actions_feature() -> ExternalActionsFeature:
    return ExternalActionsFeature()
