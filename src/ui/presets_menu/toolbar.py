from __future__ import annotations

from PyQt6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget


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
        icon_name: str | None,
        *,
        accent: bool = False,
        fixed_height: int = 32,
    ) -> QWidget:
        from ui.fluent_widgets import ActionButton, PrimaryActionButton

        button_cls = PrimaryActionButton if accent else ActionButton
        button = button_cls(text, icon_name, parent=self.container)
        button.setFixedHeight(int(fixed_height))
        return button

    def create_primary_tool_button(self, button_cls, icon_arg, *, size: int = 36):
        button = button_cls(icon_arg)
        button.setParent(self.container)
        button.setFixedSize(int(size), int(size))
        return button

    def set_buttons(self, buttons) -> None:
        self._buttons = [button for button in buttons if button is not None]

    def refresh_for_viewport(self, viewport_width: int, margins) -> None:
        available_width = max(
            0,
            int(viewport_width) - int(margins.left()) - int(margins.right()),
        )
        self.refresh_layout(available_width)

    def refresh_layout(self, available_width: int) -> None:
        assigned_rows = self._compute_rows(int(available_width))

        for index, (row_widget, row_layout) in enumerate(self._rows):
            self._clear_row(row_layout)
            row_buttons = assigned_rows[index] if index < len(assigned_rows) else []

            if row_buttons:
                for button in row_buttons:
                    row_layout.addWidget(button)
                row_layout.addStretch(1)
                row_widget.setVisible(True)
            else:
                row_widget.setVisible(False)

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
