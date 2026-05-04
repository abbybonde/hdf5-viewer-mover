"""Main Window of the GUI."""

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

import logging
import os
import pathlib
import sys
from typing import Any, Generator

import h5py
import numpy as np
import pyqtgraph as pg
from natsort import natsorted
from PyQt6.QtCore import QModelIndex, QPoint, QSettings, QSize, QSortFilterProxyModel, Qt, pyqtSlot
from PyQt6.QtGui import (
    QAction,
    QCloseEvent,
    QDragEnterEvent,
    QDropEvent,
    QIcon,
    QKeySequence,
    QShortcut,
    QStandardItem,
    QStandardItemModel,
)
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QCompleter,
    QDockWidget,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableView,
    QTextBrowser,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from src.gui.about_page import AboutPage
from src.gui.copy_move_dialog import CopyMoveDialog, MultiCopyDialog
from src.gui.hdf5_tree_view import HDF5TreeView
from src.gui.slice_control import SliceControlWidget
from src.gui.table_model import DataTable, TableModel
from src.gui.utilities_dialogs import NewDatasetDialog, NewGroupDialog, RenameDialog
from src.img.img_path import img_path
from src.lib_h5.copy_move_ops import copy_hdf5_object, move_hdf5_object
from src.lib_h5.dataset_types import H5DatasetType
from src.lib_h5.file_size import file_size_to_str
from src.lib_h5.group_dataset_ops import (
    create_hdf5_dataset,
    create_hdf5_group,
    delete_hdf5_object,
    rename_hdf5_object,
)


