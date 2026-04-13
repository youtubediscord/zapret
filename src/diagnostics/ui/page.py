"""Новая вкладка диагностики соединений в стиле Windows 11."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
)
from qfluentwidgets import (
    IndeterminateProgressBar,
    ComboBox,
    StrongBodyLabel,
    BodyLabel,
    CaptionLabel,
    PushButton,
)

from ui.pages.base_page import BasePage
from diagnostics.ui.build import (
    build_connection_controls,
    build_connection_header,
    build_connection_log_viewer,
)
from diagnostics.ui.runtime_helpers import (
    apply_connection_language,
    apply_interaction_state,
    apply_worker_update,
    cleanup_connection_runtime,
    finish_connection_test,
    open_support_with_log,
    refresh_test_combo_items,
    set_connection_status,
    start_connection_test,
    stop_connection_test,
)
from ui.text_catalog import tr as tr_catalog

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
        self._finish_mode = "completed"
        self._cleanup_in_progress = False

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
        apply_interaction_state(
            start_btn=self.start_btn,
            stop_btn=self.stop_btn,
            test_combo=self.test_combo,
            send_log_btn=self.send_log_btn,
            progress_bar=self.progress_bar,
            start_enabled=start_enabled,
            stop_enabled=stop_enabled,
            combo_enabled=combo_enabled,
            send_log_enabled=send_log_enabled,
            progress_visible=progress_visible,
        )

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
        widgets = build_connection_header(
            container_layout=self.container_layout,
            tr_fn=lambda key, default: tr_catalog(key, language=self._ui_language, default=default),
            strong_body_label_cls=StrongBodyLabel,
            body_label_cls=BodyLabel,
        )
        self.hero_title = widgets.hero_title
        self.hero_subtitle = widgets.hero_subtitle
        self.status_badge = widgets.status_badge
        self.progress_badge = widgets.progress_badge

    def _build_controls(self):
        widgets = build_connection_controls(
            container_layout=self.container_layout,
            content_parent=self.content,
            tr_fn=lambda key, default: tr_catalog(key, language=self._ui_language, default=default),
            combo_cls=ComboBox,
            body_label_cls=BodyLabel,
            caption_label_cls=CaptionLabel,
            progress_bar_cls=IndeterminateProgressBar,
            push_button_cls=PushButton,
            on_start=self.start_test,
            on_stop=self.stop_test,
            on_support=self.open_support_with_log,
        )
        self._controls_card = widgets.controls_card
        self.test_select_label = widgets.test_select_label
        self.test_combo = widgets.test_combo
        self._refresh_test_combo_items()
        self.status_label = widgets.status_label
        self.progress_bar = widgets.progress_bar
        self._actions_title_label = widgets.actions_title_label
        self._actions_bar = widgets.actions_bar
        self.start_btn = widgets.start_btn
        self.stop_btn = widgets.stop_btn
        self.send_log_btn = widgets.send_log_btn

    def _build_log_viewer(self):
        widgets = build_connection_log_viewer(
            container_layout=self.container_layout,
            tr_fn=lambda key, default: tr_catalog(key, language=self._ui_language, default=default),
        )
        self.result_text = widgets.result_text

    # ──────────────────────────────────────────────────────────────
    # Логика теста
    # ──────────────────────────────────────────────────────────────
    def start_test(self):
        state = start_connection_test(
            page=self,
            is_testing=self.is_testing,
            ui_language=self._ui_language,
            test_combo=self.test_combo,
            result_text=self.result_text,
            apply_interaction_state_callback=self._apply_interaction_state,
            set_status_callback=self._set_status,
            status_badge=self.status_badge,
            progress_badge=self.progress_badge,
            worker_update_handler=self._on_worker_update,
            worker_finished_handler=self._on_worker_finished,
        )
        if state is None:
            return
        self._cleanup_in_progress = state["cleanup_in_progress"]
        self._finish_mode = state["finish_mode"]
        self.worker = state["worker"]
        self.worker_thread = state["worker_thread"]
        self.is_testing = state["is_testing"]

    def stop_test(self):
        state, timer = stop_connection_test(
            page=self,
            worker=self.worker,
            worker_thread=self.worker_thread,
            stop_check_timer=self.stop_check_timer,
            append_callback=self._append,
            set_status_callback=self._set_status,
            stop_btn=self.stop_btn,
            worker_finished_handler=self._on_worker_finished,
        )
        if state is None:
            return
        self._finish_mode = state["finish_mode"]
        self.stop_check_timer = timer

    def _finalize_stop(self):
        if self._cleanup_in_progress:
            return
        self._on_worker_finished()

    def _on_worker_update(self, message: str):
        if self._cleanup_in_progress:
            return
        apply_worker_update(
            message=message,
            append_callback=self._append,
            result_text=self.result_text,
        )

    def _on_worker_finished(self):
        state = finish_connection_test(
            cleanup_in_progress=self._cleanup_in_progress,
            is_testing=self.is_testing,
            worker=self.worker,
            worker_thread=self.worker_thread,
            stop_check_timer=self.stop_check_timer,
            finish_mode=self._finish_mode,
            apply_interaction_state_callback=self._apply_interaction_state,
            set_status_callback=self._set_status,
            status_badge=self.status_badge,
            progress_badge=self.progress_badge,
            append_callback=self._append,
        )
        if state is None:
            return
        self._finish_mode = state["finish_mode"]
        self.is_testing = state["is_testing"]
        self.worker = state["worker"]
        self.worker_thread = state["worker_thread"]
        self.stop_check_timer = state["stop_check_timer"]

    @staticmethod
    def _release_worker_resources(worker) -> None:
        if worker is None:
            return
        release = getattr(worker, "release_resources", None)
        if not callable(release):
            return
        try:
            release()
        except Exception:
            pass

    # ──────────────────────────────────────────────────────────────
    # DNS и поддержка
    # ──────────────────────────────────────────────────────────────
    def open_support_with_log(self):
        open_support_with_log(
            selection=self.test_combo.currentText(),
            append_callback=self._append,
            set_status_callback=self._set_status,
        )

    # ──────────────────────────────────────────────────────────────
    # Вспомогательное
    # ──────────────────────────────────────────────────────────────
    def _append(self, text: str):
        self.result_text.append(text)

    def _set_status(self, text: str, status: str = "muted"):
        set_connection_status(
            status_label=self.status_label,
            status_badge=self.status_badge,
            text=text,
            status=status,
        )

    def _refresh_test_combo_items(self) -> None:
        refresh_test_combo_items(
            combo=self.test_combo,
            language=self._ui_language,
        )

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)
        apply_connection_language(
            language=self._ui_language,
            controls_card=self._controls_card,
            actions_title_label=self._actions_title_label,
            hero_title=self.hero_title,
            hero_subtitle=self.hero_subtitle,
            test_select_label=self.test_select_label,
            refresh_test_combo_items_callback=self._refresh_test_combo_items,
            start_btn=self.start_btn,
            stop_btn=self.stop_btn,
            send_log_btn=self.send_log_btn,
        )
    
    def cleanup(self):
        """Очистка потоков при закрытии"""
        from log.log import log

        try:
            state = cleanup_connection_runtime(
                cleanup_in_progress=self._cleanup_in_progress,
                finish_mode=self._finish_mode,
                stop_check_timer=self.stop_check_timer,
                worker=self.worker,
                worker_thread=self.worker_thread,
                log_debug=lambda text: log(text, "DEBUG"),
                log_warning=lambda text: log(text, "WARNING"),
            )
            self._cleanup_in_progress = state["cleanup_in_progress"]
            self._finish_mode = state["finish_mode"]
            self.is_testing = state["is_testing"]
            self.worker = state["worker"]
            self.worker_thread = state["worker_thread"]
            self.stop_check_timer = state["stop_check_timer"]
            
        except Exception as e:
            log(f"Ошибка при очистке connection_page: {e}", "DEBUG")
