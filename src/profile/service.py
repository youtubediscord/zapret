from __future__ import annotations

from functools import lru_cache
from types import SimpleNamespace

from settings.mode import DEFAULT_LAUNCH_METHOD, ENGINE_WINWS2, engine_for_launch_method, normalize_launch_method

from .match_filters import ports_label_from_match_lines, protocol_label_from_match_lines, strategy_catalog_from_match_lines
from .models import EngineName, Preset, Profile
from .parser import parse_preset_text
from .serializer import (
    append_profile_from_template,
    serialize_preset,
    with_profile_deleted,
    with_profile_duplicated,
    with_profile_enabled,
    with_profile_moved,
    with_profile_strategy_lines,
)
from .strategy_state import ProfileStrategyState, ProfileStrategyStateStore
from .strategy_catalog import StrategyEntry, load_strategy_catalogs
from .state import ProfileListItem, ProfileListPayload, ProfileSetupPayload
from .template_catalog import load_profile_templates
from .winws2_editable_settings import Winws2EditableSettings, read_winws2_editable_settings, with_winws2_editable_settings


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
        catalogs = load_strategy_catalogs(self._app_paths, self._engine)
        templates = self._load_profile_templates()
        existing_signatures = {profile.match_signature for profile in preset.profiles if profile.match_signature}

        items: list[ProfileListItem] = []
        strategy_names: dict[str, dict[str, str]] = {}

        for profile in preset.profiles:
            item = self._item_for_profile(profile, catalogs=catalogs, in_preset=True)
            items.append(item)
            strategy_names[item.key] = _strategy_names_for_catalog(_basic_strategy_entries(profile, catalogs))

        template_order = len(items)
        for template_id, template in templates.items():
            if template.match_signature in existing_signatures:
                continue
            item = self._item_for_profile(
                template,
                catalogs=catalogs,
                in_preset=False,
                key=f"template:{template_id}",
                order=template_order,
            )
            items.append(item)
            strategy_names[item.key] = _strategy_names_for_catalog(_basic_strategy_entries(template, catalogs))
            template_order += 1

        return ProfileListPayload(
            items=tuple(items),
            strategy_names_by_profile=strategy_names,
            selected_preset_file_name=str(getattr(manifest, "file_name", "") or ""),
            selected_preset_name=str(getattr(manifest, "name", "") or ""),
        )

    def get_profile_setup(self, profile_key: str) -> ProfileSetupPayload | None:
        payload = self.list_profiles()
        item = next(
            (
                candidate
                for candidate in payload.items
                if candidate.key == profile_key or candidate.persistent_key == profile_key
            ),
            None,
        )
        if item is None:
            return None
        profile = self._resolve_profile(profile_key)
        if profile is None:
            return None
        catalogs = load_strategy_catalogs(self._app_paths, self._engine)
        strategy_entries = dict(_basic_strategy_entries(profile, catalogs))
        winws2_editable = read_winws2_editable_settings(profile) if self._engine == ENGINE_WINWS2 else Winws2EditableSettings()
        return ProfileSetupPayload(
            item=item,
            strategy_entries=strategy_entries,
            raw_profile_text=_profile_raw_text(profile),
            raw_strategy_text="\n".join(getattr(profile.strategy, "strategy_lines", ()) or ()),
            match_summary=_match_summary(profile),
            editable_filter_kind=winws2_editable.filter_kind,
            editable_filter_value=winws2_editable.filter_value,
            editable_filter_enabled=winws2_editable.filter_editable,
            in_range=winws2_editable.in_range,
            out_range=winws2_editable.out_range,
            current_strategy_state=self._strategy_state_for_item(item),
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
        preset, _manifest = self.load_selected_preset()
        source_index = _profile_index_for_key(preset, source_profile_key)
        destination_index = _profile_index_for_key(preset, destination_profile_key)
        if source_index is None or destination_index is None:
            return None
        new_index = destination_index
        if source_index < destination_index:
            new_index -= 1
        preset = with_profile_moved(preset, source_index, destination_index)
        self.save_selected_preset(preset)
        return preset.profiles[new_index].key if 0 <= new_index < len(preset.profiles) else None

    def move_profile_to_end(self, profile_key: str) -> str | None:
        preset, _manifest = self.load_selected_preset()
        source_index = _profile_index_for_key(preset, profile_key)
        if source_index is None:
            return None
        preset = with_profile_moved(preset, source_index, len(preset.profiles))
        self.save_selected_preset(preset)
        new_index = len(preset.profiles) - 1
        return preset.profiles[new_index].key if 0 <= new_index < len(preset.profiles) else None

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
    ) -> ProfileListItem:
        strategy_entries = _basic_strategy_entries(profile, catalogs)
        strategy_id, strategy_name = _resolve_strategy(profile, strategy_entries)
        list_type = _list_type(profile)
        effective_strategy_id = strategy_id if in_preset and profile.enabled else "none"
        state = (
            self._state_store.get_strategy_state(profile.persistent_key, effective_strategy_id)
            if effective_strategy_id not in {"", "none", "custom"}
            else ProfileStrategyState()
        )
        return ProfileListItem(
            key=key or profile.key,
            persistent_key=profile.persistent_key,
            profile_index=profile.index if in_preset else -1,
            template_id=(key.split(":", 1)[1] if key and key.startswith("template:") else ""),
            display_name=profile.display_name,
            enabled=profile.enabled if in_preset else False,
            in_preset=in_preset,
            strategy_id=effective_strategy_id,
            strategy_name=strategy_name if in_preset and profile.enabled else "Отключено",
            match_lines=tuple(profile.match.all_lines()),
            list_type=list_type,
            rating=state.rating,
            favorite=state.favorite,
            group=_group_for_profile(profile),
            order=profile.index if order is None else int(order),
        )

    @lru_cache(maxsize=1)
    def _load_profile_templates(self) -> dict[str, Profile]:
        return load_profile_templates(self._app_paths, self._engine)


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


