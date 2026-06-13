from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
from typing import Any
import threading
import time

from log.log import log
from presets.cache_signatures import path_cache_signature
from settings.mode import DEFAULT_LAUNCH_METHOD, ENGINE_WINWS2, PRESET_LAUNCH_METHODS, engine_for_launch_method, normalize_launch_method

from .match_filters import ports_label_from_match_lines, protocol_label_from_match_lines, strategy_catalog_from_match_lines
from .folders import (
    load_profile_folder_state,
    move_profile_after_in_folder_state,
    move_profile_before_in_folder_state,
    move_profile_to_end_in_folder_state,
    move_profile_to_folder_in_folder_state,
    profile_folder_collapsed,
    profile_folder_for_profile,
)
from .list_interpreter import build_profile_list_sources
from .key_resolution import (
    PresetProfileMoveResult,
    build_preset_profile_key_map,
    find_profile_list_source,
    resolve_preset_profile_reference_index,
    resolve_preset_profile_row_index,
)
from .list_file_editor import (
    count_profile_list_entries,
    profile_list_file_exists,
    profile_list_file_reference,
    read_profile_list_file_text_parts,
    validate_profile_list_file_text,
    write_profile_list_file_text,
)
from .models import EngineName, Preset, Profile, ProfileSegment
from .normalizer import normalize_preset_profiles
from .parser import parse_preset_text
from .serializer import (
    append_profile_from_template,
    serialize_preset,
    with_profile_deleted,
    with_profile_duplicated,
    with_profile_enabled,
    with_profile_moved,
    with_profile_raw_text,
    with_profile_strategy_lines,
    with_profile_user_match,
)
from .setup_match_text import build_profile_setup_match_tab_text
from .strategy_state import ProfileStrategyState, ProfileStrategyStateStore
from .strategy_catalog import StrategyEntry, load_strategy_catalogs
from .state import (
    ProfileListFileEditorState,
    ProfileListItem,
    ProfileListPayload,
    ProfileSetupPayload,
    ProfileStrategyBranch,
    StrategyApplyResult,
)
from .template_library import load_profile_template_library
from .user_profiles import create_user_profile, delete_user_profile, update_user_profile
from .editable_settings import (
    EditableProfileSettings,
    normalize_filter_value,
    read_editable_profile_settings,
    with_editable_profile,
    with_editable_profile_settings,
)


PROFILE_LIST_PAYLOAD_CACHE_LIMIT = 24
PROFILE_SETUP_PAYLOAD_CACHE_LIMIT = 128
PROFILE_TIMING_LOG_LEVEL = "⏱ PROFILE"
PROFILE_VISIBLE_TIMING_LABELS = frozenset(
    {
        "profile_feature.folder_state.load",
        "profile_feature.list_profiles.cached",
        "profile_feature.list_profiles.total",
        "profile_feature.profile_list_item.build",
        "profile_feature.profiles.normalize",
        "profile_feature.selected_preset.parse",
        "profile_feature.selected_preset.read",
        "profile_feature.sources.build",
        "profile_feature.strategy_catalogs.load",
        "profile_feature.templates.load",
    }
)


@dataclass(slots=True)
class _SelectedPresetSnapshot:
    revision: tuple[object, ...]
    preset: Preset
    manifest: object


