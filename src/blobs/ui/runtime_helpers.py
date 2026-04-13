"""Runtime/helper слой для BlobsPage."""

from __future__ import annotations

import os

from PyQt6.QtWidgets import QLabel

from ui.compat_widgets import set_tooltip
from blobs.ui.components import AddBlobDialog, BlobItemWidget


def clear_blobs_layout(blobs_layout) -> None:
    while blobs_layout.count():
        item = blobs_layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()


def load_blobs_into_ui(
    *,
    cleanup_in_progress: bool,
    blobs_layout,
    ui_language: str,
    tr_fn,
    on_delete_blob,
    count_label,
    apply_page_theme,
    log_error,
    log_debug,
) -> None:
    if cleanup_in_progress:
        return
    try:
        from blobs.service import get_blobs_info

        clear_blobs_layout(blobs_layout)
        blobs_info = get_blobs_info()

        user_blobs = {k: v for k, v in blobs_info.items() if v.get("is_user")}
        system_blobs = {k: v for k, v in blobs_info.items() if not v.get("is_user")}

        if user_blobs:
            user_header = QLabel(
                tr_fn("page.blobs.section.user", "★ Пользовательские ({count})", count=len(user_blobs))
            )
            user_header.setProperty("blobSection", "user")
            blobs_layout.addWidget(user_header)

            for name, info in sorted(user_blobs.items()):
                item = BlobItemWidget(name, info, language=ui_language)
                item.deleted.connect(on_delete_blob)
                blobs_layout.addWidget(item)

        if system_blobs:
            system_header = QLabel(
                tr_fn("page.blobs.section.system", "Системные ({count})", count=len(system_blobs))
            )
            system_header.setProperty("blobSection", "system")
            blobs_layout.addWidget(system_header)

            for name, info in sorted(system_blobs.items()):
                item = BlobItemWidget(name, info, language=ui_language)
                blobs_layout.addWidget(item)

        total = len(blobs_info)
        user_count = len(user_blobs)
        count_label.setText(
            tr_fn("page.blobs.count", "{total} блобов ({user} пользовательских)", total=total, user=user_count)
        )

        apply_page_theme(force=True)
    except Exception as exc:
        log_error(f"Ошибка загрузки блобов: {exc}")
        try:
            import traceback
            log_debug(traceback.format_exc())
        except Exception:
            pass
        error_label = QLabel(
            tr_fn("page.blobs.error.load", "❌ Ошибка загрузки: {error}", error=exc)
        )
        error_label.setProperty("blobSection", "error")
        blobs_layout.addWidget(error_label)
        apply_page_theme(force=True)


def filter_blobs_in_ui(*, cleanup_in_progress: bool, blobs_layout, text: str) -> None:
    if cleanup_in_progress:
        return
    text = text.lower()
    for i in range(blobs_layout.count()):
        item = blobs_layout.itemAt(i)
        if item and item.widget():
            widget = item.widget()
            if isinstance(widget, BlobItemWidget):
                match = (
                    text in widget.blob_name.lower()
                    or text in widget.blob_info.get("description", "").lower()
                )
                widget.setVisible(match)


def add_blob_via_dialog(
    *,
    window,
    ui_language: str,
    reload_callback,
    tr_fn,
    info_bar_cls,
    log_info,
    log_error,
) -> None:
    dialog = AddBlobDialog(window, language=ui_language)
    if dialog.exec():
        data = dialog.get_data()
        try:
            from blobs.service import save_user_blob

            if save_user_blob(data["name"], data["type"], data["value"], data["description"]):
                log_info(f"Добавлен блоб: {data['name']}")
                reload_callback()
            else:
                info_bar_cls.warning(
                    title=tr_fn("common.error.title", "Ошибка"),
                    content=tr_fn("page.blobs.error.save", "Не удалось сохранить блоб"),
                    parent=window,
                )
        except Exception as exc:
            log_error(f"Ошибка добавления блоба: {exc}")
            info_bar_cls.warning(
                title=tr_fn("common.error.title", "Ошибка"),
                content=tr_fn("page.blobs.error.add", "Не удалось добавить блоб: {error}", error=exc),
                parent=window,
            )


