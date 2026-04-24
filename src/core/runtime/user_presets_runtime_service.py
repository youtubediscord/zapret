from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Callable, Optional
import weakref

from log.log import log

from ui.theme import get_theme_tokens


_DEFAULT_PRESET_ICON_COLOR = "#5caee8"
_HEX_COLOR_RGB_RE = re.compile(r"^#(?:[0-9a-fA-F]{6})$")
_HEX_COLOR_RGBA_RE = re.compile(r"^#(?:[0-9a-fA-F]{8})$")


def normalize_preset_icon_color(value: Optional[str]) -> str:
    raw = str(value or "").strip()
    if _HEX_COLOR_RGB_RE.fullmatch(raw):
        return raw.lower()
    if _HEX_COLOR_RGBA_RE.fullmatch(raw):
        lowered = raw.lower()
        return f"#{lowered[1:7]}"
    try:
        return get_theme_tokens().accent_hex
    except Exception:
        return _DEFAULT_PRESET_ICON_COLOR


@dataclass(slots=True)
class UserPresetsRuntimeAdapter:
    bulk_reset_running: Callable[[], bool]
    read_single_metadata: Callable[[str], tuple[str, dict[str, object]] | None]
    selected_source_file_name: Callable[[], str]
    presets_dir: Callable[[], Path]
    load_all_metadata: Callable[[], dict[str, dict[str, object]]]
    rebuild_rows: Callable[[dict[str, dict[str, object]], float | None], None]
    delete_preset_meta: Callable[[str], None]


