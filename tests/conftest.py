import numpy as np
import pytest
from PIL import Image

COLORS = {"red": (220, 30, 30), "green": (30, 200, 40), "blue": (30, 40, 220)}


class FakeEmbedder:
    """Embeds an image as its normalised mean colour and the words red/green/blue as unit axes,
    so tests can check ranking without downloading a real model."""

    name = "fake/color-model"

    def __init__(self):
        self.image_calls = 0

    @staticmethod
    def _norm(v):
        v = np.asarray(v, dtype=np.float32)
        return v / (np.linalg.norm(v) + 1e-9)

    def encode_images(self, images):
        self.image_calls += len(images)
        return np.stack([self._norm(np.asarray(img.convert("RGB"), np.float32).mean(axis=(0, 1))) for img in images])

    def encode_text(self, texts):
        out = []
        for t in texts:
            v = [float(name in t.lower()) for name in COLORS]
            out.append(self._norm(v if any(v) else [1, 1, 1]))
        return np.stack(out)


@pytest.fixture
def embedder():
    return FakeEmbedder()


@pytest.fixture
def photo_dir(tmp_path):
    (tmp_path / "trip").mkdir()
    for name, rgb in COLORS.items():
        Image.new("RGB", (64, 48), rgb).save(tmp_path / "trip" / f"{name}.jpg")
    Image.new("RGB", (40, 40), (200, 50, 60)).save(tmp_path / "reddish.png")
    (tmp_path / "notes.txt").write_text("not an image")
    (tmp_path / "broken.jpg").write_bytes(b"definitely not a jpeg")
    return tmp_path