def delete_blob_named(
    *,
    name: str,
    reload_callback,
    tr_fn,
    info_bar_cls,
    window,
    log_info,
    log_error,
) -> None:
    try:
        from blobs.service import delete_user_blob

        if delete_user_blob(name):
            log_info(f"Удалён блоб: {name}")
            reload_callback()
        else:
            info_bar_cls.warning(
                title=tr_fn("common.error.title", "Ошибка"),
                content=tr_fn("page.blobs.error.delete_named", "Не удалось удалить блоб '{name}'", name=name),
                parent=window,
            )
    except Exception as exc:
        log_error(f"Ошибка удаления блоба: {exc}")
        info_bar_cls.warning(
            title=tr_fn("common.error.title", "Ошибка"),
            content=tr_fn("page.blobs.error.delete", "Не удалось удалить блоб: {error}", error=exc),
            parent=window,
        )


def reload_blobs_data(
    *,
    cleanup_in_progress: bool,
    reload_btn,
    reload_callback,
    log_info,
    log_error,
) -> None:
    if cleanup_in_progress:
        return
    reload_btn.set_loading(True)
    try:
        from blobs.service import reload_blobs

        reload_blobs()
        reload_callback()
        log_info("Блобы перезагружены")
    except Exception as exc:
        log_error(f"Ошибка перезагрузки блобов: {exc}")
    finally:
        reload_btn.set_loading(False)


def open_bin_folder_action(*, tr_fn, info_bar_cls, window, log_error) -> None:
    try:
        from config.config import BIN_FOLDER


        os.startfile(BIN_FOLDER)
    except Exception as exc:
        log_error(f"Ошибка открытия папки: {exc}")
        info_bar_cls.warning(
            title=tr_fn("common.error.title", "Ошибка"),
            content=tr_fn("page.blobs.error.open_folder", "Не удалось открыть папку: {error}", error=exc),
            parent=window,
        )


def open_json_action(*, tr_fn, info_bar_cls, window, log_error) -> None:
    try:
        from config.config import INDEXJSON_FOLDER


        json_path = os.path.join(INDEXJSON_FOLDER, "blobs.json")
        os.startfile(json_path)
    except Exception as exc:
        log_error(f"Ошибка открытия JSON: {exc}")
        info_bar_cls.warning(
            title=tr_fn("common.error.title", "Ошибка"),
            content=tr_fn("page.blobs.error.open_file", "Не удалось открыть файл: {error}", error=exc),
            parent=window,
        )


def apply_blobs_language(
    *,
    tr_fn,
    back_btn,
    desc_label,
    actions_group,
    add_btn,
    reload_btn,
    open_folder_btn,
    open_json_btn,
    filter_edit,
    reload_callback,
) -> None:
    if back_btn is not None:
        back_btn.setText(tr_fn("page.blobs.button.back", "Управление"))
    if desc_label is not None:
        desc_label.setText(
            tr_fn(
                "page.blobs.description",
                "Блобы — это бинарные данные (файлы .bin или hex-значения), используемые в стратегиях для имитации TLS/QUIC пакетов.\nВы можете добавлять свои блобы для кастомных стратегий.",
            )
        )

    try:
        title_label = getattr(getattr(actions_group, "titleLabel", None), "setText", None)
        if title_label is not None:
            actions_group.titleLabel.setText(tr_fn("page.blobs.section.actions", "Действия"))
    except Exception:
        pass

    add_btn.setText(tr_fn("page.blobs.button.add", "Добавить блоб"))
    open_folder_btn.setText(tr_fn("page.blobs.button.bin_folder", "Папка bin"))
    open_json_btn.setText(tr_fn("page.blobs.button.open_json", "Открыть JSON"))
    set_tooltip(
        add_btn,
        tr_fn(
            "page.blobs.action.add.description",
            "Открыть форму создания нового пользовательского блоба для стратегий.",
        ),
    )
    set_tooltip(reload_btn, tr_fn("page.blobs.button.reload", "Обновить список блобов"))
    set_tooltip(
        open_folder_btn,
        tr_fn(
            "page.blobs.action.bin_folder.description",
            "Открыть папку bin с бинарными blob-файлами.",
        ),
    )
    set_tooltip(
        open_json_btn,
        tr_fn(
            "page.blobs.action.open_json.description",
            "Открыть blobs.json с индексом blob-описаний.",
        ),
    )
    filter_edit.setPlaceholderText(tr_fn("page.blobs.filter.placeholder", "Фильтр по имени..."))

    reload_callback()
