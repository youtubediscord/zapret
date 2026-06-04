# dns/ui/dns_check_page.py
"""Страница проверки DNS подмены провайдером."""

import html

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel,
)
from PyQt6.QtGui import QFont, QTextCursor

from ui.pages.base_page import BasePage, ScrollBlockingTextEdit
from ui.one_shot_worker_runtime import OneShotWorkerRuntime
import dns.dns_check_plans as dns_check_page_plans
from ui.fluent_widgets import QuickActionsBar, SettingsCard, set_tooltip
from ui.theme import get_cached_qta_pixmap, get_theme_tokens
from ui.theme_semantic import get_semantic_palette
from app.ui_texts import tr as tr_catalog

from qfluentwidgets import (
    IndeterminateProgressBar,
    FluentIcon,
    InfoBar,
    PushButton,
    StrongBodyLabel,
    BodyLabel,
    CaptionLabel,
)


class DNSCheckPage(BasePage):
    """Страница проверки DNS подмены провайдером."""
    
    def __init__(self, parent=None, *, dns_feature):
        super().__init__(
            "Проверка DNS подмены",
            "Проверка резолвинга доменов YouTube и Discord через различные DNS серверы",
            parent,
            title_key="page.dns_check.title",
            subtitle_key="page.dns_check.subtitle",
        )
        self._dns = dns_feature
        self._cleanup_in_progress = False
        self._check_runtime = OneShotWorkerRuntime()
        self._check_pending = False
        self._check_start_scheduled = False
        self._save_runtime = OneShotWorkerRuntime()
        self._save_results_pending: dict[str, str] | None = None
        self._save_results_start_scheduled = False
        self._quick_runtime = OneShotWorkerRuntime()
        self._quick_check_pending = False
        self._quick_check_start_scheduled = False
        self._status_tone = "muted"
        self._status_bold = False
        self._info_icon_labels = []
        self._info_text_labels = []
        self._info_item_keys = [
            "page.dns_check.info.blocking",
            "page.dns_check.info.servers",
            "page.dns_check.info.recommended",
        ]
        self._actions_title_label = None
        self._actions_bar = None

        self._build_ui()
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
                icon_label = QLabel()
                icon_label.setProperty("dnsIconName", icon_name)
                icon_label.setPixmap(get_cached_qta_pixmap(icon_name, color=tokens.accent_hex, size=16))
                icon_label.setFixedWidth(20)
                self._info_icon_labels.append(icon_label)
                row.addWidget(icon_label)
            except Exception:
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
        self._actions_title_label = StrongBodyLabel(
            tr_catalog("page.dns_check.section.actions", language=self._ui_language, default="Действия")
        )
        self.layout.addWidget(self._actions_title_label)

        self._actions_bar = QuickActionsBar(self.content)

        self.check_button = PushButton(
            tr_catalog("page.dns_check.button.start", language=self._ui_language, default="Начать проверку"),
            icon=FluentIcon.PLAY,
        )
        set_tooltip(
            self.check_button,
            tr_catalog(
                "page.dns_check.action.start.description",
                language=self._ui_language,
                default="Полностью проверить DNS-резолвинг через разные серверы и собрать расширенный отчёт.",
            )
        )
        self.check_button.clicked.connect(self.start_check)
        self._actions_bar.add_button(self.check_button)

        self.quick_check_button = PushButton(
            tr_catalog("page.dns_check.button.quick", language=self._ui_language, default="Быстрая проверка"),
            icon=FluentIcon.SPEED_HIGH,
        )
        set_tooltip(
            self.quick_check_button,
            tr_catalog(
                "page.dns_check.action.quick.description",
                language=self._ui_language,
                default="Сделать быстрый тест только текущего системного DNS без полного сценария.",
            )
        )
        self.quick_check_button.clicked.connect(self.quick_dns_check)
        self._actions_bar.add_button(self.quick_check_button)

        self.save_button = PushButton(
            tr_catalog("page.dns_check.button.save", language=self._ui_language, default="Сохранить результаты"),
            icon=FluentIcon.SAVE,
        )
        set_tooltip(
            self.save_button,
            tr_catalog(
                "page.dns_check.action.save.description",
                language=self._ui_language,
                default="Сохранить текущий отчёт DNS-проверки в текстовый файл.",
            )
        )
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self.save_results)
        self._actions_bar.add_button(self.save_button)

        self.layout.addWidget(self._actions_bar)
        
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
        weight = "600" if bold else "400"
        self.status_label.setText(text)
        self.status_label.setStyleSheet(
            f"color: {color}; padding: 4px 0; font-weight: {weight};"
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
            for icon_label in list(self._info_icon_labels):
                try:
                    icon_name = (icon_label.property("dnsIconName") or "fa5s.search").strip()
                    icon_label.setPixmap(get_cached_qta_pixmap(icon_name, color=tokens.accent_hex, size=16))
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
        if self._check_runtime.is_running() or self.__dict__.get("_check_start_scheduled", False):
            self._check_pending = True
            return
        self._check_pending = False
        self._cleanup_in_progress = False
        
        self.result_text.clear()
        start_plan = dns_check_page_plans.build_start_plan()
        self._apply_interaction_state(
            check_enabled=start_plan.check_enabled,
            quick_enabled=start_plan.quick_enabled,
            save_enabled=start_plan.save_enabled,
            progress_visible=start_plan.progress_visible,
        )
        self._set_status(start_plan.status_text, tone=start_plan.status_tone, bold=False)

        self._check_runtime.start_qobject_worker(
            parent=self,
            worker_factory=lambda request_id: self._dns.create_dns_check_worker(request_id),
            on_finished=self._on_check_worker_finished,
            bind_worker=self._bind_check_worker,
        )

    def _bind_check_worker(self, worker) -> None:
        worker.update_signal.connect(self.append_result)
        worker.finished_signal.connect(self.on_check_finished)
    
    def append_result(self, text):
        """Добавляет текст в результаты с форматированием."""
        if self._cleanup_in_progress:
            return
        tokens = get_theme_tokens()
        semantic = get_semantic_palette()
        plan = dns_check_page_plans.build_result_line_plan(text)
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
        
        safe_text = html.escape(str(text or ""))
        formatted_text = f'<span style="color: {color};">{safe_text}</span>'
        
        # Добавляем в текстовое поле
        cursor = self.result_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(formatted_text + "<br>")
        
        # Автопрокрутка
        self.result_text.verticalScrollBar().setValue(
            self.result_text.verticalScrollBar().maximum()
        )
    
    def on_check_finished(self, request_id: int, results):
        """Обработчик завершения проверки."""
        if not self._check_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        # Обновляем статус
        plan = dns_check_page_plans.build_finish_plan(results)
        self._apply_interaction_state(
            check_enabled=plan.check_enabled,
            quick_enabled=plan.quick_enabled,
            save_enabled=plan.save_enabled,
            progress_visible=plan.progress_visible,
        )
        self._set_status(plan.status_text, tone=plan.status_tone, bold=True)

    def _on_check_worker_finished(self, request_id: int, _thread) -> None:
        if not self._is_current_request_finish(self.__dict__.get("_check_runtime"), request_id):
            return
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if self.__dict__.get("_check_pending", False):
            self._schedule_full_dns_check_start()

    def _schedule_full_dns_check_start(self) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if self.__dict__.get("_check_start_scheduled", False):
            return
        self._check_start_scheduled = True
        QTimer.singleShot(0, self._run_scheduled_full_dns_check_start)

    def _run_scheduled_full_dns_check_start(self) -> None:
        self._check_start_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if not self.__dict__.get("_check_pending", False):
            return
        self._check_pending = False
        self.start_check()
    
    def quick_dns_check(self):
        """Выполняет быструю проверку только системного DNS."""
        if self._quick_runtime.is_running() or self.__dict__.get("_quick_check_start_scheduled", False):
            self._quick_check_pending = True
            return
        self._quick_check_pending = False
        self.result_text.clear()
        self._apply_interaction_state(
            check_enabled=False,
            quick_enabled=False,
            save_enabled=False,
            progress_visible=True,
        )
        self._set_status("⚡ Быстрая проверка DNS...", tone="accent", bold=False)
        self._start_quick_dns_check_worker()

    def create_dns_quick_check_worker(self, request_id: int):
        return self._dns.create_dns_quick_check_worker(request_id, parent=self)

    def _start_quick_dns_check_worker(self) -> None:
        self._quick_runtime.start_qthread_worker(
            worker_factory=self.create_dns_quick_check_worker,
            on_finished=self._on_quick_dns_check_worker_finished,
            bind_worker=self._bind_quick_dns_check_worker,
        )

    def _bind_quick_dns_check_worker(self, worker) -> None:
        worker.completed.connect(self._on_quick_dns_check_finished)

    def _on_quick_dns_check_finished(self, request_id: int, plan) -> None:
        if not self._quick_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        for line in plan.lines:
            self.append_result(line)
        self._apply_interaction_state(
            check_enabled=True,
            quick_enabled=True,
            save_enabled=bool(plan.enable_save),
            progress_visible=False,
        )
        self._set_status("✅ Быстрая проверка завершена", tone="success", bold=True)

    def _on_quick_dns_check_worker_finished(self, worker) -> None:
        if not self._is_current_worker_finish(self.__dict__.get("_quick_runtime"), worker):
            return
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if self.__dict__.get("_quick_check_pending", False):
            self._schedule_quick_dns_check_start()

    def _schedule_quick_dns_check_start(self) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if self.__dict__.get("_quick_check_start_scheduled", False):
            return
        self._quick_check_start_scheduled = True
        QTimer.singleShot(0, self._run_scheduled_quick_dns_check_start)

    def _run_scheduled_quick_dns_check_start(self) -> None:
        self._quick_check_start_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if not self.__dict__.get("_quick_check_pending", False):
            return
        self._quick_check_pending = False
        self.quick_dns_check()
    
    def save_results(self):
        """Сохраняет результаты в файл."""
        from PyQt6.QtWidgets import QFileDialog
        
        # Выбираем путь для сохранения
        default_filename = dns_check_page_plans.build_save_default_filename()
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить результаты DNS проверки",
            default_filename,
            "Text Files (*.txt);;All Files (*.*)"
        )
        
        if file_path:
            self._start_save_results_worker(
                file_path=file_path,
                plain_text=self.result_text.toPlainText(),
            )

    def create_dns_check_save_worker(self, request_id: int, *, file_path: str, plain_text: str):
        return self._dns.create_dns_check_save_worker(
            request_id,
            file_path=file_path,
            plain_text=plain_text,
            parent=self,
        )

    def _start_save_results_worker(self, *, file_path: str, plain_text: str) -> None:
        if self._save_runtime.is_running() or self.__dict__.get("_save_results_start_scheduled", False):
            self._save_results_pending = {
                "file_path": str(file_path or ""),
                "plain_text": str(plain_text or ""),
            }
            return
        self._save_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self.create_dns_check_save_worker(
                request_id,
                file_path=file_path,
                plain_text=plain_text,
            ),
            on_finished=self._on_save_results_worker_finished,
            bind_worker=self._bind_save_results_worker,
        )

    def _bind_save_results_worker(self, worker) -> None:
        worker.saved.connect(self._on_save_results_finished)

    def _on_save_results_finished(self, request_id: int, plan) -> None:
        if not self._save_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        if InfoBar:
            if bool(getattr(plan, "success", False)):
                InfoBar.success(title=plan.title, content=plan.content, parent=self.window())
            else:
                InfoBar.error(title=plan.title, content=plan.content, parent=self.window())

    def _on_save_results_worker_finished(self, worker) -> None:
        if not self._is_current_worker_finish(self.__dict__.get("_save_runtime"), worker):
            return
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        pending = self.__dict__.get("_save_results_pending")
        if pending:
            self._schedule_save_results_worker_start()

    def _is_current_request_finish(self, runtime, request_id: int) -> bool:
        if runtime is None:
            return True
        try:
            return int(request_id) == int(getattr(runtime, "request_id", request_id))
        except (TypeError, ValueError):
            return False

    def _is_current_worker_finish(self, runtime, worker) -> bool:
        if runtime is None:
            return True
        request_id = getattr(worker, "_request_id", None)
        if request_id is not None:
            return self._is_current_request_finish(runtime, request_id)
        current_worker = getattr(runtime, "worker", None)
        if current_worker is not None:
            return worker is current_worker
        return True

    def _schedule_save_results_worker_start(self) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if self.__dict__.get("_save_results_start_scheduled", False):
            return
        self._save_results_start_scheduled = True
        QTimer.singleShot(0, self._run_scheduled_save_results_worker_start)

    def _run_scheduled_save_results_worker_start(self) -> None:
        self._save_results_start_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        pending = self.__dict__.get("_save_results_pending")
        self._save_results_pending = None
        if not pending:
            return
        self._start_save_results_worker(
            file_path=str(pending.get("file_path") or ""),
            plain_text=str(pending.get("plain_text") or ""),
        )
    
    def cleanup(self):
        """Очистка потоков при закрытии"""
        from log.log import log

        try:
            self._cleanup_in_progress = True
            self._check_pending = False
            self._check_start_scheduled = False
            self._save_results_pending = None
            self._save_results_start_scheduled = False
            self._quick_check_pending = False
            self._quick_check_start_scheduled = False
            self._check_runtime.stop(
                blocking=True,
                log_fn=log,
                warning_prefix="DNS check worker",
            )
            self._check_runtime.cancel()
            self._save_runtime.stop(
                blocking=False,
                log_fn=log,
                warning_prefix="DNS check save worker",
            )
            self._save_runtime.cancel()
            self._quick_runtime.stop(
                blocking=False,
                log_fn=log,
                warning_prefix="DNS quick check worker",
            )
            self._quick_runtime.cancel()
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
        if self._actions_title_label is not None:
            self._actions_title_label.setText(
                tr_catalog("page.dns_check.section.actions", language=self._ui_language, default="Действия")
            )

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
        set_tooltip(
            self.check_button,
            tr_catalog(
                "page.dns_check.action.start.description",
                language=self._ui_language,
                default="Полностью проверить DNS-резолвинг через разные серверы и собрать расширенный отчёт.",
            )
        )
        set_tooltip(
            self.quick_check_button,
            tr_catalog(
                "page.dns_check.action.quick.description",
                language=self._ui_language,
                default="Сделать быстрый тест только текущего системного DNS без полного сценария.",
            )
        )
        set_tooltip(
            self.save_button,
            tr_catalog(
                "page.dns_check.action.save.description",
                language=self._ui_language,
                default="Сохранить текущий отчёт DNS-проверки в текстовый файл.",
            )
        )
