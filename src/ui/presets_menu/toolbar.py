from __future__ import annotations

from PyQt6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import PrimaryPushButton, PushButton


class PresetsToolbarLayout:
    """Общий переносимый тулбар страницы пресетов."""

    def __init__(
        self,
        parent: QWidget,
        *,
        row_count: int = 4,
        row_spacing: int = 8,
        button_spacing: int = 12,
    ) -> None:
        self.container = QWidget(parent)
        self.container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        self._row_spacing = max(0, int(row_spacing))
        self._button_spacing = max(0, int(button_spacing))
        self._buttons: list[QWidget] = []
        self._rows: list[tuple[QWidget, QHBoxLayout]] = []
        self._trailing_widget: QWidget | None = None
        self._trailing_minimum_width = 260

        self._layout = QVBoxLayout(self.container)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(self._row_spacing)

        for _ in range(max(1, int(row_count))):
            row_widget = QWidget(self.container)
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(self._button_spacing)
            row_widget.setVisible(False)
            self._layout.addWidget(row_widget)
            self._rows.append((row_widget, row_layout))

    def create_action_button(
        self,
        text: str,
        icon,
        *,
        accent: bool = False,
        fixed_height: int = 32,
    ) -> QWidget:
        button_cls = PrimaryPushButton if accent else PushButton
        button = button_cls(text, parent=self.container, icon=icon)
        button.setFixedHeight(int(fixed_height))
        return button

    def create_primary_tool_button(self, button_cls, icon_arg, *, size: int = 36):
        button = button_cls(icon_arg)
        button.setParent(self.container)
        button.setFixedSize(int(size), int(size))
        return button

    def set_buttons(self, buttons) -> None:
        self._buttons = [button for button in buttons if button is not None]
        for button in self._buttons:
            button.setParent(self.container)

    def set_trailing_widget(self, widget: QWidget | None, *, minimum_width: int = 260) -> None:
        self._trailing_widget = widget
        self._trailing_minimum_width = max(0, int(minimum_width))
        if widget is None:
            return
        widget.setParent(self.container)
        widget.setMinimumWidth(self._trailing_minimum_width)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def refresh_for_viewport(self, viewport_width: int, margins) -> None:
        available_width = max(
            0,
            int(viewport_width) - int(margins.left()) - int(margins.right()),
        )
        self.refresh_layout(available_width)

    def refresh_layout(self, available_width: int) -> None:
        assigned_rows = self._compute_layout_rows(int(available_width))

        for index, (row_widget, row_layout) in enumerate(self._rows):
            self._clear_row(row_layout)
            row = assigned_rows[index] if index < len(assigned_rows) else ([], False)
            row_buttons, has_trailing = row

            if row_buttons or has_trailing:
                for button in row_buttons:
                    row_layout.addWidget(button)
                if has_trailing and self._trailing_widget is not None:
                    if row_buttons:
                        row_layout.addStretch(1)
                    row_layout.addWidget(self._trailing_widget, 1)
                else:
                    row_layout.addStretch(1)
                row_widget.setVisible(True)
            else:
                row_widget.setVisible(False)

    def _compute_layout_rows(self, available_width: int) -> list[tuple[list[QWidget], bool]]:
        button_rows = self._compute_rows(available_width)
        trailing = self._trailing_widget
        if trailing is None or trailing.isHidden():
            return [(row, False) for row in button_rows]

        if not button_rows:
            return [([], True)]

        if len(button_rows) == 1 and self._row_fits_trailing(button_rows[0], available_width):
            return [(button_rows[0], True)]

        return [(row, False) for row in button_rows] + [([], True)]

    def _row_fits_trailing(self, row_buttons: list[QWidget], available_width: int) -> bool:
        if available_width <= 0:
            return True
        buttons_width = self._buttons_width(row_buttons)
        if buttons_width <= 0:
            return self._trailing_minimum_width <= available_width
        return buttons_width + self._button_spacing + self._trailing_minimum_width <= available_width

    def _buttons_width(self, buttons: list[QWidget]) -> int:
        if not buttons:
            return 0
        widths = [int(button.sizeHint().width()) for button in buttons]
        return sum(widths) + self._button_spacing * max(0, len(widths) - 1)

    def _visible_buttons(self) -> list[QWidget]:
        return [button for button in self._buttons if not button.isHidden()]

    def _compute_rows(self, available_width: int) -> list[list[QWidget]]:
        buttons = self._visible_buttons()
        if not buttons:
            return []

        if available_width <= 0:
            return [buttons]

        rows: list[list[QWidget]] = []
        current_row: list[QWidget] = []
        current_width = 0

        for button in buttons:
            button_width = button.sizeHint().width()
            if not current_row:
                current_row = [button]
                current_width = button_width
                continue

            next_width = current_width + self._button_spacing + button_width
            if next_width <= available_width:
                current_row.append(button)
                current_width = next_width
                continue

            rows.append(current_row)
            current_row = [button]
            current_width = button_width

        if current_row:
            rows.append(current_row)

        return rows

    @staticmethod
    def _clear_row(row_layout: QHBoxLayout) -> None:
        while row_layout.count():
            row_layout.takeAt(0)


__all__ = ["PresetsToolbarLayout"]
