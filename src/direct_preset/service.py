from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import time as _time
from typing import Any

from core.paths import AppPaths
from log.log import log


from .common.preset_editor import replace_profile_action_lines, replace_profile_selector_line, split_profile_for_target
from .common.projector import build_target_views
from .common.circular_preset_support import (
    editable_raw_args_text,
    is_circular_source_preset,
    normalize_action_lines_for_preset,
    resolve_transport_settings,
)
from direct_preset.adapters import DirectPresetEngineAdapter, get_direct_preset_engine_adapter
from direct_preset.modes import resolve_direct_mode_logic
from .common.source_preset_models import (
    OutRangeSettings,
    PresetTargetDetails,
    SendSettings,
    SourcePreset,
    SyndataSettings,
    TargetContext,
    TargetProfileSnapshot,
)
from .common.strategy_resolution import (
    infer_strategy_id as infer_strategy_id_common,
    normalized_strategy_identities as normalized_strategy_identities_common,
    strategy_lookup_for_candidates as strategy_lookup_for_candidates_common,
)
from direct_preset.catalog_provider import StrategyEntry, load_strategy_catalogs
from .common.target_metadata_service import TargetMetadataService

@dataclass(frozen=True)
class _ResolvedTargetState:
    context: TargetContext
    details: PresetTargetDetails
    raw_action_lines: tuple[str, ...]


@dataclass(frozen=True)
class BasicUiPayload:
    target_views: tuple = ()
    target_items: dict[str, Any] | None = None
    strategy_selections: dict[str, str] | None = None
    strategy_names_by_target: dict[str, dict[str, str]] | None = None
    filter_modes: dict[str, str] | None = None
    selected_preset_file_name: str = ""
    selected_preset_name: str = ""


@dataclass(frozen=True)
class TargetDetailPayload:
    target_key: str
    target_item: Any
    details: PresetTargetDetails
    strategy_entries: dict[str, dict[str, str]]
    raw_args_text: str
    filter_mode: str
    is_circular_preset: bool = False


def _log_startup_payload_metric(scope: str | None, section: str, elapsed_ms: float, *, extra: str | None = None) -> None:
    resolved_scope = str(scope or "").strip()
    if not resolved_scope:
        return
    try:
        rounded = int(round(float(elapsed_ms)))
    except Exception:
        rounded = 0
    suffix = f" ({extra})" if extra else ""
    log(f"⏱ Startup UI Section: {resolved_scope} {section} {rounded}ms{suffix}", "⏱ STARTUP")


