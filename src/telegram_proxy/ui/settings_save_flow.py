from __future__ import annotations


# Действия применения настроек, по возрастанию «силы». При слиянии нескольких
# сохранений в одном проходе очереди побеждает более сильное:
#   - restart-семейство ("schedule"/"now") пересоздаёт прокси и применяет ВСЁ,
#     поэтому доминирует над горячей заменой upstream;
#   - немедленное действие доминирует над отложенным (debounced для SpinBox).
_RESTART_PRIORITY = {
    "": 0,
    # Debounced горячая замена upstream (SpinBox порта внешнего прокси).
    "upstream_schedule": 1,
    # Немедленная горячая замена upstream-конфига без рестарта прокси.
    "upstream": 2,
    # Debounced полный рестарт (SpinBox pool_size/buffer_kb).
    "schedule": 3,
    # Немедленный полный рестарт.
    "now": 4,
}


def normalize_restart_request(value: str | None) -> str:
    restart = str(value or "").strip().lower()
    if restart not in _RESTART_PRIORITY:
        return ""
    return restart


def merge_restart_request(current: str | None, requested: str | None) -> str:
    current_restart = normalize_restart_request(current)
    requested_restart = normalize_restart_request(requested)
    if _RESTART_PRIORITY[requested_restart] > _RESTART_PRIORITY[current_restart]:
        return requested_restart
    return current_restart


__all__ = ["merge_restart_request", "normalize_restart_request"]
