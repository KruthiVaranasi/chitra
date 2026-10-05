"""Walk a folder or drive and yield image files."""

import os
from pathlib import Path
from typing import Iterator, NamedTuple

from .config import IMAGE_EXTS, SKIP_DIRS


class FileEntry(NamedTuple):
    path: str  # relative to the root, always with forward slashes
    size: int
    mtime: float


def scan(root: Path) -> Iterator[FileEntry]:
    root = Path(root)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            if Path(name).suffix.lower() not in IMAGE_EXTS:
                continue
            full = os.path.join(dirpath, name)
            try:
                st = os.stat(full)
            except OSError:
                continue
            if st.st_size == 0:
                continue
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            yield FileEntry(rel, st.st_size, st.st_mtime)
