"""Per-dimension slice control widget for HDF5 dataset viewing."""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class SliceControlWidget(QGroupBox):
    """Shows one row per dataset dimension; each row can be 'All' or a fixed index.

    Emits ``sliceChanged`` whenever the user adjusts any control so the parent
    can re-plot with the new slice.
    """

    sliceChanged = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Slice / Dimensions", parent)
        self._rows: list[tuple[QCheckBox, QSpinBox]] = []

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setMaximumHeight(160)

        outer = QVBoxLayout()
        outer.setContentsMargins(4, 4, 4, 4)
        outer.addWidget(self._scroll)
        self.setLayout(outer)
        self.setVisible(False)

    # ------------------------------------------------------------------

    def set_shape(self, shape: tuple[int, ...]) -> None:
        """Rebuild controls for *shape*.  Hides itself for scalar / 1-D data."""
        if len(shape) <= 1:
            self.setVisible(False)
            return

        self._rows = []
        inner = QWidget()
        grid = QGridLayout()
        grid.setContentsMargins(2, 2, 2, 2)
        grid.setColumnMinimumWidth(0, 130)

        for i, size in enumerate(shape):
            lbl = QLabel(f"Dim {i}  [0 … {size - 1}]")

            cb_all = QCheckBox("All")
            cb_all.setChecked(True)

            sb = QSpinBox()
            sb.setRange(0, max(0, size - 1))
            sb.setEnabled(False)
            sb.setMinimumWidth(70)

            # capture loop vars explicitly so lambdas close over the right objects
            def _on_all_toggled(checked: bool, s: QSpinBox = sb) -> None:
                s.setEnabled(not checked)
                self.sliceChanged.emit()

            cb_all.toggled.connect(_on_all_toggled)
            sb.valueChanged.connect(lambda _val: self.sliceChanged.emit())

            self._rows.append((cb_all, sb))
            grid.addWidget(lbl, i, 0)
            grid.addWidget(cb_all, i, 1)
            grid.addWidget(sb, i, 2)

        inner.setLayout(grid)
        self._scroll.setWidget(inner)
        self.setVisible(True)

    def reset(self) -> None:
        """Clear controls and hide the widget."""
        self._rows = []
        self._scroll.setWidget(QWidget())
        self.setVisible(False)

    # ------------------------------------------------------------------

    @property
    def slice_tuple(self) -> tuple:
        """Numpy-compatible slice for the current settings.

        ``slice(None)`` for "All" dims, an ``int`` index for pinned dims.
        Returns an empty tuple when there are no controls (widget hidden).
        """
        return tuple(slice(None) if cb.isChecked() else sb.value() for cb, sb in self._rows)
