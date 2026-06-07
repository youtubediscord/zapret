from __future__ import annotations

import re
from dataclasses import dataclass


_DNS_PROFILE_IP_SUFFIX = re.compile(r"\s*\(\s*(?:\d{1,3}\.){3}\d{1,3}\s*\)\s*$")
_MISSING = object()


@dataclass(slots=True)
class HostsOperationCompletionPlan:
    reset_profiles: bool
    clear_error: bool
    error_message: str


@dataclass(slots=True)
class HostsSelectionSyncEntry:
    service_name: str
    direct_only: bool
    available_profiles: list[str]
    selected_profile: str | None
    toggle_enabled: bool
    toggle_checked: bool


@dataclass(slots=True)
class HostsSelectionSyncPlan:
    entries: dict[str, HostsSelectionSyncEntry]
    new_selection: dict[str, str]


@dataclass(slots=True)
class HostsServiceRowPlan:
    service_name: str
    icon_name: str
    icon_color: str | None
    direct_only: bool
    available_profiles: list[str]
    profile_items: list[tuple[str, str]]
    selected_profile: str | None
    toggle_enabled: bool
    toggle_checked: bool


@dataclass(slots=True)
class HostsServiceGroupPlan:
    title: str
    direct_only: bool
    service_names: list[str]
    common_profiles: list[tuple[str, str]]
    rows: list[HostsServiceRowPlan]


@dataclass(slots=True)
class HostsServicesCatalogPlan:
    groups: list[HostsServiceGroupPlan]
    new_selection: dict[str, str]
    selection_changed: bool


@dataclass(slots=True)
class HostsSelectionMutationPlan:
    new_selection: dict[str, str]
    changed: bool
    apply_now: bool
    force_checked: bool | None = None
    force_enabled: bool | None = None
    skipped_services: list[str] | None = None


@dataclass(slots=True)
class HostsStatusPlan:
    active_count: int
    has_active: bool
    adobe_active: bool


@dataclass(slots=True)
class HostsAccessPlan:
    show_error: bool
    error_message: str


@dataclass(slots=True)
class HostsUiMessagePlan:
    kind: str
    title: str
    content: str


@dataclass(slots=True)
class HostsPermissionRestorePlan:
    clear_error: bool
    error_message: str
    message_plan: HostsUiMessagePlan | None


@dataclass(slots=True)
class HostsCatalogRefreshPlan:
    changed: bool
    new_signature: object
    invalidate_cache: bool
    should_rebuild: bool
    should_log: bool
    log_message: str


@dataclass(slots=True)
class HostsStatusDisplayPlan:
    dot_active: bool
    label_text: str
    adobe_active: bool


@dataclass(slots=True)
class HostsPageInitPlan:
    init_hosts_runtime: bool
    check_access: bool
    rebuild_services: bool
    mark_initialized: bool
    invalidate_cache: bool
    update_ui: bool


@dataclass(slots=True)
class HostsActivationPlan:
    reconcile_hidden_refresh: bool
    invalidate_cache: bool
    update_ui: bool


@dataclass(slots=True)
class HostsErrorBarPlan:
    title: str
    content: str
    action_text: str
    action_pending_text: str


def build_page_init_plan(
    *,
    runtime_initialized: bool,
    has_hosts_runtime: bool,
) -> HostsPageInitPlan:
    should_initialize = not bool(runtime_initialized)
    _ = has_hosts_runtime

    return HostsPageInitPlan(
        init_hosts_runtime=should_initialize and not has_hosts_runtime,
        check_access=should_initialize,
        rebuild_services=should_initialize,
        mark_initialized=should_initialize,
        invalidate_cache=True,
        update_ui=True,
    )


def build_activation_plan(*, catalog_dirty: bool) -> HostsActivationPlan:
    return HostsActivationPlan(
        reconcile_hidden_refresh=bool(catalog_dirty),
        invalidate_cache=True,
        update_ui=True,
    )


