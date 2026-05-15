from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class ExternalActionsFeature:
    open_url: Callable


def build_external_actions_feature() -> ExternalActionsFeature:
    from app import external_actions

    return ExternalActionsFeature(
        open_url=external_actions.open_url,
    )
