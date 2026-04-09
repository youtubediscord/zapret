from __future__ import annotations

import re
from dataclasses import dataclass

from PyQt6.QtCore import QObject, pyqtSignal

from log import log
from utils import get_system32_path


@dataclass(slots=True)
class HostsOperationResult:
    success: bool
    message: str


@dataclass(slots=True)
class HostsRuntimeState:
    active_domains: set[str]
    adobe_active: bool
    accessible: bool
    error_message: str | None


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
    selection_migrated: bool


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
class HostsShowEventPlan:
    init_hosts_manager: bool
    check_access: bool
    rebuild_services: bool
    mark_initialized: bool
    start_watcher: bool
    refresh_triggers: list[str]
    invalidate_cache: bool
    update_ui: bool


@dataclass(slots=True)
class HostsErrorBarPlan:
    title: str
    content: str
    action_text: str
    action_pending_text: str


class HostsOperationWorker(QObject):
    """Background worker for hosts operations."""

    finished = pyqtSignal(bool, str)

    def __init__(self, controller: "HostsPageController", hosts_manager, operation: str, payload=None):
        super().__init__()
        self._controller = controller
        self._hosts_manager = hosts_manager
        self._operation = operation
        self._payload = payload

    def run(self):
        try:
            result = self._controller.execute_operation(
                hosts_manager=self._hosts_manager,
                operation=self._operation,
                payload=self._payload,
            )
            self.finished.emit(result.success, result.message)
        except Exception as e:
            log(f"Ошибка в HostsOperationWorker: {e}", "ERROR")
            self.finished.emit(False, str(e))


