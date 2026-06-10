"""Общие dialog-окна страницы пользовательских preset-ов."""

from __future__ import annotations

from PyQt6.QtWidgets import QHBoxLayout

from ui.accessibility import set_control_accessibility, set_state_text
from ui.fluent_widgets import style_semantic_caption_label
from app.ui_texts import tr as tr_catalog
from qfluentwidgets import BodyLabel, CaptionLabel, LineEdit, MessageBoxBase, SubtitleLabel


def tr_presets_dialog(key: str, language: str, default: str, **kwargs) -> str:
    text = tr_catalog(key, language=language, default=default)
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text


class PresetDialogTextMixin:
    tr_prefix = "page.winws2_user_presets"

    def _dialog_key(self, suffix: str) -> str:
        return f"{self.tr_prefix}.{suffix}"


class CreatePresetDialog(PresetDialogTextMixin, MessageBoxBase):
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
            self._tr(self._dialog_key("dialog.create.title"), "Новый пресет"),
            self.widget,
        )
        self.subtitleLabel = BodyLabel(
            self._tr(
                self._dialog_key("dialog.create.subtitle"),
                "Сохраните текущие настройки как отдельный пресет, чтобы быстро переключаться между разными настройками.",
            ),
            self.widget,
        )
        self.subtitleLabel.setWordWrap(True)

        name_label = BodyLabel(
            self._tr(self._dialog_key("dialog.create.name"), "Название"),
            self.widget,
        )
        self.nameEdit = LineEdit(self.widget)
        self.nameEdit.setPlaceholderText(
            self._tr(
                self._dialog_key("dialog.create.placeholder"),
                "Например: Игры / YouTube / Дом",
            )
        )
        self.nameEdit.setClearButtonEnabled(True)

        source_row = QHBoxLayout()
        source_label = BodyLabel(
            self._tr(self._dialog_key("dialog.create.source"), "Создать на основе"),
            self.widget,
        )
        source_row.addWidget(source_label)
        source_row.addStretch()
        try:
            from qfluentwidgets import SegmentedWidget

            self._source_seg = SegmentedWidget(self.widget)
            self._source_seg.addItem(
                "current",
                self._tr(self._dialog_key("dialog.create.source.current"), "Текущего пресета"),
            )
            self._source_seg.addItem(
                "standard",
                self._tr(self._dialog_key("dialog.create.source.standard"), "Встроенного пресета"),
            )
            self._source_seg.setCurrentItem("current")
            self._source_seg.currentItemChanged.connect(self._on_source_changed)
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

        self.yesButton.setText(self._tr(self._dialog_key("dialog.create.button.create"), "Создать"))
        self.cancelButton.setText(self._tr(self._dialog_key("dialog.button.cancel"), "Отмена"))
        self.widget.setMinimumWidth(420)
        self._install_accessibility()

    def validate(self) -> bool:
        name = self.nameEdit.text().strip()
        if not name:
            self._show_warning(
                self._tr(self._dialog_key("dialog.validation.enter_name"), "Введите название.")
            )
            self.warningLabel.show()
            return False
        self.warningLabel.hide()
        return True

    def _install_accessibility(self) -> None:
        set_control_accessibility(
            self.nameEdit,
            name="Название нового пресета",
            description="Например Игры, YouTube или Дом. Так пресет будет называться в списке.",
        )
        if hasattr(self, "_source_seg"):
            self._update_source_accessibility()
            set_control_accessibility(
                self._source_seg,
                description="Выберите, из чего создать новый пресет: из текущих настроек или из встроенного пресета.",
            )
        set_control_accessibility(
            self.yesButton,
            name="Создать пресет",
            description="Сохраняет текущие настройки как отдельный пресет.",
        )
        set_control_accessibility(
            self.cancelButton,
            name="Отменить создание пресета",
            description="Закрывает окно без создания пресета.",
        )

    def _on_source_changed(self, key: str) -> None:
        self._source = key
        self._update_source_accessibility()

    def _update_source_accessibility(self) -> None:
        selected = {
            "current": "Текущий пресет",
            "standard": "Встроенный пресет",
        }.get(str(self._source or "").strip(), "не выбрано")
        state_text = f"Основа нового пресета, выбрано: {selected}"
        set_control_accessibility(
            self._source_seg,
            name=state_text,
        )
        set_state_text(self._source_seg, state_text)

    def _show_warning(self, text: str) -> None:
        self.warningLabel.setText(text)
        set_state_text(self.warningLabel, f"Ошибка: {text}")


