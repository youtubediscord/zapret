from __future__ import annotations

from hosts.state import HostsCommandResult, HostsState


def read_hosts_file():
    from hosts.hosts import safe_read_hosts_file

    return safe_read_hosts_file()


def write_hosts_file(content):
    from hosts.hosts import safe_write_hosts_file

    return safe_write_hosts_file(content)


def restore_hosts_permissions() -> HostsCommandResult:
    from hosts.hosts import restore_hosts_permissions as _restore_hosts_permissions

    success, message = _restore_hosts_permissions()
    return HostsCommandResult(success=bool(success), message=str(message or ""))


def create_hosts_manager(status_callback=None):
    from hosts.hosts import HostsManager

    return HostsManager(status_callback=status_callback)


def get_hosts_state(hosts_manager=None) -> HostsState:
    manager = hosts_manager or create_hosts_manager()
    error = ""
    accessible = False
    active_domains: set[str] = set()
    adobe_active = False

    try:
        accessible = bool(manager.is_hosts_file_accessible())
    except Exception as exc:
        error = str(exc)

    if not error:
        try:
            active_domains = set((manager.get_active_domains_map() or {}).keys())
        except Exception as exc:
            error = str(exc)
            active_domains = set()

    try:
        adobe_active = bool(manager.is_adobe_domains_active())
    except Exception:
        adobe_active = False

    return HostsState(
        accessible=accessible,
        active_domains=frozenset(active_domains),
        adobe_active=adobe_active,
        error=error,
    )


def apply_service_profiles(hosts_manager, service_dns: dict[str, str]) -> HostsCommandResult:
    success = bool(hosts_manager.apply_service_dns_selections(service_dns or {}))
    message = "Применено" if success else getattr(hosts_manager, "last_status", None) or "Ошибка"
    return HostsCommandResult(success=success, message=message)


def clear_hosts(hosts_manager) -> HostsCommandResult:
    success = bool(hosts_manager.clear_hosts_file())
    message = "Hosts очищен" if success else getattr(hosts_manager, "last_status", None) or "Ошибка"
    return HostsCommandResult(success=success, message=message)


def add_adobe_domains(hosts_manager) -> HostsCommandResult:
    success = bool(hosts_manager.add_adobe_domains())
    message = "Adobe заблокирован" if success else getattr(hosts_manager, "last_status", None) or "Ошибка"
    return HostsCommandResult(success=success, message=message)


def remove_adobe_domains(hosts_manager) -> HostsCommandResult:
    success = bool(hosts_manager.remove_adobe_domains())
    message = "Adobe разблокирован" if success else getattr(hosts_manager, "last_status", None) or "Ошибка"
    return HostsCommandResult(success=success, message=message)
