# lists/ui/custom_domains_page.py
"""Страница управления пользовательскими доменами (lists/user/other.txt)."""

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit
)
import qtawesome as qta
try:
    from qfluentwidgets import LineEdit, InfoBar, MessageBox, SettingCardGroup
    _HAS_FLUENT = True
except ImportError:
    LineEdit = QLineEdit
    InfoBar = None
    MessageBox = None  # type: ignore[assignment]
    SettingCardGroup = None  # type: ignore[assignment]
    _HAS_FLUENT = False

try:
    from qfluentwidgets import StrongBodyLabel, BodyLabel, CaptionLabel
    _HAS_FLUENT_LABELS = True
except ImportError:
    StrongBodyLabel = QLabel; BodyLabel = QLabel; CaptionLabel = QLabel
    _HAS_FLUENT_LABELS = False

from ui.pages.base_page import BasePage, ScrollBlockingPlainTextEdit
from lists.controller import HostlistPageController
from ui.compat_widgets import (
    SettingsCard,
    ActionButton,
    PrimaryActionButton,
    QuickActionsBar,
    insert_widget_into_setting_card_group,
    set_tooltip,
)
from ui.theme import get_theme_tokens
from ui.text_catalog import tr as tr_catalog
from log.log import log



class CustomDomainsPage(BasePage):
    """Страница управления пользовательскими доменами"""
    
    domains_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(
            "Кастомные (мои) домены (hostlist) для работы с Zapret",
            "Управление доменами (other.txt). Субдомены учитываются автоматически. Строчка rkn.ru учитывает и сайт fuckyou.rkn.ru и сайт ass.rkn.ru. Чтобы исключить субдомены напишите домен с символов ^ в начале, то есть например так ^rkn.ru",
            parent,
            title_key="page.custom_domains.title",
            subtitle_key="page.custom_domains.subtitle",
        )
        self._runtime_initialized = False
        self._cleanup_in_progress = False
        self._actions_group = None
        self._actions_bar = None
        self.open_file_btn = None
        self.reset_btn = None
        self.clear_btn = None
        self._build_ui()
        self._apply_page_theme(force=True)
        self._run_runtime_init_once()

    def _run_runtime_init_once(self) -> None:
        if self._runtime_initialized:
            return
        self._runtime_initialized = True
        QTimer.singleShot(0, lambda: (not self._cleanup_in_progress) and self._load_domains())

    def _tr(self, key: str, default: str) -> str:
        return tr_catalog(key, language=self._ui_language, default=default)
        
    def _build_ui(self):
        """Строит UI страницы"""
        tokens = get_theme_tokens()
        
        # Описание
        desc_card = SettingsCard()
        self._desc_label = BodyLabel(
            self._tr(
                "page.custom_domains.description",
                "Здесь редактируется пользовательский список доменов `lists/user/other.txt`. Системная база лежит в `lists/base/other.txt`, а итоговый `lists/other.txt` собирается автоматически. URL автоматически преобразуются в домены. Изменения сохраняются автоматически. Поддерживается Ctrl+Z.",
            )
        )
        try:
            self._desc_label.setProperty("tone", "muted")
        except Exception:
            pass
        self._desc_label.setWordWrap(True)
        desc_card.add_widget(self._desc_label)
        self.layout.addWidget(desc_card)
        
        # Добавление домена
        self._add_card = SettingsCard(self._tr("page.custom_domains.card.add", "Добавить домен"))
        add_layout = QHBoxLayout()
        add_layout.setSpacing(8)
        
        self.domain_input = LineEdit()
        self.domain_input.setPlaceholderText(
            self._tr(
                "page.custom_domains.input.placeholder",
                "Введите домен или URL (например: example.com или https://site.com/page)",
            )
        )
        self.domain_input.returnPressed.connect(self._add_domain)
        add_layout.addWidget(self.domain_input, 1)

        self.add_btn = PrimaryActionButton(self._tr("page.custom_domains.button.add", "Добавить"), "fa5s.plus")
        self.add_btn.setFixedHeight(38)
        self.add_btn.clicked.connect(self._add_domain)
        add_layout.addWidget(self.add_btn)
        
        self._add_card.add_layout(add_layout)
        self.layout.addWidget(self._add_card)
        
        # Действия
        self._actions_group = SettingCardGroup(
            self._tr("page.custom_domains.card.actions", "Действия"),
            self.content,
        )
        self._actions_bar = QuickActionsBar(self.content)

        self.open_file_btn = ActionButton(
            self._tr("page.custom_domains.button.open_file", "Открыть файл"),
            "fa5s.external-link-alt",
        )
        self.open_file_btn.clicked.connect(self._open_file)
        set_tooltip(
            self.open_file_btn,
            self._tr("page.custom_domains.tooltip.open_file", "Сохраняет изменения и открывает `lists/user/other.txt` в проводнике"),
        )

        self.reset_btn = ActionButton(
            self._tr("page.custom_domains.button.reset_file", "Сбросить файл"),
            "fa5s.undo",
        )
        self.reset_btn.clicked.connect(self._confirm_reset_file)
        set_tooltip(
            self.reset_btn,
            self._tr(
                "page.custom_domains.tooltip.reset_file",
                "Очищает `lists/user/other.txt` и пересобирает `lists/other.txt` из системной базы",
            ),
        )

        self.clear_btn = ActionButton(
            self._tr("page.custom_domains.button.clear_all", "Очистить всё"),
            "fa5s.trash-alt",
        )
        self.clear_btn.clicked.connect(self._confirm_clear_all)
        set_tooltip(
            self.clear_btn,
            self._tr(
                "page.custom_domains.tooltip.clear_all",
                "Удаляет только пользовательские домены. Системная база из `lists/base/other.txt` останется",
            ),
        )

        self._actions_bar.add_buttons([self.open_file_btn, self.reset_btn, self.clear_btn])
        insert_widget_into_setting_card_group(self._actions_group, 1, self._actions_bar)
        self.layout.addWidget(self._actions_group)
        
        # Текстовый редактор (вместо списка)
        self._editor_card = SettingsCard(self._tr("page.custom_domains.card.editor", "lists/user/other.txt (редактор)"))
        editor_layout = QVBoxLayout()
        editor_layout.setSpacing(8)
        
        self.text_edit = ScrollBlockingPlainTextEdit()
        self.text_edit.setPlaceholderText(
            self._tr(
                "page.custom_domains.editor.placeholder",
                "Домены по одному на строку:\nexample.com\nsubdomain.site.org\n\nКомментарии начинаются с #",
            )
        )
        self.text_edit.setStyleSheet(
            f"""
            QPlainTextEdit {{
                background: {tokens.surface_bg};
                border: 1px solid {tokens.surface_border};
                border-radius: 8px;
                padding: 12px;
                color: {tokens.fg};
                font-family: Consolas, 'Courier New', monospace;
                font-size: 13px;
            }}
            QPlainTextEdit:hover {{
                background: {tokens.surface_bg_hover};
                border: 1px solid {tokens.surface_border_hover};
            }}
            QPlainTextEdit:focus {{
                border: 1px solid {tokens.accent_hex};
            }}
            """
        )
        self.text_edit.setMinimumHeight(350)
        
        # Автосохранение
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._auto_save)
        self.text_edit.textChanged.connect(self._on_text_changed)
        
        editor_layout.addWidget(self.text_edit)
        
        # Подсказка
        self._hint_label = CaptionLabel(
            self._tr("page.custom_domains.hint.autosave", "Изменения сохраняются автоматически через 500мс")
        )
        try:
            self._hint_label.setProperty("tone", "faint")
        except Exception:
            pass
        editor_layout.addWidget(self._hint_label)
        
        self._editor_card.add_layout(editor_layout)
        self.layout.addWidget(self._editor_card)
        
        # Статистика
        self.status_label = CaptionLabel()
        try:
            self.status_label.setProperty("tone", "muted")
        except Exception:
            pass
        self.layout.addWidget(self.status_label)

        # Apply token-based styles (also used on theme change).
        self._apply_page_theme(force=True)

    def _apply_page_theme(self, tokens=None, force: bool = False) -> None:
        _ = force
        tokens = tokens or get_theme_tokens()

        try:
            if hasattr(self, "text_edit") and self.text_edit is not None:
                self.text_edit.setStyleSheet(
                    f"""
                    QPlainTextEdit {{
                        background: {tokens.surface_bg};
                        border: 1px solid {tokens.surface_border};
                        border-radius: 8px;
                        padding: 12px;
                        color: {tokens.fg};
                        font-family: Consolas, 'Courier New', monospace;
                        font-size: 13px;
                    }}
                    QPlainTextEdit:hover {{
                        background: {tokens.surface_bg_hover};
                        border: 1px solid {tokens.surface_border_hover};
                    }}
                    QPlainTextEdit:focus {{
                        border: 1px solid {tokens.accent_hex};
                    }}
                    """
                )
        except Exception:
            pass

    def _load_domains(self):
        """Загружает домены из файла"""
        if self._cleanup_in_progress:
            return
        try:
            state = HostlistPageController.load_custom_domains_text()
            
            # Блокируем сигнал чтобы не срабатывало автосохранение
            self.text_edit.blockSignals(True)
            self.text_edit.setPlainText(state.text)
            self.text_edit.blockSignals(False)
            
            self._update_status()
            log(f"Загружено {state.lines_count} строк из lists/user/other.txt", "INFO")

        except Exception as e:
            log(f"Ошибка загрузки доменов: {e}", "ERROR")
            self.status_label.setText(
                self._tr("page.custom_domains.status.error", "❌ Ошибка: {error}").format(error=e)
            )
            
    def _on_text_changed(self):
        """Запускает таймер автосохранения"""
        if self._cleanup_in_progress:
            return
        self._save_timer.start(500)
        self._update_status()
        
    def _auto_save(self):
        """Автосохранение"""
        if self._cleanup_in_progress:
            return
        self._save_domains()
        self.status_label.setText(
            self.status_label.text()
            + self._tr("page.custom_domains.status.suffix.saved", " • ✅ Сохранено")
        )
        
    def _save_domains(self):
        """Сохраняет домены в файл"""
        try:
            text = self.text_edit.toPlainText()
            state = HostlistPageController.save_custom_domains_text(text)
            
            # Обновляем UI - заменяем URL на домены
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
            
            log(f"Сохранено {state.saved_count} строк в lists/user/other.txt", "SUCCESS")
            self.domains_changed.emit()
            
        except Exception as e:
            log(f"Ошибка сохранения доменов: {e}", "ERROR")
            
    def _update_status(self):
        """Обновляет статус"""
        if self._cleanup_in_progress:
            return
        plan = HostlistPageController.build_custom_domains_status_plan(self.text_edit.toPlainText())
        self.status_label.setText(
            self._tr(
                "page.custom_domains.status.stats",
                "📊 Доменов: {total} (база: {base}, пользовательские: {user})",
            ).format(total=plan.total_count, base=plan.base_count, user=plan.user_count)
        )
        
    def _add_domain(self):
        """Добавляет домен"""
        plan = HostlistPageController.build_add_custom_domain_plan(
            raw_text=self.domain_input.text().strip(),
            current_text=self.text_edit.toPlainText(),
        )
        if plan.new_text is None and plan.level is None:
            return

        if plan.level == "warning":
            if InfoBar:
                InfoBar.warning(
                    title=self._tr("page.custom_domains.infobar.error", "Ошибка"),
                    content=plan.content,
                    parent=self.window(),
                )
            return
        if plan.level == "info":
            if InfoBar:
                InfoBar.info(
                    title=self._tr("page.custom_domains.infobar.info", "Информация"),
                    content=plan.content,
                    parent=self.window(),
                )
            return

        self.text_edit.setPlainText(plan.new_text or "")
        if plan.clear_input:
            self.domain_input.clear()
        added_domain = (plan.new_text or "").split("\n")[-1].strip()
        if added_domain:
            log(f"Добавлен домен: {added_domain}", "SUCCESS")
                
    def _clear_all(self):
        """Очищает только пользовательские домены."""
        self.text_edit.setPlainText("")
        self._save_domains()
        log("Пользовательские домены удалены", "INFO")

    def _confirm_reset_file(self):
        if MessageBox is not None:
            try:
                box = MessageBox(
                    self._tr("page.custom_domains.button.reset_file", "Сбросить файл"),
                    self._tr("page.custom_domains.confirm.reset_file", "Подтвердить сброс"),
                    self.window(),
                )
                if not box.exec():
                    return
            except Exception:
                pass
        self._reset_file()

    def _confirm_clear_all(self):
        if MessageBox is not None:
            try:
                box = MessageBox(
                    self._tr("page.custom_domains.button.clear_all", "Очистить всё"),
                    self._tr("page.custom_domains.confirm.clear_all", "Подтвердить очистку"),
                    self.window(),
                )
                if not box.exec():
                    return
            except Exception:
                pass
        self._clear_all()

    def _reset_file(self):
        """Очищает lists/user/other.txt и пересобирает lists/other.txt из базы."""
        try:
            if HostlistPageController.reset_domains_file():
                self._load_domains()
                self.status_label.setText(
                    self.status_label.text()
                    + self._tr("page.custom_domains.status.suffix.reset", " • ✅ Сброшено")
                )
            else:
                if InfoBar:
                    InfoBar.warning(
                        title=self._tr("page.custom_domains.infobar.error", "Ошибка"),
                        content=self._tr(
                            "page.custom_domains.infobar.reset_failed",
                            "Не удалось сбросить my hostlist",
                        ),
                        parent=self.window(),
                    )
        except Exception as e:
            log(f"Ошибка сброса my hostlist: {e}", "ERROR")
            if InfoBar:
                InfoBar.warning(
                    title=self._tr("page.custom_domains.infobar.error", "Ошибка"),
                    content=self._tr("page.custom_domains.infobar.reset_failed_error", "Не удалось сбросить:\n{error}").format(
                        error=e
                    ),
                    parent=self.window(),
                )
                
    def _open_file(self):
        """Открывает файл в проводнике"""
        try:
            # Сначала сохраняем
            self._save_domains()
            HostlistPageController.open_domains_user_file()
                
        except Exception as e:
            log(f"Ошибка открытия файла: {e}", "ERROR")
            if InfoBar:
                InfoBar.warning(
                    title=self._tr("page.custom_domains.infobar.error", "Ошибка"),
                    content=self._tr("page.custom_domains.infobar.open_failed", "Не удалось открыть:\n{error}").format(
                        error=e
                    ),
                    parent=self.window(),
                )

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)

        self._desc_label.setText(
            self._tr(
                "page.custom_domains.description",
                "Здесь редактируется пользовательский список доменов `lists/user/other.txt`. Системная база лежит в `lists/base/other.txt`, а итоговый `lists/other.txt` собирается автоматически. URL автоматически преобразуются в домены. Изменения сохраняются автоматически. Поддерживается Ctrl+Z.",
            )
        )
        self._add_card.set_title(self._tr("page.custom_domains.card.add", "Добавить домен"))
        if self._actions_card is not None:
            self._actions_card.set_title(self._tr("page.custom_domains.card.actions", "Действия"))
        if self._actions_group is not None:
            try:
                self._actions_group.titleLabel.setText(self._tr("page.custom_domains.card.actions", "Действия"))
            except Exception:
                pass
        self._editor_card.set_title(self._tr("page.custom_domains.card.editor", "lists/user/other.txt (редактор)"))

        self.domain_input.setPlaceholderText(
            self._tr(
                "page.custom_domains.input.placeholder",
                "Введите домен или URL (например: example.com или https://site.com/page)",
            )
        )
        self.add_btn.setText(self._tr("page.custom_domains.button.add", "Добавить"))
        if self.open_file_btn is not None:
            self.open_file_btn.setText(self._tr("page.custom_domains.button.open_file", "Открыть файл"))
            set_tooltip(
                self.open_file_btn,
                self._tr("page.custom_domains.tooltip.open_file", "Сохраняет изменения и открывает `lists/user/other.txt` в проводнике"),
            )
        if self.reset_btn is not None:
            self.reset_btn.setText(self._tr("page.custom_domains.button.reset_file", "Сбросить файл"))
            set_tooltip(
                self.reset_btn,
                self._tr(
                    "page.custom_domains.tooltip.reset_file",
                    "Очищает `lists/user/other.txt` и пересобирает `lists/other.txt` из системной базы",
                ),
            )
        if self.clear_btn is not None:
            self.clear_btn.setText(self._tr("page.custom_domains.button.clear_all", "Очистить всё"))
            set_tooltip(
                self.clear_btn,
                self._tr(
                    "page.custom_domains.tooltip.clear_all",
                    "Удаляет только пользовательские домены. Системная база из `lists/base/other.txt` останется",
                ),
            )
        self.text_edit.setPlaceholderText(
            self._tr(
                "page.custom_domains.editor.placeholder",
                "Домены по одному на строку:\nexample.com\nsubdomain.site.org\n\nКомментарии начинаются с #",
            )
        )
        self._hint_label.setText(self._tr("page.custom_domains.hint.autosave", "Изменения сохраняются автоматически через 500мс"))

        self._update_status()

    def cleanup(self) -> None:
        self._cleanup_in_progress = True
        try:
            self._save_timer.stop()
        except Exception:
            pass