class RenamePresetDialog(PresetDialogTextMixin, MessageBoxBase):
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
            self._tr(self._dialog_key("dialog.rename.title"), "Переименовать"),
            self.widget,
        )
        self.subtitleLabel = BodyLabel(
            self._tr(
                self._dialog_key("dialog.rename.subtitle"),
                "Имя пресета отображается в списке и используется для переключения.",
            ),
            self.widget,
        )
        self.subtitleLabel.setWordWrap(True)

        from_label = CaptionLabel(
            self._tr(
                self._dialog_key("dialog.rename.current_name"),
                "Текущее имя: {name}",
                name=self._current_name,
            ),
            self.widget,
        )
        name_label = BodyLabel(
            self._tr(self._dialog_key("dialog.rename.new_name"), "Новое имя"),
            self.widget,
        )
        self.nameEdit = LineEdit(self.widget)
        self.nameEdit.setText(self._current_name)
        self.nameEdit.setPlaceholderText(
            self._tr(self._dialog_key("dialog.rename.placeholder"), "Новое имя...")
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

        self.yesButton.setText(self._tr(self._dialog_key("dialog.rename.button"), "Переименовать"))
        self.cancelButton.setText(self._tr(self._dialog_key("dialog.button.cancel"), "Отмена"))
        self.widget.setMinimumWidth(420)
        self._install_accessibility()

    def validate(self) -> bool:
        name = self.nameEdit.text().strip()
        if not name:
            self._show_warning(
                self._tr(self._dialog_key("dialog.validation.enter_name"), "Введите название.")
            )
            self.warningLabel.show()
            return False
        if name == self._current_name:
            self.warningLabel.hide()
            return True
        self.warningLabel.hide()
        return True

    def _install_accessibility(self) -> None:
        set_control_accessibility(
            self.nameEdit,
            name="Новое название пресета",
            description=f"Текущее имя: {self._current_name}. Введите новое имя для списка пресетов.",
        )
        set_control_accessibility(
            self.yesButton,
            name="Переименовать пресет",
            description="Меняет имя пресета в списке.",
        )
        set_control_accessibility(
            self.cancelButton,
            name="Отменить переименование пресета",
            description="Закрывает окно без изменения имени.",
        )

    def _show_warning(self, text: str) -> None:
        self.warningLabel.setText(text)
        set_state_text(self.warningLabel, f"Ошибка: {text}")


class ResetAllPresetsDialog(PresetDialogTextMixin, MessageBoxBase):
    """Диалог подтверждения возврата встроенных пресетов."""

    def __init__(self, parent=None, language: str = "ru"):
        if parent and not parent.isWindow():
            parent = parent.window()
        super().__init__(parent)
        self._ui_language = language
        self.titleLabel = SubtitleLabel(
            tr_presets_dialog(
                self._dialog_key("dialog.reset_all.title"),
                self._ui_language,
                "Вернуть встроенные пресеты",
            ),
            self.widget,
        )
        self.bodyLabel = BodyLabel(
            tr_presets_dialog(
                self._dialog_key("dialog.reset_all.body"),
                self._ui_language,
                "Мы вернём встроенные пресеты к состоянию после установки.\n"
                "Если вы меняли встроенный пресет, эти изменения будут потеряны.\n"
                "Пользовательские пресеты с другими именами останутся.\n"
                "Текущий выбранный пресет будет применён заново.",
            ),
            self.widget,
        )
        self.bodyLabel.setWordWrap(True)
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.bodyLabel)
        self.yesButton.setText(
            tr_presets_dialog(
                self._dialog_key("dialog.reset_all.button"),
                self._ui_language,
                "Вернуть встроенные",
            )
        )
        self.cancelButton.setText(
            tr_presets_dialog(self._dialog_key("dialog.button.cancel"), self._ui_language, "Отмена")
        )
        self.widget.setMinimumWidth(380)
        set_control_accessibility(
            self.yesButton,
            name="Вернуть встроенные пресеты",
            description="Изменения во встроенных пресетах будут потеряны. Пользовательские пресеты останутся.",
        )
        set_control_accessibility(
            self.cancelButton,
            name="Отменить возврат встроенных пресетов",
            description="Закрывает окно без возврата встроенных пресетов.",
        )
