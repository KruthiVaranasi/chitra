"""The on-drive index: a SQLite database plus a thumbnail folder inside `<root>/.chitra/`.

Paths are stored relative to the root, so the index keeps working when a drive
mounts under a different letter or on another machine.
"""

import hashlib
import os
import sqlite3
import sys
import threading
from pathlib import Path
from typing import Iterable, Optional

import numpy as np

from .config import INDEX_DIRNAME

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS images (
    id        INTEGER PRIMARY KEY,
    path      TEXT UNIQUE NOT NULL,
    size      INTEGER NOT NULL,
    mtime     REAL NOT NULL,
    width     INTEGER,
    height    INTEGER,
    taken_at  TEXT,
    embedding BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS failures (
    path  TEXT PRIMARY KEY,
    size  INTEGER NOT NULL,
    mtime REAL NOT NULL,
    error TEXT
);
"""


def thumb_name(rel_path: str) -> str:
    return hashlib.sha1(rel_path.encode("utf-8")).hexdigest()[:20] + ".jpg"


def _hide_on_windows(path: Path) -> None:
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.kernel32.SetFileAttributesW(str(path), 0x02)  # FILE_ATTRIBUTE_HIDDEN


class Store:
    def __init__(self, root: Path, create: bool = True):
        self.root = Path(root).resolve()
        self.dir = self.root / INDEX_DIRNAME
        if not self.dir.exists():
            if not create:
                raise FileNotFoundError(f"No Chitra index in {self.root}. Run: chitra index \"{self.root}\"")
            self.dir.mkdir(parents=True)
            _hide_on_windows(self.dir)
        self.thumbs = self.dir / "thumbs"
        self.thumbs.mkdir(exist_ok=True)
        # One connection shared by the web server's worker threads; the lock serialises access to it.
        self.db = sqlite3.connect(self.dir / "index.db", check_same_thread=False)
        self._lock = threading.RLock()
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(SCHEMA)

    # -- metadata ---------------------------------------------------------
    def get_meta(self, key: str) -> Optional[str]:
        with self._lock:
            row = self.db.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else None

    def set_meta(self, key: str, value: str) -> None:
        with self._lock:
            self.db.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value))
            self.db.commit()

    # -- bookkeeping for incremental indexing ------------------------------
    def known(self) -> dict:
        with self._lock:
            return {r["path"]: (r["size"], r["mtime"]) for r in self.db.execute("SELECT path, size, mtime FROM images")}

    def failed(self) -> dict:
        with self._lock:
            return {r["path"]: (r["size"], r["mtime"]) for r in self.db.execute("SELECT path, size, mtime FROM failures")}

    def count(self) -> int:
        with self._lock:
            return self.db.execute("SELECT COUNT(*) FROM images").fetchone()[0]

    def failure_count(self) -> int:
        with self._lock:
            return self.db.execute("SELECT COUNT(*) FROM failures").fetchone()[0]

    # -- writes -------------------------------------------------------------
    def upsert(self, rows: Iterable[tuple]) -> None:
        """rows: (path, size, mtime, width, height, taken_at, embedding ndarray)"""
        rows = list(rows)
        with self._lock:
            self.db.executemany(
                """INSERT INTO images (path, size, mtime, width, height, taken_at, embedding)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(path) DO UPDATE SET
                     size = excluded.size, mtime = excluded.mtime, width = excluded.width,
                     height = excluded.height, taken_at = excluded.taken_at, embedding = excluded.embedding""",
                [(p, s, m, w, h, t, np.asarray(e, dtype=np.float32).tobytes()) for p, s, m, w, h, t, e in rows],
            )
            self.db.executemany("DELETE FROM failures WHERE path = ?", [(r[0],) for r in rows])
            self.db.commit()

    def add_failures(self, rows: Iterable[tuple]) -> None:
        """rows: (path, size, mtime, error)"""
        with self._lock:
            self.db.executemany("INSERT OR REPLACE INTO failures (path, size, mtime, error) VALUES (?, ?, ?, ?)", rows)
            self.db.commit()

    def delete(self, paths: Iterable[str]) -> None:
        with self._lock:
            paths = list(paths)
            self.db.executemany("DELETE FROM images WHERE path = ?", [(p,) for p in paths])
            self.db.executemany("DELETE FROM failures WHERE path = ?", [(p,) for p in paths])
            self.db.commit()
            for p in paths:
                try:
                    os.remove(self.thumbs / thumb_name(p))
                except OSError:
                    pass

    def clear(self) -> None:
        with self._lock:
            self.db.executescript("DELETE FROM images; DELETE FROM failures; DELETE FROM meta;")
            self.db.commit()
            for f in self.thumbs.glob("*.jpg"):
                f.unlink(missing_ok=True)

    # -- reads --------------------------------------------------------------
    def load_matrix(self):
        """Returns (ids, years, matrix): ids int64 (N,), years int32 (N,) with 0 = unknown, matrix float32 (N, D)."""
        with self._lock:
            rows = self.db.execute("SELECT id, taken_at, embedding FROM images ORDER BY id").fetchall()
            if not rows:
                return np.zeros(0, np.int64), np.zeros(0, np.int32), np.zeros((0, 0), np.float32)
            ids = np.fromiter((r["id"] for r in rows), np.int64, len(rows))
            years = np.fromiter((int(r["taken_at"][:4]) if r["taken_at"] else 0 for r in rows), np.int32, len(rows))
            matrix = np.vstack([np.frombuffer(r["embedding"], dtype=np.float32) for r in rows])
            return ids, years, matrix

    def get(self, image_id: int) -> Optional[dict]:
        with self._lock:
            row = self.db.execute(
                "SELECT id, path, size, width, height, taken_at FROM images WHERE id = ?", (int(image_id),)
            ).fetchone()
            return dict(row) if row else None

    def get_many(self, ids: Iterable[int]) -> dict:
        with self._lock:
            ids = [int(i) for i in ids]
            if not ids:
                return {}
            marks = ",".join("?" * len(ids))
            rows = self.db.execute(
                f"SELECT id, path, size, width, height, taken_at FROM images WHERE id IN ({marks})", ids
            ).fetchall()
            return {r["id"]: dict(r) for r in rows}

    def abspath(self, rel_path: str) -> Path:
        return self.root / rel_path

    def thumb_path(self, rel_path: str) -> Path:
        return self.thumbs / thumb_name(rel_path)
