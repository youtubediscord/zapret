# ui/pages/custom_ipset_page.py
"""Страница управления пользовательскими IP (ipset-all.user.txt)."""

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit
)
import qtawesome as qta

try:
    from qfluentwidgets import LineEdit, MessageBox, InfoBar, SettingCardGroup, PushSettingCard
    _HAS_FLUENT = True
except ImportError:
    LineEdit = QLineEdit
    MessageBox = None
    InfoBar = None
    SettingCardGroup = None  # type: ignore[assignment]
    PushSettingCard = None  # type: ignore[assignment]
    _HAS_FLUENT = False

try:
    from qfluentwidgets import StrongBodyLabel, BodyLabel, CaptionLabel
    _HAS_FLUENT_LABELS = True
except ImportError:
    StrongBodyLabel = QLabel; BodyLabel = QLabel; CaptionLabel = QLabel
    _HAS_FLUENT_LABELS = False

from .base_page import BasePage, ScrollBlockingPlainTextEdit
from core.hostlist_page_controller import HostlistPageController
from ui.compat_widgets import SettingsCard, ActionButton
from ui.theme import get_theme_tokens
from ui.text_catalog import tr as tr_catalog
from log import log


class CustomIpSetPage(BasePage):
    """Страница управления пользовательскими IP (ipset-all.user.txt)."""

    ipset_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(
            "Кастомные (мои) IP и подсети для ipset-all",
            "Здесь Вы можете редактировать пользовательский список IP/подсетей (ipset-all.user.txt). Пишите только IP/CIDR, изменения сохраняются автоматически.",
            parent,
            title_key="page.custom_ipset.title",
            subtitle_key="page.custom_ipset.subtitle",
        )
        self._controller = HostlistPageController()
        self._desc_label = None
        self._add_card = None
        self._actions_card = None
        self._actions_group = None
        self._editor_card = None
        self._hint_label = None
        self._open_action_card = None
        self._clear_action_card = None
        self._status_state = {
            "total": 0,
            "base": 0,
            "user": 0,
            "saved": False,
            "error_text": "",
            "error_key": None,
            "error_default": "",
            "error_kwargs": {},
        }
        self._invalid_line_items: list[tuple[int, str]] = []

        self._status_timer = QTimer()
        self._status_timer.setSingleShot(True)
        self._status_timer.timeout.connect(self._update_status)
        self._initial_entries_load_requested = False

        self.enable_deferred_ui_build(after_build=self._after_ui_built)

    def _after_ui_built(self) -> None:
        self._apply_page_theme(force=True)

    def on_page_activated(self, first_show: bool) -> None:
        _ = first_show
        if self._initial_entries_load_requested:
            return
        self._initial_entries_load_requested = True
        QTimer.singleShot(0, self._load_entries)

    def _tr(self, key: str, default: str, **kwargs) -> str:
        text = tr_catalog(key, language=self._ui_language, default=default)
        if kwargs:
            try:
                return text.format(**kwargs)
            except Exception:
                return text
        return text

    def _build_ui(self):
        tokens = get_theme_tokens()
        desc_card = SettingsCard()
        desc = CaptionLabel(
            self._tr(
                "page.custom_ipset.description",
                "Добавляйте свои IP/подсети в ipset-all.user.txt.\n"
                "• Одиночный IP: 1.2.3.4\n"
                "• Подсеть: 10.0.0.0/8\n"
                "Диапазоны (a-b) не поддерживаются.\n"
                "Системная база хранится в ipset-all.base.txt и объединяется автоматически в ipset-all.txt.",
            )
        )
        self._desc_label = desc
        desc.setStyleSheet(f"color: {tokens.fg_muted};")
        desc.setWordWrap(True)
        desc_card.add_widget(desc)
        self.layout.addWidget(desc_card)

        add_card = SettingsCard(self._tr("page.custom_ipset.section.add", "Добавить IP/подсеть"))
        self._add_card = add_card
        add_layout = QHBoxLayout()
        add_layout.setSpacing(8)

        self.input = LineEdit()
        self.input.setPlaceholderText(
            self._tr("page.custom_ipset.input.placeholder", "Например: 1.2.3.4 или 10.0.0.0/8")
        )
        self.input.returnPressed.connect(self._add_entry)
        add_layout.addWidget(self.input, 1)

        self.add_btn = ActionButton(self._tr("page.custom_ipset.button.add", "Добавить"), "fa5s.plus", accent=True)
        self.add_btn.setFixedHeight(38)
        self.add_btn.clicked.connect(self._add_entry)
        add_layout.addWidget(self.add_btn)

        add_card.add_layout(add_layout)
        self.layout.addWidget(add_card)

        self.open_btn = None
        self.clear_btn = None
        self._actions_card = None
        actions_group = SettingCardGroup(
            self._tr("page.custom_ipset.section.actions", "Действия"),
            self.content,
        )
        self._actions_group = actions_group
        self._open_action_card = PushSettingCard(
            self._tr("page.custom_ipset.button.open_file", "Открыть файл"),
            qta.icon("fa5s.external-link-alt", color=tokens.accent_hex),
            self._tr("page.custom_ipset.button.open_file", "Открыть файл"),
            self._tr(
                "page.custom_ipset.action.open_file.description",
                "Сохраняет изменения и открывает ipset-all.user.txt в проводнике.",
            ),
        )
        self._open_action_card.clicked.connect(self._open_file)
        actions_group.addSettingCard(self._open_action_card)

        self._clear_action_card = PushSettingCard(
            self._tr("page.custom_ipset.button.clear_all", "Очистить всё"),
            qta.icon("fa5s.trash-alt", color="#ff9800"),
            self._tr("page.custom_ipset.button.clear_all", "Очистить всё"),
            self._tr(
                "page.custom_ipset.action.clear_all.description",
                "Удаляет все пользовательские записи из ipset-all.user.txt.",
            ),
        )
        self._clear_action_card.clicked.connect(self._clear_all)
        actions_group.addSettingCard(self._clear_action_card)
        self.layout.addWidget(actions_group)

        # Текстовый редактор (вместо списка)
        editor_card = SettingsCard(self._tr("page.custom_ipset.section.editor", "ipset-all.user.txt (редактор)"))
        self._editor_card = editor_card
        editor_layout = QVBoxLayout()
        editor_layout.setSpacing(8)

        self.text_edit = ScrollBlockingPlainTextEdit()
        self.text_edit.setPlaceholderText(
            self._tr(
                "page.custom_ipset.editor.placeholder",
                "IP/подсети по одному на строку:\n"
                "192.168.0.1\n"
                "10.0.0.0/8\n\n"
                "Комментарии начинаются с #",
            )
        )
        base_editor_style = f"""
            QPlainTextEdit {{
                background: {tokens.surface_bg};
                border: 1px solid {tokens.surface_border};
                border-radius: 8px;
                padding: 12px;
                color: {tokens.fg};
                font-family: Consolas, 'Courier New', monospace;
                font-size: 13px;
            }}
            QPlainTextEdit:focus {{
                border: 1px solid {tokens.accent_hex};
            }}
        """
        self.text_edit.setStyleSheet(base_editor_style)
        self.text_edit.setMinimumHeight(350)

        # Автосохранение
        self._save_timer = QTimer()
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._auto_save)
        self.text_edit.textChanged.connect(self._on_text_changed)

        editor_layout.addWidget(self.text_edit)

        self._hint_label = CaptionLabel(
            self._tr("page.custom_ipset.hint.autosave", "💡 Изменения сохраняются автоматически через 500мс")
        )
        self._hint_label.setStyleSheet(f"color: {tokens.fg_faint};")
        editor_layout.addWidget(self._hint_label)

        # Метка ошибок валидации
        self.error_label = CaptionLabel()
        try:
            from qfluentwidgets import isDarkTheme as _idt
            _err_clr = "#ff6b6b" if _idt() else "#dc2626"
        except Exception:
            _err_clr = "#dc2626"
        self.error_label.setStyleSheet(f"color: {_err_clr};")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        editor_layout.addWidget(self.error_label)

        editor_card.add_layout(editor_layout)
        self.layout.addWidget(editor_card)

        self.status_label = CaptionLabel()
        self.status_label.setStyleSheet(f"color: {tokens.fg_faint};")
        self.layout.addWidget(self.status_label)
        
        # Стили для валидации
        self._normal_style = base_editor_style
        self._error_style = f"""
            QPlainTextEdit {{
                background: rgba(255, 100, 100, 0.08);
                border: 2px solid #ff6b6b;
                border-radius: 8px;
                padding: 12px;
                color: {tokens.fg};
                font-family: Consolas, 'Courier New', monospace;
                font-size: 13px;
            }}
        """
        self._has_validation_error = False

    def _load_entries(self):
        """Загружает пользовательский список из ipset-all.user.txt."""
        try:
            state = self._controller.load_custom_ipset_text()

            # Блокируем сигнал чтобы не срабатывало автосохранение
            self.text_edit.blockSignals(True)
            self.text_edit.setPlainText(state.text)
            self.text_edit.blockSignals(False)
            self._status_state["saved"] = False
            self._update_status()
            log(f"Загружено {state.lines_count} строк из ipset-all.user.txt", "INFO")
        except Exception as e:
            log(f"Ошибка загрузки ipset-all.user.txt: {e}", "ERROR")
            self._status_state["error_key"] = "page.custom_ipset.status.error_load"
            self._status_state["error_default"] = "❌ Ошибка загрузки: {error}"
            self._status_state["error_kwargs"] = {"error": e}
            self._status_state["error_text"] = ""
            self._render_status_label()

    def _render_status_label(self) -> None:
        if self._status_state.get("error_key"):
            self.status_label.setText(
                self._tr(
                    self._status_state["error_key"],
                    self._status_state.get("error_default") or "",
                    **(self._status_state.get("error_kwargs") or {}),
                )
            )
            return
        if self._status_state.get("error_text"):
            self.status_label.setText(self._status_state["error_text"])
            return

        summary = self._tr(
            "page.custom_ipset.status.summary",
            "📊 Записей: {total} (база: {base}, пользовательские: {user})",
            total=self._status_state["total"],
            base=self._status_state["base"],
            user=self._status_state["user"],
        )
        if self._status_state.get("saved"):
            summary += self._tr("page.custom_ipset.status.saved_suffix", " • ✅ Сохранено")
        self.status_label.setText(summary)

    def _render_validation_error(self) -> None:
        if not self._invalid_line_items:
            self.error_label.clear()
            self.error_label.hide()
            return

        lines = [
            self._tr("page.custom_ipset.validation.line", "Строка {line}: {value}", line=line, value=value)
            for line, value in self._invalid_line_items[:5]
        ]
        text = self._tr("page.custom_ipset.validation.invalid_prefix", "❌ Неверный формат:\n") + "\n".join(lines)
        if len(self._invalid_line_items) > 5:
            text += self._tr(
                "page.custom_ipset.validation.more_suffix",
                "\n... и ещё {count}",
                count=len(self._invalid_line_items) - 5,
            )
        self.error_label.setText(text)
        self.error_label.show()

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)

        if self._desc_label is not None:
            self._desc_label.setText(
                self._tr(
                    "page.custom_ipset.description",
                    "Добавляйте свои IP/подсети в ipset-all.user.txt.\n"
                    "• Одиночный IP: 1.2.3.4\n"
                    "• Подсеть: 10.0.0.0/8\n"
                    "Диапазоны (a-b) не поддерживаются.\n"
                    "Системная база хранится в ipset-all.base.txt и объединяется автоматически в ipset-all.txt.",
                )
            )
        if self._add_card is not None:
            self._add_card.set_title(self._tr("page.custom_ipset.section.add", "Добавить IP/подсеть"))
        if self._actions_card is not None:
            self._actions_card.set_title(self._tr("page.custom_ipset.section.actions", "Действия"))
        if self._actions_group is not None:
            try:
                self._actions_group.titleLabel.setText(self._tr("page.custom_ipset.section.actions", "Действия"))
            except Exception:
                pass
        if self._editor_card is not None:
            self._editor_card.set_title(self._tr("page.custom_ipset.section.editor", "ipset-all.user.txt (редактор)"))

        self.input.setPlaceholderText(
            self._tr("page.custom_ipset.input.placeholder", "Например: 1.2.3.4 или 10.0.0.0/8")
        )
        self.add_btn.setText(self._tr("page.custom_ipset.button.add", "Добавить"))
        if self.open_btn is not None:
            self.open_btn.setText(self._tr("page.custom_ipset.button.open_file", "Открыть файл"))
        if self.clear_btn is not None:
            self.clear_btn.setText(self._tr("page.custom_ipset.button.clear_all", "Очистить всё"))
        if self._open_action_card is not None:
            self._open_action_card.setTitle(self._tr("page.custom_ipset.button.open_file", "Открыть файл"))
            self._open_action_card.setContent(
                self._tr(
                    "page.custom_ipset.action.open_file.description",
                    "Сохраняет изменения и открывает ipset-all.user.txt в проводнике.",
                )
            )
            self._open_action_card.button.setText(self._tr("page.custom_ipset.button.open_file", "Открыть файл"))
        if self._clear_action_card is not None:
            self._clear_action_card.setTitle(self._tr("page.custom_ipset.button.clear_all", "Очистить всё"))
            self._clear_action_card.setContent(
                self._tr(
                    "page.custom_ipset.action.clear_all.description",
                    "Удаляет все пользовательские записи из ipset-all.user.txt.",
                )
            )
            self._clear_action_card.button.setText(self._tr("page.custom_ipset.button.clear_all", "Очистить всё"))
        self.text_edit.setPlaceholderText(
            self._tr(
                "page.custom_ipset.editor.placeholder",
                "IP/подсети по одному на строку:\n"
                "192.168.0.1\n"
                "10.0.0.0/8\n\n"
                "Комментарии начинаются с #",
            )
        )
        if self._hint_label is not None:
            self._hint_label.setText(
                self._tr("page.custom_ipset.hint.autosave", "💡 Изменения сохраняются автоматически через 500мс")
            )

        self._render_validation_error()
        self._render_status_label()

    def _on_text_changed(self):
        self._save_timer.start(500)
        self._status_state["saved"] = False
        self._status_state["error_key"] = None
        self._status_state["error_default"] = ""
        self._status_state["error_kwargs"] = {}
        self._status_state["error_text"] = ""
        self._status_timer.start(120)

    def _auto_save(self):
        self._save_entries()
        self._status_state["saved"] = True
        self._render_status_label()

    def _save_entries(self):
        """Сохраняет пользовательский список в ipset-all.user.txt."""
        try:
            text = self.text_edit.toPlainText()
            state = self._controller.save_custom_ipset_text(text)

            # Обновляем UI - заменяем URL на IP
            new_text = state.normalized_text
            if new_text != text:
                cursor = self.text_edit.textCursor()
                pos = cursor.position()
                
                self.text_edit.blockSignals(True)
                self.text_edit.setPlainText(new_text)
                
                # Восстанавливаем позицию курсора
                cursor = self.text_edit.textCursor()
                cursor.setPosition(min(pos, len(new_text)))
                self.text_edit.setTextCursor(cursor)
                self.text_edit.blockSignals(False)

            log(f"Сохранено {state.saved_count} строк в ipset-all.user.txt", "SUCCESS")
            self.ipset_changed.emit()
        except Exception as e:
            log(f"Ошибка сохранения ipset-all.user.txt: {e}", "ERROR")

    def _update_status(self):
        plan = self._controller.build_custom_ipset_status_plan(self.text_edit.toPlainText())

        # Обновляем UI
        if plan.invalid_lines:
            if not self._has_validation_error:
                self.text_edit.setStyleSheet(self._error_style)
                self._has_validation_error = True
            self._invalid_line_items = plan.invalid_lines
            self._render_validation_error()
        else:
            if self._has_validation_error:
                self.text_edit.setStyleSheet(self._normal_style)
                self._has_validation_error = False
            self._invalid_line_items = []
            self._render_validation_error()

        self._status_state["total"] = plan.total_count
        self._status_state["base"] = plan.base_count
        self._status_state["user"] = plan.user_count
        self._status_state["error_key"] = None
        self._status_state["error_default"] = ""
        self._status_state["error_kwargs"] = {}
        self._status_state["error_text"] = ""
        self._render_status_label()

    def _add_entry(self):
        plan = self._controller.build_add_custom_ipset_plan(
            raw_text=self.input.text().strip(),
            current_text=self.text_edit.toPlainText(),
        )
        if plan.new_text is None and plan.level is None:
            return

        if plan.level == "warning":
            if InfoBar:
                InfoBar.warning(
                    title=self._tr("common.error.title", "Ошибка"),
                    content=plan.content,
                    parent=self.window(),
                )
            return
        if plan.level == "info":
            if InfoBar:
                InfoBar.info(
                    title=self._tr("page.custom_ipset.infobar.info_title", "Информация"),
                    content=plan.content,
                    parent=self.window(),
                )
            return

        self.text_edit.setPlainText(plan.new_text or "")
        if plan.clear_input:
            self.input.clear()

    def _clear_all(self):
        text = self.text_edit.toPlainText().strip()
        if not text:
            return
        if MessageBox:
            box = MessageBox(
                self._tr("page.custom_ipset.dialog.clear.title", "Очистить всё"),
                self._tr("page.custom_ipset.dialog.clear.body", "Удалить все записи?"),
                self.window(),
            )
            if box.exec():
                self.text_edit.clear()
                log("Пользовательские записи ipset-all.user.txt удалены", "INFO")
        else:
            self.text_edit.clear()
            log("Пользовательские записи ipset-all.user.txt удалены", "INFO")

    def _open_file(self):
        try:
            # Сохраняем перед открытием
            self._save_entries()
            self._controller.open_ipset_all_user_file()
        except Exception as e:
            log(f"Ошибка открытия ipset-all.user.txt: {e}", "ERROR")
            if InfoBar:
                InfoBar.warning(
                    title=self._tr("common.error.title", "Ошибка"),
                    content=self._tr("page.custom_ipset.error.open_file", "Не удалось открыть:\n{error}", error=e),
                    parent=self.window(),
                )
