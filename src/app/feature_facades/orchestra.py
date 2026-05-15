from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import orchestra.commands as orchestra_commands


@dataclass(slots=True)
class OrchestraFeature:
    whitelist_runtime_service: Any
    runner: Any = None

    @property
    def ASKEY_ALL(self):
        return orchestra_commands.ASKEY_ALL

    def ensure_runner(self):
        if self.runner is None:
            from orchestra.orchestra_runner import OrchestraRunner

            self.runner = OrchestraRunner()
        return self.runner

    def is_running(self) -> bool:
        runner = self.runner
        if runner is None:
            return False
        try:
            return bool(runner.is_running())
        except Exception:
            return False

    def stop_runner(self) -> bool:
        runner = self.runner
        if runner is None:
            return True
        try:
            runner.stop()
            return True
        except Exception:
            return False

    def clear_learned_data(self) -> None:
        runner = self.runner
        if runner is not None:
            runner.clear_learned_data()

    def set_setting(self, key: str, value) -> None:
        from settings.dpi.public import set_orchestra_setting

        set_orchestra_setting(key, value, runner=self.runner)

    def get_whitelist_snapshot(self, runner):
        return orchestra_commands.get_whitelist_snapshot(
            runner,
            whitelist_service=self.whitelist_runtime_service,
        )

    def add_whitelist_domain(self, runner, domain: str) -> bool:
        return bool(
            orchestra_commands.add_whitelist_domain(
                runner,
                domain,
                whitelist_service=self.whitelist_runtime_service,
            )
        )

    def remove_whitelist_domain(self, runner, domain: str) -> bool:
        return bool(
            orchestra_commands.remove_whitelist_domain(
                runner,
                domain,
                whitelist_service=self.whitelist_runtime_service,
            )
        )

    def clear_whitelist_user_domains(self, runner) -> int:
        return int(
            orchestra_commands.clear_whitelist_user_domains(
                runner,
                whitelist_service=self.whitelist_runtime_service,
            )
            or 0
        )

    def create_loaded_blocked_manager(self):
        return orchestra_commands.create_loaded_blocked_manager()

    def create_loaded_locked_manager(self):
        return orchestra_commands.create_loaded_locked_manager()

    def is_default_blocked_pass_domain(self, hostname: str) -> bool:
        return bool(orchestra_commands.is_default_blocked_pass_domain(hostname))


def build_orchestra_feature() -> OrchestraFeature:
    from core.runtime.orchestra_whitelist_runtime_service import OrchestraWhitelistRuntimeService

    return OrchestraFeature(
        whitelist_runtime_service=OrchestraWhitelistRuntimeService(),
    )
