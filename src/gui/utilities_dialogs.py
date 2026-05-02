"""Dialogs for HDF5 group/dataset create, rename, and attribute utilities."""

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

_DTYPES = [
    "float32",
    "float64",
    "int8",
    "int16",
    "int32",
    "int64",
    "uint8",
    "uint16",
    "uint32",
    "uint64",
    "bool",
    "string",
]


class RenameDialog(QDialog):
    """Prompt the user for a new name for a group or dataset."""

    def __init__(self, parent: QWidget | None, current_name: str) -> None:
        super().__init__(parent)
        self.setWindowTitle("Rename")
        self.setMinimumWidth(360)

        outer = QVBoxLayout()
        form = QFormLayout()
        self._le_name = QLineEdit(current_name)
        self._le_name.selectAll()
        form.addRow("New name:", self._le_name)
        outer.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)
        self.setLayout(outer)

    @property
    def new_name(self) -> str:
        return self._le_name.text().strip()


class NewGroupDialog(QDialog):
    """Prompt the user for the name of a new HDF5 group."""

    def __init__(self, parent: QWidget | None, parent_path: str) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Group")
        self.setMinimumWidth(380)

        outer = QVBoxLayout()
        form = QFormLayout()
        form.addRow("Parent group:", QLabel(parent_path))
        self._le_name = QLineEdit()
        self._le_name.setPlaceholderText("group_name")
        form.addRow("Name:", self._le_name)
        outer.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)
        self.setLayout(outer)

    @property
    def name(self) -> str:
        return self._le_name.text().strip()


class NewDatasetDialog(QDialog):
    """Prompt the user for the parameters of a new HDF5 dataset."""

    def __init__(self, parent: QWidget | None, parent_path: str) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Dataset")
        self.setMinimumWidth(440)

        outer = QVBoxLayout()
        form = QFormLayout()

        form.addRow("Parent group:", QLabel(parent_path))

        self._le_name = QLineEdit()
        self._le_name.setPlaceholderText("dataset_name")
        form.addRow("Name:", self._le_name)

        self._cb_dtype = QComboBox()
        self._cb_dtype.addItems(_DTYPES)
        form.addRow("Data type:", self._cb_dtype)

        self._le_shape = QLineEdit()
        self._le_shape.setPlaceholderText("e.g. 100  or  10,20  (empty = scalar)")
        form.addRow("Shape:", self._le_shape)

        self._le_fill = QLineEdit("0")
        self._le_fill.setPlaceholderText("fill value (ignored for string type)")
        form.addRow("Fill value:", self._le_fill)

        outer.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)
        self.setLayout(outer)

    @property
    def name(self) -> str:
        return self._le_name.text().strip()

    @property
    def dtype(self) -> str:
        return self._cb_dtype.currentText()

    @property
    def shape(self) -> tuple[int, ...]:
        text = self._le_shape.text().strip()
        if not text:
            return ()
        parts = [p.strip() for p in text.split(",") if p.strip()]
        return tuple(int(p) for p in parts)

    @property
    def fill_value(self) -> float:
        try:
            return float(self._le_fill.text().strip())
        except ValueError:
            return 0.0
