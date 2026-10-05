import io

from fastapi.testclient import TestClient
from PIL import Image

from chitra.indexer import index
from chitra.search import Searcher
from chitra.server import create_app


def make_client(photo_dir, embedder):
    index(photo_dir, embedder=embedder, progress=False)
    return TestClient(create_app(Searcher(photo_dir, embedder=embedder)))


def test_api_end_to_end(photo_dir, embedder):
    client = make_client(photo_dir, embedder)

    stats = client.get("/api/stats").json()
    assert (stats["count"], stats["failed"]) == (4, 1)

    results = client.get("/api/search", params={"q": "green leaves", "k": 1}).json()["results"]
    assert results[0]["path"] == "trip/green.jpg"
    image_id = results[0]["id"]

    assert client.get(f"/api/thumb/{image_id}").headers["content-type"] == "image/jpeg"
    assert client.get(f"/api/image/{image_id}").status_code == 200
    assert client.get(f"/api/similar/{image_id}").json()["results"][0]["id"] == image_id
    assert client.get("/api/image/99999").status_code == 404

    buf = io.BytesIO()
    Image.new("RGB", (10, 10), (30, 40, 220)).save(buf, "PNG")
    hits = client.post("/api/search-image", files={"file": ("q.png", buf.getvalue(), "image/png")}).json()["results"]
    assert hits[0]["path"] == "trip/blue.jpg"


def test_home_page_served(photo_dir, embedder):
    client = make_client(photo_dir, embedder)
    assert "Chitra" in client.get("/").text
    assert client.get("/static/app.js").status_code == 200
