from __future__ import annotations

from hosts.commands import (
    add_adobe_domains,
    apply_service_profiles,
    clear_hosts,
    create_hosts_manager,
    get_hosts_state,
    read_hosts_file,
    remove_adobe_domains,
    restore_hosts_permissions,
    write_hosts_file,
)
from hosts.state import HostsCommandResult, HostsState

__all__ = [
    "HostsCommandResult",
    "HostsState",
    "add_adobe_domains",
    "apply_service_profiles",
    "clear_hosts",
    "create_hosts_manager",
    "get_hosts_state",
    "read_hosts_file",
    "remove_adobe_domains",
    "restore_hosts_permissions",
    "write_hosts_file",
]
