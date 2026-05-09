from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from log.log import log


from winws_runtime.runtime.start_workers import PreparedDpiStartRequest

if TYPE_CHECKING:
    from app_context import AppContext


def resolve_launch_method(launch_method=None) -> str:
    from settings.dpi.strategy_settings import get_strategy_launch_method

    return str(launch_method or get_strategy_launch_method() or "").strip().lower()


def resolve_method_name(launch_method: str) -> str:
    method = str(launch_method or "").strip().lower()
    if method == "orchestra":
        return "оркестр"
    if method == "zapret2_mode":
        return "прямой"
    if method == "zapret1_mode":
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

    if method in ("zapret2_mode", "zapret1_mode"):
        snapshot = app_context.preset_mode_coordinator.get_startup_snapshot(
            method,
            require_filters=True,
        )
        log(f"Используется выбранный source-пресет: {snapshot.preset_path}", "INFO")
        return snapshot.to_selected_mode()

    raise RuntimeError("Неизвестный метод запуска")


def preset_filter_flags(launch_method: str) -> tuple[str, ...]:
    method = str(launch_method or "").strip().lower()
    if method == "zapret1_mode":
        return ("--wf-tcp=", "--wf-udp=")
    return ("--wf-tcp-out", "--wf-udp-out", "--wf-raw-part")


def _preset_selected_mode_validated_for_method(selected_mode, launch_method: str) -> bool:
    if not isinstance(selected_mode, dict):
        return False
    validated = bool(selected_mode.get("_preset_mode_filters_validated"))
    validated_method = str(selected_mode.get("_preset_mode_filters_validated_method") or "").strip().lower()
    method = str(launch_method or "").strip().lower()
    return validated and validated_method == method


def _preset_selected_mode_has_placeholder_unknown(selected_mode) -> bool:
    if not isinstance(selected_mode, dict):
        return False
    return bool(selected_mode.get("_preset_mode_has_placeholder_unknown"))


def validate_preset_selected_mode(selected_mode, launch_method: str, *, app_context: "AppContext") -> None:
    method = str(launch_method or "").strip().lower()
    if method not in ("zapret2_mode", "zapret1_mode"):
        return
    if not isinstance(selected_mode, dict) or not bool(selected_mode.get("is_preset_file")):
        return
    if method == "zapret1_mode" and _preset_selected_mode_validated_for_method(selected_mode, method):
        return
    if (
        method == "zapret2_mode"
        and _preset_selected_mode_validated_for_method(selected_mode, method)
        and not _preset_selected_mode_has_placeholder_unknown(selected_mode)
    ):
        return

    preset_path = Path(str(selected_mode.get("preset_path") or "").strip())
    if not preset_path.exists():
        raise RuntimeError("Preset файл не найден. Создайте пресет в настройках")

    try:
        content = preset_path.read_text(encoding="utf-8").strip()

        if method == "zapret2_mode":
            content_lower = content.lower()
            if ("unknown.txt" in content_lower) or ("ipset-unknown.txt" in content_lower):
                try:
                    from profile.parser import parse_preset_text
                    from profile.serializer import serialize_preset

                    source = parse_preset_text(content, engine="winws2", source_name=preset_path.name)
                    kept = [
                        profile for profile in source.profiles
                        if "unknown.txt" not in "\n".join(profile.match.all_lines()).lower()
                        and "ipset-unknown.txt" not in "\n".join(profile.match.all_lines()).lower()
                    ]
                    if len(kept) != len(source.profiles):
                        source.profiles = kept
                        preset_path.write_text(serialize_preset(source), encoding="utf-8")
                        content = preset_path.read_text(encoding="utf-8").strip()
                except Exception as e:
                    log(f"Ошибка очистки preset файла от unknown.txt: {e}", "DEBUG")

        if not any(flag in content for flag in preset_filter_flags(method)):
            raise RuntimeError("Выберите хотя бы одну категорию для запуска")
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Ошибка чтения preset: {e}") from e


def sanitize_presets_before_launch(
    selected_mode,
    launch_method: str,
    *,
    app_context: "AppContext",
) -> tuple[list[str], str | None]:
    method = str(launch_method or "").strip().lower()
    if method != "zapret2_mode":
        return [], None
    if not isinstance(selected_mode, dict) or not bool(selected_mode.get("is_preset_file")):
        return [], None

    preset_path = Path(str(selected_mode.get("preset_path") or "").strip())
    if not preset_path.exists():
        return [], "Preset файл не найден. Создайте пресет в настройках"

    try:
        from profile.parser import parse_preset_text
        from profile.serializer import serialize_preset, with_profile_strategy_lines
        from profile.winws2_transport import normalize_winws2_action_lines

        source = parse_preset_text(preset_path.read_text(encoding="utf-8", errors="replace"), engine="winws2", source_name=preset_path.name)
        changed = False
        warnings: list[str] = []

        kept = [
            profile for profile in source.profiles
            if "unknown.txt" not in "\n".join(profile.match.all_lines()).lower()
            and "ipset-unknown.txt" not in "\n".join(profile.match.all_lines()).lower()
        ]
        if len(kept) != len(source.profiles):
            source.profiles = kept
            source = parse_preset_text(serialize_preset(source), engine="winws2", source_name=preset_path.name)
            changed = True
            warnings.append("Из source-пресета автоматически убраны placeholder-фильтры unknown.txt.")

        repaired_labels: list[str] = []
        for profile in list(source.profiles):
            current_lines = [str(line).strip() for line in getattr(profile.strategy, "strategy_lines", ()) or () if str(line).strip()]
            normalized_lines, fixes, _resolved = normalize_winws2_action_lines(
                current_lines,
                source_is_circular=False,
            )
            if fixes and normalized_lines != current_lines:
                source = with_profile_strategy_lines(source, profile.index, normalized_lines)
                repaired_labels.append(profile.display_name)
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
            preset_path.write_text(serialize_preset(source), encoding="utf-8")

        return warnings, None
    except Exception as e:
        log(f"Не удалось подготовить preset mode перед запуском: {e}", "DEBUG")
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
    validate_preset_selected_mode(
        prepared_selected_mode,
        resolved_method,
        app_context=app_context,
    )

    prelaunch_warnings, prelaunch_error = sanitize_presets_before_launch(
        prepared_selected_mode,
        resolved_method,
        app_context=app_context,
    )
    if prelaunch_error:
        raise RuntimeError(prelaunch_error)

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
