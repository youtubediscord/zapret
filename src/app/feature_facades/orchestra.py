from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True, init=False)
class OrchestraFeature:
    _whitelist_runtime_service: Any | None = field(default=None, repr=False, compare=False)
    runner: Any = None

    def __init__(self, whitelist_runtime_service: Any | None = None, runner: Any = None) -> None:
        self._whitelist_runtime_service = whitelist_runtime_service
        self.runner = runner

    @staticmethod
    def _commands():
        import orchestra.commands as orchestra_commands

        return orchestra_commands

    @staticmethod
    def _create_whitelist_runtime_service():
        from core.runtime.orchestra_whitelist_runtime_service import OrchestraWhitelistRuntimeService

        return OrchestraWhitelistRuntimeService()

    @property
    def whitelist_runtime_service(self):
        service = self._whitelist_runtime_service
        if service is None:
            service = self._create_whitelist_runtime_service()
            self._whitelist_runtime_service = service
        return service

    @property
    def ASKEY_ALL(self):
        return self._commands().ASKEY_ALL

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

    def create_setting_save_worker(self, request_id: int, *, key: str, value, parent=None):
        from orchestra.settings_worker import OrchestraSettingSaveWorker

        return OrchestraSettingSaveWorker(
            request_id,
            self,
            key=key,
            value=value,
            parent=parent,
        )

    def get_whitelist_snapshot(self, runner, *, refresh: bool = False):
        return self._commands().get_whitelist_snapshot(
            runner,
            whitelist_service=self.whitelist_runtime_service,
            refresh=refresh,
        )

    def add_whitelist_domain(self, runner, domain: str) -> bool:
        return bool(
            self._commands().add_whitelist_domain(
                runner,
                domain,
                whitelist_service=self.whitelist_runtime_service,
            )
        )

    def remove_whitelist_domain(self, runner, domain: str) -> bool:
        return bool(
            self._commands().remove_whitelist_domain(
                runner,
                domain,
                whitelist_service=self.whitelist_runtime_service,
            )
        )

    def clear_whitelist_user_domains(self, runner, domains: list[str]) -> int:
        return int(
            self._commands().clear_whitelist_user_domains(
                runner,
                domains,
                whitelist_service=self.whitelist_runtime_service,
            )
            or 0
        )

    def create_loaded_blocked_manager(self):
        return self._commands().create_loaded_blocked_manager()

    def create_loaded_locked_manager(self):
        return self._commands().create_loaded_locked_manager()

    def is_default_blocked_pass_domain(self, hostname: str) -> bool:
        return bool(self._commands().is_default_blocked_pass_domain(hostname))


def build_orchestra_feature() -> OrchestraFeature:
    return OrchestraFeature()