def _strategy_names_for_catalog(entries: dict[str, StrategyEntry]) -> dict[str, str]:
    return {
        strategy_id: entry.name
        for strategy_id, entry in (entries or {}).items()
    }


def _basic_strategy_entries(profile: Profile, catalogs: dict[str, dict[str, StrategyEntry]]) -> dict[str, StrategyEntry]:
    if _list_type(profile) == "custom":
        return {}
    return dict(catalogs.get(_catalog_name_for_profile(profile)) or {})


def _resolve_strategy(profile: Profile, entries: dict[str, StrategyEntry]) -> tuple[str, str]:
    current = _normalize_lines(getattr(profile.strategy, "strategy_lines", ()) or ())
    if not current:
        return "none", "Отключено"
    matches = [
        entry
        for entry in entries.values()
        if _normalize_lines(entry.args.splitlines()) == current
    ]
    if len(matches) == 1:
        return matches[0].strategy_id, matches[0].name
    return "custom", "custom"


def _normalize_lines(lines) -> tuple[str, ...]:
    return tuple(str(line or "").strip() for line in lines if str(line or "").strip())


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


def _group_for_profile(profile: Profile) -> str:
    text = " ".join(profile.match.all_lines() + [profile.display_name]).lower()
    if "youtube" in text or "googlevideo" in text:
        return "youtube"
    if "discord" in text:
        return "discord"
    if "telegram" in text:
        return "telegram"
    if "ipset" in text:
        return "ipsets"
    if "hostlist" in text or "lists/" in text:
        return "hostlists"
    return "default"


def _match_summary(profile: Profile) -> str:
    match_lines = tuple(profile.match.all_lines())
    parts = [part for part in (protocol_label_from_match_lines(match_lines), ports_label_from_match_lines(match_lines), _list_type(profile)) if part]
    return " • ".join(parts) or "без явных условий"


def _profile_raw_text(profile: Profile) -> str:
    return "\n".join(segment.text for segment in profile.segments if str(segment.text or "").strip()).strip()
