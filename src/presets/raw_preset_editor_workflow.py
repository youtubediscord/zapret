"""Workflow сырого редактора preset-файла."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class RawPresetLoadResult:
    text: str
    footer_text: str


@dataclass(frozen=True)
class RawPresetSaveResult:
    updated: object
    path: Path
    footer_text: str


def load_raw_preset_text(path: Path | None) -> RawPresetLoadResult:
    """Читает текст preset-файла для редактора."""
    if path is None or not path.exists():
        return RawPresetLoadResult(text="", footer_text="Файл не найден")
    return RawPresetLoadResult(
        text=path.read_text(encoding="utf-8", errors="replace"),
        footer_text="Загружено",
    )


def save_raw_preset_text(
    *,
    presets_feature,
    launch_method: str | None,
    file_name: str,
    source_text: str,
    publish_content_changed: bool = True,
) -> RawPresetSaveResult:
    """Сохраняет текст preset-файла через presets feature."""
    if not file_name:
        raise ValueError("Не удалось определить имя файла пресета для сохранения.")
    updated = presets_feature.save_preset_source_by_file_name(
        launch_method,
        file_name,
        source_text,
        publish_content_changed=publish_content_changed,
    )
    path = presets_feature.get_preset_source_path_by_file_name(
        launch_method,
        updated.file_name,
    )
    return RawPresetSaveResult(
        updated=updated,
        path=path,
        footer_text=f"Сохранено {datetime.now().strftime('%H:%M:%S')}",
    )


def get_raw_preset_source_path(*, presets_feature, launch_method: str | None, file_name: str) -> Path:
    return presets_feature.get_preset_source_path_by_file_name(
        launch_method,
        str(file_name or "").strip(),
    )


def get_raw_preset_manifest(*, presets_feature, launch_method: str | None, file_name: str):
    if not file_name:
        return None
    return presets_feature.get_preset_manifest_by_file_name(
        launch_method,
        file_name,
    )


def is_builtin_raw_preset(*, presets_feature, launch_method: str | None, file_name: str) -> bool:
    manifest = get_raw_preset_manifest(
        presets_feature=presets_feature,
        launch_method=launch_method,
        file_name=file_name,
    )
    return bool(manifest is not None and str(manifest.kind or "").strip().lower() == "builtin")


def open_raw_preset_source_file(*, presets_feature, path: Path | None) -> None:
    if path is None:
        return
    presets_feature.open_preset_source_file(path)


def rename_raw_preset(*, presets_feature, launch_method: str | None, file_name: str, new_name: str):
    if not file_name:
        raise ValueError("Не удалось определить имя файла пресета для переименования.")
    return presets_feature.rename_preset_by_file_name(
        launch_method,
        file_name,
        new_name,
    )


def duplicate_raw_preset(*, presets_feature, launch_method: str | None, file_name: str, new_name: str):
    if not file_name:
        raise ValueError("Не удалось определить имя файла пресета для дублирования.")
    return presets_feature.duplicate_preset_by_file_name(
        launch_method,
        file_name,
        new_name,
    )


def export_raw_preset(*, presets_feature, launch_method: str | None, file_name: str, target_path: str) -> None:
    if not file_name:
        raise ValueError("Не удалось определить имя файла пресета для экспорта.")
    presets_feature.export_preset_plain_text(
        launch_method,
        file_name,
        target_path,
    )


def reset_raw_preset_to_builtin(*, presets_feature, launch_method: str | None, file_name: str):
    if not file_name:
        raise ValueError("Не удалось определить имя файла пресета для сброса.")
    return presets_feature.reset_preset_to_builtin_by_file_name(
        launch_method,
        file_name,
    )


def delete_raw_preset(*, presets_feature, launch_method: str | None, file_name: str) -> None:
    if not file_name:
        raise ValueError("Не удалось определить имя файла пресета для удаления.")
    presets_feature.delete_preset_by_file_name(
        launch_method,
        file_name,
    )


def get_selected_raw_preset_name(*, presets_feature, launch_method: str | None) -> str:
    selected = presets_feature.get_selected_source_preset_manifest(launch_method)
    return (selected.name if selected is not None else "").strip()


def get_selected_raw_preset_file_name(*, presets_feature, launch_method: str | None) -> str:
    return (presets_feature.get_selected_source_preset_file_name(launch_method) or "").strip()


def activate_raw_preset(*, presets_feature, launch_method: str | None, file_name: str) -> bool:
    if not file_name:
        return False
    presets_feature.activate_preset_file(
        launch_method,
        file_name,
    )
    return True


def publish_raw_preset_content_changed(*, presets_feature, launch_method: str | None, file_name: str) -> None:
    if not file_name:
        return
    publish = getattr(presets_feature, "publish_preset_content_changed", None)
    if callable(publish):
        publish(launch_method, file_name)


class RawPresetEditorController:
    """Действия raw preset editor без привязки к QWidget."""

    def __init__(self, *, presets_feature, launch_method: str | None) -> None:
        self._presets = presets_feature
        self._launch_method = launch_method

    @property
    def launch_method(self) -> str | None:
        return self._launch_method

    def source_path(self, file_name: str) -> Path:
        return get_raw_preset_source_path(
            presets_feature=self._presets,
            launch_method=self._launch_method,
            file_name=file_name,
        )

    def manifest(self, file_name: str):
        return get_raw_preset_manifest(
            presets_feature=self._presets,
            launch_method=self._launch_method,
            file_name=file_name,
        )

    def is_builtin(self, file_name: str) -> bool:
        return is_builtin_raw_preset(
            presets_feature=self._presets,
            launch_method=self._launch_method,
            file_name=file_name,
        )

    def load_text(self, path: Path | None) -> RawPresetLoadResult:
        return load_raw_preset_text(path)

    def create_load_worker(self, request_id: int, path: Path | None, parent=None):
        from presets.raw_preset_loader import RawPresetLoadWorker

        return RawPresetLoadWorker(request_id, self, path, parent)

    def save_text(
        self,
        *,
        file_name: str,
        source_text: str,
        publish_content_changed: bool = True,
    ) -> RawPresetSaveResult:
        return save_raw_preset_text(
            presets_feature=self._presets,
            launch_method=self._launch_method,
            file_name=file_name,
            source_text=source_text,
            publish_content_changed=publish_content_changed,
        )

    def publish_content_changed(self, file_name: str) -> None:
        publish_raw_preset_content_changed(
            presets_feature=self._presets,
            launch_method=self._launch_method,
            file_name=file_name,
        )

    def open_source_file(self, path: Path | None) -> None:
        open_raw_preset_source_file(
            presets_feature=self._presets,
            path=path,
        )

    def rename(self, *, file_name: str, new_name: str):
        return rename_raw_preset(
            presets_feature=self._presets,
            launch_method=self._launch_method,
            file_name=file_name,
            new_name=new_name,
        )

    def duplicate(self, *, file_name: str, new_name: str):
        return duplicate_raw_preset(
            presets_feature=self._presets,
            launch_method=self._launch_method,
            file_name=file_name,
            new_name=new_name,
        )

    def export(self, *, file_name: str, target_path: str) -> None:
        export_raw_preset(
            presets_feature=self._presets,
            launch_method=self._launch_method,
            file_name=file_name,
            target_path=target_path,
        )

    def reset_to_builtin(self, *, file_name: str):
        return reset_raw_preset_to_builtin(
            presets_feature=self._presets,
            launch_method=self._launch_method,
            file_name=file_name,
        )

    def delete(self, *, file_name: str) -> None:
        delete_raw_preset(
            presets_feature=self._presets,
            launch_method=self._launch_method,
            file_name=file_name,
        )

    def selected_name(self) -> str:
        return get_selected_raw_preset_name(
            presets_feature=self._presets,
            launch_method=self._launch_method,
        )

    def selected_file_name(self) -> str:
        return get_selected_raw_preset_file_name(
            presets_feature=self._presets,
            launch_method=self._launch_method,
        )

    def activate(self, *, file_name: str) -> bool:
        return activate_raw_preset(
            presets_feature=self._presets,
            launch_method=self._launch_method,
            file_name=file_name,
        )
