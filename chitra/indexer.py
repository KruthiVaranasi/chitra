"""Incremental indexing: embed new/changed images, drop deleted ones.

Work is committed batch by batch, so an interrupted run resumes where it stopped.
"""

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from tqdm import tqdm

from .config import DEFAULT_MODEL
from .imaging import load_image, save_thumbnail
from .scanner import FileEntry, scan
from .store import Store


class ModelMismatch(Exception):
    pass


@dataclass
class IndexStats:
    scanned: int = 0
    added: int = 0
    removed: int = 0
    failed: int = 0
    unchanged: int = 0
    seconds: float = 0.0  # time spent decoding + embedding, excluding model load


def _load(store: Store, entry: FileEntry):
    try:
        loaded = load_image(store.abspath(entry.path))
        save_thumbnail(loaded.image, store.thumb_path(entry.path))
        return entry, loaded, None
    except Exception as exc:  # corrupt or unsupported file
        return entry, None, f"{type(exc).__name__}: {exc}"


def index(
    root: Path,
    model_name: Optional[str] = None,
    embedder=None,
    batch_size: int = 16,
    workers: int = 4,
    rebuild: bool = False,
    progress: bool = True,
) -> IndexStats:
    store = Store(root)
    if rebuild:
        store.clear()

    indexed_with = store.get_meta("model")
    model_name = embedder.name if embedder else (model_name or indexed_with or DEFAULT_MODEL)
    if indexed_with and indexed_with != model_name:
        raise ModelMismatch(
            f"This index was built with '{indexed_with}'. Use --rebuild to re-index with '{model_name}'."
        )

    stats = IndexStats()
    files = list(scan(store.root))
    stats.scanned = len(files)
    known, failed = store.known(), store.failed()

    on_disk = {f.path for f in files}
    removed = [p for p in list(known) + list(failed) if p not in on_disk]
    store.delete(removed)
    stats.removed = len(set(removed) & set(known))

    todo = [f for f in files if known.get(f.path) != (f.size, f.mtime) and failed.get(f.path) != (f.size, f.mtime)]
    stats.unchanged = len(files) - len(todo)
    if not todo:
        return stats

    if embedder is None:
        from .model import Embedder

        if progress:
            print(f"Loading model {model_name} ...")
        embedder = Embedder(model_name)
    store.set_meta("model", model_name)

    started = time.time()
    batches = [todo[i : i + batch_size] for i in range(0, len(todo), batch_size)]
    with ThreadPoolExecutor(workers) as pool, tqdm(total=len(todo), unit="img", disable=not progress) as bar:
        # Decode the next batch on worker threads while the model embeds the current one.
        pending = [pool.submit(_load, store, f) for f in batches[0]]
        for i in range(len(batches)):
            results = [fut.result() for fut in pending]
            pending = [pool.submit(_load, store, f) for f in batches[i + 1]] if i + 1 < len(batches) else []

            ok = [(e, img) for e, img, err in results if img is not None]
            bad = [(e.path, e.size, e.mtime, err) for e, img, err in results if img is None]
            if ok:
                vectors = embedder.encode_images([img.image for _, img in ok])
                store.upsert(
                    (e.path, e.size, e.mtime, img.width, img.height, img.taken_at, vec)
                    for (e, img), vec in zip(ok, vectors)
                )
            if bad:
                store.add_failures(bad)
            stats.added += len(ok)
            stats.failed += len(bad)
            bar.update(len(results))
            stats.seconds = time.time() - started
    return stats
