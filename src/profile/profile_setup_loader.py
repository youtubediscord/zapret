from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from log.log import log


class ProfileSetupLoadWorker(QThread):
    loaded = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, controller, profile_key: str, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._controller = controller
        self._profile_key = str(profile_key or "").strip()

    def run(self) -> None:
        try:
            payload = self._controller.load(self._profile_key)
        except Exception as exc:
            log(f"ProfileSetupLoadWorker: не удалось загрузить profile setup: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.loaded.emit(self._request_id, payload)


class ProfileListFileLoadWorker(QThread):
    loaded = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(
        self,
        request_id: int,
        controller,
        profile_key: str,
        *,
        filter_kind: str = "",
        filter_value: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._controller = controller
        self._profile_key = str(profile_key or "").strip()
        self._filter_kind = str(filter_kind or "").strip()
        self._filter_value = str(filter_value or "").strip()

    def run(self) -> None:
        try:
            state = self._controller.load_list_file_editor_state(
                self._profile_key,
                filter_kind=self._filter_kind,
                filter_value=self._filter_value,
            )
        except Exception as exc:
            log(f"ProfileListFileLoadWorker: не удалось загрузить файл списка profile: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.loaded.emit(self._request_id, state)


class ProfileStrategyApplyWorker(QThread):
    applied = pyqtSignal(int, str, str)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, controller, profile_key: str, strategy_id: str, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._controller = controller
        self._profile_key = str(profile_key or "").strip()
        self._strategy_id = str(strategy_id or "").strip()

    def run(self) -> None:
        try:
            profile_key = self._controller.apply_strategy(
                profile_key=self._profile_key,
                strategy_id=self._strategy_id,
            )
        except Exception as exc:
            log(f"ProfileStrategyApplyWorker: не удалось применить готовую стратегию: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        if not profile_key:
            self.failed.emit(self._request_id, "Стратегия не применена")
            return
        self.applied.emit(self._request_id, str(profile_key), self._strategy_id)
