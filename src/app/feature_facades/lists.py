from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class ListsFeature:
    startup_lists_check: Callable
    open_lists_folder_action: Callable
    rebuild_hostlists_action: Callable
    load_hostlist_folder_info: Callable
    load_ipset_folder_info: Callable
    load_custom_domains_text: Callable
    save_custom_domains_text: Callable
    build_custom_domains_status_plan: Callable
    build_add_custom_domain_plan: Callable
    open_domains_user_file_action: Callable
    reset_domains_file_action: Callable
    reset_domains_file: Callable
    open_domains_user_file: Callable
    load_custom_ipset_text: Callable
    save_custom_ipset_text: Callable
    build_custom_ipset_status_plan: Callable
    build_add_custom_ipset_plan: Callable
    open_ipset_all_user_file_action: Callable
    open_ipset_all_user_file: Callable
    load_custom_netrogat_text: Callable
    save_custom_netrogat_text: Callable
    build_custom_netrogat_status_plan: Callable
    build_add_custom_netrogat_plan: Callable
    open_netrogat_user_file_action: Callable
    open_netrogat_final_file_action: Callable
    open_netrogat_user_file: Callable
    open_netrogat_final_file: Callable
    add_missing_netrogat_defaults_action: Callable
    add_missing_netrogat_defaults: Callable
    load_custom_ipru_text: Callable
    save_custom_ipru_text: Callable
    build_custom_ipru_status_plan: Callable
    build_add_custom_ipru_plan: Callable
    open_ipset_ru_user_file_action: Callable
    open_ipset_ru_final_file_action: Callable


def build_lists_feature() -> ListsFeature:
    from lists import public as lists_public

    return ListsFeature(
        startup_lists_check=lists_public.startup_lists_check,
        open_lists_folder_action=lists_public.open_lists_folder_action,
        rebuild_hostlists_action=lists_public.rebuild_hostlists_action,
        load_hostlist_folder_info=lists_public.load_hostlist_folder_info,
        load_ipset_folder_info=lists_public.load_ipset_folder_info,
        load_custom_domains_text=lists_public.load_custom_domains_text,
        save_custom_domains_text=lists_public.save_custom_domains_text,
        build_custom_domains_status_plan=lists_public.build_custom_domains_status_plan,
        build_add_custom_domain_plan=lists_public.build_add_custom_domain_plan,
        open_domains_user_file_action=lists_public.open_domains_user_file_action,
        reset_domains_file_action=lists_public.reset_domains_file_action,
        reset_domains_file=lists_public.reset_domains_file,
        open_domains_user_file=lists_public.open_domains_user_file,
        load_custom_ipset_text=lists_public.load_custom_ipset_text,
        save_custom_ipset_text=lists_public.save_custom_ipset_text,
        build_custom_ipset_status_plan=lists_public.build_custom_ipset_status_plan,
        build_add_custom_ipset_plan=lists_public.build_add_custom_ipset_plan,
        open_ipset_all_user_file_action=lists_public.open_ipset_all_user_file_action,
        open_ipset_all_user_file=lists_public.open_ipset_all_user_file,
        load_custom_netrogat_text=lists_public.load_custom_netrogat_text,
        save_custom_netrogat_text=lists_public.save_custom_netrogat_text,
        build_custom_netrogat_status_plan=lists_public.build_custom_netrogat_status_plan,
        build_add_custom_netrogat_plan=lists_public.build_add_custom_netrogat_plan,
        open_netrogat_user_file_action=lists_public.open_netrogat_user_file_action,
        open_netrogat_final_file_action=lists_public.open_netrogat_final_file_action,
        open_netrogat_user_file=lists_public.open_netrogat_user_file,
        open_netrogat_final_file=lists_public.open_netrogat_final_file,
        add_missing_netrogat_defaults_action=lists_public.add_missing_netrogat_defaults_action,
        add_missing_netrogat_defaults=lists_public.add_missing_netrogat_defaults,
        load_custom_ipru_text=lists_public.load_custom_ipru_text,
        save_custom_ipru_text=lists_public.save_custom_ipru_text,
        build_custom_ipru_status_plan=lists_public.build_custom_ipru_status_plan,
        build_add_custom_ipru_plan=lists_public.build_add_custom_ipru_plan,
        open_ipset_ru_user_file_action=lists_public.open_ipset_ru_user_file_action,
        open_ipset_ru_final_file_action=lists_public.open_ipset_ru_final_file_action,
    )