def build_status_plan(runtime_state) -> HostsStatusPlan:
    active_count = len(runtime_state.active_domains)
    return HostsStatusPlan(
        active_count=active_count,
        has_active=active_count > 0,
        adobe_active=bool(runtime_state.adobe_active),
    )


def build_status_display_plan(
    runtime_state,
    *,
    active_text: str,
    none_text: str,
) -> HostsStatusDisplayPlan:
    status_plan = build_status_plan(runtime_state)
    return HostsStatusDisplayPlan(
        dot_active=status_plan.has_active,
        label_text=active_text if status_plan.has_active else none_text,
        adobe_active=status_plan.adobe_active,
    )


def build_access_plan(
    runtime_state,
    *,
    hosts_path: str,
    read_error_message: str,
    no_access_message: str,
) -> HostsAccessPlan:
    if runtime_state.error_message:
        return HostsAccessPlan(
            show_error=True,
            error_message=read_error_message,
        )
    if runtime_state.accessible:
        return HostsAccessPlan(
            show_error=False,
            error_message="",
        )
    return HostsAccessPlan(
        show_error=True,
        error_message=no_access_message.format(path=hosts_path),
    )


def build_error_bar_plan(
    *,
    message: str,
    title: str,
    action_text: str,
    action_pending_text: str,
) -> HostsErrorBarPlan:
    return HostsErrorBarPlan(
        title=title,
        content=str(message or ""),
        action_text=action_text,
        action_pending_text=action_pending_text,
    )


def build_catalog_refresh_plan(*, current_signature, new_signature, trigger: str, services_layout_exists: bool) -> HostsCatalogRefreshPlan:
    changed = new_signature != current_signature
    return HostsCatalogRefreshPlan(
        changed=changed,
        new_signature=new_signature,
        invalidate_cache=changed,
        should_rebuild=bool(changed and services_layout_exists),
        should_log=bool(changed and current_signature is not None and services_layout_exists),
        log_message=f"Hosts: hosts_catalog.json изменился ({trigger}) — обновляем список сервисов",
    )


def build_restore_permissions_plan(*, success: bool, message: str) -> HostsPermissionRestorePlan:
    if success:
        return HostsPermissionRestorePlan(
            clear_error=True,
            error_message="",
            message_plan=HostsUiMessagePlan(
                kind="success",
                title="Готово",
                content="Права доступа к файлу hosts восстановлены",
            ),
        )
    return HostsPermissionRestorePlan(
        clear_error=False,
        error_message=str(message or ""),
        message_plan=None,
    )


def get_direct_profile_name() -> str | None:
    from hosts.proxy_domains import get_dns_profile_display_name, get_dns_profiles

    try:
        for profile in (get_dns_profiles() or []):
            profile_id = (profile or "").strip().lower()
            display_name = (get_dns_profile_display_name(profile) or "").strip().lower()
            text = f"{profile_id} {display_name}"
            if not text.strip():
                continue
            if ("вкл. (активировать hosts)" in text) or ("direct" in text) or ("no proxy" in text):
                return profile
    except Exception:
        pass
    return None


