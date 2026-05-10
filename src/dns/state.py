from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class DnsState:
    """Текущий снимок DNS-страницы.

    Это не UI-состояние виджетов, а данные DNS-слоя: адаптеры, текущие DNS,
    доступность IPv6 и состояние принудительного DNS.
    """

    adapters: tuple[tuple[str, str], ...] = ()
    dns_info: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    ipv6_available: bool = False
    force_dns_enabled: bool = False
    active_profile: str = ""
    last_message: str = ""
    error: str = ""

    @property
    def adapters_count(self) -> int:
        return len(self.adapters)


@dataclass(frozen=True, slots=True)
class DnsCommandResult:
    success: bool
    message: str = ""
    affected_count: int = 0
    total_count: int = 0
    error: str = ""
