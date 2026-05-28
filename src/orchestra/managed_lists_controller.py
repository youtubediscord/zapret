"""Контроллер managed-списков orchestra для UI-страниц."""

from __future__ import annotations

from orchestra.managed_lists_workflow import (
    add_blocked_strategy,
    add_locked_strategy,
    add_whitelist_domain,
    build_blocked_snapshot,
    build_locked_snapshot,
    change_blocked_strategy,
    change_locked_strategy,
    clear_locked_strategies,
    clear_user_blocked_strategies,
    clear_whitelist_user_domains,
    count_locked_strategies,
    count_user_blocked_strategies,
    current_locked_strategy,
    is_blocked_strategy,
    reload_blocked_snapshot,
    reload_locked_snapshot,
    remove_blocked_strategy,
    remove_locked_strategy,
    remove_whitelist_domain,
)


class BlockedStrategiesController:
    """Единая точка действий для страницы заблокированных стратегий."""

    def __init__(self, orchestra) -> None:
        self._orchestra = orchestra
        self.askey_all = tuple(orchestra.ASKEY_ALL)
        self._direct_blocked_by_askey = {askey: {} for askey in self.askey_all}

    @property
    def runner(self):
        return self._orchestra.runner

    def reload_snapshot(self):
        snapshot = reload_blocked_snapshot(
            orchestra=self._orchestra,
            runner=self.runner,
            askey_all=self.askey_all,
        )
        self._remember_direct_snapshot(snapshot)
        return snapshot

    def create_snapshot_load_worker(self, request_id: int, parent=None):
        from orchestra.managed_lists_workers import OrchestraManagedSnapshotLoadWorker

        return OrchestraManagedSnapshotLoadWorker(request_id, self, parent)

    def load_direct_snapshot(self) -> None:
        snapshot = reload_blocked_snapshot(
            orchestra=self._orchestra,
            runner=None,
            askey_all=self.askey_all,
        )
        self._direct_blocked_by_askey = snapshot.direct_blocked_by_askey or {
            askey: {} for askey in self.askey_all
        }

    def current_snapshot(self):
        snapshot = build_blocked_snapshot(
            orchestra=self._orchestra,
            runner=self.runner,
            direct_blocked_by_askey=self._direct_blocked_by_askey,
            askey_all=self.askey_all,
        )
        self._remember_direct_snapshot(snapshot)
        return snapshot

    def change_strategy(self, *, hostname: str, old_strategy: int, new_strategy: int, askey: str):
        return change_blocked_strategy(
            self.runner,
            hostname=hostname,
            old_strategy=old_strategy,
            new_strategy=new_strategy,
            askey=askey,
        )

    def remove_strategy(self, *, hostname: str, strategy: int, askey: str):
        return remove_blocked_strategy(
            self.runner,
            hostname=hostname,
            strategy=strategy,
            askey=askey,
        )

    def add_strategy(self, *, domain: str, strategy: int, askey: str):
        return add_blocked_strategy(
            self.runner,
            domain=domain,
            strategy=strategy,
            askey=askey,
        )

    def user_count(self) -> int:
        return count_user_blocked_strategies(self.runner, askey_all=self.askey_all)

    def clear_user_strategies(self, *, user_count: int):
        return clear_user_blocked_strategies(self.runner, user_count=user_count)

    def _remember_direct_snapshot(self, snapshot) -> None:
        if snapshot.direct_blocked_by_askey is not None:
            self._direct_blocked_by_askey = snapshot.direct_blocked_by_askey


