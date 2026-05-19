from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from settings.mode import DEFAULT_LAUNCH_METHOD, ENGINE_WINWS2, PRESET_LAUNCH_METHODS, engine_for_launch_method, normalize_launch_method

from .match_filters import ports_label_from_match_lines, protocol_label_from_match_lines, strategy_catalog_from_match_lines
from .folders import (
    load_profile_folder_state,
    move_profile_before_in_folder_state,
    move_profile_to_end_in_folder_state,
    profile_folder_collapsed,
    profile_folder_for_profile,
)
from .list_interpreter import build_profile_list_sources
from .models import EngineName, Preset, Profile
from .normalizer import normalize_preset_profiles
from .parser import parse_preset_text
from .serializer import (
    append_profile_from_template,
    serialize_preset,
    with_profile_deleted,
    with_profile_duplicated,
    with_profile_enabled,
    with_profile_strategy_lines,
    with_profile_user_match,
)
from .strategy_state import ProfileStrategyState, ProfileStrategyStateStore
from .strategy_catalog import StrategyEntry, load_strategy_catalogs
from .state import ProfileListItem, ProfileListPayload, ProfileSetupPayload
from .template_library import load_profile_template_library
from .user_profiles import create_user_profile, delete_user_profile, update_user_profile
from .winws2_editable_settings import (
    Winws2EditableSettings,
    normalize_winws2_filter_value,
    read_winws2_editable_settings,
    with_winws2_editable_settings,
)


