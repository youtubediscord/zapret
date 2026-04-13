"""Dialogs для страницы пользовательских пресетов Zapret 2."""

from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QPushButton, QHBoxLayout, QLineEdit, QListView

from ui.compat_widgets import style_semantic_caption_label
from ui.text_catalog import tr as tr_catalog

try:
    from qfluentwidgets import (
        BodyLabel,
        CaptionLabel,
        SubtitleLabel,
        MessageBoxBase,
        LineEdit,
    )
except ImportError:
    BodyLabel = QLabel
    CaptionLabel = QLabel
    SubtitleLabel = QLabel
    MessageBoxBase = object
    LineEdit = QLineEdit


def tr_presets_dialog(key: str, language: str, default: str, **kwargs) -> str:
    text = tr_catalog(key, language=language, default=default)
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text


class CreatePresetDialog(MessageBoxBase):
    """Диалог создания нового пресета."""

    def __init__(self, existing_names: list, parent=None, language: str = "ru"):
        if parent and not parent.isWindow():
            parent = parent.window()
        super().__init__(parent)
        self._ui_language = language

        def _tr(key: str, default: str, **kwargs) -> str:
            return tr_presets_dialog(key, self._ui_language, default, **kwargs)

        self._tr = _tr
        self._existing_names = list(existing_names)
        self._source = "current"

        self.titleLabel = SubtitleLabel(
            self._tr("page.z2_user_presets.dialog.create.title", "Новый пресет"),
            self.widget,
        )
        self.subtitleLabel = BodyLabel(
            self._tr(
                "page.z2_user_presets.dialog.create.subtitle",
                "Сохраните текущие настройки как отдельный пресет, чтобы быстро переключаться между конфигурациями.",
            ),
            self.widget,
        )
        self.subtitleLabel.setWordWrap(True)

        name_label = BodyLabel(
            self._tr("page.z2_user_presets.dialog.create.name", "Название"),
            self.widget,
        )
        self.nameEdit = LineEdit(self.widget)
        self.nameEdit.setPlaceholderText(
            self._tr(
                "page.z2_user_presets.dialog.create.placeholder",
                "Например: Игры / YouTube / Дом",
            )
        )
        self.nameEdit.setClearButtonEnabled(True)

        source_row = QHBoxLayout()
        source_label = BodyLabel(
            self._tr("page.z2_user_presets.dialog.create.source", "Создать на основе"),
            self.widget,
        )
        source_row.addWidget(source_label)
        source_row.addStretch()
        try:
            from qfluentwidgets import SegmentedWidget

            self._source_seg = SegmentedWidget(self.widget)
            self._source_seg.addItem(
                "current",
                self._tr("page.z2_user_presets.dialog.create.source.current", "Текущего активного"),
            )
            self._source_seg.addItem(
                "empty",
                self._tr("page.z2_user_presets.dialog.create.source.empty", "Пустого"),
            )
            self._source_seg.setCurrentItem("current")
            self._source_seg.currentItemChanged.connect(lambda k: setattr(self, "_source", k))
            source_row.addWidget(self._source_seg)
        except Exception:
            pass

        self.warningLabel = CaptionLabel("", self.widget)
        style_semantic_caption_label(self.warningLabel, tone="error")
        self.warningLabel.hide()

        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.subtitleLabel)
        self.viewLayout.addWidget(name_label)
        self.viewLayout.addWidget(self.nameEdit)
        self.viewLayout.addLayout(source_row)
        self.viewLayout.addWidget(self.warningLabel)

        self.yesButton.setText(self._tr("page.z2_user_presets.dialog.create.button.create", "Создать"))
        self.cancelButton.setText(self._tr("page.z2_user_presets.dialog.button.cancel", "Отмена"))
        self.widget.setMinimumWidth(420)

    def validate(self) -> bool:
        name = self.nameEdit.text().strip()
        if not name:
            self.warningLabel.setText(
                self._tr("page.z2_user_presets.dialog.validation.enter_name", "Введите название.")
            )
            self.warningLabel.show()
            return False
        self.warningLabel.hide()
        return True


