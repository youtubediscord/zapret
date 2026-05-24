from __future__ import annotations

import time

from PyQt6.QtCore import QObject, pyqtSignal

from log.log import log


class HostsServicesCatalogWorker(QObject):
    loaded = pyqtSignal(object, object)
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(
        self,
        *,
        controller,
        hosts_runtime,
        current_selection: dict[str, str],
        direct_title: str,
        ai_title: str,
        other_title: str,
    ):
        super().__init__()
        self._controller = controller
        self._hosts_runtime = hosts_runtime
        self._current_selection = dict(current_selection or {})
        self._direct_title = str(direct_title or "")
        self._ai_title = str(ai_title or "")
        self._other_title = str(other_title or "")
        self._stopped = False

    def run(self) -> None:
        started_at = time.perf_counter()
        try:
            plan = self._controller.build_services_catalog_plan(
                hosts_runtime=self._hosts_runtime,
                current_selection=self._current_selection,
                direct_title=self._direct_title,
                ai_title=self._ai_title,
                other_title=self._other_title,
            )
            catalog_sig = self._controller.get_catalog_signature()
            if not self._stopped:
                self.loaded.emit(plan, catalog_sig)
        except Exception as exc:
            if not self._stopped:
                self.failed.emit(str(exc))
        finally:
            try:
                elapsed_ms = (time.perf_counter() - started_at) * 1000.0
                log(f"hosts_feature.services_catalog_worker.total: {elapsed_ms:.1f}ms", "DEBUG")
            except Exception:
                pass
            self.finished.emit()

    def stop(self) -> None:
        self._stopped = True


__all__ = ["HostsServicesCatalogWorker"]
