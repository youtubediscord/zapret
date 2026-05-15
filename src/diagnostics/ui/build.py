"""Build-helper основных секций ConnectionTestPage."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtWidgets import QWidget, QHBoxLayout

from ui.fluent_widgets import QuickActionsBar, SettingsCard
from diagnostics.ui.components import ConnectionStatusBadge, ScrollBlockingConnectionTextEdit
from ui.theme import get_themed_qta_icon


@dataclass(slots=True)
class ConnectionHeaderWidgets:
    hero_title: object
    hero_subtitle: object
    status_badge: object
    progress_badge: object


@dataclass(slots=True)
class ConnectionControlsWidgets:
    controls_card: object
    test_select_label: object
    test_combo: object
    status_label: object
    progress_bar: object
    actions_title_label: object
    actions_bar: object
    start_btn: object
    stop_btn: object
    send_log_btn: object


@dataclass(slots=True)
class ConnectionLogWidgets:
    result_text: object


def build_connection_header(*, container_layout, tr_fn, strong_body_label_cls, body_label_cls):
    hero_card = SettingsCard()

    hero_title = strong_body_label_cls(
        tr_fn("page.connection.hero.title", "Диагностика сетевых соединений")
    )
    hero_card.add_widget(hero_title)

    hero_subtitle = body_label_cls(
        tr_fn(
            "page.connection.hero.subtitle",
            "Проверьте доступность Discord и YouTube, а затем одной кнопкой соберите ZIP с логами и откройте GitHub Discussions.",
        )
    )
    hero_subtitle.setWordWrap(True)
    hero_card.add_widget(hero_subtitle)

    badges_layout = QHBoxLayout()
    badges_layout.setSpacing(8)
    status_badge = ConnectionStatusBadge(
        tr_fn("page.connection.status.ready", "Готово к тестированию"),
        "info",
    )
    progress_badge = ConnectionStatusBadge(
        tr_fn("page.connection.progress.waiting", "Ожидает запуска"),
        "muted",
    )
    badges_layout.addWidget(status_badge)
    badges_layout.addWidget(progress_badge)
    badges_layout.addStretch()
    hero_card.add_layout(badges_layout)

    container_layout.addWidget(hero_card)

    return ConnectionHeaderWidgets(
        hero_title=hero_title,
        hero_subtitle=hero_subtitle,
        status_badge=status_badge,
        progress_badge=progress_badge,
    )


def build_connection_controls(
    *,
    container_layout,
    content_parent,
    tr_fn,
    combo_cls,
    body_label_cls,
    caption_label_cls,
    progress_bar_cls,
    push_button_cls,
    on_start,
    on_stop,
    on_support,
) -> ConnectionControlsWidgets:
    controls_card = SettingsCard(tr_fn("page.connection.card.testing", "Тестирование"))

    selector_row = QHBoxLayout()
    selector_row.setSpacing(12)
    test_select_label = body_label_cls(tr_fn("page.connection.test.select", "Выбор теста:"))
    selector_row.addWidget(test_select_label)

    test_combo = combo_cls()
    selector_row.addWidget(test_combo, 1)
    controls_card.add_layout(selector_row)

    status_layout = QHBoxLayout()
    status_layout.setSpacing(12)

    status_label = caption_label_cls(tr_fn("page.connection.status.ready", "Готово к тестированию"))
    status_layout.addWidget(status_label, 1)

    progress_bar = progress_bar_cls()
    progress_bar.setVisible(False)
    status_layout.addWidget(progress_bar, 1)
    controls_card.add_layout(status_layout)
    container_layout.addWidget(controls_card)

    actions_title_label = body_label_cls(tr_fn("page.connection.actions.title", "Действия"))
    container_layout.addWidget(actions_title_label)

    actions_bar = QuickActionsBar(content_parent)

    start_btn = push_button_cls()
    start_btn.setText(tr_fn("page.connection.button.start", "Запустить тест"))
    start_btn.setIcon(get_themed_qta_icon("fa5s.play", color="#4CAF50"))
    start_btn.setToolTip(
        tr_fn(
            "page.connection.action.start.description",
            "Запустить выбранный сценарий диагностики для Discord и YouTube.",
        )
    )
    start_btn.clicked.connect(on_start)
    actions_bar.add_button(start_btn)

    stop_btn = push_button_cls()
    stop_btn.setText(tr_fn("page.connection.button.stop", "Стоп"))
    stop_btn.setIcon(get_themed_qta_icon("fa5s.stop", color="#ff9800"))
    stop_btn.setToolTip(
        tr_fn(
            "page.connection.action.stop.description",
            "Остановить текущий тест, если он уже запущен.",
        )
    )
    stop_btn.clicked.connect(on_stop)
    stop_btn.setEnabled(False)
    actions_bar.add_button(stop_btn)

    send_log_btn = push_button_cls()
    send_log_btn.setText(tr_fn("page.connection.button.send_log", "Подготовить обращение"))
    send_log_btn.setIcon(get_themed_qta_icon("fa5b.github", color="#60cdff"))
    send_log_btn.setToolTip(
        tr_fn(
            "page.connection.action.support.description",
            "Собрать архив логов и открыть готовое обращение в GitHub Discussions.",
        )
    )
    send_log_btn.clicked.connect(on_support)
    send_log_btn.setEnabled(False)
    actions_bar.add_button(send_log_btn)

    container_layout.addWidget(actions_bar)

    return ConnectionControlsWidgets(
        controls_card=controls_card,
        test_select_label=test_select_label,
        test_combo=test_combo,
        status_label=status_label,
        progress_bar=progress_bar,
        actions_title_label=actions_title_label,
        actions_bar=actions_bar,
        start_btn=start_btn,
        stop_btn=stop_btn,
        send_log_btn=send_log_btn,
    )


def build_connection_log_viewer(*, container_layout, tr_fn):
    log_card = SettingsCard(tr_fn("page.connection.card.result", "Результат тестирования"))
    result_text = ScrollBlockingConnectionTextEdit()
    result_text.setReadOnly(True)
    log_card.add_widget(result_text)
    container_layout.addWidget(log_card)
    return ConnectionLogWidgets(result_text=result_text)
