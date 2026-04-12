# ui/close_dialog.py
"""
WinUI диалог выбора варианта закрытия приложения.
Показывается при нажатии на крестик (X) в titlebar.
"""

from PyQt6.QtWidgets import QHBoxLayout
from qfluentwidgets import (
    MessageBoxBase, SubtitleLabel, BodyLabel,
)
from ui.dialog_action_buttons import create_dialog_action_button, create_dialog_cancel_button


class CloseDialog(MessageBoxBase):
    """
    WinUI диалог: варианты закрытия приложения.

    Результат через ask_close_action():
      - None    -> отмена (Esc / клик мимо)
      - "tray"  -> свернуть в трей
      - False   -> закрыть только GUI
      - True    -> закрыть GUI + остановить DPI
    """

    def __init__(self, parent=None, *, launch_running: bool = True):
        if parent and not parent.isWindow():
            parent = parent.window()
        super().__init__(parent)
        self.result_stop_dpi = None
        self.result_tray = False
        self._launch_running = bool(launch_running)

        # --- Заголовок и описание ---
        self.titleLabel = SubtitleLabel("Закрыть приложение", self.widget)
        description = (
            "DPI обход (winws) продолжит работать в фоне,\n"
            "если закрыть только GUI или свернуть окно в трей."
            if self._launch_running
            else
            "DPI сейчас не запущен.\n"
            "Вы можете свернуть окно в трей или просто закрыть GUI."
        )
        self.bodyLabel = BodyLabel(description, self.widget)
        self.bodyLabel.setWordWrap(True)
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.bodyLabel)
        self.viewLayout.addSpacing(8)

        # --- Кнопка "Свернуть в трей" ---
        self.trayButton = create_dialog_action_button(
            self.widget,
            text="Свернуть в трей",
            icon_name="fa5s.window-restore",
            icon_color="#d0d0d0",
        )
        self.trayButton.clicked.connect(self._on_tray)
        self.viewLayout.addWidget(self.trayButton)

        # --- Кнопка "Закрыть только GUI" ---
        self.guiOnlyButton = create_dialog_action_button(
            self.widget,
            text="Закрыть только GUI",
            icon_name="fa5s.sign-out-alt",
            icon_color="#aaaaaa",
        )
        self.guiOnlyButton.clicked.connect(self._on_gui_only)
        self.viewLayout.addWidget(self.guiOnlyButton)

        # --- Кнопка "Закрыть и остановить DPI" (danger/red) ---
        self.stopDpiButton = create_dialog_action_button(
            self.widget,
            text="Закрыть и остановить DPI",
            danger=True,
        )
        self.stopDpiButton.clicked.connect(self._on_stop_dpi)
        self.stopDpiButton.setEnabled(self._launch_running)
        self.viewLayout.addWidget(self.stopDpiButton)

        # --- Кнопка "Отмена" (прозрачная, по центру) ---
        self._cancelRow = QHBoxLayout()
        self._cancelRow.addStretch()
        self.cancelLinkButton = create_dialog_cancel_button(
            self.widget,
            text="Отмена",
            icon_name="fa5s.times",
            icon_color="#aaaaaa",
        )
        self.cancelLinkButton.clicked.connect(self.reject)
        self._cancelRow.addWidget(self.cancelLinkButton)
        self._cancelRow.addStretch()
        self.viewLayout.addLayout(self._cancelRow)

        # Скрываем дефолтные кнопки MessageBoxBase и убираем их пространство
        self.yesButton.hide()
        self.cancelButton.hide()
        self.buttonGroup.setFixedHeight(0)

        self.widget.setMinimumWidth(440)

    def _on_tray(self):
        self.result_tray = True
        self.accept()

    def _on_gui_only(self):
        self.result_stop_dpi = False
        self.accept()

    def _on_stop_dpi(self):
        self.result_stop_dpi = True
        self.accept()


def ask_close_action(parent=None):
    """
    Возвращает действие закрытия приложения:
      - None   -> пользователь отменил
      - "tray" -> свернуть в трей
      - False  -> закрыть только GUI
      - True   -> закрыть GUI + остановить DPI

    """
    is_launch_running = _is_launch_running(parent)

    dlg = CloseDialog(parent, launch_running=is_launch_running)
    dlg.exec()
    if dlg.result_tray:
        return "tray"
    return dlg.result_stop_dpi


def _is_launch_running(parent=None) -> bool:
    app_runtime_state = getattr(parent, "app_runtime_state", None)
    if app_runtime_state is None:
        return False
    try:
        return bool(app_runtime_state.is_launch_running())
    except Exception:
        return False
