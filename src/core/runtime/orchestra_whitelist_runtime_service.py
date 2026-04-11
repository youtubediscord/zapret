from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from config.reg import reg
from orchestra.orchestra_runner import OrchestraRunner, REGISTRY_ORCHESTRA


@dataclass(frozen=True, slots=True)
class OrchestraWhitelistSnapshot:
    revision: tuple[object, ...]
    entries: tuple[tuple[str, bool], ...]
    orchestra_running: bool


class OrchestraWhitelistRuntimeService:
    """Service-owned access layer for orchestra whitelist state.

    Страница whitelist не должна сама создавать и хранить запасной
    OrchestraRunner. Этот сервис держит detached runner, когда живого
    orchestra_runner у окна нет, и выдаёт готовый snapshot данных.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._detached_runner: OrchestraRunner | None = None
        self._cached_snapshot: OrchestraWhitelistSnapshot | None = None

    def _live_runner(self, window) -> OrchestraRunner | None:
        if window is None:
            return None
        runner = getattr(window, "orchestra_runner", None)
        return runner if runner is not None else None

    def _detached_runner_instance(self) -> OrchestraRunner:
        with self._lock:
            if self._detached_runner is None:
                self._detached_runner = OrchestraRunner()
            return self._detached_runner

    def _resolve_runner(self, window) -> OrchestraRunner:
        live_runner = self._live_runner(window)
        if live_runner is not None:
            return live_runner
        return self._detached_runner_instance()

    @staticmethod
    def _registry_revision() -> str:
        raw = reg(REGISTRY_ORCHESTRA, "Whitelist")
        return str(raw or "")

    def _revision(self, window) -> tuple[object, ...]:
        live_runner = self._live_runner(window)
        is_running = bool(live_runner is not None and live_runner.is_running())
        return (
            bool(live_runner is not None),
            is_running,
            self._registry_revision(),
        )

    def invalidate(self) -> None:
        with self._lock:
            self._cached_snapshot = None

    def get_snapshot(self, window=None, *, refresh: bool = False) -> OrchestraWhitelistSnapshot:
        revision = self._revision(window)
        with self._lock:
            if not refresh and self._cached_snapshot is not None and self._cached_snapshot.revision == revision:
                return self._cached_snapshot

        entries: tuple[tuple[str, bool], ...] = ()
        orchestra_running = False

        try:
            runner = self._resolve_runner(window)
            load_whitelist = getattr(runner, "load_whitelist", None)
            if callable(load_whitelist):
                load_whitelist()
            raw_entries = runner.get_whitelist() or []
            entries = tuple(
                (
                    str(entry.get("domain") or "").strip(),
                    bool(entry.get("is_default")),
                )
                for entry in raw_entries
                if str(entry.get("domain") or "").strip()
            )
            orchestra_running = bool(self._live_runner(window) is not None and self._live_runner(window).is_running())
        except Exception:
            entries = ()
            orchestra_running = False

        snapshot = OrchestraWhitelistSnapshot(
            revision=revision,
            entries=entries,
            orchestra_running=orchestra_running,
        )
        with self._lock:
            self._cached_snapshot = snapshot
        return snapshot

    def add_domain(self, window, domain: str) -> bool:
        runner = self._resolve_runner(window)
        load_whitelist = getattr(runner, "load_whitelist", None)
        if callable(load_whitelist):
            load_whitelist()
        ok = bool(runner.add_to_whitelist(domain))
        self.invalidate()
        return ok

    def remove_domain(self, window, domain: str) -> bool:
        runner = self._resolve_runner(window)
        load_whitelist = getattr(runner, "load_whitelist", None)
        if callable(load_whitelist):
            load_whitelist()
        ok = bool(runner.remove_from_whitelist(domain))
        self.invalidate()
        return ok

    def clear_user_domains(self, window, domains: list[str]) -> int:
        runner = self._resolve_runner(window)
        load_whitelist = getattr(runner, "load_whitelist", None)
        if callable(load_whitelist):
            load_whitelist()

        removed = 0
        for domain in domains:
            if runner.remove_from_whitelist(domain):
                removed += 1

        if removed:
            self.invalidate()
        return removed
