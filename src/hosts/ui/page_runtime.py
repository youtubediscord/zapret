from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class HostsPageRuntimeCache:
    runtime_state: Any = None
    active_domains: set[str] | None = None

    def invalidate(self) -> None:
        self.runtime_state = None
        self.active_domains = None


def create_runtime_cache() -> HostsPageRuntimeCache:
    return HostsPageRuntimeCache()


def create_page_hosts_runtime(create_hosts_runtime_fn):
    try:
        from log.log import log

        return create_hosts_runtime_fn(status_callback=lambda m: log(f"Hosts: {m}", "INFO"))
    except Exception as e:
        from log.log import log

        log(f"Ошибка инициализации Hosts runtime: {e}", "ERROR")
        return None
