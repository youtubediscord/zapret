from __future__ import annotations

from dataclasses import dataclass
import os
import sys


@dataclass(frozen=True)
class LauncherCommand:
    command: str
    arguments: list[str]


def build_launcher_command(engine: str, source: str = "autostart") -> LauncherCommand:
    _ = (engine, source)
    if getattr(sys, "frozen", False):
        command = sys.executable
    else:
        command = os.path.abspath(sys.argv[0])

    arguments = ["--tray"]
    return LauncherCommand(command=command, arguments=arguments)
