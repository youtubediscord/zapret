from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class StrategyTechniqueVisual:
    key: str
    label: str
    icon_name: str
    color: str
    description: str


@dataclass(frozen=True)
class StrategyVisual:
    technique_keys: tuple[str, ...]
    icon_name: str
    color: str
    colors: tuple[str, ...]
    label: str
    description: str


_UNKNOWN_TECHNIQUE = StrategyTechniqueVisual(
    key="custom",
    label="Своя",
    icon_name="ri.question-line",
    color="#9aa6b2",
    description="готовая стратегия не распознана по --lua-desync",
)

_TECHNIQUES: dict[str, StrategyTechniqueVisual] = {
    "fake": StrategyTechniqueVisual(
        key="fake",
        label="Fake",
        icon_name="ri.magic-line",
        color="#ff6b6b",
        description="подмена пакета",
    ),
    "split": StrategyTechniqueVisual(
        key="split",
        label="Split",
        icon_name="ri.scissors-cut-line",
        color="#f59e0b",
        description="разделение данных",
    ),
    "multisplit": StrategyTechniqueVisual(
        key="multisplit",
        label="MultiSplit",
        icon_name="ri.split-cells-horizontal",
        color="#4cc2ff",
        description="несколько точек разделения данных",
    ),
    "disorder": StrategyTechniqueVisual(
        key="disorder",
        label="Disorder",
        icon_name="ri.shuffle-line",
        color="#58d17a",
        description="перестановка частей данных",
    ),
    "multidisorder": StrategyTechniqueVisual(
        key="multidisorder",
        label="MultiDisorder",
        icon_name="ri.shuffle-line",
        color="#58d17a",
        description="перестановка нескольких частей данных",
    ),
    "syndata": StrategyTechniqueVisual(
        key="syndata",
        label="Syndata",
        icon_name="ri.database-2-line",
        color="#aeb8c5",
        description="добавление данных в SYN",
    ),
    "send": StrategyTechniqueVisual(
        key="send",
        label="Send",
        icon_name="ri.send-plane-2-line",
        color="#76d0ff",
        description="дополнительная отправка данных",
    ),
    "udplen": StrategyTechniqueVisual(
        key="udplen",
        label="UDPLen",
        icon_name="ri.ruler-line",
        color="#b58cff",
        description="изменение длины UDP-пакета",
    ),
    "oob": StrategyTechniqueVisual(
        key="oob",
        label="OOB",
        icon_name="ri.external-link-line",
        color="#ff78b7",
        description="отправка out-of-band данных",
    ),
    "tcpseg": StrategyTechniqueVisual(
        key="tcpseg",
        label="TCPSeg",
        icon_name="ri.git-branch-line",
        color="#f6c945",
        description="изменение TCP-сегментации",
    ),
    "pass": StrategyTechniqueVisual(
        key="pass",
        label="Pass",
        icon_name="ri.subtract-line",
        color="#8f9aa6",
        description="строка без активного desync-действия",
    ),
}


def describe_strategy_visual(args_text: str) -> StrategyVisual:
    techniques = tuple(_extract_techniques(args_text))
    if not techniques:
        return _visual_from_techniques(())
    return _visual_from_techniques(techniques)


def _visual_from_techniques(technique_keys: tuple[str, ...]) -> StrategyVisual:
    visuals = [_TECHNIQUES[key] for key in technique_keys if key in _TECHNIQUES]
    if not visuals:
        return StrategyVisual(
            technique_keys=(),
            icon_name=_UNKNOWN_TECHNIQUE.icon_name,
            color=_UNKNOWN_TECHNIQUE.color,
            colors=(_UNKNOWN_TECHNIQUE.color,),
            label=_UNKNOWN_TECHNIQUE.label,
            description=_UNKNOWN_TECHNIQUE.description,
        )

    primary = visuals[0]
    labels = [visual.label for visual in visuals]
    descriptions = [f"{visual.label}: {visual.description}" for visual in visuals]
    return StrategyVisual(
        technique_keys=tuple(visual.key for visual in visuals),
        icon_name=primary.icon_name,
        color=primary.color,
        colors=tuple(visual.color for visual in visuals),
        label=" + ".join(labels),
        description="; ".join(descriptions),
    )


def _extract_techniques(args_text: str) -> list[str]:
    result: list[str] = []
    for value in re.findall(r"(?:^|\s)--lua-desync=([a-zA-Z0-9_-]+)", str(args_text or "")):
        key = _map_lua_desync_value(value)
        if key and key not in result:
            result.append(key)
    return result


def _map_lua_desync_value(value: str) -> str | None:
    raw = str(value or "").strip().lower()
    if not raw:
        return None
    if raw == "pass":
        return "pass"
    if "syndata" in raw:
        return "syndata"
    if raw == "send":
        return "send"
    if "udplen" in raw:
        return "udplen"
    if "oob" in raw:
        return "oob"
    if "multidisorder" in raw or "fakeddisorder" in raw:
        return "multidisorder"
    if "disorder" in raw:
        return "disorder"
    if "multisplit" in raw:
        return "multisplit"
    if "split" in raw:
        return "split"
    if "tcpseg" in raw:
        return "tcpseg"
    if "fake" in raw or "hostfakesplit" in raw:
        return "fake"
    return None
