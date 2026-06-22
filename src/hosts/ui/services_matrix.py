"""Табличная матрица выбора DNS-профилей для Hosts page."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, QRect, QSize, Qt
from PyQt6.QtGui import QColor, QFontMetrics, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QWidget,
)

from ui.accessibility import set_control_accessibility, set_state_text
from ui.fluent_widgets import SettingsCard
from ui.theme import get_cached_qta_pixmap, get_theme_tokens, to_qcolor


@dataclass(slots=True)
class HostsServicesMatrixWidgets:
    card: SettingsCard
    view: "HostsServicesMatrixCanvas"
    model: "HostsServicesMatrixModel"


class HostsServicesMatrixModel(QAbstractTableModel):
    """Одна модель для всех DNS-сервисов вместо отдельных ComboBox."""

    KindRole = Qt.ItemDataRole.UserRole + 1
    ServiceNameRole = Qt.ItemDataRole.UserRole + 2
    ProfileNameRole = Qt.ItemDataRole.UserRole + 3
    AvailableRole = Qt.ItemDataRole.UserRole + 4
    SelectedRole = Qt.ItemDataRole.UserRole + 5
    IconNameRole = Qt.ItemDataRole.UserRole + 6
    IconColorRole = Qt.ItemDataRole.UserRole + 7

    def __init__(self, groups, *, off_label: str, parent=None):
        super().__init__(parent)
        self._off_label = str(off_label or "Откл.")
        self._profiles: list[tuple[str | None, str]] = [(None, self._off_label)]
        self._rows: list[dict[str, object]] = []
        self._selected_by_service: dict[str, str | None] = {}
        self._build(groups)

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return 1 + len(self._profiles)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        kind = str(row.get("kind") or "")
        column = int(index.column())

        if role == self.KindRole:
            return kind

        if kind == "group":
            title = str(row.get("title") or "")
            count = int(row.get("count") or 0)
            if role == Qt.ItemDataRole.DisplayRole and column == 0:
                return f"{title}   {count}"
            if role == Qt.ItemDataRole.AccessibleTextRole:
                return f"Группа hosts: {title}, сервисов: {count}"
            if role == Qt.ItemDataRole.TextAlignmentRole:
                return Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
            if role == Qt.ItemDataRole.ForegroundRole:
                return QColor(get_theme_tokens().fg)
            return None

        row_plan = row.get("row_plan")
        if row_plan is None:
            return None
        service_name = str(getattr(row_plan, "service_name", "") or "")
        if role == self.ServiceNameRole:
            return service_name
        if role == self.IconNameRole:
            return str(getattr(row_plan, "icon_name", "") or "")
        if role == self.IconColorRole:
            return getattr(row_plan, "icon_color", None)

        if column == 0:
            if role == Qt.ItemDataRole.DisplayRole:
                return service_name
            if role == Qt.ItemDataRole.AccessibleTextRole:
                return f"Сервис hosts: {service_name}"
            if role == Qt.ItemDataRole.TextAlignmentRole:
                return Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
            if role == Qt.ItemDataRole.ForegroundRole:
                return QColor(get_theme_tokens().fg)
            return None

        profile_name, label = self._profile_for_column(column)
        available = self.is_profile_available(index.row(), column)
        selected = self._selected_by_service.get(service_name) == profile_name

        if role == self.ProfileNameRole:
            return profile_name
        if role == self.AvailableRole:
            return available
        if role == self.SelectedRole:
            return selected
        if role == Qt.ItemDataRole.DisplayRole:
            if not available:
                return ""
            return "●" if selected else "○"
        if role == Qt.ItemDataRole.AccessibleTextRole:
            state = "выбран" if selected else "доступен" if available else "недоступен"
            return f"{service_name}: {label}, {state}"
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignCenter
        if role == Qt.ItemDataRole.ForegroundRole:
            tokens = get_theme_tokens()
            if not available:
                return QColor(tokens.fg_faint)
            return QColor(tokens.accent_hex if selected else tokens.fg_muted)
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if orientation != Qt.Orientation.Horizontal:
            return None
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if int(section) == 0:
            return "Сервис"
        _profile_name, label = self._profile_for_column(int(section))
        return label

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        base = Qt.ItemFlag.ItemIsEnabled
        if self.is_group_row(index.row()):
            return base
        if index.column() > 0 and self.is_profile_available(index.row(), index.column()):
            return base | Qt.ItemFlag.ItemIsSelectable
        return base

    def is_group_row(self, row: int) -> bool:
        if row < 0 or row >= len(self._rows):
            return False
        return str(self._rows[row].get("kind") or "") == "group"

    def service_for_row(self, row: int) -> str:
        if row < 0 or row >= len(self._rows):
            return ""
        row_plan = self._rows[row].get("row_plan")
        return str(getattr(row_plan, "service_name", "") or "")

    def profile_for_column(self, column: int) -> str | None:
        return self._profile_for_column(column)[0]

    def service_names_for_profile(self, profile_name: str | None) -> list[str]:
        result: list[str] = []
        column = self._column_for_profile(profile_name)
        if column < 0:
            return result
        for row in range(self.rowCount()):
            if self.is_profile_available(row, column):
                service_name = self.service_for_row(row)
                if service_name:
                    result.append(service_name)
        return result

    def selected_profile_for_service(self, service_name: str) -> str | None:
        return self._selected_by_service.get(str(service_name or ""))

    def set_selected_profile_for_service(self, service_name: str, profile_name: str | None) -> None:
        service_name = str(service_name or "")
        if not service_name:
            return
        self._selected_by_service[service_name] = profile_name
        row = self._row_for_service(service_name)
        if row >= 0:
            self.dataChanged.emit(self.index(row, 1), self.index(row, max(1, self.columnCount() - 1)))

    def update_selection(self, selection: dict[str, str]) -> None:
        normalized = {
            str(service_name): str(profile_name)
            for service_name, profile_name in dict(selection or {}).items()
            if str(service_name or "").strip() and str(profile_name or "").strip()
        }
        changed_rows: list[int] = []
        for row_idx, row in enumerate(self._rows):
            if str(row.get("kind") or "") != "service":
                continue
            row_plan = row.get("row_plan")
            service_name = str(getattr(row_plan, "service_name", "") or "")
            selected = normalized.get(service_name)
            if selected not in (getattr(row_plan, "available_profiles", []) or []):
                selected = None
            if self._selected_by_service.get(service_name) != selected:
                self._selected_by_service[service_name] = selected
                changed_rows.append(row_idx)
        for row in changed_rows:
            self.dataChanged.emit(self.index(row, 1), self.index(row, max(1, self.columnCount() - 1)))

    def is_profile_available(self, row: int, column: int) -> bool:
        if row < 0 or row >= len(self._rows) or column <= 0:
            return False
        item = self._rows[row]
        if str(item.get("kind") or "") != "service":
            return False
        profile_name = self.profile_for_column(column)
        if profile_name is None:
            return True
        row_plan = item.get("row_plan")
        return profile_name in (getattr(row_plan, "available_profiles", []) or [])

    def _build(self, groups) -> None:
        profile_names: list[str] = []
        profile_labels: dict[str, str] = {}
        for group in groups or ():
            for profile_name, label in getattr(group, "common_profiles", []) or ():
                _append_profile(profile_names, profile_labels, profile_name, label)
            for row_plan in getattr(group, "rows", []) or ():
                for profile_name, label in getattr(row_plan, "profile_items", []) or ():
                    _append_profile(profile_names, profile_labels, profile_name, label)

        self._profiles.extend((name, profile_labels.get(name) or name) for name in profile_names)

        for group in groups or ():
            rows = list(getattr(group, "rows", []) or [])
            if not rows:
                continue
            self._rows.append(
                {
                    "kind": "group",
                    "title": str(getattr(group, "title", "") or ""),
                    "count": len(rows),
                }
            )
            for row_plan in rows:
                service_name = str(getattr(row_plan, "service_name", "") or "")
                selected = getattr(row_plan, "selected_profile", None)
                if selected not in (getattr(row_plan, "available_profiles", []) or []):
                    selected = None
                self._selected_by_service[service_name] = selected
                self._rows.append({"kind": "service", "row_plan": row_plan})

    def _profile_for_column(self, column: int) -> tuple[str | None, str]:
        index = int(column) - 1
        if index < 0 or index >= len(self._profiles):
            return None, ""
        return self._profiles[index]

    def _column_for_profile(self, profile_name: str | None) -> int:
        for index, (candidate, _label) in enumerate(self._profiles, start=1):
            if candidate == profile_name:
                return index
        return -1

    def _row_for_service(self, service_name: str) -> int:
        for row_idx, row in enumerate(self._rows):
            row_plan = row.get("row_plan")
            if str(getattr(row_plan, "service_name", "") or "") == service_name:
                return row_idx
        return -1


class HostsServicesMatrixDelegate(QStyledItemDelegate):
    """Лёгкая отрисовка матрицы: иконка, текст и точка без QSS per-cell."""

    _ICON_SIZE = 18
    _DOT_SIZE = 8
    _SELECTED_DOT_SIZE = 9
    _DOT_PIXMAP_SIZE = 14
    _ROW_HEIGHT = 38
    _GROUP_HEIGHT = 30

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dot_pixmap_cache: dict[tuple[bool, bool, str, str, int], QPixmap] = {}

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        _ = option
        height = self._GROUP_HEIGHT if self._is_group(index) else self._ROW_HEIGHT
        return QSize(0, height)

    def dot_colors(self, *, selected: bool, available: bool) -> tuple[QColor, QColor]:
        tokens = get_theme_tokens()
        if not available:
            faint = to_qcolor(tokens.fg_faint, "rgba(255, 255, 255, 0.28)")
            return faint, QColor(0, 0, 0, 0)
        if selected:
            accent = to_qcolor(tokens.accent_hex, "#45ead9")
            return accent, accent
        if tokens.is_light:
            outline = QColor(0, 0, 0, 118)
        else:
            outline = QColor(236, 241, 248, 190)
        return outline, QColor(0, 0, 0, 0)

    def dot_pixmap(self, *, selected: bool, available: bool) -> QPixmap:
        outline, fill = self.dot_colors(selected=selected, available=available)
        size = self._SELECTED_DOT_SIZE if selected else self._DOT_SIZE
        key = (
            bool(selected),
            bool(available),
            outline.name(QColor.NameFormat.HexArgb),
            fill.name(QColor.NameFormat.HexArgb),
            int(size),
        )
        cached = self._dot_pixmap_cache.get(key)
        if cached is not None:
            return cached

        pixmap = QPixmap(self._DOT_PIXMAP_SIZE, self._DOT_PIXMAP_SIZE)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRect(0, 0, size, size)
        rect.moveCenter(pixmap.rect().center())
        painter.setPen(QPen(outline, 1.4))
        painter.setBrush(fill)
        painter.drawEllipse(rect)
        painter.end()
        self._dot_pixmap_cache[key] = pixmap
        return pixmap

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        painter.save()
        tokens = get_theme_tokens()

        if self._is_group(index):
            self._paint_group(painter, option, index, tokens)
        elif int(index.column()) == 0:
            self._paint_service(painter, option, index, tokens)
        else:
            self._paint_dot(painter, option, index)

        painter.restore()

    def _paint_group(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex, tokens) -> None:
        if int(index.column()) != 0:
            return
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        if not text:
            return
        font = painter.font()
        font.setBold(True)
        font.setPointSize(max(8, font.pointSize() - 1))
        painter.setFont(font)
        rect = option.rect.adjusted(12, 0, -8, 0)
        painter.setPen(to_qcolor(tokens.fg_muted, "#d7dde7"))
        painter.drawText(rect, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), text)

    def _paint_service(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex, tokens) -> None:
        rect = option.rect.adjusted(12, 0, -8, 0)
        center_y = rect.center().y()
        icon_name = str(index.data(HostsServicesMatrixModel.IconNameRole) or "fa5s.globe")
        icon_color = index.data(HostsServicesMatrixModel.IconColorRole) or tokens.icon_fg_faint
        icon_rect = QRect(rect.left(), center_y - self._ICON_SIZE // 2, self._ICON_SIZE, self._ICON_SIZE)
        pixmap = get_cached_qta_pixmap(icon_name, color=icon_color, size=self._ICON_SIZE)
        if not pixmap.isNull():
            painter.drawPixmap(icon_rect, pixmap)
        else:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(to_qcolor(icon_color, tokens.icon_fg_faint))
            painter.drawEllipse(icon_rect.adjusted(3, 3, -3, -3))

        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        text_rect = QRect(icon_rect.right() + 10, rect.top(), max(0, rect.right() - icon_rect.right() - 10), rect.height())
        metrics = QFontMetrics(painter.font())
        painter.setPen(to_qcolor(tokens.fg, "#f5f5f5"))
        painter.drawText(
            text_rect,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            metrics.elidedText(text, Qt.TextElideMode.ElideRight, text_rect.width()),
        )

    def _paint_dot(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        available = bool(index.data(HostsServicesMatrixModel.AvailableRole))
        if not available:
            return
        selected = bool(index.data(HostsServicesMatrixModel.SelectedRole))
        pixmap = self.dot_pixmap(selected=selected, available=available)
        top_left = option.rect.center() - pixmap.rect().center()
        painter.drawPixmap(top_left, pixmap)

    def _is_group(self, index: QModelIndex) -> bool:
        return str(index.data(HostsServicesMatrixModel.KindRole) or "") == "group"


class HostsServicesMatrixCanvas(QWidget):
    """Лёгкая матрица без QTableView: рисует только видимую часть."""

    _HEADER_HEIGHT = 38
    _SERVICE_COLUMN_MIN_WIDTH = 260
    _PROFILE_COLUMN_WIDTH = 88
    _ICON_SIZE = 18
    _SERVICE_LEFT_PADDING = 12

    def __init__(self, model: HostsServicesMatrixModel, *, on_profile_selected, on_bulk_profile_selected, parent=None):
        super().__init__(parent)
        self._model = model
        self._delegate = HostsServicesMatrixDelegate(self)
        self._on_profile_selected = on_profile_selected
        self._on_bulk_profile_selected = on_bulk_profile_selected
        self._row_tops: list[int] = []
        self._row_heights: list[int] = []
        self._total_height = self._HEADER_HEIGHT
        self.setObjectName("hostsServicesMatrix")
        self.setMouseTracking(False)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_StaticContents, True)
        self._rebuild_geometry_cache()
        self._model.dataChanged.connect(self._on_model_data_changed)

    def delegate(self) -> HostsServicesMatrixDelegate:
        return self._delegate

    def model(self) -> HostsServicesMatrixModel:
        return self._model

    def profile_column_width(self) -> int:
        return self._PROFILE_COLUMN_WIDTH

    def sizeHint(self) -> QSize:
        return QSize(self.minimumWidth(), self._total_height)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def visible_rows_for_rect(self, rect: QRect) -> list[int]:
        if not rect.isValid() or not self._row_tops:
            return []
        top = int(rect.top())
        bottom = int(rect.bottom())
        rows: list[int] = []
        for row, row_top in enumerate(self._row_tops):
            row_bottom = row_top + self._row_heights[row] - 1
            if row_bottom < top:
                continue
            if row_top > bottom:
                break
            rows.append(row)
        return rows

    def paintEvent(self, event) -> None:  # noqa: N802
        tokens = get_theme_tokens()
        painter = QPainter(self)
        painter.fillRect(event.rect(), to_qcolor(tokens.surface_bg, "#343434"))
        if event.rect().intersects(QRect(0, 0, self.width(), self._HEADER_HEIGHT)):
            self._paint_header(painter, tokens)
        for row in self.visible_rows_for_rect(event.rect()):
            self._paint_row(painter, row, tokens, event.rect())
        painter.end()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mouseReleaseEvent(event)
        point = event.position().toPoint()
        column = self._column_at(point.x())
        if point.y() < self._HEADER_HEIGHT:
            if column > 0:
                _activate_matrix_column(self._model, column, self._on_bulk_profile_selected)
            return
        row = self._row_at(point.y())
        if row >= 0 and column > 0:
            _activate_matrix_index(self._model, self._model.index(row, column), self._on_profile_selected)

    def _rebuild_geometry_cache(self) -> None:
        self._row_tops = []
        self._row_heights = []
        y = self._HEADER_HEIGHT
        for row in range(self._model.rowCount()):
            height = self._delegate._GROUP_HEIGHT if self._model.is_group_row(row) else self._delegate._ROW_HEIGHT
            self._row_tops.append(y)
            self._row_heights.append(height)
            y += height
        self._total_height = y + 6
        min_width = self._SERVICE_COLUMN_MIN_WIDTH + self._PROFILE_COLUMN_WIDTH * max(0, self._model.columnCount() - 1)
        self.setMinimumWidth(min_width)
        self.setMinimumHeight(self._total_height)
        self.setMaximumHeight(self._total_height)

    def _on_model_data_changed(self, top_left: QModelIndex, bottom_right: QModelIndex) -> None:
        if not top_left.isValid() or not bottom_right.isValid():
            self.update()
            return
        top = self._row_tops[max(0, top_left.row())] if self._row_tops else 0
        bottom_row = min(bottom_right.row(), len(self._row_tops) - 1)
        bottom = self._row_tops[bottom_row] + self._row_heights[bottom_row] if bottom_row >= 0 else self.height()
        self.update(QRect(0, top, self.width(), max(1, bottom - top)))

    def _service_column_width(self) -> int:
        profile_width = self._PROFILE_COLUMN_WIDTH * max(0, self._model.columnCount() - 1)
        return max(self._SERVICE_COLUMN_MIN_WIDTH, self.width() - profile_width)

    def _column_rect(self, column: int) -> QRect:
        service_width = self._service_column_width()
        if column <= 0:
            return QRect(0, 0, service_width, self.height())
        x = service_width + (column - 1) * self._PROFILE_COLUMN_WIDTH
        return QRect(x, 0, self._PROFILE_COLUMN_WIDTH, self.height())

    def _column_at(self, x: int) -> int:
        service_width = self._service_column_width()
        if x < service_width:
            return 0
        column = ((int(x) - service_width) // self._PROFILE_COLUMN_WIDTH) + 1
        if column >= self._model.columnCount():
            return -1
        return int(column)

    def _row_at(self, y: int) -> int:
        for row, row_top in enumerate(self._row_tops):
            if row_top <= y < row_top + self._row_heights[row]:
                return row
            if row_top > y:
                break
        return -1

    def _paint_header(self, painter: QPainter, tokens) -> None:
        rect = QRect(0, 0, self.width(), self._HEADER_HEIGHT)
        painter.fillRect(rect, to_qcolor(tokens.surface_bg, "#343434"))
        painter.setPen(to_qcolor(tokens.fg_muted, "#d7dde7"))
        metrics = QFontMetrics(painter.font())
        for column in range(self._model.columnCount()):
            column_rect = self._column_rect(column)
            header_rect = QRect(column_rect.left(), 0, column_rect.width(), self._HEADER_HEIGHT).adjusted(8, 0, -8, 0)
            text = str(self._model.headerData(column, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole) or "")
            painter.drawText(
                header_rect,
                int(Qt.AlignmentFlag.AlignCenter),
                metrics.elidedText(text, Qt.TextElideMode.ElideRight, header_rect.width()),
            )

    def _paint_row(self, painter: QPainter, row: int, tokens, dirty_rect: QRect) -> None:
        row_rect = QRect(0, self._row_tops[row], self.width(), self._row_heights[row])
        if self._model.is_group_row(row):
            self._paint_group_row(painter, row, row_rect, tokens)
            return
        self._paint_service_cell(painter, row, row_rect, tokens, dirty_rect)
        for column in range(1, self._model.columnCount()):
            column_rect = QRect(
                self._column_rect(column).left(),
                row_rect.top(),
                self._PROFILE_COLUMN_WIDTH,
                row_rect.height(),
            )
            if column_rect.intersects(dirty_rect):
                self._paint_dot_cell(painter, row, column, column_rect)

    def _paint_group_row(self, painter: QPainter, row: int, row_rect: QRect, tokens) -> None:
        text = str(self._model.data(self._model.index(row, 0), Qt.ItemDataRole.DisplayRole) or "")
        if not text:
            return
        original_font = painter.font()
        font = painter.font()
        font.setBold(True)
        font.setPointSize(max(8, font.pointSize() - 1))
        painter.setFont(font)
        painter.setPen(to_qcolor(tokens.fg_muted, "#d7dde7"))
        painter.drawText(
            row_rect.adjusted(self._SERVICE_LEFT_PADDING, 0, -8, 0),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            text,
        )
        painter.setFont(original_font)

    def _paint_service_cell(self, painter: QPainter, row: int, row_rect: QRect, tokens, dirty_rect: QRect) -> None:
        service_rect = QRect(0, row_rect.top(), self._service_column_width(), row_rect.height())
        if not service_rect.intersects(dirty_rect):
            return
        index = self._model.index(row, 0)
        rect = service_rect.adjusted(self._SERVICE_LEFT_PADDING, 0, -8, 0)
        center_y = rect.center().y()
        icon_name = str(self._model.data(index, HostsServicesMatrixModel.IconNameRole) or "fa5s.globe")
        icon_color = self._model.data(index, HostsServicesMatrixModel.IconColorRole) or tokens.icon_fg_faint
        icon_rect = QRect(rect.left(), center_y - self._ICON_SIZE // 2, self._ICON_SIZE, self._ICON_SIZE)
        pixmap = get_cached_qta_pixmap(icon_name, color=icon_color, size=self._ICON_SIZE)
        if not pixmap.isNull():
            painter.drawPixmap(icon_rect, pixmap)
        else:
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(to_qcolor(icon_color, tokens.icon_fg_faint))
            painter.drawEllipse(icon_rect.adjusted(3, 3, -3, -3))
            painter.restore()

        text_rect = QRect(icon_rect.right() + 10, rect.top(), max(0, rect.right() - icon_rect.right() - 10), rect.height())
        text = str(self._model.data(index, Qt.ItemDataRole.DisplayRole) or "")
        metrics = QFontMetrics(painter.font())
        painter.setPen(to_qcolor(tokens.fg, "#f5f5f5"))
        painter.drawText(
            text_rect,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            metrics.elidedText(text, Qt.TextElideMode.ElideRight, text_rect.width()),
        )

    def _paint_dot_cell(self, painter: QPainter, row: int, column: int, rect: QRect) -> None:
        index = self._model.index(row, column)
        available = bool(self._model.data(index, HostsServicesMatrixModel.AvailableRole))
        if not available:
            return
        selected = bool(self._model.data(index, HostsServicesMatrixModel.SelectedRole))
        pixmap = self._delegate.dot_pixmap(selected=selected, available=available)
        top_left = rect.center() - pixmap.rect().center()
        painter.drawPixmap(top_left, pixmap)


def build_hosts_services_matrix(
    groups,
    *,
    off_label: str,
    on_profile_selected,
    on_bulk_profile_selected,
    title: str = "DNS-службы",
) -> HostsServicesMatrixWidgets:
    card = SettingsCard()
    model = HostsServicesMatrixModel(groups, off_label=off_label)
    view = HostsServicesMatrixCanvas(
        model,
        on_profile_selected=on_profile_selected,
        on_bulk_profile_selected=on_bulk_profile_selected,
    )

    _apply_matrix_style(view)
    set_control_accessibility(
        view,
        name=title,
        description=(
            "Таблица выбора DNS-профиля для каждого сервиса. "
            "Строки — сервисы, столбцы — DNS-профили."
        ),
    )
    set_state_text(view, title)
    _disable_matrix_focus_highlight(view)

    card.add_widget(view)
    return HostsServicesMatrixWidgets(card=card, view=view, model=model)


def _disable_matrix_focus_highlight(view: QWidget) -> None:
    view.setFocusPolicy(Qt.FocusPolicy.NoFocus)


def _append_profile(profile_names: list[str], profile_labels: dict[str, str], profile_name: str, label: str) -> None:
    name = str(profile_name or "").strip()
    if not name or name in profile_labels:
        return
    profile_names.append(name)
    profile_labels[name] = str(label or name).strip() or name


def _activate_matrix_index(model: HostsServicesMatrixModel, index: QModelIndex, callback) -> None:
    if not index.isValid() or index.column() <= 0:
        return
    if model.is_group_row(index.row()) or not model.is_profile_available(index.row(), index.column()):
        return
    service_name = model.service_for_row(index.row())
    if not service_name:
        return
    callback(service_name, model.profile_for_column(index.column()))


def _activate_matrix_column(model: HostsServicesMatrixModel, column: int, callback) -> None:
    if column <= 0:
        return
    profile_name = model.profile_for_column(column)
    service_names = model.service_names_for_profile(profile_name)
    if service_names:
        callback(service_names, profile_name)


def _apply_matrix_style(view: QWidget) -> None:
    tokens = get_theme_tokens()
    view.setStyleSheet(
        f"""
        QWidget#hostsServicesMatrix {{
            background: {tokens.surface_bg};
            border: none;
            outline: none;
            color: {tokens.fg};
        }}
        """
    )


__all__ = [
    "HostsServicesMatrixCanvas",
    "HostsServicesMatrixDelegate",
    "HostsServicesMatrixModel",
    "HostsServicesMatrixWidgets",
    "build_hosts_services_matrix",
]
