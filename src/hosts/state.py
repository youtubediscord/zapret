from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HostsState:
    accessible: bool = False
    active_domains: frozenset[str] = frozenset()
    adobe_active: bool = False
    last_message: str = ""
    error: str = ""

    @property
    def error_message(self) -> str | None:
        return self.error or None


@dataclass(frozen=True, slots=True)
class HostsCommandResult:
    success: bool
    message: str = ""
    error: str = ""