class ProfilePresetService:
    def __init__(self, profile_services, launch_method: str = DEFAULT_LAUNCH_METHOD) -> None:
        self._profile_services = profile_services
        self._presets = profile_services._presets_feature
        self._app_paths = profile_services._app_paths
        self._launch_method = normalize_launch_method(launch_method)
        self._engine = _engine_for_method(self._launch_method)
        self._state_store = ProfileStrategyStateStore()
        self._selected_preset_snapshot: _SelectedPresetSnapshot | None = None
        self._profile_list_snapshot: ProfileListPayload | None = None
        self._profile_list_snapshot_revision: tuple[object, ...] | None = None
        self._profile_list_snapshots_by_revision: OrderedDict[
            tuple[object, ...],
            ProfileListPayload,
        ] = OrderedDict()
        self._profile_setup_payload_cache: OrderedDict[
            tuple[object, ...],
            ProfileSetupPayload | None,
        ] = OrderedDict()
        self._profile_list_lock = threading.RLock()

    @property
    def engine(self) -> EngineName:
        return self._engine

    def load_selected_preset(self) -> tuple[Preset, object]:
        revision, manifest, source_text = self._selected_preset_revision()
        return self._load_selected_preset_for_revision(revision, manifest, source_text)

    def _load_selected_preset_for_revision(
        self,
        revision: tuple[object, ...],
        manifest: object,
        source_text: str | None,
    ) -> tuple[Preset, object]:
        snapshot = self._selected_preset_snapshot
        if snapshot is not None and snapshot.revision == revision:
            return snapshot.preset, snapshot.manifest

        read_started_at = time.perf_counter()
        if source_text is None:
            source_text, manifest = self._presets.read_selected_preset_source(self._launch_method)
        self._log_timing("profile_feature.selected_preset.read", read_started_at)

        parse_started_at = time.perf_counter()
        preset = parse_preset_text(source_text, engine=self._engine, source_name=manifest.file_name)
        self._log_timing("profile_feature.selected_preset.parse", parse_started_at)

        snapshot = _SelectedPresetSnapshot(
            revision=revision,
            preset=preset,
            manifest=manifest,
        )
        self._selected_preset_snapshot = snapshot
        return snapshot.preset, snapshot.manifest

    def save_selected_preset(self, preset: Preset) -> None:
        source_text = serialize_preset(preset)
        snapshot = self._selected_preset_snapshot
        if snapshot is not None and serialize_preset(snapshot.preset) == source_text:
            return
        self._presets.save_selected_preset_source(self._launch_method, source_text)
        self._invalidate_selected_preset_snapshot()

    def list_profiles(self) -> ProfileListPayload:
        with self._profile_list_lock:
            return self._list_profiles_locked()

    def get_cached_profile_list(self) -> ProfileListPayload | None:
        lock_acquired = self._profile_list_lock.acquire(blocking=False)
        if not lock_acquired:
            return None
        try:
            snapshot = self._profile_list_snapshot
            if snapshot is None and not self._profile_list_snapshots_by_revision:
                return None
            try:
                list_revision = self._current_profile_list_revision()
            except Exception as exc:
                log(f"profile_feature.list_profiles.cache_check_failed: {exc}", "DEBUG")
                return None
            revision_snapshot = self._profile_list_snapshots_by_revision.get(list_revision)
            if revision_snapshot is not None:
                self._profile_list_snapshots_by_revision.move_to_end(list_revision)
                self._profile_list_snapshot = revision_snapshot
                self._profile_list_snapshot_revision = list_revision
                return revision_snapshot
            if snapshot is None or self._profile_list_snapshot_revision is None:
                return None
            if self._profile_list_snapshot_revision != list_revision:
                return None
            return snapshot
        finally:
            self._profile_list_lock.release()

    def peek_cached_profile_list(self) -> ProfileListPayload | None:
        lock_acquired = self._profile_list_lock.acquire(blocking=False)
        if not lock_acquired:
            return None
        try:
            return self._profile_list_snapshot
        finally:
            self._profile_list_lock.release()

    def list_preset_order_profiles(self) -> ProfileListPayload:
        preset, manifest = self.load_selected_preset()
        catalogs = load_strategy_catalogs(self._app_paths, self._engine)
        items = [
            self._item_for_profile(
                profile,
                catalogs=catalogs,
                in_preset=True,
                key=profile.key,
                order=profile.index,
            )
            for profile in tuple(preset.profiles)
        ]
        items.sort(key=lambda item: int(getattr(item, "profile_index", 0) or 0))
        return ProfileListPayload(
            items=tuple(items),
            selected_preset_file_name=str(getattr(manifest, "file_name", "") or ""),
            selected_preset_name=str(getattr(manifest, "name", "") or ""),
        )

    def _current_profile_list_revision(self) -> tuple[object, ...]:
        preset_revision, _manifest, _source_text = self._selected_preset_revision()
        folder_state_started_at = time.perf_counter()
        folder_state = load_profile_folder_state()
        self._log_timing("profile_feature.folder_state.load", folder_state_started_at)
        return (*preset_revision, ("profile_folders", _profile_folder_state_revision(folder_state)))

    def _list_profiles_locked(self) -> ProfileListPayload:
        total_started_at = time.perf_counter()
        preset_revision, manifest, source_text = self._selected_preset_revision()
        folder_state_started_at = time.perf_counter()
        folder_state = load_profile_folder_state()
        self._log_timing("profile_feature.folder_state.load", folder_state_started_at)
        list_revision = (*preset_revision, ("profile_folders", _profile_folder_state_revision(folder_state)))
        snapshot = self._profile_list_snapshot
        if snapshot is not None and self._profile_list_snapshot_revision == list_revision:
            self._log_timing("profile_feature.list_profiles.cached", total_started_at)
            return snapshot
        revision_snapshot = self._profile_list_snapshots_by_revision.get(list_revision)
        if revision_snapshot is not None:
            self._profile_list_snapshots_by_revision.move_to_end(list_revision)
            self._profile_list_snapshot = revision_snapshot
            self._profile_list_snapshot_revision = list_revision
            self._log_timing("profile_feature.list_profiles.cached", total_started_at)
            return revision_snapshot

        preset, manifest = self._load_selected_preset_for_revision(preset_revision, manifest, source_text)
        normalize_started_at = time.perf_counter()
        normalization = normalize_preset_profiles(preset)
        self._log_timing("profile_feature.profiles.normalize", normalize_started_at)
        if normalization.changed:
            preset = normalization.preset
            self.save_selected_preset(preset)

        catalogs_started_at = time.perf_counter()
        catalogs = load_strategy_catalogs(self._app_paths, self._engine)
        self._log_timing("profile_feature.strategy_catalogs.load", catalogs_started_at)

        templates_started_at = time.perf_counter()
        templates = self._load_profile_templates()
        self._log_timing("profile_feature.templates.load", templates_started_at)

        items: list[ProfileListItem] = []

        sources_started_at = time.perf_counter()
        sources = build_profile_list_sources(tuple(preset.profiles), templates)
        self._log_timing("profile_feature.sources.build", sources_started_at)

        items_started_at = time.perf_counter()
        for index, source in enumerate(sources):
            self._yield_profile_payload_worker(index)
            item = self._item_for_profile(
                source.profile,
                catalogs=catalogs,
                in_preset=source.in_preset,
                key=source.key,
                order=source.order,
                folder_state=folder_state,
                user_template_key=getattr(source, "user_template_key", ""),
                display_name_override=getattr(source, "display_name_override", ""),
            )
            items.append(item)
        self._log_timing("profile_feature.profile_list_item.build", items_started_at)

        payload = ProfileListPayload(
            items=tuple(items),
            selected_preset_file_name=str(getattr(manifest, "file_name", "") or ""),
            selected_preset_name=str(getattr(manifest, "name", "") or ""),
            normalized_split_profiles=normalization.split_profile_count,
            normalized_created_profiles=normalization.created_profile_count,
        )
        self._profile_list_snapshot = payload
        self._profile_list_snapshot_revision = list_revision
        self._remember_profile_list_snapshot(list_revision, payload)
        self._log_timing("profile_feature.list_profiles.total", total_started_at)
        return payload

    def _remember_profile_list_snapshot(self, revision: tuple[object, ...], payload: ProfileListPayload) -> None:
        self._profile_list_snapshots_by_revision[revision] = payload
        self._profile_list_snapshots_by_revision.move_to_end(revision)
        limit = max(1, int(PROFILE_LIST_PAYLOAD_CACHE_LIMIT))
        while len(self._profile_list_snapshots_by_revision) > limit:
            self._profile_list_snapshots_by_revision.popitem(last=False)

    @staticmethod
    def _yield_profile_payload_worker(index: int) -> None:
        if index > 0 and index % 64 == 0:
            time.sleep(0)

    def count_enabled_profiles(self) -> int:
        preset, _manifest = self.load_selected_preset()
        return sum(1 for profile in preset.profiles if bool(getattr(profile, "enabled", False)))

    def get_profile_strategy_display_state(self, max_items: int = 2):
        from presets.display_state import ProfileStrategyDisplayState

        payload = self._profile_list_snapshot
        if payload is None:
            return ProfileStrategyDisplayState(summary="Профили", active_count=0)
        current_file_name = self._current_selected_preset_file_name()
        payload_file_name = str(getattr(payload, "selected_preset_file_name", "") or "").strip()
        if current_file_name and payload_file_name and current_file_name != payload_file_name:
            return ProfileStrategyDisplayState(summary="Профили", active_count=0)

        active_names = [
            item.display_name
            for item in payload.items
            if item.in_preset and item.enabled and item.strategy_id != "none"
        ]
        if not active_names:
            return ProfileStrategyDisplayState(summary="Не выбрана", active_count=0)
        if len(active_names) <= max_items:
            return ProfileStrategyDisplayState(
                summary=" • ".join(active_names),
                active_count=len(active_names),
            )
        return ProfileStrategyDisplayState(
            summary=" • ".join(active_names[:max_items]) + f" +{len(active_names) - max_items} ещё",
            active_count=len(active_names),
        )

    def get_enabled_profile_count_snapshot(self) -> int | None:
        details = self.get_profile_selection_details()
        if not details:
            return None
        return int(details.get("enabled_profile_count") or 0)

    def get_profile_selection_details(self, *, selected_profile_key: str = "", max_items: int = 2) -> dict[str, Any]:
        payload = self._profile_list_snapshot
        if payload is None:
            return {}
        current_file_name = self._current_selected_preset_file_name()
        payload_file_name = str(getattr(payload, "selected_preset_file_name", "") or "").strip()
        if current_file_name and payload_file_name and current_file_name != payload_file_name:
            return {}

        profile_items = [item for item in payload.items if item.in_preset]
        enabled_items = [item for item in profile_items if item.enabled]
        active_items = [item for item in enabled_items if item.strategy_id != "none"]

        selected_key = str(selected_profile_key or "").strip()
        if selected_key:
            for item in payload.items:
                if selected_key in {str(item.key or ""), str(item.persistent_key or "")}:
                    return {
                        "summary": str(item.strategy_name or item.display_name or "").strip(),
                        "selected_profile_name": str(item.display_name or "").strip(),
                        "profile_count": 1 if item.in_preset else 0,
                        "enabled_profile_count": 1 if item.in_preset and item.enabled else 0,
                        "active_strategy_count": 1 if item.in_preset and item.enabled and item.strategy_id != "none" else 0,
                    }

        active_names = [str(item.strategy_name or item.display_name or "").strip() for item in active_items]
        active_names = [name for name in active_names if name]
        if not active_names:
            summary = ""
        elif len(active_names) <= max_items:
            summary = " • ".join(active_names)
        else:
            summary = " • ".join(active_names[:max_items]) + f" +{len(active_names) - max_items} ещё"
        return {
            "summary": summary,
            "selected_profile_name": "",
            "profile_count": len(profile_items),
            "enabled_profile_count": len(enabled_items),
            "active_strategy_count": len(active_items),
        }

    def get_profile_setup(self, profile_key: str) -> ProfileSetupPayload | None:
        with self._profile_list_lock:
            return self._get_profile_setup_locked(profile_key)

    def warm_profile_setups(self, profile_keys: tuple[str, ...]) -> None:
        for index, profile_key in enumerate(tuple(profile_keys or ())):
            self._yield_profile_payload_worker(index)
            self.get_profile_setup(profile_key)

    def _get_profile_setup_locked(self, profile_key: str) -> ProfileSetupPayload | None:
        cache_key = self._profile_setup_cache_key(profile_key)
        if cache_key is None:
            return None
        cached = self._profile_setup_payload_cache.get(cache_key)
        if cache_key in self._profile_setup_payload_cache:
            self._profile_setup_payload_cache.move_to_end(cache_key)
            return cached

        preset_revision, manifest, source_text = self._selected_preset_revision()
        preset, _manifest = self._load_selected_preset_for_revision(preset_revision, manifest, source_text)
        catalogs = load_strategy_catalogs(self._app_paths, self._engine)
        templates = self._load_profile_templates()
        source = find_profile_list_source(
            build_profile_list_sources(tuple(preset.profiles), templates),
            profile_key,
        )
        if source is None:
            self._remember_profile_setup_payload(cache_key, None)
            return None
        profile = source.profile
        item = self._item_for_profile(
            profile,
            catalogs=catalogs,
            in_preset=source.in_preset,
            key=source.key,
            order=source.order,
            user_template_key=getattr(source, "user_template_key", ""),
            display_name_override=getattr(source, "display_name_override", ""),
        )
        strategy_entries = dict(_basic_strategy_entries(profile, catalogs))
        match_summary = _match_summary(profile, list_type=item.list_type)
        strategy_branches = _strategy_branches_with_match_text(
            _strategy_branches_for_profile(profile, strategy_entries),
            match_summary=match_summary,
        )
        current_branch = strategy_branches[0] if strategy_branches else None
        current_strategy_id = (
            str(current_branch.strategy_id or "").strip()
            if current_branch is not None
            else str(item.strategy_id or "").strip()
        )
        raw_strategy_text = (
            current_branch.raw_strategy_text
            if current_branch is not None
            else "\n".join(getattr(profile.strategy, "strategy_lines", ()) or ())
        )
        editable = read_editable_profile_settings(profile)
        strategy_states = self._state_store.get_strategy_states(
            profile.persistent_key,
            tuple(strategy_entries),
        )
        payload = ProfileSetupPayload(
            item=item,
            strategy_entries=strategy_entries,
            strategy_states=strategy_states,
            raw_profile_text=_profile_raw_text(profile),
            raw_strategy_text=raw_strategy_text,
            match_summary=match_summary,
            match_tab_text=(
                str(current_branch.match_tab_text or "")
                if current_branch is not None
                else build_profile_setup_match_tab_text(
                    match_summary=match_summary,
                    strategy_id=item.strategy_id,
                    strategy_name=item.strategy_name,
                    raw_strategy_text=raw_strategy_text,
                )
            ),
            strategy_branches=strategy_branches,
            current_strategy_branch_id=str(getattr(current_branch, "branch_id", "") or ""),
            editable_filter_kind=editable.filter_kind,
            editable_filter_value=editable.filter_value,
            editable_filter_enabled=editable.filter_editable,
            editable_filter_role=editable.filter_role,
            editable_filter_kinds=_available_filter_kinds(editable, self._app_paths),
            in_range=editable.in_range,
            out_range=editable.out_range,
            current_strategy_state=strategy_states.get(current_strategy_id, ProfileStrategyState()),
        )
        self._remember_profile_setup_payload(cache_key, payload)
        return payload

    def _profile_setup_cache_key(self, profile_key: str) -> tuple[object, ...] | None:
        key = str(profile_key or "").strip()
        if not key:
            return None
        preset_revision, _manifest, _source_text = self._selected_preset_revision()
        return (*preset_revision, ("profile_setup", key))

    def _remember_profile_setup_payload(
        self,
        cache_key: tuple[object, ...],
        payload: ProfileSetupPayload | None,
    ) -> None:
        self._profile_setup_payload_cache[cache_key] = payload
        self._profile_setup_payload_cache.move_to_end(cache_key)
        limit = max(1, int(PROFILE_SETUP_PAYLOAD_CACHE_LIMIT))
        while len(self._profile_setup_payload_cache) > limit:
            self._profile_setup_payload_cache.popitem(last=False)

    def set_profile_enabled(
        self,
        profile_key: str,
        enabled: bool,
        *,
        filter_kind: str = "",
        filter_value: str = "",
    ) -> str | None:
        preset, _manifest = self.load_selected_preset()
        index = resolve_preset_profile_reference_index(preset, profile_key)
        if index is not None:
            if bool(preset.profiles[index].enabled) == bool(enabled):
                return preset.profiles[index].key
            preset = with_profile_enabled(preset, index, bool(enabled))
            self.save_selected_preset(preset)
            return preset.profiles[index].key if 0 <= index < len(preset.profiles) else None

        if profile_key.startswith("template:") and enabled:
            preset, resolved_key = self._append_template_profile_to_preset(
                preset,
                profile_key,
                filter_kind=filter_kind,
                filter_value=filter_value,
            )
            if not resolved_key:
                return None
            self.save_selected_preset(preset)
            return resolved_key
        return None

    def apply_strategy(self, profile_key: str, strategy_id: str, *, strategy_branch_id: str = "") -> StrategyApplyResult:
        result = self._apply_strategy_once(
            profile_key,
            strategy_id,
            strategy_branch_id=strategy_branch_id,
        )
        if result.status in {"profile_missing", "stale_reloaded"} and result.should_reload:
            self._invalidate_selected_preset_snapshot()
            retried = self._apply_strategy_once(
                profile_key,
                strategy_id,
                strategy_branch_id=strategy_branch_id,
            )
            return retried
        return result

    def _apply_strategy_once(
        self,
        profile_key: str,
        strategy_id: str,
        *,
        strategy_branch_id: str = "",
    ) -> StrategyApplyResult:
        strategy_id = str(strategy_id or "").strip()
        if not strategy_id or strategy_id in {"none", "custom"}:
            return _strategy_apply_result("not_applicable", strategy_id=strategy_id)

        setup = self.get_profile_setup(profile_key)
        if setup is None:
            return _strategy_apply_result("profile_missing", strategy_id=strategy_id, should_reload=True)
        if setup.item.in_preset and not setup.item.enabled:
            return _strategy_apply_result(
                "not_applicable",
                profile_key=setup.item.key,
                strategy_id=strategy_id,
                should_reload=True,
                message="profile_disabled",
            )
        if setup.item.list_type == "custom":
            return _strategy_apply_result(
                "not_applicable",
                profile_key=setup.item.key,
                strategy_id=strategy_id,
                should_reload=True,
                message="custom_profile",
            )
        entry = setup.strategy_entries.get(strategy_id)
        if entry is None:
            return _strategy_apply_result(
                "not_applicable",
                profile_key=setup.item.key,
                strategy_id=strategy_id,
                should_reload=True,
                message="strategy_entry_missing",
            )
        branch_id = str(strategy_branch_id or "").strip()
        if not branch_id:
            branch_id = str(getattr(setup, "current_strategy_branch_id", "") or "").strip()
        strategy_branches = tuple(getattr(setup, "strategy_branches", ()) or ())
        if branch_id and strategy_branches and setup.item.in_preset:
            branch = next((item for item in strategy_branches if item.branch_id == branch_id), None)
            if branch is None:
                return _strategy_apply_result(
                    "stale_reloaded",
                    profile_key=setup.item.key,
                    strategy_id=strategy_id,
                    should_reload=True,
                    message="strategy_branch_missing",
                )
            if (
                setup.item.in_preset
                and setup.item.enabled
                and str(branch.strategy_id or "").strip() == strategy_id
            ):
                return _strategy_apply_result(
                    "already_applied",
                    profile_key=setup.item.key,
                    strategy_id=strategy_id,
                )
            preset, _manifest = self.load_selected_preset()
            index = resolve_preset_profile_reference_index(preset, profile_key)
            if index is None:
                return _strategy_apply_result(
                    "stale_reloaded",
                    profile_key=setup.item.key,
                    strategy_id=strategy_id,
                    should_reload=True,
                    message="profile_index_missing",
                )
            preset = _with_profile_strategy_branch_lines(preset, index, branch_id, entry.args.splitlines())
            preset = with_profile_enabled(preset, index, True)
            self.save_selected_preset(preset)
            applied_key = preset.profiles[index].key if 0 <= index < len(preset.profiles) else ""
            return _strategy_apply_result("applied", profile_key=applied_key, strategy_id=strategy_id)
        if setup.item.in_preset and strategy_branches and len(strategy_branches) > 1:
            return _strategy_apply_result(
                "stale_reloaded",
                profile_key=setup.item.key,
                strategy_id=strategy_id,
                should_reload=True,
                message="strategy_branch_required",
            )
        if (
            setup.item.in_preset
            and setup.item.enabled
            and str(setup.item.strategy_id or "").strip() == strategy_id
        ):
            return _strategy_apply_result(
                "already_applied",
                profile_key=setup.item.key,
                strategy_id=strategy_id,
            )

        preset, _manifest = self.load_selected_preset()
        resolved_key = profile_key
        if profile_key.startswith("template:"):
            preset, resolved_key = self._append_template_profile_to_preset(preset, profile_key)
            if not resolved_key:
                return _strategy_apply_result(
                    "profile_missing",
                    strategy_id=strategy_id,
                    should_reload=True,
                    message="template_profile_missing",
                )

        index = resolve_preset_profile_reference_index(preset, resolved_key)
        if index is None:
            return _strategy_apply_result(
                "profile_missing",
                strategy_id=strategy_id,
                should_reload=True,
                message="profile_index_missing",
            )
        preset = with_profile_strategy_lines(preset, index, entry.args.splitlines())
        preset = with_profile_enabled(preset, index, True)
        self.save_selected_preset(preset)
        applied_key = preset.profiles[index].key if 0 <= index < len(preset.profiles) else ""
        return _strategy_apply_result("applied", profile_key=applied_key, strategy_id=strategy_id)

    def set_current_strategy_state(
        self,
        profile_key: str,
        *,
        rating: str | None = None,
        favorite: bool | None = None,
        clear: bool = False,
    ) -> ProfileStrategyState | None:
        setup = self.get_profile_setup(profile_key)
        if setup is None:
            return None
        return self.set_strategy_state(
            setup.item.persistent_key,
            setup.item.strategy_id,
            rating=rating,
            favorite=favorite,
            clear=clear,
        )

    def set_strategy_state(
        self,
        profile_key: str,
        strategy_id: str,
        *,
        rating: str | None = None,
        favorite: bool | None = None,
        clear: bool = False,
    ) -> ProfileStrategyState | None:
        persistent_key = self._persistent_key_for_profile(profile_key)
        strategy_id = str(strategy_id or "").strip()
        if not persistent_key or strategy_id in {"", "none", "custom"}:
            return None
        current_state = self._state_store.get_strategy_state(persistent_key, strategy_id)
        next_state = ProfileStrategyState(
            rating=str(rating or "").strip().lower() if rating is not None else current_state.rating,
            favorite=bool(favorite) if favorite is not None else current_state.favorite,
        )
        if clear:
            if current_state == ProfileStrategyState():
                return current_state
            self._state_store.clear_strategy_state(persistent_key, strategy_id)
            self._invalidate_profile_list_snapshot()
            return ProfileStrategyState()
        if next_state == current_state:
            return current_state
        state = self._state_store.set_strategy_state(
            persistent_key,
            strategy_id,
            rating=rating,
            favorite=favorite,
        )
        self._invalidate_profile_list_snapshot()
        return state

    def update_winws2_editable_settings(
        self,
        profile_key: str,
        *,
        filter_kind: str,
        filter_value: str,
        in_range: str,
        out_range: str,
    ) -> str | None:
        preset, _manifest = self.load_selected_preset()
        index = resolve_preset_profile_reference_index(preset, profile_key)
        if index is None:
            return None
        current = read_editable_profile_settings(preset.profiles[index])
        next_settings = EditableProfileSettings(
            filter_kind=filter_kind,
            filter_value=filter_value,
            filter_role=current.filter_role,
            in_range=in_range,
            out_range=out_range,
        )
        if (
            current.filter_kind == next_settings.filter_kind
            and current.filter_value == next_settings.filter_value
            and current.filter_role == next_settings.filter_role
            and current.in_range == next_settings.in_range
            and current.out_range == next_settings.out_range
        ):
            return preset.profiles[index].key
        preset = with_editable_profile_settings(
            preset,
            index,
            next_settings,
        )
        self.save_selected_preset(preset)
        return preset.profiles[index].key if 0 <= index < len(preset.profiles) else None

    def update_profile_raw_text(self, profile_key: str, raw_text: str) -> str | None:
        preset, _manifest = self.load_selected_preset()
        index = resolve_preset_profile_reference_index(preset, profile_key)
        if index is None:
            return None
        normalized_text = str(raw_text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
        if _profile_raw_text(preset.profiles[index]) == normalized_text:
            return preset.profiles[index].key
        preset = with_profile_raw_text(preset, index, raw_text)
        self.save_selected_preset(preset)
        return preset.profiles[index].key if 0 <= index < len(preset.profiles) else None

    def validate_list_file_text(self, kind: str, text: str) -> tuple[tuple[int, str], ...]:
        return validate_profile_list_file_text(kind, text)

    def save_profile_list_file_text(self, profile_key: str, text: str) -> ProfileListFileEditorState | None:
        profile = self._resolve_profile(profile_key)
        if profile is None:
            return None
        reference = profile_list_file_reference(profile, self._lists_root())
        if not reference.editable or not reference.file_name:
            raise ValueError(reference.error_text or "Файл списка недоступен для редактирования.")
        invalid_lines = validate_profile_list_file_text(reference.kind, text)
        if invalid_lines:
            line, value = invalid_lines[0]
            raise ValueError(f"Строка {line}: неверная запись `{value}`.")
        text_parts = read_profile_list_file_text_parts(self._lists_root(), reference)
        if text_parts.user_text == str(text or ""):
            return self._list_editor_state_for_profile(profile)
        write_profile_list_file_text(self._lists_root(), reference, text)
        return self._list_editor_state_for_profile(profile)

    def get_profile_list_file_editor_state(
        self,
        profile_key: str,
        *,
        filter_kind: str = "",
        filter_value: str = "",
    ) -> ProfileListFileEditorState | None:
        profile = self._resolve_profile(profile_key)
        if profile is None:
            return None
        profile = self._profile_with_filter_override(
            profile,
            filter_kind=filter_kind,
            filter_value=filter_value,
        )
        return self._list_editor_state_for_profile(profile)

    def set_profile_filter_kind(self, profile_key: str, filter_kind: str) -> str | None:
        filter_kind = str(filter_kind or "").strip().lower()
        if filter_kind not in {"hostlist", "ipset"}:
            return None

        preset, _manifest = self.load_selected_preset()
        index = resolve_preset_profile_reference_index(preset, profile_key)
        if index is None:
            return None
        profile = preset.profiles[index]
        current = read_editable_profile_settings(profile)
        if not current.filter_editable:
            return None
        if current.filter_kind == filter_kind:
            return profile.key
        if filter_kind not in _available_filter_kinds(current, self._app_paths):
            return None

        preset = with_editable_profile_settings(
            preset,
            index,
            EditableProfileSettings(
                filter_kind=filter_kind,
                filter_value=current.filter_value,
                filter_role=current.filter_role,
                in_range=current.in_range,
                out_range=current.out_range,
            ),
        )
        self.save_selected_preset(preset)
        return preset.profiles[index].key if 0 <= index < len(preset.profiles) else None

    def delete_profile(self, profile_key: str) -> bool:
        preset, _manifest = self.load_selected_preset()
        index = resolve_preset_profile_reference_index(preset, profile_key)
        if index is None:
            return False
        preset = with_profile_deleted(preset, index)
        self.save_selected_preset(preset)
        return True

    def duplicate_profile(self, profile_key: str) -> str | None:
        preset, _manifest = self.load_selected_preset()
        index = resolve_preset_profile_reference_index(preset, profile_key)
        if index is None:
            return None
        preset = with_profile_duplicated(preset, index)
        self.save_selected_preset(preset)
        duplicate_index = index + 1
        return preset.profiles[duplicate_index].key if 0 <= duplicate_index < len(preset.profiles) else None

    def move_profile_before(
        self,
        source_profile_key: str,
        destination_profile_key: str,
        *,
        destination_folder_key: str = "",
    ) -> str | None:
        sources = self._profile_sources_for_folder_order()
        source = find_profile_list_source(sources, source_profile_key)
        destination = find_profile_list_source(sources, destination_profile_key)
        if source is None or destination is None:
            return None
        folder_state = load_profile_folder_state()
        destination_folder_key = str(destination_folder_key or "").strip()
        if not destination_folder_key:
            destination_folder_key, _folder_name, _order = profile_folder_for_profile(destination.profile, folder_state)
        current_ordered_keys = _profile_order_keys_for_folder(
            sources,
            folder_state,
            destination_folder_key,
        )
        if _profile_key_is_immediately_before(
            current_ordered_keys,
            source.profile.persistent_key,
            destination.profile.persistent_key,
        ):
            return source.key
        ordered_keys = _profile_order_keys_for_folder(
            sources,
            folder_state,
            destination_folder_key,
            source_key=source.profile.persistent_key,
        )
        move_profile_before_in_folder_state(
            source.profile.persistent_key,
            destination.profile.persistent_key,
            ordered_keys,
            destination_folder_key=destination_folder_key,
        )
        self._invalidate_profile_list_snapshot()
        return source.key

    def move_profile_after(
        self,
        source_profile_key: str,
        destination_profile_key: str,
        *,
        destination_folder_key: str = "",
    ) -> str | None:
        sources = self._profile_sources_for_folder_order()
        source = find_profile_list_source(sources, source_profile_key)
        destination = find_profile_list_source(sources, destination_profile_key)
        if source is None or destination is None:
            return None
        folder_state = load_profile_folder_state()
        destination_folder_key = str(destination_folder_key or "").strip()
        if not destination_folder_key:
            destination_folder_key, _folder_name, _order = profile_folder_for_profile(destination.profile, folder_state)
        current_ordered_keys = _profile_order_keys_for_folder(
            sources,
            folder_state,
            destination_folder_key,
        )
        if _profile_key_is_immediately_before(
            current_ordered_keys,
            destination.profile.persistent_key,
            source.profile.persistent_key,
        ):
            return source.key
        ordered_keys = _profile_order_keys_for_folder(
            sources,
            folder_state,
            destination_folder_key,
            source_key=source.profile.persistent_key,
        )
        move_profile_after_in_folder_state(
            source.profile.persistent_key,
            destination.profile.persistent_key,
            ordered_keys,
            destination_folder_key=destination_folder_key,
        )
        self._invalidate_profile_list_snapshot()
        return source.key

    def move_profile_to_end(self, profile_key: str) -> str | None:
        sources = self._profile_sources_for_folder_order()
        source = find_profile_list_source(sources, profile_key)
        if source is None:
            return None
        folder_state = load_profile_folder_state()
        source_folder_key, _folder_name, _order = profile_folder_for_profile(source.profile, folder_state)
        current_ordered_keys = _profile_order_keys_for_folder(
            sources,
            folder_state,
            source_folder_key,
        )
        if current_ordered_keys and current_ordered_keys[-1] == source.profile.persistent_key:
            return source.key
        move_profile_to_end_in_folder_state(
            source.profile.persistent_key,
            current_ordered_keys,
            source_folder_key=source_folder_key,
        )
        self._invalidate_profile_list_snapshot()
        return source.key

    def move_profile_to_folder(self, profile_key: str, folder_key: str) -> str | None:
        sources = self._profile_sources_for_folder_order()
        source = find_profile_list_source(sources, profile_key)
        target_folder = str(folder_key or "").strip()
        if source is None or not target_folder:
            return None
        folder_state = load_profile_folder_state()
        ordered_keys = _profile_order_keys_for_folder(
            sources,
            folder_state,
            target_folder,
            source_key=source.profile.persistent_key,
        )
        move_profile_to_folder_in_folder_state(
            source.profile.persistent_key,
            target_folder,
            ordered_keys,
        )
        self._invalidate_profile_list_snapshot()
        return source.key

    def move_preset_profile_before(self, source_profile_key: str, destination_profile_key: str) -> PresetProfileMoveResult | None:
        preset, _manifest = self.load_selected_preset()
        source_index = resolve_preset_profile_row_index(preset, source_profile_key)
        destination_index = resolve_preset_profile_row_index(preset, destination_profile_key)
        return self._move_preset_profile_to_index(preset, source_index, destination_index)

    def move_preset_profile_after(self, source_profile_key: str, destination_profile_key: str) -> PresetProfileMoveResult | None:
        preset, _manifest = self.load_selected_preset()
        source_index = resolve_preset_profile_row_index(preset, source_profile_key)
        destination_index = resolve_preset_profile_row_index(preset, destination_profile_key)
        if destination_index is not None:
            destination_index += 1
        return self._move_preset_profile_to_index(preset, source_index, destination_index)

    def move_preset_profile_to_end(self, profile_key: str) -> PresetProfileMoveResult | None:
        preset, _manifest = self.load_selected_preset()
        source_index = resolve_preset_profile_row_index(preset, profile_key)
        return self._move_preset_profile_to_index(preset, source_index, len(preset.profiles))

    def create_user_profile(self, *, name: str, protocol: str, ports: str) -> str:
        profile_id = create_user_profile(self._app_paths, name=name, protocol=protocol, ports=ports)
        self._load_profile_templates.cache_clear()
        self._invalidate_profile_list_snapshot()
        return profile_id

    def _move_preset_profile_to_index(self, preset: Preset, source_index: int | None, destination_index: int | None) -> PresetProfileMoveResult | None:
        if source_index is None or destination_index is None:
            return None
        if source_index < 0 or source_index >= len(preset.profiles):
            return None
        destination = max(0, min(int(destination_index), len(preset.profiles)))
        if source_index == destination or source_index + 1 == destination:
            key = preset.profiles[source_index].key
            return PresetProfileMoveResult(profile_key=key, key_map={key: key})
        updated = with_profile_moved(preset, source_index, destination)
        key_map = build_preset_profile_key_map(tuple(preset.profiles), tuple(updated.profiles))
        moved_key = str(preset.profiles[source_index].key or "")
        self.save_selected_preset(updated)
        return PresetProfileMoveResult(profile_key=key_map.get(moved_key, moved_key), key_map=key_map)

    def update_user_profile(self, profile_id: str, *, name: str, protocol: str, ports: str) -> int:
        old_name, row = update_user_profile(self._app_paths, profile_id, name=name, protocol=protocol, ports=ports)
        self._load_profile_templates.cache_clear()
        self._invalidate_profile_list_snapshot()
        if not old_name:
            return 0
        return self._update_user_profile_in_all_presets(old_name, row)

    def delete_user_profile(self, profile_id: str) -> int:
        old_name, _row = delete_user_profile(self._app_paths, profile_id)
        self._load_profile_templates.cache_clear()
        self._invalidate_profile_list_snapshot()
        if not old_name:
            return 0
        return self._delete_user_profile_from_all_presets(old_name)

    def _update_user_profile_in_all_presets(self, old_name: str, row: dict[str, str]) -> int:
        changed_profiles = 0
        old_key = str(old_name or "").strip().casefold()
        if not old_key:
            return 0
        for launch_method in sorted(PRESET_LAUNCH_METHODS):
            list_manifests = getattr(self._presets, "list_preset_manifests", None)
            read_source = getattr(self._presets, "read_preset_source_by_file_name", None)
            save_source = getattr(self._presets, "save_preset_source_by_file_name", None)
            if not callable(list_manifests) or not callable(read_source) or not callable(save_source):
                continue
            engine = _engine_for_method(launch_method)
            for manifest in list_manifests(launch_method):
                file_name = str(getattr(manifest, "file_name", "") or "").strip()
                if not file_name:
                    continue
                source_text = str(read_source(launch_method, file_name) or "")
                if old_name not in source_text:
                    continue
                preset = parse_preset_text(source_text, engine=engine, source_name=file_name)
                changed_indexes = [
                    profile.index
                    for profile in preset.profiles
                    if str(getattr(profile, "name", "") or "").strip().casefold() == old_key
                ]
                if not changed_indexes:
                    continue
                for index in changed_indexes:
                    preset = with_profile_user_match(
                        preset,
                        index,
                        name=str(row.get("name") or ""),
                        protocol=str(row.get("protocol") or ""),
                        ports=str(row.get("ports") or ""),
                        hostlist=str(row.get("hostlist") or ""),
                        ipset=str(row.get("ipset") or ""),
                    )
                save_source(launch_method, file_name, serialize_preset(preset))
                changed_profiles += len(changed_indexes)
        return changed_profiles

    def _delete_user_profile_from_all_presets(self, old_name: str) -> int:
        changed_profiles = 0
        old_key = str(old_name or "").strip().casefold()
        if not old_key:
            return 0
        for launch_method in sorted(PRESET_LAUNCH_METHODS):
            list_manifests = getattr(self._presets, "list_preset_manifests", None)
            read_source = getattr(self._presets, "read_preset_source_by_file_name", None)
            save_source = getattr(self._presets, "save_preset_source_by_file_name", None)
            if not callable(list_manifests) or not callable(read_source) or not callable(save_source):
                continue
            engine = _engine_for_method(launch_method)
            for manifest in list_manifests(launch_method):
                file_name = str(getattr(manifest, "file_name", "") or "").strip()
                if not file_name:
                    continue
                source_text = str(read_source(launch_method, file_name) or "")
                if old_name not in source_text:
                    continue
                preset = parse_preset_text(source_text, engine=engine, source_name=file_name)
                changed_indexes = [
                    profile.index
                    for profile in preset.profiles
                    if str(getattr(profile, "name", "") or "").strip().casefold() == old_key
                ]
                if not changed_indexes:
                    continue
                for index in sorted(changed_indexes, reverse=True):
                    preset = with_profile_deleted(preset, index)
                save_source(launch_method, file_name, serialize_preset(preset))
                changed_profiles += len(changed_indexes)
        return changed_profiles

    def _profile_sources_for_folder_order(self):
        preset, _manifest = self.load_selected_preset()
        templates = self._load_profile_templates()
        return build_profile_list_sources(tuple(preset.profiles), templates)

    def _resolve_profile(self, profile_key: str) -> Profile | None:
        preset, _manifest = self.load_selected_preset()
        index = resolve_preset_profile_reference_index(preset, profile_key)
        if index is not None:
            return preset.profiles[index]
        if profile_key.startswith("template:"):
            return self._load_profile_templates().get(profile_key.split(":", 1)[1])
        return None

    def _persistent_key_for_profile(self, profile_key: str) -> str:
        profile = self._resolve_profile(profile_key)
        return str(getattr(profile, "persistent_key", "") or "").strip() if profile is not None else ""

    def _strategy_state_for_item(self, item: ProfileListItem) -> ProfileStrategyState:
        if not item.in_preset or not item.enabled or item.strategy_id in {"", "none", "custom"}:
            return ProfileStrategyState()
        return self._state_store.get_strategy_state(item.persistent_key, item.strategy_id)

    def _lists_root(self) -> Path:
        return Path(getattr(self._app_paths, "user_root", "")) / "lists"

    def _list_editor_state_for_profile(self, profile: Profile) -> ProfileListFileEditorState:
        reference = profile_list_file_reference(profile, self._lists_root())
        text_parts = read_profile_list_file_text_parts(self._lists_root(), reference)
        invalid_lines = validate_profile_list_file_text(reference.kind, text_parts.user_text) if reference.editable else ()
        base_entries_count = count_profile_list_entries(text_parts.base_text) if reference.editable else 0
        user_entries_count = count_profile_list_entries(
            text_parts.user_text if reference.editable else text_parts.final_text
        )
        return ProfileListFileEditorState(
            kind=reference.kind,
            display_path=reference.display_path,
            text=text_parts.final_text,
            base_text=text_parts.base_text,
            user_text=text_parts.user_text,
            base_display_path=reference.base_display_path,
            user_display_path=reference.user_display_path,
            editable=reference.editable,
            invalid_lines=invalid_lines,
            error_text=reference.error_text,
            base_entries_count=base_entries_count,
            user_entries_count=user_entries_count,
        )

    def _append_template_profile_to_preset(
        self,
        preset: Preset,
        profile_key: str,
        *,
        filter_kind: str = "",
        filter_value: str = "",
    ) -> tuple[Preset, str]:
        if not str(profile_key or "").startswith("template:"):
            return preset, ""

        template = self._load_profile_templates().get(str(profile_key).split(":", 1)[1])
        if template is None:
            return preset, ""

        current = read_editable_profile_settings(template)
        template = self._profile_with_filter_override(
            template,
            filter_kind=filter_kind or current.filter_kind,
            filter_value=filter_value or current.filter_value,
            out_range="-d8",
        )
        updated = append_profile_from_template(preset, template, enabled=True, position="top")
        return updated, updated.profiles[0].key if updated.profiles else ""

    def _profile_with_filter_override(
        self,
        profile: Profile,
        *,
        filter_kind: str,
        filter_value: str,
        out_range: str = "",
    ) -> Profile:
        if profile.engine != self._engine:
            return profile

        kind = str(filter_kind or "").strip().lower()
        if kind not in {"hostlist", "ipset"}:
            return profile

        current = read_editable_profile_settings(profile)
        if not current.filter_editable:
            return profile
        if kind not in _available_filter_kinds(current, self._app_paths):
            return profile

        value = normalize_filter_value(filter_value or current.filter_value, kind, filter_role=current.filter_role)
        if not value:
            return profile

        return with_editable_profile(
            profile,
            EditableProfileSettings(
                filter_kind=kind,
                filter_value=value,
                filter_role=current.filter_role,
                in_range=current.in_range,
                out_range=out_range or current.out_range,
            ),
        )

    def _item_for_profile(
        self,
        profile: Profile,
        *,
        catalogs: dict[str, dict[str, StrategyEntry]],
        in_preset: bool,
        key: str | None = None,
        order: int | None = None,
        folder_state: dict | None = None,
        user_template_key: str = "",
        display_name_override: str = "",
    ) -> ProfileListItem:
        strategy_entries = _basic_strategy_entries(profile, catalogs)
        strategy_branches = _strategy_branches_for_profile(profile, strategy_entries)
        strategy_id, strategy_name = _profile_strategy_summary(profile, strategy_entries, strategy_branches)
        list_type = _visible_list_type(profile, self._app_paths)
        folder_key, folder_name, folder_order = profile_folder_for_profile(profile, folder_state)
        effective_strategy_id = strategy_id if in_preset and profile.enabled else "none"
        display_strategy_name = _profile_status_name(
            in_preset=in_preset,
            enabled=bool(profile.enabled),
            strategy_name=strategy_name,
        )
        state = (
            self._state_store.get_strategy_state(profile.persistent_key, effective_strategy_id)
            if effective_strategy_id not in {"", "none", "custom"}
            else ProfileStrategyState()
        )
        visible_name = str(display_name_override or "").strip()
        return ProfileListItem(
            key=key or profile.key,
            persistent_key=profile.persistent_key,
            profile_index=profile.index if in_preset else -1,
            display_name=visible_name or profile.display_name,
            enabled=profile.enabled if in_preset else False,
            in_preset=in_preset,
            strategy_id=effective_strategy_id,
            strategy_name=display_strategy_name,
            match_lines=tuple(profile.match.all_lines()),
            list_type=list_type,
            rating=state.rating,
            favorite=state.favorite,
            group=folder_key,
            group_name=folder_name,
            order=folder_order if folder_order is not None else (profile.index if order is None else int(order)),
            order_is_manual=folder_order is not None,
            group_collapsed=profile_folder_collapsed(folder_key, folder_state),
            user_profile_id=_user_profile_id_from_template_key(user_template_key),
            profile_name=profile.name,
            display_name_override=visible_name,
            strategy_branches=strategy_branches,
        )

    @lru_cache(maxsize=1)
    def _load_profile_templates(self) -> dict[str, Profile]:
        return load_profile_template_library(self._app_paths, self._engine)

    def _invalidate_selected_preset_snapshot(self) -> None:
        self._selected_preset_snapshot = None
        self._invalidate_profile_list_snapshot()

    def _invalidate_profile_list_snapshot(self) -> None:
        self._profile_list_snapshot = None
        self._profile_list_snapshot_revision = None
        self._profile_list_snapshots_by_revision.clear()
        self._profile_setup_payload_cache.clear()

    def _current_selected_preset_file_name(self) -> str:
        file_name_getter = getattr(self._presets, "get_selected_source_preset_file_name", None)
        if callable(file_name_getter):
            return str(file_name_getter(self._launch_method) or "").strip()
        manifest_getter = getattr(self._presets, "get_selected_source_preset_manifest", None)
        if callable(manifest_getter):
            manifest = manifest_getter(self._launch_method)
            return str(getattr(manifest, "file_name", "") or "").strip()
        return ""

    def _selected_preset_revision(self) -> tuple[tuple[object, ...], object, str | None]:
        manifest_getter = getattr(self._presets, "get_selected_source_preset_manifest", None)
        path_getter = getattr(self._presets, "get_selected_source_path", None)
        if callable(manifest_getter) and callable(path_getter):
            manifest = manifest_getter(self._launch_method)
            path = Path(path_getter(self._launch_method))
            revision = (
                self._launch_method,
                str(getattr(manifest, "file_name", "") or ""),
                str(path),
                *path_cache_signature(path),
            )
            return revision, manifest, None

        source_text, manifest = self._presets.read_selected_preset_source(self._launch_method)
        revision = (
            self._launch_method,
            str(getattr(manifest, "file_name", "") or ""),
            len(source_text),
            hash(source_text),
        )
        return revision, manifest, source_text

    def _log_timing(self, label: str, started_at: float) -> None:
        try:
            elapsed_ms = (time.perf_counter() - started_at) * 1000.0
            level = PROFILE_TIMING_LOG_LEVEL if label in PROFILE_VISIBLE_TIMING_LABELS else "DEBUG"
            log(f"{label}: {elapsed_ms:.1f}ms", level)
        except Exception:
            pass


def _engine_for_method(launch_method: str) -> EngineName:
    return engine_for_launch_method(launch_method)  # type: ignore[return-value]


def _strategy_apply_result(
    status: str,
    *,
    profile_key: str = "",
    strategy_id: str = "",
    should_reload: bool = False,
    message: str = "",
) -> StrategyApplyResult:
    return StrategyApplyResult(
        status=str(status or "").strip(),
        profile_key=str(profile_key or "").strip(),
        strategy_id=str(strategy_id or "").strip(),
        should_reload=bool(should_reload),
        message=str(message or "").strip(),
    )


def _profile_folder_state_revision(folder_state: dict[str, Any]) -> tuple[object, ...]:
    folders = folder_state.get("folders", {}) if isinstance(folder_state, dict) else {}
    items = folder_state.get("items", {}) if isinstance(folder_state, dict) else {}
    folder_rows: list[tuple[object, ...]] = []
    if isinstance(folders, dict):
        for key, folder in sorted(folders.items()):
            if not isinstance(folder, dict):
                continue
            folder_rows.append((
                str(key),
                str(folder.get("name") or ""),
                folder.get("order"),
                bool(folder.get("collapsed", False)),
            ))
    item_rows: list[tuple[object, ...]] = []
    if isinstance(items, dict):
        for key, meta in sorted(items.items()):
            if not isinstance(meta, dict):
                continue
            item_rows.append((
                str(key),
                str(meta.get("folder_key") or ""),
                meta.get("order"),
            ))
    return tuple(folder_rows), tuple(item_rows)


def _profile_order_keys_for_folder(sources, folder_state: dict[str, Any], folder_key: str, *, source_key: str = "") -> list[str]:
    target_folder = str(folder_key or "").strip()
    source = str(source_key or "").strip()
    keys: list[str] = []
    for item in tuple(sources or ()):
        profile = getattr(item, "profile", None)
        key = str(getattr(profile, "persistent_key", "") or "").strip()
        if not key or key == source:
            continue
        item_folder_key, _folder_name, _order = profile_folder_for_profile(profile, folder_state)
        if item_folder_key == target_folder:
            keys.append(key)
    if source and source not in keys:
        keys.append(source)
    return keys


def _profile_key_is_immediately_before(keys: list[str], source_key: str, destination_key: str) -> bool:
    source = str(source_key or "").strip()
    destination = str(destination_key or "").strip()
    if not source or not destination:
        return False
    try:
        return int(keys.index(source)) + 1 == int(keys.index(destination))
    except ValueError:
        return False


def _basic_strategy_entries(profile: Profile, catalogs: dict[str, dict[str, StrategyEntry]]) -> dict[str, StrategyEntry]:
    if _list_type(profile) == "custom":
        return {}
    return dict(catalogs.get(_catalog_name_for_profile(profile)) or {})


def _profile_strategy_summary(
    profile: Profile,
    entries: dict[str, StrategyEntry],
    branches: tuple[ProfileStrategyBranch, ...],
) -> tuple[str, str]:
    if len(branches) <= 1:
        return _resolve_strategy(profile, entries)
    names = [str(branch.strategy_name or "").strip() for branch in branches if str(branch.strategy_name or "").strip()]
    visible = names[:2]
    suffix = f" +{len(names) - len(visible)}" if len(names) > len(visible) else ""
    label = ", ".join(visible)
    if label:
        return "custom", f"{len(branches)} стратегии: {label}{suffix}"
    return "custom", f"{len(branches)} стратегии"


def _resolve_strategy(profile: Profile, entries: dict[str, StrategyEntry]) -> tuple[str, str]:
    return _resolve_strategy_lines(profile, entries, getattr(profile.strategy, "strategy_lines", ()) or ())


def _resolve_strategy_lines(profile: Profile, entries: dict[str, StrategyEntry], lines) -> tuple[str, str]:
    current = _strategy_identity_lines(profile, lines)
    if not current:
        return "none", "Стратегия не выбрана"
    matches = [
        entry
        for entry in entries.values()
        if _strategy_identity_lines(profile, entry.args.splitlines()) == current
    ]
    if len(matches) == 1:
        return matches[0].strategy_id, matches[0].name
    return "custom", "custom"


def _strategy_branches_for_profile(profile: Profile, entries: dict[str, StrategyEntry]) -> tuple[ProfileStrategyBranch, ...]:
    if profile.engine != ENGINE_WINWS2:
        return ()

    payload = "all"
    in_range = "x"
    out_range = "a"
    raw_lines: list[str] = []
    branches: list[ProfileStrategyBranch] = []

    def flush() -> None:
        nonlocal raw_lines
        if not raw_lines:
            return
        strategy_id, strategy_name = _resolve_strategy_lines(profile, entries, raw_lines)
        scope_lines = _strategy_branch_scope_lines(payload=payload, in_range=in_range, out_range=out_range)
        branches.append(
            ProfileStrategyBranch(
                branch_id=f"branch:{len(branches)}",
                payload=payload,
                in_range=in_range,
                out_range=out_range,
                strategy_id=strategy_id,
                strategy_name=strategy_name,
                raw_strategy_text="\n".join((*scope_lines, *raw_lines)).strip(),
            )
        )
        raw_lines = []

    for segment in tuple(getattr(profile, "segments", ()) or ()):
        name = str(getattr(segment, "name", "") or "").strip().lower()
        text = str(getattr(segment, "text", "") or "").strip()
        if segment.kind == "strategy_filter":
            flush()
            value = str(getattr(segment, "value", "") or "").strip()
            if name == "--payload":
                payload = value or "all"
            elif name == "--in-range":
                in_range = value or "x"
            elif name == "--out-range":
                out_range = value or "a"
            continue
        if segment.kind == "strategy" and text:
            raw_lines.append(text)

    flush()
    return tuple(branches)


def _strategy_branches_with_match_text(
    branches: tuple[ProfileStrategyBranch, ...],
    *,
    match_summary: str,
) -> tuple[ProfileStrategyBranch, ...]:
    return tuple(
        replace(
            branch,
            match_tab_text=build_profile_setup_match_tab_text(
                match_summary=match_summary,
                strategy_id=branch.strategy_id,
                strategy_name=branch.strategy_name,
                raw_strategy_text=branch.raw_strategy_text,
            ),
        )
        for branch in branches
    )


def _strategy_branch_scope_lines(*, payload: str, in_range: str, out_range: str) -> tuple[str, ...]:
    lines: list[str] = []
    if str(in_range or "x").strip() != "x":
        lines.append(f"--in-range={str(in_range).strip()}")
    if str(out_range or "a").strip() != "a":
        lines.append(f"--out-range={str(out_range).strip()}")
    if str(payload or "all").strip() != "all":
        lines.append(f"--payload={str(payload).strip()}")
    return tuple(lines)


def _with_profile_strategy_branch_lines(
    preset: Preset,
    profile_index: int,
    branch_id: str,
    strategy_lines,
) -> Preset:
    updated = deepcopy(preset)
    profile = updated.profiles[int(profile_index)]
    groups = _strategy_branch_segment_groups(profile)
    target = groups.get(str(branch_id or "").strip())
    if not target:
        return preset

    normalized_lines = [str(line or "").strip() for line in strategy_lines or () if str(line or "").strip()]
    replacement = [_strategy_segment(line) for line in normalized_lines]
    start, end = target
    profile.segments = [*profile.segments[:start], *replacement, *profile.segments[end + 1 :]]
    return parse_preset_text(
        serialize_preset(updated),
        engine=updated.engine,
        source_name=updated.source_name,
    )


def _strategy_branch_segment_groups(profile: Profile) -> dict[str, tuple[int, int]]:
    groups: dict[str, tuple[int, int]] = {}
    current: list[int] = []

    def flush() -> None:
        nonlocal current
        if not current:
            return
        groups[f"branch:{len(groups)}"] = (current[0], current[-1])
        current = []

    for index, segment in enumerate(tuple(getattr(profile, "segments", ()) or ())):
        if segment.kind == "strategy_filter":
            flush()
            continue
        if segment.kind == "strategy":
            current.append(index)

    flush()
    return groups


def _strategy_segment(line: str) -> ProfileSegment:
    name, value = _split_profile_option(line)
    return ProfileSegment(kind="strategy", text=str(line or "").strip(), name=name, value=value)


def _split_profile_option(line: str) -> tuple[str, str]:
    text = str(line or "").strip()
    if "=" not in text:
        return text, ""
    name, _sep, value = text.partition("=")
    return name.strip(), value.strip()


def _profile_status_name(*, in_preset: bool, enabled: bool, strategy_name: str) -> str:
    if not in_preset:
        return "Не добавлен"
    if not enabled:
        return "Выключен"
    return str(strategy_name or "").strip() or "Стратегия не выбрана"


def _normalize_lines(lines) -> tuple[str, ...]:
    return tuple(str(line or "").strip() for line in lines if str(line or "").strip())


def _strategy_identity_lines(profile: Profile, lines) -> tuple[str, ...]:
    normalized = _normalize_lines(lines)
    if profile.engine != ENGINE_WINWS2:
        return normalized
    return tuple(line for line in normalized if line.lower().startswith("--lua-desync="))


def _catalog_name_for_profile(profile: Profile) -> str:
    return strategy_catalog_from_match_lines(tuple(profile.match.all_lines()))


def _list_type(profile: Profile) -> str:
    catalog_name = _catalog_name_for_profile(profile)
    if catalog_name == "voice":
        return "voice"
    has_hostlist = bool(profile.match.hostlist_lines or profile.match.hostlist_domains_lines)
    has_ipset = bool(profile.match.ipset_lines or profile.match.inline_ipset_lines)
    has_excludes = bool(profile.match.hostlist_exclude_lines or profile.match.ipset_exclude_lines)
    if has_excludes:
        settings = read_editable_profile_settings(profile)
        if settings.filter_role == "exclude" and not (has_hostlist or has_ipset):
            if settings.filter_kind in {"hostlist", "ipset"}:
                return settings.filter_kind
        return "custom"
    if has_hostlist and has_ipset:
        return "custom"
    if has_hostlist:
        return "hostlist"
    if has_ipset:
        return "ipset"
    return catalog_name


def _visible_list_type(profile: Profile, app_paths) -> str:
    list_type = _list_type(profile)
    if list_type not in {"hostlist", "ipset"}:
        return ""
    if not _profile_has_filter_choice(profile, app_paths):
        return ""
    return list_type


def _profile_has_filter_choice(profile: Profile, app_paths) -> bool:
    settings = read_editable_profile_settings(profile)
    if not settings.filter_editable:
        return False
    available = {
        kind
        for kind in _available_filter_kinds(settings, app_paths)
        if kind in {"hostlist", "ipset"}
    }
    return len(available) > 1


def _user_profile_id_from_template_key(template_key: str) -> str:
    key = str(template_key or "").strip()
    if key.startswith("template:user:"):
        return key.split("template:user:", 1)[1].strip()
    if key.startswith("user:"):
        return key.split("user:", 1)[1].strip()
    return ""


def _match_summary(profile: Profile, *, list_type: str | None = None) -> str:
    match_lines = tuple(profile.match.all_lines())
    visible_list_type = _list_type(profile) if list_type is None else str(list_type or "")
    parts = [part for part in (protocol_label_from_match_lines(match_lines), ports_label_from_match_lines(match_lines), visible_list_type) if part]
    return " • ".join(parts) or "без явных условий"


def _available_filter_kinds(settings: EditableProfileSettings, app_paths) -> tuple[str, ...]:
    current_kind = str(settings.filter_kind or "hostlist").strip().lower()
    if not settings.filter_editable or current_kind not in {"hostlist", "ipset"}:
        return (current_kind,)

    result: list[str] = []
    for candidate in ("hostlist", "ipset"):
        candidate_value = normalize_filter_value(settings.filter_value, candidate, filter_role=settings.filter_role)
        if candidate == current_kind or _filter_files_available(app_paths, candidate_value):
            result.append(candidate)
    return tuple(result) or (current_kind,)


def _filter_files_available(app_paths, filter_value: str) -> bool:
    lists_root = Path(getattr(app_paths, "user_root", "")) / "lists"
    if not lists_root.exists():
        return False
    for value in _filter_reference_values(filter_value):
        if not _looks_like_list_file_reference(value):
            continue
        if not profile_list_file_exists(lists_root, value):
            return False
    return True


def _filter_reference_values(filter_value: str) -> tuple[str, ...]:
    values: list[str] = []
    for part in str(filter_value or "").split(","):
        value = part.strip().strip('"').strip("'").lstrip("@")
        if value:
            values.append(value)
    return tuple(values)


def _looks_like_list_file_reference(value: str) -> bool:
    normalized = str(value or "").strip().replace("\\", "/")
    return normalized.startswith("lists/") or "/" in normalized or normalized.lower().endswith((".txt", ".lst", ".list"))


def _profile_raw_text(profile: Profile) -> str:
    return "\n".join(segment.text for segment in profile.segments if str(segment.text or "").strip()).strip()
