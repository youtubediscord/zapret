from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProfileListFilterState:
    """Канонический объект состояния фильтров списка профилей.

    Единственный источник истины для намерения пользователя: поисковый
    запрос, «только добавленные» и активные типы профилей. Объект создаёт
    страница (`PresetSetupPageBase`) и передаёт виджету `ProfilesList` —
    оба читают и пишут одно и то же состояние вместо собственных копий.

    `ProfileListModel` при этом хранит только применённый снимок фильтров,
    приходящий через `apply_view_state`: это не третья копия намерения,
    а состояние уже показанных строк (нужно модели, чтобы решать
    `allow_structural` и детектировать «новый список»).
    """

    search_query: str = ""
    show_only_added: bool = False
    active_profile_types: set[str] = field(default_factory=lambda: {"all"})


__all__ = ["ProfileListFilterState"]
