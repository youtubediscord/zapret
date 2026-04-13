from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from log.log import log


from winws_runtime.runtime.workers import PreparedDpiStartRequest

if TYPE_CHECKING:
    from app_context import AppContext


def resolve_launch_method(launch_method=None) -> str:
    from settings.dpi.strategy_settings import get_strategy_launch_method

    return str(launch_method or get_strategy_launch_method() or "").strip().lower()


def resolve_method_name(launch_method: str) -> str:
    method = str(launch_method or "").strip().lower()
    if method == "orchestra":
        return "оркестр"
    if method == "direct_zapret2":
        return "прямой"
    if method == "direct_zapret1":
        return "прямой Z1"
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


def prepare_selected_mode_for_start(selected_mode, launch_method: str, *, app_context: "AppContext"):
    method = str(launch_method or "").strip().lower()

    if method == "orchestra":
        return {"is_orchestra": True, "name": "Оркестр"}

    if selected_mode is not None and selected_mode != "default":
        return selected_mode

    if method in ("direct_zapret2", "direct_zapret1"):
        snapshot = app_context.direct_flow_coordinator.get_startup_snapshot(
            method,
            require_filters=True,
        )
        log(f"Используется выбранный source-пресет: {snapshot.preset_path}", "INFO")
        return snapshot.to_selected_mode()

    raise RuntimeError("Неизвестный метод запуска")


def direct_filter_flags(launch_method: str) -> tuple[str, ...]:
    method = str(launch_method or "").strip().lower()
    if method == "direct_zapret1":
        return ("--wf-tcp=", "--wf-udp=")
    return ("--wf-tcp-out", "--wf-udp-out", "--wf-raw-part")


def validate_direct_selected_mode(selected_mode, launch_method: str, *, app_context: "AppContext") -> None:
    method = str(launch_method or "").strip().lower()
    if method not in ("direct_zapret2", "direct_zapret1"):
        return
    if not isinstance(selected_mode, dict) or not bool(selected_mode.get("is_preset_file")):
        return

    preset_path = Path(str(selected_mode.get("preset_path") or "").strip())
    if not preset_path.exists():
        raise RuntimeError("Preset файл не найден. Создайте пресет в настройках")

    try:
        content = preset_path.read_text(encoding="utf-8").strip()

        if method == "direct_zapret2":
            content_lower = content.lower()
            if ("unknown.txt" in content_lower) or ("ipset-unknown.txt" in content_lower):
                try:
                    from direct_preset.service import DirectPresetService

                    service = DirectPresetService(app_context.app_paths, "winws2")
                    source = service.read_source_preset(preset_path)
                    if service.remove_placeholder_profiles(source):
                        service.write_source_preset(preset_path, source)
                        content = preset_path.read_text(encoding="utf-8").strip()
                except Exception as e:
                    log(f"Ошибка очистки preset файла от unknown.txt: {e}", "DEBUG")

        if not any(flag in content for flag in direct_filter_flags(method)):
            raise RuntimeError("Выберите хотя бы одну категорию для запуска")
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Ошибка чтения preset: {e}") from e


def collect_soft_launch_warnings(selected_mode, launch_method: str, *, app_context: "AppContext") -> list[str]:
    method = str(launch_method or "").strip().lower()
    if method != "direct_zapret2":
        return []
    if not isinstance(selected_mode, dict) or not bool(selected_mode.get("is_preset_file")):
        return []

    preset_path = str(selected_mode.get("preset_path") or "").strip()
    if not preset_path or not Path(preset_path).exists():
        return []

    try:
        from direct_preset.service import DirectPresetService

        service = DirectPresetService(app_context.app_paths, "winws2")
        source = service.read_source_preset(Path(preset_path))
        labels = service.collect_out_range_autofix_warning_labels(source)
    except Exception as e:
        log(f"Не удалось собрать предупреждения out-range для запуска: {e}", "DEBUG")
        return []

    if not labels:
        return []

    max_show = 5
    shown = labels[:max_show]
    hidden = len(labels) - len(shown)
    message = (
        "У некоторых фильтров out-range отсутствует или записан некорректно. "
        f"Перед запуском будет автоматически применён --out-range=-d8 или исправлен формат: {', '.join(shown)}"
    )
    if hidden > 0:
        message += f" (+{hidden} ещё)"
    return [message]


def sanitize_direct_preset_before_launch(
    selected_mode,
    launch_method: str,
    *,
    app_context: "AppContext",
) -> tuple[list[str], str | None]:
    method = str(launch_method or "").strip().lower()
    if method != "direct_zapret2":
        return [], None
    if not isinstance(selected_mode, dict) or not bool(selected_mode.get("is_preset_file")):
        return [], None

    preset_path = Path(str(selected_mode.get("preset_path") or "").strip())
    if not preset_path.exists():
        return [], "Preset файл не найден. Создайте пресет в настройках"

    try:
        from direct_preset.service import DirectPresetService

        service = DirectPresetService(app_context.app_paths, "winws2")
        source = service.read_source_preset(preset_path)
        changed = False
        warnings: list[str] = []

        if service.remove_placeholder_profiles(source):
            changed = True
            warnings.append("Из source-пресета автоматически убраны placeholder-фильтры unknown.txt.")

        repaired_labels = service.repair_out_range_profiles(source)
        if repaired_labels:
            changed = True
            max_show = 5
            shown = repaired_labels[:max_show]
            hidden = len(repaired_labels) - len(shown)
            message = (
                "В source-пресете автоматически исправлен out-range. "
                f"Для этих фильтров записан канонический формат или подставлен --out-range=-d8: {', '.join(shown)}"
            )
            if hidden > 0:
                message += f" (+{hidden} ещё)"
            warnings.append(message)

        if changed:
            service.write_source_preset(preset_path, source)

        return warnings, None
    except Exception as e:
        log(f"Не удалось подготовить direct preset перед запуском: {e}", "DEBUG")
        return [], None


def prepare_start_request(
    selected_mode=None,
    launch_method=None,
    *,
    app_context: "AppContext",
) -> tuple[PreparedDpiStartRequest, list[str]]:
    resolved_method = resolve_launch_method(launch_method)
    log(f"Используется метод запуска: {resolved_method}", "INFO")

    prepared_selected_mode = prepare_selected_mode_for_start(
        selected_mode,
        resolved_method,
        app_context=app_context,
    )
    validate_direct_selected_mode(
        prepared_selected_mode,
        resolved_method,
        app_context=app_context,
    )

    prelaunch_warnings, prelaunch_error = sanitize_direct_preset_before_launch(
        prepared_selected_mode,
        resolved_method,
        app_context=app_context,
    )
    if prelaunch_error:
        raise RuntimeError(prelaunch_error)

    warnings = [
        *prelaunch_warnings,
        *collect_soft_launch_warnings(
            prepared_selected_mode,
            resolved_method,
            app_context=app_context,
        ),
    ]

    return (
        PreparedDpiStartRequest(
            launch_method=resolved_method,
            selected_mode=prepared_selected_mode,
            mode_name=resolve_mode_name(prepared_selected_mode),
            method_name=resolve_method_name(resolved_method),
        ),
        warnings,
    )
