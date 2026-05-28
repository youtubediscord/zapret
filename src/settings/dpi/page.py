# settings/dpi/page.py
"""Страница настроек DPI"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame

from ui.pages.base_page import BasePage
from settings.mode import (
    ENGINE_WINWS1,
    ENGINE_WINWS2,
    EXE_NAME_WINWS1,
    EXE_NAME_WINWS2,
    ORCHESTRA_MODE,
    ZAPRET1_MODE,
    ZAPRET2_MODE,
)
from ui.fluent_widgets import (
    SettingsCard,
)
from app.ui_texts import tr as tr_catalog
from ui.theme import get_theme_tokens
from ui.widgets.win11_controls import (
    Win11ComboRow,
    Win11NumberRow,
    Win11RadioOption,
    Win11ToggleRow,
)
from log.log import log
from qfluentwidgets import StrongBodyLabel, CaptionLabel as _CaptionLabel


METHOD_OPTION_TEXT = {
    ZAPRET2_MODE: {
        "title_key": "page.dpi_settings.method.zapret2_mode.title",
        "title": "Zapret 2",
        "desc_key": "page.dpi_settings.method.zapret2_mode.desc",
        "desc": (
            f"Режим Zapret 2 на движке {ENGINE_WINWS2} ({EXE_NAME_WINWS2}) "
            "+ готовые пресеты для быстрого запуска. Поддерживает Lua-код для своих стратегий."
        ),
    },
    ORCHESTRA_MODE: {
        "title_key": "page.dpi_settings.method.orchestra.title",
        "title": "Оркестратор v0.9.6 (Beta)",
        "desc_key": "page.dpi_settings.method.orchestra.desc",
        "desc": (
            "Автоматическое обучение. Система сама подбирает лучшие стратегии "
            "для каждого домена. Запоминает результаты между запусками."
        ),
    },
    ZAPRET1_MODE: {
        "title_key": "page.dpi_settings.method.zapret1_mode.title",
        "title": "Zapret 1",
        "desc_key": "page.dpi_settings.method.zapret1_mode.desc",
        "desc": (
            f"Режим Zapret 1 на движке {ENGINE_WINWS1} ({EXE_NAME_WINWS1}) "
            "+ готовые пресеты для быстрого запуска. Не использует Lua-код и блобы."
        ),
    },
}


class DpiSettingsPage(BasePage):
    """Страница настроек DPI"""
    
    def __init__(
        self,
        parent=None,
        *,
        dpi_settings_feature,
        orchestra_feature,
        runtime_feature,
        set_status,
        after_launch_method_changed,
    ):
        super().__init__(
            "Настройки DPI",
            "Параметры обхода блокировок",
            parent,
            title_key="page.dpi_settings.title",
            subtitle_key="page.dpi_settings.subtitle",
        )
        self._dpi_settings = dpi_settings_feature
        self._orchestra = orchestra_feature
        self._runtime = runtime_feature
        self._set_status = set_status
        self._after_launch_method_changed = after_launch_method_changed
        self._method_card = None
        self._method_desc_label = None
        self._zapret1_header = None
        self._orchestra_label = None
        self._orchestra_settings_bound = False
        self._orchestra_settings_built = False
        self.orchestra_settings_container = None
        self.strict_detection_toggle = None
        self.debug_file_toggle = None
        self.auto_restart_discord_toggle = None
        self.discord_fails_spin = None
        self.lock_successes_spin = None
        self.unlock_fails_spin = None
        self._settings_loaded = False
        self._dpi_settings_worker = None
        self._dpi_settings_request_id = 0
        self._dpi_settings_pending: list[tuple[str, str]] = []
        self._orchestra_settings_save_worker = None
        self._orchestra_settings_save_request_id = 0
        self._orchestra_settings_save_pending: list[tuple[str, object]] = []
        self._build_ui()

    def _tr(self, key: str, default: str, **kwargs) -> str:
        text = tr_catalog(key, language=self._ui_language, default=default)
        if kwargs:
            try:
                return text.format(**kwargs)
            except Exception:
                return text
        return text

    def _method_option_text(self, method: str) -> tuple[str, str]:
        text = METHOD_OPTION_TEXT[method]
        return (
            self._tr(text["title_key"], text["title"]),
            self._tr(text["desc_key"], text["desc"]),
        )

    def _apply_page_theme(self, tokens=None, force: bool = False) -> None:
        _ = force
        theme_tokens = tokens or get_theme_tokens()

        try:
            if hasattr(self, "separator2") and self.separator2 is not None:
                self.separator2.setStyleSheet(f"background-color: {theme_tokens.divider_strong}; margin: 8px 0;")
        except Exception:
            pass

    def _build_ui(self):
        """Строит UI страницы"""

        # Метод запуска
        method_card = SettingsCard(
            self._tr(
                "page.dpi_settings.card.launch_method",
                "Метод запуска стратегий (режим работы программы)",
            )
        )
        self._method_card = method_card
        method_layout = QVBoxLayout()
        method_layout.setSpacing(10)
        
        method_desc = _CaptionLabel(
            self._tr("page.dpi_settings.launch_method.desc", "Выберите способ запуска обхода блокировок")
        )
        self._method_desc_label = method_desc
        method_layout.addWidget(method_desc)

        # ═══════════════════════════════════════
        # ZAPRET 2
        # ═══════════════════════════════════════
        self.zapret2_header = StrongBodyLabel(
            self._tr("page.dpi_settings.section.zapret2", f"Zapret 2 ({EXE_NAME_WINWS2})")
        )
        self.zapret2_header.setContentsMargins(0, 8, 0, 4)
        method_layout.addWidget(self.zapret2_header)

        # Zapret 2 mode - рекомендуется
        self.method_zapret2_mode = Win11RadioOption(
            *self._method_option_text(ZAPRET2_MODE),
            icon_name="mdi.rocket-launch",
            recommended=True,
            recommended_badge=self._tr("page.dpi_settings.option.recommended", "рекомендуется"),
        )
        self.method_zapret2_mode.clicked.connect(lambda: self._select_method(ZAPRET2_MODE))
        method_layout.addWidget(self.method_zapret2_mode)

        # Оркестр (auto-learning)
        self.method_orchestra = Win11RadioOption(
            *self._method_option_text(ORCHESTRA_MODE),
            icon_name="mdi.brain",
            icon_color="#9c27b0",
        )
        self.method_orchestra.clicked.connect(lambda: self._select_method(ORCHESTRA_MODE))
        method_layout.addWidget(self.method_orchestra)

        # ───────────────────────────────────────
        # ZAPRET 1
        # ───────────────────────────────────────
        zapret1_header = StrongBodyLabel(
            self._tr("page.dpi_settings.section.zapret1", f"Zapret 1 ({EXE_NAME_WINWS1})")
        )
        self._zapret1_header = zapret1_header
        zapret1_header.setContentsMargins(0, 12, 0, 4)
        method_layout.addWidget(zapret1_header)

        # Zapret 1 mode
        self.method_zapret1_mode = Win11RadioOption(
            *self._method_option_text(ZAPRET1_MODE),
            icon_name="mdi.rocket-launch-outline",
            icon_color="#ff9800",
        )
        self.method_zapret1_mode.clicked.connect(lambda: self._select_method(ZAPRET1_MODE))
        method_layout.addWidget(self.method_zapret1_mode)

        # Разделитель 2
        self.separator2 = QFrame()
        self.separator2.setFrameShape(QFrame.Shape.HLine)
        self.separator2.setFixedHeight(1)
        method_layout.addWidget(self.separator2)

        self.orchestra_settings_container = QWidget()
        self.orchestra_settings_container.setVisible(False)
        method_layout.addWidget(self.orchestra_settings_container)

        method_card.add_layout(method_layout)
        self.layout.addWidget(method_card)

        self.layout.addStretch()

        # Apply token-driven accents/dividers.
        self._apply_page_theme(force=True)

    def _ensure_orchestra_settings_built(self) -> None:
        if self._orchestra_settings_built:
            return
        self._orchestra_settings_built = True
        orchestra_settings_layout = QVBoxLayout(self.orchestra_settings_container)
        orchestra_settings_layout.setContentsMargins(0, 0, 0, 0)
        orchestra_settings_layout.setSpacing(6)

        self._orchestra_label = StrongBodyLabel(
            self._tr("page.dpi_settings.section.orchestra_settings", "Настройки оркестратора")
        )
        orchestra_settings_layout.addWidget(self._orchestra_label)

        self.strict_detection_toggle = Win11ToggleRow(
            "mdi.check-decagram",
            self._tr("page.dpi_settings.orchestra.strict_detection.title", "Строгий режим детекции"),
            self._tr("page.dpi_settings.orchestra.strict_detection.desc", "HTTP 200 + проверка блок-страниц"),
            "#4CAF50",
        )
        orchestra_settings_layout.addWidget(self.strict_detection_toggle)

        self.debug_file_toggle = Win11ToggleRow(
            "mdi.file-document-outline",
            self._tr("page.dpi_settings.orchestra.debug_file.title", "Сохранять debug файл"),
            self._tr("page.dpi_settings.orchestra.debug_file.desc", "Сырой debug файл для отладки"),
            "#8a2be2",
        )
        orchestra_settings_layout.addWidget(self.debug_file_toggle)

        self.auto_restart_discord_toggle = Win11ToggleRow(
            "mdi.discord",
            self._tr("page.dpi_settings.orchestra.auto_restart_discord.title", "Авторестарт Discord при FAIL"),
            self._tr(
                "page.dpi_settings.orchestra.auto_restart_discord.desc",
                "Перезапуск Discord при неудачном обходе",
            ),
            "#7289da",
        )
        orchestra_settings_layout.addWidget(self.auto_restart_discord_toggle)

        self.discord_fails_spin = Win11NumberRow(
            "mdi.discord",
            self._tr("page.dpi_settings.orchestra.discord_fails.title", "Фейлов для рестарта Discord"),
            self._tr(
                "page.dpi_settings.orchestra.discord_fails.desc",
                "Сколько FAIL подряд для перезапуска Discord",
            ),
            "#7289da",
            min_val=1, max_val=10, default_val=3,
        )
        orchestra_settings_layout.addWidget(self.discord_fails_spin)

        self.lock_successes_spin = Win11NumberRow(
            "mdi.lock",
            self._tr("page.dpi_settings.orchestra.lock_successes.title", "Успехов для LOCK"),
            self._tr(
                "page.dpi_settings.orchestra.lock_successes.desc",
                "Количество успешных обходов для закрепления стратегии",
            ),
            "#4CAF50",
            min_val=1, max_val=10, default_val=3,
        )
        orchestra_settings_layout.addWidget(self.lock_successes_spin)

        self.unlock_fails_spin = Win11NumberRow(
            "mdi.lock-open",
            self._tr("page.dpi_settings.orchestra.unlock_fails.title", "Ошибок для AUTO-UNLOCK"),
            self._tr(
                "page.dpi_settings.orchestra.unlock_fails.desc",
                "Количество ошибок для автоматической разблокировки стратегии",
            ),
            "#FF5722",
            min_val=1, max_val=10, default_val=3,
        )
        orchestra_settings_layout.addWidget(self.unlock_fails_spin)
        
    def _load_settings(self):
        """Загружает настройки"""
        if self._settings_loaded:
            return
        self._settings_loaded = True
        self._request_dpi_initial_state_load()

    def create_dpi_settings_worker(self, request_id: int, *, action: str, method: str = ""):
        return self._dpi_settings.create_dpi_settings_worker(
            request_id,
            action=action,
            method=method,
            parent=self,
        )

    def _request_dpi_initial_state_load(self) -> None:
        self._request_dpi_settings_action("load_initial_state")

    def _request_launch_method_apply(self, method: str) -> None:
        self._request_dpi_settings_action("apply_launch_method", method)

    def _request_dpi_settings_action(self, action: str, method: str = "") -> None:
        payload = (str(action or "").strip(), str(method or "").strip())
        worker = self.__dict__.get("_dpi_settings_worker")
        if worker is not None:
            try:
                if worker.isRunning():
                    self._dpi_settings_pending.append(payload)
                    self._coalesce_dpi_settings_pending()
                    return
            except Exception:
                self._dpi_settings_pending.append(payload)
                self._coalesce_dpi_settings_pending()
                return
        self._start_dpi_settings_worker(payload)

    def _coalesce_dpi_settings_pending(self) -> None:
        latest_load: tuple[str, str] | None = None
        latest_apply: tuple[str, str] | None = None
        for payload in self._dpi_settings_pending:
            if payload[0] == "load_initial_state":
                latest_load = payload
            elif payload[0] == "apply_launch_method":
                latest_apply = payload
        self._dpi_settings_pending = [
            payload for payload in (latest_load, latest_apply) if payload is not None
        ]

    def _start_dpi_settings_worker(self, payload: tuple[str, str]) -> None:
        self._dpi_settings_request_id += 1
        request_id = self._dpi_settings_request_id
        worker = self.create_dpi_settings_worker(
            request_id,
            action=payload[0],
            method=payload[1],
        )
        self._dpi_settings_worker = worker
        worker.completed.connect(self._on_dpi_settings_worker_completed)
        worker.failed.connect(self._on_dpi_settings_worker_failed)
        worker.finished.connect(lambda w=worker: self._on_dpi_settings_worker_finished(w))
        worker.start()

    def _on_dpi_settings_worker_completed(self, request_id: int, action: str, result) -> None:
        if request_id != self._dpi_settings_request_id:
            return
        if not isinstance(result, dict):
            return
        if action == "load_initial_state":
            initial = result.get("initial")
            if initial is not None:
                self._apply_dpi_initial_state(initial, result.get("orchestra_settings"))
            return
        if action == "apply_launch_method":
            next_method = str(result.get("launch_method") or "").strip()
            visibility = result.get("visibility")
            if not next_method or visibility is None:
                return
            self._update_method_selection(next_method)
            self._apply_visibility(visibility)
            orchestra_settings = result.get("orchestra_settings")
            if visibility.show_orchestra_settings and orchestra_settings is not None:
                self._load_orchestra_settings(orchestra_settings)
            self._runtime.handle_launch_method_changed(next_method, set_status=self._set_status)
            self._after_launch_method_changed(next_method)

    def _on_dpi_settings_worker_failed(self, request_id: int, action: str, error: str) -> None:
        if request_id != self._dpi_settings_request_id:
            return
        if action == "load_initial_state":
            self._settings_loaded = False
        log(f"Ошибка DPI-настроек ({action}): {error}", "ERROR")

    def _on_dpi_settings_worker_finished(self, worker) -> None:
        if self.__dict__.get("_dpi_settings_worker") is worker:
            self._dpi_settings_worker = None
        worker.deleteLater()
        if self._dpi_settings_pending and not self._cleanup_in_progress:
            pending = self._dpi_settings_pending.pop(0)
            self._start_dpi_settings_worker(pending)

    def _apply_dpi_initial_state(self, initial, orchestra_settings=None) -> None:
        try:
            self._update_method_selection(initial.launch_method)
            self._apply_visibility(initial.visibility)
            if initial.visibility.show_orchestra_settings and orchestra_settings is not None:
                self._load_orchestra_settings(orchestra_settings)

        except Exception as e:
            self._settings_loaded = False
            log(f"Ошибка загрузки настроек DPI: {e}", "WARNING")

    def _run_runtime_init_once(self) -> None:
        self._load_settings()

    def on_page_activated(self) -> None:
        self._run_runtime_init_once()
    
    def _update_method_selection(self, method: str):
        """Обновляет визуальное состояние выбора метода"""
        self.method_zapret2_mode.setSelected(method == ZAPRET2_MODE)
        self.method_zapret1_mode.setSelected(method == ZAPRET1_MODE)
        self.method_orchestra.setSelected(method == ORCHESTRA_MODE)
    
    def _select_method(self, method: str):
        """Обработчик выбора метода"""
        try:
            visibility = self._dpi_settings.describe_visibility(method)
            self._update_method_selection(method)
            self._apply_visibility(visibility)
            self._request_launch_method_apply(method)
        except Exception as e:
            log(f"Ошибка смены метода: {e}", "ERROR")

    def _load_orchestra_settings(self, state):
        """Загружает настройки оркестратора"""
        try:
            self._ensure_orchestra_settings_built()
            self.strict_detection_toggle.setChecked(bool(state.strict_detection), block_signals=True)
            self.debug_file_toggle.setChecked(bool(state.debug_file), block_signals=True)
            self.auto_restart_discord_toggle.setChecked(bool(state.auto_restart_discord), block_signals=True)
            self.discord_fails_spin.setValue(int(state.discord_fails))
            self.lock_successes_spin.setValue(int(state.lock_successes))
            self.unlock_fails_spin.setValue(int(state.unlock_fails))

            if not self._orchestra_settings_bound:
                self.strict_detection_toggle.toggled.connect(self._on_strict_detection_changed)
                self.debug_file_toggle.toggled.connect(self._on_debug_file_changed)
                self.auto_restart_discord_toggle.toggled.connect(self._on_auto_restart_discord_changed)
                self.discord_fails_spin.valueChanged.connect(self._on_discord_fails_changed)
                self.lock_successes_spin.valueChanged.connect(self._on_lock_successes_changed)
                self.unlock_fails_spin.valueChanged.connect(self._on_unlock_fails_changed)
                self._orchestra_settings_bound = True

        except Exception as e:
            log(f"Ошибка загрузки настроек оркестратора: {e}", "WARNING")

    def _on_strict_detection_changed(self, enabled: bool):
        """Обработчик изменения строгого режима детекции"""
        self._request_orchestra_setting_save("strict_detection", bool(enabled))
        log(f"Строгий режим детекции: {'включён' if enabled else 'выключен'}", "INFO")

    def _on_debug_file_changed(self, enabled: bool):
        """Обработчик изменения сохранения debug файла"""
        self._request_orchestra_setting_save("debug_file", bool(enabled))
        log(f"Сохранение debug файла: {'включено' if enabled else 'выключено'}", "INFO")

    def _on_auto_restart_discord_changed(self, enabled: bool):
        """Обработчик изменения авторестарта при Discord FAIL"""
        self._request_orchestra_setting_save("auto_restart_discord", bool(enabled))
        log(f"Авторестарт при Discord FAIL: {'включён' if enabled else 'выключен'}", "INFO")

    def _on_discord_fails_changed(self, value: int):
        """Обработчик изменения количества фейлов для рестарта Discord"""
        self._request_orchestra_setting_save("discord_fails", int(value))
        log(f"Фейлов для рестарта Discord: {value}", "INFO")

    def _on_lock_successes_changed(self, value: int):
        """Обработчик изменения количества успехов для LOCK"""
        self._request_orchestra_setting_save("lock_successes", int(value))
        log(f"Успехов для LOCK: {value}", "INFO")

    def _on_unlock_fails_changed(self, value: int):
        """Обработчик изменения количества ошибок для AUTO-UNLOCK"""
        self._request_orchestra_setting_save("unlock_fails", int(value))
        log(f"Ошибок для AUTO-UNLOCK: {value}", "INFO")

    def create_orchestra_setting_save_worker(self, request_id: int, *, key: str, value):
        return self._orchestra.create_setting_save_worker(
            request_id,
            key=key,
            value=value,
            parent=self,
        )

    def _request_orchestra_setting_save(self, key: str, value) -> None:
        payload = (str(key or "").strip(), value)
        worker = self.__dict__.get("_orchestra_settings_save_worker")
        if worker is not None:
            try:
                if worker.isRunning():
                    self._orchestra_settings_save_pending.append(payload)
                    self._coalesce_orchestra_settings_save_pending()
                    return
            except Exception:
                self._orchestra_settings_save_pending.append(payload)
                self._coalesce_orchestra_settings_save_pending()
                return
        self._start_orchestra_setting_save_worker(payload)

    def _coalesce_orchestra_settings_save_pending(self) -> None:
        latest_by_key: dict[str, tuple[str, object]] = {}
        order: list[str] = []
        for payload in self._orchestra_settings_save_pending:
            key = str(payload[0] or "").strip()
            if key not in latest_by_key:
                order.append(key)
            latest_by_key[key] = payload
        self._orchestra_settings_save_pending = [latest_by_key[key] for key in order]

    def _start_orchestra_setting_save_worker(self, payload: tuple[str, object]) -> None:
        self._orchestra_settings_save_request_id += 1
        request_id = self._orchestra_settings_save_request_id
        worker = self.create_orchestra_setting_save_worker(
            request_id,
            key=str(payload[0]),
            value=payload[1],
        )
        self._orchestra_settings_save_worker = worker
        worker.saved.connect(self._on_orchestra_setting_save_finished)
        worker.failed.connect(self._on_orchestra_setting_save_failed)
        worker.finished.connect(lambda w=worker: self._on_orchestra_setting_save_worker_finished(w))
        worker.start()

    def _on_orchestra_setting_save_finished(self, request_id: int, _key: str, _value) -> None:
        if request_id != self._orchestra_settings_save_request_id:
            return

    def _on_orchestra_setting_save_failed(self, request_id: int, key: str, error: str) -> None:
        if request_id != self._orchestra_settings_save_request_id:
            return
        log(f"Ошибка сохранения настройки оркестратора {key}: {error}", "ERROR")

    def _on_orchestra_setting_save_worker_finished(self, worker) -> None:
        if self.__dict__.get("_orchestra_settings_save_worker") is worker:
            self._orchestra_settings_save_worker = None
        worker.deleteLater()
        if self._orchestra_settings_save_pending and not self._cleanup_in_progress:
            pending = self._orchestra_settings_save_pending.pop(0)
            self._start_orchestra_setting_save_worker(pending)
    
    def _update_filters_visibility(self, method: str | None = None):
        """Обновляет видимость фильтров и секций"""
        try:
            resolved_method = str(method or self._dpi_settings.get_launch_method()).strip().lower()
            visibility = self._dpi_settings.describe_visibility(resolved_method)
            self._apply_visibility(visibility)

        except Exception:
            pass

    def _apply_visibility(self, visibility) -> None:
        # Настройки оркестратора строятся только когда этот режим действительно виден.
        if visibility.show_orchestra_settings:
            self._ensure_orchestra_settings_built()
        if self.orchestra_settings_container is not None:
            self.orchestra_settings_container.setVisible(visibility.show_orchestra_settings)

    def _sync_visible_settings(self, method: str | None = None, visibility=None) -> None:
        try:
            resolved_visibility = visibility
            if resolved_visibility is None:
                self._request_dpi_initial_state_load()
                return

            if resolved_visibility.show_orchestra_settings:
                self._request_dpi_initial_state_load()
        except Exception as e:
            log(f"Ошибка синхронизации видимых настроек DPI: {e}", "WARNING")

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)

        if self._method_card is not None:
            self._method_card.set_title(
                self._tr(
                    "page.dpi_settings.card.launch_method",
                    "Метод запуска стратегий (режим работы программы)",
                )
            )
        if self._method_desc_label is not None:
            self._method_desc_label.setText(
                self._tr("page.dpi_settings.launch_method.desc", "Выберите способ запуска обхода блокировок")
            )

        if hasattr(self, "zapret2_header") and self.zapret2_header is not None:
            self.zapret2_header.setText(self._tr("page.dpi_settings.section.zapret2", f"Zapret 2 ({EXE_NAME_WINWS2})"))
        if self._zapret1_header is not None:
            self._zapret1_header.setText(self._tr("page.dpi_settings.section.zapret1", f"Zapret 1 ({EXE_NAME_WINWS1})"))
        if self._orchestra_label is not None:
            self._orchestra_label.setText(
                self._tr("page.dpi_settings.section.orchestra_settings", "Настройки оркестратора")
            )

        self.method_zapret2_mode.set_texts(
            *self._method_option_text(ZAPRET2_MODE),
            recommended_badge=self._tr("page.dpi_settings.option.recommended", "рекомендуется"),
        )
        self.method_orchestra.set_texts(
            *self._method_option_text(ORCHESTRA_MODE),
        )
        self.method_zapret1_mode.set_texts(
            *self._method_option_text(ZAPRET1_MODE),
        )

        if self.strict_detection_toggle is not None:
            self.strict_detection_toggle.set_texts(
                self._tr("page.dpi_settings.orchestra.strict_detection.title", "Строгий режим детекции"),
                self._tr("page.dpi_settings.orchestra.strict_detection.desc", "HTTP 200 + проверка блок-страниц"),
            )
        if self.debug_file_toggle is not None:
            self.debug_file_toggle.set_texts(
                self._tr("page.dpi_settings.orchestra.debug_file.title", "Сохранять debug файл"),
                self._tr("page.dpi_settings.orchestra.debug_file.desc", "Сырой debug файл для отладки"),
            )
        if self.auto_restart_discord_toggle is not None:
            self.auto_restart_discord_toggle.set_texts(
                self._tr("page.dpi_settings.orchestra.auto_restart_discord.title", "Авторестарт Discord при FAIL"),
                self._tr(
                    "page.dpi_settings.orchestra.auto_restart_discord.desc",
                    "Перезапуск Discord при неудачном обходе",
                ),
            )
        if self.discord_fails_spin is not None:
            self.discord_fails_spin.set_texts(
                self._tr("page.dpi_settings.orchestra.discord_fails.title", "Фейлов для рестарта Discord"),
                self._tr(
                    "page.dpi_settings.orchestra.discord_fails.desc",
                    "Сколько FAIL подряд для перезапуска Discord",
                ),
            )
        if self.lock_successes_spin is not None:
            self.lock_successes_spin.set_texts(
                self._tr("page.dpi_settings.orchestra.lock_successes.title", "Успехов для LOCK"),
                self._tr(
                    "page.dpi_settings.orchestra.lock_successes.desc",
                    "Количество успешных обходов для закрепления стратегии",
                ),
            )
        if self.unlock_fails_spin is not None:
            self.unlock_fails_spin.set_texts(
                self._tr("page.dpi_settings.orchestra.unlock_fails.title", "Ошибок для AUTO-UNLOCK"),
                self._tr(
                    "page.dpi_settings.orchestra.unlock_fails.desc",
                    "Количество ошибок для автоматической разблокировки стратегии",
                ),
            )

    def cleanup(self) -> None:
        self._dpi_settings_pending.clear()
        worker = self.__dict__.get("_dpi_settings_worker")
        if worker is not None:
            try:
                worker.quit()
            except Exception:
                pass
            self._dpi_settings_worker = None
        self._orchestra_settings_save_pending.clear()
        worker = self.__dict__.get("_orchestra_settings_save_worker")
        if worker is not None:
            try:
                worker.quit()
            except Exception:
                pass
            self._orchestra_settings_save_worker = None
        super().cleanup()
