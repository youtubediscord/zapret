from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from log import log


class DirectFlowError(RuntimeError):
    """Raised when the direct-launch preset/runtime flow cannot be prepared."""


@dataclass(frozen=True)
class DirectLaunchProfile:
    launch_method: str
    engine: str
    preset_id: str
    preset_name: str
    launch_config_path: Path
    display_name: str

    def to_selected_mode(self) -> dict[str, object]:
        return {
            "is_preset_file": True,
            "name": self.display_name,
            "preset_path": str(self.launch_config_path),
        }


class DirectFlowCoordinator:
    _METHOD_TO_ENGINE = {
        "direct_zapret1": "winws1",
        "direct_zapret2": "winws2",
    }

    def ensure_launch_profile(
        self,
        launch_method: str,
        *,
        require_filters: bool = False,
    ) -> DirectLaunchProfile:
        method = self._normalize_method(launch_method)
        selected = self._ensure_selected_source_preset(method)
        self._sync_selected_runtime(method, selected.manifest.name)

        launch_config_path = self._runtime_path(method)
        if not launch_config_path.exists():
            raise DirectFlowError(f"Generated launch config not found: {launch_config_path}")

        text = ""
        try:
            text = launch_config_path.read_text(encoding="utf-8").strip()
        except Exception as exc:
            raise DirectFlowError(f"Failed to read generated launch config: {exc}") from exc

        if require_filters and not self._has_required_filters(method, text):
            raise DirectFlowError("Выберите хотя бы одну категорию для запуска")

        return DirectLaunchProfile(
            launch_method=method,
            engine=self._METHOD_TO_ENGINE[method],
            preset_id=selected.manifest.id,
            preset_name=selected.manifest.name,
            launch_config_path=launch_config_path,
            display_name=f"Пресет: {selected.manifest.name}",
        )

    def build_selected_mode(
        self,
        launch_method: str,
        *,
        require_filters: bool = False,
    ) -> dict[str, object]:
        return self.ensure_launch_profile(
            launch_method,
            require_filters=require_filters,
        ).to_selected_mode()

    def get_selected_source_preset(self, launch_method: str):
        return self._ensure_selected_source_preset(launch_method)

    def get_selected_source_path(self, launch_method: str) -> Path:
        selected = self.get_selected_source_preset(launch_method)
        from core.services import get_app_paths

        engine = self._METHOD_TO_ENGINE[self._normalize_method(launch_method)]
        return get_app_paths().engine_paths(engine).ensure_directories().presets_dir / selected.manifest.file_name

    def ensure_runtime(self, launch_method: str) -> Path:
        return self.ensure_launch_profile(launch_method, require_filters=False).launch_config_path

    def get_selected_preset_name(self, launch_method: str) -> str:
        return self.get_selected_source_preset(launch_method).manifest.name

    def is_selected_preset(self, launch_method: str, preset_name: str) -> bool:
        current = (self.get_selected_preset_name(launch_method) or "").strip().lower()
        target = str(preset_name or "").strip().lower()
        return bool(current and target and current == target)

    def select_preset(self, launch_method: str, preset_name: str) -> DirectLaunchProfile:
        method = self._normalize_method(launch_method)
        engine = self._METHOD_TO_ENGINE[method]
        self._ensure_support_files(method)

        from core.services import get_selection_service

        selected = get_selection_service().select_preset_by_name(engine, preset_name)
        self._sync_selected_runtime(method, selected.manifest.name)
        return DirectLaunchProfile(
            launch_method=method,
            engine=engine,
            preset_id=selected.manifest.id,
            preset_name=selected.manifest.name,
            launch_config_path=self._runtime_path(method),
            display_name=f"Пресет: {selected.manifest.name}",
        )

    def refresh_selected_runtime(self, launch_method: str) -> DirectLaunchProfile:
        return self.ensure_launch_profile(launch_method, require_filters=False)

    def _normalize_method(self, launch_method: str) -> str:
        method = str(launch_method or "").strip().lower()
        if method not in self._METHOD_TO_ENGINE:
            raise DirectFlowError(f"Unsupported direct launch method: {launch_method}")
        return method

    def _ensure_selected_source_preset(self, launch_method: str):
        method = self._normalize_method(launch_method)
        engine = self._METHOD_TO_ENGINE[method]

        self._ensure_support_files(method)

        from core.services import get_preset_repository, get_selection_service

        repo = get_preset_repository()
        selection = get_selection_service()

        if repo.find_preset_by_name(engine, "Default") is None:
            template_name, template_content = self._get_default_template(method)
            if not template_content:
                raise DirectFlowError("Отсутствует встроенный шаблон Default")
            repo.create_preset(engine, template_name or "Default", template_content)

        selected = selection.ensure_selected_preset(engine, "Default")
        if selected is None:
            raise DirectFlowError("Не удалось определить выбранный пресет")
        return selected

    def _sync_selected_runtime(self, launch_method: str, preset_name: str) -> None:
        method = self._normalize_method(launch_method)
        try:
            if method == "direct_zapret2":
                from preset_zapret2 import PresetManager, load_preset

                preset = load_preset(preset_name)
                if preset is None:
                    raise DirectFlowError(f"Не удалось загрузить source preset: {preset_name}")
                ok = PresetManager().sync_preset_to_active_file(preset)
            else:
                from preset_zapret1 import PresetManagerV1, load_preset_v1

                preset = load_preset_v1(preset_name)
                if preset is None:
                    raise DirectFlowError(f"Не удалось загрузить source preset: {preset_name}")
                ok = PresetManagerV1().sync_preset_to_active_file(preset)
        except Exception as exc:
            raise DirectFlowError(f"Не удалось синхронизировать launch config: {exc}") from exc

        if not ok:
            raise DirectFlowError("Не удалось синхронизировать launch config")

    def _runtime_path(self, launch_method: str) -> Path:
        method = self._normalize_method(launch_method)
        if method == "direct_zapret2":
            from preset_zapret2 import get_active_preset_path

            return get_active_preset_path()

        from preset_zapret1 import get_active_preset_path_v1

        return get_active_preset_path_v1()

    @staticmethod
    def _has_required_filters(launch_method: str, text: str) -> bool:
        content = str(text or "")
        if launch_method == "direct_zapret1":
            return any(flag in content for flag in ("--wf-tcp=", "--wf-udp="))
        return any(flag in content for flag in ("--wf-tcp-out", "--wf-udp-out", "--wf-raw-part"))

    @staticmethod
    def _get_default_template(launch_method: str) -> tuple[str | None, str | None]:
        if launch_method == "direct_zapret2":
            from preset_zapret2.preset_defaults import (
                get_default_template_content,
                get_default_template_name,
            )

            return get_default_template_name(), get_default_template_content()

        from preset_zapret1.preset_defaults import (
            get_default_template_content_v1,
            get_default_template_name_v1,
        )

        return get_default_template_name_v1(), get_default_template_content_v1()

    @staticmethod
    def _ensure_support_files(launch_method: str) -> None:
        try:
            if launch_method == "direct_zapret2":
                from preset_zapret2 import (
                    ensure_advanced_strategies_exist,
                    ensure_basic_strategies_exist,
                    ensure_builtin_presets_exist,
                )

                ensure_builtin_presets_exist()
                ensure_basic_strategies_exist()
                ensure_advanced_strategies_exist()
                return

            from preset_zapret1 import ensure_v1_strategies_exist
            from preset_zapret1.preset_defaults import (
                ensure_v1_templates_copied_to_presets,
                update_changed_v1_templates_in_presets,
            )

            ensure_v1_strategies_exist()
            update_changed_v1_templates_in_presets()
            ensure_v1_templates_copied_to_presets()
        except Exception as exc:
            log(f"Failed to prepare direct support files for {launch_method}: {exc}", "DEBUG")
