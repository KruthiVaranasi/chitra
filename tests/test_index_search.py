import os

from PIL import Image

from chitra.indexer import ModelMismatch, index
from chitra.scanner import scan
from chitra.search import Searcher
from chitra.store import Store


def test_scan_finds_only_images_and_skips_index_dir(photo_dir):
    (photo_dir / ".chitra").mkdir()
    Image.new("RGB", (8, 8)).save(photo_dir / ".chitra" / "thumb.jpg")
    paths = sorted(e.path for e in scan(photo_dir))
    assert paths == ["broken.jpg", "reddish.png", "trip/blue.jpg", "trip/green.jpg", "trip/red.jpg"]


def test_index_is_incremental(photo_dir, embedder):
    first = index(photo_dir, embedder=embedder, progress=False)
    assert (first.added, first.failed) == (4, 1)

    second = index(photo_dir, embedder=embedder, progress=False)
    assert (second.added, second.failed, second.unchanged) == (0, 0, 5)
    assert embedder.image_calls == 4

    os.remove(photo_dir / "trip" / "green.jpg")
    Image.new("RGB", (64, 48), (10, 10, 10)).save(photo_dir / "trip" / "red.jpg")
    os.utime(photo_dir / "trip" / "red.jpg", (1, 1))
    third = index(photo_dir, embedder=embedder, progress=False)
    assert (third.added, third.removed) == (1, 1)
    assert Store(photo_dir).count() == 3


def test_thumbnails_and_metadata(photo_dir, embedder):
    index(photo_dir, embedder=embedder, progress=False)
    store = Store(photo_dir)
    assert store.get_meta("model") == embedder.name
    info = next(store.get(i) for i in store.load_matrix()[0] if store.get(i)["path"] == "trip/red.jpg")
    assert (info["width"], info["height"]) == (64, 48)
    assert store.thumb_path("trip/red.jpg").exists()


def test_model_mismatch_requires_rebuild(photo_dir, embedder):
    index(photo_dir, embedder=embedder, progress=False)
    embedder.name = "other/model"
    try:
        index(photo_dir, embedder=embedder, progress=False)
        raise AssertionError("expected ModelMismatch")
    except ModelMismatch:
        pass
    stats = index(photo_dir, embedder=embedder, rebuild=True, progress=False)
    assert stats.added == 4


def test_text_search_ranks_by_meaning(photo_dir, embedder):
    index(photo_dir, embedder=embedder, progress=False)
    searcher = Searcher(photo_dir, embedder=embedder)
    top = searcher.search_text("a red car", k=2)
    assert [r["path"] for r in top] == ["trip/red.jpg", "reddish.png"]
    assert searcher.search_text("blue sky", k=1)[0]["path"] == "trip/blue.jpg"


def test_similar_and_image_search(photo_dir, embedder):
    index(photo_dir, embedder=embedder, progress=False)
    searcher = Searcher(photo_dir, embedder=embedder)
    red_id = next(r["id"] for r in searcher.search_text("red", k=1))
    similar = searcher.similar(red_id, k=2)
    assert [r["path"] for r in similar] == ["trip/red.jpg", "reddish.png"]

    query = Image.new("RGB", (10, 10), (20, 190, 50))
    assert searcher.search_image(query, k=1)[0]["path"] == "trip/green.jpg"


def test_year_filter_excludes_undated(photo_dir, embedder):
    index(photo_dir, embedder=embedder, progress=False)
    searcher = Searcher(photo_dir, embedder=embedder)
    assert searcher.search_text("red", year_from=2000) == []  # synthetic images have no EXIF date
