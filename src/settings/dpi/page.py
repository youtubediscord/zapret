# settings/dpi/page.py
"""Страница настроек DPI"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame

from ui.pages.base_page import BasePage
from settings.dpi.controller import DpiSettingsPageController
from ui.compat_widgets import (
    SettingsCard,
)
from ui.text_catalog import tr as tr_catalog
from ui.theme import get_theme_tokens
from ui.widgets.win11_controls import (
    Win11ComboRow,
    Win11NumberRow,
    Win11RadioOption,
    Win11ToggleRow,
)
from log import log

try:
    from qfluentwidgets import StrongBodyLabel, CaptionLabel as _CaptionLabel, SettingCardGroup
    _HAS_FLUENT_LABELS = True
except ImportError:
    StrongBodyLabel = QLabel  # type: ignore[assignment,misc]
    _CaptionLabel = QLabel  # type: ignore[assignment,misc]
    SettingCardGroup = None  # type: ignore[assignment,misc]
    _HAS_FLUENT_LABELS = False

class DpiSettingsPage(BasePage):
    """Страница настроек DPI"""

    launch_method_changed = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(
            "Настройки DPI",
            "Параметры обхода блокировок",
            parent,
            title_key="page.dpi_settings.title",
            subtitle_key="page.dpi_settings.subtitle",
        )
        self._method_card = None
        self._method_desc_label = None
        self._zapret1_header = None
        self._orchestra_label = None
        self._orchestra_settings_bound = False
        self._build_ui()
        self._load_settings()

    def _tr(self, key: str, default: str, **kwargs) -> str:
        text = tr_catalog(key, language=self._ui_language, default=default)
        if kwargs:
            try:
                return text.format(**kwargs)
            except Exception:
                return text
        return text

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
        # ZAPRET 2 (winws2.exe)
        # ═══════════════════════════════════════
        self.zapret2_header = StrongBodyLabel(
            self._tr("page.dpi_settings.section.z2", "Zapret 2 (winws2.exe)")
        )
        self.zapret2_header.setContentsMargins(0, 8, 0, 4)
        method_layout.addWidget(self.zapret2_header)

        # Zapret 2 (direct) - рекомендуется
        self.method_direct = Win11RadioOption(
            self._tr("page.dpi_settings.method.direct_z2.title", "Zapret 2"),
            self._tr(
                "page.dpi_settings.method.direct_z2.desc",
                "Режим со второй версией Zapret (winws2.exe) + готовые пресеты для быстрого запуска. Поддерживает кастомный lua-код чтобы писать свои стратегии.",
            ),
            icon_name="mdi.rocket-launch",
            recommended=True,
            recommended_badge=self._tr("page.dpi_settings.option.recommended", "рекомендуется"),
        )
        self.method_direct.clicked.connect(lambda: self._select_method("direct_zapret2"))
        method_layout.addWidget(self.method_direct)

        # Оркестр (auto-learning)
        self.method_orchestra = Win11RadioOption(
            self._tr("page.dpi_settings.method.orchestra.title", "Оркестратор v0.9.6 (Beta)"),
            self._tr(
                "page.dpi_settings.method.orchestra.desc",
                "Автоматическое обучение. Система сама подбирает лучшие стратегии для каждого домена. Запоминает результаты между запусками.",
            ),
            icon_name="mdi.brain",
            icon_color="#9c27b0"
        )
        self.method_orchestra.clicked.connect(lambda: self._select_method("orchestra"))
        method_layout.addWidget(self.method_orchestra)

        # ───────────────────────────────────────
        # ZAPRET 1 (winws.exe)
        # ───────────────────────────────────────
        zapret1_header = StrongBodyLabel(
            self._tr("page.dpi_settings.section.z1", "Zapret 1 (winws.exe)")
        )
        self._zapret1_header = zapret1_header
        zapret1_header.setContentsMargins(0, 12, 0, 4)
        method_layout.addWidget(zapret1_header)

        # Zapret 1 Direct (прямой запуск winws.exe с JSON стратегиями)
        self.method_direct_zapret1 = Win11RadioOption(
            self._tr("page.dpi_settings.method.direct_z1.title", "Zapret 1"),
            self._tr(
                "page.dpi_settings.method.direct_z1.desc",
                "Режим первой версии Zapret 1 (winws.exe) + готовые пресеты для быстрого запуска. Не использует Lua код, нет понятия блобов.",
            ),
            icon_name="mdi.rocket-launch-outline",
            icon_color="#ff9800"
        )
        self.method_direct_zapret1.clicked.connect(lambda: self._select_method("direct_zapret1"))
        method_layout.addWidget(self.method_direct_zapret1)

        # Разделитель 2
        self.separator2 = QFrame()
        self.separator2.setFrameShape(QFrame.Shape.HLine)
        self.separator2.setFixedHeight(1)
        method_layout.addWidget(self.separator2)

        # ─────────────────────────────────────────────────────────────────────
        # НАСТРОЙКИ ОРКЕСТРАТОРА (только в режиме оркестратора)
        # ─────────────────────────────────────────────────────────────────────
        self.orchestra_settings_container = QWidget()
        orchestra_settings_layout = QVBoxLayout(self.orchestra_settings_container)
        orchestra_settings_layout.setContentsMargins(0, 0, 0, 0)
        orchestra_settings_layout.setSpacing(6)

        orchestra_label = StrongBodyLabel(
            self._tr("page.dpi_settings.section.orchestra_settings", "Настройки оркестратора")
        )
        self._orchestra_label = orchestra_label
        orchestra_settings_layout.addWidget(orchestra_label)

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

        # Количество фейлов для рестарта Discord
        self.discord_fails_spin = Win11NumberRow(
            "mdi.discord",
            self._tr("page.dpi_settings.orchestra.discord_fails.title", "Фейлов для рестарта Discord"),
            self._tr(
                "page.dpi_settings.orchestra.discord_fails.desc",
                "Сколько FAIL подряд для перезапуска Discord",
            ),
            "#7289da",
            min_val=1, max_val=10, default_val=3)
        orchestra_settings_layout.addWidget(self.discord_fails_spin)

        # Успехов для LOCK (сколько успехов подряд для закрепления стратегии)
        self.lock_successes_spin = Win11NumberRow(
            "mdi.lock",
            self._tr("page.dpi_settings.orchestra.lock_successes.title", "Успехов для LOCK"),
            self._tr(
                "page.dpi_settings.orchestra.lock_successes.desc",
                "Количество успешных обходов для закрепления стратегии",
            ),
            "#4CAF50",
            min_val=1, max_val=10, default_val=3)
        orchestra_settings_layout.addWidget(self.lock_successes_spin)

        # Ошибок для AUTO-UNLOCK (сколько ошибок подряд для разблокировки)
        self.unlock_fails_spin = Win11NumberRow(
            "mdi.lock-open",
            self._tr("page.dpi_settings.orchestra.unlock_fails.title", "Ошибок для AUTO-UNLOCK"),
            self._tr(
                "page.dpi_settings.orchestra.unlock_fails.desc",
                "Количество ошибок для автоматической разблокировки стратегии",
            ),
            "#FF5722",
            min_val=1, max_val=10, default_val=3)
        orchestra_settings_layout.addWidget(self.unlock_fails_spin)

        method_layout.addWidget(self.orchestra_settings_container)

        method_card.add_layout(method_layout)
        self.layout.addWidget(method_card)
        
        self.layout.addStretch()

        # Apply token-driven accents/dividers.
        self._apply_page_theme(force=True)
        
    def _load_settings(self):
        """Загружает настройки"""
        try:
            initial = DpiSettingsPageController.load_initial_state()
            self._update_method_selection(initial.launch_method)
            self._update_filters_visibility(initial.launch_method)
            self._sync_visible_settings()

        except Exception as e:
            log(f"Ошибка загрузки настроек DPI: {e}", "WARNING")
    
    def _update_method_selection(self, method: str):
        """Обновляет визуальное состояние выбора метода"""
        self.method_direct.setSelected(method == "direct_zapret2")
        self.method_direct_zapret1.setSelected(method == "direct_zapret1")
        self.method_orchestra.setSelected(method == "orchestra")
    
    def _select_method(self, method: str):
        """Обработчик выбора метода"""
        try:
            next_method = DpiSettingsPageController.apply_launch_method(method)
            self._update_method_selection(next_method)
            self._update_filters_visibility(next_method)
            self._sync_visible_settings()
            self.launch_method_changed.emit(next_method)
        except Exception as e:
            log(f"Ошибка смены метода: {e}", "ERROR")

    def _load_orchestra_settings(self, state):
        """Загружает настройки оркестратора"""
        try:
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
        try:
            DpiSettingsPageController.set_orchestra_setting("strict_detection", enabled, app=self)
            log(f"Строгий режим детекции: {'включён' if enabled else 'выключен'}", "INFO")

        except Exception as e:
            log(f"Ошибка сохранения настройки строгого режима: {e}", "ERROR")

    def _on_debug_file_changed(self, enabled: bool):
        """Обработчик изменения сохранения debug файла"""
        try:
            DpiSettingsPageController.set_orchestra_setting("debug_file", enabled, app=self)
            log(f"Сохранение debug файла: {'включено' if enabled else 'выключено'}", "INFO")

        except Exception as e:
            log(f"Ошибка сохранения настройки debug файла: {e}", "ERROR")

    def _on_auto_restart_discord_changed(self, enabled: bool):
        """Обработчик изменения авторестарта при Discord FAIL"""
        try:
            DpiSettingsPageController.set_orchestra_setting("auto_restart_discord", enabled, app=self)
            log(f"Авторестарт при Discord FAIL: {'включён' if enabled else 'выключен'}", "INFO")

        except Exception as e:
            log(f"Ошибка сохранения настройки авторестарта Discord: {e}", "ERROR")

    def _on_discord_fails_changed(self, value: int):
        """Обработчик изменения количества фейлов для рестарта Discord"""
        try:
            DpiSettingsPageController.set_orchestra_setting("discord_fails", value, app=self)
            log(f"Фейлов для рестарта Discord: {value}", "INFO")

        except Exception as e:
            log(f"Ошибка сохранения настройки DiscordFailsForRestart: {e}", "ERROR")

    def _on_lock_successes_changed(self, value: int):
        """Обработчик изменения количества успехов для LOCK"""
        try:
            DpiSettingsPageController.set_orchestra_setting("lock_successes", value, app=self)
            log(f"Успехов для LOCK: {value}", "INFO")

        except Exception as e:
            log(f"Ошибка сохранения настройки LockSuccesses: {e}", "ERROR")

    def _on_unlock_fails_changed(self, value: int):
        """Обработчик изменения количества ошибок для AUTO-UNLOCK"""
        try:
            DpiSettingsPageController.set_orchestra_setting("unlock_fails", value, app=self)
            log(f"Ошибок для AUTO-UNLOCK: {value}", "INFO")

        except Exception as e:
            log(f"Ошибка сохранения настройки UnlockFails: {e}", "ERROR")
    
    def _update_filters_visibility(self, method: str | None = None):
        """Обновляет видимость фильтров и секций"""
        try:
            resolved_method = str(method or DpiSettingsPageController.get_launch_method()).strip().lower()
            visibility = DpiSettingsPageController.describe_visibility(resolved_method)

            # Настройки оркестратора только для Python-оркестратора.
            self.orchestra_settings_container.setVisible(visibility.show_orchestra_settings)

        except:
            pass

    def _sync_visible_settings(self) -> None:
        try:
            visibility = DpiSettingsPageController.describe_visibility(
                DpiSettingsPageController.get_launch_method()
            )
            if visibility.show_orchestra_settings:
                self._load_orchestra_settings(
                    DpiSettingsPageController.load_orchestra_settings()
                )
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
            self.zapret2_header.setText(self._tr("page.dpi_settings.section.z2", "Zapret 2 (winws2.exe)"))
        if self._zapret1_header is not None:
            self._zapret1_header.setText(self._tr("page.dpi_settings.section.z1", "Zapret 1 (winws.exe)"))
        if self._orchestra_label is not None:
            self._orchestra_label.setText(
                self._tr("page.dpi_settings.section.orchestra_settings", "Настройки оркестратора")
            )

        self.method_direct.set_texts(
            self._tr("page.dpi_settings.method.direct_z2.title", "Zapret 2"),
            self._tr(
                "page.dpi_settings.method.direct_z2.desc",
                "Режим со второй версией Zapret (winws2.exe) + готовые пресеты для быстрого запуска. Поддерживает кастомный lua-код чтобы писать свои стратегии.",
            ),
            recommended_badge=self._tr("page.dpi_settings.option.recommended", "рекомендуется"),
        )
        self.method_orchestra.set_texts(
            self._tr("page.dpi_settings.method.orchestra.title", "Оркестратор v0.9.6 (Beta)"),
            self._tr(
                "page.dpi_settings.method.orchestra.desc",
                "Автоматическое обучение. Система сама подбирает лучшие стратегии для каждого домена. Запоминает результаты между запусками.",
            ),
        )
        self.method_direct_zapret1.set_texts(
            self._tr("page.dpi_settings.method.direct_z1.title", "Zapret 1"),
            self._tr(
                "page.dpi_settings.method.direct_z1.desc",
                "Режим первой версии Zapret 1 (winws.exe) + готовые пресеты для быстрого запуска. Не использует Lua код, нет понятия блобов.",
            ),
        )

        self.strict_detection_toggle.set_texts(
            self._tr("page.dpi_settings.orchestra.strict_detection.title", "Строгий режим детекции"),
            self._tr("page.dpi_settings.orchestra.strict_detection.desc", "HTTP 200 + проверка блок-страниц"),
        )
        self.debug_file_toggle.set_texts(
            self._tr("page.dpi_settings.orchestra.debug_file.title", "Сохранять debug файл"),
            self._tr("page.dpi_settings.orchestra.debug_file.desc", "Сырой debug файл для отладки"),
        )
        self.auto_restart_discord_toggle.set_texts(
            self._tr("page.dpi_settings.orchestra.auto_restart_discord.title", "Авторестарт Discord при FAIL"),
            self._tr(
                "page.dpi_settings.orchestra.auto_restart_discord.desc",
                "Перезапуск Discord при неудачном обходе",
            ),
        )
        self.discord_fails_spin.set_texts(
            self._tr("page.dpi_settings.orchestra.discord_fails.title", "Фейлов для рестарта Discord"),
            self._tr(
                "page.dpi_settings.orchestra.discord_fails.desc",
                "Сколько FAIL подряд для перезапуска Discord",
            ),
        )
        self.lock_successes_spin.set_texts(
            self._tr("page.dpi_settings.orchestra.lock_successes.title", "Успехов для LOCK"),
            self._tr(
                "page.dpi_settings.orchestra.lock_successes.desc",
                "Количество успешных обходов для закрепления стратегии",
            ),
        )
        self.unlock_fails_spin.set_texts(
            self._tr("page.dpi_settings.orchestra.unlock_fails.title", "Ошибок для AUTO-UNLOCK"),
            self._tr(
                "page.dpi_settings.orchestra.unlock_fails.desc",
                "Количество ошибок для автоматической разблокировки стратегии",
            ),
        )
