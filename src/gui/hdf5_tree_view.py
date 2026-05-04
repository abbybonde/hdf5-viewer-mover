"""QTreeView subclass with internal HDF5 drag-and-drop move support."""

from PyQt6.QtCore import QModelIndex, Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
from PyQt6.QtWidgets import QAbstractItemView, QTreeView, QWidget


class HDF5TreeView(QTreeView):
    """Tree view that emits ``hdf5_move_requested`` when an HDF5 item is
    dragged and dropped onto a group or file-root entry.

    External file drops (dragging an .h5 file from the desktop) are
    deliberately ignored here so they propagate to the parent MainWindow
    which already handles them.
    """

    hdf5_move_requested = pyqtSignal(QModelIndex, QModelIndex)  # (src, dst) proxy indices

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._drag_src_idx: QModelIndex | None = None

    # ------------------------------------------------------------------
    # Drag initiation

    def startDrag(self, _supported_actions: Qt.DropAction) -> None:  # type: ignore[override]
        idxs = self.selectedIndexes()
        if not idxs:
            return
        src = idxs[0].sibling(idxs[0].row(), 0)
        # Only allow dragging actual HDF5 objects (groups/datasets), not the
        # top-level file entries whose parent().data() is None.
        if not src.isValid() or src.parent().data() is None:
            self._drag_src_idx = None
            return
        self._drag_src_idx = src
        super().startDrag(Qt.DropAction.MoveAction)

    # ------------------------------------------------------------------
    # Drop handling

    def dragEnterEvent(self, event: QDragEnterEvent | None) -> None:
        if event is None:
            return
        # Accept only internal drags that originated from this widget.
        if self._drag_src_idx is not None and self._drag_src_idx.isValid() and event.source() is self:
            event.acceptProposedAction()
        else:
            # External file drag or stale state — reset and let the
            # parent window handle it.
            self._drag_src_idx = None
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent | None) -> None:
        if event is None:
            return
        if self._drag_src_idx is None:
            event.ignore()
            return
        if self._valid_drop_target(event.pos()).isValid():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent | None) -> None:
        if event is None:
            return
        if self._drag_src_idx is None:
            event.ignore()
            return
        dst = self._valid_drop_target(event.pos())
        if dst.isValid() and self._drag_src_idx.isValid():
            self.hdf5_move_requested.emit(self._drag_src_idx, dst)
        # Always ignore so Qt never modifies the underlying model directly.
        event.ignore()
        self._drag_src_idx = None

    # ------------------------------------------------------------------

    def _valid_drop_target(self, pos) -> QModelIndex:
        """Column-0 index at *pos* if it is a group or file-root — else invalid."""
        dst = self.indexAt(pos)
        if not dst.isValid():
            return QModelIndex()
        dst = dst.sibling(dst.row(), 0)
        type_text = (dst.sibling(dst.row(), 1).data() or "")
        if type_text in ("Group", "HDF5 File") or dst.parent().data() is None:
            return dst
        return QModelIndex()
