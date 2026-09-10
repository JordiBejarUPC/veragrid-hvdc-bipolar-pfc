# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Authenticate immutable files and closed external-tool trees."""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
from typing import BinaryIO


def verify_regular_file_identity(
    path: Path,
    expected_size_bytes: int,
    expected_sha256: str,
) -> bytes:
    """Read and authenticate one explicit regular non-symlink file.

    :param path: Explicit file path selected by the caller.
    :param expected_size_bytes: Required exact file size.
    :param expected_sha256: Required lowercase SHA-256 digest.
    :return: Exact authenticated immutable file bytes.
    """

    arguments_are_valid: bool = bool(
        isinstance(path, Path)
        and isinstance(expected_size_bytes, int)
        and not isinstance(expected_size_bytes, bool)
        and expected_size_bytes > 0
        and isinstance(expected_sha256, str)
        and re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is not None
    )
    path_is_valid: bool = bool(
        arguments_are_valid
        and path.exists()
        and path.is_file()
        and not path.is_symlink()
        and path.stat().st_size == expected_size_bytes
    )
    if path_is_valid:
        pass
    else:
        raise ValueError("Explicit file identity path is unsafe or invalid")

    source_file: BinaryIO = path.open("rb")
    try:
        content: bytes = source_file.read(expected_size_bytes + 1)
    finally:
        source_file.close()
    content_is_valid: bool = bool(
        len(content) == expected_size_bytes
        and hashlib.sha256(content).hexdigest() == expected_sha256
    )
    if content_is_valid:
        return content
    else:
        raise ValueError("Explicit file content identity does not match")


def read_regular_tree_identity(tree_root: Path) -> tuple[int, int, str]:
    """Compute the deterministic identity of one closed regular-file tree.

    :param tree_root: Explicit directory containing one complete owned tree.
    :return: Regular-file count, aggregate size and path-size-content digest.
    """

    root_is_valid: bool = bool(
        isinstance(tree_root, Path)
        and tree_root.exists()
        and tree_root.is_dir()
        and not tree_root.is_symlink()
    )
    if root_is_valid:
        canonical_root: Path = tree_root.resolve(strict=True)
    else:
        raise ValueError("Regular tree root is unsafe or unavailable")

    # First inventory every entry and reject any reparse-style ownership escape.
    paths_by_portable_name: dict[str, Path] = dict()
    discovered_entries: list[Path] = list(canonical_root.rglob("*"))
    for discovered_entry in discovered_entries:
        if discovered_entry.is_symlink():
            raise ValueError("Regular tree contains a symbolic link")
        else:
            if discovered_entry.is_file():
                portable_name: str = discovered_entry.relative_to(
                    canonical_root
                ).as_posix()
                if portable_name in paths_by_portable_name:
                    raise ValueError("Regular tree contains a duplicate path")
                else:
                    paths_by_portable_name[portable_name] = discovered_entry
            else:
                if discovered_entry.is_dir():
                    pass
                else:
                    raise ValueError("Regular tree contains a non-file entry")

    portable_names: list[str] = list(paths_by_portable_name.keys())
    portable_names.sort()
    if len(portable_names) > 0:
        pass
    else:
        raise ValueError("Regular tree contains no regular files")

    # Each record binds its portable path, stable size and complete content digest.
    records: list[str] = [""] * len(portable_names)
    total_size_bytes: int = 0
    for file_index in range(len(portable_names)):
        portable_name = portable_names[file_index]
        runtime_path: Path = paths_by_portable_name[portable_name]
        size_before_read: int = runtime_path.stat().st_size
        runtime_file: BinaryIO = runtime_path.open("rb")
        try:
            content: bytes = runtime_file.read(size_before_read + 1)
        finally:
            runtime_file.close()
        size_after_read: int = runtime_path.stat().st_size
        file_is_stable: bool = bool(
            len(content) == size_before_read
            and size_after_read == size_before_read
            and runtime_path.is_file()
            and not runtime_path.is_symlink()
        )
        if file_is_stable:
            pass
        else:
            raise ValueError("Regular tree file changed during authentication")
        content_sha256: str = hashlib.sha256(content).hexdigest()
        records[file_index] = (
            f"{portable_name} {size_before_read} {content_sha256}\n"
        )
        total_size_bytes += size_before_read
    digest_input: bytes = "".join(records).encode("utf-8")
    return (
        len(portable_names),
        total_size_bytes,
        hashlib.sha256(digest_input).hexdigest(),
    )
