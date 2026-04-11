"""Runtime/load workflow helper'ы для страницы Network."""

from __future__ import annotations

import threading


def run_network_runtime_init(
    *,
    runtime_initialized: bool,
    build_page_init_plan_fn,
    mark_initialized_fn,
    schedule_fn,
    start_loading_fn,
) -> None:
    plan = build_page_init_plan_fn(runtime_initialized=runtime_initialized)
    if not plan.should_start_initial_load:
        return
    mark_initialized_fn()
    schedule_fn(plan.load_delay_ms, start_loading_fn)


def start_background_loading(*, load_data_fn) -> None:
    thread = threading.Thread(target=load_data_fn, daemon=True)
    thread.start()


def apply_loaded_page_state(
    *,
    state,
    set_ipv6_available_fn,
    set_force_dns_active_fn,
    set_adapters_fn,
    set_dns_info_fn,
    emit_adapters_loaded_fn,
    emit_dns_info_loaded_fn,
) -> None:
    set_ipv6_available_fn(state.ipv6_available)
    set_force_dns_active_fn(state.force_dns_active)
    set_adapters_fn(state.adapters)
    set_dns_info_fn(state.dns_info)
    emit_adapters_loaded_fn(state.adapters)
    emit_dns_info_loaded_fn(state.dns_info)


def handle_loaded_adapters(
    *,
    adapters,
    current_dns_info,
    ui_built: bool,
    set_adapters_fn,
    build_dynamic_ui_fn,
) -> None:
    set_adapters_fn(adapters)
    if current_dns_info and not ui_built:
        build_dynamic_ui_fn()


def handle_loaded_dns_info(
    *,
    dns_info,
    current_adapters,
    ui_built: bool,
    set_dns_info_fn,
    build_dynamic_ui_fn,
) -> None:
    set_dns_info_fn(dns_info)
    if current_adapters and not ui_built:
        build_dynamic_ui_fn()
