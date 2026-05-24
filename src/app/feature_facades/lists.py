from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class ListsFeature:
    startup_lists_check: Callable


def build_lists_feature() -> ListsFeature:
    def _public():
        from lists import public as lists_public

        return lists_public

    return ListsFeature(
        startup_lists_check=lambda *args, **kwargs: _public().startup_lists_check(*args, **kwargs),
    )
