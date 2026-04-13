from __future__ import annotations

from ui.compat_widgets import set_tooltip

from filters.ui.strategy_detail.filter_mode_ui import apply_filter_mode_selector_texts
from filters.ui.strategy_detail.zapret2.common import STRATEGY_TECHNIQUE_FILTERS, refresh_strategy_filter_combo


def apply_strategy_detail_page_language(page) -> None:
    if not getattr(page, "_content_built", False):
        return

    if getattr(page, "_breadcrumb", None) is not None:
        page._breadcrumb.blockSignals(True)
        try:
            page._breadcrumb.clear()
            page._breadcrumb.addItem("control", page._tr("page.z2_strategy_detail.breadcrumb.control", "Управление"))
            page._breadcrumb.addItem(
                "strategies", page._tr("page.z2_strategy_detail.breadcrumb.strategies", "Стратегии DPI")
            )
            detail = ""
            try:
                detail = page._target_info.full_name if page._target_info else ""
            except Exception:
                detail = ""
            page._breadcrumb.addItem(
                "detail",
                detail or page._tr("page.z2_strategy_detail.header.category_fallback", "Target"),
            )
        finally:
            page._breadcrumb.blockSignals(False)

    if getattr(page, "_parent_link", None) is not None:
        page._parent_link.setText(page._tr("page.z2_strategy_detail.back.strategies", "Стратегии DPI"))

    if getattr(page, "_title", None) is not None:
        target_title = ""
        protocol = ""
        ports = ""
        try:
            if page._target_info:
                target_title = str(getattr(page._target_info, "full_name", "") or "").strip()
                protocol = str(getattr(page._target_info, "protocol", "") or "").strip()
                ports = str(getattr(page._target_info, "ports", "") or "").strip()
        except Exception:
            pass
        page._title.setText(target_title or page._tr("page.z2_strategy_detail.header.select_category", "Выберите target"))
        if getattr(page, "_subtitle", None) is not None:
            if protocol:
                page._subtitle.setText(
                    f"{protocol}  |  "
                    f"{page._tr('page.z2_strategy_detail.subtitle.ports', 'порты: {ports}', ports=ports)}"
                )
            else:
                page._subtitle.setText("")

    if getattr(page, "_filter_mode_frame", None) is not None:
        page._filter_mode_frame.set_title(
            page._tr("page.z2_strategy_detail.filter_mode.title", "Режим фильтрации")
        )
        page._filter_mode_frame.set_description(
            page._tr("page.z2_strategy_detail.filter_mode.description", "Hostlist - по доменам, IPset - по IP")
        )
    if getattr(page, "_filter_mode_selector", None) is not None:
        apply_filter_mode_selector_texts(
            page._filter_mode_selector,
            ipset_text=page._tr("page.z2_strategy_detail.filter.ipset", "IPset"),
            hostlist_text=page._tr("page.z2_strategy_detail.filter.hostlist", "Hostlist"),
        )

    if getattr(page, "_out_range_mode_label", None) is not None:
        page._out_range_mode_label.setText(page._tr("page.z2_strategy_detail.out_range.mode", "Режим:"))
    if getattr(page, "_out_range_value_label", None) is not None:
        page._out_range_value_label.setText(page._tr("page.z2_strategy_detail.out_range.value", "Значение:"))
    if getattr(page, "_out_range_frame", None) is not None:
        page._out_range_frame.set_title(page._tr("page.z2_strategy_detail.out_range.title", "Out Range"))
        page._out_range_frame.set_description(
            page._tr("page.z2_strategy_detail.out_range.description", "Ограничение исходящих пакетов")
        )
    if getattr(page, "_out_range_seg", None) is not None:
        set_tooltip(
            page._out_range_seg,
            page._tr(
                "page.z2_strategy_detail.out_range.mode.tooltip",
                "n = количество пакетов с самого первого, d = отсчитывать ТОЛЬКО количество пакетов с данными",
            ),
        )
    if getattr(page, "_out_range_spin", None) is not None:
        set_tooltip(
            page._out_range_spin,
            page._tr(
                "page.z2_strategy_detail.out_range.value.tooltip",
                "--out-range: ограничение количества исходящих пакетов (n) или задержки (d)",
            ),
        )

    if getattr(page, "_search_input", None) is not None:
        page._search_input.setPlaceholderText(
            page._tr("page.z2_strategy_detail.search.placeholder", "Поиск по имени или args...")
        )

    if getattr(page, "_strategies_title_label", None) is not None:
        page._strategies_title_label.setText(
            page._tr("page.z2_strategy_detail.tree.title", "Все стратегии")
        )

    if getattr(page, "_sort_btn", None) is not None:
        page._update_sort_button_ui()

    if getattr(page, "_sort_combo", None) is not None:
        page._populate_sort_combo()

    if getattr(page, "_filter_combo", None) is not None:
        idx = page._filter_combo.currentIndex()
        refresh_strategy_filter_combo(
            page._filter_combo,
            page._tr,
            current_index=idx,
            technique_filters=STRATEGY_TECHNIQUE_FILTERS,
        )

    if getattr(page, "_edit_args_btn", None) is not None:
        set_tooltip(
            page._edit_args_btn,
            page._tr(
                "page.z2_strategy_detail.args.tooltip",
                "Аргументы стратегии для выбранного target'а",
            ),
        )
    page._update_strategies_summary()

    if getattr(page, "_send_toggle_row", None) is not None:
        page._send_toggle_row.set_texts(
            page._tr("page.z2_strategy_detail.send.toggle.title", "Send параметры"),
            page._tr("page.z2_strategy_detail.send.toggle.description", "Отправка копий пакетов"),
        )
    if getattr(page, "_send_repeats_row", None) is not None:
        page._send_repeats_row.set_texts(
            page._tr("page.z2_strategy_detail.send.repeats.title", "repeats"),
            page._tr("page.z2_strategy_detail.send.repeats.description", "Количество повторных отправок"),
        )
    if getattr(page, "_send_ip_ttl_frame", None) is not None:
        page._send_ip_ttl_frame.set_title(page._tr("page.z2_strategy_detail.send.ip_ttl.title", "ip_ttl"))
        page._send_ip_ttl_frame.set_description(
            page._tr("page.z2_strategy_detail.send.ip_ttl.description", "TTL для IPv4 отправляемых пакетов")
        )
    if getattr(page, "_send_ip6_ttl_frame", None) is not None:
        page._send_ip6_ttl_frame.set_title(page._tr("page.z2_strategy_detail.send.ip6_ttl.title", "ip6_ttl"))
        page._send_ip6_ttl_frame.set_description(
            page._tr("page.z2_strategy_detail.send.ip6_ttl.description", "TTL для IPv6 отправляемых пакетов")
        )
    if getattr(page, "_send_ip_id_row", None) is not None:
        page._send_ip_id_row.set_texts(
            page._tr("page.z2_strategy_detail.send.ip_id.title", "ip_id"),
            page._tr("page.z2_strategy_detail.send.ip_id.description", "Режим IP ID для отправляемых пакетов"),
        )
    if getattr(page, "_send_badsum_frame", None) is not None:
        page._send_badsum_frame.set_title(page._tr("page.z2_strategy_detail.send.badsum.title", "badsum"))
        page._send_badsum_frame.set_description(
            page._tr(
                "page.z2_strategy_detail.send.badsum.description",
                "Отправлять пакеты с неправильной контрольной суммой",
            )
        )

    if getattr(page, "_syndata_toggle_row", None) is not None:
        page._syndata_toggle_row.set_texts(
            page._tr("page.z2_strategy_detail.syndata.toggle.title", "Syndata параметры"),
            page._tr(
                "page.z2_strategy_detail.syndata.toggle.description",
                "Дополнительные параметры обхода DPI",
            ),
        )
    if getattr(page, "_blob_row", None) is not None:
        page._blob_row.set_texts(
            page._tr("page.z2_strategy_detail.syndata.blob.title", "blob"),
            page._tr("page.z2_strategy_detail.syndata.blob.description", "Полезная нагрузка пакета"),
        )
    if getattr(page, "_tls_mod_row", None) is not None:
        page._tls_mod_row.set_texts(
            page._tr("page.z2_strategy_detail.syndata.tls_mod.title", "tls_mod"),
            page._tr("page.z2_strategy_detail.syndata.tls_mod.description", "Модификация полезной нагрузки TLS"),
        )
    if getattr(page, "_autottl_delta_frame", None) is not None:
        page._autottl_delta_frame.set_title(
            page._tr("page.z2_strategy_detail.syndata.autottl_delta.title", "AutoTTL Delta")
        )
        page._autottl_delta_frame.set_description(
            page._tr(
                "page.z2_strategy_detail.syndata.autottl_delta.description",
                "Смещение от измеренного TTL (OFF = убрать ip_autottl)",
            )
        )
    if getattr(page, "_autottl_min_frame", None) is not None:
        page._autottl_min_frame.set_title(
            page._tr("page.z2_strategy_detail.syndata.autottl_min.title", "AutoTTL Min")
        )
        page._autottl_min_frame.set_description(
            page._tr("page.z2_strategy_detail.syndata.autottl_min.description", "Минимальный TTL")
        )
    if getattr(page, "_autottl_max_frame", None) is not None:
        page._autottl_max_frame.set_title(
            page._tr("page.z2_strategy_detail.syndata.autottl_max.title", "AutoTTL Max")
        )
        page._autottl_max_frame.set_description(
            page._tr("page.z2_strategy_detail.syndata.autottl_max.description", "Максимальный TTL")
        )
    if getattr(page, "_tcp_flags_row", None) is not None:
        page._tcp_flags_row.set_texts(
            page._tr("page.z2_strategy_detail.syndata.tcp_flags.title", "tcp_flags_unset"),
            page._tr("page.z2_strategy_detail.syndata.tcp_flags.description", "Сбросить TCP флаги"),
        )

    if getattr(page, "_create_preset_btn", None) is not None:
        page._create_preset_btn.setText(
            page._tr("page.z2_strategy_detail.button.create_preset", "Создать пресет")
        )
        set_tooltip(
            page._create_preset_btn,
            page._tr(
                "page.z2_strategy_detail.button.create_preset.tooltip",
                "Создать новый пресет на основе текущих настроек",
            ),
        )
    if getattr(page, "_rename_preset_btn", None) is not None:
        page._rename_preset_btn.setText(
            page._tr("page.z2_strategy_detail.button.rename_preset", "Переименовать")
        )
        set_tooltip(
            page._rename_preset_btn,
            page._tr(
                "page.z2_strategy_detail.button.rename_preset.tooltip",
                "Переименовать текущий активный пресет",
            ),
        )
    if getattr(page, "_reset_settings_btn", None) is not None:
        page._reset_settings_btn.setText(
            page._tr("page.z2_strategy_detail.button.reset_settings", "Сбросить настройки")
        )

    updater = getattr(page, "_update_header_labels", None)
    if callable(updater):
        try:
            updater()
        except Exception:
            pass
