from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget
from log import log

from ui.smooth_scroll import apply_editor_smooth_scroll_preference
from ui.text_catalog import tr as tr_catalog

try:
    from qfluentwidgets import CaptionLabel, MessageBoxBase, SubtitleLabel, TextEdit

    HAS_FLUENT = True
except ImportError:
    from PyQt6.QtWidgets import QDialog as MessageBoxBase, QTextEdit as TextEdit

    CaptionLabel = QLabel
    SubtitleLabel = QLabel
    HAS_FLUENT = False


def _tr_text(language: str, key: str, default: str, **kwargs) -> str:
    text = tr_catalog(key, language=language, default=default)
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text


class ArgsEditorDialog(MessageBoxBase):
    """Общий диалог редактирования аргументов для direct strategy detail страниц."""

    def __init__(self, initial_text: str = "", parent=None, language: str = "ru"):
        super().__init__(parent)
        self._ui_language = language
        if HAS_FLUENT:
            self._title_lbl = SubtitleLabel(
                _tr_text(self._ui_language, "page.z2_strategy_detail.args_dialog.title", "Аргументы стратегии")
            )
        else:
            self._title_lbl = QLabel(
                _tr_text(self._ui_language, "page.z2_strategy_detail.args_dialog.title", "Аргументы стратегии")
            )
        self.viewLayout.addWidget(self._title_lbl)

        if HAS_FLUENT:
            hint = CaptionLabel(
                _tr_text(
                    self._ui_language,
                    "page.z2_strategy_detail.args_dialog.hint",
                    "Один аргумент на строку. Изменяет только выбранный target.",
                )
            )
        else:
            hint = QLabel(
                _tr_text(self._ui_language, "page.z2_strategy_detail.args_dialog.hint.short", "Один аргумент на строку.")
            )
        self.viewLayout.addWidget(hint)

        self._text_edit = TextEdit()
        apply_editor_smooth_scroll_preference(self._text_edit)
        self._text_edit.setPlaceholderText(
            _tr_text(
                self._ui_language,
                "page.z2_strategy_detail.args_dialog.placeholder",
                "Например:\n--dpi-desync=multisplit\n--dpi-desync-split-pos=1",
            )
        )
        self._text_edit.setMinimumWidth(420)
        self._text_edit.setMinimumHeight(120)
        self._text_edit.setMaximumHeight(220)
        if HAS_FLUENT:
            self._text_edit.setFont(QFont("Consolas", 10))
        self._text_edit.setText(initial_text)
        self.viewLayout.addWidget(self._text_edit)

        self.yesButton.setText(
            _tr_text(self._ui_language, "page.z2_strategy_detail.args_dialog.button.save", "Сохранить")
        )
        self.cancelButton.setText(
            _tr_text(self._ui_language, "page.z2_strategy_detail.args_dialog.button.cancel", "Отмена")
        )

    def validate(self) -> bool:
        return True

    def get_text(self) -> str:
        return self._text_edit.toPlainText()


def run_args_editor_dialog(
    *,
    initial_text: str = "",
    parent=None,
    language: str = "ru",
    dialog_cls=ArgsEditorDialog,
) -> str | None:
    """Открывает диалог редактирования args и возвращает итоговый текст или None."""
    dialog = dialog_cls(initial_text=initial_text, parent=parent, language=language)
    accepted = False
    try:
        accepted = bool(dialog.exec())
    except Exception:
        accepted = False
    if not accepted:
        return None
    try:
        return dialog.get_text()
    except Exception:
        return None


@dataclass(slots=True)
class DetailSubtitleWidgets:
    container_widget: QWidget
    spinner: object
    success_icon: object
    subtitle_label: object
    subtitle_strategy_label: object


def build_strategies_tree_widget(
    *,
    parent,
    tree_cls,
    on_row_clicked,
    on_favorite_toggled,
    on_working_mark_requested,
    on_preview_requested,
    on_preview_pinned_requested,
    on_preview_hide_requested,
):
    tree = tree_cls(parent)
    tree.setProperty("noDrag", True)
    tree.strategy_clicked.connect(on_row_clicked)
    tree.favorite_toggled.connect(on_favorite_toggled)
    tree.working_mark_requested.connect(on_working_mark_requested)
    tree.preview_requested.connect(on_preview_requested)
    tree.preview_pinned_requested.connect(on_preview_pinned_requested)
    tree.preview_hide_requested.connect(on_preview_hide_requested)
    return tree


def build_detail_subtitle_widgets(
    *,
    parent,
    body_label_cls,
    spinner_cls,
    pixmap_label_cls,
    subtitle_strategy_label_cls,
    detail_text_color: str,
) -> DetailSubtitleWidgets:
    container_widget = QWidget(parent)
    subtitle_row = QHBoxLayout(container_widget)
    subtitle_row.setContentsMargins(0, 0, 0, 0)
    subtitle_row.setSpacing(6)

    spinner = spinner_cls(start=False)
    spinner.setFixedSize(16, 16)
    try:
        spinner.setStrokeWidth(2)
    except Exception:
        pass
    spinner.hide()
    subtitle_row.addWidget(spinner)

    success_icon = pixmap_label_cls()
    success_icon.setFixedSize(16, 16)
    success_icon.hide()
    subtitle_row.addWidget(success_icon)

    subtitle_label = body_label_cls("")
    subtitle_row.addWidget(subtitle_label)

    subtitle_strategy_label = subtitle_strategy_label_cls("")
    subtitle_strategy_label.setFont(QFont("Segoe UI", 11))
    try:
        subtitle_strategy_label.setProperty("tone", "muted")
    except Exception:
        pass
    subtitle_strategy_label.setStyleSheet(
        f"background: transparent; padding-left: 10px; color: {detail_text_color};"
    )
    subtitle_strategy_label.hide()
    subtitle_row.addWidget(subtitle_strategy_label, 1)

    return DetailSubtitleWidgets(
        container_widget=container_widget,
        spinner=spinner,
        success_icon=success_icon,
        subtitle_label=subtitle_label,
        subtitle_strategy_label=subtitle_strategy_label,
    )


def coerce_global_pos_to_qpoint(global_pos):
    try:
        return global_pos.toPoint()
    except Exception:
        return global_pos


def ensure_preview_dialog(
    existing_dialog,
    *,
    parent_win,
    on_closed,
    dialog_cls,
):
    dialog = existing_dialog
    if dialog is not None:
        try:
            dialog.isVisible()
            return dialog
        except RuntimeError:
            dialog = None
        except Exception:
            return dialog

    try:
        dialog = dialog_cls(parent_win)
        dialog.closed.connect(on_closed)
        return dialog
    except Exception:
        return None


def show_strategy_preview_dialog(
    dialog,
    *,
    strategy_data: dict,
    strategy_id: str,
    target_key: str,
    global_pos,
    rating_getter,
    rating_toggler,
    log_fn=log,
) -> None:
    try:
        dialog.set_strategy_data(
            strategy_data,
            strategy_id=strategy_id,
            target_key=target_key,
            rating_getter=rating_getter,
            rating_toggler=rating_toggler,
        )
        dialog.show_animated(coerce_global_pos_to_qpoint(global_pos))
    except Exception as exc:
        log_fn(f"Preview dialog failed: {exc}", "DEBUG")

