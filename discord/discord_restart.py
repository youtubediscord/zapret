# discord_restart.py

from PyQt6.QtWidgets import QMessageBox
from config import reg                       # ← единый helper

# ----------------------------------------------------------------------
# 1.  Чтение / запись настройки в реестре
# ----------------------------------------------------------------------
def get_discord_restart_setting(default: bool = True) -> bool:
    """
    Возвращает текущее значение AutoRestartDiscord.
    Если параметра нет – отдаёт default (по-умолчанию True).
    """
    val = reg(r"Software\ZapretReg2", "AutoRestartDiscord")
    return bool(val) if val is not None else default


def set_discord_restart_setting(enabled: bool) -> bool:
    """
    Записывает AutoRestartDiscord = 1/0.
    Возвращает True при успехе.
    """
    return reg(r"Software\ZapretReg2", "AutoRestartDiscord", int(enabled))


# ----------------------------------------------------------------------
# 2.  UI-переключатель
# ----------------------------------------------------------------------
def toggle_discord_restart(
        parent,
        status_callback=None,
        discord_auto_restart_attr_name: str = "discord_auto_restart"
    ) -> bool:
    """
    Переключает настройку автоперезапуска Discord, показывая диалоги
    подтверждения/информирования.

    parent  – QWidget-родитель для QMessageBox
    status_callback(msg) – функция вывода статуса (можно None)
    discord_auto_restart_attr_name – имя атрибута во `parent`,
                                     где хранится текущее значение
    """
    current = get_discord_restart_setting()

    # ----- хотим ОТКЛЮЧИТЬ ------------------------------------------------
    if current:
        msg = QMessageBox(parent)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("Отключение автоперезапуска Discord")
        msg.setText("Вы действительно хотите отключить автоматический "
                    "перезапуск Discord?")
        msg.setInformativeText(
            "После отключения вам придётся вручную перезапускать Discord "
            "при смене стратегии, иначе возможны проблемы со связью."
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if msg.exec() != QMessageBox.StandardButton.Yes:
            return False   # пользователь отменил

        set_discord_restart_setting(False)
        if hasattr(parent, discord_auto_restart_attr_name):
            setattr(parent, discord_auto_restart_attr_name, False)

        if status_callback:
            status_callback("Автоматический перезапуск Discord отключён")

        QMessageBox.information(parent, "Настройка изменена",
                                "Автоматический перезапуск Discord отключён.\n\n"
                                "При смене стратегии перезапускайте Discord вручную.")
        return True

    # ----- хотим ВКЛЮЧИТЬ -------------------------------------------------
    set_discord_restart_setting(True)
    if hasattr(parent, discord_auto_restart_attr_name):
        setattr(parent, discord_auto_restart_attr_name, True)

    if status_callback:
        status_callback("Автоматический перезапуск Discord включён")

    QMessageBox.information(parent, "Настройка изменена",
                            "Автоматический перезапуск Discord снова включён.")
    return True