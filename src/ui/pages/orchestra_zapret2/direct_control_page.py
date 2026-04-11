from __future__ import annotations

from ui.compat_widgets import set_tooltip
from ui.pages.zapret2.direct_control_page import Zapret2DirectControlPage
from ui.text_catalog import tr as tr_catalog


class OrchestraZapret2DirectControlPage(Zapret2DirectControlPage):
    def _after_ui_built(self) -> None:
        self._attach_program_settings_runtime()
        super()._after_ui_built()
        self._apply_orchestra_labels(language=self._ui_language)
        self._refresh_direct_mode_label()

    def _apply_orchestra_labels(self, language: str | None = None) -> None:
        try:
            self.title_label.setText(
                tr_catalog(
                    "page.z2_orchestra_control.title",
                    language=language,
                    default="Управление Orchestra Z2",
                )
            )
            if self.subtitle_label is not None:
                self.subtitle_label.setText(
                    tr_catalog(
                        "page.z2_orchestra_control.subtitle",
                        language=language,
                        default="Управление пресетами и запуском для режима direct_zapret2_orchestra.",
                    )
                )

            if getattr(self, "control_section_label", None) is not None:
                self.control_section_label.setText(
                    tr_catalog(
                        "page.z2_orchestra_control.section.management",
                        language=language,
                        default="Управление Orchestra Z2",
                    )
                )
            if getattr(self, "preset_section_label", None) is not None:
                self.preset_section_label.setText(
                    tr_catalog(
                        "page.z2_orchestra_control.section.preset",
                        language=language,
                        default="Сменить пресет Orchestra Z2",
                    )
                )
            if getattr(self, "direct_section_label", None) is not None:
                self.direct_section_label.setText(
                    tr_catalog(
                        "page.z2_orchestra_control.section.direct_tuning",
                        language=language,
                        default="Тонкая настройка активного пресета",
                    )
                )

            if getattr(self, "presets_btn", None) is not None:
                self.presets_btn.setText(
                    tr_catalog(
                        "page.z2_orchestra_control.button.presets",
                        language=language,
                        default="Пресеты Orchestra",
                    )
                )
            if getattr(self, "direct_open_btn", None) is not None:
                self.direct_open_btn.setText(
                    tr_catalog(
                        "page.z2_orchestra_control.button.direct_open",
                        language=language,
                        default="Прямой запуск",
                    )
                )
            if getattr(self, "direct_mode_btn", None) is not None:
                self.direct_mode_btn.setVisible(False)

            if getattr(self, "direct_mode_caption", None) is not None:
                self.direct_mode_caption.setText(
                    tr_catalog(
                        "page.z2_orchestra_control.section.category_editing",
                        language=language,
                        default="Редактирование активного пресета по категориям",
                    )
                )

            if getattr(self, "wssize_toggle", None) is not None:
                self.wssize_toggle.setVisible(False)
            if getattr(self, "blobs_open_btn", None) is not None:
                self.blobs_open_btn.setText(
                    tr_catalog(
                        "page.z2_orchestra_control.button.blobs_open",
                        language=language,
                        default="Открыть блобы",
                    )
                )
        except Exception:
            pass

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)
        self._apply_orchestra_labels(language=language)
        self._refresh_direct_mode_label()

    def _open_direct_mode_dialog(self) -> None:
        return

    def _on_direct_launch_mode_selected(self, mode: str) -> None:
        _ = mode
        return

    def _refresh_direct_mode_label(self) -> None:
        try:
            self.direct_mode_label.setText(
                tr_catalog(
                    "page.z2_orchestra_control.mode_label",
                    language=self._ui_language,
                    default="Orchestra Z2",
                )
            )
        except Exception:
            pass

    def _sync_direct_launch_mode_from_settings(self) -> None:
        self._refresh_direct_mode_label()

    def _build_orchestra_preset_summary(self) -> tuple[str, str, str, str]:
        preset_name = ""
        category_names: list[str] = []

        try:
            from preset_orchestra_zapret2 import PresetManager

            manager = PresetManager()
            preset_name = str(manager.get_active_preset_name() or "").strip()
            selections = manager.get_strategy_selections() or {}
            category_names = [str(key or "").strip() for key in selections.keys() if str(key or "").strip()]
        except Exception:
            preset_name = ""
            category_names = []

        if not preset_name:
            preset_name = tr_catalog(
                "page.z2_control.preset.not_selected",
                language=self._ui_language,
                default="Не выбран",
            )
            preset_tooltip = ""
        else:
            preset_tooltip = preset_name

        if category_names:
            strategy_text = " • ".join(category_names)
            strategy_tooltip = "\n".join(category_names)
        else:
            strategy_text = tr_catalog(
                "page.z2_orchestra_control.strategy.no_active_categories",
                language=self._ui_language,
                default="Нет активных категорий",
            )
            strategy_tooltip = ""

        return preset_name, preset_tooltip, strategy_text, strategy_tooltip

    def _hydrate_initial_advanced_settings(self) -> None:
        self._advanced_settings_dirty = False
        self._load_advanced_settings()

    def _hydrate_initial_preset_summary(self) -> None:
        self._preset_summary_dirty = False
        preset_name, preset_tooltip, strategy_text, strategy_tooltip = self._build_orchestra_preset_summary()
        self.preset_name_label.setText(preset_name)
        set_tooltip(self.preset_name_label, preset_tooltip)
        self.strategy_label.setText(strategy_text)
        set_tooltip(self.strategy_label, strategy_tooltip)

    def _schedule_advanced_settings_reload(self, *, force: bool = False) -> None:
        if not force and not getattr(self, "_advanced_settings_dirty", True):
            return
        if not self.isVisible():
            self._advanced_settings_dirty = True
            return
        if getattr(self, "_advanced_settings_worker", None) is not None:
            try:
                if self._advanced_settings_worker.isRunning():
                    return
            except Exception:
                pass

        self._advanced_settings_request_id += 1
        request_id = self._advanced_settings_request_id
        from ui.pages.zapret2.direct_control_page import Zapret2DirectControlPageController

        self._advanced_settings_worker = Zapret2DirectControlPageController.create_advanced_settings_worker(request_id, self)
        self._advanced_settings_worker.loaded.connect(self._on_advanced_settings_loaded)
        self._advanced_settings_worker.finished.connect(self._advanced_settings_worker.deleteLater)
        self._advanced_settings_worker.start()

    def _on_advanced_settings_loaded(self, request_id: int, state: dict) -> None:
        if int(request_id) != int(self._advanced_settings_request_id):
            return
        self._advanced_settings_dirty = False
        from ui.pages.zapret2.direct_control_page import Zapret2DirectControlPageController

        plan = Zapret2DirectControlPageController.build_advanced_settings_apply_plan(state if isinstance(state, dict) else {})
        self._apply_advanced_settings_plan(plan)

    def _schedule_preset_summary_reload(self, *, force: bool = False) -> None:
        if not force and not getattr(self, "_preset_summary_dirty", True):
            return
        if not self.isVisible():
            self._preset_summary_dirty = True
            return
        if getattr(self, "_preset_summary_worker", None) is not None:
            try:
                if self._preset_summary_worker.isRunning():
                    return
            except Exception:
                pass

        self._preset_summary_request_id += 1
        request_id = self._preset_summary_request_id
        from ui.pages.zapret2.direct_control_page import Zapret2DirectControlPageController

        self._preset_summary_worker = Zapret2DirectControlPageController.create_preset_summary_worker(request_id, self)
        self._preset_summary_worker.loaded.connect(self._on_preset_summary_loaded)
        self._preset_summary_worker.finished.connect(self._preset_summary_worker.deleteLater)
        self._preset_summary_worker.start()

    def _on_preset_summary_loaded(self, request_id: int, payload: dict) -> None:
        if int(request_id) != int(self._preset_summary_request_id):
            return
        self._preset_summary_dirty = False
        from ui.pages.zapret2.direct_control_page import Zapret2DirectControlPageController

        plan = Zapret2DirectControlPageController.build_preset_summary_plan(payload, language=self._ui_language)
        self.preset_name_label.setText(plan.preset_name_text)
        set_tooltip(self.preset_name_label, plan.preset_name_tooltip)
        self.strategy_label.setText(plan.strategy_text)
        set_tooltip(self.strategy_label, plan.strategy_tooltip)

    def _load_advanced_settings(self) -> None:
        try:
            from discord.discord_restart import get_discord_restart_setting

            toggle = getattr(self, "discord_restart_toggle", None)
            set_checked = getattr(toggle, "setChecked", None)
            if callable(set_checked):
                set_checked(get_discord_restart_setting(default=True), block_signals=True)
        except Exception:
            pass

        try:
            from preset_orchestra_zapret2 import PresetManager

            debug_toggle = getattr(self, "debug_log_toggle", None)
            set_checked = getattr(debug_toggle, "setChecked", None)
            if callable(set_checked):
                set_checked(bool(PresetManager().get_debug_log_enabled()), block_signals=True)
        except Exception:
            pass

    def _on_debug_log_toggled(self, enabled: bool) -> None:
        try:
            from preset_orchestra_zapret2 import PresetManager

            PresetManager().set_debug_log_enabled(bool(enabled))
        except Exception:
            pass

        try:
            from preset_orchestra_zapret2 import PresetManager, ensure_default_preset_exists

            if not ensure_default_preset_exists():
                return
            manager = PresetManager()
            preset = manager.get_active_preset()
            if preset:
                manager.sync_preset_to_active_file(preset)
        except Exception:
            pass

    def update_strategy(self, name: str):
        super().update_strategy(name)

        try:
            if getattr(self, "strategy_label", None) is not None and self.strategy_label.text() == "Нет активных листов":
                self.strategy_label.setText(
                    tr_catalog(
                        "page.z2_orchestra_control.strategy.no_active_categories",
                        language=self._ui_language,
                        default="Нет активных категорий",
                    )
                )
        except Exception:
            pass

        active_preset_name = ""
        try:
            from preset_orchestra_zapret2 import PresetManager

            preset_manager = PresetManager()
            active_preset_name = (preset_manager.get_active_preset_name() or "").strip()
            if not active_preset_name:
                preset = preset_manager.get_active_preset()
                active_preset_name = (getattr(preset, "name", "") or "").strip()
        except Exception:
            active_preset_name = ""

        if active_preset_name:
            try:
                self.preset_name_label.setText(active_preset_name)
                set_tooltip(self.preset_name_label, active_preset_name)
            except Exception:
                pass
