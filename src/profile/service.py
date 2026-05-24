from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any
import threading
import time

from log.log import log
from settings.mode import DEFAULT_LAUNCH_METHOD, ENGINE_WINWS2, PRESET_LAUNCH_METHODS, engine_for_launch_method, normalize_launch_method

from .match_filters import ports_label_from_match_lines, protocol_label_from_match_lines, strategy_catalog_from_match_lines
from .folders import (
    load_profile_folder_state,
    move_profile_before_in_folder_state,
    move_profile_to_end_in_folder_state,
    move_profile_to_folder_in_folder_state,
    profile_folder_collapsed,
    profile_folder_for_profile,
)
from .list_interpreter import build_profile_list_sources
from .list_file_editor import (
    profile_list_file_exists,
    profile_list_file_reference,
    read_profile_list_file_text,
    validate_profile_list_file_text,
    write_profile_list_file_text,
)
from .models import EngineName, Preset, Profile
from .normalizer import normalize_preset_profiles
from .parser import parse_preset_text
from .serializer import (
    append_profile_from_template,
    serialize_preset,
    with_profile_deleted,
    with_profile_duplicated,
    with_profile_enabled,
    with_profile_raw_text,
    with_profile_strategy_lines,
    with_profile_user_match,
)
from .strategy_state import ProfileStrategyState, ProfileStrategyStateStore
from .strategy_catalog import StrategyEntry, load_strategy_catalogs
from .state import ProfileListFileEditorState, ProfileListItem, ProfileListPayload, ProfileSetupPayload
from .template_library import load_profile_template_library
from .user_profiles import create_user_profile, delete_user_profile, update_user_profile
from .editable_settings import (
    EditableProfileSettings,
    normalize_filter_value,
    read_editable_profile_settings,
    with_editable_profile,
    with_editable_profile_settings,
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
        self._presets.save_selected_preset_source(self._launch_method, serialize_preset(preset))
        self._invalidate_selected_preset_snapshot()

    def list_profiles(self) -> ProfileListPayload:
        with self._profile_list_lock:
            return self._list_profiles_locked()

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
        for source in sources:
            item = self._item_for_profile(
                source.profile,
                catalogs=catalogs,
                in_preset=source.in_preset,
                key=source.key,
                order=source.order,
                folder_state=folder_state,
                user_template_key=getattr(source, "user_template_key", ""),
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
        self._log_timing("profile_feature.list_profiles.total", total_started_at)
        return payload

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
        preset, _manifest = self.load_selected_preset()
        catalogs = load_strategy_catalogs(self._app_paths, self._engine)
        templates = self._load_profile_templates()
        source = _find_profile_list_source(
            build_profile_list_sources(tuple(preset.profiles), templates),
            profile_key,
        )
        if source is None:
            return None
        profile = source.profile
        item = self._item_for_profile(
            profile,
            catalogs=catalogs,
            in_preset=source.in_preset,
            key=source.key,
            order=source.order,
            user_template_key=getattr(source, "user_template_key", ""),
        )
        strategy_entries = dict(_basic_strategy_entries(profile, catalogs))
        editable = read_editable_profile_settings(profile)
        strategy_states = self._state_store.get_strategy_states(
            profile.persistent_key,
            tuple(strategy_entries),
        )
        return ProfileSetupPayload(
            item=item,
            strategy_entries=strategy_entries,
            strategy_states=strategy_states,
            raw_profile_text=_profile_raw_text(profile),
            raw_strategy_text="\n".join(getattr(profile.strategy, "strategy_lines", ()) or ()),
            match_summary=_match_summary(profile, list_type=item.list_type),
            editable_filter_kind=editable.filter_kind,
            editable_filter_value=editable.filter_value,
            editable_filter_enabled=editable.filter_editable,
            editable_filter_role=editable.filter_role,
            editable_filter_kinds=_available_filter_kinds(editable, self._app_paths),
            in_range=editable.in_range,
            out_range=editable.out_range,
            current_strategy_state=strategy_states.get(item.strategy_id, ProfileStrategyState()),
        )

    def set_profile_enabled(
        self,
        profile_key: str,
        enabled: bool,
        *,
        filter_kind: str = "",
        filter_value: str = "",
    ) -> str | None:
        preset, _manifest = self.load_selected_preset()
        index = _profile_index_for_key(preset, profile_key)
        if index is not None:
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

    def apply_strategy(self, profile_key: str, strategy_id: str) -> str | None:
        strategy_id = str(strategy_id or "").strip()
        if not strategy_id or strategy_id in {"none", "custom"}:
            return None

        setup = self.get_profile_setup(profile_key)
        if setup is None:
            return None
        if setup.item.list_type == "custom":
            return None
        entry = setup.strategy_entries.get(strategy_id)
        if entry is None:
            return None

        preset, _manifest = self.load_selected_preset()
        resolved_key = profile_key
        if profile_key.startswith("template:"):
            preset, resolved_key = self._append_template_profile_to_preset(preset, profile_key)
            if not resolved_key:
                return None

        index = _profile_index_for_key(preset, resolved_key)
        if index is None:
            return None
        preset = with_profile_strategy_lines(preset, index, entry.args.splitlines())
        preset = with_profile_enabled(preset, index, True)
        self.save_selected_preset(preset)
        return preset.profiles[index].key if 0 <= index < len(preset.profiles) else None

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
        if clear:
            self._state_store.clear_strategy_state(persistent_key, strategy_id)
            self._invalidate_profile_list_snapshot()
            return ProfileStrategyState()
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
        index = _profile_index_for_key(preset, profile_key)
        if index is None:
            return None
        preset = with_editable_profile_settings(
            preset,
            index,
            EditableProfileSettings(
                filter_kind=filter_kind,
                filter_value=filter_value,
                filter_role=read_editable_profile_settings(preset.profiles[index]).filter_role,
                in_range=in_range,
                out_range=out_range,
            ),
        )
        self.save_selected_preset(preset)
        return preset.profiles[index].key if 0 <= index < len(preset.profiles) else None

    def update_profile_raw_text(self, profile_key: str, raw_text: str) -> str | None:
        preset, _manifest = self.load_selected_preset()
        index = _profile_index_for_key(preset, profile_key)
        if index is None:
            return None
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
        index = _profile_index_for_key(preset, profile_key)
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
        index = _profile_index_for_key(preset, profile_key)
        if index is None:
            return False
        preset = with_profile_deleted(preset, index)
        self.save_selected_preset(preset)
        return True

    def duplicate_profile(self, profile_key: str) -> str | None:
        preset, _manifest = self.load_selected_preset()
        index = _profile_index_for_key(preset, profile_key)
        if index is None:
            return None
        preset = with_profile_duplicated(preset, index)
        self.save_selected_preset(preset)
        duplicate_index = index + 1
        return preset.profiles[duplicate_index].key if 0 <= duplicate_index < len(preset.profiles) else None

    def move_profile_before(self, source_profile_key: str, destination_profile_key: str) -> str | None:
        sources = self._profile_sources_for_folder_order()
        source = _find_profile_list_source(sources, source_profile_key)
        destination = _find_profile_list_source(sources, destination_profile_key)
        if source is None or destination is None:
            return None
        folder_state = load_profile_folder_state()
        destination_folder_key, _folder_name, _order = profile_folder_for_profile(destination.profile, folder_state)
        move_profile_before_in_folder_state(
            source.profile.persistent_key,
            destination.profile.persistent_key,
            [item.profile.persistent_key for item in sources],
            destination_folder_key=destination_folder_key,
        )
        self._invalidate_profile_list_snapshot()
        return source.key

    def move_profile_to_end(self, profile_key: str) -> str | None:
        sources = self._profile_sources_for_folder_order()
        source = _find_profile_list_source(sources, profile_key)
        if source is None:
            return None
        folder_state = load_profile_folder_state()
        source_folder_key, _folder_name, _order = profile_folder_for_profile(source.profile, folder_state)
        move_profile_to_end_in_folder_state(
            source.profile.persistent_key,
            [item.profile.persistent_key for item in sources],
            source_folder_key=source_folder_key,
        )
        self._invalidate_profile_list_snapshot()
        return source.key

    def move_profile_to_folder(self, profile_key: str, folder_key: str) -> str | None:
        sources = self._profile_sources_for_folder_order()
        source = _find_profile_list_source(sources, profile_key)
        target_folder = str(folder_key or "").strip()
        if source is None or not target_folder:
            return None
        move_profile_to_folder_in_folder_state(
            source.profile.persistent_key,
            target_folder,
            [item.profile.persistent_key for item in sources],
        )
        self._invalidate_profile_list_snapshot()
        return source.key

    def create_user_profile(self, *, name: str, protocol: str, ports: str) -> str:
        profile_id = create_user_profile(self._app_paths, name=name, protocol=protocol, ports=ports)
        self._load_profile_templates.cache_clear()
        self._invalidate_profile_list_snapshot()
        return profile_id

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
        needle = f"--name={old_name}"
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
                if needle not in source_text and old_name not in source_text:
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
        index = _profile_index_for_key(preset, profile_key)
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
        text = read_profile_list_file_text(self._lists_root(), reference)
        invalid_lines = validate_profile_list_file_text(reference.kind, text) if reference.editable else ()
        return ProfileListFileEditorState(
            kind=reference.kind,
            display_path=reference.display_path,
            text=text,
            editable=reference.editable,
            invalid_lines=invalid_lines,
            error_text=reference.error_text,
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
    ) -> ProfileListItem:
        strategy_entries = _basic_strategy_entries(profile, catalogs)
        strategy_id, strategy_name = _resolve_strategy(profile, strategy_entries)
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
        return ProfileListItem(
            key=key or profile.key,
            persistent_key=profile.persistent_key,
            profile_index=profile.index if in_preset else -1,
            display_name=profile.display_name,
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
            stat = path.stat()
            revision = (
                self._launch_method,
                str(getattr(manifest, "file_name", "") or ""),
                str(path),
                int(stat.st_mtime_ns),
                int(stat.st_size),
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
            log(f"{label}: {elapsed_ms:.1f}ms", "DEBUG")
        except Exception:
            pass


def _engine_for_method(launch_method: str) -> EngineName:
    return engine_for_launch_method(launch_method)  # type: ignore[return-value]


def _profile_index_for_key(preset: Preset, profile_key: str) -> int | None:
    key = str(profile_key or "").strip()
    if not key:
        return None
    for index, profile in enumerate(preset.profiles):
        if profile.key == key or profile.persistent_key == key:
            return index
    return None


def _find_profile_list_source(sources, profile_key: str):
    key = str(profile_key or "").strip()
    if not key:
        return None
    for source in tuple(sources or ()):
        if source.key == key or source.profile.persistent_key == key:
            return source
    return None


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


def _basic_strategy_entries(profile: Profile, catalogs: dict[str, dict[str, StrategyEntry]]) -> dict[str, StrategyEntry]:
    if _list_type(profile) == "custom":
        return {}
    return dict(catalogs.get(_catalog_name_for_profile(profile)) or {})


def _resolve_strategy(profile: Profile, entries: dict[str, StrategyEntry]) -> tuple[str, str]:
    current = _strategy_identity_lines(profile, getattr(profile.strategy, "strategy_lines", ()) or ())
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
    return "custom"


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