class MainWindow(QMainWindow):
    """Start Main Window of the GUI."""

    def __init__(self) -> None:
        """Start Main Window of the GUI."""
        super().__init__(flags=Qt.WindowType.Window)
        self.setAcceptDrops(True)

        # Variables
        self.cur_file = pathlib.Path()
        self.cur_obj_path = ""
        self.icon_dir = img_path()

        # Appearance
        settings = QSettings()
        self.setMinimumSize(1400, 700)
        self.setWindowTitle("HDF5 Viewer")
        self.resize(settings.value("main_window/size", defaultValue=QSize(1400, 700)))
        self.move(settings.value("main_window/position", defaultValue=QPoint(300, 150)))
        self.setWindowIcon(QIcon(str(pathlib.Path(self.icon_dir, "file.svg"))))

        # Layout Right Side
        self.table_model_dataset = TableModel(header=["Attribute", "Value"])
        self.table_view_dataset = QTableView()
        self.table_view_dataset.setMinimumWidth(700)
        self.table_view_dataset.setModel(self.table_model_dataset)
        self.table_view_dataset.setColumnWidth(1, 300)
        self.plot_wgt_dataset = pg.PlotWidget()

        self.dock_table = QDockWidget()
        self.dock_table.setWindowTitle("Attributes")
        self.dock_table.setWidget(self.table_view_dataset)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_table)
        self.dock_plot = QDockWidget()
        self.dock_plot.setWindowTitle("Data")
        self.dock_plot.setWidget(self.plot_wgt_dataset)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_plot)

        # Center Layout
        self.tree_view_file = HDF5TreeView()
        self.tree_view_file.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_view_file.customContextMenuRequested.connect(self._handle_tree_menu)
        self.tree_model_file = QStandardItemModel()
        self.tree_model_file.setHorizontalHeaderLabels(["Name", "Type"])
        self.tree_model_file_proxy = QSortFilterProxyModel()
        self.tree_model_file_proxy.setRecursiveFilteringEnabled(True)

        self.tree_model_file_proxy.setSourceModel(self.tree_model_file)
        self.tree_view_file.setModel(self.tree_model_file_proxy)
        self.tree_view_file.setColumnWidth(0, 500)
        self.tree_view_file.clicked.connect(self._handle_item_changed)
        self.tree_view_file.hdf5_move_requested.connect(self._handle_drag_drop_move)

        # Operation button bar
        def _vsep() -> QFrame:
            f = QFrame()
            f.setFrameShape(QFrame.Shape.VLine)
            f.setFrameShadow(QFrame.Shadow.Sunken)
            return f

        self.btn_new_group = QPushButton("+ Group")
        self.btn_new_group.setToolTip("Create a new group inside the selected item")
        self.btn_new_group.setEnabled(False)
        self.btn_new_group.clicked.connect(self._handle_btn_new_group)

        self.btn_new_dataset = QPushButton("+ Dataset")
        self.btn_new_dataset.setToolTip("Create a new dataset inside the selected group")
        self.btn_new_dataset.setEnabled(False)
        self.btn_new_dataset.clicked.connect(self._handle_btn_new_dataset)

        self.btn_rename = QPushButton("Rename")
        self.btn_rename.setToolTip("Rename selected item  [F2]")
        self.btn_rename.setEnabled(False)
        self.btn_rename.clicked.connect(self._handle_btn_rename)

        self.btn_delete = QPushButton("Delete")
        self.btn_delete.setToolTip("Delete selected item  [Del]")
        self.btn_delete.setEnabled(False)
        self.btn_delete.clicked.connect(self._handle_btn_delete)

        self.btn_copy_to = QPushButton("Copy To…")
        self.btn_copy_to.setToolTip("Copy selected item to another location")
        self.btn_copy_to.setEnabled(False)
        self.btn_copy_to.clicked.connect(self._handle_btn_copy)

        self.btn_move_to = QPushButton("Move To…")
        self.btn_move_to.setToolTip("Move selected item to another location")
        self.btn_move_to.setEnabled(False)
        self.btn_move_to.clicked.connect(self._handle_btn_move)

        lyt_ops = QHBoxLayout()
        lyt_ops.setSpacing(4)
        lyt_ops.setContentsMargins(0, 2, 0, 2)
        lyt_ops.addWidget(self.btn_new_group)
        lyt_ops.addWidget(self.btn_new_dataset)
        lyt_ops.addWidget(_vsep())
        lyt_ops.addWidget(self.btn_rename)
        lyt_ops.addWidget(self.btn_delete)
        lyt_ops.addWidget(_vsep())
        lyt_ops.addWidget(self.btn_copy_to)
        lyt_ops.addWidget(self.btn_move_to)
        lyt_ops.addStretch()

        # Keyboard shortcuts for common operations
        QShortcut(QKeySequence(Qt.Key.Key_F2), self).activated.connect(self._handle_btn_rename)
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self).activated.connect(self._handle_btn_delete)

        self.btn_filter_regex = QPushButton("RegExp")
        self.btn_filter_regex.setCheckable(True)
        self.btn_filter_regex.clicked.connect(self._handle_filter_changed)
        self.btn_filter_case = QPushButton("Cc")
        self.btn_filter_case.setCheckable(True)
        self.btn_filter_case.clicked.connect(self._handle_filter_changed)
        self.le_filter = QLineEdit()
        self.le_filter.setPlaceholderText("Search in all files (press 'f' to focus)")
        self.act_filter = QShortcut(QKeySequence(Qt.Key.Key_F), self)
        self.act_filter.activated.connect(self.le_filter.setFocus)
        self.le_filter.textEdited.connect(self._handle_filter_changed)
        self.completer = QCompleter()
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.le_filter.setCompleter(self.completer)

        lyt_plot_type = QFormLayout()
        self.cb_plot_type = QComboBox()
        self.cb_plot_type.addItems(["Auto", "String", "Array1D", "Array2D", "ImageRGB", "Table"])
        self.cb_plot_type.currentTextChanged.connect(self._handle_plot_type_changed)
        lyt_plot_type.addRow("Plot as", self.cb_plot_type)

        lyt_filter = QHBoxLayout()
        lyt_filter.addWidget(self.btn_filter_regex)
        lyt_filter.addWidget(self.btn_filter_case)
        lyt_filter.addWidget(self.le_filter)

        self.slice_control = SliceControlWidget()
        self.slice_control.sliceChanged.connect(lambda: self._plot_data(self.cb_plot_type.currentText()))

        lyt_file_tree = QVBoxLayout()
        lyt_file_tree.addLayout(lyt_ops)
        lyt_file_tree.addWidget(self.tree_view_file)
        lyt_file_tree.addLayout(lyt_filter)
        lyt_file_tree.addLayout(lyt_plot_type)
        lyt_file_tree.addWidget(self.slice_control)

        wgt_total = QHBoxLayout()
        wgt_total.addLayout(lyt_file_tree)
        # wgt_total.addLayout(self.lyt_dataset)
        wgt_central = QWidget()
        wgt_central.setLayout(wgt_total)
        self.setCentralWidget(wgt_central)

        # File Menu
        if (menu_bar := self.menuBar()) is None:
            return
        if (mbr_file := menu_bar.addMenu("&File")) is not None:
            act_file = QAction("&Open File...", self)
            act_file.setIcon(QIcon(str(pathlib.Path(self.icon_dir, "file.svg"))))
            act_file.setShortcut("Ctrl+O")
            act_file.triggered.connect(self._handle_action_open_file)
            mbr_file.addAction(act_file)
            act_open_folder = QAction("&Open Folder...", self)
            act_open_folder.setIcon(QIcon(str(pathlib.Path(self.icon_dir, "group.svg"))))
            act_open_folder.triggered.connect(self._handle_action_open_folder)
            mbr_file.addAction(act_open_folder)
            act_clear_files = QAction("&Close all Files", self)
            act_clear_files.setIcon(QIcon(str(pathlib.Path(self.icon_dir, "file_clear.svg"))))
            act_clear_files.triggered.connect(self._handle_action_clear_files)
            mbr_file.addAction(act_clear_files)
            mbr_file.addSeparator()
            act_quit = QAction("&Quit", self)
            act_quit.setIcon(QIcon(str(pathlib.Path(self.icon_dir, "quit.svg"))))
            act_quit.setShortcut("Ctrl+Q")
            act_quit.triggered.connect(self._handle_close)
            mbr_file.addAction(act_quit)

        # Help Menu
        if (mbr_help := menu_bar.addMenu("&Help")) is not None:
            act_about = QAction("&About Page...", self)
            act_about.setIcon(QIcon(os.path.join(self.icon_dir, "about.svg")))
            act_about.triggered.connect(self._handle_action_about)
            mbr_help.addAction(act_about)

        # Open File when double-clicking
        if len(sys.argv) > 1:
            self._open_file(pathlib.Path(sys.argv[0]))
        for file in settings.value("settings/last_opened_files", ()):
            self._open_file(file)

    @staticmethod
    def iter_items(root: QStandardItem) -> Generator[Any, Any, None]:
        """Iterate recursively through all children of a QStandardItem."""

        def recurse(parent: QStandardItem) -> Generator[Any, Any, None]:
            for row in range(parent.rowCount()):
                if (child := parent.child(row, 0)) is not None:
                    yield child.text()
                    if child.hasChildren():
                        yield from recurse(child)

        if root is not None:
            yield from recurse(root)

    @property
    def selected_item(self) -> tuple[pathlib.Path, str, Any]:
        """Tuple of selected file name, object name and object type."""
        if not self.cur_obj_path:
            obj_type = h5py.File
        else:
            with h5py.File(self.cur_file, "r") as file:
                obj_type = type(file[self.cur_obj_path])

        return self.cur_file, self.cur_obj_path, obj_type

    @property
    def opened_files(self) -> tuple[pathlib.Path, ...]:
        """Currently opened files."""
        file_paths = []
        for i in range(self.tree_model_file.rowCount()):
            if (item := self.tree_model_file.item(i, 0)) is not None:
                file_paths.append(pathlib.Path(item.text()))
        return tuple(file_paths)

    def _open_file(self, file_path: pathlib.Path) -> None:
        """
        Open one File.

        :param str file_path: File Path
        """
        logging.info(f"Open file '{file_path}'")
        try:
            # Load TreeModel from File
            with h5py.File(file_path, "r") as file:
                parent_name = QStandardItem(str(file_path))
                parent_name.setEditable(False)
                parent_text = QStandardItem("HDF5 File")
                parent_text.setEditable(False)
                parent_text.setIcon(QIcon(str(pathlib.Path(self.icon_dir, "file.svg"))))
                self._hdf5_recursion(hdf5_object=file, root=parent_name, parent=parent_name)
                self.tree_model_file.appendRow([parent_name, parent_text])
        except (OSError, ValueError) as err:
            logging.warning(f"Failed to open file. Error: '{err}'")

        if (root := self.tree_model_file.invisibleRootItem()) is not None:
            self.completer = QCompleter(list(self.iter_items(root)))
            self.completer.setCaseSensitivity(
                Qt.CaseSensitivity.CaseSensitive
                if self.btn_filter_case.isChecked()
                else Qt.CaseSensitivity.CaseInsensitive
            )
            self.le_filter.setCompleter(self.completer)

    def _hdf5_recursion(
        self,
        hdf5_object: h5py.File | h5py.Group | h5py.Dataset,
        root: QStandardItem,
        parent: QStandardItem,
    ) -> None:
        """Recursively go through hdf5 File and construct tree view model."""
        for name in natsorted(hdf5_object):
            value = hdf5_object[name]
            if isinstance(value, h5py.Group):
                child_name = QStandardItem(name)
                child_name.setEditable(False)
                child_type = QStandardItem("Group")
                child_type.setEditable(False)
                child_type.setIcon(QIcon(str(pathlib.Path(self.icon_dir, "group.svg"))))
                parent.appendRow([child_name, child_type])
                self._hdf5_recursion(value, root, child_name)
            elif isinstance(value, h5py.Dataset):
                child_name = QStandardItem(name)
                child_name.setEditable(False)
                child_type = QStandardItem("Dataset")
                child_type.setEditable(False)
                child_type.setIcon(QIcon(str(pathlib.Path(self.icon_dir, "dataset.svg"))))
                parent.appendRow([child_name, child_type])

    @pyqtSlot()
    def _plot_data(self, plot_type: str = "") -> None:
        """
        Update Plot Widget.

        :param str plot_type: Plot Type
        """
        if self.cur_file is None or not self.cur_obj_path or not os.path.exists(self.cur_file):
            return

        with h5py.File(self.cur_file, "r") as file:
            h5_obj = file[self.cur_obj_path]
            if isinstance(h5_obj, h5py.Group):
                data = np.array([name for name in file[self.cur_obj_path]])
                data_type = H5DatasetType.String
            if isinstance(h5_obj, h5py.Dataset):
                slice_tuple = self.slice_control.slice_tuple
                data = np.array(h5_obj[slice_tuple] if slice_tuple else h5_obj)
                if plot_type and plot_type != "Auto":
                    data_type = H5DatasetType.from_string(plot_type)
                else:
                    data_type = H5DatasetType.from_numpy_array(data)

        new_widget: QTextBrowser | pg.PlotWidget | pg.ImageView | QTableView | QWidget
        if data_type == H5DatasetType.String:
            if data.ndim == 0:
                label = data.item()
                if isinstance(label, bytes):
                    label = label.decode()
                label = str(label)
            else:
                label = str(data)
            new_widget = QTextBrowser()
            new_widget.setText(label)
        elif data_type == H5DatasetType.Array1D:
            if data.ndim == 2 and min(data.shape) == 1:
                data = data.ravel()
            new_widget = pg.PlotWidget()
            try:
                new_widget.plot(data)
            except Exception as err:
                logging.error(f"Failed plot dataset as '{plot_type}'. Error: '{err}'")
                return
        elif data_type == H5DatasetType.Array2D:
            new_widget = pg.ImageView()
            try:
                new_widget.setImage(data)
            except Exception as err:
                logging.error(f"Failed plot dataset as '{plot_type}'. Error: '{err}'")
                return
            new_widget.setColorMap(pg.colormap.get("inferno"))
        elif data_type == H5DatasetType.Table:
            new_widget = QTableView()
            model = DataTable(data)
            new_widget.setModel(model)
        elif data_type == H5DatasetType.ImageRGB:
            data = np.sum(data, axis=0)
            new_widget = pg.ImageView()
            try:
                new_widget.setImage(data)
            except Exception as err:
                logging.error(f"Failed plot dataset as '{plot_type}'. Error: '{err}'")
                return
            new_widget.setColorMap(pg.colormap.get("inferno"))
        else:
            new_widget = QWidget()

        # Replace old Plot Widget
        self.dock_plot.setWidget(new_widget)
        # self.lyt_dataset.replaceWidget(self.plot_wgt_dataset, new_widget)
        # self.plot_wgt_dataset.hide()
        # self.plot_wgt_dataset.destroy()
        # self.plot_wgt_dataset = new_widget

    # ----- Drag & Drop ----- #
    def dragEnterEvent(self, event: QDragEnterEvent | None) -> None:
        """Accept Drag Events for h5 and hdf5 files to initiate Drag & Drop Events."""
        if event is None:
            return
        if (mime_data := event.mimeData()) is None:
            return
        for file in mime_data.text().split("\n"):
            if len(file) == 0:
                continue
            if not file.split(".")[-1] in ["h5", "hdf5"]:
                return
        event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent | None) -> None:
        """Open Files that are dropped into Window."""
        if event is None:
            return
        if (mime_data := event.mimeData()) is None:
            return
        for file in mime_data.text().split("\n"):
            if sys.platform == "win32":
                file = file[8:]
            else:
                file = file.removeprefix("file:")
            self._open_file(pathlib.Path(file))
        event.acceptProposedAction()

    # ----- Button / keyboard helpers ----- #

    def _current_index(self) -> QModelIndex:
        """Column-0 proxy index of the currently selected tree item, or invalid."""
        idxs = self.tree_view_file.selectedIndexes()
        if not idxs:
            return QModelIndex()
        return idxs[0].sibling(idxs[0].row(), 0)

    def _update_buttons(self, index: QModelIndex) -> None:
        """Enable or disable operation buttons based on what is selected."""
        if not index.isValid():
            for btn in (self.btn_new_group, self.btn_new_dataset,
                        self.btn_rename, self.btn_delete,
                        self.btn_copy_to, self.btn_move_to):
                btn.setEnabled(False)
            return
        is_file_root = index.parent().data() is None
        obj_type = index.sibling(index.row(), 1).data() or ""
        is_group_like = is_file_root or obj_type == "Group"
        is_hdf5_obj = not is_file_root
        self.btn_new_group.setEnabled(is_group_like)
        self.btn_new_dataset.setEnabled(is_group_like)
        self.btn_rename.setEnabled(is_hdf5_obj)
        self.btn_delete.setEnabled(is_hdf5_obj)
        self.btn_copy_to.setEnabled(is_hdf5_obj)
        self.btn_move_to.setEnabled(is_hdf5_obj)

    def _handle_btn_new_group(self) -> None:
        idx = self._current_index()
        if idx.isValid():
            self._handle_new_group(idx)

    def _handle_btn_new_dataset(self) -> None:
        idx = self._current_index()
        if idx.isValid():
            self._handle_new_dataset(idx)

    def _handle_btn_rename(self) -> None:
        idx = self._current_index()
        if idx.isValid() and self.btn_rename.isEnabled():
            self._handle_rename(idx)

    def _handle_btn_delete(self) -> None:
        idx = self._current_index()
        if idx.isValid() and self.btn_delete.isEnabled():
            self._handle_delete(idx)

    def _handle_btn_copy(self) -> None:
        idx = self._current_index()
        if idx.isValid():
            self._handle_copy_to(idx)

    def _handle_btn_move(self) -> None:
        idx = self._current_index()
        if idx.isValid():
            self._handle_move_to(idx)

    def _handle_drag_drop_move(self, src_idx: QModelIndex, dst_idx: QModelIndex) -> None:
        """Move (or copy) an HDF5 item dropped onto a group or file root in the tree.

        Same-file drops always move.  Cross-file drops ask the user whether to
        copy or move before proceeding.
        """
        src_file, src_obj_path = self._get_path_from_index(src_idx)
        if not src_obj_path:
            return
        dst_file, dst_obj_path = self._get_path_from_index(dst_idx)
        dst_group = dst_obj_path if dst_obj_path else "/"
        src_name = src_obj_path.rsplit("/", 1)[-1]

        # No-op: dropping onto the same parent group in the same file
        src_parent = src_obj_path.rstrip("/").rsplit("/", 1)[0] or "/"
        if dst_file.resolve() == src_file.resolve() and dst_group.rstrip("/") == src_parent.rstrip("/"):
            return

        # For cross-file drops let the user choose Copy vs Move
        if dst_file.resolve() != src_file.resolve():
            msg = QMessageBox(self)
            msg.setWindowTitle("Copy or Move?")
            msg.setText(
                f"Drop <b>{src_name}</b> into <b>{dst_file.name}</b> / <b>{dst_group}</b>"
            )
            copy_btn = msg.addButton("Copy", QMessageBox.ButtonRole.ActionRole)
            move_btn = msg.addButton("Move", QMessageBox.ButtonRole.ActionRole)
            msg.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
            msg.exec()
            clicked = msg.clickedButton()
            if clicked is copy_btn:
                op_fn = copy_hdf5_object
                op_label = "Copy"
            elif clicked is move_btn:
                op_fn = move_hdf5_object
                op_label = "Move"
            else:
                return
        else:
            op_fn = move_hdf5_object
            op_label = "Move"

        ok = self._perform_op(op_fn, src_file, src_obj_path, dst_file, dst_group, src_name, op_label)
        if ok:
            self._reload_file(src_file)
            if dst_file.resolve() != src_file.resolve():
                if dst_file in self.opened_files:
                    self._reload_file(dst_file)
                else:
                    self._open_file(dst_file)

    # ----- Slots ----- #
    @pyqtSlot(str)
    def _handle_plot_type_changed(self, plot_type: str) -> None:
        """Update plot when new plot type is selected."""
        self._plot_data(plot_type)

    @pyqtSlot(QModelIndex)
    def _handle_item_changed(self, index: None | QModelIndex) -> None:
        """Update Info of currently selected Item."""
        if index is None:
            return

        # Normalise to column 0 — clicking the Type column would otherwise feed
        # "Group"/"Dataset" labels into the path-building logic.
        index = index.sibling(index.row(), 0)
        if not index.isValid():
            return

        self._update_buttons(index)

        parents_list = [index.data()]
        self._tree_recursion(index, parents_list)
        parents_list.reverse()
        path = ""
        for e in parents_list[1:]:
            path += "/" + e
        self.cur_file = pathlib.Path(parents_list[0])
        self.cur_obj_path = path

        if len(parents_list) == 1:
            self.table_model_dataset.resetData()
            self.table_model_dataset.appendRow(["Name", parents_list[0]])
            self.table_model_dataset.appendRow(["File Size", file_size_to_str(parents_list[0])])
            self.slice_control.reset()
            return

        with h5py.File(parents_list[0], "r") as file:
            h5_obj = file[path]

            if isinstance(h5_obj, h5py.Group):
                self.table_model_dataset.resetData()
                self.table_model_dataset.appendRow(["Name", str(h5_obj.name)])
                self.slice_control.reset()

            elif isinstance(h5_obj, h5py.Dataset):
                self.table_model_dataset.resetData()
                self.table_model_dataset.appendRow(["Name", str(h5_obj.name)])
                self.table_model_dataset.appendRow(["Data", f"shape {h5_obj.shape} of type {h5_obj.dtype}"])

                for attribute, value in h5_obj.attrs.items():
                    self.table_model_dataset.appendRow([attribute, str(value)])

                self.slice_control.set_shape(h5_obj.shape)

        self._plot_data(self.cb_plot_type.currentText())

    def _tree_recursion(self, item: QModelIndex, path: list[str]) -> None:
        """Get Array of all Parents."""
        if (data := item.parent().data()) is None:
            return
        path.append(data)
        self._tree_recursion(item.parent(), path)

    @pyqtSlot()
    def _handle_filter_changed(self) -> None:
        text = self.le_filter.text()
        if text:
            self.tree_view_file.expandAll()
        else:
            self.tree_view_file.collapseAll()
        self.tree_model_file_proxy.setFilterCaseSensitivity(
            Qt.CaseSensitivity.CaseSensitive if self.btn_filter_case.isChecked() else Qt.CaseSensitivity.CaseInsensitive
        )
        if self.btn_filter_regex.isChecked():
            self.tree_model_file_proxy.setFilterRegularExpression(text)
        else:
            self.tree_model_file_proxy.setFilterFixedString(text)
        self.completer.setCaseSensitivity(
            Qt.CaseSensitivity.CaseSensitive if self.btn_filter_case.isChecked() else Qt.CaseSensitivity.CaseInsensitive
        )

    @pyqtSlot(QPoint)
    def _handle_tree_menu(self, pos: QPoint) -> None:
        menu = QMenu(self)
        proxy_index = self.tree_view_file.indexAt(pos)

        if not proxy_index.isValid():
            return

        # Always work from column 0 so data() returns the name, not the type label
        index = proxy_index.sibling(proxy_index.row(), 0)

        is_root_file = index.parent().data() is None
        obj_type = index.sibling(index.row(), 1).data() or ""  # "Group", "Dataset", or "HDF5 File"

        if is_root_file:
            # Map to source model row so removeRow works correctly even when a filter is active
            source_row = self.tree_model_file_proxy.mapToSource(index).row()
            act_close = QAction("Close File", self)
            act_reload = QAction("Reload File", self)
            menu.addAction(act_close)
            menu.addAction(act_reload)
            act_close.triggered.connect(lambda: self.tree_model_file.removeRow(source_row))
            act_reload.triggered.connect(lambda: self._handle_reload_from_index(index))
            menu.addSeparator()
            act_new_grp = QAction("New Group…", self)
            act_new_ds = QAction("New Dataset…", self)
            menu.addAction(act_new_grp)
            menu.addAction(act_new_ds)
            act_new_grp.triggered.connect(lambda: self._handle_new_group(index))
            act_new_ds.triggered.connect(lambda: self._handle_new_dataset(index))
        else:
            act_copy = QAction("Copy to…", self)
            act_move = QAction("Move to…", self)
            act_rename = QAction("Rename…", self)
            act_delete = QAction("Delete", self)
            menu.addAction(act_copy)
            menu.addAction(act_move)
            menu.addSeparator()
            menu.addAction(act_rename)
            menu.addAction(act_delete)
            act_copy.triggered.connect(lambda: self._handle_copy_to(index))
            act_move.triggered.connect(lambda: self._handle_move_to(index))
            act_rename.triggered.connect(lambda: self._handle_rename(index))
            act_delete.triggered.connect(lambda: self._handle_delete(index))

            if obj_type == "Group":
                menu.addSeparator()
                act_new_grp = QAction("New Group…", self)
                act_new_ds = QAction("New Dataset…", self)
                menu.addAction(act_new_grp)
                menu.addAction(act_new_ds)
                act_new_grp.triggered.connect(lambda: self._handle_new_group(index))
                act_new_ds.triggered.connect(lambda: self._handle_new_dataset(index))

        if (viewport := self.tree_view_file.viewport()) is not None:
            menu.popup(viewport.mapToGlobal(pos))

    def _get_path_from_index(self, index: QModelIndex) -> tuple[pathlib.Path, str]:
        """Return ``(file_path, hdf5_obj_path)`` for a tree-view index."""
        parents_list = [index.data()]
        self._tree_recursion(index, parents_list)
        parents_list.reverse()
        file_path = pathlib.Path(parents_list[0])
        obj_path = "".join("/" + part for part in parents_list[1:])
        return file_path, obj_path

    def _reload_file(self, file_path: pathlib.Path) -> None:
        """Refresh a file's tree node in-place without removing and re-adding the row.

        Updating in-place means the row never disappears from the tree — if the
        h5py read fails for any reason the existing data stays visible rather than
        the whole entry being deleted.
        """
        for i in range(self.tree_model_file.rowCount()):
            item = self.tree_model_file.item(i, 0)
            if item is not None and pathlib.Path(item.text()) == file_path:
                # Wipe children and repopulate from disk
                item.removeRows(0, item.rowCount())
                try:
                    with h5py.File(file_path, "r") as f:
                        self._hdf5_recursion(hdf5_object=f, root=item, parent=item)
                except Exception as err:
                    logging.warning(f"Failed to reload '{file_path}': {err}")
                    return
                # Expand the node so the updated contents are immediately visible
                source_idx = self.tree_model_file.index(i, 0)
                proxy_idx = self.tree_model_file_proxy.mapFromSource(source_idx)
                self.tree_view_file.expand(proxy_idx)
                return
        # File not currently in the tree — open it fresh
        self._open_file(file_path)

    def _perform_op(self, op_fn, src_file: pathlib.Path, src_obj_path: str,
                    dst_file: pathlib.Path, dst_group: str, dst_name: str,
                    label: str) -> bool:
        """Execute a copy/move with overwrite confirmation loop. Returns True on success."""
        overwrite = False
        while True:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                op_fn(src_file, src_obj_path, dst_file, dst_group, dst_name, overwrite=overwrite)
                QApplication.restoreOverrideCursor()
                return True
            except FileExistsError as err:
                QApplication.restoreOverrideCursor()
                reply = QMessageBox.question(
                    self,
                    "Destination Exists",
                    f"{err}\n\nOverwrite?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return False
                overwrite = True
            except ValueError:
                QApplication.restoreOverrideCursor()
                return False  # circular / same-location — silently ignore
            except Exception as exc:
                QApplication.restoreOverrideCursor()
                logging.error(f"{label} failed: {exc}")
                QMessageBox.critical(self, f"{label} Failed", str(exc))
                return False

    def _run_copy_move(self, index: QModelIndex, operation: str) -> None:
        """Common logic for Copy and Move button/menu actions.

        Copy uses MultiCopyDialog (one or more destination files).
        Move uses CopyMoveDialog (single destination).
        """
        src_file, src_obj_path = self._get_path_from_index(index)
        if not src_obj_path:
            return

        if operation == "Copy":
            dlg = MultiCopyDialog(self, src_file, src_obj_path)
            if dlg.exec() != MultiCopyDialog.DialogCode.Accepted:
                return
            dst_files = dlg.dst_files
            dst_group = dlg.dst_group
            dst_name = dlg.dst_name
            if not dst_name:
                QMessageBox.warning(self, "Copy", "Destination name must not be empty.")
                return
            if not dst_files:
                QMessageBox.warning(self, "Copy", "No destination files selected.")
                return
            src_reloaded = False
            for dst_file in dst_files:
                ok = self._perform_op(copy_hdf5_object, src_file, src_obj_path,
                                      dst_file, dst_group, dst_name, "Copy")
                if ok:
                    if dst_file.resolve() == src_file.resolve():
                        if not src_reloaded:
                            self._reload_file(src_file)
                            src_reloaded = True
                    else:
                        if dst_file in self.opened_files:
                            self._reload_file(dst_file)
                        else:
                            self._open_file(dst_file)
        else:
            dlg = CopyMoveDialog(self, operation, src_file, src_obj_path)
            if dlg.exec() != CopyMoveDialog.DialogCode.Accepted:
                return
            dst_file = dlg.dst_file
            dst_group = dlg.dst_group
            dst_name = dlg.dst_name
            if not dst_name:
                QMessageBox.warning(self, operation, "Destination name must not be empty.")
                return
            ok = self._perform_op(move_hdf5_object, src_file, src_obj_path,
                                  dst_file, dst_group, dst_name, operation)
            if ok:
                self._reload_file(src_file)
                if dst_file.resolve() != src_file.resolve():
                    if dst_file in self.opened_files:
                        self._reload_file(dst_file)
                    else:
                        self._open_file(dst_file)

    def _handle_reload_from_index(self, index: QModelIndex) -> None:
        """Reload the file represented by a root-level tree index."""
        file_path = pathlib.Path(index.data())
        self._reload_file(file_path)

    @pyqtSlot()
    def _handle_rename(self, index: QModelIndex) -> None:
        """Handle 'Rename…' context-menu action."""
        file_path, obj_path = self._get_path_from_index(index)
        if not obj_path:
            return
        current_name = obj_path.rsplit("/", 1)[-1]
        dlg = RenameDialog(self, current_name)
        if dlg.exec() != RenameDialog.DialogCode.Accepted:
            return
        new_name = dlg.new_name
        if not new_name:
            QMessageBox.warning(self, "Rename", "Name must not be empty.")
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        success = False
        try:
            rename_hdf5_object(file_path, obj_path, new_name)
            success = True
        except Exception as exc:
            logging.error(f"Rename failed: {exc}")
            QMessageBox.critical(self, "Rename Failed", str(exc))
        finally:
            QApplication.restoreOverrideCursor()
        if success:
            self._reload_file(file_path)

    @pyqtSlot()
    def _handle_delete(self, index: QModelIndex) -> None:
        """Handle 'Delete' context-menu action."""
        file_path, obj_path = self._get_path_from_index(index)
        if not obj_path:
            return
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete '{obj_path}' from '{file_path.name}'?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        success = False
        try:
            delete_hdf5_object(file_path, obj_path)
            success = True
        except Exception as exc:
            logging.error(f"Delete failed: {exc}")
            QMessageBox.critical(self, "Delete Failed", str(exc))
        finally:
            QApplication.restoreOverrideCursor()
        if success:
            self._reload_file(file_path)

    @pyqtSlot()
    def _handle_new_group(self, index: QModelIndex) -> None:
        """Handle 'New Group…' context-menu action."""
        file_path, obj_path = self._get_path_from_index(index)
        parent_path = obj_path if obj_path else "/"
        dlg = NewGroupDialog(self, parent_path)
        if dlg.exec() != NewGroupDialog.DialogCode.Accepted:
            return
        name = dlg.name
        if not name:
            QMessageBox.warning(self, "New Group", "Name must not be empty.")
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        success = False
        try:
            create_hdf5_group(file_path, parent_path, name)
            success = True
        except Exception as exc:
            logging.error(f"Create group failed: {exc}")
            QMessageBox.critical(self, "New Group Failed", str(exc))
        finally:
            QApplication.restoreOverrideCursor()
        if success:
            self._reload_file(file_path)

    @pyqtSlot()
    def _handle_new_dataset(self, index: QModelIndex) -> None:
        """Handle 'New Dataset…' context-menu action."""
        file_path, obj_path = self._get_path_from_index(index)
        parent_path = obj_path if obj_path else "/"
        dlg = NewDatasetDialog(self, parent_path)
        if dlg.exec() != NewDatasetDialog.DialogCode.Accepted:
            return
        name = dlg.name
        if not name:
            QMessageBox.warning(self, "New Dataset", "Name must not be empty.")
            return
        try:
            shape = dlg.shape
        except ValueError as exc:
            QMessageBox.warning(self, "New Dataset", f"Invalid shape: {exc}")
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        success = False
        try:
            create_hdf5_dataset(file_path, parent_path, name, shape, dlg.dtype, dlg.fill_value)
            success = True
        except Exception as exc:
            logging.error(f"Create dataset failed: {exc}")
            QMessageBox.critical(self, "New Dataset Failed", str(exc))
        finally:
            QApplication.restoreOverrideCursor()
        if success:
            self._reload_file(file_path)

    @pyqtSlot()
    def _handle_copy_to(self, index: QModelIndex) -> None:
        """Handle 'Copy to…' context-menu action."""
        self._run_copy_move(index, "Copy")

    @pyqtSlot()
    def _handle_move_to(self, index: QModelIndex) -> None:
        """Handle 'Move to…' context-menu action."""
        self._run_copy_move(index, "Move")

    @pyqtSlot()
    def _handle_action_open_file(self) -> None:
        """Open HDF5 Files."""
        settings = QSettings()
        folder: pathlib.Path = pathlib.Path(
            settings.value("paths/last_opened_file_directory", defaultValue=os.path.expanduser("~"))
        )
        default_path = str(folder.absolute()) if folder.absolute().exists() else os.path.expanduser("~")
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Open File",
            default_path,
            "HDF5 File (*.hdf5, *.h5);;All Files (*.*)",
        )
        if not file_paths:
            return

        settings.setValue("paths/last_opened_file_directory", pathlib.Path(file_paths[0]).parent)
        for file in file_paths:
            self._open_file(pathlib.Path(file))

    @pyqtSlot()
    def _handle_action_open_folder(self) -> None:
        """Open all HDF5 Files in a Folder."""
        settings = QSettings()
        folder: pathlib.Path = settings.value(
            "paths/last_opened_folder_directory",
            defaultValue=pathlib.Path(os.path.expanduser("~")),
        )
        default_path = str(folder.absolute()) if folder.absolute().exists() else os.path.expanduser("~")
        folder_path = QFileDialog.getExistingDirectory(self, "Open Folder", default_path)
        if not folder_path:
            return

        settings.setValue("paths/last_opened_folder_directory", pathlib.Path(folder_path))
        for file in os.listdir(folder_path):
            self._open_file(pathlib.Path(folder_path, file))

    @pyqtSlot()
    def _handle_action_clear_files(self) -> None:
        """Clear Tree Widget."""
        self.tree_model_file.clear()
        self.table_model_dataset.resetData()

    @pyqtSlot()
    def _handle_action_about(self) -> None:
        """Open About Page."""
        self._about_page = AboutPage()

    @pyqtSlot()
    def _handle_close(self) -> None:
        """Close Window."""
        self.close()

    @pyqtSlot()
    def closeEvent(self, a0: QCloseEvent | None) -> None:
        """Close Window."""
        if a0 is None:
            return

        settings = QSettings()
        settings.setValue("main_window/size", self.size())
        settings.setValue("main_window/position", self.pos())
        settings.setValue("settings/last_opened_files", self.opened_files)
        settings.sync()
