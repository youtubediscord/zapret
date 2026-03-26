from __future__ import annotations

import subprocess

from .commands import build_launcher_command


class SchedulerAutostartManager:
    TASK_NAME = "ZapretGUI_AutoStart"
    LEGACY_TASKS = ("ZapretLauncher-winws1", "ZapretLauncher-winws2")

    @staticmethod
    def _task_name() -> str:
        return SchedulerAutostartManager.TASK_NAME

    def install(self, engine: str) -> None:
        _ = str(engine or "").strip().lower()

        for other in self.LEGACY_TASKS:
            subprocess.run(
                ["schtasks", "/Delete", "/TN", other, "/F"],
                capture_output=True,
                text=True,
            )

        subprocess.run(
            ["schtasks", "/Delete", "/TN", self._task_name(), "/F"],
            capture_output=True,
            text=True,
        )

        launcher = build_launcher_command("")
        command_line = " ".join([f'"{launcher.command}"', *launcher.arguments])
        subprocess.run(
            [
                "schtasks",
                "/Create",
                "/TN",
                self._task_name(),
                "/TR",
                command_line,
                "/SC",
                "ONLOGON",
                "/RL",
                "HIGHEST",
                "/F",
            ],
            capture_output=True,
            text=True,
        )
