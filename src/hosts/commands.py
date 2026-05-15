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


def create_hosts_runtime(status_callback=None):
    return create_hosts_manager(status_callback=status_callback)


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


def execute_hosts_operation(hosts_manager, operation: str, payload=None) -> HostsCommandResult:
    if operation == "apply_selection":
        return apply_service_profiles(hosts_manager, payload or {})
    if operation == "clear_all":
        return clear_hosts(hosts_manager)
    if operation == "adobe_add":
        return add_adobe_domains(hosts_manager)
    if operation == "adobe_remove":
        return remove_adobe_domains(hosts_manager)
    return HostsCommandResult(success=False, message="Неизвестная операция")


def load_user_selection() -> dict[str, str]:
    from hosts.proxy_domains import load_user_hosts_selection

    try:
        return dict(load_user_hosts_selection() or {})
    except Exception:
        return {}


def save_user_selection(selection: dict[str, str]) -> bool:
    from hosts.proxy_domains import save_user_hosts_selection

    try:
        return bool(save_user_hosts_selection(dict(selection)))
    except Exception:
        return False


def ensure_ipv6_catalog_sections() -> tuple[bool, bool]:
    from hosts.proxy_domains import ensure_ipv6_catalog_sections_if_available

    try:
        return ensure_ipv6_catalog_sections_if_available()
    except Exception:
        return (False, False)


def get_catalog_signature():
    from hosts.proxy_domains import get_hosts_catalog_signature

    try:
        return get_hosts_catalog_signature()
    except Exception:
        return None


def invalidate_catalog_cache() -> None:
    from hosts.proxy_domains import invalidate_hosts_catalog_cache

    try:
        invalidate_hosts_catalog_cache()
    except Exception:
        pass


def read_active_domains_map(hosts_manager) -> dict[str, str]:
    if hosts_manager is None:
        return {}
    try:
        return dict(hosts_manager.get_active_domains_map() or {})
    except Exception:
        return {}


def get_hosts_path_str() -> str:
    import os

    from utils.subproc import get_system32_path

    try:
        if os.name == "nt":
            sys_root = os.environ.get("SystemRoot") or os.environ.get("WINDIR")
            if sys_root:
                return os.path.join(sys_root, "System32", "drivers", "etc", "hosts")
        return os.path.join(get_system32_path(), "drivers", "etc", "hosts")
    except Exception:
        return os.path.join(get_system32_path(), "drivers", "etc", "hosts")


def open_hosts_file() -> HostsCommandResult:
    import ctypes
    import os

    hosts_path = get_hosts_path_str()
    if not os.path.exists(hosts_path):
        return HostsCommandResult(False, f"Файл не найден: {hosts_path}")

    try:
        ctypes.windll.shell32.ShellExecuteW(None, "runas", "notepad.exe", hosts_path, None, 1)
        return HostsCommandResult(True, hosts_path)
    except Exception as exc:
        return HostsCommandResult(False, str(exc))