class DirectPresetService:
    def __init__(self, paths: AppPaths, engine: str):
        self._paths = paths
        self._engine = str(engine or "").strip().lower()
        self._adapter: DirectPresetEngineAdapter = get_direct_preset_engine_adapter(self._engine)
        self._target_metadata = TargetMetadataService()

    def read_source_preset(self, path: Path) -> SourcePreset:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
        return self._parser().parse(text)

    def write_source_preset(self, path: Path, source: SourcePreset) -> None:
        content = self._serializer().serialize(source)
        Path(path).write_text(content, encoding="utf-8")

    def remove_placeholder_profiles(self, source: SourcePreset) -> bool:
        kept_profiles = [profile for profile in source.profiles if not self._profile_uses_placeholder_unknown(profile)]
        if len(kept_profiles) == len(source.profiles):
            return False
        source.profiles = kept_profiles
        return True

    def repair_out_range_profiles(self, source: SourcePreset) -> list[str]:
        labels: list[str] = []
        seen: set[str] = set()
        contexts = self.collect_target_contexts(source)
        source_is_circular = is_circular_source_preset(source)

        for index, profile in enumerate(list(source.profiles or [])):
            current_action_lines = [str(line).strip() for line in getattr(profile, "action_lines", ()) or () if str(line).strip()]
            normalized_action_lines, fixes, _resolved = normalize_action_lines_for_preset(
                current_action_lines,
                rules_module=self._rules(),
                source_is_circular=source_is_circular,
            )
            if not fixes or normalized_action_lines == current_action_lines:
                continue

            replace_profile_action_lines(source, index, normalized_action_lines)
            label = self._warning_label_for_profile(profile, contexts, index)
            dedupe_key = label.strip().lower()
            if dedupe_key and dedupe_key not in seen:
                seen.add(dedupe_key)
                labels.append(label)

        return labels

    def collect_target_contexts(
        self,
        source: SourcePreset,
        *,
        startup_scope: str | None = None,
    ) -> dict[str, TargetContext]:
        _t_total = _time.perf_counter()
        related_profiles: dict[str, list[TargetProfileSnapshot]] = {}
        canonical_indices: dict[str, int] = {}
        canonical_profiles: dict[str, Any] = {}

        _t_scan_profiles = _time.perf_counter()
        for index, profile in enumerate(source.profiles):
            target_keys = self._classifier().classify(profile)
            profile.canonical_target_keys = tuple(target_keys)
            snapshot = TargetProfileSnapshot(
                profile_index=index,
                protocol_kind=profile.protocol_kind,
                match_lines=tuple(profile.match_lines),
                action_lines=tuple(profile.action_lines),
                target_keys=tuple(target_keys),
            )
            for target_key in target_keys:
                related_profiles.setdefault(target_key, []).append(snapshot)
                canonical_indices.setdefault(target_key, index)
                canonical_profiles.setdefault(target_key, profile)
        _log_startup_payload_metric(
            startup_scope,
            "_build_content.payload.service.collect_target_contexts.scan_profiles",
            (_time.perf_counter() - _t_scan_profiles) * 1000,
            extra=f"profiles={len(source.profiles)}, canonical_targets={len(canonical_indices)}",
        )

        contexts: dict[str, TargetContext] = {}
        _t_build_contexts = _time.perf_counter()
        for target_key, index in canonical_indices.items():
            profile = canonical_profiles[target_key]
            metadata = self._target_metadata.get_metadata(target_key)
            contexts[target_key] = TargetContext(
                target_key=target_key,
                profile_index=index,
                display_name=metadata.display_name,
                protocol_kind=profile.protocol_kind,
                filter_mode=self._detect_filter_mode(profile),
                selector_family=self._selector_family(profile, target_key),
                selector_value=self._selector_value(profile, target_key),
                strategy_candidates=tuple(
                    self._candidate_catalog_names(
                        metadata.strategy_type,
                        profile.protocol_kind,
                    )
                ),
                related_profiles=tuple(related_profiles.get(target_key, [])),
                metadata=metadata,
            )
        _log_startup_payload_metric(
            startup_scope,
            "_build_content.payload.service.collect_target_contexts.build_contexts",
            (_time.perf_counter() - _t_build_contexts) * 1000,
            extra=f"contexts={len(contexts)}",
        )
        _log_startup_payload_metric(
            startup_scope,
            "_build_content.payload.service.collect_target_contexts.total",
            (_time.perf_counter() - _t_total) * 1000,
            extra=f"contexts={len(contexts)}",
        )
        return contexts

    def build_target_views(self, source: SourcePreset):
        contexts = {
            key: ctx
            for key, ctx in self.collect_target_contexts(source).items()
            if self._target_metadata.should_include_in_basic_ui(key)
        }
        return build_target_views(contexts)

    def build_basic_ui_payload(
        self,
        source: SourcePreset,
        *,
        startup_scope: str | None = None,
        direct_mode: str | None = None,
    ) -> BasicUiPayload:
        _t_total = _time.perf_counter()
        contexts = self.collect_target_contexts(source, startup_scope=startup_scope)

        _t_basic_contexts = _time.perf_counter()
        basic_contexts = {
            key: ctx
            for key, ctx in contexts.items()
            if self._target_metadata.should_include_in_basic_ui(key)
        }
        _log_startup_payload_metric(
            startup_scope,
            "_build_content.payload.service.basic_contexts",
            (_time.perf_counter() - _t_basic_contexts) * 1000,
            extra=f"contexts={len(contexts)}, basic_contexts={len(basic_contexts)}",
        )

        _t_target_views = _time.perf_counter()
        target_views = tuple(build_target_views(basic_contexts))
        _log_startup_payload_metric(
            startup_scope,
            "_build_content.payload.service.target_views",
            (_time.perf_counter() - _t_target_views) * 1000,
            extra=f"target_views={len(target_views)}",
        )

        _t_target_items = _time.perf_counter()
        target_items = {
            key: self._target_metadata.build_ui_item(key)
            for key in basic_contexts
        }
        _log_startup_payload_metric(
            startup_scope,
            "_build_content.payload.service.target_items",
            (_time.perf_counter() - _t_target_items) * 1000,
            extra=f"target_items={len(target_items)}",
        )

        catalogs = self._strategy_catalogs()
        _t_strategy_names = _time.perf_counter()
        strategy_names_by_target: dict[str, dict[str, str]] = {}
        strategy_names_cache: dict[tuple[str, ...], dict[str, str]] = {}
        for key, ctx in basic_contexts.items():
            candidates_key = tuple(ctx.strategy_candidates)
            names = strategy_names_cache.get(candidates_key)
            if names is None:
                names = {
                    strategy_id: str(entry.get("name") or strategy_id)
                    for strategy_id, entry in self._strategy_entries_from_candidates(
                        candidates_key,
                        catalogs=catalogs,
                    ).items()
                }
                strategy_names_cache[candidates_key] = names
            strategy_names_by_target[key] = dict(names)
        _log_startup_payload_metric(
            startup_scope,
            "_build_content.payload.service.strategy_name_maps",
            (_time.perf_counter() - _t_strategy_names) * 1000,
            extra=f"targets={len(strategy_names_by_target)}, variants={len(strategy_names_cache)}",
        )

        _t_strategy_selections = _time.perf_counter()
        strategy_selections: dict[str, str] = {}
        strategy_lookup_cache: dict[tuple[str, ...], dict[str, str]] = {}
        current_strategy_cache: dict[tuple[int, tuple[str, ...]], str] = {}
        for key, ctx in basic_contexts.items():
            profile_key = (int(ctx.profile_index), tuple(ctx.strategy_candidates))
            current_strategy = current_strategy_cache.get(profile_key)
            if current_strategy is None:
                current_strategy = self._resolve_current_strategy_from_context(
                    source,
                    ctx,
                    direct_mode=direct_mode,
                    catalogs=catalogs,
                    strategy_lookup_cache=strategy_lookup_cache,
                )
                current_strategy_cache[profile_key] = current_strategy
            strategy_selections[key] = current_strategy
        _log_startup_payload_metric(
            startup_scope,
            "_build_content.payload.service.strategy_selections",
            (_time.perf_counter() - _t_strategy_selections) * 1000,
            extra=(
                f"targets={len(strategy_selections)}, "
                f"unique_profiles={len(current_strategy_cache)}, "
                f"variants={len(strategy_lookup_cache)}"
            ),
        )

        _t_filter_modes = _time.perf_counter()
        filter_modes = {
            key: ctx.filter_mode
            for key, ctx in basic_contexts.items()
        }
        _log_startup_payload_metric(
            startup_scope,
            "_build_content.payload.service.filter_modes",
            (_time.perf_counter() - _t_filter_modes) * 1000,
            extra=f"targets={len(filter_modes)}",
        )
        _log_startup_payload_metric(
            startup_scope,
            "_build_content.payload.service.total",
            (_time.perf_counter() - _t_total) * 1000,
            extra=f"targets={len(target_items)}",
        )
        return BasicUiPayload(
            target_views=target_views,
            target_items=target_items,
            strategy_selections=strategy_selections,
            strategy_names_by_target=strategy_names_by_target,
            filter_modes=filter_modes,
        )

    def build_ui_items(self, source: SourcePreset) -> dict[str, Any]:
        items: dict[str, Any] = {}
        for target_key in self.collect_target_contexts(source):
            if not self._target_metadata.should_include_in_basic_ui(target_key):
                continue
            items[target_key] = self._target_metadata.build_ui_item(target_key)
        return items

    def build_target_detail_payload(
        self,
        source: SourcePreset,
        target_key: str,
        *,
        direct_mode: str | None = None,
    ) -> TargetDetailPayload | None:
        normalized_key = str(target_key or "").strip().lower()
        if not normalized_key:
            return None
        contexts = self.collect_target_contexts(source)
        ctx = contexts.get(normalized_key)
        if ctx is None:
            return None
        state = self._resolve_target_state_from_context(source, ctx, direct_mode=direct_mode)
        if state is None:
            return None
        catalogs = self._strategy_catalogs()
        source_is_circular = is_circular_source_preset(source)
        return TargetDetailPayload(
            target_key=normalized_key,
            target_item=self._target_metadata.build_ui_item(normalized_key),
            details=state.details,
            strategy_entries=self._strategy_entries_from_candidates(ctx.strategy_candidates, catalogs=catalogs),
            raw_args_text=editable_raw_args_text(
                list(state.raw_action_lines),
                rules_module=self._rules(),
                source_is_circular=source_is_circular,
            ),
            filter_mode=ctx.filter_mode,
            is_circular_preset=source_is_circular,
        )

    def get_target_details(
        self,
        source: SourcePreset,
        target_key: str,
        *,
        direct_mode: str | None = None,
    ) -> PresetTargetDetails | None:
        state = self._resolve_target_state(source, target_key, direct_mode=direct_mode)
        if state is None:
            return None
        return state.details

    def get_strategy_selections(self, source: SourcePreset, *, direct_mode: str | None = None) -> dict[str, str]:
        out: dict[str, str] = {}
        for target_key in self.collect_target_contexts(source):
            details = self.get_target_details(source, target_key, direct_mode=direct_mode)
            out[target_key] = details.current_strategy if details else "none"
        return out

    def _get_filter_mode(self, source: SourcePreset, target_key: str) -> str:
        ctx = self.collect_target_contexts(source).get(str(target_key or "").strip().lower())
        return ctx.filter_mode if ctx else "hostlist"

    def _update_filter_mode(self, source: SourcePreset, target_key: str, filter_mode: str) -> bool:
        normalized_key = str(target_key or "").strip().lower()
        normalized_mode = str(filter_mode or "").strip().lower()
        if normalized_mode not in ("hostlist", "ipset"):
            return False
        contexts = self.collect_target_contexts(source)
        ctx = contexts.get(normalized_key)
        if ctx is None:
            return False
        profile_index = split_profile_for_target(source, ctx.profile_index, normalized_key)
        base_key = self._target_metadata.base_key_from_target_key(normalized_key)
        new_line = f"--{normalized_mode}=lists/{'ipset-' if normalized_mode == 'ipset' else ''}{base_key}.txt"
        replace_profile_selector_line(source, profile_index, normalized_key, new_line, normalized_mode)
        return True

    def update_strategy_selection(
        self,
        source: SourcePreset,
        target_key: str,
        strategy_id: str,
        *,
        direct_mode: str | None = None,
    ) -> bool:
        if is_circular_source_preset(source):
            return False
        normalized_key = str(target_key or "").strip().lower()
        contexts = self.collect_target_contexts(source)
        ctx = contexts.get(normalized_key)
        if ctx is None:
            return False
        profile_index = split_profile_for_target(source, ctx.profile_index, normalized_key)
        requested_strategy_id = str(strategy_id or "").strip() or "none"
        if requested_strategy_id == "none":
            try:
                source.profiles.pop(profile_index)
            except Exception:
                return False
            return True
        details = self.get_target_details(source, normalized_key, direct_mode=direct_mode) or PresetTargetDetails(
            target_key=normalized_key,
            display_name=ctx.display_name,
            current_strategy="none",
            out_range_settings=OutRangeSettings(),
            send_settings=SendSettings(),
            syndata_settings=SyndataSettings(),
        )
        strategy_args = self._strategy_args_by_id(requested_strategy_id, ctx.strategy_candidates)
        mode_logic = self._resolve_mode_logic(direct_mode)
        if mode_logic is None:
            action_lines = self._rules().compose_action_lines(
                strategy_args,
                details.out_range_settings,
                details.send_settings,
                details.syndata_settings,
            )
        else:
            action_lines = mode_logic.compose_action_lines_for_strategy_selection(
                strategy_args=strategy_args,
                details=details,
                rules_module=self._rules(),
            )
        replace_profile_action_lines(source, profile_index, action_lines)
        return True

    def _update_raw_args(self, source: SourcePreset, target_key: str, raw_args: str) -> bool:
        normalized_key = str(target_key or "").strip().lower()
        contexts = self.collect_target_contexts(source)
        ctx = contexts.get(normalized_key)
        if ctx is None:
            return False
        profile_index = split_profile_for_target(source, ctx.profile_index, normalized_key)
        action_lines = [line.strip() for line in str(raw_args or "").splitlines() if line.strip()]
        replace_profile_action_lines(source, profile_index, action_lines)
        return True

    def _get_raw_args(self, source: SourcePreset, target_key: str) -> str:
        state = self._resolve_target_state(source, target_key)
        if state is None:
            return ""
        return editable_raw_args_text(
            list(state.raw_action_lines),
            rules_module=self._rules(),
            source_is_circular=is_circular_source_preset(source),
        )

    def update_syndata(self, source: SourcePreset, target_key: str, syndata: SyndataSettings) -> bool:
        if is_circular_source_preset(source):
            return False
        normalized_key = str(target_key or "").strip().lower()
        state = self._resolve_target_state(source, normalized_key)
        if state is None:
            return False
        profile_index = split_profile_for_target(source, state.context.profile_index, normalized_key)
        action_lines = self._rules().compose_action_lines(
            self._rules().strip_helper_lines(list(state.raw_action_lines)),
            state.details.out_range_settings,
            state.details.send_settings,
            syndata,
        )
        replace_profile_action_lines(source, profile_index, action_lines)
        return True

    def update_target_settings(
        self,
        source: SourcePreset,
        target_key: str,
        *,
        out_range: OutRangeSettings | None = None,
        send: SendSettings | None = None,
        syndata: SyndataSettings | None = None,
    ) -> bool:
        if is_circular_source_preset(source):
            return False
        normalized_key = str(target_key or "").strip().lower()
        state = self._resolve_target_state(source, normalized_key)
        if state is None:
            return False
        profile_index = split_profile_for_target(source, state.context.profile_index, normalized_key)
        action_lines = self._rules().compose_action_lines(
            self._rules().strip_helper_lines(list(state.raw_action_lines)),
            out_range or state.details.out_range_settings,
            send or state.details.send_settings,
            syndata or state.details.syndata_settings,
        )
        replace_profile_action_lines(source, profile_index, action_lines)
        return True

    def reset_target_from_template(self, current: SourcePreset, template: SourcePreset, target_key: str) -> bool:
        template_state = self._resolve_target_state(template, target_key)
        if template_state is None:
            return False
        normalized_key = str(target_key or "").strip().lower()
        current_ctx = self.collect_target_contexts(current).get(normalized_key)
        if current_ctx is None:
            return False
        profile_index = split_profile_for_target(current, current_ctx.profile_index, normalized_key)
        replace_profile_action_lines(current, profile_index, list(template_state.raw_action_lines))
        if template_state.context.filter_mode != current_ctx.filter_mode:
            self._update_filter_mode(current, normalized_key, template_state.context.filter_mode)
        return True

    def target_info(self, source: SourcePreset, target_key: str):
        contexts = self.collect_target_contexts(source)
        if target_key not in contexts:
            return None
        return self._target_metadata.build_ui_item(target_key)

    def get_strategy_entries(self, source: SourcePreset, target_key: str) -> dict[str, dict[str, str]]:
        contexts = self.collect_target_contexts(source)
        ctx = contexts.get(str(target_key or "").strip().lower())
        if ctx is None:
            return {}
        return self._strategy_entries_from_candidates(ctx.strategy_candidates)

    def collect_missing_out_range_warning_labels(self, source: SourcePreset) -> list[str]:
        labels: list[str] = []
        seen: set[str] = set()
        contexts = self.collect_target_contexts(source)

        for index, profile in enumerate(source.profiles):
            action_lines = [str(line).strip() for line in getattr(profile, "action_lines", ()) or () if str(line).strip()]
            if not action_lines:
                continue
            if self._profile_has_explicit_out_range(profile):
                continue

            label = self._warning_label_for_profile(profile, contexts, index)
            dedupe_key = label.strip().lower()
            if not dedupe_key or dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            labels.append(label)

        return labels

    def collect_out_range_autofix_warning_labels(self, source: SourcePreset) -> list[str]:
        labels: list[str] = []
        seen: set[str] = set()
        contexts = self.collect_target_contexts(source)
        source_is_circular = is_circular_source_preset(source)

        for index, profile in enumerate(source.profiles):
            current_action_lines = [str(line).strip() for line in getattr(profile, "action_lines", ()) or () if str(line).strip()]
            if not current_action_lines:
                continue
            _normalized, fixes, _resolved = normalize_action_lines_for_preset(
                current_action_lines,
                rules_module=self._rules(),
                source_is_circular=source_is_circular,
            )
            if not fixes:
                continue
            label = self._warning_label_for_profile(profile, contexts, index)
            dedupe_key = label.strip().lower()
            if not dedupe_key or dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            labels.append(label)

        return labels

    def _target_occurrence_count(self, source: SourcePreset, target_key: str) -> int:
        count = 0
        for profile in source.profiles:
            if target_key in profile.canonical_target_keys:
                count += 1
        return count

    def _resolve_target_state(
        self,
        source: SourcePreset,
        target_key: str,
        *,
        direct_mode: str | None = None,
    ) -> _ResolvedTargetState | None:
        normalized_key = str(target_key or "").strip().lower()
        contexts = self.collect_target_contexts(source)
        ctx = contexts.get(normalized_key)
        if ctx is None:
            return None
        return self._resolve_target_state_from_context(source, ctx, direct_mode=direct_mode)

    def _resolve_target_state_from_context(
        self,
        source: SourcePreset,
        ctx: TargetContext,
        *,
        direct_mode: str | None = None,
    ) -> _ResolvedTargetState | None:
        try:
            profile = source.profiles[ctx.profile_index]
        except Exception:
            return None

        strategy_id = self._infer_strategy_id(
            profile.action_lines,
            ctx.strategy_candidates,
            direct_mode=direct_mode,
            match_lines=profile.match_lines,
        )
        out_range, send, syndata = resolve_transport_settings(
            profile.action_lines,
            rules_module=self._rules(),
            source_is_circular=is_circular_source_preset(source),
        )

        warnings: list[str] = []
        if len(ctx.related_profiles) > 1:
            warnings.append("target appears in multiple profiles; UI edits affect only the first profile")

        details = PresetTargetDetails(
            target_key=ctx.target_key,
            display_name=ctx.display_name,
            current_strategy=strategy_id,
            out_range_settings=out_range,
            send_settings=send,
            syndata_settings=syndata,
            warnings=tuple(warnings),
        )
        return _ResolvedTargetState(
            context=ctx,
            details=details,
            raw_action_lines=tuple(profile.action_lines),
        )

    def _resolve_current_strategy_from_context(
        self,
        source: SourcePreset,
        ctx: TargetContext,
        *,
        direct_mode: str | None = None,
        catalogs: dict[str, dict[str, StrategyEntry]] | None = None,
        strategy_lookup_cache: dict[tuple[tuple[str, ...], str], dict[str, str]] | None = None,
    ) -> str:
        try:
            profile = source.profiles[ctx.profile_index]
        except Exception:
            return "none"
        return self._infer_strategy_id(
            profile.action_lines,
            ctx.strategy_candidates,
            direct_mode=direct_mode,
            match_lines=profile.match_lines,
            catalogs=catalogs,
            strategy_lookup_cache=strategy_lookup_cache,
        )

    def _candidate_catalog_names(self, strategy_type: str, protocol_kind: str) -> tuple[str, ...]:
        return self._adapter.candidate_catalog_names(strategy_type, protocol_kind)

    def _strategy_catalogs(self) -> dict[str, dict[str, StrategyEntry]]:
        return load_strategy_catalogs(self._paths, self._engine)

    def _resolve_mode_logic(self, direct_mode: str | None):
        return resolve_direct_mode_logic(self._engine, direct_mode or "")

    def _strategy_entries_from_candidates(
        self,
        candidates: tuple[str, ...] | list[str],
        *,
        catalogs: dict[str, dict[str, StrategyEntry]] | None = None,
    ) -> dict[str, dict[str, str]]:
        resolved_catalogs = catalogs or self._strategy_catalogs()
        entries: dict[str, dict[str, str]] = {}
        for catalog_name in tuple(candidates or ()):
            for entry in resolved_catalogs.get(catalog_name, {}).values():
                entries.setdefault(
                    entry.strategy_id,
                    {
                        "id": entry.strategy_id,
                        "name": entry.name,
                        "args": entry.args,
                    },
                )
        return entries

    def _strategy_args_by_id(self, strategy_id: str, candidates: tuple[str, ...]) -> list[str]:
        sid = str(strategy_id or "").strip()
        if not sid or sid == "none":
            return []
        for name in candidates:
            entry = self._strategy_catalogs().get(name, {}).get(sid)
            if entry is not None:
                return [line.strip() for line in entry.args.splitlines() if line.strip()]
        return []

    def _infer_strategy_id(
        self,
        action_lines: list[str],
        candidates: tuple[str, ...],
        *,
        direct_mode: str | None = None,
        match_lines: list[str] | tuple[str, ...] | None = None,
        catalogs: dict[str, dict[str, StrategyEntry]] | None = None,
        strategy_lookup_cache: dict[tuple[tuple[str, ...], str], dict[str, str]] | None = None,
    ) -> str:
        return infer_strategy_id_common(
            action_lines=action_lines,
            candidates=candidates,
            direct_mode=direct_mode,
            match_lines=match_lines,
            catalogs=catalogs or self._strategy_catalogs(),
            strategy_lookup_cache=strategy_lookup_cache,
            identities_fn=lambda lines, mode, matches, names: self._normalized_strategy_identities(
                lines,
                direct_mode=mode,
                match_lines=matches,
                candidates=names,
            ),
        )

    def _strategy_lookup_for_candidates(
        self,
        candidates: tuple[str, ...],
        *,
        direct_mode: str | None = None,
        catalogs: dict[str, dict[str, StrategyEntry]] | None = None,
        strategy_lookup_cache: dict[tuple[tuple[str, ...], str], dict[str, str]] | None = None,
    ) -> dict[str, str]:
        return strategy_lookup_for_candidates_common(
            candidates=candidates,
            direct_mode=direct_mode,
            catalogs=catalogs or self._strategy_catalogs(),
            strategy_lookup_cache=strategy_lookup_cache,
            identities_fn=lambda lines, mode, matches, names: self._normalized_strategy_identities(
                lines,
                direct_mode=mode,
                match_lines=matches,
                candidates=names,
            ),
        )

    def _normalized_strategy_identities(
        self,
        action_lines: list[str] | tuple[str, ...],
        *,
        direct_mode: str | None = None,
        match_lines: list[str] | tuple[str, ...] | None = None,
        candidates: tuple[str, ...] | list[str] | None = None,
    ) -> tuple[str, ...]:
        return normalized_strategy_identities_common(
            action_lines=action_lines,
            direct_mode=direct_mode,
            match_lines=match_lines,
            candidates=candidates,
            resolve_mode_logic_fn=self._resolve_mode_logic,
            rules_module=self._rules(),
        )

    @staticmethod
    def _detect_filter_mode(profile) -> str:
        for line in profile.match_lines:
            lowered = line.strip().lower()
            if lowered.startswith("--ipset="):
                return "ipset"
            if lowered.startswith("--hostlist="):
                return "hostlist"
        return "hostlist"

    @staticmethod
    def _selector_family(profile, target_key: str) -> str:
        for segment in profile.segments:
            if target_key in segment.target_keys and segment.selector_is_positive:
                return segment.selector_family
        return ""

    @staticmethod
    def _selector_value(profile, target_key: str) -> str:
        for segment in profile.segments:
            if target_key in segment.target_keys and segment.selector_is_positive:
                return segment.selector_value
        return ""

    def _parser(self):
        return self._adapter.parser_module

    def _classifier(self):
        return self._adapter.classifier_module

    def _serializer(self):
        return self._adapter.serializer_module

    def _rules(self):
        return self._adapter.rules_module

    @staticmethod
    def _profile_uses_placeholder_unknown(profile) -> bool:
        for segment in getattr(profile, "segments", ()) or ():
            if getattr(segment, "kind", "") != "match":
                continue
            family = str(getattr(segment, "selector_family", "") or "").strip().lower()
            if family not in {"hostlist", "ipset"}:
                continue
            value = str(getattr(segment, "selector_value", "") or "").strip().lower().replace("\\", "/")
            if value.endswith("/unknown.txt") or value == "lists/unknown.txt":
                return True
            if value.endswith("/ipset-unknown.txt") or value == "lists/ipset-unknown.txt":
                return True
        return False

    @staticmethod
    def _profile_has_explicit_out_range(profile) -> bool:
        for line in getattr(profile, "action_lines", ()) or ():
            lowered = str(line or "").strip().lower()
            if lowered.startswith("--out-range="):
                return True
            if ":out_range=" in lowered:
                return True
        return False

    def _warning_label_for_profile(self, profile, contexts: dict[str, TargetContext], profile_index: int) -> str:
        target_keys = tuple(getattr(profile, "canonical_target_keys", ()) or ())
        if target_keys:
            first_key = target_keys[0]
            ctx = contexts.get(first_key)
            if ctx is not None:
                proto = str(ctx.protocol_kind or "tcp").strip().lower() or "tcp"
                return f"{ctx.target_key}/{proto}"

        for segment in getattr(profile, "segments", ()) or ():
            if getattr(segment, "kind", "") != "match":
                continue
            family = str(getattr(segment, "selector_family", "") or "").strip().lower()
            value = str(getattr(segment, "selector_value", "") or "").strip()
            if family in {"hostlist", "ipset"} and value:
                return f"{value}/{getattr(profile, 'protocol_kind', 'tcp') or 'tcp'}"

        proto = str(getattr(profile, "protocol_kind", "") or "tcp").strip().lower() or "tcp"
        return f"profile{profile_index + 1}/{proto}"
