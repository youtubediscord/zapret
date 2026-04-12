"""Args-dialog для страницы деталей стратегии Zapret 1."""

from __future__ import annotations

from PyQt6.QtGui import QFont

from ui.smooth_scroll import apply_editor_smooth_scroll_preference
from ui.text_catalog import tr as tr_catalog

try:
    from qfluentwidgets import CaptionLabel, MessageBoxBase, SubtitleLabel, TextEdit

    HAS_FLUENT = True
except ImportError:
    from PyQt6.QtWidgets import QLabel, QDialog as MessageBoxBase, QTextEdit as TextEdit

    CaptionLabel = QLabel
    SubtitleLabel = QLabel
    HAS_FLUENT = False


class ArgsEditorDialogV1(MessageBoxBase):  # type: ignore[misc, valid-type]
    """Диалог ручного редактирования аргументов стратегии Zapret 1."""

    def __init__(self, initial_text: str = "", parent=None, language: str = "ru"):
        super().__init__(parent)
        self._ui_language = language

        def _tr(key: str, default: str, **kwargs) -> str:
            text = tr_catalog(key, language=self._ui_language, default=default)
            if kwargs:
                try:
                    return text.format(**kwargs)
                except Exception:
                    return text
            return text

        self._tr = _tr

        if not HAS_FLUENT:
            return

        self._title_lbl = SubtitleLabel(
            self._tr("page.z1_strategy_detail.args_dialog.title", "Аргументы стратегии")
        )
        self.viewLayout.addWidget(self._title_lbl)

        hint = CaptionLabel(
            self._tr(
                "page.z1_strategy_detail.args_dialog.hint",
                "Один аргумент на строку. Изменяет только выбранный target.",
            )
        )
        self.viewLayout.addWidget(hint)

        self._text_edit = TextEdit()
        apply_editor_smooth_scroll_preference(self._text_edit)
        self._text_edit.setPlaceholderText(
            self._tr(
                "page.z1_strategy_detail.args_dialog.placeholder",
                "Например:\n--dpi-desync=multisplit\n--dpi-desync-split-pos=1",
            )
        )
        self._text_edit.setMinimumWidth(460)
        self._text_edit.setMinimumHeight(150)
        self._text_edit.setMaximumHeight(260)
        self._text_edit.setFont(QFont("Consolas", 10))
        self._text_edit.setPlainText(initial_text)
        self.viewLayout.addWidget(self._text_edit)

        self.yesButton.setText(self._tr("page.z1_strategy_detail.args_dialog.button.save", "Сохранить"))
        self.cancelButton.setText(self._tr("page.z1_strategy_detail.args_dialog.button.cancel", "Отмена"))

    def validate(self) -> bool:
        return True

    def get_text(self) -> str:
        if hasattr(self, "_text_edit"):
            return self._text_edit.toPlainText()
        return ""
