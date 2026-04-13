from __future__ import annotations

from dataclasses import dataclass

from core.presets.runtime_store import DirectRuntimePresetStore
from direct_preset.engines import (
    winws1_classifier,
    winws1_parser,
    winws1_rules,
    winws1_serializer,
    winws2_classifier,
    winws2_parser,
    winws2_rules,
    winws2_serializer,
)


@dataclass(frozen=True)
class DirectPresetEngineAdapter:
    engine: str
    parser_module: object
    classifier_module: object
    serializer_module: object
    rules_module: object

    def runtime_store(
        self,
        *,
        preset_store: DirectRuntimePresetStore,
        preset_store_v1: DirectRuntimePresetStore,
    ) -> DirectRuntimePresetStore:
        return preset_store if self.engine == "winws2" else preset_store_v1

    def hierarchy_scope_key(self) -> str:
        return "direct_preset_winws2" if self.engine == "winws2" else "direct_preset_winws1"

    def supports_direct_ui_mode(self) -> bool:
        return self.engine == "winws2"

    def supports_structured_target_settings(self) -> bool:
        return self.engine == "winws2"

    def supports_target_sort_order(self) -> bool:
        return self.engine == "winws2"

    def candidate_catalog_names(self, strategy_type: str, protocol_kind: str) -> tuple[str, ...]:
        normalized_type = str(strategy_type or "").strip().lower()
        if normalized_type == "discord_voice":
            return ("voice",)
        if normalized_type in {"tcp", "udp", "http80"}:
            return (normalized_type,)

        normalized_protocol = str(protocol_kind or "").strip().lower()
        if self.engine == "winws2":
            if normalized_protocol in ("udp", "l7"):
                return ("udp",)
            return ("tcp",)
        if normalized_protocol in ("udp", "l7"):
            return ("udp",)
        return ("tcp",)

    def strategy_identity_modes(self, strategy_set: str | None) -> tuple[str, ...]:
        if self.engine == "winws2" and str(strategy_set or "").strip().lower() == "basic":
            return ("keep_send_syndata", "helpers_stripped")
        return ("helpers_stripped",)

    def wssize_enabled_from_args(self, args_text: str) -> bool:
        lines = _split_arg_lines(args_text)
        if self.engine == "winws2":
            return any(line.strip().lower() == _V2_WSSIZE_LINE for line in lines)

        for idx, line in enumerate(lines):
            lowered = line.lower()
            if lowered == _V1_WSSIZE_COMBINED:
                return True
            if lowered == _V1_WSSIZE_FLAG and idx + 1 < len(lines) and lines[idx + 1].strip() == _V1_WSSIZE_VALUE:
                return True
        return False

    def rewrite_wssize_args(self, args_text: str, enabled: bool) -> str:
        if self.engine == "winws2":
            lines = [line for line in _split_arg_lines(args_text) if line.strip().lower() != _V2_WSSIZE_LINE]
            if enabled and not any(line.strip().lower() == _V2_WSSIZE_LINE for line in lines):
                lines.insert(0, _V2_WSSIZE_LINE)
            return _join_arg_lines(lines)

        lines = _split_arg_lines(args_text)
        cleaned: list[str] = []
        idx = 0
        while idx < len(lines):
            lowered = lines[idx].strip().lower()
            if lowered == _V1_WSSIZE_COMBINED:
                idx += 1
                continue
            if lowered == _V1_WSSIZE_FLAG:
                if idx + 1 < len(lines) and lines[idx + 1].strip() == _V1_WSSIZE_VALUE:
                    idx += 2
                    if idx < len(lines) and lines[idx].strip().lower() == _V1_WSSIZE_CUTOFF:
                        idx += 1
                    continue
            if lowered == _V1_WSSIZE_CUTOFF:
                idx += 1
                continue
            cleaned.append(lines[idx])
            idx += 1

        if enabled and not self.wssize_enabled_from_args(_join_arg_lines(cleaned)):
            cleaned.extend([_V1_WSSIZE_FLAG, _V1_WSSIZE_VALUE, _V1_WSSIZE_CUTOFF])

        return _join_arg_lines(cleaned)


_V1_WSSIZE_FLAG = "--wssize"
_V1_WSSIZE_VALUE = "1:6"
_V1_WSSIZE_COMBINED = "--wssize=1:6"
_V1_WSSIZE_CUTOFF = "--wssize-forced-cutoff=0"
_V2_WSSIZE_LINE = "--lua-desync=wssize:wsize=1:scale=6"


def _split_arg_lines(args_text: str) -> list[str]:
    return [str(raw or "").strip() for raw in str(args_text or "").splitlines() if str(raw or "").strip()]


def _join_arg_lines(lines: list[str]) -> str:
    return "\n".join(str(line or "").strip() for line in lines if str(line or "").strip()).strip()


_ENGINE_ADAPTERS: dict[str, DirectPresetEngineAdapter] = {
    "winws1": DirectPresetEngineAdapter(
        engine="winws1",
        parser_module=winws1_parser,
        classifier_module=winws1_classifier,
        serializer_module=winws1_serializer,
        rules_module=winws1_rules,
    ),
    "winws2": DirectPresetEngineAdapter(
        engine="winws2",
        parser_module=winws2_parser,
        classifier_module=winws2_classifier,
        serializer_module=winws2_serializer,
        rules_module=winws2_rules,
    ),
}


def get_direct_preset_engine_adapter(engine: str) -> DirectPresetEngineAdapter:
    normalized = str(engine or "").strip().lower()
    adapter = _ENGINE_ADAPTERS.get(normalized)
    if adapter is None:
        raise ValueError(f"Unsupported direct preset engine: {engine}")
    return adapter


__all__ = [
    "DirectPresetEngineAdapter",
    "get_direct_preset_engine_adapter",
]
