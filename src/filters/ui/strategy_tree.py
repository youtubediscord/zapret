from __future__ import annotations

from dataclasses import dataclass
import re
import time
from typing import Dict, Iterable, Optional, Set

from PyQt6.QtCore import QEvent, Qt, pyqtSignal, QSize, QTimer, QPoint, QRect
from PyQt6.QtGui import QBrush, QColor, QFont, QPen, QIcon, QPainter, QPainterPath, QPixmap, QCursor, QPalette
from PyQt6.QtWidgets import (
    QApplication,
    QAbstractScrollArea,
    QDialog,
    QHBoxLayout,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QStyle,
    QStyleOptionViewItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from ui.theme import get_theme_tokens, get_cached_qta_pixmap, to_qcolor
from ui.theme_refresh import ThemeRefreshController
from ui.theme_semantic import get_semantic_palette

try:
    from qfluentwidgets import PushButton as _PushButton
except ImportError:
    _PushButton = QPushButton


@dataclass(frozen=True)
class StrategyTreeRow:
    strategy_id: str
    name: str
    args: list[str]
    is_favorite: bool = False
    is_working: Optional[bool] = None


class StrategyTree(QTreeWidget):
    """
    Лёгкий список стратегий на базе QTreeWidget (без множества QWidget-строк).

    Две секции:
    - ★ Избранные
    - Все стратегии

    Columns:
      0: star
      1: name
    """

    strategy_clicked = pyqtSignal(str)
    favorite_toggled = pyqtSignal(str, bool)
    working_mark_requested = pyqtSignal(str, object)  # bool|None
    preview_requested = pyqtSignal(str, object)  # strategy_id, global_pos(QPoint)
    preview_pinned_requested = pyqtSignal(str, object)  # strategy_id, global_pos(QPoint)
    preview_hide_requested = pyqtSignal()

    _ROLE_STRATEGY_ID = int(Qt.ItemDataRole.UserRole) + 1
    _ROLE_ARGS_TEXT = int(Qt.ItemDataRole.UserRole) + 2
    _ROLE_ARGS_FULL = int(Qt.ItemDataRole.UserRole) + 6
    _ROLE_IS_FAVORITE = int(Qt.ItemDataRole.UserRole) + 3
    _ROLE_IS_WORKING = int(Qt.ItemDataRole.UserRole) + 4
    _ROLE_INSERT_INDEX = int(Qt.ItemDataRole.UserRole) + 5
    _ROLE_PHASE_KEYS = int(Qt.ItemDataRole.UserRole) + 7
    _ROLE_TECHNIQUES = int(Qt.ItemDataRole.UserRole) + 8

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("strategyDetailTree")
        self._hover_delay_ms = 180
        self.setColumnCount(2)
        self.setHeaderHidden(True)
        self.setRootIsDecorated(False)
        self.setIndentation(0)
        self.setUniformRowHeights(False)
        self.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self.setSelectionBehavior(QTreeWidget.SelectionBehavior.SelectRows)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)
        self.setMouseTracking(True)
        self.setIconSize(QSize(16, 16))

        # Use internal scrolling (more reliable than growing-by-height inside BasePage/QScrollArea).
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        from PyQt6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # Avoid a huge sizeHint based on all rows; we want a stable viewport + internal scrollbar.
        self.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored)
        # Larger viewport: strategy lists are long, so give the tree more room by default.
        self.setMinimumHeight(520)

        header = self.header()
        header.setSectionResizeMode(0, header.ResizeMode.Fixed)
        header.setSectionResizeMode(1, header.ResizeMode.Stretch)
        self._star_col_w = 45
        self.setColumnWidth(0, self._star_col_w)

        self._row_height = 31
        self._section_height = 22

        self._tokens = get_theme_tokens()
        self._applying_theme_styles = False
        self._apply_theme_styles()
        self._theme_refresh = ThemeRefreshController(self, self._apply_theme_refresh)

        self._mono_font = QFont("Consolas", 9)
        self._name_font = QFont("Segoe UI", 10)
        self._section_font = QFont("Segoe UI", 10)
        self._section_font.setBold(True)

        self._rows: Dict[str, QTreeWidgetItem] = {}
        self._sort_mode = "default"  # default, name_asc, name_desc
        self._insert_counter = 0
        self._active_strategy_id: str = "none"
        self._tech_icon_cache: Dict[tuple, QIcon] = {}
        self._bulk_update_depth = 0
        self._bulk_sections_dirty = False
        self._bulk_geometry_dirty = False

        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.timeout.connect(self._emit_hover_preview)
        self._hover_strategy_id: Optional[str] = None
        self._hover_global_pos: Optional[QPoint] = None
        self._hover_delay_ms = 180
        self._hover_switch_delay_ms = 60
        self._hover_emit_last_ts = 0.0
        self._hover_emit_throttle_s = 0.06  # avoid flooding updates while fast scrolling

        self._geom_timer = QTimer(self)
        self._geom_timer.setSingleShot(True)
        self._geom_timer.timeout.connect(self._propagate_geometry_change)

        self._show_favorites_root_title = True
        self._show_all_root_title = False
        self._fav_root_title = "Избранные"
        self._all_root_title = "Все стратегии"
        self._fav_root = self._add_section(self._fav_root_title)
        self._all_root_default_title = "Все стратегии"
        self._all_root = self._add_section(self._all_root_default_title)
        self._refresh_section_headers()

        self.itemClicked.connect(self._on_item_clicked)

        # WinUI smooth scrollbar (replaces native Qt scrollbar)
        try:
            from qfluentwidgets import SmoothScrollDelegate
            from config.reg import get_smooth_scroll_enabled
            smooth_enabled = get_smooth_scroll_enabled()
            try:
                self._smooth_scroll_delegate = SmoothScrollDelegate(self, useAni=smooth_enabled)
                self.set_smooth_scroll_enabled(smooth_enabled)
            except TypeError:
                self._smooth_scroll_delegate = SmoothScrollDelegate(self)
                self.set_smooth_scroll_enabled(smooth_enabled)
        except Exception:
            self._smooth_scroll_delegate = None

    def set_smooth_scroll_enabled(self, enabled: bool) -> None:
        delegate = getattr(self, "_smooth_scroll_delegate", None)
        if delegate is None:
            return
        try:
            from qfluentwidgets.common.smooth_scroll import SmoothMode
            mode = SmoothMode.COSINE if enabled else SmoothMode.NO_SMOOTH

            if hasattr(delegate, "useAni"):
                if not hasattr(delegate, "_zapret_base_use_ani"):
                    delegate._zapret_base_use_ani = bool(delegate.useAni)
                delegate.useAni = bool(delegate._zapret_base_use_ani) if enabled else False

            for smooth_attr in ("verticalSmoothScroll", "horizonSmoothScroll"):
                smooth = getattr(delegate, smooth_attr, None)
                smooth_setter = getattr(smooth, "setSmoothMode", None)
                if callable(smooth_setter):
                    smooth_setter(mode)

            setter = getattr(delegate, "setSmoothMode", None)
            if callable(setter):
                try:
                    setter(mode)
                except TypeError:
                    setter(mode, Qt.Orientation.Vertical)
            elif hasattr(delegate, "smoothMode"):
                delegate.smoothMode = mode
        except Exception:
            pass

    def _apply_theme_styles(self) -> None:
        if self._applying_theme_styles:
            return

        self._applying_theme_styles = True
        try:
            tokens = self._tokens or get_theme_tokens("Темная синяя")
            # Remove borders/separators; let drawRow() handle all row painting.
            self.setStyleSheet(
                "QTreeWidget { border: none; background: transparent; outline: none; }"
                "QTreeWidget::item { border: none; border-bottom: none; padding: 0; }"
                "QTreeWidget::branch { border: none; background: transparent; }"
            )

            try:
                section_brush = QBrush(QColor("#636b78" if tokens.is_light else "#e8edf5"))
                if hasattr(self, "_fav_root") and self._fav_root is not None:
                    self._fav_root.setForeground(0, section_brush)
                if hasattr(self, "_all_root") and self._all_root is not None:
                    self._all_root.setForeground(0, section_brush)
            except Exception:
                pass
            self._refresh_section_headers()
        finally:
            self._applying_theme_styles = False

    def _set_section_header_state(self, root: QTreeWidgetItem, title: str, visible: bool) -> None:
        text = title if visible else ""
        # Do not use a true zero-height row here: with QTreeWidget that can break
        # viewport height calculation and make the whole list appear empty.
        height = self._section_height if visible else 1
        root.setText(0, text)
        root.setSizeHint(0, QSize(0, height))
        root.setSizeHint(1, QSize(0, height))

    def _refresh_section_headers(self) -> None:
        try:
            fav_has_rows = any(not self._fav_root.child(i).isHidden() for i in range(self._fav_root.childCount()))
        except Exception:
            fav_has_rows = False
        try:
            all_has_rows = any(not self._all_root.child(i).isHidden() for i in range(self._all_root.childCount()))
        except Exception:
            all_has_rows = False

        try:
            self._set_section_header_state(
                self._fav_root,
                self._fav_root_title,
                bool(self._show_favorites_root_title and fav_has_rows),
            )
        except Exception:
            pass
        try:
            self._set_section_header_state(
                self._all_root,
                self._all_root_title,
                bool(self._show_all_root_title and all_has_rows),
            )
        except Exception:
            pass

    def _apply_theme_refresh(self, tokens=None, force: bool = False) -> None:
        _ = force
        old_key = self._current_icon_theme_key()
        self._tokens = tokens or get_theme_tokens()
        self._apply_theme_styles()
        new_key = self._current_icon_theme_key()
        if old_key != new_key:
            self._tech_icon_cache.clear()
            self._refresh_tech_icons_after_theme_change()

    def _current_icon_theme_key(self) -> tuple[str, str, str, str, str, str, int]:
        tokens = self._tokens or get_theme_tokens("Темная синяя")
        semantic = get_semantic_palette(tokens.theme_name)
        size = self.iconSize()
        icon_px = max(1, int(size.width()))
        return (
            str(tokens.theme_name),
            str(tokens.accent_hex),
            str(tokens.icon_fg_muted),
            str(semantic.error),
            str(semantic.warning),
            str(semantic.success),
            icon_px,
        )

    def _refresh_tech_icons_after_theme_change(self) -> None:
        try:
            for strategy_id, item in self._rows.items():
                if strategy_id == "none":
                    continue
                techniques_raw = item.data(0, self._ROLE_TECHNIQUES) or []
                if not isinstance(techniques_raw, (list, tuple)):
                    continue
                techniques = [str(tech).strip().lower() for tech in techniques_raw if str(tech).strip()]
                icon = self._get_tech_icon(techniques[:2])
                if icon:
                    item.setIcon(1, icon)
                else:
                    item.setIcon(1, QIcon())
            self.viewport().update()
        except Exception:
            pass

    def set_all_strategies_phase(self, phase_key: Optional[str]) -> None:
        """
        Updates the "Все стратегии" section title to reflect the currently active phase.

        Examples:
          None -> "Все стратегии"
          "fake" -> "Все стратегии (fake)"
        """
        try:
            key = (phase_key or "").strip().lower()
        except Exception:
            key = ""

        title = self._all_root_default_title
        if key:
            title = f"{title} ({key})"
        self._all_root_title = title

        try:
            self._refresh_section_headers()
        except Exception:
            pass

    def _is_interactive_preview_open(self) -> bool:
        try:
            app = QApplication.instance()
            return bool(app and app.property("zapretgui_args_preview_open"))
        except Exception:
            return False

    def _extract_strategy_id(self, item: Optional[QTreeWidgetItem]) -> Optional[str]:
        if not item:
            return None
        try:
            sid = item.data(0, self._ROLE_STRATEGY_ID)
        except Exception:
            sid = None
        sid = str(sid) if sid else None
        if (not sid) or sid == "none":
            return None
        return sid

    def _cursor_hover_target(self) -> tuple[Optional[str], Optional[QPoint]]:
        """
        Returns strategy id under cursor and global cursor position.

        Strategy id is returned only when cursor is inside this tree viewport and
        points to a real strategy row.
        """
        try:
            gp = QCursor.pos()
        except Exception:
            return None, None

        try:
            w = QApplication.widgetAt(gp)
            if (w is None) or (w is not self.viewport() and (not self.viewport().isAncestorOf(w))):
                return None, gp

            vp_pos = self.viewport().mapFromGlobal(gp)
            if not self.viewport().rect().contains(vp_pos):
                return None, gp

            # Do not show hover preview when cursor is over the favorite star column.
            # The popup covers the list and gets in the way when users try to click the star.
            try:
                if self.columnAt(vp_pos.x()) == 0:
                    return None, gp
            except Exception:
                pass

            item = self.itemAt(vp_pos)
            return self._extract_strategy_id(item), gp
        except Exception:
            return None, gp

    def _emit_preview_request(self, strategy_id: str, pos: Optional[QPoint]) -> None:
        sid = str(strategy_id or "").strip()
        if (not sid) or sid == "none":
            return

        if pos is None:
            try:
                pos = QCursor.pos()
            except Exception:
                try:
                    pos = self.mapToGlobal(self.rect().center())
                except Exception:
                    return

        self._hover_emit_last_ts = time.monotonic()
        try:
            self.preview_requested.emit(sid, pos)
        except Exception:
            pass

    def _sync_hover_from_cursor(self, *, immediate: bool) -> None:
        """
        Keep hover preview in sync even when the list scrolls under a stationary cursor.

        Qt often won't emit MouseMove when users scroll with the wheel/scrollbar,
        so we re-check what's under the cursor after scroll changes.
        """
        # When RMB preview is open, disable all hover previews.
        if self._is_interactive_preview_open():
            self._cancel_hover_preview()
            return

        sid, gp = self._cursor_hover_target()
        if not sid:
            self._cancel_hover_preview()
            return

        # Update hover target + position
        prev_sid = self._hover_strategy_id
        changed = (sid != prev_sid)
        self._hover_strategy_id = sid
        self._hover_global_pos = gp

        # Ensure a repaint even if the Qt style does not provide State_MouseOver
        # for the hovered index (we also use _hover_strategy_id in drawRow()).
        if changed:
            try:
                self.viewport().update()
            except Exception:
                pass

        if immediate:
            # Immediate refresh when scrolling: show correct strategy without waiting.
            now = time.monotonic()
            if changed or (now - self._hover_emit_last_ts) >= self._hover_emit_throttle_s:
                self._emit_preview_request(sid, gp)
            else:
                # Too frequent: schedule a delayed emit.
                self._hover_timer.start(self._hover_delay_ms)
        else:
            if changed:
                delay = self._hover_switch_delay_ms if prev_sid else self._hover_delay_ms
                self._hover_timer.start(max(0, int(delay)))

    def drawRow(self, painter, options: QStyleOptionViewItem, index) -> None:  # noqa: N802 (Qt override)
        """
        Paint selection and working/broken tint manually.

        This avoids conflicts with global app QSS (theme) which can override
        `QTreeWidget::item:selected` and per-item BackgroundRole brushes.
        """
        item = self.itemFromIndex(index)
        if not item or item.flags() == Qt.ItemFlag.NoItemFlags:
            return super().drawRow(painter, options, index)

        sid = item.data(0, self._ROLE_STRATEGY_ID)
        sid = str(sid) if sid else ""
        is_active = bool(sid) and sid == (self._active_strategy_id or "none")
        is_hover = bool(options.state & QStyle.StateFlag.State_MouseOver) or (
            bool(sid) and sid == (self._hover_strategy_id or "")
        )
        is_working = item.data(0, self._ROLE_IS_WORKING)
        if is_working not in (True, False, None):
            is_working = None

        try:
            tokens = get_theme_tokens()
            self._tokens = tokens
        except Exception:
            tokens = self._tokens or get_theme_tokens("Темная синяя")
        semantic = get_semantic_palette(tokens.theme_name)
        accent_r, accent_g, accent_b = tokens.accent_rgb

        r = options.rect.adjusted(4, 1, -4, -1)

        # Base tint (working/broken)
        base_bg = None
        if is_working is True:
            success_tint = QColor(semantic.success)
            success_tint.setAlpha(42)
            base_bg = success_tint
        elif is_working is False:
            error_tint = QColor(semantic.error)
            error_tint.setAlpha(42)
            base_bg = error_tint

        hover_bg = None
        try:
            if is_hover and not is_active:
                hover_bg = to_qcolor(tokens.accent_soft_bg, tokens.accent_hex)
                if hover_bg.alpha() <= 0:
                    hover_bg.setAlpha(14)
                else:
                    hover_bg.setAlpha(max(8, min(hover_bg.alpha(), 16)))
        except Exception:
            hover_bg = QColor(accent_r, accent_g, accent_b, 8) if is_hover and not is_active else None

        selected_bg = None
        if is_active:
            try:
                selected_bg = to_qcolor(tokens.accent_soft_bg, tokens.surface_bg_hover)
                if selected_bg.alpha() <= 0:
                    selected_bg.setAlpha(76)
            except Exception:
                selected_bg = QColor(accent_r, accent_g, accent_b, 24)

        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing, True)

        if base_bg is not None:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(base_bg))
            painter.drawRoundedRect(r, 6, 6)

        if hover_bg is not None:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(hover_bg))
            painter.drawRoundedRect(r, 6, 6)

        if selected_bg is not None:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(selected_bg))
            painter.drawRoundedRect(r, 6, 6)

        painter.restore()

        # Draw text/icons without letting the style paint its own selection background.
        opt = QStyleOptionViewItem(options)
        opt.state &= ~QStyle.StateFlag.State_Selected
        opt.state &= ~QStyle.StateFlag.State_MouseOver
        try:
            if not tokens.is_light:
                white_text = QColor(245, 245, 245, 240)
                opt.palette.setColor(QPalette.ColorRole.Text, white_text)
                opt.palette.setColor(QPalette.ColorRole.WindowText, white_text)
                opt.palette.setColor(QPalette.ColorRole.HighlightedText, white_text)
        except Exception:
            pass
        return super().drawRow(painter, opt, index)

    def _add_section(self, title: str) -> QTreeWidgetItem:
        root = QTreeWidgetItem(self)
        root.setFirstColumnSpanned(True)
        root.setText(0, title)
        root.setFont(0, self._section_font)
        tokens = self._tokens or get_theme_tokens("Темная синяя")
        root.setForeground(0, QBrush(QColor("#636b78" if tokens.is_light else "#e8edf5")))
        root.setFlags(Qt.ItemFlag.NoItemFlags)
        root.setExpanded(True)
        root.setHidden(True)
        root.setSizeHint(0, QSize(0, self._section_height))
        return root

    def clear_strategies(self) -> None:
        self._rows.clear()
        self._fav_root.takeChildren()
        self._all_root.takeChildren()
        self._fav_root.setHidden(True)
        self._all_root.setHidden(True)
        self._insert_counter = 0
        self._active_strategy_id = "none"
        self._refresh_section_headers()
        self._update_height_to_contents()

    def has_rows(self) -> bool:
        return bool(self._rows)

    def has_strategy(self, strategy_id: str) -> bool:
        return (strategy_id or "") in self._rows

    def get_strategy_item_rect(self, strategy_id: str) -> Optional[QRect]:
        item = self._rows.get(strategy_id or "")
        if not item:
            return None
        try:
            return self.visualItemRect(item)
        except Exception:
            return None

    def is_strategy_visible(self, strategy_id: str) -> bool:
        item = self._rows.get(strategy_id or "")
        if not item:
            return False
        return not bool(item.isHidden())

    def set_sort_mode(self, mode: str) -> None:
        if mode in ("default", "name_asc", "name_desc"):
            self._sort_mode = mode

    def _args_preview_text(self, args: list[str]) -> str:
        # kept for compatibility (search/filter); not shown in UI
        if not args:
            return ""
        parts = [str(a).strip() for a in args if str(a).strip()]
        return " ".join(parts)

    @staticmethod
    def _map_desync_value_to_technique(val: str) -> Optional[str]:
        v = (val or "").strip().lower()
        if not v:
            return None
        if "syndata" in v:
            return "syndata"
        if "oob" in v:
            return "oob"
        if "disorder" in v:
            return "disorder"
        if "multisplit" in v:
            return "multisplit"
        if "split" in v:
            return "split"
        if "fake" in v or "hostfakesplit" in v:
            return "fake"
        return None

    @staticmethod
    def _map_desync_value_to_phase_key(val: str) -> Optional[str]:
        """
        Maps raw --lua-desync/--dpi-desync values to a stable phase key.

        Phase keys are used for the multi-phase TCP UI (FAKE + MULTISPLIT + ...).
        """
        v = (val or "").strip().lower()
        if not v:
            return None

        # Dedicated fake phase (pure fake only)
        if v == "fake":
            return "fake"

        # "pass" is a no-op. Keep it in the main phase so users can enable a
        # category for send/syndata/out-range without selecting other techniques.
        if v == "pass":
            return "multisplit"

        # "Embedded fake" techniques belong to the main phase tabs
        if v in ("multisplit", "fakedsplit", "hostfakesplit"):
            return "multisplit"
        if v in ("multidisorder", "fakeddisorder"):
            return "multidisorder"
        if v == "multidisorder_legacy":
            return "multidisorder_legacy"
        if v == "tcpseg":
            return "tcpseg"
        if v == "oob":
            return "oob"

        return "other"

    @classmethod
    def _infer_phase_keys(cls, strategy_id: str, args_full_text: str) -> list[str]:
        """
        Best-effort phase keys for filtering (multi-phase TCP UI).

        Unlike `_infer_techniques()` (icon-only), this keeps more granular
        phase buckets and avoids substring collisions like `fake` vs `fakedsplit`.
        """
        sid = (strategy_id or "").strip().lower()
        txt = (args_full_text or "").strip().lower()

        # Special pseudo rows (not real strategies).
        if sid.startswith("__phase_fake_disabled__"):
            return ["fake"]

        out: list[str] = []
        for val in re.findall(r"--(?:lua-desync|dpi-desync)=([a-z0-9_-]+)", txt):
            key = cls._map_desync_value_to_phase_key(val)
            if key and key not in out:
                out.append(key)

        # Fallback by id when no desync marker was found
        if not out:
            for key in ("fake", "multisplit", "multidisorder", "multidisorder_legacy", "tcpseg", "oob"):
                if key in sid:
                    out.append(key)
                    break

        return out or ["other"]

    @classmethod
    def _infer_techniques(cls, strategy_id: str, args_text_lower: str) -> list[str]:
        """
        Best-effort detect techniques for an icon.

        If there are multiple `--lua-desync/--dpi-desync` entries, we return multiple
        techniques in order; the icon can be split diagonally into two colors.
        """
        sid = (strategy_id or "").lower()
        txt = (args_text_lower or "")

        # Primary source: explicit desync values (can be multiple)
        out: list[str] = []
        for val in re.findall(r"--(?:lua-desync|dpi-desync)=([a-z0-9_-]+)", txt):
            tech = cls._map_desync_value_to_technique(val)
            if tech and tech not in out:
                out.append(tech)
        if out:
            return out

        # Fallback by substring (order matters: multisplit before split)
        hay = f"{sid} {txt}"
        fallback = []
        for tech in ("syndata", "oob", "disorder", "multisplit", "split", "fake"):
            if tech in hay:
                fallback.append(tech)
                break
        return fallback

    @staticmethod
    def _compose_diagonal_pixmap(pix_a: QPixmap, pix_b: QPixmap) -> QPixmap:
        w = max(1, pix_a.width())
        h = max(1, pix_a.height())
        out = QPixmap(w, h)
        out.fill(Qt.GlobalColor.transparent)

        p = QPainter(out)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Split by diagonal (top-left -> bottom-right)
        path_a = QPainterPath()
        path_a.moveTo(0, 0)
        path_a.lineTo(w, 0)
        path_a.lineTo(0, h)
        path_a.closeSubpath()

        path_b = QPainterPath()
        path_b.moveTo(w, 0)
        path_b.lineTo(w, h)
        path_b.lineTo(0, h)
        path_b.closeSubpath()

        p.save()
        p.setClipPath(path_a)
        p.drawPixmap(0, 0, pix_a)
        p.restore()

        p.save()
        p.setClipPath(path_b)
        p.drawPixmap(0, 0, pix_b)
        p.restore()

        p.end()
        return out

    @staticmethod
    def _fixed_icon_from_pixmap(pix: QPixmap) -> QIcon:
        """
        Freeze icon colors across view states.

        Some Qt styles auto-generate Disabled/Selected pixmaps by tinting/grayscaling.
        To keep our pastel colors, we provide the same pixmap for all modes.
        """
        icon = QIcon()
        for mode in (QIcon.Mode.Normal, QIcon.Mode.Disabled, QIcon.Mode.Active, QIcon.Mode.Selected):
            icon.addPixmap(pix, mode, QIcon.State.Off)
            icon.addPixmap(pix, mode, QIcon.State.On)
        return icon

    def _get_tech_icon(self, techniques: list[str]) -> Optional[QIcon]:
        if not techniques:
            return None
        normalized_techniques = tuple(str(t).strip().lower() for t in techniques[:2] if str(t).strip())
        if not normalized_techniques:
            return None

        key = (self._current_icon_theme_key(), normalized_techniques)
        if key in self._tech_icon_cache:
            return self._tech_icon_cache[key]

        try:
            tokens = self._tokens or get_theme_tokens()
            accent_color = tokens.accent_hex
            semantic = get_semantic_palette(tokens.theme_name)
        except Exception:
            tokens = get_theme_tokens("Темная синяя")
            accent_color = tokens.accent_hex
            semantic = get_semantic_palette("Темная синяя")

        icon_px = max(1, int(self.iconSize().width()))

        # Minimalistic icons + pastel palette (no emoji).
        # Colors per request:
        # - fake: red
        # - multisplit: blue
        # - (multi)disorder: green
        mapping = {
            "fake": ("fa5s.magic", semantic.error),
            "split": ("fa5s.cut", semantic.warning),
            "multisplit": ("fa5s.stream", accent_color),
            "disorder": ("fa5s.random", semantic.success),
            "oob": ("fa5s.external-link-alt", "#f472b6"),
            "syndata": ("fa5s.database", tokens.icon_fg_muted),
        }

        primary = normalized_techniques[0]
        icon_name, color_a = mapping.get(primary, (None, None))
        if not icon_name or not color_a:
            return None

        try:
            if len(normalized_techniques) >= 2 and normalized_techniques[1] != primary:
                secondary = normalized_techniques[1]
                _, color_b = mapping.get(secondary, (icon_name, color_a))
                base_a = get_cached_qta_pixmap(icon_name, color=color_a, size=icon_px, theme_name=tokens.theme_name)
                base_b = get_cached_qta_pixmap(icon_name, color=color_b, size=icon_px, theme_name=tokens.theme_name)
                if base_a.isNull() or base_b.isNull():
                    return None
                pix = self._compose_diagonal_pixmap(base_a, base_b)
                icon = self._fixed_icon_from_pixmap(pix)
            else:
                pix = get_cached_qta_pixmap(icon_name, color=color_a, size=icon_px, theme_name=tokens.theme_name)
                if pix.isNull():
                    return None
                icon = self._fixed_icon_from_pixmap(pix)
        except Exception:
            return None

        self._tech_icon_cache[key] = icon
        return icon

    def add_strategy(self, row: StrategyTreeRow) -> None:
        parent = self._fav_root if row.is_favorite else self._all_root
        item = QTreeWidgetItem(parent)

        item.setData(0, self._ROLE_STRATEGY_ID, row.strategy_id)
        args_joined = self._args_preview_text(row.args)
        item.setData(0, self._ROLE_ARGS_TEXT, args_joined.lower())
        args_full = "\n".join(row.args)
        item.setData(0, self._ROLE_ARGS_FULL, args_full)
        item.setData(0, self._ROLE_IS_FAVORITE, bool(row.is_favorite))
        item.setData(0, self._ROLE_IS_WORKING, row.is_working)
        item.setData(0, self._ROLE_INSERT_INDEX, self._insert_counter)
        item.setData(0, self._ROLE_PHASE_KEYS, self._infer_phase_keys(row.strategy_id, args_full))
        self._insert_counter += 1

        item.setText(1, row.name)
        item.setFont(1, self._name_font)
        try:
            tokens = self._tokens or get_theme_tokens("Темная синяя")
            row_text_color = QColor("#111111" if tokens.is_light else "#f5f5f5")
            item.setForeground(1, QBrush(row_text_color))
        except Exception:
            pass

        if row.strategy_id != "none":
            techniques = self._infer_techniques(row.strategy_id, args_joined.lower())
            try:
                item.setData(0, self._ROLE_TECHNIQUES, techniques)
            except Exception:
                pass
            icon = self._get_tech_icon(techniques[:2])
            if icon:
                item.setIcon(1, icon)
        else:
            try:
                item.setData(0, self._ROLE_TECHNIQUES, [])
            except Exception:
                pass

        self._apply_star(item, row.is_favorite, allow=(row.strategy_id != "none"))
        self._apply_working_style(item, row.is_working)
        item.setSizeHint(0, QSize(0, self._row_height))
        item.setSizeHint(1, QSize(0, self._row_height))

        self._rows[row.strategy_id] = item
        self._request_structure_refresh()

    def set_selected_strategy(self, strategy_id: str) -> None:
        self._active_strategy_id = strategy_id or "none"
        item = self._rows.get(self._active_strategy_id)
        if item:
            self.clearSelection()
            self.setCurrentItem(item)
            item.setSelected(True)
        self.viewport().update()

    def clear_active_strategy(self) -> None:
        """Clears the highlighted (active) strategy row without removing items."""
        self._active_strategy_id = "none"
        try:
            self.clearSelection()
            self.setCurrentItem(None)
        except Exception:
            pass
        self.viewport().update()

    def get_strategy_ids(self) -> list[str]:
        return list(self._rows.keys())

    def total_strategy_count(self) -> int:
        return len(self._rows)

    def visible_strategy_count(self) -> int:
        return sum(1 for item in self._rows.values() if not item.isHidden())

    def set_working_state(self, strategy_id: str, is_working: Optional[bool]) -> None:
        item = self._rows.get(strategy_id)
        if not item:
            return
        item.setData(0, self._ROLE_IS_WORKING, is_working)
        self._apply_working_style(item, is_working)
        # Ensure repaint even if global QSS overrides item roles.
        self.viewport().update()

    def set_favorite_state(self, strategy_id: str, is_favorite: bool) -> None:
        item = self._rows.get(strategy_id)
        if not item:
            return
        if strategy_id == "none":
            is_favorite = False
        if bool(item.data(0, self._ROLE_IS_FAVORITE)) == bool(is_favorite):
            return

        item.setData(0, self._ROLE_IS_FAVORITE, bool(is_favorite))
        self._apply_star(item, bool(is_favorite), allow=(strategy_id != "none"))

        was_selected = bool(item.isSelected())

        # Move between sections
        src_parent = item.parent()
        dst_parent = self._fav_root if is_favorite else self._all_root
        if src_parent is not None and src_parent is not dst_parent:
            idx = src_parent.indexOfChild(item)
            moved = src_parent.takeChild(idx)
            self._insert_sorted(dst_parent, moved)

        self._request_structure_refresh()
        if was_selected:
            self.set_selected_strategy(strategy_id)

    def apply_filter(self, search_text: str, techniques: Set[str]) -> None:
        search = (search_text or "").strip().lower()
        tech = {t.strip().lower() for t in (techniques or set()) if t and t.strip()}

        selected_id = self._active_strategy_id or self._get_selected_strategy_id()
        for sid, item in self._rows.items():
            visible = True
            args_text = str(item.data(0, self._ROLE_ARGS_TEXT) or "")
            if search:
                visible = (search in args_text) or (search in (item.text(1) or "").lower())
            if visible and tech:
                inferred = item.data(0, self._ROLE_TECHNIQUES) or []
                try:
                    visible = bool(tech.intersection({str(t or "").strip().lower() for t in inferred if str(t or "").strip()}))
                except Exception:
                    visible = any(t in args_text for t in tech)
            item.setHidden(not visible)

        self._request_structure_refresh()
        if selected_id and self.has_strategy(selected_id) and not self._rows[selected_id].isHidden():
            self.set_selected_strategy(selected_id)

    def apply_phase_filter(self, search_text: str, phase_key: Optional[str]) -> None:
        """
        Filters rows by a phase key (exact match), optionally combined with search.

        This is used by the multi-phase TCP UI. It intentionally avoids substring
        matching so `fake` does not match `fakedsplit`, etc.
        """
        search = (search_text or "").strip().lower()
        phase = (phase_key or "").strip().lower()

        selected_id = self._active_strategy_id or self._get_selected_strategy_id()

        for sid, item in self._rows.items():
            visible = True
            args_text = str(item.data(0, self._ROLE_ARGS_TEXT) or "")
            if search:
                visible = (search in args_text) or (search in (item.text(1) or "").lower())

            if visible and phase:
                keys = item.data(0, self._ROLE_PHASE_KEYS) or []
                try:
                    visible = phase in set(str(k).lower() for k in keys)
                except Exception:
                    visible = False

            item.setHidden(not visible)

        self._request_structure_refresh()
        if selected_id and self.has_strategy(selected_id) and not self._rows[selected_id].isHidden():
            self.set_selected_strategy(selected_id)

    def apply_sort(self) -> None:
        selected_id = self._active_strategy_id or self._get_selected_strategy_id()
        self._sort_section(self._fav_root)
        self._sort_section(self._all_root)
        self._request_structure_refresh()
        if selected_id:
            self.set_selected_strategy(selected_id)

    def begin_bulk_update(self) -> None:
        self._bulk_update_depth += 1
        if self._bulk_update_depth == 1:
            try:
                self.setUpdatesEnabled(False)
            except Exception:
                pass

    def end_bulk_update(self) -> None:
        if self._bulk_update_depth <= 0:
            return
        self._bulk_update_depth -= 1
        if self._bulk_update_depth > 0:
            return
        try:
            self.setUpdatesEnabled(True)
        except Exception:
            pass
        self._flush_structure_refresh()

    def _sort_section(self, root: QTreeWidgetItem) -> None:
        children = [root.child(i) for i in range(root.childCount())]
        if not children:
            return

        if self._sort_mode == "name_asc":
            children.sort(key=lambda it: (it.text(1) or "").lower())
        elif self._sort_mode == "name_desc":
            children.sort(key=lambda it: (it.text(1) or "").lower(), reverse=True)
        else:
            children.sort(key=lambda it: int(it.data(0, self._ROLE_INSERT_INDEX) or 0))

        root.takeChildren()
        for child in children:
            root.addChild(child)

    def _insert_sorted(self, root: QTreeWidgetItem, item: QTreeWidgetItem) -> None:
        if self._sort_mode == "name_asc":
            key = (item.text(1) or "").lower()
            for i in range(root.childCount()):
                if key < (root.child(i).text(1) or "").lower():
                    root.insertChild(i, item)
                    return
        elif self._sort_mode == "name_desc":
            key = (item.text(1) or "").lower()
            for i in range(root.childCount()):
                if key > (root.child(i).text(1) or "").lower():
                    root.insertChild(i, item)
                    return
        else:
            idx = int(item.data(0, self._ROLE_INSERT_INDEX) or 0)
            for i in range(root.childCount()):
                other = root.child(i)
                other_idx = int(other.data(0, self._ROLE_INSERT_INDEX) or 0)
                if idx < other_idx:
                    root.insertChild(i, item)
                    return
        root.addChild(item)

    def _refresh_sections_visibility(self) -> None:
        fav_visible = any(not self._fav_root.child(i).isHidden() for i in range(self._fav_root.childCount()))
        all_visible = any(not self._all_root.child(i).isHidden() for i in range(self._all_root.childCount()))
        self._fav_root.setHidden(not fav_visible)
        self._all_root.setHidden(not all_visible)
        self._refresh_section_headers()

        self.expandItem(self._fav_root)
        self.expandItem(self._all_root)

    def _update_height_to_contents(self) -> None:
        # Internal scrollbar mode: keep a stable viewport height.
        # Still request a layout/paint update after bulk changes.
        try:
            self.updateGeometry()
            self.viewport().update()
        except Exception:
            pass

    def _request_structure_refresh(self) -> None:
        self._bulk_sections_dirty = True
        self._bulk_geometry_dirty = True
        if self._bulk_update_depth > 0:
            return
        self._flush_structure_refresh()

    def _flush_structure_refresh(self) -> None:
        if self._bulk_sections_dirty:
            self._bulk_sections_dirty = False
            self._refresh_sections_visibility()
        if self._bulk_geometry_dirty:
            self._bulk_geometry_dirty = False
            self._update_height_to_contents()

    def _schedule_geometry_update(self) -> None:
        # Coalesce multiple updates during batch loads (e.g. lazy strategy load).
        if self._geom_timer.isActive():
            return
        self._geom_timer.start(0)

    def _propagate_geometry_change(self) -> None:
        try:
            self.updateGeometry()
        except Exception:
            pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.setColumnWidth(0, self._star_col_w)

    def wheelEvent(self, event) -> None:  # noqa: N802 (Qt override)
        """
        Always consume wheel events so the parent page (QScrollArea/BasePage)
        does not scroll when the cursor is over the strategies list.
        """
        super().wheelEvent(event)
        # QAbstractItemView may scroll contents without moving the cursor,
        # so update hover target right away.
        try:
            self._sync_hover_from_cursor(immediate=True)
        except Exception:
            pass
        try:
            event.accept()
        except Exception:
            pass

    def scrollContentsBy(self, dx: int, dy: int) -> None:  # noqa: N802 (Qt override)
        super().scrollContentsBy(dx, dy)
        try:
            if dx or dy:
                self._sync_hover_from_cursor(immediate=True)
        except Exception:
            pass

    def _apply_star(self, item: QTreeWidgetItem, is_favorite: bool, allow: bool) -> None:
        tokens = self._tokens or get_theme_tokens("Темная синяя")
        semantic = get_semantic_palette(tokens.theme_name)
        if not allow:
            item.setText(0, "")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            return
        item.setText(0, "★" if is_favorite else "☆")
        item.setTextAlignment(0, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        if is_favorite:
            favorite_color = QColor(semantic.warning)
            favorite_color.setAlpha(235)
        else:
            favorite_color = to_qcolor(tokens.fg_faint, "#aeb5c1")
            favorite_color.setAlpha(120)
        item.setForeground(0, QBrush(favorite_color))

    def _apply_working_style(self, item: QTreeWidgetItem, is_working: Optional[bool]) -> None:
        # We keep the state in a data role and paint in drawRow().
        # Also, clear any previously set background to avoid theme/QSS conflicts.
        item.setData(0, self._ROLE_IS_WORKING, is_working if is_working in (True, False) else None)
        for col in range(2):
            item.setData(col, Qt.ItemDataRole.BackgroundRole, None)

    def _get_selected_strategy_id(self) -> Optional[str]:
        item = self.currentItem()
        if not item:
            sel = self.selectedItems()
            item = sel[0] if sel else None
        if not item:
            return None
        sid = item.data(0, self._ROLE_STRATEGY_ID)
        return str(sid) if sid else None

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        strategy_id = item.data(0, self._ROLE_STRATEGY_ID)
        if not strategy_id:
            return

        if column == 0:
            if strategy_id == "none":
                return
            new_state = not bool(item.data(0, self._ROLE_IS_FAVORITE))
            # UI сразу обновляем, persistence пусть делает владелец
            self.set_favorite_state(strategy_id, new_state)
            self.favorite_toggled.emit(strategy_id, new_state)
            return

        # Click should immediately sync the preview to the clicked strategy.
        # This avoids "stale" hover previews when users scroll/click quickly.
        try:
            self._hover_timer.stop()
        except Exception:
            pass
        sid = str(strategy_id or "").strip()
        if sid and sid != "none":
            try:
                gp = QCursor.pos()
            except Exception:
                gp = None
            self._hover_strategy_id = sid
            self._hover_global_pos = gp
            self._emit_preview_request(sid, gp)

        self.strategy_clicked.emit(strategy_id)

    def viewportEvent(self, event):
        et = event.type()
        if et == QEvent.Type.Wheel:
            handled = super().viewportEvent(event)
            try:
                event.accept()
            except Exception:
                pass
            return True
        if et in (QEvent.Type.MouseMove, QEvent.Type.HoverMove):
            # When RMB preview is open, disable all hover previews to avoid conflicts.
            if self._is_interactive_preview_open():
                self._cancel_hover_preview()
                return super().viewportEvent(event)
            # Use cursor-based sync to keep behavior consistent with scroll updates.
            try:
                self._sync_hover_from_cursor(immediate=False)
            except Exception:
                pass
            return super().viewportEvent(event)

        if et in (QEvent.Type.Leave, QEvent.Type.HoverLeave):
            self._cancel_hover_preview()
            return super().viewportEvent(event)

        return super().viewportEvent(event)

    def _cancel_hover_preview(self) -> None:
        had = bool(self._hover_strategy_id)
        self._hover_timer.stop()
        self._hover_strategy_id = None
        self._hover_global_pos = None
        if had:
            try:
                self.viewport().update()
            except Exception:
                pass
        if had:
            try:
                self.preview_hide_requested.emit()
            except Exception:
                pass

    def _emit_hover_preview(self) -> None:
        sid = self._hover_strategy_id
        if not sid:
            return

        # When RMB preview is open, disable all hover previews.
        if self._is_interactive_preview_open():
            self._cancel_hover_preview()
            return

        # Validate that the cursor is still over the same strategy row.
        current_sid, gp = self._cursor_hover_target()
        if current_sid != sid:
            if current_sid:
                # Cursor moved to another row while timer was running.
                # Sync immediately to prevent stale preview content.
                self._sync_hover_from_cursor(immediate=True)
            else:
                # Cursor is outside a strategy row (or outside viewport) now.
                self._cancel_hover_preview()
            return

        item = self._rows.get(sid)
        if not item or item.isHidden():
            self._cancel_hover_preview()
            return

        pos = gp or self._hover_global_pos
        self._emit_preview_request(sid, pos)

    def _show_args_dialog(self, item: QTreeWidgetItem) -> None:
        full = str(item.data(0, self._ROLE_ARGS_FULL) or "").strip()
        if not full:
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Аргументы стратегии")
        dlg.setModal(True)
        tokens = get_theme_tokens()
        dlg_bg = "#f6f7f9" if tokens.is_light else "#2a2a2a"
        btn_text = "#111111" if tokens.is_light else "rgba(245,245,245,0.90)"
        dlg.setStyleSheet(f"""
            QDialog {{ background: {dlg_bg}; }}
            QPushButton {{
                background: {tokens.surface_bg};
                border: 1px solid {tokens.surface_border};
                border-radius: 6px;
                color: {btn_text};
                padding: 6px 12px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: {tokens.surface_bg_hover}; }}
        """)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        edit = QPlainTextEdit()
        edit.setReadOnly(True)
        edit.setPlainText(full)
        edit_bg = "rgba(0, 0, 0, 0.06)" if tokens.is_light else "rgba(0, 0, 0, 0.25)"
        edit_text = "#111111" if tokens.is_light else "rgba(245,245,245,0.90)"
        edit.setStyleSheet(f"""
            QPlainTextEdit {{
                background: {edit_bg};
                border: 1px solid {tokens.surface_border};
                border-radius: 8px;
                color: {edit_text};
                font-family: 'Consolas', monospace;
                font-size: 10px;
                padding: 10px;
            }}
        """)
        edit.setMinimumHeight(200)
        layout.addWidget(edit, 1)

        btns = QHBoxLayout()
        btns.addStretch()

        copy_btn = _PushButton()
        copy_btn.setText("Копировать")
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(full))
        btns.addWidget(copy_btn)

        close_btn = _PushButton()
        close_btn.setText("Закрыть")
        close_btn.clicked.connect(dlg.accept)
        btns.addWidget(close_btn)

        layout.addLayout(btns)
        dlg.resize(640, 360)
        dlg.exec()

    def contextMenuEvent(self, event):
        # If RMB preview is already open, first RMB closes it (consumed globally),
        # so do not open another preview on the same click.
        try:
            app = QApplication.instance()
            if app and bool(app.property("zapretgui_args_preview_open")):
                return
        except Exception:
            pass
        self._cancel_hover_preview()
        item = self.itemAt(event.pos())
        if not item:
            return
        strategy_id = item.data(0, self._ROLE_STRATEGY_ID)
        if not strategy_id or strategy_id == "none":
            return

        # ПКМ: показать интерактивное окно (как в direct_zapret1), а не контекстное меню.
        self.preview_pinned_requested.emit(str(strategy_id), event.globalPos())

    def hideEvent(self, event):  # noqa: N802 (Qt override)
        # When the page/window is hidden, ensure we never show a delayed hover preview.
        try:
            self._cancel_hover_preview()
        except Exception:
            pass
        return super().hideEvent(event)