class LockedStrategiesController:
    """Единая точка действий для страницы залоченных стратегий."""

    def __init__(self, orchestra) -> None:
        self._orchestra = orchestra
        self.askey_all = tuple(orchestra.ASKEY_ALL)
        self._direct_locked_by_askey = {askey: {} for askey in self.askey_all}

    @property
    def runner(self):
        return self._orchestra.runner

    def reload_snapshot(self):
        snapshot = reload_locked_snapshot(
            orchestra=self._orchestra,
            runner=self.runner,
            askey_all=self.askey_all,
        )
        self._remember_direct_snapshot(snapshot)
        return snapshot

    def create_snapshot_load_worker(self, request_id: int, parent=None):
        from orchestra.managed_lists_workers import OrchestraManagedSnapshotLoadWorker

        return OrchestraManagedSnapshotLoadWorker(request_id, self, parent)

    def load_direct_snapshot(self) -> None:
        snapshot = reload_locked_snapshot(
            orchestra=self._orchestra,
            runner=None,
            askey_all=self.askey_all,
        )
        self._direct_locked_by_askey = snapshot.direct_locked_by_askey or {
            askey: {} for askey in self.askey_all
        }

    def current_snapshot(self):
        snapshot = build_locked_snapshot(
            orchestra=self._orchestra,
            runner=self.runner,
            direct_locked_by_askey=self._direct_locked_by_askey,
            askey_all=self.askey_all,
        )
        self._remember_direct_snapshot(snapshot)
        return snapshot

    def is_blocked_strategy(self, *, domain: str, strategy: int) -> bool:
        return is_blocked_strategy(
            orchestra=self._orchestra,
            runner=self.runner,
            domain=domain,
            strategy=strategy,
        )

    def current_strategy(self, *, domain: str, askey: str) -> int:
        return current_locked_strategy(
            runner=self.runner,
            direct_locked_by_askey=self._direct_locked_by_askey,
            domain=domain,
            askey=askey,
        )

    def change_strategy(self, *, domain: str, new_strategy: int, askey: str):
        return change_locked_strategy(
            orchestra=self._orchestra,
            runner=self.runner,
            direct_locked_by_askey=self._direct_locked_by_askey,
            domain=domain,
            new_strategy=new_strategy,
            askey=askey,
        )

    def add_strategy(self, *, domain: str, strategy: int, askey: str):
        return add_locked_strategy(
            orchestra=self._orchestra,
            runner=self.runner,
            direct_locked_by_askey=self._direct_locked_by_askey,
            domain=domain,
            strategy=strategy,
            askey=askey,
        )

    def remove_strategy(self, *, domain: str, askey: str):
        return remove_locked_strategy(
            orchestra=self._orchestra,
            runner=self.runner,
            direct_locked_by_askey=self._direct_locked_by_askey,
            domain=domain,
            askey=askey,
        )

    def count(self) -> int:
        return count_locked_strategies(self.runner)

    def clear_strategies(self, *, total: int):
        return clear_locked_strategies(
            self.runner,
            askey_all=self.askey_all,
            total=total,
        )

    def _remember_direct_snapshot(self, snapshot) -> None:
        if snapshot.direct_locked_by_askey is not None:
            self._direct_locked_by_askey = snapshot.direct_locked_by_askey


class WhitelistController:
    """Единая точка действий для страницы whitelist оркестратора."""

    def __init__(self, orchestra) -> None:
        self._orchestra = orchestra

    @property
    def runner(self):
        return self._orchestra.runner

    def is_running(self) -> bool:
        runner = self.runner
        return bool(runner is not None and runner.is_running())

    def snapshot(self, *, refresh: bool):
        return self._orchestra.get_whitelist_snapshot(
            self.runner,
            refresh=refresh,
        )

    def create_action_worker(
        self,
        request_id: int,
        *,
        action: str,
        domain: str = "",
        user_domains: list[str] | None = None,
        parent=None,
    ):
        from orchestra.managed_lists_workers import OrchestraWhitelistActionWorker

        return OrchestraWhitelistActionWorker(
            request_id,
            self,
            action=action,
            domain=domain,
            user_domains=user_domains,
            parent=parent,
        )

    def add_domain(self, *, domain: str):
        return add_whitelist_domain(
            orchestra=self._orchestra,
            runner=self.runner,
            domain=domain,
        )

    def remove_domain(self, *, domain: str):
        return remove_whitelist_domain(
            orchestra=self._orchestra,
            runner=self.runner,
            domain=domain,
        )

    def user_domains(self) -> list[str]:
        snapshot = self.snapshot(refresh=True)
        return [domain for domain, is_default in snapshot.entries if not is_default]

    def clear_user_domains(self, *, user_domains: list[str]):
        return clear_whitelist_user_domains(
            orchestra=self._orchestra,
            runner=self.runner,
            user_domains=user_domains,
        )
