from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class DiagnosticsFeature:
    create_connection_test_worker: Callable


def build_diagnostics_feature() -> DiagnosticsFeature:
    def _commands():
        from diagnostics import commands as diagnostics_commands

        return diagnostics_commands

    return DiagnosticsFeature(
        create_connection_test_worker=lambda *args, **kwargs: _commands().create_connection_test_worker(*args, **kwargs),
    )