class RenamePresetDialog(MessageBoxBase):
    """Диалог переименования пресета."""

    def __init__(self, current_name: str, existing_names: list, parent=None, language: str = "ru"):
        if parent and not parent.isWindow():
            parent = parent.window()
        super().__init__(parent)
        self._ui_language = language

        def _tr(key: str, default: str, **kwargs) -> str:
            return tr_presets_dialog(key, self._ui_language, default, **kwargs)

        self._tr = _tr
        self._current_name = str(current_name or "")
        self._existing_names = [n for n in existing_names if n != self._current_name]

        self.titleLabel = SubtitleLabel(
            self._tr("page.z2_user_presets.dialog.rename.title", "Переименовать"),
            self.widget,
        )
        self.subtitleLabel = BodyLabel(
            self._tr(
                "page.z2_user_presets.dialog.rename.subtitle",
                "Имя пресета отображается в списке и используется для переключения.",
            ),
            self.widget,
        )
        self.subtitleLabel.setWordWrap(True)

        from_label = CaptionLabel(
            self._tr(
                "page.z2_user_presets.dialog.rename.current_name",
                "Текущее имя: {name}",
                name=self._current_name,
            ),
            self.widget,
        )
        name_label = BodyLabel(
            self._tr("page.z2_user_presets.dialog.rename.new_name", "Новое имя"),
            self.widget,
        )
        self.nameEdit = LineEdit(self.widget)
        self.nameEdit.setText(self._current_name)
        self.nameEdit.setPlaceholderText(
            self._tr("page.z2_user_presets.dialog.rename.placeholder", "Новое имя...")
        )
        self.nameEdit.selectAll()
        self.nameEdit.setClearButtonEnabled(True)

        self.warningLabel = CaptionLabel("", self.widget)
        style_semantic_caption_label(self.warningLabel, tone="error")
        self.warningLabel.hide()

        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.subtitleLabel)
        self.viewLayout.addWidget(from_label)
        self.viewLayout.addWidget(name_label)
        self.viewLayout.addWidget(self.nameEdit)
        self.viewLayout.addWidget(self.warningLabel)

        self.yesButton.setText(self._tr("page.z2_user_presets.dialog.rename.button", "Переименовать"))
        self.cancelButton.setText(self._tr("page.z2_user_presets.dialog.button.cancel", "Отмена"))
        self.widget.setMinimumWidth(420)

    def validate(self) -> bool:
        name = self.nameEdit.text().strip()
        if not name:
            self.warningLabel.setText(
                self._tr("page.z2_user_presets.dialog.validation.enter_name", "Введите название.")
            )
            self.warningLabel.show()
            return False
        if name == self._current_name:
            self.warningLabel.hide()
            return True
        self.warningLabel.hide()
        return True


class ResetAllPresetsDialog(MessageBoxBase):
    """Диалог подтверждения перезаписи пресетов из шаблонов."""

    def __init__(self, parent=None, language: str = "ru"):
        if parent and not parent.isWindow():
            parent = parent.window()
        super().__init__(parent)
        self._ui_language = language
        self.titleLabel = SubtitleLabel(
            tr_presets_dialog(
                "page.z2_user_presets.dialog.reset_all.title",
                self._ui_language,
                "Вернуть заводские пресеты",
            ),
            self.widget,
        )
        self.bodyLabel = BodyLabel(
            tr_presets_dialog(
                "page.z2_user_presets.dialog.reset_all.body",
                self._ui_language,
                "Стандартные пресеты будут восстановлены как после установки.\n"
                "Ваши изменения в стандартных пресетах будут потеряны.\n"
                "Пользовательские пресеты с другими именами останутся.\n"
                "Текущий активный пресет будет применен заново автоматически.",
            ),
            self.widget,
        )
        self.bodyLabel.setWordWrap(True)
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.bodyLabel)
        self.yesButton.setText(
            tr_presets_dialog(
                "page.z2_user_presets.dialog.reset_all.button",
                self._ui_language,
                "Вернуть заводские",
            )
        )
        self.cancelButton.setText(
            tr_presets_dialog("page.z2_user_presets.dialog.button.cancel", self._ui_language, "Отмена")
        )
        self.widget.setMinimumWidth(380)
