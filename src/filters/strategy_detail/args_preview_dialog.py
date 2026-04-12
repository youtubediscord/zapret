"""
Диалог информации о стратегии.
Открывается как обычное окно у курсора мыши по ПКМ.
"""

from PyQt6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QVBoxLayout, QWidget,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QCursor

from qfluentwidgets import (
    BodyLabel, CaptionLabel, StrongBodyLabel,
    TextEdit, PushButton, TogglePushButton,
    isDarkTheme,
)
from qfluentwidgets.common.style_sheet import FluentStyleSheet

from ui.smooth_scroll import apply_editor_smooth_scroll_preference
from ui.theme_refresh import ThemeRefreshController


class ArgsPreviewDialog(QDialog):
    """
    Обычное окно с информацией о стратегии, открывается у курсора.

    Публичный интерфейс окна:
        dlg = ArgsPreviewDialog(parent_window)
        dlg.closed.connect(handler)
        dlg.set_strategy_data(data, strategy_id=..., ...)
        dlg.show_animated(global_pos)   # pos = QPoint или None → QCursor.pos()
        dlg.close_dialog()
    """

    closed = pyqtSignal()
    rating_changed = pyqtSignal(str, str)  # strategy_id, new_rating

    _PROVIDER_NAMES = {
        "universal": "All",
        "rostelecom": "Ростелеком",
        "mts": "МТС",
        "megafon": "МегаФон",
        "beeline": "Билайн",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Информация о стратегии")
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self._strategy_id = None
        self._target_key = None
        self._rating_getter = None
        self._rating_toggler = None
        self._original_args = ""

        self._info_strategy_id = None
        self._info_provider = None

        FluentStyleSheet.DIALOG.apply(self)

        self._init_ui()
        self._theme_refresh = ThemeRefreshController(self, self._refresh_info_label)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(8)

        self.title_label = StrongBodyLabel()
        layout.addWidget(self.title_label)

        self.author_label = CaptionLabel()
        self.author_label.hide()
        layout.addWidget(self.author_label)

        self.info_label = BodyLabel()
        self.info_label.setWordWrap(True)
        self.info_label.hide()
        layout.addWidget(self.info_label)

        self.args_widget = QWidget()
        args_layout = QVBoxLayout(self.args_widget)
        args_layout.setContentsMargins(0, 4, 0, 0)
        args_layout.setSpacing(6)

        args_header = QHBoxLayout()
        args_header.setSpacing(8)
        args_header.addWidget(CaptionLabel("Аргументы запуска:"))
        args_header.addStretch()

        self.copy_button = PushButton()
        self.copy_button.setText("Копировать")
        self.copy_button.setFixedHeight(24)
        self.copy_button.clicked.connect(self._copy_args)
        args_header.addWidget(self.copy_button)
        args_layout.addLayout(args_header)

        self.args_text = TextEdit()
        apply_editor_smooth_scroll_preference(self.args_text)
        self.args_text.setReadOnly(True)
        self.args_text.setMinimumHeight(60)
        self.args_text.setMaximumHeight(200)
        args_layout.addWidget(self.args_text)

        layout.addWidget(self.args_widget)

        rating_widget = QWidget()
        rating_layout = QHBoxLayout(rating_widget)
        rating_layout.setContentsMargins(0, 4, 0, 0)
        rating_layout.setSpacing(8)

        rating_layout.addWidget(CaptionLabel("Оценить:"))
        rating_layout.addStretch()

        self.working_button = TogglePushButton()
        self.working_button.setText("РАБОЧАЯ")
        self.working_button.setFixedHeight(26)
        self.working_button.clicked.connect(lambda: self._toggle_rating("working"))
        rating_layout.addWidget(self.working_button)

        self.broken_button = TogglePushButton()
        self.broken_button.setText("НЕРАБОЧАЯ")
        self.broken_button.setFixedHeight(26)
        self.broken_button.clicked.connect(lambda: self._toggle_rating("broken"))
        rating_layout.addWidget(self.broken_button)

        layout.addWidget(rating_widget)

        self.setMinimumWidth(420)
        self.setMaximumWidth(520)

    def set_pinned(self, pinned: bool) -> None:
        pass

    def set_hover_follow(self, enabled: bool, offset=None) -> None:
        pass

    def set_strategy_data(
        self,
        strategy_data,
        strategy_id=None,
        source_widget=None,
        target_key=None,
        rating_getter=None,
        rating_toggler=None,
    ):
        self._strategy_id = strategy_id
        self._target_key = target_key
        self._rating_getter = rating_getter
        self._rating_toggler = rating_toggler

        name = strategy_data.get("name", strategy_id or "Стратегия")
        self.title_label.setText(name)
        self.setWindowTitle(name)

        author = strategy_data.get("author")
        if author and author != "unknown":
            self.author_label.setText(f"Автор: {author}")
            self.author_label.show()
        else:
            self.author_label.hide()

        self._info_strategy_id = strategy_id
        self._info_provider = strategy_data.get("provider", "universal")
        self._refresh_info_label()

        args = strategy_data.get("args", "")
        self._original_args = str(args)
        if args:
            self.args_text.setPlainText(str(args))
            self.args_widget.show()
        else:
            self.args_widget.hide()

        self._update_rating_buttons()
        self.adjustSize()

    def _refresh_info_label(self) -> None:
        if self._info_strategy_id is None and self._info_provider is None:
            return
        _dark = isDarkTheme()
        id_color = "#60cdff" if _dark else "#0066cc"
        prov_color = "#a78bfa" if _dark else "#7c3aed"

        info_parts = []
        if self._info_strategy_id:
            info_parts.append(
                f"<span style='color:{id_color}'>ID:</span> {self._info_strategy_id}"
            )
        if self._info_provider:
            prov_name = self._PROVIDER_NAMES.get(self._info_provider, self._info_provider)
            info_parts.append(f"<span style='color:{prov_color}'>{prov_name}</span>")

        if info_parts:
            self.info_label.setText(" • ".join(info_parts))
            self.info_label.setTextFormat(Qt.TextFormat.RichText)
            self.info_label.show()
        else:
            self.info_label.hide()

    def show_animated(self, pos=None):
        if pos is None:
            pos = QCursor.pos()

        self.adjustSize()
        screen = None
        try:
            screen = QApplication.primaryScreen().availableGeometry()
        except Exception:
            pass

        x, y = pos.x() + 12, pos.y() + 12
        if screen is not None:
            if x + self.width() > screen.right():
                x = pos.x() - self.width() - 12
            if y + self.height() > screen.bottom():
                y = pos.y() - self.height() - 12
            x = max(screen.left(), x)
            y = max(screen.top(), y)

        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()

    def close_dialog(self):
        self.close()

    def closeEvent(self, e):
        super().closeEvent(e)
        try:
            self.closed.emit()
        except Exception:
            pass

    def _update_rating_buttons(self):
        current_rating = None
        if self._rating_getter and self._strategy_id and self._target_key:
            try:
                current_rating = self._rating_getter(self._strategy_id, self._target_key)
            except Exception:
                pass

        self.working_button.blockSignals(True)
        self.broken_button.blockSignals(True)
        self.working_button.setChecked(current_rating == "working")
        self.broken_button.setChecked(current_rating == "broken")
        self.working_button.blockSignals(False)
        self.broken_button.blockSignals(False)

    def _toggle_rating(self, rating: str):
        if not self._strategy_id:
            return
        new_rating = None
        if self._rating_toggler:
            try:
                new_rating = self._rating_toggler(
                    self._strategy_id, rating, self._target_key
                )
            except Exception:
                pass
        self._update_rating_buttons()
        self.rating_changed.emit(self._strategy_id or "", new_rating or "")

    def _copy_args(self):
        if self._original_args:
            QApplication.clipboard().setText(self._original_args)
            self.copy_button.setText("✓ Скопировано")
            QTimer.singleShot(1500, lambda: self.copy_button.setText("Копировать"))
