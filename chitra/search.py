"""Search the index by text, by an example image, or by similarity to an indexed image."""

import threading
from pathlib import Path
from typing import List, Optional

import numpy as np
from PIL import Image

from .config import DEFAULT_MODEL
from .store import Store


class Searcher:
    def __init__(self, root: Path, embedder=None):
        self.store = Store(root, create=False)
        self._embedder = embedder
        self._lock = threading.Lock()
        self.reload()

    def reload(self) -> None:
        self.ids, self.years, self.matrix = self.store.load_matrix()
        self._row_of = {int(i): n for n, i in enumerate(self.ids)}

    @property
    def model_name(self) -> str:
        return self.store.get_meta("model") or DEFAULT_MODEL

    @property
    def embedder(self):
        if self._embedder is None:
            from .model import Embedder

            self._embedder = Embedder(self.model_name)
        return self._embedder

    def __len__(self) -> int:
        return len(self.ids)

    def search_text(self, query: str, k: int = 50, **filters) -> List[dict]:
        with self._lock:
            vec = self.embedder.encode_text([query])[0]
        return self._rank(vec, k, **filters)

    def search_image(self, image: Image.Image, k: int = 50, **filters) -> List[dict]:
        with self._lock:
            vec = self.embedder.encode_images([image.convert("RGB")])[0]
        return self._rank(vec, k, **filters)

    def similar(self, image_id: int, k: int = 50, **filters) -> List[dict]:
        row = self._row_of.get(int(image_id))
        if row is None:
            return []
        return self._rank(self.matrix[row], k, **filters)

    def _rank(self, vec: np.ndarray, k: int, year_from: Optional[int] = None, year_to: Optional[int] = None) -> List[dict]:
        if not len(self.ids):
            return []
        scores = self.matrix @ vec.astype(np.float32)
        if year_from or year_to:
            mask = self.years > 0
            if year_from:
                mask &= self.years >= year_from
            if year_to:
                mask &= self.years <= year_to
            scores = np.where(mask, scores, -np.inf)
        k = min(k, len(scores))
        top = np.argpartition(-scores, k - 1)[:k]
        top = top[np.argsort(-scores[top])]
        top = [i for i in top if np.isfinite(scores[i])]
        info = self.store.get_many(self.ids[top])
        return [{**info[int(self.ids[i])], "score": round(float(scores[i]), 4)} for i in top]
