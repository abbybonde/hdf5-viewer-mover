"""Dialog for selecting the destination of a copy/move operation."""

# Copyright (C) 2023 Dennis Lönard
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import pathlib

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class CopyMoveDialog(QDialog):
    """Modal dialog that collects the destination for a copy/move operation."""

    def __init__(
        self,
        parent: QWidget | None,
        operation: str,
        src_file: pathlib.Path,
        src_obj_path: str,
    ) -> None:
        """Create the dialog.

        :param parent: Parent widget.
        :param operation: Either ``"Copy"`` or ``"Move"``.
        :param src_file: Source HDF5 file path (shown read-only for reference).
        :param src_obj_path: HDF5 path of the object being copied/moved.
        """
        super().__init__(parent)

        src_name = src_obj_path.rsplit("/", 1)[-1] if "/" in src_obj_path else src_obj_path

        self.setWindowTitle(f"{operation} HDF5 Object")
        self.setMinimumWidth(520)

        outer = QVBoxLayout()
        form = QFormLayout()

        # Source info (read-only)
        lbl_src_file = QLabel(str(src_file))
        lbl_src_file.setWordWrap(True)
        form.addRow("Source File:", lbl_src_file)

        lbl_src_path = QLabel(src_obj_path)
        form.addRow("Source Path:", lbl_src_path)

        # Destination file (pre-filled with source; user can change)
        dst_file_row = QHBoxLayout()
        self._le_dst_file = QLineEdit(str(src_file))
        btn_browse = QPushButton("Browse…")
        btn_browse.clicked.connect(self._browse_dst_file)
        dst_file_row.addWidget(self._le_dst_file)
        dst_file_row.addWidget(btn_browse)
        form.addRow("Destination File:", dst_file_row)

        # Destination group (default "/")
        self._le_dst_group = QLineEdit("/")
        form.addRow("Destination Group:", self._le_dst_group)

        # Destination name (default = source object's own name)
        self._le_dst_name = QLineEdit(src_name)
        form.addRow("Destination Name:", self._le_dst_name)

        outer.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

        self.setLayout(outer)

    # ----- private -----

    def _browse_dst_file(self) -> None:
        """Open a file-save dialog so the user can pick (or create) a destination file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Select Destination HDF5 File",
            self._le_dst_file.text(),
            "HDF5 File (*.h5 *.hdf5);;All Files (*.*)",
        )
        if file_path:
            self._le_dst_file.setText(file_path)

    # ----- properties -----

    @property
    def dst_file(self) -> pathlib.Path:
        """Selected destination file path."""
        return pathlib.Path(self._le_dst_file.text().strip())

    @property
    def dst_group(self) -> str:
        """Destination group path (defaults to ``"/"`` if empty)."""
        group = self._le_dst_group.text().strip()
        return group if group else "/"

    @property
    def dst_name(self) -> str:
        """Destination object name."""
        return self._le_dst_name.text().strip()


class MultiCopyDialog(QDialog):
    """Copy an HDF5 object to one or more destination files simultaneously."""

    def __init__(
        self,
        parent: QWidget | None,
        src_file: pathlib.Path,
        src_obj_path: str,
    ) -> None:
        super().__init__(parent)
        src_name = src_obj_path.rsplit("/", 1)[-1] if "/" in src_obj_path else src_obj_path

        self.setWindowTitle("Copy HDF5 Object")
        self.setMinimumWidth(560)
        self.setMinimumHeight(420)

        outer = QVBoxLayout()
        form = QFormLayout()

        lbl_src_file = QLabel(str(src_file))
        lbl_src_file.setWordWrap(True)
        form.addRow("Source File:", lbl_src_file)
        form.addRow("Source Path:", QLabel(src_obj_path))
        outer.addLayout(form)

        outer.addWidget(QLabel("Destination Files:"))
        self._list = QListWidget()
        self._list.addItem(str(src_file))  # sensible default
        self._list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        outer.addWidget(self._list)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("Add File…")
        btn_add.clicked.connect(self._add_file)
        btn_remove = QPushButton("Remove Selected")
        btn_remove.clicked.connect(self._remove_selected)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_remove)
        btn_row.addStretch()
        outer.addLayout(btn_row)

        form2 = QFormLayout()
        self._le_dst_group = QLineEdit("/")
        form2.addRow("Destination Group:", self._le_dst_group)
        self._le_dst_name = QLineEdit(src_name)
        form2.addRow("Destination Name:", self._le_dst_name)
        outer.addLayout(form2)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

        self.setLayout(outer)

    def _add_file(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Select Destination HDF5 File",
            "",
            "HDF5 File (*.h5 *.hdf5);;All Files (*.*)",
        )
        if not file_path:
            return
        for i in range(self._list.count()):
            if self._list.item(i) is not None and self._list.item(i).text() == file_path:  # type: ignore[union-attr]
                return
        self._list.addItem(file_path)

    def _remove_selected(self) -> None:
        for item in self._list.selectedItems():
            self._list.takeItem(self._list.row(item))

    @property
    def dst_files(self) -> list[pathlib.Path]:
        """All destination file paths in the list."""
        return [pathlib.Path(self._list.item(i).text()) for i in range(self._list.count()) if self._list.item(i) is not None]  # type: ignore[union-attr]

    @property
    def dst_group(self) -> str:
        group = self._le_dst_group.text().strip()
        return group if group else "/"

    @property
    def dst_name(self) -> str:
        return self._le_dst_name.text().strip()