def _normalize_active_domains_map(active_domains_map: dict[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for domain, ip in (active_domains_map or {}).items():
        domain_key = str(domain or "").strip().casefold()
        if not domain_key or domain_key in normalized:
            continue
        normalized[domain_key] = str(ip or "").strip()
    return normalized


def infer_profile_from_hosts(
    service_name: str,
    available_profiles: list[str],
    active_domains_map: dict[str, str],
) -> str | None:
    from hosts.proxy_domains import get_service_domain_ip_map

    normalized_active = _normalize_active_domains_map(active_domains_map)
    if not normalized_active or not available_profiles:
        return None

    best_profile: str | None = None
    best_matches = -1
    best_present = -1
    best_total = 0

    for profile_name in available_profiles:
        try:
            domain_map = get_service_domain_ip_map(service_name, profile_name) or {}
        except Exception:
            domain_map = {}
        if not domain_map:
            continue

        total = len(domain_map)
        present = 0
        matches = 0
        for domain, ip in domain_map.items():
            active_ip = normalized_active.get(str(domain or "").casefold())
            if active_ip is None:
                continue
            present += 1
            if (active_ip or "").strip().casefold() == (ip or "").strip().casefold():
                matches += 1

        if total and matches == total:
            return profile_name

        if matches > best_matches or (matches == best_matches and present > best_present):
            best_profile = profile_name
            best_matches = matches
            best_present = present
            best_total = total

    if not best_profile:
        return None

    if len(available_profiles) == 1 and best_present > 0:
        return best_profile

    if best_total and best_matches > 0 and (best_matches / best_total) >= 0.6:
        return best_profile

    return None


def infer_direct_toggle_from_hosts(service_name: str, active_domains_map: dict[str, str]) -> bool:
    from hosts.proxy_domains import get_service_domain_names

    normalized_active = _normalize_active_domains_map(active_domains_map)
    if not normalized_active:
        return False
    try:
        for domain in (get_service_domain_names(service_name) or []):
            if str(domain or "").strip().casefold() in normalized_active:
                return True
    except Exception:
        pass
    return False


def build_selection_sync_plan(
    *,
    service_names: list[str],
    active_domains_map: dict[str, str],
    available_profiles_by_service: dict[str, list[str]] | None = None,
    service_has_proxy_by_service: dict[str, bool] | None = None,
    direct_profile: object = _MISSING,
) -> HostsSelectionSyncPlan:
    from hosts.proxy_domains import get_service_available_dns_profiles, service_has_proxy_profiles

    if direct_profile is _MISSING:
        direct_profile = get_direct_profile_name()
    direct_profile = direct_profile if isinstance(direct_profile, str) else None
    available_profiles_by_service = dict(available_profiles_by_service or {})
    service_has_proxy_by_service = dict(service_has_proxy_by_service or {})
    entries: dict[str, HostsSelectionSyncEntry] = {}
    new_selection: dict[str, str] = {}

    for service_name in service_names:
        if service_name in service_has_proxy_by_service:
            direct_only = not bool(service_has_proxy_by_service.get(service_name))
        else:
            direct_only = not service_has_proxy_profiles(service_name)
        if service_name in available_profiles_by_service:
            available = list(available_profiles_by_service.get(service_name) or [])
        else:
            available = list(get_service_available_dns_profiles(service_name) or [])
        selected_profile: str | None = None
        toggle_enabled = False
        toggle_checked = False

        if direct_only:
            enabled = infer_direct_toggle_from_hosts(service_name, active_domains_map)
            toggle_enabled = bool(direct_profile and direct_profile in available)
            toggle_checked = bool(enabled and toggle_enabled)
            if toggle_checked and direct_profile:
                selected_profile = direct_profile
                new_selection[service_name] = direct_profile
        else:
            inferred = infer_profile_from_hosts(service_name, available, active_domains_map)
            if inferred:
                selected_profile = inferred
                new_selection[service_name] = inferred

        entries[service_name] = HostsSelectionSyncEntry(
            service_name=service_name,
            direct_only=direct_only,
            available_profiles=available,
            selected_profile=selected_profile,
            toggle_enabled=toggle_enabled,
            toggle_checked=toggle_checked,
        )

    return HostsSelectionSyncPlan(entries=entries, new_selection=new_selection)


def format_dns_profile_label(profile_name: str) -> str:
    from hosts.proxy_domains import get_dns_profile_display_name

    label = (get_dns_profile_display_name(profile_name) or profile_name or "").strip()
    if not label:
        return ""
    return _DNS_PROFILE_IP_SUFFIX.sub("", label).strip()


def is_ai_service(name: str) -> bool:
    service_name = (name or "").strip().lower()
    return any(
        marker in service_name
        for marker in ("chatgpt", "openai", "gemini", "claude", "copilot", "grok", "manus")
    ) or service_name in {"meta ai", "trae.ai", "windsurf"}


def build_services_catalog_plan(
    *,
    current_selection: dict[str, str],
    active_domains_map: dict[str, str],
    direct_title: str,
    ai_title: str,
    other_title: str,
) -> HostsServicesCatalogPlan:
    from hosts.proxy_domains import (
        QUICK_SERVICES,
        get_services_profile_index,
    )

    profile_index = get_services_profile_index()
    all_dns_profiles = [
        p
        for p in (profile_index.get("dns_profiles") or [])
        if isinstance(p, str) and p.strip()
    ]
    profile_names = profile_index.get("dns_profile_names") if isinstance(profile_index, dict) else {}
    if not isinstance(profile_names, dict):
        profile_names = {}
    profile_labels = {
        profile_name: _DNS_PROFILE_IP_SUFFIX.sub(
            "",
            (profile_names.get(profile_name) or profile_name or "").strip(),
        ).strip()
        for profile_name in all_dns_profiles
    }
    ui_map = {name: (icon_name, icon_color) for icon_name, name, icon_color in QUICK_SERVICES}

    all_services = list(profile_index.get("services") or [])
    ordered_services: list[str] = []
    for _icon, name, _color in QUICK_SERVICES:
        if name in all_services and name not in ordered_services:
            ordered_services.append(name)
    for name in all_services:
        if name not in ordered_services:
            ordered_services.append(name)

    raw_available = profile_index.get("available_by_service") or {}
    raw_has_proxy = profile_index.get("has_proxy_by_service") or {}
    available_profiles_by_service = dict(raw_available) if isinstance(raw_available, dict) else {}
    service_has_proxy_by_service = dict(raw_has_proxy) if isinstance(raw_has_proxy, dict) else {}
    direct_profile = get_direct_profile_name()

    no_geohide: list[str] = []
    ai: list[str] = []
    other: list[str] = []
    for service_name in ordered_services:
        if not service_has_proxy_by_service.get(service_name, False):
            no_geohide.append(service_name)
        elif is_ai_service(service_name):
            ai.append(service_name)
        else:
            other.append(service_name)

    sync_plan = build_selection_sync_plan(
        service_names=ordered_services,
        active_domains_map=active_domains_map,
        available_profiles_by_service=available_profiles_by_service,
        service_has_proxy_by_service=service_has_proxy_by_service,
        direct_profile=direct_profile,
    )
    current_selection = dict(current_selection or {})
    new_selection: dict[str, str] = {}

    def get_common_dns_profiles(service_names: list[str]) -> list[str]:
        common: set[str] | None = None
        for service_name in service_names:
            available = {
                p
                for p in (available_profiles_by_service.get(service_name) or [])
                if isinstance(p, str) and p.strip()
            }
            if common is None:
                common = available
            else:
                common &= available
            if not common:
                return []
        if not common:
            return []
        return [profile for profile in all_dns_profiles if profile in common]

    def label_for_profile(profile_name: str) -> str:
        return str(profile_labels.get(profile_name) or "").strip()

    groups: list[HostsServiceGroupPlan] = []
    for title, names, direct_only in (
        (direct_title, no_geohide, True),
        (ai_title, ai, False),
        (other_title, other, False),
    ):
        if not names:
            continue

        common_profiles = [
            (profile_name, label)
            for profile_name in get_common_dns_profiles(names)
            for label in (label_for_profile(profile_name),)
            if label
        ]

        rows: list[HostsServiceRowPlan] = []
        for service_name in names:
            entry = sync_plan.entries.get(service_name)
            available_profiles = list(entry.available_profiles) if entry is not None else []
            saved_profile = current_selection.get(service_name)
            selected_profile: str | None = None
            toggle_checked = False
            toggle_enabled = bool(entry.toggle_enabled) if entry is not None else False

            if saved_profile in available_profiles:
                selected_profile = saved_profile
                new_selection[service_name] = saved_profile
            elif not saved_profile and entry is not None and entry.selected_profile in available_profiles:
                selected_profile = entry.selected_profile
                if selected_profile:
                    new_selection[service_name] = selected_profile

            if entry is not None and entry.direct_only:
                toggle_checked = bool(selected_profile and selected_profile == direct_profile)
            elif entry is not None:
                toggle_checked = bool(entry.toggle_checked)

            rows.append(
                HostsServiceRowPlan(
                    service_name=service_name,
                    icon_name=ui_map.get(service_name, ("fa5s.globe", None))[0],
                    icon_color=ui_map.get(service_name, ("fa5s.globe", None))[1],
                    direct_only=bool(entry.direct_only) if entry is not None else direct_only,
                    available_profiles=available_profiles,
                    profile_items=[
                        (profile_name, label)
                        for profile_name in available_profiles
                        for label in (label_for_profile(profile_name),)
                        if label
                    ],
                    selected_profile=selected_profile,
                    toggle_enabled=toggle_enabled,
                    toggle_checked=toggle_checked,
                )
            )

        groups.append(
            HostsServiceGroupPlan(
                title=title,
                direct_only=direct_only,
                service_names=list(names),
                common_profiles=common_profiles,
                rows=rows,
            )
        )

    return HostsServicesCatalogPlan(
        groups=groups,
        new_selection=new_selection,
        selection_changed=dict(current_selection) != new_selection,
    )


def build_profile_selection_plan(
    *,
    current_selection: dict[str, str],
    service_name: str,
    selected_profile: object,
) -> HostsSelectionMutationPlan:
    new_selection = dict(current_selection)
    profile_name = selected_profile.strip() if isinstance(selected_profile, str) else ""
    if not profile_name:
        new_selection.pop(service_name, None)
    else:
        new_selection[service_name] = profile_name

    return HostsSelectionMutationPlan(
        new_selection=new_selection,
        changed=new_selection != dict(current_selection),
        apply_now=True,
    )


def build_mode_toggle_plan(
    *,
    current_selection: dict[str, str],
    service_name: str,
    checked: bool,
) -> HostsSelectionMutationPlan:
    direct_profile = get_direct_profile_name()
    new_selection = dict(current_selection)
    if not direct_profile:
        new_selection.pop(service_name, None)
        return HostsSelectionMutationPlan(
            new_selection=new_selection,
            changed=new_selection != dict(current_selection),
            apply_now=False,
            force_checked=False,
            force_enabled=False,
        )

    if checked:
        new_selection[service_name] = direct_profile
    else:
        new_selection.pop(service_name, None)

    return HostsSelectionMutationPlan(
        new_selection=new_selection,
        changed=new_selection != dict(current_selection),
        apply_now=True,
    )


def build_reset_selection_plan() -> HostsSelectionMutationPlan:
    return HostsSelectionMutationPlan(
        new_selection={},
        changed=True,
        apply_now=False,
    )


def build_bulk_profile_selection_plan(
    *,
    current_selection: dict[str, str],
    service_names: list[str],
    profile_name: str | None,
) -> HostsSelectionMutationPlan:
    from hosts.proxy_domains import get_service_available_dns_profiles

    target_profile = (profile_name or "").strip()
    if target_profile:
        unavailable = [
            service_name
            for service_name in service_names
            if target_profile not in (get_service_available_dns_profiles(service_name) or [])
        ]
        if unavailable:
            return HostsSelectionMutationPlan(
                new_selection=dict(current_selection),
                changed=False,
                apply_now=False,
                skipped_services=unavailable,
            )

    new_selection = dict(current_selection)
    for service_name in service_names:
        if not target_profile:
            new_selection.pop(service_name, None)
        else:
            new_selection[service_name] = target_profile

    return HostsSelectionMutationPlan(
        new_selection=new_selection,
        changed=new_selection != dict(current_selection),
        apply_now=new_selection != dict(current_selection),
        skipped_services=[],
    )


def build_operation_completion_plan(*, operation: str | None, success: bool, message: str, hosts_path: str) -> HostsOperationCompletionPlan:
    if success:
        return HostsOperationCompletionPlan(
            reset_profiles=operation == "clear_all",
            clear_error=True,
            error_message="",
        )

    return HostsOperationCompletionPlan(
        reset_profiles=False,
        clear_error=False,
        error_message=f"{message}\nПуть: {hosts_path}",
    )