class UserPresetsRuntimeService:
    def __init__(self, *, scope_key: str = "") -> None:
        self._scope_key = str(scope_key or "").strip()
        self._ui_dirty = True
        self._cached_presets_metadata: dict[str, dict[str, object]] = {}
        self._file_watcher = None
        self._watcher_active = False
        self._watcher_reload_timer = None
        self._attached_page_ref = None
        self._attached_adapter: UserPresetsRuntimeAdapter | None = None

    def is_ui_dirty(self) -> bool:
        return bool(self._ui_dirty)

    def set_ui_dirty(self, value: bool) -> None:
        self._ui_dirty = bool(value)

    def cached_presets_metadata(self) -> dict[str, dict[str, object]]:
        return self._cached_presets_metadata

    @staticmethod
    def _make_page_ref(page):
        try:
            return weakref.ref(page)
        except TypeError:
            return lambda: page

    def _resolve_page(self, page=None):
        if page is not None:
            return page
        try:
            if self._attached_page_ref is not None:
                resolved = self._attached_page_ref()
                if resolved is not None:
                    return resolved
        except Exception:
            pass
        raise RuntimeError("user presets page is not attached")

    def _resolve_adapter(self, adapter: UserPresetsRuntimeAdapter | None = None) -> UserPresetsRuntimeAdapter:
        if adapter is not None:
            return adapter
        attached = self._attached_adapter
        if attached is not None:
            return attached
        raise RuntimeError("user presets runtime adapter is not attached")

    def attach_page(self, page, adapter: UserPresetsRuntimeAdapter) -> None:
        current_page = None
        try:
            if self._attached_page_ref is not None:
                current_page = self._attached_page_ref()
        except Exception:
            current_page = None

        self._attached_adapter = adapter
        if current_page is page and self._watcher_reload_timer is not None:
            return
        self._attached_page_ref = self._make_page_ref(page)
        try:
            from PyQt6.QtCore import QTimer

            timer = QTimer(page)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda p=page: self.reload_presets_from_watcher(p))
            self._watcher_reload_timer = timer
        except Exception:
            self._watcher_reload_timer = None

    def on_store_changed(self, page=None) -> None:
        page = self._resolve_page(page)
        _ = self._resolve_adapter()
        self.mark_presets_structure_changed(page)

    def mark_presets_structure_changed(self, page=None) -> None:
        page = self._resolve_page(page)
        adapter = self._resolve_adapter()
        self._ui_dirty = True
        if adapter.bulk_reset_running():
            return
        if page.isVisible():
            self.schedule_presets_reload(page, 0)

    def on_ui_state_changed(self, _state, changed_fields: frozenset[str], page=None) -> None:
        if "preset_structure_revision" in changed_fields:
            self.mark_presets_structure_changed(page)

    def on_store_updated(self, file_name_or_name: str, page=None) -> None:
        page = self._resolve_page(page)
        adapter = self._resolve_adapter()
        if adapter.bulk_reset_running():
            return

        refreshed = adapter.read_single_metadata(file_name_or_name)
        if refreshed is None:
            self._ui_dirty = True
            if page.isVisible():
                self.schedule_presets_reload(page, 0)
            return

        normalized_file_name, metadata = refreshed
        previous_metadata = dict(self._cached_presets_metadata.get(normalized_file_name) or {})
        self._cached_presets_metadata[normalized_file_name] = metadata
        self.sync_watched_preset_files(page)
        if page.isVisible():
            if self.try_apply_single_preset_metadata_update(
                normalized_file_name,
                previous_metadata=previous_metadata,
                next_metadata=metadata,
                page=page,
            ):
                return
            self.refresh_presets_view_from_cache(page)
        else:
            self._ui_dirty = True

    def current_search_query(self, page=None) -> str:
        page = self._resolve_page(page)
        try:
            if page._preset_search_input is not None:
                return str(page._preset_search_input.text() or "").strip().lower()
        except Exception:
            pass
        return ""

    def capture_presets_view_state(self, page=None) -> dict[str, object]:
        page = self._resolve_page(page)
        state = {
            "current_file_name": "",
            "scroll_value": 0,
        }
        try:
            current_index = page.presets_list.currentIndex()
            if current_index.isValid():
                file_role = getattr(type(page._presets_model), "FileNameRole", None)
                if file_role is not None:
                    state["current_file_name"] = str(current_index.data(file_role) or "")
        except Exception:
            pass
        try:
            scrollbar = page.presets_list.verticalScrollBar()
            if scrollbar is not None:
                state["scroll_value"] = int(scrollbar.value())
        except Exception:
            pass
        return state

    def restore_presets_view_state(self, state: dict[str, object], page=None) -> None:
        page = self._resolve_page(page)
        target_file_name = str((state or {}).get("current_file_name") or "").strip()
        if target_file_name:
            self.set_current_preset_index(target_file_name, page=page)
        try:
            scrollbar = page.presets_list.verticalScrollBar()
            if scrollbar is not None:
                scrollbar.setValue(int((state or {}).get("scroll_value") or 0))
        except Exception:
            pass

    def set_current_preset_index(
        self,
        file_name: str,
        *,
        display_name: str = "",
        use_display_name_fallback: bool = False,
        page=None,
    ) -> None:
        page = self._resolve_page(page)
        if page._presets_model is None or not hasattr(page, "presets_list"):
            return

        target_file_name = str(file_name or "").strip()
        target_display_name = str(display_name or "").strip()
        if not target_file_name and not (use_display_name_fallback and target_display_name):
            return

        model_type = type(page._presets_model)
        kind_role = getattr(model_type, "KindRole", None)
        file_role = getattr(model_type, "FileNameRole", None)
        name_role = getattr(model_type, "NameRole", None)

        for row in range(page._presets_model.rowCount()):
            index = page._presets_model.index(row, 0)
            if str(index.data(kind_role) or "") != "preset":
                continue
            if target_file_name and str(index.data(file_role) or "") == target_file_name:
                page.presets_list.setCurrentIndex(index)
                return
            if use_display_name_fallback and target_display_name and name_role is not None:
                if str(index.data(name_role) or "") == target_display_name:
                    page.presets_list.setCurrentIndex(index)
                    return

    def apply_active_preset_marker_for_target(
        self,
        file_name: str,
        *,
        display_name: str = "",
        use_display_name_fallback: bool = False,
        page=None,
    ) -> bool:
        page = self._resolve_page(page)
        if page._presets_model is None:
            return False
        changed = page._presets_model.set_active_preset(
            str(file_name or "").strip(),
            display_name=str(display_name or "").strip(),
            use_display_name_fallback=bool(use_display_name_fallback),
        )
        if changed and hasattr(page, "presets_list"):
            self.set_current_preset_index(
                file_name,
                display_name=display_name,
                use_display_name_fallback=use_display_name_fallback,
                page=page,
            )
            page.presets_list.viewport().update()
            page.presets_list.viewport().repaint()
        return changed

    def apply_active_preset_marker(self, page=None) -> bool:
        page = self._resolve_page(page)
        adapter = self._resolve_adapter()
        active_file_name = adapter.selected_source_file_name()
        return self.apply_active_preset_marker_for_target(active_file_name, page=page)

    def ensure_preset_list_current_index(self, page=None) -> None:
        page = self._resolve_page(page)
        if page._presets_model is None:
            return
        current = page.presets_list.currentIndex()
        model_type = type(page._presets_model)
        kind_role = getattr(model_type, "KindRole", None)
        if current.isValid() and str(current.data(kind_role) or "") == "preset":
            return
        for row in range(page._presets_model.rowCount()):
            index = page._presets_model.index(row, 0)
            if str(index.data(kind_role) or "") == "preset":
                page.presets_list.setCurrentIndex(index)
                break

    def try_apply_single_preset_metadata_update(
        self,
        normalized_file_name: str,
        *,
        previous_metadata: dict[str, object],
        next_metadata: dict[str, object],
        page=None,
    ) -> bool:
        page = self._resolve_page(page)
        adapter = self._resolve_adapter()
        model = page._presets_model
        if model is None or model.find_preset_row(normalized_file_name) < 0:
            return False

        previous_display_name = str(previous_metadata.get("display_name") or normalized_file_name).strip()
        next_display_name = str(next_metadata.get("display_name") or normalized_file_name).strip()
        if previous_display_name != next_display_name:
            return False

        query = self.current_search_query(page)
        if query and query not in next_display_name.lower():
            return False

        active_file_name = adapter.selected_source_file_name()
        updated = model.update_preset_row(
            normalized_file_name,
            name=next_display_name,
            description=str(next_metadata.get("description") or ""),
            date=str(next_metadata.get("modified_display") or ""),
            is_active=bool(normalized_file_name and normalized_file_name == active_file_name),
            is_builtin=bool(next_metadata.get("is_builtin", False)),
            icon_color=normalize_preset_icon_color(str(next_metadata.get("icon_color") or "")),
        )
        if updated:
            try:
                page.presets_list.viewport().update()
            except Exception:
                pass
        return updated

    def on_store_switched(self, _name: str, page=None) -> None:
        page = self._resolve_page(page)
        adapter = self._resolve_adapter()
        if adapter.bulk_reset_running():
            return
        marker_changed = self.apply_active_preset_marker(page)
        if marker_changed and not self._ui_dirty:
            return
        if not self._ui_dirty and self._cached_presets_metadata and not marker_changed:
            return
        self._ui_dirty = True
        if page.isVisible():
            page.refresh_presets_view_if_possible()

    def start_watching_presets(self, page=None) -> None:
        page = self._resolve_page(page)
        adapter = self._resolve_adapter()
        try:
            if self._watcher_active:
                return

            presets_dir = adapter.presets_dir()
            presets_dir.mkdir(parents=True, exist_ok=True)

            if not self._file_watcher:
                from PyQt6.QtCore import QFileSystemWatcher

                watcher = QFileSystemWatcher(page)
                watcher.directoryChanged.connect(
                    lambda path: self.on_presets_dir_changed(path)
                )
                watcher.fileChanged.connect(
                    lambda path: self.on_preset_file_changed(path)
                )
                self._file_watcher = watcher

            dir_path = str(presets_dir)
            if dir_path not in self._file_watcher.directories():
                self._file_watcher.addPath(dir_path)

            self.sync_watched_preset_files(page)
            self._watcher_active = True
        except Exception as e:
            log(f"Ошибка запуска мониторинга пресетов: {e}", "DEBUG")

    def stop_watching_presets(self, page=None) -> None:
        _ = self._resolve_page(page)
        try:
            if not self._watcher_active:
                timer = self._watcher_reload_timer
                if timer is not None:
                    timer.stop()
                self._ui_dirty = True
                return
            timer = self._watcher_reload_timer
            if timer is not None:
                timer.stop()
            if self._file_watcher:
                directories = self._file_watcher.directories()
                files = self._file_watcher.files()
                if directories:
                    self._file_watcher.removePaths(directories)
                if files:
                    self._file_watcher.removePaths(files)
            self._watcher_active = False
            self._ui_dirty = True
        except Exception as e:
            log(f"Ошибка остановки мониторинга пресетов: {e}", "DEBUG")

    def on_presets_dir_changed(self, path: str, page=None) -> None:
        page = self._resolve_page(page)
        try:
            log(f"Обнаружены изменения в папке пресетов: {path}", "DEBUG")
            self.schedule_presets_reload(page)
        except Exception as e:
            log(f"Ошибка обработки изменений папки пресетов: {e}", "DEBUG")

    def on_preset_file_changed(self, path: str, page=None) -> None:
        page = self._resolve_page(page)
        try:
            changed_path = Path(path)
            if self._file_watcher is not None and changed_path.exists():
                normalized_path = str(changed_path)
                if normalized_path not in self._file_watcher.files():
                    self._file_watcher.addPath(normalized_path)

            file_name = changed_path.name
            if file_name:
                self.on_store_updated(file_name, page)
        except Exception as e:
            log(f"Ошибка обработки изменений файла пресета: {e}", "DEBUG")

    def schedule_presets_reload(self, page=None, delay_ms: int = 500) -> None:
        page = self._resolve_page(page)
        try:
            if self._watcher_reload_timer is None:
                self.attach_page(page)
            if self._watcher_reload_timer is None:
                raise RuntimeError("watcher reload timer not initialized")
            self._watcher_reload_timer.stop()
            self._watcher_reload_timer.start(delay_ms)
        except Exception as e:
            log(f"Ошибка планирования обновления пресетов: {e}", "DEBUG")

    def reload_presets_from_watcher(self, page=None) -> None:
        page = self._resolve_page(page)
        adapter = self._resolve_adapter()
        try:
            next_metadata = dict(adapter.load_all_metadata())
            next_file_names = set(next_metadata.keys())
            self.sync_watched_preset_files(page, next_file_names)
            self._cached_presets_metadata = next_metadata
        except Exception:
            if page.isVisible():
                self.load_presets(page)
            else:
                self._ui_dirty = True
            return

        if not page.isVisible():
            self._ui_dirty = True
            return

        self._ui_dirty = False
        self.refresh_presets_view_from_cache(page)

    def sync_watched_preset_files(self, page=None, file_names: set[str] | None = None) -> None:
        page = self._resolve_page(page)
        adapter = self._resolve_adapter()
        watcher = self._file_watcher
        if watcher is None:
            return

        try:
            presets_dir = adapter.presets_dir()
            if file_names is None:
                file_names = {
                    str(file_name or "").strip()
                    for file_name in self._cached_presets_metadata.keys()
                    if str(file_name or "").strip()
                }

            desired_paths = {
                str(presets_dir / file_name)
                for file_name in file_names
                if file_name
            }
            current_paths = set(watcher.files() or [])

            remove_paths = sorted(current_paths - desired_paths)
            add_paths = sorted(
                path for path in (desired_paths - current_paths)
                if Path(path).exists()
            )

            if remove_paths:
                watcher.removePaths(remove_paths)
            if add_paths:
                watcher.addPaths(add_paths)
        except Exception as e:
            log(f"Ошибка синхронизации watcher файлов пресетов: {e}", "DEBUG")

    def load_presets(self, page=None) -> None:
        page = self._resolve_page(page)
        adapter = self._resolve_adapter()
        self._ui_dirty = False
        try:
            import time

            started_at = time.perf_counter()
            all_presets = adapter.load_all_metadata()
            self._cached_presets_metadata = dict(all_presets)
            self.sync_watched_preset_files(page, set(all_presets.keys()))
            adapter.rebuild_rows(all_presets, started_at)
        except Exception as e:
            log(f"Ошибка загрузки пресетов: {e}", "ERROR")

    def refresh_presets_view_if_possible(self, page=None) -> None:
        page = self._resolve_page(page)
        if self._cached_presets_metadata:
            self._ui_dirty = False
            self.refresh_presets_view_from_cache(page)
            return
        self.load_presets(page)

    def refresh_presets_view_from_cache(self, page=None) -> None:
        _ = self._resolve_page(page)
        adapter = self._resolve_adapter()
        if not self._cached_presets_metadata:
            self.load_presets(page)
            return
        adapter.rebuild_rows(self._cached_presets_metadata, None)

    def recover_missing_deleted_preset(self, name: str, page=None) -> None:
        page = self._resolve_page(page)
        adapter = self._resolve_adapter()
        try:
            adapter.delete_preset_meta(name)
        except Exception:
            pass

        normalized_name = str(name or "").strip()
        if normalized_name:
            self._cached_presets_metadata.pop(normalized_name, None)
            if not normalized_name.lower().endswith(".txt"):
                self._cached_presets_metadata.pop(f"{normalized_name}.txt", None)

        if page.isVisible() and self._cached_presets_metadata:
            self._ui_dirty = False
            self.refresh_presets_view_from_cache(page)
            return

        self._ui_dirty = True
        if page.isVisible():
            self.load_presets(page)
