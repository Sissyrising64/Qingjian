"""The filmstrip and the thumbnail grid.

Both are ``QListWidget`` in icon mode, with three things that keep a folder of
tens of thousands of files usable:

* **Icons are requested for what the viewport shows, not for the whole list.**
  Asking for every thumbnail on open was the single reason a large folder hung.
* **Rows are laid out in batches** (``LayoutMode.Batched``) and are all the same
  size, so Qt never has to measure the entire model at once.
* **The filmstrip holds a window around the cursor**, not the whole queue; it is
  a way to glance at neighbours, and nobody scrubs through 20 000 of them.

Badges (raw, duration, rating, colour label) are painted into the thumbnail
rather than drawn by a custom item delegate: fewer moving parts, and the same
composited image serves both views.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QAbstractItemView, QListWidget, QListWidgetItem

from ..core import mediatypes, metadata, viewport
from . import theme
from .thumbs import ThumbnailCache, pending_pixmap

_ROLE_PATH = int(Qt.ItemDataRole.UserRole) + 1

#: Rows fetched beyond the visible range, so a slow scroll is never empty.
_OVERSCAN = 12
#: Upper bound on the walk that finds the last visible row.
_MAX_PROBE = 400
#: How many neighbours the filmstrip keeps loaded around the current item.
FILMSTRIP_WINDOW = 80


def decorate(pixmap: QPixmap, raw: bool = False, duration: str = "", rating: int = 0,
             label: str = "", burst: str = "", keeper: bool = False) -> QPixmap:
    """Paint the small status badges onto a copy of *pixmap*."""
    if pixmap.isNull():
        return pixmap
    if not (raw or duration or rating or label or burst or keeper):
        return pixmap
    canvas = QPixmap(pixmap)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    width, height = canvas.width(), canvas.height()
    font = painter.font()
    font.setPointSizeF(max(5.5, height * 0.085))
    font.setBold(True)
    painter.setFont(font)
    metrics = painter.fontMetrics()
    pad = max(2, int(height * 0.03))

    def chip(text: str, x: int, y: int, fill: str, ink: str, right: bool = False) -> None:
        box_width = metrics.horizontalAdvance(text) + 8
        box_height = metrics.height() + 2
        left = x - box_width if right else x
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(fill))
        painter.drawRoundedRect(left, y, box_width, box_height, 3, 3)
        painter.setPen(QColor(ink))
        painter.drawText(left, y, box_width, box_height, Qt.AlignmentFlag.AlignCenter, text)

    if raw:
        chip("RAW", width - pad, pad, "#241E3D", theme.KEYCAP_TEXT, right=True)
    if duration:
        chip(duration, width - pad, height - pad - metrics.height() - 2,
             "#0B0E14", theme.TEXT_BUTTON, right=True)
    if burst:
        chip(burst, pad, pad, "#2C2415", theme.WARN)
    if keeper:
        chip("✓", pad, pad, theme.WARN, "#201803")
    if rating:
        chip("★" * min(5, rating), pad, height - pad - metrics.height() - 2,
             "#0B0E14", theme.WARN)
    if label:
        colour = theme.LABEL_COLOURS.get(label)
        if colour:
            dot = max(6, int(height * 0.09))
            painter.setPen(QColor("#0B0E14"))
            painter.setBrush(QColor(colour))
            painter.drawRoundedRect(pad, int(height * 0.42), dot, dot, 2, 2)
    painter.end()
    return canvas


class _Browser(QListWidget):
    """Shared plumbing: paths in, thumbnails filled in as they become visible."""

    path_activated = Signal(str)
    path_selected = Signal(str)

    def __init__(self, cache: ThumbnailCache, edge: int, parent=None) -> None:
        super().__init__(parent)
        self.cache = cache
        self.edge = edge
        self._rows: dict[str, QListWidgetItem] = {}
        self._decorations: dict[str, dict] = {}
        self._placeholder = pending_pixmap(QSize(edge, edge))
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setMovement(QListWidget.Movement.Static)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setUniformItemSizes(True)
        self.setLayoutMode(QListWidget.LayoutMode.Batched)
        self.setBatchSize(200)
        self.setIconSize(QSize(edge, edge))
        self.setFrameShape(QListWidget.Shape.NoFrame)
        self.cache.ready.connect(self._thumbnail_ready)
        self.cache.dropped.connect(self._thumbnail_dropped)
        self.itemActivated.connect(self._activated)
        self.itemSelectionChanged.connect(self._selection_changed)

        # Scrolling only marks the view dirty; the actual fetch happens once
        # the scroll settles, so a flick does not queue every row it passed.
        self._fetch_timer = QTimer(self)
        self._fetch_timer.setSingleShot(True)
        self._fetch_timer.setInterval(60)
        self._fetch_timer.timeout.connect(self.request_visible)
        self.verticalScrollBar().valueChanged.connect(self._schedule_fetch)
        self.horizontalScrollBar().valueChanged.connect(self._schedule_fetch)

    # -- population ----------------------------------------------------
    def set_paths(self, paths, decorations: dict | None = None) -> None:
        self.blockSignals(True)
        self.setUpdatesEnabled(False)
        try:
            self.clear()
            self._rows.clear()
            self._decorations = dict(decorations or {})
            blank = QIcon(self._placeholder)
            for path in paths:
                item = QListWidgetItem()
                item.setData(_ROLE_PATH, str(path))
                item.setToolTip(str(path))
                item.setIcon(blank)
                self._label(item, Path(path))
                self.addItem(item)
                self._rows[str(path)] = item
        finally:
            self.setUpdatesEnabled(True)
            self.blockSignals(False)
        self._schedule_fetch()

    def set_paths_chunked(self, paths, decorations: dict | None = None,
                          progress=None, cancel=None, chunk: int = 500) -> bool:
        """Fill a very long list without the window ever looking stuck.

        Returns False if the caller cancelled part-way, in which case the view
        holds whatever was built so far.
        """
        paths = list(paths)
        total = max(1, len(paths))
        self.blockSignals(True)
        self.clear()
        self._rows.clear()
        self._decorations = dict(decorations or {})
        blank = QIcon(self._placeholder)
        finished = True
        try:
            for start in range(0, len(paths), chunk):
                if cancel is not None and cancel():
                    finished = False
                    break
                self.setUpdatesEnabled(False)
                for path in paths[start:start + chunk]:
                    item = QListWidgetItem()
                    item.setData(_ROLE_PATH, str(path))
                    item.setToolTip(str(path))
                    item.setIcon(blank)
                    self._label(item, Path(path))
                    self.addItem(item)
                    self._rows[str(path)] = item
                self.setUpdatesEnabled(True)
                if progress is not None:
                    progress("", int(min(100, (start + chunk) * 100 / total)))
        finally:
            self.setUpdatesEnabled(True)
            self.blockSignals(False)
        self._schedule_fetch()
        return finished

    def _label(self, item: QListWidgetItem, path: Path) -> None:
        """Subclass hook: what the caption under the tile says."""

    def remove_path(self, path: str | Path) -> int:
        """Drop one row. Returns the position it held, or -1.

        Rebuilding the whole list after every classification was turning each
        keystroke into O(number of files).
        """
        item = self._rows.pop(str(path), None)
        if item is None:
            return -1
        row = self.row(item)
        self.blockSignals(True)
        self.takeItem(row)
        self.blockSignals(False)
        return row

    def insert_path(self, path: str | Path, row: int, decoration: dict | None = None) -> None:
        key = str(path)
        if key in self._rows:
            return
        if decoration:
            self._decorations[key] = decoration
        item = QListWidgetItem()
        item.setData(_ROLE_PATH, key)
        item.setToolTip(key)
        item.setIcon(QIcon(self._placeholder))
        self._label(item, Path(key))
        self.blockSignals(True)
        self.insertItem(max(0, min(row, self.count())), item)
        self.blockSignals(False)
        self._rows[key] = item
        self._schedule_fetch()

    def paths(self) -> list[str]:
        return [str(self.item(row).data(_ROLE_PATH)) for row in range(self.count())]

    # -- lazy loading --------------------------------------------------
    def _schedule_fetch(self) -> None:
        self._fetch_timer.start()

    def showEvent(self, event) -> None:              # noqa: N802 - Qt naming
        super().showEvent(event)
        self._schedule_fetch()

    def resizeEvent(self, event) -> None:            # noqa: N802 - Qt naming
        super().resizeEvent(event)
        self._schedule_fetch()

    def visible_rows(self) -> tuple[int, int]:
        """First and last row the viewport currently shows.

        Walks forward from the first visible index rather than scanning the
        whole model, so the cost is proportional to what is on screen.
        """
        total = self.count()
        if not total:
            return (0, -1)
        viewport = self.viewport().rect()
        first_index = self.indexAt(viewport.topLeft())
        start = first_index.row() if first_index.isValid() else 0
        if start < 0:
            start = 0
        end = start
        bottom = viewport.bottom()
        right = viewport.right()
        for row in range(start, min(total, start + _MAX_PROBE)):
            rect = self.visualItemRect(self.item(row))
            if rect.isNull():
                break
            if rect.top() > bottom or (self.flow() == QListWidget.Flow.LeftToRight
                                       and not self.isWrapping() and rect.left() > right):
                break
            end = row
        return (start, end)

    def request_visible(self) -> None:
        total = self.count()
        if not total or not self.isVisible():
            return
        start, end = self.visible_rows()
        low, high = viewport.band(start, end, total, _OVERSCAN)
        wanted = [str(self.item(row).data(_ROLE_PATH)) for row in range(low, high + 1)]
        # Anything outside this band stops being worth a worker's time.
        self.cache.set_wanted(wanted, self.edge)
        for key in wanted:
            pixmap = self.cache.request(key, self.edge)
            if pixmap is not None:
                self._apply_icon(key, pixmap)

    def _apply_icon(self, key: str, pixmap: QPixmap) -> None:
        item = self._rows.get(key)
        if item is not None:
            item.setIcon(QIcon(self._decorated(key, pixmap)))

    def _decorated(self, key: str, pixmap: QPixmap) -> QPixmap:
        extra = self._decorations.get(key)
        path = Path(key)
        duration = ""
        if mediatypes.is_video(path):
            info = metadata.read(path)
            duration = metadata.format_duration(info.duration)
        options = {"raw": mediatypes.is_raw(path), "duration": duration}
        if extra:
            options.update(extra)
        return decorate(pixmap, **options)

    def _thumbnail_ready(self, path: str, edge: int, pixmap: QPixmap) -> None:
        if edge != self.edge:
            return
        self._apply_icon(path, pixmap)

    def _thumbnail_dropped(self, edge: int) -> None:
        """Something was abandoned mid-flight; ask again for what is on screen."""
        if edge == self.edge:
            self._schedule_fetch()

    def set_decoration(self, path: str, **options) -> None:
        self._decorations[str(path)] = options
        cached = self.cache.peek(path, self.edge)
        if cached is not None:
            self._apply_icon(str(path), cached)

    # -- selection -----------------------------------------------------
    def _activated(self, item: QListWidgetItem) -> None:
        self.path_activated.emit(str(item.data(_ROLE_PATH)))

    def _selection_changed(self) -> None:
        paths = self.selected_paths()
        if paths:
            self.path_selected.emit(paths[0])

    def selected_paths(self) -> list[str]:
        return [str(item.data(_ROLE_PATH)) for item in self.selectedItems()]

    def show_path(self, path: str | Path) -> None:
        item = self._rows.get(str(path))
        if item is None:
            return
        self.blockSignals(True)
        self.setCurrentItem(item)
        self.blockSignals(False)
        self.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtCenter)
        self._schedule_fetch()

    def set_edge(self, edge: int) -> None:
        if edge == self.edge:
            return
        self.edge = edge
        self._placeholder = pending_pixmap(QSize(edge, edge))
        self.setIconSize(QSize(edge, edge))
        keys = self.paths()
        selected = self.selected_paths()
        self.set_paths(keys, self._decorations)
        # setSelected fires itemSelectionChanged synchronously, so restoring a
        # selection one item at a time would emit a burst of half-built states
        # on every tick of the size slider.
        self.blockSignals(True)
        for path in selected:
            item = self._rows.get(path)
            if item is not None:
                item.setSelected(True)
        self.blockSignals(False)
        if selected:
            self._selection_changed()


class Filmstrip(_Browser):
    """A window of neighbours under the preview, for jumping about by eye."""

    def __init__(self, cache: ThumbnailCache, parent=None) -> None:
        super().__init__(cache, 84, parent)
        self.setObjectName("filmstrip")
        self.setFlow(QListWidget.Flow.LeftToRight)
        self.setWrapping(False)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setFixedHeight(104)
        self.setSpacing(2)
        self.setGridSize(QSize(96, 82))
        self.setIconSize(QSize(84, 64))
        self._all: list[str] = []
        self._window = (0, 0)

    def set_queue(self, paths, current_index: int, decorations: dict | None = None) -> None:
        """Show a window of the queue centred on *current_index*."""
        self._all = [str(p) for p in paths]
        self._show_window(current_index, decorations, force=True)

    def follow(self, current_index: int, decorations: dict | None = None) -> None:
        self._show_window(current_index, decorations, force=False)

    def _show_window(self, index: int, decorations: dict | None, force: bool) -> None:
        total = len(self._all)
        if not total:
            if force:
                self.set_paths([], decorations)
                self._window = (0, 0)
            return
        index = viewport.clamp_index(index, total)
        low, high = viewport.window(index, total, FILMSTRIP_WINDOW)
        # Rebuild only once the cursor nears the edge of the loaded window.
        if not force and self.count() and not viewport.needs_rebuild(
                index, self._window, total=total):
            self.show_path(self._all[index])
            return
        self._window = (low, high)
        self.set_paths(self._all[low:high], decorations)
        self.show_path(self._all[index])

    def drop(self, path: str | Path) -> None:
        """Remove one item, keeping the loaded window aligned with the queue.

        A bulk classification in the grid removes items from anywhere, not just
        from inside the window, so the adjustment depends on where the item was.
        Letting the window collapse would silently turn every later step back
        into a full rebuild.
        """
        key = str(path)
        try:
            position = self._all.index(key)
        except ValueError:
            self.remove_path(key)
            return
        self._all.pop(position)
        self.remove_path(key)
        low, high = self._window
        if position < low:
            low, high = max(0, low - 1), max(0, high - 1)
        elif position < high:
            high = max(low, high - 1)
        self._window = (low, high)

    def insert(self, path: str | Path, row: int, decoration: dict | None = None) -> None:
        """Put one item back, keeping the loaded window aligned with the queue.

        The counterpart of `drop`. Rebuilding the strip instead turned an undo
        into a full repopulate, which is what `drop` exists to avoid.
        """
        key = str(path)
        if key in self._all:
            return
        position = max(0, min(int(row), len(self._all)))
        self._all.insert(position, key)
        low, high = self._window
        if position < low:
            self._window = (low + 1, high + 1)
            return
        if position <= high:
            self.insert_path(key, position - low, decoration)
            self._window = (low, high + 1)


class ThumbnailGrid(_Browser):
    """Many at once, with multi-select so a whole burst files in one keypress."""

    selection_changed = Signal(int)

    def __init__(self, cache: ThumbnailCache, parent=None) -> None:
        super().__init__(cache, 168, parent)
        self.setObjectName("grid")
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setWrapping(True)
        self.setSpacing(4)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.show_names = True
        self.itemSelectionChanged.connect(
            lambda: self.selection_changed.emit(len(self.selectedItems())))
        self._sync_grid()

    def _sync_grid(self) -> None:
        label = 22 if self.show_names else 0
        self.setGridSize(QSize(self.edge + 18, self.edge + 18 + label))

    def _label(self, item: QListWidgetItem, path: Path) -> None:
        item.setText(path.name if self.show_names else "")
        item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)

    def set_edge(self, edge: int) -> None:
        super().set_edge(edge)
        self._sync_grid()

    def set_show_names(self, enabled: bool) -> None:
        self.show_names = bool(enabled)
        for row in range(self.count()):
            item = self.item(row)
            self._label(item, Path(str(item.data(_ROLE_PATH))))
        self._sync_grid()

    def select_all_paths(self, paths) -> None:
        self.blockSignals(True)
        self.clearSelection()
        for path in paths:
            item = self._rows.get(str(path))
            if item is not None:
                item.setSelected(True)
        self.blockSignals(False)
        self.selection_changed.emit(len(self.selectedItems()))

    def invert_selection(self) -> None:
        self.blockSignals(True)
        for row in range(self.count()):
            item = self.item(row)
            item.setSelected(not item.isSelected())
        self.blockSignals(False)
        self.selection_changed.emit(len(self.selectedItems()))
