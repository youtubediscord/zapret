# ui/pages/dns_check_page.py
"""Страница проверки DNS подмены провайдером."""

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QWidget
)
from PyQt6.QtCore import QThread, Qt
from PyQt6.QtGui import QFont, QTextCursor
import qtawesome as qta

from .base_page import BasePage, ScrollBlockingTextEdit
from dns.dns_check_page_controller import DNSCheckPageController
from ui.compat_widgets import SettingsCard
from ui.theme import get_theme_tokens
from ui.theme_semantic import get_semantic_palette
from ui.text_catalog import tr as tr_catalog

from qfluentwidgets import (
    IndeterminateProgressBar,
    InfoBar,
    SettingCardGroup,
    PushSettingCard,
    PrimaryPushSettingCard,
    StrongBodyLabel,
    BodyLabel,
    CaptionLabel,
)


class DNSCheckPage(BasePage):
    """Страница проверки DNS подмены провайдером."""
    
    def __init__(self, parent=None):
        super().__init__(
            "Проверка DNS подмены",
            "Проверка резолвинга доменов YouTube и Discord через различные DNS серверы",
            parent,
            title_key="page.dns_check.title",
            subtitle_key="page.dns_check.subtitle",
        )
        self.worker = None
        self.thread = None
        self._controller = DNSCheckPageController()
        self._status_tone = "muted"
        self._status_bold = False
        self._info_icon_labels = []
        self._info_text_labels = []
        self._info_item_keys = [
            "page.dns_check.info.blocking",
            "page.dns_check.info.servers",
            "page.dns_check.info.recommended",
        ]
        self._actions_group = None
        self._start_action_card = None
        self._quick_action_card = None
        self._save_action_card = None

        self.enable_deferred_ui_build(after_build=self._after_ui_built)

    def _after_ui_built(self) -> None:
        self._apply_page_theme(force=True)

    def _apply_interaction_state(
        self,
        *,
        check_enabled: bool,
        quick_enabled: bool,
        save_enabled: bool,
        progress_visible: bool,
    ) -> None:
        self.check_button.setEnabled(check_enabled)
        self.quick_check_button.setEnabled(quick_enabled)
        self.save_button.setEnabled(save_enabled)
        self.progress_bar.setVisible(progress_visible)
        if progress_visible:
            self.progress_bar.start()
        else:
            self.progress_bar.stop()
        try:
            if self._start_action_card is not None:
                self._start_action_card.setEnabled(check_enabled)
            if self._quick_action_card is not None:
                self._quick_action_card.setEnabled(quick_enabled)
            if self._save_action_card is not None:
                self._save_action_card.setEnabled(save_enabled)
        except Exception:
            pass
    
    def _build_ui(self):
        """Создаёт интерфейс страницы."""
        tokens = get_theme_tokens()
        # Информационная карточка
        self.info_card = SettingsCard(tr_catalog("page.dns_check.card.what_we_check", language=self._ui_language, default="Что проверяем"))
        info_layout = QVBoxLayout()
        info_layout.setSpacing(8)
        
        info_items = [
            ("fa5s.search", self._info_item_keys[0], "Блокирует ли провайдер сайты через DNS подмену"),
            ("fa5s.server", self._info_item_keys[1], "Какие DNS серверы возвращают корректные адреса"),
            ("fa5s.check-circle", self._info_item_keys[2], "Какой DNS сервер рекомендуется использовать"),
        ]
        
        for icon_name, text_key, default_text in info_items:
            row = QHBoxLayout()
            row.setSpacing(10)
            
            try:
                import qtawesome as qta
                icon_label = QLabel()
                icon_label.setProperty("dnsIconName", icon_name)
                icon_label.setPixmap(qta.icon(icon_name, color=tokens.accent_hex).pixmap(16, 16))
                icon_label.setFixedWidth(20)
                self._info_icon_labels.append(icon_label)
                row.addWidget(icon_label)
            except:
                pass
            
            text_label = BodyLabel(tr_catalog(text_key, language=self._ui_language, default=default_text))
            text_label.setStyleSheet(f"color: {tokens.fg_muted};")
            text_label.setProperty("textKey", text_key)
            text_label.setProperty("textDefault", default_text)
            self._info_text_labels.append(text_label)
            row.addWidget(text_label, 1)
            
            info_layout.addLayout(row)
        
        self.info_card.add_layout(info_layout)
        self.layout.addWidget(self.info_card)
        
        # Карточка с управлением
        self.control_card = SettingsCard(tr_catalog("page.dns_check.card.testing", language=self._ui_language, default="Тестирование"))
        
        # Прогресс бар
        self.progress_bar = IndeterminateProgressBar(self)
        self.progress_bar.setVisible(False)
        self.control_card.add_widget(self.progress_bar)
        
        # Статус
        self.status_label = CaptionLabel(tr_catalog("page.dns_check.status.ready", language=self._ui_language, default="Готово к проверке"))
        self._set_status(tr_catalog("page.dns_check.status.ready", language=self._ui_language, default="Готово к проверке"), tone="muted", bold=False)
        self.control_card.add_widget(self.status_label)

        self.layout.addWidget(self.control_card)

        # Действия
        self._actions_group = SettingCardGroup(
            tr_catalog("page.dns_check.section.actions", language=self._ui_language, default="Действия"),
            self.content,
        )

        self._start_action_card = PrimaryPushSettingCard(
            tr_catalog("page.dns_check.button.start", language=self._ui_language, default="Начать проверку"),
            qta.icon("fa5s.play", color="#4CAF50"),
            tr_catalog("page.dns_check.button.start", language=self._ui_language, default="Начать проверку"),
            tr_catalog(
                "page.dns_check.action.start.description",
                language=self._ui_language,
                default="Полностью проверить DNS-резолвинг через разные серверы и собрать расширенный отчёт.",
            ),
        )
        self._start_action_card.clicked.connect(self.start_check)
        self.check_button = self._start_action_card.button
        self._actions_group.addSettingCard(self._start_action_card)

        self._quick_action_card = PushSettingCard(
            tr_catalog("page.dns_check.button.quick", language=self._ui_language, default="Быстрая проверка"),
            qta.icon("fa5s.bolt", color="#60cdff"),
            tr_catalog("page.dns_check.button.quick", language=self._ui_language, default="Быстрая проверка"),
            tr_catalog(
                "page.dns_check.action.quick.description",
                language=self._ui_language,
                default="Сделать быстрый тест только текущего системного DNS без полного сценария.",
            ),
        )
        self._quick_action_card.clicked.connect(self.quick_dns_check)
        self.quick_check_button = self._quick_action_card.button
        self._actions_group.addSettingCard(self._quick_action_card)

        self._save_action_card = PushSettingCard(
            tr_catalog("page.dns_check.button.save", language=self._ui_language, default="Сохранить результаты"),
            qta.icon("fa5s.save", color="#ff9800"),
            tr_catalog("page.dns_check.button.save", language=self._ui_language, default="Сохранить результаты"),
            tr_catalog(
                "page.dns_check.action.save.description",
                language=self._ui_language,
                default="Сохранить текущий отчёт DNS-проверки в текстовый файл.",
            ),
        )
        self._save_action_card.setEnabled(False)
        self._save_action_card.clicked.connect(self.save_results)
        self.save_button = self._save_action_card.button
        self._actions_group.addSettingCard(self._save_action_card)

        self.layout.addWidget(self._actions_group)
        
        # Результаты
        self.results_card = SettingsCard(tr_catalog("page.dns_check.card.results", language=self._ui_language, default="Результаты"))
        
        self.result_text = ScrollBlockingTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setFont(QFont("Consolas", 10))
        self.result_text.setMinimumHeight(300)
        self.result_text.setStyleSheet(
            f"""
            QTextEdit {{
                background-color: {tokens.surface_bg};
                color: {tokens.fg};
                border: 1px solid {tokens.surface_border};
                border-radius: 6px;
                padding: 12px;
            }}
            """
        )
        self.results_card.add_widget(self.result_text)
        
        self.layout.addWidget(self.results_card)
        
        # Stretch в конце
        self.layout.addStretch()

    def _set_status(self, text: str, *, tone: str, bold: bool) -> None:
        tokens = get_theme_tokens()
        semantic = get_semantic_palette()
        tone_map = {
            "muted": tokens.fg_muted,
            "accent": tokens.accent_hex,
            "success": semantic.success,
            "warning": semantic.warning,
            "error": semantic.error,
        }
        color = tone_map.get(tone, tokens.fg_muted)
        self.status_label.setText(text)
        self.status_label.setStyleSheet(
            f"color: {color}; padding: 4px 0;"
        )
        self._status_tone = tone
        self._status_bold = bold

    def _apply_page_theme(self, tokens=None, force: bool = False) -> None:
        _ = force
        tokens = tokens or get_theme_tokens()
        for label in list(self._info_text_labels):
            try:
                label.setStyleSheet(f"color: {tokens.fg_muted};")
            except Exception:
                pass

        try:
            import qtawesome as qta

            for icon_label in list(self._info_icon_labels):
                try:
                    icon_name = (icon_label.property("dnsIconName") or "fa5s.search").strip()
                    icon_label.setPixmap(qta.icon(icon_name, color=tokens.accent_hex).pixmap(16, 16))
                except Exception:
                    pass
        except Exception:
            pass

        try:
            self.result_text.setStyleSheet(
                f"""
                QTextEdit {{
                    background-color: {tokens.surface_bg};
                    color: {tokens.fg};
                    border: 1px solid {tokens.surface_border};
                    border-radius: 6px;
                    padding: 12px;
                }}
                """
            )
        except Exception:
            pass

        try:
            self._set_status(self.status_label.text(), tone=self._status_tone, bold=self._status_bold)
        except Exception:
            pass

    def start_check(self):
        """Начинает полную проверку DNS."""
        if self.thread and self.thread.isRunning():
            return
        
        self.result_text.clear()
        start_plan = self._controller.build_start_plan()
        self._apply_interaction_state(
            check_enabled=start_plan.check_enabled,
            quick_enabled=start_plan.quick_enabled,
            save_enabled=start_plan.save_enabled,
            progress_visible=start_plan.progress_visible,
        )
        self._set_status(start_plan.status_text, tone=start_plan.status_tone, bold=False)
        
        # Создаём поток и worker
        self.thread = QThread()
        self.worker = self._controller.create_worker()
        self.worker.moveToThread(self.thread)
        
        # Подключаем сигналы
        self.thread.started.connect(self.worker.run)
        self.worker.update_signal.connect(self.append_result)
        self.worker.finished_signal.connect(self.on_check_finished)
        
        # Запускаем
        self.thread.start()
    
    def append_result(self, text):
        """Добавляет текст в результаты с форматированием."""
        tokens = get_theme_tokens()
        semantic = get_semantic_palette()
        plan = self._controller.build_result_line_plan(text)
        role_map = {
            "success": semantic.success,
            "error": semantic.error,
            "warning": semantic.warning,
            "blocked": "#e91e63",
            "accent": tokens.accent_hex,
            "faint": tokens.fg_faint,
            "normal": tokens.fg,
        }
        color = role_map.get(plan.color_role, tokens.fg)
        
        # Форматируем текст
        formatted_text = f'<span style="color: {color};">{text}</span>'
        
        # Добавляем в текстовое поле
        cursor = self.result_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(formatted_text + "<br>")
        
        # Автопрокрутка
        self.result_text.verticalScrollBar().setValue(
            self.result_text.verticalScrollBar().maximum()
        )
    
    def on_check_finished(self, results):
        """Обработчик завершения проверки."""
        # Обновляем статус
        plan = self._controller.build_finish_plan(results)
        self._apply_interaction_state(
            check_enabled=plan.check_enabled,
            quick_enabled=plan.quick_enabled,
            save_enabled=plan.save_enabled,
            progress_visible=plan.progress_visible,
        )
        self._set_status(plan.status_text, tone=plan.status_tone, bold=True)
        
        # Очистка потока
        cleanup_plan = self._controller.build_cleanup_plan(
            has_thread=self.thread is not None,
            has_worker=self.worker is not None,
            thread_running=bool(self.thread and self.thread.isRunning()),
        )
        if cleanup_plan.should_quit_thread and self.thread:
            self.thread.quit()
            self.thread.wait(cleanup_plan.wait_timeout_ms)
        if cleanup_plan.should_delete_thread and self.thread:
            self.thread.deleteLater()
            self.thread = None
        if cleanup_plan.should_delete_worker and self.worker:
            self.worker.deleteLater()
            self.worker = None
    
    def quick_dns_check(self):
        """Выполняет быструю проверку только системного DNS."""
        self.result_text.clear()
        plan = self._controller.run_quick_dns_check()
        for line in plan.lines:
            self.append_result(line)
        self.save_button.setEnabled(plan.enable_save)
    
    def save_results(self):
        """Сохраняет результаты в файл."""
        from PyQt6.QtWidgets import QFileDialog
        
        # Выбираем путь для сохранения
        default_filename = self._controller.build_save_default_filename()
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить результаты DNS проверки",
            default_filename,
            "Text Files (*.txt);;All Files (*.*)"
        )
        
        if file_path:
            plan = self._controller.save_results_text(
                file_path=file_path,
                plain_text=self.result_text.toPlainText(),
            )
            if InfoBar:
                if plan.success:
                    InfoBar.success(title=plan.title, content=plan.content, parent=self.window())
                else:
                    InfoBar.error(title=plan.title, content=plan.content, parent=self.window())
    
    def cleanup(self):
        """Очистка потоков при закрытии"""
        from log import log
        try:
            cleanup_plan = self._controller.build_cleanup_plan(
                has_thread=self.thread is not None,
                has_worker=self.worker is not None,
                thread_running=bool(self.thread and self.thread.isRunning()),
            )
            if cleanup_plan.should_quit_thread and self.thread and self.thread.isRunning():
                log("Останавливаем DNS check worker...", "DEBUG")
                self.thread.quit()
                if not self.thread.wait(cleanup_plan.wait_timeout_ms):
                    log("⚠ DNS check worker не завершился, принудительно завершаем", "WARNING")
                    try:
                        self.thread.terminate()
                        self.thread.wait(500)
                    except:
                        pass
            if cleanup_plan.should_delete_thread and self.thread is not None:
                self.thread.deleteLater()
                self.thread = None
            if cleanup_plan.should_delete_worker and self.worker is not None:
                self.worker.deleteLater()
                self.worker = None
        except Exception as e:
            log(f"Ошибка при очистке dns_check_page: {e}", "DEBUG")

    def _set_card_title(self, card: SettingsCard, text: str) -> None:
        try:
            card.set_title(text)
        except Exception:
            pass

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)

        self._set_card_title(self.info_card, tr_catalog("page.dns_check.card.what_we_check", language=self._ui_language, default="Что проверяем"))
        self._set_card_title(self.control_card, tr_catalog("page.dns_check.card.testing", language=self._ui_language, default="Тестирование"))
        self._set_card_title(self.results_card, tr_catalog("page.dns_check.card.results", language=self._ui_language, default="Результаты"))
        try:
            title_label = getattr(getattr(self, "_actions_group", None), "titleLabel", None)
            if title_label is not None:
                title_label.setText(tr_catalog("page.dns_check.section.actions", language=self._ui_language, default="Действия"))
        except Exception:
            pass

        for label in list(self._info_text_labels):
            try:
                key = label.property("textKey")
                default = label.property("textDefault")
                label.setText(tr_catalog(str(key), language=self._ui_language, default=str(default or "")))
            except Exception:
                pass

        self.check_button.setText(tr_catalog("page.dns_check.button.start", language=self._ui_language, default="Начать проверку"))
        self.quick_check_button.setText(tr_catalog("page.dns_check.button.quick", language=self._ui_language, default="Быстрая проверка"))
        self.save_button.setText(tr_catalog("page.dns_check.button.save", language=self._ui_language, default="Сохранить результаты"))
        if self._start_action_card is not None:
            self._start_action_card.setTitle(tr_catalog("page.dns_check.button.start", language=self._ui_language, default="Начать проверку"))
            self._start_action_card.setContent(
                tr_catalog(
                    "page.dns_check.action.start.description",
                    language=self._ui_language,
                    default="Полностью проверить DNS-резолвинг через разные серверы и собрать расширенный отчёт.",
                )
            )
        if self._quick_action_card is not None:
            self._quick_action_card.setTitle(tr_catalog("page.dns_check.button.quick", language=self._ui_language, default="Быстрая проверка"))
            self._quick_action_card.setContent(
                tr_catalog(
                    "page.dns_check.action.quick.description",
                    language=self._ui_language,
                    default="Сделать быстрый тест только текущего системного DNS без полного сценария.",
                )
            )
        if self._save_action_card is not None:
            self._save_action_card.setTitle(tr_catalog("page.dns_check.button.save", language=self._ui_language, default="Сохранить результаты"))
            self._save_action_card.setContent(
                tr_catalog(
                    "page.dns_check.action.save.description",
                    language=self._ui_language,
                    default="Сохранить текущий отчёт DNS-проверки в текстовый файл.",
                )
            )
