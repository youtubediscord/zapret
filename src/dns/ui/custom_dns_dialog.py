"""Диалог управления пользовательскими DNS-серверами."""

from __future__ import annotations

from ipaddress import IPv4Address
from uuid import uuid4

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QListWidget, QListWidgetItem
from qfluentwidgets import BodyLabel, CaptionLabel, LineEdit, MessageBoxBase, PushButton, RoundMenu, SubtitleLabel

from ui.accessibility import remove_line_edit_buttons_from_tab_order, set_control_accessibility, set_state_text
from ui.fluent_widgets import style_semantic_caption_label
from ui.popup_menu import exec_popup_menu
from ui.presets_menu.common import fluent_icon, make_menu_action


class CustomDnsDialog(MessageBoxBase):
    """Окно добавления и редактирования пользовательских DNS."""

    def __init__(self, parent=None, *, servers: list[dict] | None = None):
        if parent is not None and not parent.isWindow():
            parent = parent.window()
        super().__init__(parent)
        self._servers: list[dict] = [_copy_server(server) for server in (servers or [])]
        self._selected_id = ""

        self.titleLabel = SubtitleLabel("Свои DNS", self.widget)
        self.subtitleLabel = BodyLabel(
            "Добавьте DNS-серверы в список. Потом их можно будет выбрать на странице как обычный DNS.",
            self.widget,
        )
        self.subtitleLabel.setWordWrap(True)

        self.serversList = QListWidget(self.widget)
        self.serversList.setMinimumHeight(140)
        self.serversList.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.serversList.viewport().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.serversList.currentItemChanged.connect(self._on_current_item_changed)
        self.serversList.customContextMenuRequested.connect(self._show_servers_context_menu)
        self.serversList.viewport().customContextMenuRequested.connect(self._show_servers_context_menu)
        self.serversList.installEventFilter(self)
        self.serversList.setStyleSheet(
            """
            QListWidget {
                background: transparent;
                border: none;
                outline: none;
            }
            QListWidget::item {
                background: transparent;
                border: none;
            }
            """
        )

        self.nameEdit = LineEdit(self.widget)
        self.nameEdit.setPlaceholderText("Название, например Мой DNS")
        self.nameEdit.setClearButtonEnabled(True)

        self.primaryEdit = LineEdit(self.widget)
        self.primaryEdit.setPlaceholderText("Основной DNS, например 8.8.8.8")
        self.primaryEdit.setClearButtonEnabled(True)

        self.secondaryEdit = LineEdit(self.widget)
        self.secondaryEdit.setPlaceholderText("Дополнительный DNS, например 1.1.1.1")
        self.secondaryEdit.setClearButtonEnabled(True)

        self.deleteButton = PushButton("Удалить", self.widget)
        self.deleteButton.clicked.connect(self.delete_current)

        actions = QHBoxLayout()
        actions.addWidget(self.deleteButton)
        actions.addStretch()

        self.warningLabel = CaptionLabel("", self.widget)
        style_semantic_caption_label(self.warningLabel, tone="error")
        self.warningLabel.hide()

        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.subtitleLabel)
        self.viewLayout.addWidget(self.serversList)
        self.viewLayout.addWidget(BodyLabel("Название", self.widget))
        self.viewLayout.addWidget(self.nameEdit)
        self.viewLayout.addWidget(BodyLabel("Основной DNS", self.widget))
        self.viewLayout.addWidget(self.primaryEdit)
        self.viewLayout.addWidget(BodyLabel("Дополнительный DNS", self.widget))
        self.viewLayout.addWidget(self.secondaryEdit)
        self.viewLayout.addLayout(actions)
        self.viewLayout.addWidget(self.warningLabel)

        self.yesButton.setText("Добавить")
        self.cancelButton.setText("Отмена")
        self.widget.setMinimumWidth(520)
        self._install_accessibility()
        self._reload_list()
        self._sync_buttons()

    def servers(self) -> list[dict]:
        return [_copy_server(server) for server in self._servers]

    def validate(self) -> bool:
        return self.save_current()

    def save_current(self) -> bool:
        name = self.nameEdit.text().strip()
        primary = self.primaryEdit.text().strip()
        secondary = self.secondaryEdit.text().strip()
        if not name:
            self._show_warning("Введите название DNS.")
            return False
        if not primary:
            self._show_warning("Введите основной DNS сервер.")
            return False
        if not _is_ipv4(primary):
            self._show_warning("Основной DNS должен быть IPv4 адресом.")
            return False
        if secondary and not _is_ipv4(secondary):
            self._show_warning("Дополнительный DNS должен быть IPv4 адресом.")
            return False
        duplicate = next(
            (
                server
                for server in self._servers
                if server.get("id") != self._selected_id
                and str(server.get("name") or "").strip().lower() == name.lower()
            ),
            None,
        )
        if duplicate is not None:
            self._show_warning("DNS с таким названием уже есть.")
            return False

        server = {
            "id": self._selected_id or f"custom-{uuid4().hex[:12]}",
            "name": name,
            "ipv4": [primary] + ([secondary] if secondary else []),
            "ipv6": [],
        }
        for index, item in enumerate(self._servers):
            if item.get("id") == server["id"]:
                self._servers[index] = server
                break
        else:
            self._servers.append(server)
        self._selected_id = str(server["id"])
        self.warningLabel.hide()
        self._reload_list(select_id=self._selected_id)
        return True

    def delete_current(self) -> bool:
        if not self._selected_id:
            return False
        self._servers = [server for server in self._servers if server.get("id") != self._selected_id]
        self._selected_id = ""
        self._clear_form()
        self._reload_list()
        return True

    def _reload_list(self, *, select_id: str = "") -> None:
        self.serversList.blockSignals(True)
        self.serversList.clear()
        selected_row = -1
        for row, server in enumerate(self._servers):
            item = QListWidgetItem(str(server.get("name") or "Свой DNS"))
            item.setData(Qt.ItemDataRole.UserRole, str(server.get("id") or ""))
            item.setData(Qt.ItemDataRole.AccessibleTextRole, _server_accessible_text(server))
            self.serversList.addItem(item)
            if item.data(Qt.ItemDataRole.UserRole) == select_id:
                selected_row = row
        self.serversList.blockSignals(False)
        if selected_row >= 0:
            self.serversList.setCurrentRow(selected_row)
        self._sync_servers_list_visibility()
        self._update_servers_list_accessibility(self.serversList.currentItem())
        self._sync_buttons()

    def _on_current_item_changed(self, item, _previous) -> None:
        self._update_servers_list_accessibility(item)
        if item is None:
            self._selected_id = ""
            self._clear_form()
            return
        self._selected_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
        server = next((entry for entry in self._servers if entry.get("id") == self._selected_id), None)
        if server is None:
            self._clear_form()
            return
        ipv4 = list(server.get("ipv4", []) or [])
        self.nameEdit.setText(str(server.get("name") or ""))
        self.primaryEdit.setText(str(ipv4[0] if ipv4 else ""))
        self.secondaryEdit.setText(str(ipv4[1] if len(ipv4) > 1 else ""))
        self.yesButton.setText("Сохранить")
        self._sync_buttons()

    def _clear_form(self) -> None:
        self.nameEdit.clear()
        self.primaryEdit.clear()
        self.secondaryEdit.clear()
        self.yesButton.setText("Добавить")
        self._sync_buttons()

    def _sync_buttons(self) -> None:
        is_editing = bool(self._selected_id)
        self.deleteButton.setVisible(is_editing)
        self.deleteButton.setEnabled(is_editing)

    def _sync_servers_list_visibility(self) -> None:
        self.serversList.setVisible(self.serversList.count() > 0)

    def _show_servers_context_menu(self, pos) -> None:
        item = self.serversList.itemAt(pos)
        if item is None:
            return
        self.serversList.setCurrentItem(item)
        self._on_current_item_changed(item, None)

        menu = RoundMenu(parent=self)
        action_map: dict[object, str] = {}

        def add_action(text: str, *, icon_name: str, command: str):
            action = make_menu_action(text, icon=fluent_icon(icon_name), parent=menu)
            menu.addAction(action)
            menu_item = menu.view.item(menu.view.count() - 1)
            if menu_item is not None:
                menu_item.setData(Qt.ItemDataRole.AccessibleTextRole, text)
                menu_item.setData(Qt.ItemDataRole.AccessibleDescriptionRole, text)
            action_map[action] = command
            return action

        add_action("Редактировать", icon_name="EDIT", command="edit")
        add_action("Создать копию", icon_name="COPY", command="duplicate")
        add_action("Копировать DNS", icon_name="COPY", command="copy")
        menu.addSeparator()
        add_action("Новый DNS", icon_name="ADD", command="new")
        menu.addSeparator()
        add_action("Удалить", icon_name="DELETE", command="delete")

        chosen = exec_popup_menu(
            menu,
            self.serversList.viewport().mapToGlobal(pos),
            owner=self,
            capture_action=True,
        )
        command = action_map.get(chosen, "")
        if command == "edit":
            self._edit_current_server()
        elif command == "duplicate":
            self._duplicate_current_server()
        elif command == "copy":
            self._copy_current_dns_to_clipboard()
        elif command == "new":
            self._new_server_from_context_menu()
        elif command == "delete":
            self._delete_current_server()

    def _edit_current_server(self) -> bool:
        item = self.serversList.currentItem()
        if item is None:
            return False
        self._on_current_item_changed(item, None)
        try:
            self.nameEdit.setFocus(Qt.FocusReason.OtherFocusReason)
            self.nameEdit.selectAll()
        except Exception:
            pass
        return True

    def _new_server_from_context_menu(self) -> bool:
        self.serversList.setCurrentItem(None)
        self._selected_id = ""
        self._clear_form()
        try:
            self.nameEdit.setFocus(Qt.FocusReason.OtherFocusReason)
        except Exception:
            pass
        return True

    def _copy_current_dns_to_clipboard(self) -> bool:
        server = self._current_server()
        if server is None:
            return False
        dns_values = [str(item).strip() for item in server.get("ipv4", []) or [] if str(item).strip()]
        if not dns_values:
            return False
        clipboard = QApplication.clipboard()
        if clipboard is None:
            return False
        clipboard.setText(", ".join(dns_values))
        return True

    def _duplicate_current_server(self) -> bool:
        server = self._current_server()
        if server is None:
            return False
        name = _unique_copy_name(
            str(server.get("name") or "Свой DNS"),
            [str(item.get("name") or "") for item in self._servers],
        )
        copy_server = _copy_server(server)
        copy_server["id"] = f"custom-{uuid4().hex[:12]}"
        copy_server["name"] = name
        self._servers.append(copy_server)
        self._selected_id = str(copy_server["id"])
        self.warningLabel.hide()
        self._reload_list(select_id=self._selected_id)
        return True

    def _delete_current_server(self) -> bool:
        return self.delete_current()

    def _current_server(self) -> dict | None:
        selected_id = str(self._selected_id or "").strip()
        if not selected_id:
            item = self.serversList.currentItem()
            if item is not None:
                selected_id = str(item.data(Qt.ItemDataRole.UserRole) or "").strip()
        if not selected_id:
            return None
        return next((entry for entry in self._servers if entry.get("id") == selected_id), None)

    def _install_accessibility(self) -> None:
        set_control_accessibility(
            self.serversList,
            name="Список своих DNS",
            description="Выберите DNS стрелками вверх и вниз. Правый клик или клавиша меню открывает быстрые действия.",
        )
        set_state_text(self.serversList, "Список своих DNS")
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
            name="Дополнительный DNS сервер",
            description="Введите второй DNS сервер, если он нужен.",
        )
        remove_line_edit_buttons_from_tab_order(self.secondaryEdit)
        set_state_text(self.deleteButton, "Удалить свой DNS")
        set_control_accessibility(
            self.deleteButton,
            name="Удалить свой DNS",
            description="Удаляет выбранный DNS из пользовательского списка.",
        )
        set_state_text(self.yesButton, "Добавить или сохранить свой DNS")
        set_control_accessibility(
            self.yesButton,
            name="Добавить или сохранить свой DNS",
            description="Сохраняет введённый DNS и закрывает окно.",
        )
        set_state_text(self.cancelButton, "Отменить изменение своих DNS")
        set_control_accessibility(
            self.cancelButton,
            name="Отменить изменение своих DNS",
            description="Закрывает окно без применения изменений к странице.",
        )

    def eventFilter(self, watched, event):  # noqa: N802
        servers_list = getattr(self, "serversList", None)
        if servers_list is not None and watched is servers_list:
            if event.type() == QEvent.Type.FocusIn:
                if self.serversList.currentItem() is None:
                    self._focus_first_server()
                self._update_servers_list_accessibility(self.serversList.currentItem())
            elif event.type() == QEvent.Type.KeyPress and event.key() in (
                Qt.Key.Key_Return,
                Qt.Key.Key_Enter,
                Qt.Key.Key_Space,
            ):
                item = self.serversList.currentItem()
                if item is not None:
                    self._on_current_item_changed(item, None)
                    event.accept()
                    return True
            elif event.type() == QEvent.Type.KeyPress and (
                event.key() == Qt.Key.Key_Menu
                or (
                    event.key() == Qt.Key.Key_F10
                    and bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
                )
            ):
                item = self.serversList.currentItem()
                if item is not None:
                    self._show_servers_context_menu(self.serversList.visualItemRect(item).center())
                    event.accept()
                    return True
        return super().eventFilter(watched, event)

    def _focus_first_server(self) -> None:
        if self.serversList.count() > 0:
            self.serversList.setCurrentRow(0)

    def _update_servers_list_accessibility(self, item) -> None:
        text = str(item.data(Qt.ItemDataRole.AccessibleTextRole) or "").strip() if item is not None else ""
        if text:
            set_state_text(
                self.serversList,
                f"Список своих DNS: {text}. Нажмите Enter или Пробел, чтобы выбрать DNS для изменения.",
            )
            return
        set_state_text(self.serversList, "Список своих DNS")

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


def _is_ipv4(value: str) -> bool:
    try:
        IPv4Address(str(value).strip())
    except Exception:
        return False
    return True


def _server_accessible_text(server: dict) -> str:
    name = str(server.get("name") or "Свой DNS").strip() or "Свой DNS"
    ipv4 = [str(item).strip() for item in server.get("ipv4", []) or [] if str(item).strip()]
    if ipv4:
        return f"{name}, DNS {', '.join(ipv4)}"
    return name


def _unique_copy_name(base_name: str, existing_names: list[str]) -> str:
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


__all__ = ["CustomDnsDialog"]
