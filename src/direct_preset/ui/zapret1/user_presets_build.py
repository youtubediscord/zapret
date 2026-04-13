"""Build-helper'ы для страницы пользовательских пресетов Zapret 1."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QListView, QSizePolicy

from ui.compat_widgets import PrimaryActionButton, SettingsCard, set_tooltip
from ui.presets_menu.delegate import PresetListDelegate
from ui.presets_menu.model import PresetListModel
from ui.presets_menu.toolbar import PresetsToolbarLayout
from ui.presets_menu.view import LinkedWheelListView


@dataclass(slots=True)
class UserPresetsPageBuildWidgets:
    configs_card: object
    configs_icon: object
    configs_title_label: object
    get_configs_btn: object
    toolbar_layout: object
    create_btn: object
    import_btn: object
    open_folder_btn: object
    reset_all_btn: object
    presets_info_btn: object
    info_btn: object
    preset_search_input: object
    presets_list: object
    presets_model: object
    presets_delegate: object


def build_user_presets_page_shell(
    *,
    parent,
    tr_fn,
    tokens,
    strong_body_label_cls,
    line_edit_cls,
    primary_tool_button_cls,
    fluent_icon,
    get_cached_qta_pixmap_fn,
    on_open_new_configs_post,
    on_create_clicked,
    on_import_clicked,
    on_open_folder_clicked,
    on_reset_all_presets_clicked,
    on_open_presets_info,
    on_info_clicked,
    on_preset_search_text_changed,
    on_activate_preset,
    on_move_preset_by_step,
    on_item_dropped,
    on_preset_context_requested,
    on_preset_list_action,
    ui_language: str,
):
    configs_card = SettingsCard()
    configs_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    configs_layout = QHBoxLayout()
    configs_layout.setSpacing(12)

    configs_icon = QLabel()
    configs_icon.setPixmap(get_cached_qta_pixmap_fn("fa5b.github", color=tokens.accent_hex, size=18))
    configs_layout.addWidget(configs_icon)

    configs_title_label = strong_body_label_cls(
        tr_fn(
            "page.z1_user_presets.configs.title",
            "Обменивайтесь пресетами и категориями в разделе GitHub Discussions",
        )
    )
    configs_title_label.setWordWrap(True)
    configs_title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    configs_title_label.setMinimumWidth(0)
    configs_layout.addWidget(configs_title_label, 1)

    get_configs_btn = PrimaryActionButton(
        tr_fn("page.z1_user_presets.configs.button", "Получить конфиги"),
        "fa5s.external-link-alt",
    )
    get_configs_btn.setFixedHeight(36)
    get_configs_btn.clicked.connect(on_open_new_configs_post)
    configs_layout.addWidget(get_configs_btn)
    configs_card.add_layout(configs_layout)

    toolbar_layout = PresetsToolbarLayout(parent)
    create_btn = toolbar_layout.create_primary_tool_button(
        primary_tool_button_cls,
        fluent_icon.ADD if fluent_icon else None,
    )
    set_tooltip(create_btn, tr_fn("page.z1_user_presets.tooltip.create", "Создать новый пресет"))
    create_btn.clicked.connect(on_create_clicked)

    import_btn = toolbar_layout.create_action_button(
        tr_fn("page.z1_user_presets.button.import", "Импорт"),
        "fa5s.file-import",
    )
    set_tooltip(import_btn, tr_fn("page.z1_user_presets.tooltip.import", "Импорт пресета из файла"))
    import_btn.clicked.connect(on_import_clicked)

    open_folder_btn = toolbar_layout.create_action_button(
        tr_fn("page.z1_user_presets.button.open_folder", "Открыть папку"),
        "fa5s.folder-open",
    )
    set_tooltip(
        open_folder_btn,
        tr_fn("page.z1_user_presets.tooltip.open_folder", "Открыть папку, где лежат ваши пресеты"),
    )
    open_folder_btn.clicked.connect(on_open_folder_clicked)

    reset_all_btn = toolbar_layout.create_action_button(
        tr_fn("page.z1_user_presets.button.reset_all", "Вернуть заводские"),
        "fa5s.undo",
    )
    set_tooltip(
        reset_all_btn,
        tr_fn(
            "page.z1_user_presets.tooltip.reset_all",
            "Восстанавливает стандартные пресеты. Ваши изменения в стандартных пресетах будут потеряны.",
        ),
    )
    reset_all_btn.clicked.connect(on_reset_all_presets_clicked)

    presets_info_btn = toolbar_layout.create_action_button(
        tr_fn("page.z1_user_presets.button.wiki", "Вики по пресетам"),
        "fa5s.info-circle",
    )
    presets_info_btn.clicked.connect(on_open_presets_info)

    info_btn = toolbar_layout.create_action_button(
        tr_fn("page.z1_user_presets.button.what_is_this", "Что это такое?"),
        "fa5s.question-circle",
    )
    info_btn.clicked.connect(on_info_clicked)

    toolbar_layout.set_buttons([
        create_btn,
        import_btn,
        open_folder_btn,
        reset_all_btn,
        presets_info_btn,
        info_btn,
    ])
    toolbar_layout.refresh_for_viewport(parent.viewport().width(), parent.layout.contentsMargins())

    preset_search_input = line_edit_cls()
    preset_search_input.setPlaceholderText(
        tr_fn("page.z1_user_presets.search.placeholder", "Поиск пресетов по имени...")
    )
    preset_search_input.setClearButtonEnabled(True)
    preset_search_input.setFixedHeight(34)
    preset_search_input.setProperty("noDrag", True)
    preset_search_input.textChanged.connect(on_preset_search_text_changed)

    presets_list = LinkedWheelListView(parent, draggable_kinds={"preset", "folder"})
    presets_list.setObjectName("userPresetsList")
    presets_list.setMouseTracking(True)
    presets_list.setSelectionMode(QListView.SelectionMode.SingleSelection)
    presets_list.setEditTriggers(QListView.EditTrigger.NoEditTriggers)
    presets_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    presets_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    presets_list.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
    presets_list.setUniformItemSizes(False)
    presets_list.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    presets_list.setProperty("uiList", True)
    presets_list.setProperty("noDrag", True)
    presets_list.viewport().setProperty("noDrag", True)
    presets_list.preset_activated.connect(on_activate_preset)
    presets_list.preset_move_requested.connect(on_move_preset_by_step)
    presets_list.item_dropped.connect(on_item_dropped)
    presets_list.preset_context_requested.connect(on_preset_context_requested)
    presets_list.setDragEnabled(True)
    presets_list.setAcceptDrops(True)
    presets_list.setDropIndicatorShown(True)
    presets_list.setDefaultDropAction(Qt.DropAction.MoveAction)
    presets_list.setDragDropMode(QListView.DragDropMode.DragDrop)

    presets_model = PresetListModel(presets_list)
    presets_delegate = PresetListDelegate(presets_list, language_scope="z1", help_name_role="file_name")
    presets_delegate.set_ui_language(ui_language)
    presets_delegate.action_triggered.connect(on_preset_list_action)
    presets_list.setModel(presets_model)
    presets_list.setItemDelegate(presets_delegate)
    presets_list.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    presets_list.setFrameShape(QFrame.Shape.NoFrame)
    presets_list.verticalScrollBar().setSingleStep(28)

    return UserPresetsPageBuildWidgets(
        configs_card=configs_card,
        configs_icon=configs_icon,
        configs_title_label=configs_title_label,
        get_configs_btn=get_configs_btn,
        toolbar_layout=toolbar_layout,
        create_btn=create_btn,
        import_btn=import_btn,
        open_folder_btn=open_folder_btn,
        reset_all_btn=reset_all_btn,
        presets_info_btn=presets_info_btn,
        info_btn=info_btn,
        preset_search_input=preset_search_input,
        presets_list=presets_list,
        presets_model=presets_model,
        presets_delegate=presets_delegate,
    )
