"""Copy and move operations for HDF5 objects."""

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

import h5py


def _dst_full_path(dst_group_path: str, dst_name: str) -> str:
    """Construct the full destination path from group and name."""
    group = dst_group_path.strip("/")
    return ("/" + group + "/" + dst_name).replace("//", "/")


def copy_hdf5_object(
    src_file_path: pathlib.Path,
    src_obj_path: str,
    dst_file_path: pathlib.Path,
    dst_group_path: str,
    dst_name: str,
    overwrite: bool = False,
) -> None:
    """Copy an HDF5 dataset or group from one file to another.

    Metadata and attributes are preserved via h5py's built-in copy semantics.

    :param src_file_path: Path to the source HDF5 file.
    :param src_obj_path: Path of the object inside the source file.
    :param dst_file_path: Path to the destination HDF5 file (created if absent).
    :param dst_group_path: Group path inside the destination file.
    :param dst_name: Name for the copied object at the destination.
    :param overwrite: If True, delete an existing destination object first.
    :raises FileExistsError: If the destination path already exists and *overwrite* is False.
    :raises ValueError: If the operation would copy an object into its own subtree.
    """
    dst_path = _dst_full_path(dst_group_path, dst_name)
    same_file = src_file_path.resolve() == dst_file_path.resolve()

    if same_file:
        _validate_no_self_subtree(src_obj_path, dst_path)
        with h5py.File(src_file_path, "r+") as f:
            _ensure_no_collision(f, dst_path, overwrite)
            dst_group = f.require_group(dst_group_path)
            f.copy(src_obj_path, dst_group, name=dst_name)
    else:
        with h5py.File(src_file_path, "r") as src, h5py.File(dst_file_path, "a") as dst:
            _ensure_no_collision(dst, dst_path, overwrite)
            dst_group = dst.require_group(dst_group_path)
            src.copy(src_obj_path, dst_group, name=dst_name)


def move_hdf5_object(
    src_file_path: pathlib.Path,
    src_obj_path: str,
    dst_file_path: pathlib.Path,
    dst_group_path: str,
    dst_name: str,
    overwrite: bool = False,
) -> None:
    """Move an HDF5 dataset or group from one file to another.

    Performs a copy then deletes the original object from the source.

    :param src_file_path: Path to the source HDF5 file.
    :param src_obj_path: Path of the object inside the source file.
    :param dst_file_path: Path to the destination HDF5 file (created if absent).
    :param dst_group_path: Group path inside the destination file.
    :param dst_name: Name for the moved object at the destination.
    :param overwrite: If True, delete an existing destination object first.
    :raises FileExistsError: If the destination path already exists and *overwrite* is False.
    :raises ValueError: If the operation would move an object into its own subtree.
    """
    dst_path = _dst_full_path(dst_group_path, dst_name)
    same_file = src_file_path.resolve() == dst_file_path.resolve()

    if same_file:
        _validate_no_self_subtree(src_obj_path, dst_path)
        with h5py.File(src_file_path, "r+") as f:
            _ensure_no_collision(f, dst_path, overwrite)
            dst_group = f.require_group(dst_group_path)
            f.copy(src_obj_path, dst_group, name=dst_name)
            del f[src_obj_path]
    else:
        # Source must be writable so the original can be deleted.
        with h5py.File(src_file_path, "r+") as src, h5py.File(dst_file_path, "a") as dst:
            _ensure_no_collision(dst, dst_path, overwrite)
            dst_group = dst.require_group(dst_group_path)
            src.copy(src_obj_path, dst_group, name=dst_name)
            del src[src_obj_path]


# ----- helpers -----


def _ensure_no_collision(h5file: h5py.File, dst_path: str, overwrite: bool) -> None:
    """Raise FileExistsError if *dst_path* exists and overwrite is False; else delete it."""
    if dst_path in h5file:
        if not overwrite:
            raise FileExistsError(f"Destination path '{dst_path}' already exists in '{h5file.filename}'.")
        del h5file[dst_path]


def _validate_no_self_subtree(src_path: str, dst_path: str) -> None:
    """Raise ValueError if dst_path is equal to or a child of src_path."""
    src = src_path.rstrip("/")
    dst = dst_path.rstrip("/")
    if dst == src or dst.startswith(src + "/"):
        raise ValueError(
            f"Cannot copy/move '{src_path}' into itself or its own subtree (destination: '{dst_path}')."
        )
