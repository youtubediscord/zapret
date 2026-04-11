from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ServerStatusRowEntry:
    server_name: str
    row: int
    status: dict


@dataclass(slots=True)
class ServerStatusUpsertResult:
    row: int
    status: dict
    created: bool


class ServerStatusTableState:
    """Минимальный runtime-state для таблицы статусов серверов.

    Страница больше не должна вручную синхронизировать два разрозненных словаря:
    один для row index, другой для status payload. Этот helper хранит оба слоя
    рядом и возвращает уже готовые результаты для рендера.
    """

    def __init__(self) -> None:
        self._status_by_server: dict[str, dict] = {}
        self._row_by_server: dict[str, int] = {}

    def reset(self) -> None:
        self._status_by_server.clear()
        self._row_by_server.clear()

    def upsert(self, server_name: str, status: dict, *, next_row: int) -> ServerStatusUpsertResult:
        row = self._row_by_server.get(server_name)
        created = row is None
        if created:
            row = int(next_row)
            self._row_by_server[server_name] = row

        prepared_status = dict(status or {})
        self._status_by_server[server_name] = prepared_status
        return ServerStatusUpsertResult(
            row=row,
            status=prepared_status,
            created=created,
        )

    def iter_entries(self) -> list[ServerStatusRowEntry]:
        entries: list[ServerStatusRowEntry] = []
        for server_name, row in self._row_by_server.items():
            status = self._status_by_server.get(server_name)
            if not status:
                continue
            entries.append(
                ServerStatusRowEntry(
                    server_name=server_name,
                    row=row,
                    status=dict(status),
                )
            )
        return entries
