"""Create, delete, and rename HDF5 groups and datasets."""

import pathlib

import h5py
import numpy as np


def delete_hdf5_object(file_path: pathlib.Path, obj_path: str) -> None:
    """Delete a group or dataset from an HDF5 file.

    :raises KeyError: If *obj_path* does not exist.
    """
    with h5py.File(file_path, "r+") as f:
        if obj_path not in f:
            raise KeyError(f"'{obj_path}' does not exist in '{file_path}'.")
        del f[obj_path]


def rename_hdf5_object(file_path: pathlib.Path, obj_path: str, new_name: str) -> None:
    """Rename (move within same file) an HDF5 group or dataset.

    :raises KeyError: If *obj_path* does not exist.
    :raises FileExistsError: If the target path already exists.
    """
    stripped = obj_path.rstrip("/")
    slash_pos = stripped.rfind("/")
    parent_path = "/" if slash_pos <= 0 else stripped[:slash_pos]
    new_path = parent_path.rstrip("/") + "/" + new_name
    with h5py.File(file_path, "r+") as f:
        if obj_path not in f:
            raise KeyError(f"'{obj_path}' does not exist in '{file_path}'.")
        if new_path in f:
            raise FileExistsError(f"'{new_path}' already exists in '{file_path}'.")
        f.move(obj_path, new_path)


def create_hdf5_group(file_path: pathlib.Path, parent_group: str, name: str) -> None:
    """Create a new group inside *parent_group*.

    :raises FileExistsError: If the target path already exists.
    """
    full_path = _join(parent_group, name)
    with h5py.File(file_path, "r+") as f:
        if full_path in f:
            raise FileExistsError(f"'{full_path}' already exists in '{file_path}'.")
        f.require_group(full_path)


def create_hdf5_dataset(
    file_path: pathlib.Path,
    parent_group: str,
    name: str,
    shape: tuple[int, ...],
    dtype: str,
    fill_value: float = 0,
) -> None:
    """Create a new dataset filled with zeros (or *fill_value*) inside *parent_group*.

    Pass ``dtype="string"`` to create a variable-length string dataset.
    Pass an empty tuple for *shape* to create a scalar dataset.

    :raises FileExistsError: If the target path already exists.
    """
    full_path = _join(parent_group, name)
    with h5py.File(file_path, "r+") as f:
        if full_path in f:
            raise FileExistsError(f"'{full_path}' already exists in '{file_path}'.")
        grp = f.require_group(parent_group)
        if dtype == "string":
            grp.create_dataset(name, shape=shape if shape else (1,), dtype=h5py.string_dtype())
        else:
            grp.create_dataset(name, shape=shape, dtype=np.dtype(dtype), fillvalue=fill_value)


def _join(group: str, name: str) -> str:
    return (group.rstrip("/") + "/" + name).replace("//", "/")
