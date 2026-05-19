from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from app.page_names import PageName


@dataclass(frozen=True, slots=True)
class PageDepsSources:
    """Внутренние источники deps для сборщика страниц.

    Builder страницы этот объект не получает. Он нужен только в
    `page_composition.py`, где по явной карте выбираются конкретные deps.
    """

    feature_deps: Mapping[str, object]
    ui_state_store: object
    actions: Mapping[str, object]


PageDepsBuilder = Callable[..., dict]


@dataclass(frozen=True, slots=True)
class PageDepsSpec:
    builder: PageDepsBuilder
    features: tuple[str, ...] = field(default_factory=tuple)
    actions: tuple[str, ...] = field(default_factory=tuple)
    include_ui_state_store: bool = False

    def build(self, sources: PageDepsSources, page_name: PageName) -> dict:
        kwargs = {"page_name": page_name}
        for feature_name in self.features:
            kwargs[f"{feature_name}_feature"] = sources.feature_deps[feature_name]
        for action_name in self.actions:
            kwargs[action_name] = sources.actions[action_name]
        if self.include_ui_state_store:
            kwargs["ui_state_store"] = sources.ui_state_store
        return self.builder(**kwargs)


__all__ = [
    "PageDepsBuilder",
    "PageDepsSources",
    "PageDepsSpec",
]
