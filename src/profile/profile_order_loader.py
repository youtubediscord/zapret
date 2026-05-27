from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from log.log import log


class ProfileOrderListLoadWorker(QThread):
    loaded = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, profile_feature, launch_method: str, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._profile = profile_feature
        self._launch_method = str(launch_method or "").strip()

    def run(self) -> None:
        try:
            payload = self._profile.list_preset_order_profiles(self._launch_method)
        except Exception as exc:
            log(f"ProfileOrderListLoadWorker: не удалось прочитать порядок profile-ов: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.loaded.emit(self._request_id, payload)


class ProfilePresetOrderMoveWorker(QThread):
    moved = pyqtSignal(int, str, str, str, object)
    failed = pyqtSignal(int, str)

    def __init__(
        self,
        request_id: int,
        profile_feature,
        launch_method: str,
        *,
        action: str,
        source_profile_key: str,
        destination_profile_key: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._profile = profile_feature
        self._launch_method = str(launch_method or "").strip()
        self._action = str(action or "").strip()
        self._source_profile_key = str(source_profile_key or "").strip()
        self._destination_profile_key = str(destination_profile_key or "").strip()

    def run(self) -> None:
        try:
            if self._action == "before":
                result = self._profile.move_preset_profile_before(
                    self._launch_method,
                    self._source_profile_key,
                    self._destination_profile_key,
                )
            elif self._action == "after":
                result = self._profile.move_preset_profile_after(
                    self._launch_method,
                    self._source_profile_key,
                    self._destination_profile_key,
                )
            elif self._action == "end":
                result = self._profile.move_preset_profile_to_end(
                    self._launch_method,
                    self._source_profile_key,
                )
            else:
                raise ValueError(f"Неизвестное перемещение profile: {self._action}")
        except Exception as exc:
            log(f"ProfilePresetOrderMoveWorker: не удалось переместить profile: {exc}", "ERROR")
            self.failed.emit(self._request_id, str(exc))
            return
        self.moved.emit(
            self._request_id,
            self._action,
            self._source_profile_key,
            self._destination_profile_key,
            result,
        )


__all__ = ["ProfileOrderListLoadWorker", "ProfilePresetOrderMoveWorker"]
