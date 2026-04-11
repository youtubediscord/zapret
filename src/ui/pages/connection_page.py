"""Новая вкладка диагностики соединений в стиле Windows 11."""

from PyQt6.QtCore import Qt, QThread, QTimer
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
)
import qtawesome as qta

from qfluentwidgets import (
    IndeterminateProgressBar,
    ComboBox,
    StrongBodyLabel,
    BodyLabel,
    CaptionLabel,
    TextEdit,
    PushButton,
)

from .base_page import BasePage, ScrollBlockingTextEdit
from ui.compat_widgets import QuickActionsBar, SettingsCard
from connection_test import ConnectionTestWorker
from ui.connection_page_controller import ConnectionPageController
from ui.smooth_scroll import apply_editor_smooth_scroll_preference
from ui.text_catalog import tr as tr_catalog

class _ScrollBlockingTextBase(TextEdit):
    """TextEdit (Fluent) that stops wheel-scroll from propagating to the parent page."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("noDrag", True)
        apply_editor_smooth_scroll_preference(self)

    def wheelEvent(self, event):
        scrollbar = self.verticalScrollBar()
        delta = event.angleDelta().y()
        if delta > 0 and scrollbar.value() == scrollbar.minimum():
            event.accept()
            return
        if delta < 0 and scrollbar.value() == scrollbar.maximum():
            event.accept()
            return
        super().wheelEvent(event)
        event.accept()


class StatusBadge(CaptionLabel):
    """Status label — delegates all styling to qfluentwidgets CaptionLabel."""

    def __init__(self, text: str = "", status: str = "muted", parent=None):
        super().__init__(parent)
        self.setText(text)

    def set_status(self, text: str, status: str = "muted"):
        self.setText(text)


class ConnectionTestPage(BasePage):
    """Страница теста соединений, заменяющая старое диалоговое окно."""

    def __init__(self, parent=None):
        super().__init__(
            "Диагностика соединения",
            "Автотест Discord и YouTube, проверка DNS подмены и быстрая подготовка обращения в GitHub Discussions",
            parent,
            title_key="page.connection.title",
            subtitle_key="page.connection.subtitle",
        )
        self.is_testing = False
        self.worker = None
        self.worker_thread = None
        self.stop_check_timer = None
        self._actions_title_label = None
        self._actions_bar = None
        self._controls_card = None
        self._pending_start_focus = False

        # Контейнер с ограниченной шириной, чтобы не расползалось за края
        self.container = QWidget(self.content)
        self.container.setObjectName("connectionContainer")
        self.container.setMaximumWidth(1080)
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(14)
        self.container_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        self._build_page_ui()

    def _apply_pending_start_focus_if_ready(self) -> None:
        if not self._pending_start_focus:
            return
        if not self.is_page_ready():
            return
        self.run_when_page_ready(self._apply_pending_start_focus)

    def request_start_focus(self) -> None:
        self._pending_start_focus = True
        self._apply_pending_start_focus_if_ready()

    def _apply_pending_start_focus(self) -> None:
        if not self._pending_start_focus:
            return
        button = getattr(self, "start_btn", None)
        if button is None:
            return
        try:
            button.setFocus()
        except Exception:
            return
        self._pending_start_focus = False

    def _apply_interaction_state(
        self,
        *,
        start_enabled: bool,
        stop_enabled: bool,
        combo_enabled: bool,
        send_log_enabled: bool,
        progress_visible: bool,
    ) -> None:
        self.start_btn.setEnabled(start_enabled)
        self.stop_btn.setEnabled(stop_enabled)
        self.test_combo.setEnabled(combo_enabled)
        self.send_log_btn.setEnabled(send_log_enabled)
        self.progress_bar.setVisible(progress_visible)

        if progress_visible:
            self.progress_bar.start()
        else:
            self.progress_bar.stop()

    def _build_page_ui(self) -> None:
        self._build_header()
        self._build_controls()
        self._build_log_viewer()
        self.add_widget(self.container)
        self.add_spacing(8)

    # ──────────────────────────────────────────────────────────────
    # UI
    # ──────────────────────────────────────────────────────────────
    def _build_header(self):
        hero_card = SettingsCard()

        self.hero_title = StrongBodyLabel(
            tr_catalog("page.connection.hero.title", language=self._ui_language, default="Диагностика сетевых соединений")
        )
        hero_card.add_widget(self.hero_title)

        self.hero_subtitle = BodyLabel(
            tr_catalog(
                "page.connection.hero.subtitle",
                language=self._ui_language,
                default="Проверьте доступность Discord и YouTube, а затем одной кнопкой соберите ZIP с логами и откройте GitHub Discussions.",
            )
        )
        self.hero_subtitle.setWordWrap(True)
        hero_card.add_widget(self.hero_subtitle)

        badges_layout = QHBoxLayout()
        badges_layout.setSpacing(8)
        self.status_badge = StatusBadge(tr_catalog("page.connection.status.ready", language=self._ui_language, default="Готово к тестированию"), "info")
        self.progress_badge = StatusBadge(tr_catalog("page.connection.progress.waiting", language=self._ui_language, default="Ожидает запуска"), "muted")
        badges_layout.addWidget(self.status_badge)
        badges_layout.addWidget(self.progress_badge)
        badges_layout.addStretch()
        hero_card.add_layout(badges_layout)

        self.container_layout.addWidget(hero_card)

    def _build_controls(self):
        card = SettingsCard(tr_catalog("page.connection.card.testing", language=self._ui_language, default="Тестирование"))
        self._controls_card = card

        # Тип теста
        selector_row = QHBoxLayout()
        selector_row.setSpacing(12)
        self.test_select_label = BodyLabel(tr_catalog("page.connection.test.select", language=self._ui_language, default="Выбор теста:"))
        selector_row.addWidget(self.test_select_label)

        self.test_combo = ComboBox()
        self._refresh_test_combo_items()
        selector_row.addWidget(self.test_combo, 1)
        card.add_layout(selector_row)

        # Прогресс + статус
        status_layout = QHBoxLayout()
        status_layout.setSpacing(12)

        self.status_label = CaptionLabel(tr_catalog("page.connection.status.ready", language=self._ui_language, default="Готово к тестированию"))
        status_layout.addWidget(self.status_label, 1)

        self.progress_bar = IndeterminateProgressBar()
        self.progress_bar.setVisible(False)
        status_layout.addWidget(self.progress_bar, 1)

        card.add_layout(status_layout)
        self.container_layout.addWidget(card)

        self._actions_title_label = StrongBodyLabel(
            tr_catalog("page.connection.actions.title", language=self._ui_language, default="Действия")
        )
        self.container_layout.addWidget(self._actions_title_label)

        self._actions_bar = QuickActionsBar(self.content)

        self.start_btn = PushButton()
        self.start_btn.setText(tr_catalog("page.connection.button.start", language=self._ui_language, default="Запустить тест"))
        self.start_btn.setIcon(qta.icon("fa5s.play", color="#4CAF50"))
        self.start_btn.setToolTip(
            tr_catalog(
                "page.connection.action.start.description",
                language=self._ui_language,
                default="Запустить выбранный сценарий диагностики для Discord и YouTube.",
            )
        )
        self.start_btn.clicked.connect(self.start_test)
        self._actions_bar.add_button(self.start_btn)

        self.stop_btn = PushButton()
        self.stop_btn.setText(tr_catalog("page.connection.button.stop", language=self._ui_language, default="Стоп"))
        self.stop_btn.setIcon(qta.icon("fa5s.stop", color="#ff9800"))
        self.stop_btn.setToolTip(
            tr_catalog(
                "page.connection.action.stop.description",
                language=self._ui_language,
                default="Остановить текущий тест, если он уже запущен.",
            )
        )
        self.stop_btn.clicked.connect(self.stop_test)
        self.stop_btn.setEnabled(False)
        self._actions_bar.add_button(self.stop_btn)

        self.send_log_btn = PushButton()
        self.send_log_btn.setText(tr_catalog("page.connection.button.send_log", language=self._ui_language, default="Подготовить обращение"))
        self.send_log_btn.setIcon(qta.icon("fa5b.github", color="#60cdff"))
        self.send_log_btn.setToolTip(
            tr_catalog(
                "page.connection.action.support.description",
                language=self._ui_language,
                default="Собрать архив логов и открыть готовое обращение в GitHub Discussions.",
            )
        )
        self.send_log_btn.clicked.connect(self.open_support_with_log)
        self.send_log_btn.setEnabled(False)
        self._actions_bar.add_button(self.send_log_btn)

        self.container_layout.addWidget(self._actions_bar)

    def _build_log_viewer(self):
        log_card = SettingsCard(tr_catalog("page.connection.card.result", language=self._ui_language, default="Результат тестирования"))
        self.result_text = _ScrollBlockingTextBase()
        self.result_text.setReadOnly(True)
        log_card.add_widget(self.result_text)
        self.container_layout.addWidget(log_card)

    # ──────────────────────────────────────────────────────────────
    # Логика теста
    # ──────────────────────────────────────────────────────────────
    def start_test(self):
        if self.is_testing:
            self._append("ℹ️ Тест уже выполняется. Дождитесь завершения.")
            return

        selection = self.test_combo.currentText()
        plan = ConnectionPageController.build_start_plan(selection=selection)

        self.result_text.clear()
        for line in plan.start_lines:
            self._append(line)

        self._apply_interaction_state(
            start_enabled=plan.start_enabled,
            stop_enabled=plan.stop_enabled,
            combo_enabled=plan.combo_enabled,
            send_log_enabled=plan.send_log_enabled,
            progress_visible=plan.progress_visible,
        )
        self._set_status(plan.status_text, plan.status_tone)
        self.status_badge.set_status(plan.status_badge_text, plan.status_tone)
        self.progress_badge.set_status(plan.progress_badge_text, plan.status_tone)

        self.worker_thread = QThread(self)
        self.worker = ConnectionTestWorker(plan.test_type)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.update_signal.connect(self._on_worker_update)
        self.worker.finished_signal.connect(self._on_worker_finished)
        self.worker.finished_signal.connect(self.worker_thread.quit)
        self.worker.finished_signal.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)

        self.is_testing = True
        self.worker_thread.start()

    def stop_test(self):
        if not self.worker or not self.worker_thread:
            return

        plan = ConnectionPageController.build_stop_plan()
        for line in plan.append_lines:
            self._append(line)
        self._set_status(plan.status_text, plan.status_tone)
        self.worker.stop_gracefully()

        self.stop_check_timer = QTimer(self)
        self.stop_check_attempts = 0

        def check_thread():
            if not self.stop_check_timer:
                return
            self.stop_check_attempts += 1
            poll_plan = ConnectionPageController.build_stop_poll_plan(
                attempt_count=self.stop_check_attempts,
                thread_running=bool(self.worker_thread and self.worker_thread.isRunning()),
                max_attempts=plan.max_attempts,
                finalize_delay_ms=plan.finalize_delay_ms,
            )
            if poll_plan.action == "finish":
                if self.stop_check_timer:
                    self.stop_check_timer.stop()
                if poll_plan.append_line:
                    self._append(poll_plan.append_line)
                self._on_worker_finished()
            elif poll_plan.action == "force_terminate":
                if self.stop_check_timer:
                    self.stop_check_timer.stop()
                if poll_plan.append_line:
                    self._append(poll_plan.append_line)
                if self.worker_thread:
                    self.worker_thread.terminate()
                    QTimer.singleShot(poll_plan.finalize_delay_ms, self._finalize_stop)

        self.stop_check_timer.timeout.connect(check_thread)
        self.stop_check_timer.start(plan.poll_interval_ms)

    def _finalize_stop(self):
        self._on_worker_finished()

    def _on_worker_update(self, message: str):
        for line in ConnectionPageController.build_worker_update_lines(message):
            self._append(line)

        scrollbar = self.result_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _on_worker_finished(self):
        self.is_testing = False
        self.worker = None
        self.worker_thread = None
        self.stop_check_timer = None

        plan = ConnectionPageController.build_finish_plan()
        self._apply_interaction_state(
            start_enabled=plan.start_enabled,
            stop_enabled=plan.stop_enabled,
            combo_enabled=plan.combo_enabled,
            send_log_enabled=plan.send_log_enabled,
            progress_visible=plan.progress_visible,
        )
        self.status_badge.set_status(plan.status_badge_text, plan.status_tone)
        self.progress_badge.set_status(plan.progress_badge_text, "muted")
        self._set_status(plan.status_text, plan.status_tone)
        for line in plan.finish_lines:
            self._append(line)

    # ──────────────────────────────────────────────────────────────
    # DNS и поддержка
    # ──────────────────────────────────────────────────────────────
    def open_support_with_log(self):
        plan = ConnectionPageController.prepare_support_request_for_connection(
            selection=self.test_combo.currentText(),
        )
        for line in plan.log_lines:
            self._append(line)
        self._set_status(plan.status_text, plan.status_tone)

    # ──────────────────────────────────────────────────────────────
    # Вспомогательное
    # ──────────────────────────────────────────────────────────────
    def _append(self, text: str):
        self.result_text.append(text)

    def _set_status(self, text: str, status: str = "muted"):
        self.status_label.setText(text)
        self.status_badge.set_status(text, status)

    def _refresh_test_combo_items(self) -> None:
        current = self.test_combo.currentIndex() if hasattr(self, "test_combo") else 0
        items = [
            tr_catalog("page.connection.test.all", language=self._ui_language, default="🌐 Все тесты (Discord + YouTube)"),
            tr_catalog("page.connection.test.discord_only", language=self._ui_language, default="🎮 Только Discord"),
            tr_catalog("page.connection.test.youtube_only", language=self._ui_language, default="🎬 Только YouTube"),
        ]
        self.test_combo.clear()
        self.test_combo.addItems(items)
        self.test_combo.setCurrentIndex(max(0, min(current, len(items) - 1)))

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)

        try:
            if self._controls_card is not None:
                self._controls_card.set_title(
                    tr_catalog("page.connection.card.testing", language=self._ui_language, default="Тестирование")
                )
        except Exception:
            pass
        if self._actions_title_label is not None:
            self._actions_title_label.setText(
                tr_catalog("page.connection.actions.title", language=self._ui_language, default="Действия")
            )

        self.hero_title.setText(tr_catalog("page.connection.hero.title", language=self._ui_language, default="Диагностика сетевых соединений"))
        self.hero_subtitle.setText(
            tr_catalog(
                "page.connection.hero.subtitle",
                language=self._ui_language,
                default="Проверьте доступность Discord и YouTube, а затем одной кнопкой соберите ZIP с логами и откройте GitHub Discussions.",
            )
        )
        self.test_select_label.setText(tr_catalog("page.connection.test.select", language=self._ui_language, default="Выбор теста:"))
        self._refresh_test_combo_items()

        self.start_btn.setText(tr_catalog("page.connection.button.start", language=self._ui_language, default="Запустить тест"))
        self.stop_btn.setText(tr_catalog("page.connection.button.stop", language=self._ui_language, default="Стоп"))
        self.send_log_btn.setText(tr_catalog("page.connection.button.send_log", language=self._ui_language, default="Подготовить обращение"))
        if self._actions_title_label is not None:
            self._actions_title_label.setText(
                tr_catalog("page.connection.actions.title", language=self._ui_language, default="Действия")
            )
        self.start_btn.setToolTip(
            tr_catalog(
                "page.connection.action.start.description",
                language=self._ui_language,
                default="Запустить выбранный сценарий диагностики для Discord и YouTube.",
            )
        )
        self.stop_btn.setToolTip(
            tr_catalog(
                "page.connection.action.stop.description",
                language=self._ui_language,
                default="Остановить текущий тест, если он уже запущен.",
            )
        )
        self.send_log_btn.setToolTip(
            tr_catalog(
                "page.connection.action.support.description",
                language=self._ui_language,
                default="Собрать архив логов и открыть готовое обращение в GitHub Discussions.",
            )
        )
    
    def cleanup(self):
        """Очистка потоков при закрытии"""
        from log import log
        try:
            cleanup_plan = ConnectionPageController.build_cleanup_plan(
                has_worker=self.worker is not None,
                thread_running=bool(self.worker_thread and self.worker_thread.isRunning()),
            )
            if cleanup_plan.should_quit_thread and self.worker_thread and self.worker_thread.isRunning():
                log("Останавливаем connection test worker...", "DEBUG")
                if cleanup_plan.should_request_stop and self.worker:
                    self.worker.stop_gracefully()
                self.worker_thread.quit()
                if not self.worker_thread.wait(cleanup_plan.wait_timeout_ms):
                    log("⚠ Connection test worker не завершился, принудительно завершаем", "WARNING")
                    if cleanup_plan.should_terminate:
                        self.worker_thread.terminate()
                        self.worker_thread.wait(cleanup_plan.terminate_wait_ms)
            
        except Exception as e:
            log(f"Ошибка при очистке connection_page: {e}", "DEBUG")
