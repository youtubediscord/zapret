from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from types import SimpleNamespace

from core.presets.preset_file_store import PresetFileStore

from .match_filters import ports_label_from_match_lines, protocol_label_from_match_lines, strategy_catalog_from_match_lines
from .models import EngineName, Preset, Profile
from .parser import parse_preset_text
from .serializer import (
    append_profile_from_template,
    serialize_preset,
    with_profile_enabled,
    with_profile_strategy_lines,
)
from .strategy_catalog import StrategyEntry, load_strategy_catalogs
from .template_catalog import load_profile_templates
from .winws2_editable_settings import Winws2EditableSettings, read_winws2_editable_settings, with_winws2_editable_settings


@dataclass(frozen=True)
class ProfileListItem:
    key: str
    profile_index: int
    template_id: str
    display_name: str
    enabled: bool
    in_preset: bool
    strategy_id: str
    strategy_name: str
    match_lines: tuple[str, ...]
    list_type: str
    group: str
    order: int


@dataclass(frozen=True)
class ProfileListPayload:
    items: tuple[ProfileListItem, ...]
    strategy_names_by_profile: dict[str, dict[str, str]]
    selected_preset_file_name: str
    selected_preset_name: str


@dataclass(frozen=True)
class ProfileDetailPayload:
    item: ProfileListItem
    strategy_entries: dict[str, StrategyEntry]
    raw_profile_text: str
    raw_strategy_text: str
    match_summary: str
    editable_filter_kind: str = ""
    editable_filter_value: str = ""
    editable_filter_enabled: bool = True
    in_range: str = "x"
    out_range: str = "a"


class ProfilePresetService:
    def __init__(self, app_context, launch_method: str = "zapret2_mode") -> None:
        self._app_context = app_context
        self._launch_method = str(launch_method or "").strip().lower()
        self._engine = _engine_for_method(self._launch_method)
        self._preset_file_store: PresetFileStore = app_context.preset_file_store

    @property
    def engine(self) -> EngineName:
        return self._engine

    def load_selected_preset(self) -> tuple[Preset, object]:
        manifest = self._app_context.preset_mode_coordinator.get_selected_source_manifest(self._launch_method)
        source_text = self._preset_file_store.read_source_text(self._engine, manifest.file_name)
        return parse_preset_text(source_text, engine=self._engine, source_name=manifest.file_name), manifest

    def save_selected_preset(self, preset: Preset) -> None:
        manifest = self._app_context.preset_mode_coordinator.get_selected_source_manifest(self._launch_method)
        source_text = serialize_preset(preset)
        updated = self._preset_file_store.update_preset(self._engine, manifest.file_name, source_text, getattr(manifest, "name", None))
        try:
            ui_store = self._app_context.preset_store if self._engine == "winws2" else self._app_context.preset_store_v1
            ui_store.notify_preset_saved(updated.file_name)
        except Exception:
            pass
        try:
            self._app_context.preset_mode_coordinator.refresh_selected_launch_preset(self._launch_method)
        except Exception:
            pass

    def list_profiles(self) -> ProfileListPayload:
        preset, manifest = self.load_selected_preset()
        catalogs = load_strategy_catalogs(self._app_context.app_paths, self._engine)
        templates = self._load_profile_templates()
        existing_signatures = {profile.match_signature for profile in preset.profiles if profile.match_signature}

        items: list[ProfileListItem] = []
        strategy_names: dict[str, dict[str, str]] = {}

        for profile in preset.profiles:
            item = self._item_for_profile(profile, catalogs=catalogs, in_preset=True)
            items.append(item)
            strategy_names[item.key] = _strategy_names_for_catalog(catalogs, _catalog_name_for_profile(profile))

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
            strategy_names[item.key] = _strategy_names_for_catalog(catalogs, _catalog_name_for_profile(template))
            template_order += 1

        return ProfileListPayload(
            items=tuple(items),
            strategy_names_by_profile=strategy_names,
            selected_preset_file_name=str(getattr(manifest, "file_name", "") or ""),
            selected_preset_name=str(getattr(manifest, "name", "") or ""),
        )

    def get_profile_detail(self, profile_key: str) -> ProfileDetailPayload | None:
        payload = self.list_profiles()
        item = next((candidate for candidate in payload.items if candidate.key == profile_key), None)
        if item is None:
            return None
        profile = self._resolve_profile(profile_key)
        if profile is None:
            return None
        catalogs = load_strategy_catalogs(self._app_context.app_paths, self._engine)
        strategy_entries = dict((catalogs.get(_catalog_name_for_profile(profile)) or {}))
        winws2_editable = read_winws2_editable_settings(profile) if self._engine == "winws2" else Winws2EditableSettings()
        return ProfileDetailPayload(
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

        detail = self.get_profile_detail(profile_key)
        if detail is None:
            return None
        entry = detail.strategy_entries.get(strategy_id)
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

    def update_winws2_editable_settings(
        self,
        profile_key: str,
        *,
        filter_kind: str,
        filter_value: str,
        in_range: str,
        out_range: str,
    ) -> str | None:
        if self._engine != "winws2":
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

    def _resolve_profile(self, profile_key: str) -> Profile | None:
        preset, _manifest = self.load_selected_preset()
        index = _profile_index_for_key(preset, profile_key)
        if index is not None:
            return preset.profiles[index]
        if profile_key.startswith("template:"):
            return self._load_profile_templates().get(profile_key.split(":", 1)[1])
        return None

    def _item_for_profile(
        self,
        profile: Profile,
        *,
        catalogs: dict[str, dict[str, StrategyEntry]],
        in_preset: bool,
        key: str | None = None,
        order: int | None = None,
    ) -> ProfileListItem:
        catalog_name = _catalog_name_for_profile(profile)
        strategy_id, strategy_name = _resolve_strategy(profile, catalogs.get(catalog_name) or {})
        list_type = _list_type(profile)
        return ProfileListItem(
            key=key or profile.key,
            profile_index=profile.index if in_preset else -1,
            template_id=(key.split(":", 1)[1] if key and key.startswith("template:") else ""),
            display_name=profile.display_name,
            enabled=profile.enabled if in_preset else False,
            in_preset=in_preset,
            strategy_id=strategy_id if in_preset and profile.enabled else "none",
            strategy_name=strategy_name if in_preset and profile.enabled else "Отключено",
            match_lines=tuple(profile.match.all_lines()),
            list_type=list_type,
            group=_group_for_profile(profile),
            order=profile.index if order is None else int(order),
        )

    @lru_cache(maxsize=1)
    def _load_profile_templates(self) -> dict[str, Profile]:
        return load_profile_templates(self._engine)


def _engine_for_method(launch_method: str) -> EngineName:
    method = str(launch_method or "").strip().lower()
    if method == "zapret1_mode":
        return "winws1"
    if method == "zapret2_mode":
        return "winws2"
    raise ValueError(f"Unsupported profile launch method: {launch_method}")


def _profile_index_for_key(preset: Preset, profile_key: str) -> int | None:
    key = str(profile_key or "").strip()
    if not key:
        return None
    for index, profile in enumerate(preset.profiles):
        if profile.key == key:
            return index
    return None


def _strategy_names_for_catalog(catalogs: dict[str, dict[str, StrategyEntry]], catalog_name: str) -> dict[str, str]:
    return {
        strategy_id: entry.name
        for strategy_id, entry in (catalogs.get(catalog_name) or {}).items()
    }


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
