from __future__ import annotations

from dataclasses import dataclass

from filters.strategy_detail.shared_filter_mode import (
    load_target_filter_mode as _load_target_filter_mode,
    save_target_filter_mode as _save_target_filter_mode,
)
from filters.strategy_detail.zapret2.filtering_logic import resolve_sort_mode


@dataclass(slots=True)
class StrategyDetailPresetActionResult:
    ok: bool
    log_level: str
    log_message: str
    infobar_level: str | None
    infobar_title: str
    infobar_content: str
    structure_changed: bool
    switched_file_name: str | None = None


@dataclass(slots=True)
class StrategyDetailResetPlan:
    ok: bool
    log_level: str
    log_message: str
    should_reload_payload: bool
    should_apply_syndata_settings: bool
    should_refresh_filter_mode: bool
    should_refresh_strategy_selection: bool
    should_show_loading: bool
    should_refresh_args_editor: bool
    should_refresh_target_enabled_ui: bool


class StrategyDetailPageController:
    @staticmethod
    def create_preset(facade, *, name: str) -> StrategyDetailPresetActionResult:
        facade.create(name, from_current=True)
        return StrategyDetailPresetActionResult(
            ok=True,
            log_level="INFO",
            log_message=f"Создан пресет '{name}'",
            infobar_level="success",
            infobar_title="Пресет создан",
            infobar_content=f"Пресет '{name}' создан на основе текущих настроек.",
            structure_changed=True,
        )

    @staticmethod
    def build_missing_active_preset_result() -> StrategyDetailPresetActionResult:
        return StrategyDetailPresetActionResult(
            ok=False,
            log_level="WARNING",
            log_message="Выбранный source-пресет не найден",
            infobar_level="warning",
            infobar_title="Нет выбранного source-пресета",
            infobar_content="Выбранный source-пресет не найден.",
            structure_changed=False,
        )

    @staticmethod
    def rename_preset(facade, *, old_file_name: str, old_name: str, new_name: str) -> StrategyDetailPresetActionResult:
        updated = facade.rename_by_file_name(old_file_name, new_name)
        switched_file_name = updated.file_name if facade.is_selected_file_name(updated.file_name) else None
        if switched_file_name:
            facade.notify_preset_identity_changed(updated.file_name)

        return StrategyDetailPresetActionResult(
            ok=True,
            log_level="INFO",
            log_message=f"Пресет '{old_name}' переименован в '{new_name}'",
            infobar_level="success",
            infobar_title="Переименован",
            infobar_content=f"Пресет переименован: '{old_name}' -> '{new_name}'.",
            structure_changed=True,
            switched_file_name=switched_file_name,
        )

    @staticmethod
    def save_target_filter_mode(facade, *, target_key: str, mode: str) -> None:
        _save_target_filter_mode(facade, target_key=target_key, mode=mode)

    @staticmethod
    def load_target_filter_mode(facade, *, payload, target_key: str) -> str:
        return _load_target_filter_mode(
            facade,
            target_key=target_key,
            current_payload=payload,
        )

    @staticmethod
    def save_target_sort(facade, *, target_key: str, sort_order: str) -> None:
        normalized = resolve_sort_mode(sort_order)
        facade.update_target_sort_order(target_key, normalized, save_and_sync=True)

    @staticmethod
    def load_target_sort(facade, *, target_key: str) -> str:
        return resolve_sort_mode(facade.get_target_sort_order(target_key))

    @staticmethod
    def build_reset_settings_plan(*, target_key: str, success: bool) -> StrategyDetailResetPlan:
        if success:
            return StrategyDetailResetPlan(
                ok=True,
                log_level="INFO",
                log_message=f"Настройки target'а {target_key} сброшены",
                should_reload_payload=True,
                should_apply_syndata_settings=True,
                should_refresh_filter_mode=True,
                should_refresh_strategy_selection=True,
                should_show_loading=True,
                should_refresh_args_editor=True,
                should_refresh_target_enabled_ui=True,
            )
        return StrategyDetailResetPlan(
            ok=False,
            log_level="WARNING",
            log_message=f"Не удалось сбросить настройки target'а {target_key}",
            should_reload_payload=False,
            should_apply_syndata_settings=False,
            should_refresh_filter_mode=False,
            should_refresh_strategy_selection=False,
            should_show_loading=False,
            should_refresh_args_editor=False,
            should_refresh_target_enabled_ui=False,
        )
