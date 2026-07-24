"""Диалог добавления или редактирования одного пользовательского DNS."""

from __future__ import annotations

from ipaddress import IPv4Address, IPv6Address
from uuid import uuid4

from qfluentwidgets import BodyLabel, CaptionLabel, LineEdit, SubtitleLabel
from ui.fluent_dialog import MessageBoxBase

from ui.accessibility import remove_line_edit_buttons_from_tab_order, set_control_accessibility, set_state_text
from ui.fluent_widgets import style_semantic_caption_label


class CustomDnsDialog(MessageBoxBase):
    """Окно для одного DNS: создать новый или изменить выбранный."""

    def __init__(self, parent=None, *, server: dict | None = None, ipv6_available: bool = False):
        if parent is not None and not parent.isWindow():
            parent = parent.window()
        super().__init__(parent)
        self._server = _copy_server(server or {})
        self._server_id = str(self._server.get("id") or "")
        self._show_ipv6 = bool(ipv6_available) or bool(self._server.get("ipv6"))

        editing = bool(self._server_id)
        self.titleLabel = SubtitleLabel("Редактировать свой DNS" if editing else "Добавить свой DNS", self.widget)
        self.subtitleLabel = BodyLabel(
            "Укажите DNS-сервер. После сохранения он появится в общем списке DNS.",
            self.widget,
        )
        self.subtitleLabel.setWordWrap(True)

        self.nameEdit = LineEdit(self.widget)
        self.nameEdit.setPlaceholderText("Название, например Мой DNS")
        self.nameEdit.setClearButtonEnabled(True)

        self.primaryEdit = LineEdit(self.widget)
        self.primaryEdit.setPlaceholderText("Основной IPv4 DNS, например 8.8.8.8")
        self.primaryEdit.setClearButtonEnabled(True)

        self.secondaryEdit = LineEdit(self.widget)
        self.secondaryEdit.setPlaceholderText("Дополнительный IPv4 DNS, например 1.1.1.1")
        self.secondaryEdit.setClearButtonEnabled(True)

        ipv4 = list(self._server.get("ipv4", []) or [])
        ipv6 = list(self._server.get("ipv6", []) or [])
        self.nameEdit.setText(str(self._server.get("name") or ""))
        self.primaryEdit.setText(str(ipv4[0] if ipv4 else ""))
        self.secondaryEdit.setText(str(ipv4[1] if len(ipv4) > 1 else ""))

        if self._show_ipv6:
            self.ipv6PrimaryEdit = LineEdit(self.widget)
            self.ipv6PrimaryEdit.setPlaceholderText("Основной IPv6 DNS, например 2001:4860:4860::8888")
            self.ipv6PrimaryEdit.setClearButtonEnabled(True)

            self.ipv6SecondaryEdit = LineEdit(self.widget)
            self.ipv6SecondaryEdit.setPlaceholderText("Дополнительный IPv6 DNS, например 2001:4860:4860::8844")
            self.ipv6SecondaryEdit.setClearButtonEnabled(True)

            self.ipv6PrimaryEdit.setText(str(ipv6[0] if ipv6 else ""))
            self.ipv6SecondaryEdit.setText(str(ipv6[1] if len(ipv6) > 1 else ""))

        self.warningLabel = CaptionLabel("", self.widget)
        style_semantic_caption_label(self.warningLabel, tone="error")
        self.warningLabel.hide()

        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.subtitleLabel)
        self.viewLayout.addWidget(BodyLabel("Название", self.widget))
        self.viewLayout.addWidget(self.nameEdit)
        self.viewLayout.addWidget(BodyLabel("Основной IPv4 DNS", self.widget))
        self.viewLayout.addWidget(self.primaryEdit)
        self.viewLayout.addWidget(BodyLabel("Дополнительный IPv4 DNS", self.widget))
        self.viewLayout.addWidget(self.secondaryEdit)
        if self._show_ipv6:
            self.viewLayout.addWidget(BodyLabel("Основной IPv6 DNS", self.widget))
            self.viewLayout.addWidget(self.ipv6PrimaryEdit)
            self.viewLayout.addWidget(BodyLabel("Дополнительный IPv6 DNS", self.widget))
            self.viewLayout.addWidget(self.ipv6SecondaryEdit)
        self.viewLayout.addWidget(self.warningLabel)

        self.yesButton.setText("Сохранить" if editing else "Добавить")
        self.cancelButton.setText("Отмена")
        self.widget.setMinimumWidth(520)
        self._install_accessibility(editing=editing)

    def server(self) -> dict:
        return _copy_server(self._server)

    def servers(self) -> list[dict]:
        server = self.server()
        return [server] if server.get("id") else []

    def validate(self) -> bool:
        name = self.nameEdit.text().strip()
        primary = self.primaryEdit.text().strip()
        secondary = self.secondaryEdit.text().strip()
        ipv6_primary = self.ipv6PrimaryEdit.text().strip() if self._show_ipv6 else ""
        ipv6_secondary = self.ipv6SecondaryEdit.text().strip() if self._show_ipv6 else ""
        if not name:
            self._show_warning("Введите название DNS.")
            return False
        if not primary and not secondary and not ipv6_primary and not ipv6_secondary:
            self._show_warning("Введите основной DNS сервер.")
            return False
        if secondary and not primary:
            self._show_warning("Введите основной IPv4 DNS сервер.")
            return False
        if primary and not _is_ipv4(primary):
            self._show_warning("Основной DNS должен быть IPv4 адресом.")
            return False
        if secondary and not _is_ipv4(secondary):
            self._show_warning("Дополнительный DNS должен быть IPv4 адресом.")
            return False
        if ipv6_secondary and not ipv6_primary:
            self._show_warning("Введите основной IPv6 DNS сервер.")
            return False
        if ipv6_primary and not _is_ipv6(ipv6_primary):
            self._show_warning("Основной DNS должен быть IPv6 адресом.")
            return False
        if ipv6_secondary and not _is_ipv6(ipv6_secondary):
            self._show_warning("Дополнительный DNS должен быть IPv6 адресом.")
            return False

        self._server = {
            "id": self._server_id or f"custom-{uuid4().hex[:12]}",
            "name": name,
            "ipv4": ([primary] if primary else []) + ([secondary] if secondary else []),
            "ipv6": ([ipv6_primary] if ipv6_primary else []) + ([ipv6_secondary] if ipv6_secondary else []),
        }
        self._server_id = str(self._server["id"])
        self.warningLabel.hide()
        return True

    def _install_accessibility(self, *, editing: bool) -> None:
        title_text = str(self.titleLabel.text() or "").strip()
        subtitle_text = str(self.subtitleLabel.text() or "").strip()
        if title_text:
            set_state_text(self.titleLabel, f"Диалог: {title_text}")
            set_control_accessibility(
                self.titleLabel,
                name=f"Диалог: {title_text}",
                description="Заголовок окна настройки своего DNS.",
            )
        if subtitle_text:
            set_state_text(self.subtitleLabel, f"Описание диалога DNS: {subtitle_text}")
            set_control_accessibility(
                self.subtitleLabel,
                name=f"Описание диалога DNS: {subtitle_text}",
                description="Поясняет, что нужно заполнить в окне своего DNS.",
            )
        set_control_accessibility(
            self.nameEdit,
            name="Название своего DNS",
            description="Введите понятное имя, которое будет показано в списке DNS.",
        )
        remove_line_edit_buttons_from_tab_order(self.nameEdit)
        set_control_accessibility(
            self.primaryEdit,
            name="Основной DNS сервер",
            description="Введите первый DNS сервер. Например 8.8.8.8.",
        )
        remove_line_edit_buttons_from_tab_order(self.primaryEdit)
        set_control_accessibility(
            self.secondaryEdit,
            name="Дополнительный IPv4 DNS сервер",
            description="Введите второй IPv4 DNS сервер, если он нужен.",
        )
        remove_line_edit_buttons_from_tab_order(self.secondaryEdit)
        if self._show_ipv6:
            set_control_accessibility(
                self.ipv6PrimaryEdit,
                name="Основной IPv6 DNS сервер",
                description="Введите первый IPv6 DNS сервер. Например 2001:4860:4860::8888.",
            )
            remove_line_edit_buttons_from_tab_order(self.ipv6PrimaryEdit)
            set_control_accessibility(
                self.ipv6SecondaryEdit,
                name="Дополнительный IPv6 DNS сервер",
                description="Введите второй IPv6 DNS сервер, если он нужен.",
            )
            remove_line_edit_buttons_from_tab_order(self.ipv6SecondaryEdit)

        action_text = "Сохранить свой DNS" if editing else "Добавить свой DNS"
        set_state_text(self.yesButton, action_text)
        set_control_accessibility(
            self.yesButton,
            name=action_text,
            description="Сохраняет DNS и закрывает окно.",
        )
        cancel_text = "Отменить изменение своего DNS" if editing else "Отменить добавление своего DNS"
        set_state_text(self.cancelButton, cancel_text)
        set_control_accessibility(
            self.cancelButton,
            name=cancel_text,
            description="Закрывает окно без применения изменений.",
        )

    def _show_warning(self, text: str) -> None:
        self.warningLabel.setText(text)
        self.warningLabel.show()
        set_state_text(self.warningLabel, f"Ошибка: {text}")


def _copy_server(server: dict) -> dict:
    return {
        "id": str(server.get("id") or ""),
        "name": str(server.get("name") or ""),
        "ipv4": [str(item) for item in server.get("ipv4", []) or []],
        "ipv6": [str(item) for item in server.get("ipv6", []) or []],
    }


def is_ipv4(value: str) -> bool:
    return _is_ipv4(value)


def is_ipv6(value: str) -> bool:
    return _is_ipv6(value)


def unique_copy_name(base_name: str, existing_names: list[str]) -> str:
    base = str(base_name or "Свой DNS").strip() or "Свой DNS"
    existing = {str(name or "").strip().lower() for name in existing_names}
    first = f"{base} копия"
    if first.lower() not in existing:
        return first
    index = 2
    while True:
        candidate = f"{first} {index}"
        if candidate.lower() not in existing:
            return candidate
        index += 1


def _is_ipv4(value: str) -> bool:
    try:
        IPv4Address(str(value).strip())
    except Exception:
        return False
    return True


def _is_ipv6(value: str) -> bool:
    try:
        IPv6Address(str(value).strip())
    except Exception:
        return False
    return True


__all__ = ["CustomDnsDialog", "is_ipv4", "is_ipv6", "unique_copy_name"]
