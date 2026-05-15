from __future__ import annotations

from settings.mode import ZAPRET1_MODE, ZAPRET2_MODE


def bind_preset_stores_to_runtime(*, presets_feature, preset_runtime) -> None:
    """Связывает события preset-ов с runtime-координатором.

    Это часть preset-логики: выбранный source preset изменился, значит runtime
    должен знать о смене, переименовании или сохранении файла.
    """
    if presets_feature is None or preset_runtime is None:
        return

    for method in (ZAPRET2_MODE, ZAPRET1_MODE):
        presets_feature.connect_preset_signals(
            method,
            on_switched=lambda file_name, m=method: preset_runtime.handle_preset_switched(
                m,
                file_name,
            ),
            on_identity_changed=lambda file_name, m=method: preset_runtime.handle_preset_identity_changed(
                m,
                file_name,
            ),
            on_content_changed=lambda file_name, m=method: preset_runtime.handle_preset_content_changed(
                m,
                file_name,
            ),
        )

    preset_runtime.setup_active_preset_file_watcher()


__all__ = ["bind_preset_stores_to_runtime"]
