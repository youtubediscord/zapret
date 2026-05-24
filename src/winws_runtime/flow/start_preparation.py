from __future__ import annotations

from pathlib import Path

from log.log import log
from settings.mode import (
    is_orchestra_launch_method,
    is_preset_launch_method,
    is_zapret1_launch_method,
    is_zapret2_launch_method,
    normalize_launch_method,
)


from winws_runtime.runtime.start_workers import PreparedDpiStartRequest
from profile.launch_validation import (
    preset_filter_flags_for_launch_method,
    preset_has_enabled_profiles_for_launch,
)


def resolve_launch_method(launch_method=None) -> str:
    from settings.dpi.strategy_settings import get_strategy_launch_method

    return normalize_launch_method(launch_method or get_strategy_launch_method())


def resolve_method_name(launch_method: str) -> str:
    method = normalize_launch_method(launch_method, default="")
    if is_orchestra_launch_method(method):
        return "оркестр"
    if is_zapret2_launch_method(method):
        return "прямой winws2"
    if is_zapret1_launch_method(method):
        return "прямой winws1"
    return "классический"


def resolve_mode_name(selected_mode) -> str:
    if isinstance(selected_mode, tuple) and len(selected_mode) == 2:
        _, strategy_name = selected_mode
        return str(strategy_name or "Неизвестная стратегия")
    if isinstance(selected_mode, dict):
        return str(selected_mode.get("name", str(selected_mode)) or "Неизвестная стратегия")
    if isinstance(selected_mode, str):
        return str(selected_mode or "Неизвестная стратегия")
    return "Неизвестная стратегия"


def prepare_selected_mode_for_start(selected_mode, launch_method: str, *, presets_feature):
    method = normalize_launch_method(launch_method, default="")

    if is_orchestra_launch_method(method):
        return {"is_orchestra": True, "name": "Оркестр"}

    if selected_mode is not None and selected_mode != "default":
        return selected_mode

    if is_preset_launch_method(method):
        snapshot = presets_feature.get_launch_snapshot(
            method,
            require_filters=True,
        )
        log(f"Используется выбранный source-пресет: {snapshot.preset_path}", "INFO")
        return snapshot.to_selected_mode()

    raise RuntimeError("Неизвестный метод запуска")


def preset_filter_flags(launch_method: str) -> tuple[str, ...]:
    return preset_filter_flags_for_launch_method(launch_method)


def validate_preset_selected_mode(selected_mode, launch_method: str, *, prepared_text: str | None = None) -> None:
    method = normalize_launch_method(launch_method, default="")
    if not is_preset_launch_method(method):
        return
    if not isinstance(selected_mode, dict) or not bool(selected_mode.get("is_preset_file")):
        return

    preset_path = Path(str(selected_mode.get("preset_path") or "").strip())
    if not preset_path.exists():
        raise RuntimeError("Preset файл не найден. Создайте пресет в настройках")

    try:
        content = (
            str(prepared_text or "").strip()
            if prepared_text is not None
            else preset_path.read_text(encoding="utf-8").strip()
        )
        if not preset_has_enabled_profiles_for_launch(method, content):
            raise RuntimeError("В выбранном preset нет включённых profile для запуска")
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Ошибка чтения preset: {e}") from e


def validate_presets_before_launch(
    selected_mode,
    launch_method: str,
) -> tuple[object, list[str], str | None, str | None]:
    method = normalize_launch_method(launch_method, default="")
    if not is_zapret2_launch_method(method):
        return selected_mode, [], None, None
    if not isinstance(selected_mode, dict) or not bool(selected_mode.get("is_preset_file")):
        return selected_mode, [], None, None

    preset_path = Path(str(selected_mode.get("preset_path") or "").strip())
    if not preset_path.exists():
        return selected_mode, [], "Preset файл не найден. Создайте пресет в настройках", None

    try:
        from winws_runtime.preset_launch_text import (
            is_winws2_circular_preset_text,
            prepare_winws2_preset_text_for_launch,
        )

        source_text = preset_path.read_text(encoding="utf-8", errors="replace")
        prepared = prepare_winws2_preset_text_for_launch(
            source_text,
            source_name=preset_path.name,
            source_is_circular=is_winws2_circular_preset_text(source_text),
        )
        return selected_mode, list(prepared.warnings), None, None
    except Exception as e:
        log(f"Preset не прошёл проверку перед запуском: {e}", "DEBUG")
        return selected_mode, [], f"Preset не прошёл проверку перед запуском: {e}", None


def prepare_start_request(
    selected_mode=None,
    launch_method=None,
    *,
    presets_feature,
    skip_preset_prevalidation: bool = False,
) -> tuple[PreparedDpiStartRequest, list[str]]:
    resolved_method = resolve_launch_method(launch_method)
    log(f"Используется метод запуска: {resolved_method}", "INFO")

    prepared_selected_mode = prepare_selected_mode_for_start(
        selected_mode,
        resolved_method,
        presets_feature=presets_feature,
    )

    warnings: list[str] = []
    if skip_preset_prevalidation:
        if is_preset_launch_method(resolved_method) and isinstance(prepared_selected_mode, dict):
            preset_path = Path(str(prepared_selected_mode.get("preset_path") or "").strip())
            if not bool(prepared_selected_mode.get("is_preset_file")) or not preset_path.exists():
                raise RuntimeError("Preset файл не найден. Создайте пресет в настройках")
    else:
        prepared_selected_mode, prelaunch_warnings, prelaunch_error, prepared_text = validate_presets_before_launch(
            prepared_selected_mode,
            resolved_method,
        )
        if prelaunch_error:
            raise RuntimeError(prelaunch_error)

        validate_preset_selected_mode(
            prepared_selected_mode,
            resolved_method,
            prepared_text=prepared_text,
        )

        warnings = list(prelaunch_warnings)

    return (
        PreparedDpiStartRequest(
            launch_method=resolved_method,
            selected_mode=prepared_selected_mode,
            mode_name=resolve_mode_name(prepared_selected_mode),
            method_name=resolve_method_name(resolved_method),
        ),
        warnings,
    )