class ProfilePresetService:
    def __init__(self, profile_services, launch_method: str = DEFAULT_LAUNCH_METHOD) -> None:
        self._profile_services = profile_services
        self._presets = profile_services._presets_feature
        self._app_paths = profile_services._app_paths
        self._launch_method = normalize_launch_method(launch_method)
        self._engine = _engine_for_method(self._launch_method)
        self._state_store = ProfileStrategyStateStore()

    @property
    def engine(self) -> EngineName:
        return self._engine

    def load_selected_preset(self) -> tuple[Preset, object]:
        source_text, manifest = self._presets.read_selected_preset_source(self._launch_method)
        return parse_preset_text(source_text, engine=self._engine, source_name=manifest.file_name), manifest

    def save_selected_preset(self, preset: Preset) -> None:
        self._presets.save_selected_preset_source(self._launch_method, serialize_preset(preset))

    def list_profiles(self) -> ProfileListPayload:
        preset, manifest = self.load_selected_preset()
        normalization = normalize_preset_profiles(preset)
        if normalization.changed:
            preset = normalization.preset
            self.save_selected_preset(preset)
        catalogs = load_strategy_catalogs(self._app_paths, self._engine)
        templates = self._load_profile_templates()
        folder_state = load_profile_folder_state()

        items: list[ProfileListItem] = []

        for source in build_profile_list_sources(tuple(preset.profiles), templates):
            item = self._item_for_profile(
                source.profile,
                catalogs=catalogs,
                in_preset=source.in_preset,
                key=source.key,
                order=source.order,
                folder_state=folder_state,
            )
            items.append(item)

        return ProfileListPayload(
            items=tuple(items),
            selected_preset_file_name=str(getattr(manifest, "file_name", "") or ""),
            selected_preset_name=str(getattr(manifest, "name", "") or ""),
            normalized_split_profiles=normalization.split_profile_count,
            normalized_created_profiles=normalization.created_profile_count,
        )

    def count_enabled_profiles(self) -> int:
        preset, _manifest = self.load_selected_preset()
        return sum(1 for profile in preset.profiles if bool(getattr(profile, "enabled", False)))

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
        )
        strategy_entries = dict(_basic_strategy_entries(profile, catalogs))
        winws2_editable = read_winws2_editable_settings(profile) if self._engine == ENGINE_WINWS2 else Winws2EditableSettings()
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
            match_summary=_match_summary(profile),
            editable_filter_kind=winws2_editable.filter_kind,
            editable_filter_value=winws2_editable.filter_value,
            editable_filter_enabled=winws2_editable.filter_editable,
            editable_filter_kinds=_available_filter_kinds(winws2_editable, self._app_paths),
            in_range=winws2_editable.in_range,
            out_range=winws2_editable.out_range,
            current_strategy_state=strategy_states.get(item.strategy_id, ProfileStrategyState()),
        )

    def set_profile_enabled(self, profile_key: str, enabled: bool) -> str | None:
        preset, _manifest = self.load_selected_preset()
        index = _profile_index_for_key(preset, profile_key)
        if index is not None:
            preset = with_profile_enabled(preset, index, bool(enabled))
            self.save_selected_preset(preset)
            return preset.profiles[index].key if 0 <= index < len(preset.profiles) else None

        if profile_key.startswith("template:") and enabled:
            template = self._load_profile_templates().get(profile_key.split(":", 1)[1])
            if template is None:
                return None
            new_index = len(preset.profiles)
            preset = append_profile_from_template(preset, template, enabled=True)
            self.save_selected_preset(preset)
            return preset.profiles[new_index].key if 0 <= new_index < len(preset.profiles) else None
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
            template = self._load_profile_templates().get(profile_key.split(":", 1)[1])
            if template is None:
                return None
            new_index = len(preset.profiles)
            preset = append_profile_from_template(preset, template, enabled=True)
            resolved_key = preset.profiles[new_index].key if 0 <= new_index < len(preset.profiles) else ""

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
            return ProfileStrategyState()
        return self._state_store.set_strategy_state(
            persistent_key,
            strategy_id,
            rating=rating,
            favorite=favorite,
        )

    def update_winws2_editable_settings(
        self,
        profile_key: str,
        *,
        filter_kind: str,
        filter_value: str,
        in_range: str,
        out_range: str,
    ) -> str | None:
        if self._engine != ENGINE_WINWS2:
            return None

        preset, _manifest = self.load_selected_preset()
        index = _profile_index_for_key(preset, profile_key)
        if index is None:
            return None
        preset = with_winws2_editable_settings(
            preset,
            index,
            Winws2EditableSettings(
                filter_kind=filter_kind,
                filter_value=filter_value,
                in_range=in_range,
                out_range=out_range,
            ),
        )
        self.save_selected_preset(preset)
        return preset.profiles[index].key if 0 <= index < len(preset.profiles) else None

    def set_profile_filter_kind(self, profile_key: str, filter_kind: str) -> str | None:
        if self._engine != ENGINE_WINWS2:
            return None
        filter_kind = str(filter_kind or "").strip().lower()
        if filter_kind not in {"hostlist", "ipset"}:
            return None

        preset, _manifest = self.load_selected_preset()
        index = _profile_index_for_key(preset, profile_key)
        if index is None:
            return None
        profile = preset.profiles[index]
        current = read_winws2_editable_settings(profile)
        if not current.filter_editable:
            return None
        if current.filter_kind == filter_kind:
            return profile.key
        if filter_kind not in _available_filter_kinds(current, self._app_paths):
            return None

        preset = with_winws2_editable_settings(
            preset,
            index,
            Winws2EditableSettings(
                filter_kind=filter_kind,
                filter_value=current.filter_value,
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
        move_profile_before_in_folder_state(
            source.profile.persistent_key,
            destination.profile.persistent_key,
            [item.profile.persistent_key for item in sources],
        )
        return source.key

    def move_profile_to_end(self, profile_key: str) -> str | None:
        sources = self._profile_sources_for_folder_order()
        source = _find_profile_list_source(sources, profile_key)
        if source is None:
            return None
        move_profile_to_end_in_folder_state(
            source.profile.persistent_key,
            [item.profile.persistent_key for item in sources],
        )
        return source.key

    def create_user_profile(self, *, name: str, protocol: str, ports: str) -> str:
        profile_id = create_user_profile(self._app_paths, name=name, protocol=protocol, ports=ports)
        self._load_profile_templates.cache_clear()
        return profile_id

    def update_user_profile(self, profile_id: str, *, name: str, protocol: str, ports: str) -> int:
        old_name, row = update_user_profile(self._app_paths, profile_id, name=name, protocol=protocol, ports=ports)
        self._load_profile_templates.cache_clear()
        if not old_name:
            return 0
        return self._update_user_profile_in_all_presets(old_name, row)

    def delete_user_profile(self, profile_id: str) -> int:
        old_name, _row = delete_user_profile(self._app_paths, profile_id)
        self._load_profile_templates.cache_clear()
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

    def _item_for_profile(
        self,
        profile: Profile,
        *,
        catalogs: dict[str, dict[str, StrategyEntry]],
        in_preset: bool,
        key: str | None = None,
        order: int | None = None,
        folder_state: dict | None = None,
    ) -> ProfileListItem:
        strategy_entries = _basic_strategy_entries(profile, catalogs)
        strategy_id, strategy_name = _resolve_strategy(profile, strategy_entries)
        list_type = _list_type(profile)
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
        )

    @lru_cache(maxsize=1)
    def _load_profile_templates(self) -> dict[str, Profile]:
        return load_profile_template_library(self._app_paths, self._engine)


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
    if has_excludes or (has_hostlist and has_ipset):
        return "custom"
    if has_hostlist:
        return "hostlist"
    if has_ipset:
        return "ipset"
    return "custom"


def _match_summary(profile: Profile) -> str:
    match_lines = tuple(profile.match.all_lines())
    parts = [part for part in (protocol_label_from_match_lines(match_lines), ports_label_from_match_lines(match_lines), _list_type(profile)) if part]
    return " • ".join(parts) or "без явных условий"


def _available_filter_kinds(settings: Winws2EditableSettings, app_paths) -> tuple[str, ...]:
    current_kind = str(settings.filter_kind or "hostlist").strip().lower()
    if not settings.filter_editable or current_kind not in {"hostlist", "ipset"}:
        return (current_kind,)

    result: list[str] = []
    for candidate in ("hostlist", "ipset"):
        candidate_value = normalize_winws2_filter_value(settings.filter_value, candidate)
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
        if not (lists_root / Path(value.replace("\\", "/")).name).is_file():
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