class HostsPageController:
    _DNS_PROFILE_IP_SUFFIX = re.compile(r"\s*\(\s*(?:\d{1,3}\.){3}\d{1,3}\s*\)\s*$")

    @staticmethod
    def create_operation_worker(hosts_manager, operation: str, payload=None) -> HostsOperationWorker:
        controller = HostsPageController()
        return HostsOperationWorker(controller, hosts_manager, operation, payload)

    @staticmethod
    def resolve_hosts_manager(parent_app, app_parent):
        try:
            app_hosts_manager = None
            if parent_app is not None:
                app_hosts_manager = getattr(parent_app, "hosts_manager", None)
            if app_hosts_manager is None and app_parent is not None:
                app_hosts_manager = getattr(app_parent, "hosts_manager", None)

            if app_hosts_manager is not None:
                log("HostsPage: используем общий HostsManager приложения", "DEBUG")
                return app_hosts_manager
        except Exception:
            pass

        try:
            from hosts.hosts import HostsManager

            return HostsManager(status_callback=lambda m: log(f"Hosts: {m}", "INFO"))
        except Exception as e:
            log(f"Ошибка инициализации HostsManager: {e}", "ERROR")
            return None

    @staticmethod
    def build_show_event_plan(
        *,
        startup_initialized: bool,
        has_hosts_manager: bool,
        ipv6_catalog_changed: bool,
    ) -> HostsShowEventPlan:
        refresh_triggers: list[str] = []
        if ipv6_catalog_changed:
            refresh_triggers.append("ipv6")
        refresh_triggers.append("tab")

        return HostsShowEventPlan(
            init_hosts_manager=not startup_initialized and not has_hosts_manager,
            check_access=not startup_initialized,
            rebuild_services=not startup_initialized,
            mark_initialized=not startup_initialized,
            start_watcher=True,
            refresh_triggers=refresh_triggers,
            invalidate_cache=True,
            update_ui=True,
        )

    @staticmethod
    def load_user_selection() -> dict[str, str]:
        from hosts.proxy_domains import load_user_hosts_selection

        try:
            return dict(load_user_hosts_selection() or {})
        except Exception:
            return {}

    @staticmethod
    def save_user_selection(selection: dict[str, str]) -> bool:
        from hosts.proxy_domains import save_user_hosts_selection

        try:
            return bool(save_user_hosts_selection(dict(selection)))
        except Exception:
            return False

    @staticmethod
    def execute_operation(*, hosts_manager, operation: str, payload=None) -> HostsOperationResult:
        success = False
        message = ""

        if operation == "apply_selection":
            service_dns = payload or {}
            success = hosts_manager.apply_service_dns_selections(service_dns)
            if success:
                message = "Применено"
            else:
                message = getattr(hosts_manager, "last_status", None) or "Ошибка"

        elif operation == "clear_all":
            success = hosts_manager.clear_hosts_file()
            if success:
                message = "Hosts очищен"
            else:
                message = getattr(hosts_manager, "last_status", None) or "Ошибка"

        elif operation == "adobe_add":
            success = hosts_manager.add_adobe_domains()
            if success:
                message = "Adobe заблокирован"
            else:
                message = getattr(hosts_manager, "last_status", None) or "Ошибка"

        elif operation == "adobe_remove":
            success = hosts_manager.remove_adobe_domains()
            if success:
                message = "Adobe разблокирован"
            else:
                message = getattr(hosts_manager, "last_status", None) or "Ошибка"

        return HostsOperationResult(success=success, message=message)

    @staticmethod
    def restore_hosts_permissions() -> HostsOperationResult:
        from hosts.hosts import restore_hosts_permissions

        success, message = restore_hosts_permissions()
        return HostsOperationResult(success=bool(success), message=str(message or ""))

    @staticmethod
    def ensure_ipv6_catalog_sections() -> tuple[bool, bool]:
        from hosts.proxy_domains import ensure_ipv6_catalog_sections_if_available

        try:
            return ensure_ipv6_catalog_sections_if_available()
        except Exception:
            return (False, False)

    @staticmethod
    def get_catalog_signature():
        from hosts.proxy_domains import get_hosts_catalog_signature

        try:
            return get_hosts_catalog_signature()
        except Exception:
            return None

    @staticmethod
    def invalidate_catalog_cache() -> None:
        from hosts.proxy_domains import invalidate_hosts_catalog_cache

        try:
            invalidate_hosts_catalog_cache()
        except Exception:
            pass

    @staticmethod
    def read_runtime_state(hosts_manager) -> HostsRuntimeState:
        if hosts_manager is None:
            return HostsRuntimeState(
                active_domains=set(),
                adobe_active=False,
                accessible=False,
                error_message=None,
            )

        error_message: str | None = None
        accessible = False
        active_domains: set[str] = set()
        adobe_active = False

        try:
            accessible = bool(hosts_manager.is_hosts_file_accessible())
        except Exception as exc:
            error_message = str(exc)

        if error_message is None:
            try:
                active_domains = set(hosts_manager.get_active_domains() or set())
            except Exception as exc:
                error_message = str(exc)
                active_domains = set()

        try:
            adobe_active = bool(hosts_manager.is_adobe_domains_active())
        except Exception:
            adobe_active = False

        return HostsRuntimeState(
            active_domains=active_domains,
            adobe_active=adobe_active,
            accessible=accessible,
            error_message=error_message,
        )

    @staticmethod
    def build_status_plan(runtime_state: HostsRuntimeState) -> HostsStatusPlan:
        active_count = len(runtime_state.active_domains)
        return HostsStatusPlan(
            active_count=active_count,
            has_active=active_count > 0,
            adobe_active=bool(runtime_state.adobe_active),
        )

    @staticmethod
    def build_status_display_plan(
        runtime_state: HostsRuntimeState,
        *,
        active_text: str,
        none_text: str,
    ) -> HostsStatusDisplayPlan:
        status_plan = HostsPageController.build_status_plan(runtime_state)
        return HostsStatusDisplayPlan(
            dot_active=status_plan.has_active,
            label_text=active_text if status_plan.has_active else none_text,
            adobe_active=status_plan.adobe_active,
        )

    @staticmethod
    def build_access_plan(
        runtime_state: HostsRuntimeState,
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

    @staticmethod
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

    @staticmethod
    def build_catalog_refresh_plan(*, current_signature, new_signature, trigger: str, services_layout_exists: bool) -> HostsCatalogRefreshPlan:
        changed = new_signature != current_signature
        return HostsCatalogRefreshPlan(
            changed=changed,
            new_signature=new_signature,
            invalidate_cache=changed,
            should_rebuild=bool(changed and services_layout_exists),
            should_log=bool(changed and current_signature is not None and services_layout_exists),
            log_message=f"Hosts: hosts.ini изменился ({trigger}) — обновляем список сервисов",
        )

    @staticmethod
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

    @staticmethod
    def read_active_domains_map(hosts_manager) -> dict[str, str]:
        if hosts_manager is None:
            return {}
        try:
            return dict(hosts_manager.get_active_domains_map() or {})
        except Exception:
            return {}

    @staticmethod
    def get_direct_profile_name() -> str | None:
        from hosts.proxy_domains import get_dns_profiles

        try:
            for profile in (get_dns_profiles() or []):
                p = (profile or "").strip().lower()
                if not p:
                    continue
                if ("вкл. (активировать hosts)" in p) or ("direct" in p) or ("no proxy" in p):
                    return profile
        except Exception:
            pass
        return None

    @staticmethod
    def _infer_profile_from_hosts(
        service_name: str,
        available_profiles: list[str],
        active_domains_map: dict[str, str],
    ) -> str | None:
        from hosts.proxy_domains import get_service_domain_ip_map

        if not active_domains_map or not available_profiles:
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
                active_ip = active_domains_map.get(domain)
                if active_ip is None:
                    continue
                present += 1
                if (active_ip or "").strip() == (ip or "").strip():
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

    @staticmethod
    def _infer_direct_toggle_from_hosts(service_name: str, active_domains_map: dict[str, str]) -> bool:
        from hosts.proxy_domains import get_service_domain_names

        try:
            for domain in (get_service_domain_names(service_name) or []):
                if domain in active_domains_map:
                    return True
        except Exception:
            pass
        return False

    def build_selection_sync_plan(
        self,
        *,
        service_names: list[str],
        active_domains_map: dict[str, str],
    ) -> HostsSelectionSyncPlan:
        from hosts.proxy_domains import get_service_available_dns_profiles, get_service_has_geohide_ips

        direct_profile = self.get_direct_profile_name()
        entries: dict[str, HostsSelectionSyncEntry] = {}
        new_selection: dict[str, str] = {}

        for service_name in service_names:
            direct_only = not get_service_has_geohide_ips(service_name)
            available = list(get_service_available_dns_profiles(service_name) or [])
            selected_profile: str | None = None
            toggle_enabled = False
            toggle_checked = False

            if direct_only:
                enabled = self._infer_direct_toggle_from_hosts(service_name, active_domains_map)
                toggle_enabled = bool(direct_profile and direct_profile in available)
                toggle_checked = bool(enabled and toggle_enabled)
                if toggle_checked and direct_profile:
                    selected_profile = direct_profile
                    new_selection[service_name] = direct_profile
            else:
                inferred = self._infer_profile_from_hosts(service_name, available, active_domains_map)
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

    @classmethod
    def format_dns_profile_label(cls, profile_name: str) -> str:
        label = (profile_name or "").strip()
        if not label:
            return ""
        return cls._DNS_PROFILE_IP_SUFFIX.sub("", label).strip()

    @staticmethod
    def _is_ai_service(name: str) -> bool:
        service_name = (name or "").strip().lower()
        return any(
            marker in service_name
            for marker in ("chatgpt", "openai", "gemini", "claude", "copilot", "grok", "manus")
        )

    def build_services_catalog_plan(
        self,
        *,
        current_selection: dict[str, str],
        active_domains_map: dict[str, str],
        direct_title: str,
        ai_title: str,
        other_title: str,
    ) -> HostsServicesCatalogPlan:
        from hosts.proxy_domains import (
            QUICK_SERVICES,
            get_all_services,
            get_dns_profiles,
            get_service_available_dns_profiles,
            get_service_has_geohide_ips,
        )

        all_dns_profiles = [p for p in (get_dns_profiles() or []) if isinstance(p, str) and p.strip()]
        ui_map = {name: (icon_name, icon_color) for icon_name, name, icon_color in QUICK_SERVICES}

        all_services = list(get_all_services() or [])
        ordered_services: list[str] = []
        for _icon, name, _color in QUICK_SERVICES:
            if name in all_services and name not in ordered_services:
                ordered_services.append(name)
        for name in all_services:
            if name not in ordered_services:
                ordered_services.append(name)

        no_geohide: list[str] = []
        ai: list[str] = []
        other: list[str] = []
        for service_name in ordered_services:
            if not get_service_has_geohide_ips(service_name):
                no_geohide.append(service_name)
            elif self._is_ai_service(service_name):
                ai.append(service_name)
            else:
                other.append(service_name)

        sync_plan = self.build_selection_sync_plan(
            service_names=ordered_services,
            active_domains_map=active_domains_map,
        )

        def get_common_dns_profiles(service_names: list[str]) -> list[str]:
            common: set[str] | None = None
            for service_name in service_names:
                available = {
                    p
                    for p in (get_service_available_dns_profiles(service_name) or [])
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

        groups: list[HostsServiceGroupPlan] = []
        for title, names, direct_only in (
            (direct_title, no_geohide, True),
            (ai_title, ai, False),
            (other_title, other, False),
        ):
            if not names:
                continue

            common_profiles = [
                (profile_name, self.format_dns_profile_label(profile_name))
                for profile_name in get_common_dns_profiles(names)
                if self.format_dns_profile_label(profile_name)
            ]

            rows: list[HostsServiceRowPlan] = []
            for service_name in names:
                entry = sync_plan.entries.get(service_name)
                available_profiles = list(entry.available_profiles) if entry is not None else []
                rows.append(
                    HostsServiceRowPlan(
                        service_name=service_name,
                        icon_name=ui_map.get(service_name, ("fa5s.globe", None))[0],
                        icon_color=ui_map.get(service_name, ("fa5s.globe", None))[1],
                        direct_only=bool(entry.direct_only) if entry is not None else direct_only,
                        available_profiles=available_profiles,
                        profile_items=[
                            (profile_name, self.format_dns_profile_label(profile_name))
                            for profile_name in available_profiles
                        ],
                        selected_profile=entry.selected_profile if entry is not None else None,
                        toggle_enabled=bool(entry.toggle_enabled) if entry is not None else False,
                        toggle_checked=bool(entry.toggle_checked) if entry is not None else False,
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

        new_selection = dict(sync_plan.new_selection)
        return HostsServicesCatalogPlan(
            groups=groups,
            new_selection=new_selection,
            selection_migrated=dict(current_selection) != new_selection,
        )

    @staticmethod
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

    def build_direct_toggle_plan(
        self,
        *,
        current_selection: dict[str, str],
        service_name: str,
        checked: bool,
    ) -> HostsSelectionMutationPlan:
        direct_profile = self.get_direct_profile_name()
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

    @staticmethod
    def build_reset_selection_plan() -> HostsSelectionMutationPlan:
        return HostsSelectionMutationPlan(
            new_selection={},
            changed=True,
            apply_now=False,
        )

    def build_bulk_profile_selection_plan(
        self,
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

    @staticmethod
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

    @staticmethod
    def get_hosts_path_str() -> str:
        import os

        try:
            if os.name == "nt":
                sys_root = os.environ.get("SystemRoot") or os.environ.get("WINDIR")
                if sys_root:
                    return os.path.join(sys_root, "System32", "drivers", "etc", "hosts")
            return os.path.join(get_system32_path(), "drivers", "etc", "hosts")
        except Exception:
            return os.path.join(get_system32_path(), "drivers", "etc", "hosts")

    @staticmethod
    def open_hosts_file() -> HostsOperationResult:
        import ctypes
        import os

        hosts_path = HostsPageController.get_hosts_path_str()
        if not os.path.exists(hosts_path):
            return HostsOperationResult(False, f"Файл не найден: {hosts_path}")

        try:
            ctypes.windll.shell32.ShellExecuteW(None, "runas", "notepad.exe", hosts_path, None, 1)
            return HostsOperationResult(True, hosts_path)
        except Exception as exc:
            return HostsOperationResult(False, str(exc))
